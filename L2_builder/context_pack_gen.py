#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from L2_builder.common import ROOT as REPO_ROOT, ensure_inside, has_symlink_parent, resolve_path
from sdslv2_builder.context_pack import extract_context_pack

DEFAULT_OUT = "OUTPUT/context_pack.yaml"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="Topology .sdsl2 file path (SSOT).")
    ap.add_argument("--target", required=True, help="Target @Node.<RELID>.")
    ap.add_argument("--hops", type=int, default=1, help="Neighbor hops (>=0).")
    ap.add_argument("--out", default=DEFAULT_OUT, help="Output path (OUTPUT/context_pack.yaml) or '-' for stdout.")
    ap.add_argument("--project-root", default=str(REPO_ROOT), help="Project root.")
    args = ap.parse_args()

    project_root = Path(args.project_root).resolve()
    if args.hops < 0:
        print("E_CONTEXT_PACK_HOPS_INVALID", file=sys.stderr)
        return 2

    input_path = resolve_path(project_root, args.input)
    try:
        ensure_inside(project_root, input_path, "E_CONTEXT_PACK_INPUT_OUTSIDE_PROJECT")
    except ValueError:
        print("E_CONTEXT_PACK_INPUT_OUTSIDE_PROJECT", file=sys.stderr)
        return 2
    if has_symlink_parent(input_path, project_root):
        print("E_CONTEXT_PACK_INPUT_SYMLINK", file=sys.stderr)
        return 2
    if not input_path.exists():
        print(f"E_CONTEXT_PACK_INPUT_NOT_FOUND: {input_path}", file=sys.stderr)
        return 2
    if input_path.is_dir():
        print("E_CONTEXT_PACK_INPUT_IS_DIRECTORY", file=sys.stderr)
        return 2

    try:
        content = extract_context_pack(input_path, args.target, args.hops)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    if args.out == "-":
        print(content, end="")
        return 0

    out_path = resolve_path(project_root, args.out)
    expected = (project_root / DEFAULT_OUT).resolve()
    if out_path != expected:
        print("E_CONTEXT_PACK_OUTPUT_PATH_INVALID", file=sys.stderr)
        return 2
    if has_symlink_parent(out_path.parent, project_root):
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
    out_path.write_text(content, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
