#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import subprocess
import sys


def run(cmd: list[str]) -> int:
    print("+", " ".join(cmd))
    return subprocess.call(cmd)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--manifest",
        default="tests/determinism_manifest.json",
        help="Determinism manifest path.",
    )
    ap.add_argument("--allow", action="append", default=[], help="Allowlist prefix for diff gate.")
    args = ap.parse_args()

    py = sys.executable

    steps = [
        [py, "scripts/check_spec_locks.py", "--locks", "spec_locks_v0_1.json"],
        [
            py,
            "scripts/check_error_catalog.py",
            "--errors",
            "coder_planning/errors_v0_1.md",
            "--diagnostics-glob",
            "tests/goldens/**/diagnostics.json",
        ],
        [py, "scripts/gate_a_check.py", "--input", "OUTPUT", "--input", "tests/goldens"],
        [py, "scripts/determinism_check.py", "--manifest", args.manifest],
        [py, "scripts/gate_b_check.py", "--input", "OUTPUT", "--input", "tests/goldens"],
    ]

    for cmd in steps:
        if run(cmd) != 0:
            return 2

    diff_gate = [py, "scripts/diff_gate.py"]
    for allowed in args.allow:
        diff_gate.extend(["--allow", allowed])
    if run(diff_gate) != 0:
        return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
