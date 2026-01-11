#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sdslv2_builder.context_pack import extract_context_pack
from sdslv2_builder.io_atomic import atomic_write_text
from sdslv2_builder.input_hash import compute_input_hash

DEFAULT_OUT = "OUTPUT/context_pack.yaml"


def _resolve_path(base: Path, raw: str) -> Path:
    path = Path(raw)
    if not path.is_absolute():
        path = (base / path).absolute()
    return path


def _has_symlink_parent(path: Path, stop: Path) -> bool:
    for parent in [path, *path.parents]:
        if parent == stop:
            break
        if parent.is_symlink():
            return True
    return False


def _git_rev(project_root: Path) -> tuple[str, str | None]:
    try:
        result = subprocess.run(
            ["git", "-C", str(project_root), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        return "UNKNOWN", "E_CONTEXT_PACK_SOURCE_REV_GIT_MISSING"
    if result.returncode != 0:
        return "UNKNOWN", "E_CONTEXT_PACK_SOURCE_REV_MISSING"
    rev = result.stdout.strip()
    if not rev:
        return "UNKNOWN", "E_CONTEXT_PACK_SOURCE_REV_EMPTY"
    return rev, None


def _quote(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="SDSL2 file path")
    ap.add_argument("--target", required=True, help="@Node.<RELID> target")
    ap.add_argument("--hops", type=int, default=1, help="Neighbor hop count (>=0)")
    ap.add_argument(
        "--out",
        default=DEFAULT_OUT,
        help="Output path (OUTPUT/context_pack.yaml) or '-' for stdout",
    )
    ap.add_argument(
        "--project-root",
        default=None,
        help="Project root (defaults to repo root); output path is OUTPUT/context_pack.yaml",
    )
    args = ap.parse_args()

    project_root = Path(args.project_root).resolve() if args.project_root else ROOT
    if args.hops < 0:
        print("E_CONTEXT_PACK_HOPS_INVALID", file=sys.stderr)
        return 2

    input_path = _resolve_path(project_root, args.input)
    ssot_root = (project_root / "sdsl2" / "topology").absolute()
    if ssot_root.is_symlink() or _has_symlink_parent(ssot_root, project_root):
        print("E_CONTEXT_PACK_SSOT_ROOT_SYMLINK", file=sys.stderr)
        return 2
    try:
        input_path.resolve().relative_to(ssot_root)
    except ValueError:
        print("E_CONTEXT_PACK_INPUT_NOT_SSOT", file=sys.stderr)
        return 2
    if not input_path.exists():
        print(f"E_CONTEXT_PACK_INPUT_NOT_FOUND: {input_path}", file=sys.stderr)
        return 2
    if not input_path.is_file():
        print("E_CONTEXT_PACK_INPUT_NOT_FILE", file=sys.stderr)
        return 2
    if input_path.suffix != ".sdsl2":
        print("E_CONTEXT_PACK_INPUT_NOT_SSOT", file=sys.stderr)
        return 2
    if input_path.is_symlink() or _has_symlink_parent(input_path, project_root):
        print("E_CONTEXT_PACK_INPUT_SYMLINK", file=sys.stderr)
        return 2

    try:
        content = extract_context_pack(input_path, args.target, args.hops)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    source_rev, warn = _git_rev(project_root)
    if warn:
        print(warn, file=sys.stderr)
    try:
        result = compute_input_hash(
            project_root,
            include_decisions=False,
            include_policy=False,
        )
    except Exception as exc:  # pragma: no cover - defensive
        print(f"E_CONTEXT_PACK_INPUT_HASH_FAILED:{exc}", file=sys.stderr)
        return 2

    inputs_rel = []
    for path in result.inputs:
        rel = path.resolve().relative_to(project_root.resolve()).as_posix()
        inputs_rel.append(rel)
    inputs_rel.append(f"input_hash:{result.input_hash}")

    supplement_lines = [
        "---",
        "Supplementary: provenance",
        f"generator: {_quote('L0_builder.context_pack_gen')}",
        f"source_rev: {_quote(source_rev)}",
        "inputs:",
    ]
    for item in inputs_rel:
        supplement_lines.append(f"  - {_quote(item)}")
    supplement = "\n".join(supplement_lines) + "\n"

    content = content if content.endswith("\n") else content + "\n"
    output = content + supplement

    if args.out == "-":
        print(output, end="")
        return 0

    out_path = _resolve_path(project_root, args.out)
    expected = (project_root / DEFAULT_OUT).absolute()
    if out_path != expected:
        print("E_CONTEXT_PACK_OUTPUT_PATH_INVALID", file=sys.stderr)
        return 2
    if _has_symlink_parent(out_path.parent, project_root):
        print("E_CONTEXT_PACK_OUTPUT_SYMLINK", file=sys.stderr)
        return 2
    if out_path.exists() and out_path.is_symlink():
        print("E_CONTEXT_PACK_OUTPUT_SYMLINK", file=sys.stderr)
        return 2
    if out_path.exists() and out_path.is_dir():
        print("E_CONTEXT_PACK_OUTPUT_IS_DIRECTORY", file=sys.stderr)
        return 2
    if out_path.parent.exists() and not out_path.parent.is_dir():
        print("E_CONTEXT_PACK_OUTPUT_PARENT_NOT_DIR", file=sys.stderr)
        return 2

    out_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        atomic_write_text(out_path, output, symlink_code="E_CONTEXT_PACK_OUTPUT_SYMLINK")
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"E_CONTEXT_PACK_WRITE_FAILED:{exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
