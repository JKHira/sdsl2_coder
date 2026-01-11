#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
from hashlib import sha256
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sdslv2_builder.io_atomic import atomic_write_text

DEFAULT_DEFINITIONS = "ssot_kernel_builder/ssot_definitions.ts"
DEFAULT_OUT_DEFINITIONS = "OUTPUT/ssot/ssot_definitions.json"
DEFAULT_OUT_REGISTRY_MAP = "OUTPUT/ssot/ssot_registry_map.json"


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


def _extract_definitions_object(text: str) -> dict:
    anchor = "SSOT_DEFINITIONS"
    anchor_idx = text.find(anchor)
    if anchor_idx == -1:
        raise ValueError("E_SSOT_DEF_ANCHOR_NOT_FOUND")
    brace_start = text.find("{", anchor_idx)
    if brace_start == -1:
        raise ValueError("E_SSOT_DEF_OBJECT_START_NOT_FOUND")

    in_string = False
    escape = False
    in_line_comment = False
    in_block_comment = False
    depth = 0
    end_idx = None

    i = brace_start
    while i < len(text):
        ch = text[i]
        nxt = text[i + 1] if i + 1 < len(text) else ""

        if in_line_comment:
            if ch == "\n":
                in_line_comment = False
            i += 1
            continue
        if in_block_comment:
            if ch == "*" and nxt == "/":
                in_block_comment = False
                i += 2
                continue
            i += 1
            continue
        if in_string:
            if escape:
                escape = False
                i += 1
                continue
            if ch == "\\":
                escape = True
                i += 1
                continue
            if ch == '"':
                in_string = False
            i += 1
            continue

        if ch == "/" and nxt == "/":
            in_line_comment = True
            i += 2
            continue
        if ch == "/" and nxt == "*":
            in_block_comment = True
            i += 2
            continue
        if ch == '"':
            in_string = True
            i += 1
            continue
        if ch == "{":
            depth += 1
        if ch == "}":
            depth -= 1
            if depth == 0:
                end_idx = i
                break
        i += 1

    if end_idx is None:
        raise ValueError("E_SSOT_DEF_OBJECT_UNTERMINATED")

    json_text = text[brace_start : end_idx + 1]
    try:
        data = json.loads(json_text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"E_SSOT_DEF_JSON_INVALID:{exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("E_SSOT_DEF_JSON_NOT_OBJECT")
    return data


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
    for path in sorted(inputs, key=lambda p: _rel_path(project_root, p)):
        rel = _rel_path(project_root, path)
        digest = _content_hash(path)
        parts.append(f"{rel}\n{digest}\n")
    payload = "".join(parts)
    digest = sha256(payload.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def _escape_pointer(segment: str) -> str:
    return segment.replace("~", "~0").replace("/", "~1")


def _write_json(path: Path, payload: dict, symlink_code: str) -> None:
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    atomic_write_text(path, text, symlink_code=symlink_code)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project-root", default=None, help="Project root (defaults to repo root)")
    ap.add_argument(
        "--kernel-root",
        default=None,
        help="Kernel source root for ssot_definitions.ts (defaults to project root)",
    )
    ap.add_argument("--definitions", default=DEFAULT_DEFINITIONS, help="SSOT definitions TS path")
    ap.add_argument("--out-definitions", default=DEFAULT_OUT_DEFINITIONS, help="Output definitions JSON path")
    ap.add_argument("--out-registry-map", default=DEFAULT_OUT_REGISTRY_MAP, help="Output registry map JSON path")
    ap.add_argument("--schema-version", default="1.0", help="schema_version for distribution boundary")
    ap.add_argument("--source-rev", default=None, help="Override git source_rev")
    ap.add_argument("--allow-unknown-source-rev", action="store_true", help="Allow UNKNOWN source_rev")
    args = ap.parse_args()

    project_root = Path(args.project_root).resolve() if args.project_root else ROOT
    if args.kernel_root:
        raw_kernel = Path(args.kernel_root)
        kernel_root = (ROOT / raw_kernel).resolve() if not raw_kernel.is_absolute() else raw_kernel.resolve()
    else:
        kernel_root = project_root
    raw_definitions = Path(args.definitions)
    definitions_path = (
        raw_definitions.resolve()
        if raw_definitions.is_absolute()
        else (kernel_root / raw_definitions).resolve()
    )
    out_definitions = (project_root / args.out_definitions).resolve()
    out_registry_map = (project_root / args.out_registry_map).resolve()

    try:
        _ensure_inside(ROOT, kernel_root, "E_SSOT_DEF_KERNEL_ROOT_OUTSIDE_REPO")
        _ensure_inside(kernel_root, definitions_path, "E_SSOT_DEF_INPUT_OUTSIDE_PROJECT")
        _ensure_inside(project_root, out_definitions, "E_SSOT_DEF_OUTPUT_OUTSIDE_PROJECT")
        _ensure_inside(project_root, out_registry_map, "E_SSOT_DEF_OUTPUT_OUTSIDE_PROJECT")
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    if kernel_root.is_symlink() or _has_symlink_parent(kernel_root, ROOT):
        print("E_SSOT_DEF_KERNEL_ROOT_SYMLINK", file=sys.stderr)
        return 2
    if definitions_path.is_symlink() or _has_symlink_parent(definitions_path, kernel_root):
        print("E_SSOT_DEF_INPUT_SYMLINK", file=sys.stderr)
        return 2
    if not definitions_path.exists() or definitions_path.is_dir():
        print("E_SSOT_DEF_INPUT_NOT_FOUND", file=sys.stderr)
        return 2

    allowed_root = (project_root / "OUTPUT" / "ssot").resolve()
    for out_path in (out_definitions, out_registry_map):
        try:
            out_path.resolve().relative_to(allowed_root)
        except ValueError:
            print("E_SSOT_DEF_OUTPUT_PATH_INVALID", file=sys.stderr)
            return 2
        if out_path.exists() and out_path.is_symlink():
            print("E_SSOT_DEF_OUTPUT_SYMLINK", file=sys.stderr)
            return 2
        if out_path.exists() and out_path.is_dir():
            print("E_SSOT_DEF_OUTPUT_IS_DIR", file=sys.stderr)
            return 2
        if _has_symlink_parent(out_path, project_root):
            print("E_SSOT_DEF_OUTPUT_SYMLINK_PARENT", file=sys.stderr)
            return 2

    source_rev = (args.source_rev or "").strip()
    if not source_rev:
        source_rev = _git_rev(project_root)
    if source_rev == "UNKNOWN" and not args.allow_unknown_source_rev:
        print("E_SSOT_DEF_SOURCE_REV_UNKNOWN", file=sys.stderr)
        return 2

    raw_text = definitions_path.read_text(encoding="utf-8")
    try:
        defs = _extract_definitions_object(raw_text)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    tokens = defs.get("tokens")
    if tokens is None:
        tokens = {}
    if not isinstance(tokens, dict):
        print("E_SSOT_DEF_TOKENS_INVALID", file=sys.stderr)
        return 2
    for key in tokens.keys():
        if not isinstance(key, str) or not key.startswith("SSOT."):
            print("E_SSOT_DEF_TOKEN_INVALID", file=sys.stderr)
            return 2

    input_hash = _compute_input_hash(kernel_root, [definitions_path])
    payload = {
        "schema_version": args.schema_version,
        "source_rev": source_rev,
        "input_hash": input_hash,
        "generator_id": "ssot_kernel_builder.build_ssot_definitions",
    }
    payload.update(defs)

    out_definitions.parent.mkdir(parents=True, exist_ok=True)
    out_registry_map.parent.mkdir(parents=True, exist_ok=True)

    try:
        _write_json(out_definitions, payload, "E_SSOT_DEF_OUTPUT_SYMLINK")
    except OSError as exc:
        print(f"E_SSOT_DEF_WRITE_FAILED:{exc}", file=sys.stderr)
        return 2

    registry_map: dict[str, str] = {
        "schema_version": args.schema_version,
        "source_rev": source_rev,
        "input_hash": input_hash,
        "generator_id": "ssot_kernel_builder.build_ssot_definitions",
    }
    for token in sorted(tokens.keys()):
        pointer = "/tokens/" + _escape_pointer(token)
        registry_map[token] = f"{DEFAULT_OUT_DEFINITIONS}#{pointer}"

    try:
        _write_json(out_registry_map, registry_map, "E_SSOT_DEF_OUTPUT_SYMLINK")
    except OSError as exc:
        print(f"E_SSOT_DEF_MAP_WRITE_FAILED:{exc}", file=sys.stderr)
        return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
