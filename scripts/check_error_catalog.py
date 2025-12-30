#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import glob
import json
import re
from pathlib import Path


ERROR_CODE_RE = re.compile(r"\bE_[A-Z0-9_]+\b")


def load_catalog(path: Path) -> set[str]:
    if not path.exists():
        raise SystemExit(f"ERROR_CATALOG_NOT_FOUND: {path}")
    text = path.read_text(encoding="utf-8")
    return set(ERROR_CODE_RE.findall(text))


def load_diagnostics(paths: list[Path]) -> set[str]:
    codes: set[str] = set()
    for path in paths:
        if not path.exists():
            raise SystemExit(f"DIAGNOSTICS_NOT_FOUND: {path}")
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            raise SystemExit(f"DIAGNOSTICS_NOT_LIST: {path}")
        for item in data:
            if not isinstance(item, dict):
                raise SystemExit(f"DIAGNOSTICS_NOT_OBJECT: {path}")
            for key in ("code", "message", "expected", "got", "path"):
                if key not in item:
                    raise SystemExit(f"DIAGNOSTICS_MISSING_FIELD: {path}: {key}")
                if not isinstance(item[key], str):
                    raise SystemExit(f"DIAGNOSTICS_FIELD_NOT_STRING: {path}: {key}")
            diag_path = item.get("path")
            if not is_valid_json_pointer(diag_path):
                raise SystemExit(f"DIAGNOSTICS_PATH_INVALID: {path}: {diag_path}")
            code = item.get("code")
            if code:
                codes.add(str(code))
    return codes


def is_valid_json_pointer(path: str) -> bool:
    if path == "":
        return True
    if not path.startswith("/"):
        return False
    i = 0
    while i < len(path):
        if path[i] == "~":
            if i + 1 >= len(path) or path[i + 1] not in ("0", "1"):
                return False
            i += 2
            continue
        i += 1
    return True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--errors",
        default="coder_planning/errors_v0_1.md",
        help="Path to error catalog (markdown).",
    )
    ap.add_argument(
        "--diagnostics-glob",
        default="tests/goldens/**/diagnostics.json",
        help="Glob for diagnostics snapshots.",
    )
    args = ap.parse_args()

    catalog = load_catalog(Path(args.errors))
    if not catalog:
        raise SystemExit("ERROR_CATALOG_EMPTY")

    diag_paths = [Path(p) for p in glob.glob(args.diagnostics_glob, recursive=True)]
    if not diag_paths:
        raise SystemExit("DIAGNOSTICS_GLOB_EMPTY")

    seen = load_diagnostics(diag_paths)
    unknown = sorted(code for code in seen if code not in catalog)
    if unknown:
        print("[FAIL] Unknown error codes:")
        for code in unknown:
            print(f"  - {code}")
        return 2

    missing = sorted(code for code in catalog if code not in seen)
    if missing:
        print("[WARN] Catalog codes not seen in diagnostics:")
        for code in missing:
            print(f"  - {code}")

    print("[OK] error catalog coverage")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
