#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

DEFAULT_LOCK_FILES = [
    "coder_planning/builder_writer_api_v0_1.md",
    "coder_planning/errors_v0_1.md",
    "coder_planning/ledger_v0_1.md",
    "coder_planning/ledger_format/closed_set_v0_1.md",
    "coder_planning/ledger_format/topology_ledger_v0_1.md",
]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_lock_file(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def build_lock_entries(paths: list[str]) -> list[dict]:
    entries = []
    for raw in paths:
        p = Path(raw)
        if not p.exists():
            raise SystemExit(f"SPEC_LOCK_MISSING_FILE: {p}")
        entries.append({"path": raw, "sha256": sha256_file(p)})
    return entries


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--locks", default="spec_locks_v0_1.json", help="Lock file path.")
    ap.add_argument("--write", action="store_true", help="Write lock file.")
    args = ap.parse_args()

    lock_path = Path(args.locks)
    lock_data = load_lock_file(lock_path)

    if args.write:
        paths = [entry.get("path") for entry in lock_data.get("files", []) if isinstance(entry, dict)]
        if not paths:
            paths = DEFAULT_LOCK_FILES
        entries = build_lock_entries(paths)
        payload = {
            "spec_lock_version": lock_data.get("spec_lock_version", "v0.1"),
            "files": entries,
        }
        lock_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return 0

    files = lock_data.get("files")
    if not isinstance(files, list):
        raise SystemExit("SPEC_LOCK_INVALID_FORMAT")

    failures = 0
    for entry in files:
        if not isinstance(entry, dict) or "path" not in entry or "sha256" not in entry:
            print("[FAIL] invalid lock entry")
            failures += 1
            continue
        path = Path(entry["path"])
        if not path.exists():
            print(f"[FAIL] missing file: {path}")
            failures += 1
            continue
        actual = sha256_file(path)
        expected = entry["sha256"]
        if actual != expected:
            print(f"[FAIL] spec lock mismatch: {path}")
            print(f"  expected: {expected}")
            print(f"  actual:   {actual}")
            failures += 1

    if failures:
        print("Spec lock mismatch detected. Spec bump (v0.2+) required.")
        return 2
    print("[OK] spec locks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
