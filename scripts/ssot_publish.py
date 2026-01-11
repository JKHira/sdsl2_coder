#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(cmd: list[str]) -> int:
    print("+", " ".join(cmd))
    return subprocess.call(cmd)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project-root", default=None, help="Project root for publish.")
    ap.add_argument("--kernel-root", default=None, help="SSOT kernel source root.")
    ap.add_argument("--today", required=True, help="YYYY-MM-DD for exception_lint.")
    ap.add_argument("--policy-path", default=None, help="Explicit policy path.")
    ap.add_argument(
        "--allow-nonstandard-path",
        action="store_true",
        help="Allow nonstandard decisions/evidence paths.",
    )
    ap.add_argument("--verbose", action="store_true", help="Print commands.")
    args = ap.parse_args()

    py = sys.executable
    cmd = [
        py,
        str(ROOT / "L2_builder" / "l2_gate_runner.py"),
        "--publish",
        "--build-ssot",
        "--today",
        args.today,
    ]
    if args.project_root:
        cmd.extend(["--project-root", args.project_root])
    if args.kernel_root:
        cmd.extend(["--kernel-root", args.kernel_root])
    if args.policy_path:
        cmd.extend(["--policy-path", args.policy_path])
    if args.allow_nonstandard_path:
        cmd.append("--allow-nonstandard-path")
    if args.verbose:
        cmd.append("--verbose")

    return run(cmd)


if __name__ == "__main__":
    raise SystemExit(main())
