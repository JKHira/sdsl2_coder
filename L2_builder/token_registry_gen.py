#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sdslv2_builder.input_hash import compute_input_hash
from sdslv2_builder.io_atomic import atomic_write_text
from sdslv2_builder.lint import _capture_metadata, _parse_metadata_pairs, _split_list_items
from sdslv2_builder.op_yaml import load_yaml
from sdslv2_builder.refs import parse_contract_ref, parse_ssot_ref


def _git_rev(root: Path) -> str:
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return "UNKNOWN"
    if proc.returncode != 0:
        return "UNKNOWN"
    return proc.stdout.strip() or "UNKNOWN"


def _resolve_path(project_root: Path, raw: str) -> Path:
    path = Path(raw)
    if not path.is_absolute():
        path = (project_root / path).resolve()
    return path


def _ensure_inside(project_root: Path, path: Path, code: str) -> None:
    try:
        path.resolve().relative_to(project_root.resolve())
    except ValueError as exc:
        raise ValueError(code) from exc


def _has_symlink_parent(path: Path, stop: Path) -> bool:
    for parent in [path, *path.parents]:
        if parent == stop:
            break
        if parent.is_symlink():
            return True
    return False


def _extract_tokens_from_value(value: str) -> tuple[set[str], set[str]]:
    contract_tokens: set[str] = set()
    ssot_tokens: set[str] = set()
    items: list[str]
    if value.strip().startswith("[") and value.strip().endswith("]"):
        items = _split_list_items(value)
    else:
        items = [value]
    for item in items:
        raw = item.strip()
        if len(raw) >= 2 and raw[0] == raw[-1] == '"':
            raw = raw[1:-1]
        contract = parse_contract_ref(raw)
        if contract:
            contract_tokens.add(contract.token)
        ssot = parse_ssot_ref(raw)
        if ssot:
            ssot_tokens.add(ssot.token)
    return contract_tokens, ssot_tokens


def _collect_tokens_from_sdsl(project_root: Path) -> tuple[set[str], set[str], list[Path]]:
    ssot_root = project_root / "sdsl2"
    contract_tokens: set[str] = set()
    ssot_tokens: set[str] = set()
    inputs: list[Path] = []
    if not ssot_root.exists():
        return contract_tokens, ssot_tokens, inputs
    if ssot_root.is_symlink() or _has_symlink_parent(ssot_root, project_root):
        raise ValueError("E_REGISTRY_GEN_SSOT_SYMLINK")
    for path in sorted(ssot_root.rglob("*.sdsl2")):
        if not path.is_file():
            continue
        if path.is_symlink() or _has_symlink_parent(path, ssot_root):
            raise ValueError("E_REGISTRY_GEN_SSOT_SYMLINK")
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError) as exc:
            raise ValueError(f"E_REGISTRY_GEN_SSOT_READ_FAILED:{exc}") from exc
        inputs.append(path)
        for idx, line in enumerate(lines):
            stripped = line.lstrip()
            if stripped == "" or stripped.startswith("//") or not stripped.startswith("@"):
                continue
            brace_idx = line.find("{")
            if brace_idx == -1:
                continue
            try:
                meta, _ = _capture_metadata(lines, idx, brace_idx)
            except Exception as exc:
                raise ValueError(f"E_REGISTRY_GEN_METADATA_PARSE_FAILED:{path}:{idx + 1}:{exc}") from exc
            pairs = _parse_metadata_pairs(meta)
            for _, value in pairs:
                contract, ssot = _extract_tokens_from_value(value)
                contract_tokens.update(contract)
                ssot_tokens.update(ssot)
    return contract_tokens, ssot_tokens, inputs


def _load_token_map(path: Path, prefix: str) -> dict[str, str]:
    data = load_yaml(path)
    mapping: dict[str, str] = {}
    if isinstance(data, dict):
        entries = data.get("entries")
        if isinstance(entries, list):
            data = entries
        elif all(isinstance(k, str) for k in data.keys()):
            for key, value in data.items():
                if not isinstance(key, str) or not key.startswith(prefix):
                    continue
                if isinstance(value, str):
                    mapping[key] = value
            return mapping
        else:
            data = []
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                token = item.get("token")
                target = item.get("target")
                if isinstance(token, str) and token.startswith(prefix) and isinstance(target, str):
                    mapping[token] = target
            elif isinstance(item, str) and item.startswith(prefix):
                mapping[item] = "UNRESOLVED#/"
    return mapping


def _load_map_with_checks(
    project_root: Path,
    raw: str | None,
    prefix: str,
    extra_inputs: list[Path],
    default_rel: str | None = None,
) -> dict[str, str]:
    if raw is None:
        if not default_rel:
            return {}
        candidate = (project_root / default_rel).resolve()
        if not candidate.exists():
            return {}
        path = candidate
    else:
        path = _resolve_path(project_root, raw)
        if not path.exists():
            raise ValueError("E_REGISTRY_GEN_MAP_NOT_FOUND")
    try:
        _ensure_inside(project_root, path, "E_REGISTRY_GEN_MAP_OUTSIDE_PROJECT")
    except ValueError as exc:
        raise ValueError(str(exc)) from exc
    if path.is_symlink() or _has_symlink_parent(path, project_root):
        raise ValueError("E_REGISTRY_GEN_MAP_SYMLINK")
    if path.is_dir():
        raise ValueError("E_REGISTRY_GEN_MAP_IS_DIR")
    mapping = _load_token_map(path, prefix)
    extra_inputs.append(path)
    return mapping


def _build_registry_entries(
    used_tokens: set[str],
    mapping: dict[str, str],
    allow_unresolved: bool,
) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    tokens = set(mapping.keys())
    tokens.update(used_tokens)
    for token in sorted(tokens):
        target = mapping.get(token)
        if target is None:
            if not allow_unresolved and token in used_tokens:
                raise ValueError("E_REGISTRY_GEN_MAPPING_REQUIRED")
            target = "UNRESOLVED#/"
        entries.append({"token": token, "target": target})
    return entries


def _write_registry(
    path: Path,
    project_root: Path,
    entries: list[dict[str, str]],
    extra_inputs: list[Path],
    generator_id: str,
) -> None:
    try:
        _ensure_inside(project_root, path, "E_REGISTRY_GEN_OUTPUT_OUTSIDE_PROJECT")
    except ValueError as exc:
        raise ValueError(str(exc)) from exc
    allowed_root = (project_root / "OUTPUT" / "ssot").resolve()
    try:
        path.resolve().relative_to(allowed_root)
    except ValueError as exc:
        raise ValueError("E_REGISTRY_GEN_OUTPUT_PATH_INVALID") from exc
    if path.exists() and path.is_symlink():
        raise ValueError("E_REGISTRY_GEN_OUTPUT_SYMLINK")
    if path.exists() and path.is_dir():
        raise ValueError("E_REGISTRY_GEN_OUTPUT_IS_DIR")
    if _has_symlink_parent(path, project_root):
        raise ValueError("E_REGISTRY_GEN_OUTPUT_SYMLINK_PARENT")
    if not str(path).endswith(".json"):
        raise ValueError("E_REGISTRY_GEN_OUTPUT_INVALID")
    out_parent = path.parent
    out_parent.mkdir(parents=True, exist_ok=True)

    try:
        input_hash = compute_input_hash(
            project_root,
            include_decisions=False,
            extra_inputs=extra_inputs,
        )
    except (FileNotFoundError, ValueError) as exc:
        raise ValueError(f"E_REGISTRY_GEN_INPUT_HASH_FAILED:{exc}") from exc

    payload = {
        "schema_version": "1.0",
        "source_rev": _git_rev(project_root),
        "input_hash": input_hash.input_hash,
        "generator_id": generator_id,
        "entries": entries,
    }
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    atomic_write_text(path, text, symlink_code="E_REGISTRY_GEN_OUTPUT_SYMLINK")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--project-root",
        default=None,
        help="Project root (defaults to repo root)",
    )
    ap.add_argument(
        "--ssot-map",
        default=None,
        help="Mapping file for SSOT registry entries",
    )
    ap.add_argument(
        "--contract-map",
        default=None,
        help="Mapping file for Contract registry entries",
    )
    ap.add_argument(
        "--allow-unresolved",
        action="store_true",
        help="Allow unresolved targets for used tokens",
    )
    ap.add_argument(
        "--ssot-out",
        default="OUTPUT/ssot/ssot_registry.json",
        help="Output path for SSOT registry (fixed under OUTPUT/ssot)",
    )
    ap.add_argument(
        "--contract-out",
        default="OUTPUT/ssot/contract_registry.json",
        help="Output path for Contract registry (fixed under OUTPUT/ssot)",
    )
    args = ap.parse_args()

    project_root = Path(args.project_root).resolve() if args.project_root else ROOT
    output_root = project_root / "OUTPUT"
    output_ssot = output_root / "ssot"
    if output_root.is_symlink() or _has_symlink_parent(output_root, project_root):
        print("E_REGISTRY_GEN_OUTPUT_SYMLINK", file=sys.stderr)
        return 2
    if output_ssot.is_symlink() or _has_symlink_parent(output_ssot, project_root):
        print("E_REGISTRY_GEN_OUTPUT_SYMLINK", file=sys.stderr)
        return 2
    ssot_out = _resolve_path(project_root, args.ssot_out)
    contract_out = _resolve_path(project_root, args.contract_out)

    try:
        contract_used, ssot_used, sdsl_inputs = _collect_tokens_from_sdsl(project_root)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    ssot_map: dict[str, str] = {}
    contract_map: dict[str, str] = {}
    extra_inputs: list[Path] = []
    extra_inputs.extend(sdsl_inputs)
    try:
        ssot_map = _load_map_with_checks(
            project_root,
            args.ssot_map,
            "SSOT.",
            extra_inputs,
            default_rel="OUTPUT/ssot/ssot_registry_map.json",
        )
        contract_map = _load_map_with_checks(
            project_root,
            args.contract_map,
            "CONTRACT.",
            extra_inputs,
            default_rel="OUTPUT/ssot/contract_registry_map.json",
        )
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    try:
        ssot_entries = _build_registry_entries(ssot_used, ssot_map, args.allow_unresolved)
        contract_entries = _build_registry_entries(contract_used, contract_map, args.allow_unresolved)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    try:
        _write_registry(ssot_out, project_root, ssot_entries, extra_inputs, "L2_builder.token_registry_gen.ssot")
        _write_registry(contract_out, project_root, contract_entries, extra_inputs, "L2_builder.token_registry_gen.contract")
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
