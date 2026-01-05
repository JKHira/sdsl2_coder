#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sdslv2_builder.errors import Diagnostic, json_pointer
from sdslv2_builder.lint import _capture_metadata, _parse_metadata_pairs, _split_list_items
from sdslv2_builder.op_yaml import load_yaml
from sdslv2_builder.refs import parse_contract_ref, parse_ssot_ref

ANNOTATION_KIND_RE = re.compile(r"^\s*@(?P<kind>[A-Za-z_][A-Za-z0-9_]*)\b")


def _diag(diags: list[Diagnostic], code: str, message: str, expected: str, got: str, path: str) -> None:
    diags.append(Diagnostic(code=code, message=message, expected=expected, got=got, path=path))


def _print_diags(diags: list[Diagnostic]) -> None:
    payload = [d.to_dict() for d in diags]
    print(json.dumps(payload, ensure_ascii=False, indent=2), file=sys.stderr)


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


def _parse_annotations(lines: list[str]) -> list[tuple[str, dict[str, str], int, int]]:
    annotations: list[tuple[str, dict[str, str], int, int]] = []
    for idx, line in enumerate(lines):
        stripped = line.lstrip()
        if stripped == "" or stripped.startswith("//"):
            continue
        if not stripped.startswith("@"):
            continue
        match = ANNOTATION_KIND_RE.match(stripped)
        if not match:
            continue
        kind = match.group("kind")
        brace_idx = line.find("{")
        if brace_idx == -1:
            raise ValueError(f"E_TOKEN_REGISTRY_METADATA_MISSING: line {idx + 1}")
        meta, end_line = _capture_metadata(lines, idx, brace_idx)
        pairs = _parse_metadata_pairs(meta)
        meta_map: dict[str, str] = {}
        for key, value in pairs:
            if key in meta_map:
                raise ValueError(f"E_TOKEN_REGISTRY_DUPLICATE_KEY: line {idx + 1} key {key}")
            meta_map[key] = value
        annotations.append((kind, meta_map, idx, end_line))
    return annotations


def _strip_quotes(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] == '"':
        return value[1:-1]
    return value


def _extract_tokens_from_value(value: str) -> tuple[set[str], set[str]]:
    contract_tokens: set[str] = set()
    ssot_tokens: set[str] = set()
    items: list[str]
    if value.strip().startswith("[") and value.strip().endswith("]"):
        items = _split_list_items(value)
    else:
        items = [value]
    for item in items:
        raw = _strip_quotes(item) or ""
        contract = parse_contract_ref(raw)
        if contract:
            contract_tokens.add(contract.token)
        ssot = parse_ssot_ref(raw)
        if ssot:
            ssot_tokens.add(ssot.token)
    return contract_tokens, ssot_tokens


def _collect_tokens_from_files(
    root: Path,
    diags: list[Diagnostic],
) -> tuple[set[str], set[str]]:
    contract_tokens: set[str] = set()
    ssot_tokens: set[str] = set()
    if not root.exists():
        return contract_tokens, ssot_tokens
    if root.is_symlink() or _has_symlink_parent(root, root.parent):
        _diag(
            diags,
            "E_TOKEN_REGISTRY_SYMLINK",
            "symlink not allowed under sdsl2 root",
            "non-symlink",
            str(root),
            json_pointer(),
        )
        return contract_tokens, ssot_tokens
    for path in sorted(root.rglob("*.sdsl2")):
        if not path.is_file():
            continue
        if path.is_symlink() or _has_symlink_parent(path, root):
            _diag(
                diags,
                "E_TOKEN_REGISTRY_SYMLINK",
                "symlink not allowed under sdsl2 root",
                "non-symlink",
                str(path),
                json_pointer(),
            )
            continue
        text = path.read_text(encoding="utf-8")
        try:
            annotations = _parse_annotations(text.splitlines())
        except ValueError as exc:
            _diag(
                diags,
                "E_TOKEN_REGISTRY_PARSE_FAILED",
                "annotation parse failed",
                "valid @Kind { ... } metadata",
                str(exc),
                path.as_posix(),
            )
            continue
        for _, meta, _, _ in annotations:
            for value in meta.values():
                contract, ssot = _extract_tokens_from_value(value)
                contract_tokens.update(contract)
                ssot_tokens.update(ssot)
    return contract_tokens, ssot_tokens


def _extract_tokens_from_registry(data: object, prefix: str) -> set[str]:
    tokens: set[str] = set()
    if isinstance(data, dict):
        entries = data.get("entries")
        if isinstance(entries, list):
            data = entries
        else:
            keys = [k for k in data.keys() if isinstance(k, str)]
            if keys and all(k.startswith(prefix) for k in keys):
                tokens.update(keys)
                return tokens
            if "tokens" in data and isinstance(data.get("tokens"), list):
                data = data.get("tokens")
            else:
                data = []
    if isinstance(data, list):
        for item in data:
            if isinstance(item, str) and item.startswith(prefix):
                tokens.add(item)
            elif isinstance(item, dict):
                token = item.get("token")
                if isinstance(token, str) and token.startswith(prefix):
                    tokens.add(token)
    return tokens


def _load_registry_tokens(
    project_root: Path,
    path: Path,
    prefix: str,
    diags: list[Diagnostic],
    missing_code: str,
    invalid_code: str,
) -> set[str]:
    try:
        _ensure_inside(project_root, path, "E_TOKEN_REGISTRY_PATH_OUTSIDE_PROJECT")
    except ValueError as exc:
        _diag(diags, str(exc), "registry path under project_root", "project_root/...", str(path), json_pointer())
        return set()
    if not path.exists():
        _diag(diags, missing_code, "registry file not found", "existing file", str(path), json_pointer())
        return set()
    if path.is_symlink():
        _diag(diags, "E_TOKEN_REGISTRY_SYMLINK", "registry file is symlink", "non-symlink", str(path), json_pointer())
        return set()
    data = load_yaml(path)
    tokens = _extract_tokens_from_registry(data, prefix)
    if not tokens:
        _diag(
            diags,
            invalid_code,
            "registry has no valid tokens",
            f"{prefix}* entries",
            str(path),
            json_pointer(),
        )
    return tokens


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--project-root",
        default=None,
        help="Project root (defaults to repo root); inputs can be relative to it",
    )
    ap.add_argument(
        "--ssot-registry",
        default="OUTPUT/ssot/ssot_registry.json",
        help="SSOT registry path",
    )
    ap.add_argument(
        "--contract-registry",
        default="OUTPUT/ssot/contract_registry.json",
        help="Contract registry path",
    )
    args = ap.parse_args()

    project_root = Path(args.project_root).resolve() if args.project_root else ROOT
    ssot_registry = _resolve_path(project_root, args.ssot_registry)
    contract_registry = _resolve_path(project_root, args.contract_registry)

    diags: list[Diagnostic] = []
    ssot_tokens = _load_registry_tokens(
        project_root,
        ssot_registry,
        "SSOT.",
        diags,
        "E_TOKEN_REGISTRY_SSOT_REGISTRY_NOT_FOUND",
        "E_TOKEN_REGISTRY_SSOT_REGISTRY_INVALID",
    )
    contract_tokens = _load_registry_tokens(
        project_root,
        contract_registry,
        "CONTRACT.",
        diags,
        "E_TOKEN_REGISTRY_CONTRACT_REGISTRY_NOT_FOUND",
        "E_TOKEN_REGISTRY_CONTRACT_REGISTRY_INVALID",
    )

    ssot_root = project_root / "sdsl2"
    contract_used, ssot_used = _collect_tokens_from_files(ssot_root, diags)

    if not ssot_used and not ssot_tokens:
        ssot_tokens = set()
    if not contract_used and not contract_tokens:
        contract_tokens = set()

    for token in sorted(ssot_used):
        if token not in ssot_tokens:
            _diag(
                diags,
                "E_TOKEN_REGISTRY_SSOT_TOKEN_MISSING",
                "SSOT token missing from registry",
                "registry token",
                token,
                json_pointer("ssot_tokens", token),
            )

    for token in sorted(contract_used):
        if token not in contract_tokens:
            _diag(
                diags,
                "E_TOKEN_REGISTRY_CONTRACT_TOKEN_MISSING",
                "CONTRACT token missing from registry",
                "registry token",
                token,
                json_pointer("contract_tokens", token),
            )

    if diags:
        _print_diags(diags)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
