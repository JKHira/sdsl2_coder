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


def _is_explicit_empty_registry(data: object) -> bool:
    if isinstance(data, dict):
        entries = data.get("entries")
        if isinstance(entries, list) and len(entries) == 0:
            return True
        tokens = data.get("tokens")
        if isinstance(tokens, list) and len(tokens) == 0:
            return True
    if isinstance(data, list) and len(data) == 0:
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


def _collect_registry_entries(
    data: object,
    prefix: str,
    diags: list[Diagnostic],
) -> tuple[set[str], list[tuple[str, str]]]:
    tokens: set[str] = set()
    entries: list[tuple[str, str]] = []
    items: list[object] = []
    if isinstance(data, dict):
        if isinstance(data.get("entries"), list):
            items = data.get("entries")  # type: ignore[assignment]
        else:
            keys = [k for k in data.keys() if isinstance(k, str)]
            if keys and all(k.startswith(prefix) for k in keys):
                for key in keys:
                    value = data.get(key)
                    items.append({"token": key, "target": value})
            elif isinstance(data.get("tokens"), list):
                items = data.get("tokens")  # type: ignore[assignment]
    elif isinstance(data, list):
        items = data

    for idx, item in enumerate(items):
        if isinstance(item, str):
            if not item.startswith(prefix):
                _diag(
                    diags,
                    "E_TOKEN_REGISTRY_ENTRY_INVALID",
                    "registry token invalid",
                    f"{prefix}*",
                    str(item),
                    json_pointer("entries", str(idx)),
                )
                continue
            tokens.add(item)
            _diag(
                diags,
                "E_TOKEN_REGISTRY_TARGET_MISSING",
                "registry target missing",
                "token + target",
                "missing",
                json_pointer("entries", str(idx), "target"),
            )
            continue
        if isinstance(item, dict):
            token = item.get("token")
            target = item.get("target")
            if not isinstance(token, str) or not token.startswith(prefix):
                _diag(
                    diags,
                    "E_TOKEN_REGISTRY_ENTRY_INVALID",
                    "registry token invalid",
                    f"{prefix}*",
                    str(token),
                    json_pointer("entries", str(idx), "token"),
                )
                continue
            tokens.add(token)
            if not isinstance(target, str) or not target:
                _diag(
                    diags,
                    "E_TOKEN_REGISTRY_TARGET_MISSING",
                    "registry target missing",
                    "token + target",
                    str(target),
                    json_pointer("entries", str(idx), "target"),
                )
                continue
            entries.append((token, target))
            continue
        _diag(
            diags,
            "E_TOKEN_REGISTRY_ENTRY_INVALID",
            "registry entry invalid",
            "token string or {token,target}",
            type(item).__name__,
            json_pointer("entries", str(idx)),
        )
    return tokens, entries


def _decode_json_pointer(pointer: str) -> list[str] | None:
    if pointer == "/":
        return []
    if not pointer.startswith("/"):
        return None
    parts = pointer.split("/")[1:]
    decoded: list[str] = []
    for part in parts:
        if "~" in part:
            part = part.replace("~1", "/").replace("~0", "~")
        decoded.append(part)
    return decoded


def _validate_target(
    project_root: Path,
    token: str,
    target: str,
    hard_diags: list[Diagnostic],
    soft_diags: list[Diagnostic],
    fail_on_unresolved: bool,
) -> None:
    if target == "UNRESOLVED#/":
        if fail_on_unresolved:
            _diag(
                hard_diags,
                "E_TOKEN_REGISTRY_TARGET_UNRESOLVED",
                "registry target unresolved",
                "resolved target",
                target,
                json_pointer("targets", token),
            )
        else:
            _diag(
                soft_diags,
                "E_TOKEN_REGISTRY_TARGET_UNRESOLVED",
                "registry target unresolved",
                "resolved target",
                target,
                json_pointer("targets", token),
            )
        return
    if "#" not in target:
        _diag(
            hard_diags,
            "E_TOKEN_REGISTRY_TARGET_INVALID",
            "target must contain #",
            "<path>#/<json_pointer>",
            target,
            json_pointer("targets", token),
        )
        return
    path_part, pointer = target.split("#", 1)
    if not path_part or path_part.startswith("/") or ".." in Path(path_part).parts:
        _diag(
            hard_diags,
            "E_TOKEN_REGISTRY_TARGET_INVALID",
            "target path must be repo-relative",
            "repo-relative path",
            target,
            json_pointer("targets", token),
        )
        return
    if not pointer.startswith("/"):
        _diag(
            hard_diags,
            "E_TOKEN_REGISTRY_TARGET_INVALID",
            "json_pointer must start with '/'",
            "#/<json_pointer>",
            target,
            json_pointer("targets", token),
        )
        return
    if not path_part.endswith(".json"):
        _diag(
            hard_diags,
            "E_TOKEN_REGISTRY_TARGET_INVALID",
            "target path must be .json",
            "*.json",
            target,
            json_pointer("targets", token),
        )
        return
    path = _resolve_path(project_root, path_part)
    try:
        _ensure_inside(project_root, path, "E_TOKEN_REGISTRY_TARGET_OUTSIDE_PROJECT")
    except ValueError as exc:
        _diag(
            hard_diags,
            str(exc),
            "target path under project_root",
            "project_root/...",
            str(path),
            json_pointer("targets", token),
        )
        return
    if path.is_symlink() or _has_symlink_parent(path, project_root):
        _diag(
            hard_diags,
            "E_TOKEN_REGISTRY_TARGET_SYMLINK",
            "target path must not be symlink",
            "non-symlink",
            str(path),
            json_pointer("targets", token),
        )
        return
    if not path.exists():
        _diag(
            hard_diags,
            "E_TOKEN_REGISTRY_TARGET_FILE_NOT_FOUND",
            "target file not found",
            "existing file",
            str(path),
            json_pointer("targets", token),
        )
        return
    if not path.is_file():
        _diag(
            hard_diags,
            "E_TOKEN_REGISTRY_TARGET_FILE_NOT_FILE",
            "target path must be file",
            "file",
            str(path),
            json_pointer("targets", token),
        )
        return
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        _diag(
            hard_diags,
            "E_TOKEN_REGISTRY_TARGET_JSON_INVALID",
            "target file must be valid JSON",
            "valid JSON",
            str(exc),
            json_pointer("targets", token),
        )
        return
    segments = _decode_json_pointer(pointer)
    if segments is None:
        _diag(
            hard_diags,
            "E_TOKEN_REGISTRY_TARGET_POINTER_INVALID",
            "json_pointer invalid",
            "#/<json_pointer>",
            target,
            json_pointer("targets", token),
        )
        return
    current: object = data
    for segment in segments:
        if isinstance(current, dict):
            if segment not in current:
                _diag(
                    hard_diags,
                    "E_TOKEN_REGISTRY_TARGET_POINTER_MISSING",
                    "json_pointer target missing",
                    pointer,
                    target,
                    json_pointer("targets", token),
                )
                return
            current = current[segment]
            continue
        if isinstance(current, list):
            if not segment.isdigit():
                _diag(
                    hard_diags,
                    "E_TOKEN_REGISTRY_TARGET_POINTER_INVALID",
                    "json_pointer index invalid",
                    "integer index",
                    segment,
                    json_pointer("targets", token),
                )
                return
            idx = int(segment)
            if idx < 0 or idx >= len(current):
                _diag(
                    hard_diags,
                    "E_TOKEN_REGISTRY_TARGET_POINTER_MISSING",
                    "json_pointer index out of range",
                    pointer,
                    target,
                    json_pointer("targets", token),
                )
                return
            current = current[idx]
            continue
        _diag(
            hard_diags,
            "E_TOKEN_REGISTRY_TARGET_POINTER_INVALID",
            "json_pointer target not indexable",
            "object or list",
            type(current).__name__,
            json_pointer("targets", token),
        )
        return


def _load_registry_tokens(
    project_root: Path,
    path: Path,
    prefix: str,
    diags: list[Diagnostic],
    missing_code: str,
    invalid_code: str,
) -> tuple[set[str], list[tuple[str, str]]]:
    try:
        _ensure_inside(project_root, path, "E_TOKEN_REGISTRY_PATH_OUTSIDE_PROJECT")
    except ValueError as exc:
        _diag(diags, str(exc), "registry path under project_root", "project_root/...", str(path), json_pointer())
        return set(), []
    if not path.exists():
        _diag(diags, missing_code, "registry file not found", "existing file", str(path), json_pointer())
        return set(), []
    if path.is_symlink() or _has_symlink_parent(path, project_root):
        _diag(diags, "E_TOKEN_REGISTRY_SYMLINK", "registry file is symlink", "non-symlink", str(path), json_pointer())
        return set(), []
    data = load_yaml(path)
    explicit_empty = _is_explicit_empty_registry(data)
    tokens, entries = _collect_registry_entries(data, prefix, diags)
    if not tokens and not explicit_empty:
        _diag(
            diags,
            invalid_code,
            "registry has no valid tokens",
            f"{prefix}* entries",
            str(path),
            json_pointer(),
        )
    return tokens, entries


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
    ap.add_argument(
        "--fail-on-unresolved",
        action="store_true",
        help="Treat UNRESOLVED#/ targets as failure",
    )
    args = ap.parse_args()

    project_root = Path(args.project_root).resolve() if args.project_root else ROOT
    ssot_registry = _resolve_path(project_root, args.ssot_registry)
    contract_registry = _resolve_path(project_root, args.contract_registry)

    hard_diags: list[Diagnostic] = []
    soft_diags: list[Diagnostic] = []
    ssot_tokens, ssot_entries = _load_registry_tokens(
        project_root,
        ssot_registry,
        "SSOT.",
        hard_diags,
        "E_TOKEN_REGISTRY_SSOT_REGISTRY_NOT_FOUND",
        "E_TOKEN_REGISTRY_SSOT_REGISTRY_INVALID",
    )
    contract_tokens, contract_entries = _load_registry_tokens(
        project_root,
        contract_registry,
        "CONTRACT.",
        hard_diags,
        "E_TOKEN_REGISTRY_CONTRACT_REGISTRY_NOT_FOUND",
        "E_TOKEN_REGISTRY_CONTRACT_REGISTRY_INVALID",
    )

    ssot_root = project_root / "sdsl2"
    contract_used, ssot_used = _collect_tokens_from_files(ssot_root, hard_diags)

    if not ssot_used and not ssot_tokens:
        ssot_tokens = set()
    if not contract_used and not contract_tokens:
        contract_tokens = set()

    for token in sorted(ssot_used):
        if token not in ssot_tokens:
            _diag(
                hard_diags,
                "E_TOKEN_REGISTRY_SSOT_TOKEN_MISSING",
                "SSOT token missing from registry",
                "registry token",
                token,
                json_pointer("ssot_tokens", token),
            )

    for token in sorted(contract_used):
        if token not in contract_tokens:
            _diag(
                hard_diags,
                "E_TOKEN_REGISTRY_CONTRACT_TOKEN_MISSING",
                "CONTRACT token missing from registry",
                "registry token",
                token,
                json_pointer("contract_tokens", token),
            )

    for token, target in ssot_entries:
        _validate_target(project_root, token, target, hard_diags, soft_diags, args.fail_on_unresolved)
    for token, target in contract_entries:
        _validate_target(project_root, token, target, hard_diags, soft_diags, args.fail_on_unresolved)

    if hard_diags:
        _print_diags(hard_diags + soft_diags)
        return 2
    if soft_diags:
        _print_diags(soft_diags)
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
