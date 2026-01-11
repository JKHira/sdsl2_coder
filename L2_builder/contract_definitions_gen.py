#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from hashlib import sha256
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sdslv2_builder.errors import Diagnostic, json_pointer
from sdslv2_builder.io_atomic import atomic_write_text
from sdslv2_builder.lint import _capture_metadata, _parse_metadata_pairs, _split_list_items
from sdslv2_builder.op_yaml import load_yaml
from sdslv2_builder.refs import parse_contract_ref

DEFAULT_EDGES = "decisions/edges.yaml"
DEFAULT_CONTRACTS = "decisions/contracts.yaml"
DEFAULT_OUT_DEFINITIONS = "OUTPUT/ssot/contract_definitions.json"
DEFAULT_OUT_MAP = "OUTPUT/ssot/contract_registry_map.json"


def _diag(diags: list[Diagnostic], code: str, message: str, expected: str, got: str, path: str) -> None:
    diags.append(Diagnostic(code=code, message=message, expected=expected, got=got, path=path))


def _print_diags(diags: list[Diagnostic]) -> None:
    payload = [d.to_dict() for d in diags]
    print(json.dumps(payload, ensure_ascii=False, indent=2), file=sys.stderr)


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


def _normalize_text(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _rel_path(root: Path, path: Path) -> str:
    rel = path.resolve().relative_to(root.resolve())
    return rel.as_posix()


def _content_hash(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    normalized = _normalize_text(text)
    return sha256(normalized.encode("utf-8")).hexdigest()


def _compute_input_hash(project_root: Path, inputs: list[Path]) -> str:
    parts: list[str] = []
    for path in sorted(dict.fromkeys(inputs), key=lambda p: _rel_path(project_root, p)):
        rel = _rel_path(project_root, path)
        digest = _content_hash(path)
        parts.append(f"{rel}\n{digest}\n")
    payload = "".join(parts)
    digest = sha256(payload.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def _strip_quotes(value: str) -> str:
    raw = value.strip()
    if len(raw) >= 2 and raw[0] == raw[-1] == '"':
        return raw[1:-1]
    return raw


def _extract_tokens_from_value(value: str) -> set[str]:
    items: list[str]
    if value.strip().startswith("[") and value.strip().endswith("]"):
        items = _split_list_items(value)
    else:
        items = [value]
    tokens: set[str] = set()
    for item in items:
        raw = _strip_quotes(item)
        ref = parse_contract_ref(raw)
        if ref:
            tokens.add(ref.token)
    return tokens


def _collect_tokens_from_edges(path: Path, diags: list[Diagnostic]) -> set[str]:
    tokens: set[str] = set()
    if not path.exists():
        return tokens
    if path.is_symlink() or _has_symlink_parent(path, path.parent):
        _diag(
            diags,
            "E_CONTRACT_DEF_EDGE_SYMLINK",
            "edges.yaml must not be symlink",
            "non-symlink",
            str(path),
            json_pointer(),
        )
        return tokens
    try:
        data = load_yaml(path)
    except Exception as exc:
        _diag(
            diags,
            "E_CONTRACT_DEF_EDGE_PARSE_FAILED",
            "edges.yaml parse failed",
            "valid YAML",
            str(exc),
            json_pointer(),
        )
        return tokens
    if not isinstance(data, dict):
        _diag(
            diags,
            "E_CONTRACT_DEF_EDGE_SCHEMA_INVALID",
            "edges.yaml must be object",
            "object",
            type(data).__name__,
            json_pointer(),
        )
        return tokens
    edges = data.get("edges")
    if not isinstance(edges, list):
        _diag(
            diags,
            "E_CONTRACT_DEF_EDGE_SCHEMA_INVALID",
            "edges must be list",
            "list",
            type(edges).__name__,
            json_pointer("edges"),
        )
        return tokens
    for idx, edge in enumerate(edges):
        if not isinstance(edge, dict):
            _diag(
                diags,
                "E_CONTRACT_DEF_EDGE_ITEM_INVALID",
                "edge must be object",
                "object",
                type(edge).__name__,
                json_pointer("edges", str(idx)),
            )
            continue
        refs = edge.get("contract_refs")
        if not isinstance(refs, list):
            _diag(
                diags,
                "E_CONTRACT_DEF_EDGE_REFS_INVALID",
                "contract_refs must be list",
                "list",
                type(refs).__name__,
                json_pointer("edges", str(idx), "contract_refs"),
            )
            continue
        for jdx, ref in enumerate(refs):
            if not isinstance(ref, str):
                _diag(
                    diags,
                    "E_CONTRACT_DEF_TOKEN_INVALID",
                    "contract_refs item must be string",
                    "CONTRACT.*",
                    type(ref).__name__,
                    json_pointer("edges", str(idx), "contract_refs", str(jdx)),
                )
                continue
            token = parse_contract_ref(ref)
            if not token:
                _diag(
                    diags,
                    "E_CONTRACT_DEF_TOKEN_INVALID",
                    "contract_refs token invalid",
                    "CONTRACT.*",
                    ref,
                    json_pointer("edges", str(idx), "contract_refs", str(jdx)),
                )
                continue
            tokens.add(token.token)
    return tokens


def _collect_tokens_from_contracts(path: Path, diags: list[Diagnostic]) -> set[str]:
    tokens: set[str] = set()
    if not path.exists():
        return tokens
    if path.is_symlink() or _has_symlink_parent(path, path.parent):
        _diag(
            diags,
            "E_CONTRACT_DEF_CONTRACTS_SYMLINK",
            "contracts.yaml must not be symlink",
            "non-symlink",
            str(path),
            json_pointer(),
        )
        return tokens
    try:
        data = load_yaml(path)
    except Exception as exc:
        _diag(
            diags,
            "E_CONTRACT_DEF_CONTRACTS_PARSE_FAILED",
            "contracts.yaml parse failed",
            "valid YAML",
            str(exc),
            json_pointer(),
        )
        return tokens
    if not isinstance(data, dict):
        _diag(
            diags,
            "E_CONTRACT_DEF_CONTRACTS_SCHEMA_INVALID",
            "contracts.yaml must be object",
            "object",
            type(data).__name__,
            json_pointer(),
        )
        return tokens
    rules = data.get("rules")
    if not isinstance(rules, list):
        _diag(
            diags,
            "E_CONTRACT_DEF_CONTRACTS_SCHEMA_INVALID",
            "rules must be list",
            "list",
            type(rules).__name__,
            json_pointer("rules"),
        )
        return tokens
    for idx, rule in enumerate(rules):
        if not isinstance(rule, dict):
            _diag(
                diags,
                "E_CONTRACT_DEF_RULE_INVALID",
                "rule must be object",
                "object",
                type(rule).__name__,
                json_pointer("rules", str(idx)),
            )
            continue
        contracts = rule.get("contract")
        if not isinstance(contracts, list):
            _diag(
                diags,
                "E_CONTRACT_DEF_RULE_INVALID",
                "rule.contract must be list",
                "list",
                type(contracts).__name__,
                json_pointer("rules", str(idx), "contract"),
            )
            continue
        for jdx, ref in enumerate(contracts):
            if not isinstance(ref, str):
                _diag(
                    diags,
                    "E_CONTRACT_DEF_TOKEN_INVALID",
                    "rule.contract item must be string",
                    "CONTRACT.*",
                    type(ref).__name__,
                    json_pointer("rules", str(idx), "contract", str(jdx)),
                )
                continue
            token = parse_contract_ref(ref)
            if not token:
                _diag(
                    diags,
                    "E_CONTRACT_DEF_TOKEN_INVALID",
                    "rule.contract token invalid",
                    "CONTRACT.*",
                    ref,
                    json_pointer("rules", str(idx), "contract", str(jdx)),
                )
                continue
            tokens.add(token.token)
    return tokens


def _collect_tokens_from_sdsl(project_root: Path, diags: list[Diagnostic]) -> tuple[set[str], list[Path]]:
    tokens: set[str] = set()
    inputs: list[Path] = []
    root = project_root / "sdsl2"
    if not root.exists():
        return tokens, inputs
    if root.is_symlink() or _has_symlink_parent(root, project_root):
        _diag(
            diags,
            "E_CONTRACT_DEF_SDSL_SYMLINK",
            "sdsl2 root must not be symlink",
            "non-symlink",
            str(root),
            json_pointer(),
        )
        return tokens, inputs
    for path in sorted(root.rglob("*.sdsl2")):
        if not path.is_file():
            continue
        if path.is_symlink() or _has_symlink_parent(path, root):
            _diag(
                diags,
                "E_CONTRACT_DEF_SDSL_SYMLINK",
                "sdsl2 file must not be symlink",
                "non-symlink",
                str(path),
                json_pointer(),
            )
            continue
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError as exc:
            _diag(
                diags,
                "E_CONTRACT_DEF_SDSL_READ_FAILED",
                "sdsl2 read failed",
                "readable file",
                str(exc),
                path.as_posix(),
            )
            continue
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
                pairs = _parse_metadata_pairs(meta)
            except ValueError as exc:
                _diag(
                    diags,
                    "E_CONTRACT_DEF_SDSL_PARSE_FAILED",
                    "metadata parse failed",
                    "valid @Kind { ... } metadata",
                    str(exc),
                    path.as_posix(),
                )
                continue
            for _, value in pairs:
                tokens.update(_extract_tokens_from_value(value))
    return tokens, inputs


def _escape_pointer(segment: str) -> str:
    return segment.replace("~", "~0").replace("/", "~1")


def _write_json(path: Path, payload: dict, symlink_code: str) -> None:
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    atomic_write_text(path, text, symlink_code=symlink_code)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project-root", default=None, help="Project root (defaults to repo root)")
    ap.add_argument("--edges", default=DEFAULT_EDGES, help="decisions/edges.yaml path")
    ap.add_argument("--contracts", default=DEFAULT_CONTRACTS, help="decisions/contracts.yaml path")
    ap.add_argument("--out-definitions", default=DEFAULT_OUT_DEFINITIONS, help="Output definitions JSON path")
    ap.add_argument("--out-map", default=DEFAULT_OUT_MAP, help="Output registry map JSON path")
    ap.add_argument("--schema-version", default="1.0", help="schema_version for definitions")
    ap.add_argument("--source-rev", default=None, help="Override git source_rev")
    ap.add_argument("--allow-unknown-source-rev", action="store_true", help="Allow UNKNOWN source_rev")
    args = ap.parse_args()

    project_root = Path(args.project_root).resolve() if args.project_root else ROOT
    edges_path = (project_root / args.edges).resolve()
    contracts_path = (project_root / args.contracts).resolve()
    out_definitions = (project_root / args.out_definitions).resolve()
    out_map = (project_root / args.out_map).resolve()

    try:
        _ensure_inside(project_root, edges_path, "E_CONTRACT_DEF_INPUT_OUTSIDE_PROJECT")
        _ensure_inside(project_root, contracts_path, "E_CONTRACT_DEF_INPUT_OUTSIDE_PROJECT")
        _ensure_inside(project_root, out_definitions, "E_CONTRACT_DEF_OUTPUT_OUTSIDE_PROJECT")
        _ensure_inside(project_root, out_map, "E_CONTRACT_DEF_OUTPUT_OUTSIDE_PROJECT")
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    allowed_root = (project_root / "OUTPUT" / "ssot").resolve()
    for out_path in (out_definitions, out_map):
        try:
            out_path.resolve().relative_to(allowed_root)
        except ValueError:
            print("E_CONTRACT_DEF_OUTPUT_PATH_INVALID", file=sys.stderr)
            return 2
        if out_path.exists() and out_path.is_symlink():
            print("E_CONTRACT_DEF_OUTPUT_SYMLINK", file=sys.stderr)
            return 2
        if out_path.exists() and out_path.is_dir():
            print("E_CONTRACT_DEF_OUTPUT_IS_DIR", file=sys.stderr)
            return 2
        if _has_symlink_parent(out_path, project_root):
            print("E_CONTRACT_DEF_OUTPUT_SYMLINK_PARENT", file=sys.stderr)
            return 2
        if not str(out_path).endswith(".json"):
            print("E_CONTRACT_DEF_OUTPUT_INVALID", file=sys.stderr)
            return 2

    source_rev = (args.source_rev or "").strip()
    if not source_rev:
        source_rev = _git_rev(project_root)
    if source_rev == "UNKNOWN" and not args.allow_unknown_source_rev:
        print("E_CONTRACT_DEF_SOURCE_REV_UNKNOWN", file=sys.stderr)
        return 2

    diags: list[Diagnostic] = []
    decision_tokens: set[str] = set()
    input_files: list[Path] = []

    if edges_path.exists():
        decision_tokens.update(_collect_tokens_from_edges(edges_path, diags))
        input_files.append(edges_path)
    if contracts_path.exists():
        decision_tokens.update(_collect_tokens_from_contracts(contracts_path, diags))
        input_files.append(contracts_path)

    sdsl_tokens, sdsl_inputs = _collect_tokens_from_sdsl(project_root, diags)
    input_files.extend(sdsl_inputs)

    if diags:
        _print_diags(diags)
        return 2

    tokens = sorted(decision_tokens.union(sdsl_tokens))
    token_entries = {
        token: {"summary": "Referenced by decisions/sdsl2"} for token in tokens
    }

    input_hash = _compute_input_hash(project_root, input_files)
    payload = {
        "schema_version": args.schema_version,
        "source_rev": source_rev,
        "input_hash": input_hash,
        "generator_id": "L2_builder.contract_definitions_gen",
        "tokens": token_entries,
    }

    registry_map: dict[str, str] = {
        "schema_version": args.schema_version,
        "source_rev": source_rev,
        "input_hash": input_hash,
        "generator_id": "L2_builder.contract_definitions_gen",
    }
    for token in tokens:
        pointer = "/tokens/" + _escape_pointer(token)
        registry_map[token] = f"{DEFAULT_OUT_DEFINITIONS}#{pointer}"

    out_definitions.parent.mkdir(parents=True, exist_ok=True)
    out_map.parent.mkdir(parents=True, exist_ok=True)
    try:
        _write_json(out_definitions, payload, "E_CONTRACT_DEF_OUTPUT_SYMLINK")
        _write_json(out_map, registry_map, "E_CONTRACT_DEF_OUTPUT_SYMLINK")
    except OSError as exc:
        print(f"E_CONTRACT_DEF_WRITE_FAILED:{exc}", file=sys.stderr)
        return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
