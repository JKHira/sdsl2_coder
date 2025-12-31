#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sdslv2_builder.context_pack import extract_context_pack


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="Topology .sdsl2 file.")
    ap.add_argument("--target", required=True, help="Target @Node.<RELID>.")
    ap.add_argument("--hops", type=int, default=1, help="Neighbor hops (default: 1).")
    ap.add_argument("--output", help="Output file path (optional).")
    args = ap.parse_args()
    if args.hops < 0:
        print("E_CONTEXT_PACK_HOPS_INVALID", file=sys.stderr)
        return 2

    try:
        content = extract_context_pack(Path(args.input), args.target, args.hops)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    if args.output:
        Path(args.output).write_text(content, encoding="utf-8")
        return 0
    print(content, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
