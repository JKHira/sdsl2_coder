#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


DEFAULT_ALLOW = [
    "OUTPUT/",
    "tests/goldens/",
]


def run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, capture_output=True, text=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--allow", action="append", default=[], help="Allowed path prefix.")
    args = ap.parse_args()

    allow = DEFAULT_ALLOW + list(args.allow)
    allow = [a if a.endswith("/") else f"{a}/" for a in allow]

    root_check = run(["git", "rev-parse", "--is-inside-work-tree"])
    if root_check.returncode != 0:
        print("DIFF_GATE_NOT_GIT_REPO", file=sys.stderr)
        return 2

    diff = run(["git", "diff", "--name-only"])
    if diff.returncode != 0:
        print("DIFF_GATE_DIFF_FAILED", file=sys.stderr)
        return 2
    diff_cached = run(["git", "diff", "--name-only", "--cached"])
    if diff_cached.returncode != 0:
        print("DIFF_GATE_DIFF_CACHED_FAILED", file=sys.stderr)
        return 2
    status = run(["git", "status", "--porcelain"])
    if status.returncode != 0:
        print("DIFF_GATE_STATUS_FAILED", file=sys.stderr)
        return 2

    files = set()
    for line in diff.stdout.splitlines():
        if line.strip():
            files.add(line.strip())
    for line in diff_cached.stdout.splitlines():
        if line.strip():
            files.add(line.strip())
    for line in status.stdout.splitlines():
        if line.startswith("?? "):
            path = line[3:].strip()
            if path:
                files.add(path)

    if not files:
        print("[OK] diff gate (no changes)")
        return 0

    violations = []
    for path in sorted(files):
        ok = any(path == prefix.rstrip("/") or path.startswith(prefix) for prefix in allow)
        if not ok:
            violations.append(path)

    if violations:
        print("[FAIL] diff gate violations:", file=sys.stderr)
        for path in violations:
            print(f"  - {path}", file=sys.stderr)
        return 2

    print("[OK] diff gate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
