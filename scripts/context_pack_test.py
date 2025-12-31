#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sdslv2_builder.context_pack import extract_context_pack


def _canonical_text(text: str) -> str:
    return text.strip() + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True, help="Path to context pack manifest JSON.")
    ap.add_argument("--update", action="store_true", help="Update golden outputs.")
    args = ap.parse_args()

    manifest = Path(args.manifest)
    data = json.loads(manifest.read_text(encoding="utf-8"))
    version = data.get("version")
    if version != "context-pack-manifest-v0.1":
        print(f"E_CONTEXT_PACK_MANIFEST_VERSION: {version}", file=sys.stderr)
        return 2

    cases = data.get("cases", [])
    if not isinstance(cases, list):
        print("E_CONTEXT_PACK_MANIFEST_INVALID", file=sys.stderr)
        return 2

    base = manifest.parent
    for case in cases:
        if not isinstance(case, dict):
            print("E_CONTEXT_PACK_CASE_INVALID", file=sys.stderr)
            return 2
        input_path = case.get("input")
        target = case.get("target")
        golden = case.get("golden")
        try:
            hops = int(case.get("hops", 1))
        except (TypeError, ValueError):
            print("E_CONTEXT_PACK_CASE_INVALID: hops", file=sys.stderr)
            return 2
        if hops < 0:
            print("E_CONTEXT_PACK_CASE_INVALID: hops", file=sys.stderr)
            return 2
        if not input_path or not target or not golden:
            print("E_CONTEXT_PACK_CASE_MISSING_FIELDS", file=sys.stderr)
            return 2

        input_path = (base / input_path).resolve()
        golden_path = (base / golden).resolve()

        try:
            output = extract_context_pack(input_path, target, hops)
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 2

        if args.update:
            golden_path.parent.mkdir(parents=True, exist_ok=True)
            golden_path.write_text(_canonical_text(output), encoding="utf-8")
            print(f"[OK] updated {golden_path}")
        else:
            if not golden_path.exists():
                print(f"[FAIL] golden not found: {golden_path}", file=sys.stderr)
                return 2
            expected = _canonical_text(golden_path.read_text(encoding="utf-8"))
            got = _canonical_text(output)
            if got != expected:
                print(f"[FAIL] context pack differs: {golden_path}", file=sys.stderr)
                print("[HINT] re-run with --update to refresh goldens", file=sys.stderr)
                return 2

    print("[OK] context pack manifest")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
