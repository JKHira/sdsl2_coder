#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sdslv2_builder.context_pack import extract_context_pack


def _resolve_path(base: Path, raw: str) -> Path:
    path = Path(raw)
    if not path.is_absolute():
        path = (base / path).resolve()
    return path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="SDSL2 file path")
    ap.add_argument("--target", required=True, help="@Node.<RELID> target")
    ap.add_argument("--hops", type=int, default=1, help="Neighbor hop count (>=0)")
    ap.add_argument(
        "--out",
        default=str(ROOT / "OUTPUT" / "context_pack.yaml"),
        help="Output path or '-' for stdout",
    )
    ap.add_argument(
        "--project-root",
        default=None,
        help="Project root (defaults to repo root); outputs must stay under project_root/OUTPUT",
    )
    args = ap.parse_args()

    project_root = Path(args.project_root).resolve() if args.project_root else ROOT
    if args.hops < 0:
        print("E_CONTEXT_PACK_HOPS_INVALID", file=sys.stderr)
        return 2

    input_path = _resolve_path(project_root, args.input)
    try:
        input_path.resolve().relative_to(project_root.resolve())
    except ValueError:
        print("E_CONTEXT_PACK_INPUT_OUTSIDE_PROJECT", file=sys.stderr)
        return 2
    if not input_path.exists():
        print(f"E_CONTEXT_PACK_INPUT_NOT_FOUND: {input_path}", file=sys.stderr)
        return 2

    content = extract_context_pack(input_path, args.target, args.hops)

    if args.out == "-":
        print(content)
        return 0

    out_path = _resolve_path(project_root, args.out)
    output_root = (project_root / "OUTPUT").resolve()
    if output_root not in out_path.parents and out_path != output_root:
        print("E_CONTEXT_PACK_OUTPUT_OUTSIDE_OUTPUT", file=sys.stderr)
        return 2
    if out_path.exists() and out_path.is_dir():
        print("E_CONTEXT_PACK_OUTPUT_IS_DIRECTORY", file=sys.stderr)
        return 2

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(content, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
