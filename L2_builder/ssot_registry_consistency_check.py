#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from L2_builder.common import ROOT as REPO_ROOT, ensure_inside, has_symlink_parent, resolve_path
from sdslv2_builder.errors import Diagnostic, json_pointer
from sdslv2_builder.refs import parse_ssot_ref

DEFAULT_REGISTRY = "OUTPUT/ssot/ssot_registry.json"
DEFAULT_DEFINITIONS = "OUTPUT/ssot/ssot_definitions.json"


def _diag(diags: list[Diagnostic], code: str, message: str, expected: str, got: str, path: str) -> None:
    diags.append(Diagnostic(code=code, message=message, expected=expected, got=got, path=path))


def _print_diags(diags: list[Diagnostic]) -> None:
    payload = [d.to_dict() for d in diags]
    print(json.dumps(payload, ensure_ascii=False, indent=2), file=sys.stderr)


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


def _resolve_pointer(data: object, pointer: str) -> bool:
    parts = _decode_json_pointer(pointer)
    if parts is None:
        return False
    current: object = data
    for segment in parts:
        if isinstance(current, dict):
            if segment not in current:
                return False
            current = current[segment]
            continue
        if isinstance(current, list):
            if not segment.isdigit():
                return False
            idx = int(segment)
            if idx < 0 or idx >= len(current):
                return False
            current = current[idx]
            continue
        return False
    return True


def _load_registry(data: object) -> list[tuple[str, str]]:
    entries: list[tuple[str, str]] = []
    items: list[object] = []
    if isinstance(data, dict):
        if isinstance(data.get("entries"), list):
            items = data.get("entries")  # type: ignore[assignment]
        else:
            keys = [k for k in data.keys() if isinstance(k, str)]
            if keys and all(k.startswith("SSOT.") for k in keys):
                for key in keys:
                    value = data.get(key)
                    if isinstance(value, str):
                        items.append({"token": key, "target": value})
    elif isinstance(data, list):
        items = data

    for item in items:
        if isinstance(item, dict):
            token = item.get("token")
            target = item.get("target")
            if isinstance(token, str) and isinstance(target, str):
                entries.append((token, target))
    return entries


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project-root", default=str(REPO_ROOT), help="Project root.")
    ap.add_argument("--registry", default=DEFAULT_REGISTRY, help="SSOT registry path.")
    ap.add_argument("--definitions", default=DEFAULT_DEFINITIONS, help="SSOT definitions path.")
    ap.add_argument("--allow-missing", action="store_true", help="Return OK if inputs missing.")
    args = ap.parse_args()

    project_root = Path(args.project_root).resolve()
    registry_path = resolve_path(project_root, args.registry)
    definitions_path = resolve_path(project_root, args.definitions)

    try:
        ensure_inside(project_root, registry_path, "E_SSOT_REGISTRY_INPUT_OUTSIDE_PROJECT")
        ensure_inside(project_root, definitions_path, "E_SSOT_REGISTRY_DEFINITIONS_OUTSIDE_PROJECT")
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    expected_registry = (project_root / DEFAULT_REGISTRY).resolve()
    expected_definitions = (project_root / DEFAULT_DEFINITIONS).resolve()
    if registry_path != expected_registry:
        print("E_SSOT_REGISTRY_PATH_INVALID", file=sys.stderr)
        return 2
    if definitions_path != expected_definitions:
        print("E_SSOT_REGISTRY_DEFINITIONS_PATH_INVALID", file=sys.stderr)
        return 2

    if not registry_path.exists() or not definitions_path.exists():
        if args.allow_missing:
            return 0
        missing = []
        if not registry_path.exists():
            missing.append("registry")
        if not definitions_path.exists():
            missing.append("definitions")
        _print_diags([
            Diagnostic(
                code="E_SSOT_REGISTRY_INPUT_NOT_FOUND",
                message="SSOT registry or definitions missing",
                expected="registry + definitions",
                got=",".join(missing),
                path=json_pointer(),
            )
        ])
        return 2

    if registry_path.is_dir() or definitions_path.is_dir():
        print("E_SSOT_REGISTRY_INPUT_IS_DIRECTORY", file=sys.stderr)
        return 2
    if (
        has_symlink_parent(registry_path, project_root)
        or registry_path.is_symlink()
        or has_symlink_parent(definitions_path, project_root)
        or definitions_path.is_symlink()
    ):
        print("E_SSOT_REGISTRY_INPUT_SYMLINK", file=sys.stderr)
        return 2

    try:
        registry_data = json.loads(registry_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        _print_diags([
            Diagnostic(
                code="E_SSOT_REGISTRY_JSON_INVALID",
                message="registry must be valid JSON",
                expected="valid JSON",
                got=str(exc),
                path=json_pointer(),
            )
        ])
        return 2

    try:
        definitions_data = json.loads(definitions_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        _print_diags([
            Diagnostic(
                code="E_SSOT_REGISTRY_DEFINITIONS_JSON_INVALID",
                message="definitions must be valid JSON",
                expected="valid JSON",
                got=str(exc),
                path=json_pointer(),
            )
        ])
        return 2

    expected_path = DEFAULT_DEFINITIONS
    diags: list[Diagnostic] = []
    entries = _load_registry(registry_data)
    for idx, (token, target) in enumerate(entries):
        if not parse_ssot_ref(token):
            _diag(
                diags,
                "E_SSOT_REGISTRY_TOKEN_INVALID",
                "registry token must be SSOT.*",
                "SSOT.*",
                token,
                json_pointer("entries", str(idx), "token"),
            )
            continue
        if "#" not in target:
            _diag(
                diags,
                "E_SSOT_REGISTRY_TARGET_INVALID",
                "target must contain #",
                "<path>#/<json_pointer>",
                target,
                json_pointer("entries", str(idx), "target"),
            )
            continue
        path_part, pointer = target.split("#", 1)
        if path_part != expected_path:
            _diag(
                diags,
                "E_SSOT_REGISTRY_TARGET_MISMATCH",
                "SSOT registry target must use ssot_definitions.json",
                expected_path,
                path_part,
                json_pointer("entries", str(idx), "target"),
            )
            continue
        if not pointer.startswith("/"):
            _diag(
                diags,
                "E_SSOT_REGISTRY_POINTER_INVALID",
                "json_pointer must start with '/'",
                "#/<json_pointer>",
                target,
                json_pointer("entries", str(idx), "target"),
            )
            continue
        if not _resolve_pointer(definitions_data, pointer):
            _diag(
                diags,
                "E_SSOT_REGISTRY_POINTER_MISSING",
                "json_pointer target missing",
                pointer,
                target,
                json_pointer("entries", str(idx), "target"),
            )

    if diags:
        _print_diags(diags)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
