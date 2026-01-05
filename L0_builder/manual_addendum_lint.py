#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _run(cmd: list[str]) -> int:
    return subprocess.run(cmd).returncode


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", action="append", required=True, help="File or directory path")
    ap.add_argument("--policy-path", default=None, help="Explicit policy path")
    ap.add_argument(
        "--project-root",
        default=None,
        help="Project root (defaults to repo root); inputs can be relative to it",
    )
    args = ap.parse_args()

    project_root = Path(args.project_root).resolve() if args.project_root else ROOT

    files: list[Path] = []
    for raw in args.input:
        path = Path(raw)
        if not path.is_absolute():
            path = (project_root / path).resolve()
        try:
            path.resolve().relative_to(project_root.resolve())
        except ValueError:
            print("E_LINT_INPUT_OUTSIDE_PROJECT", file=sys.stderr)
            return 2
        if path.is_dir():
            files.extend(sorted(p for p in path.rglob("*.sdsl2") if p.is_file()))
        elif path.is_file():
            files.append(path)

    if not files:
        print("E_LINT_INPUT_NOT_FOUND", file=sys.stderr)
        return 2

    gate_cmd = [sys.executable, str(ROOT / "scripts" / "gate_a_check.py")]
    for path in files:
        gate_cmd.extend(["--input", str(path)])
    rc = _run(gate_cmd)
    if rc != 0:
        return rc

    add_cmd = [sys.executable, str(ROOT / "scripts" / "addendum_check.py")]
    for path in files:
        add_cmd.extend(["--input", str(path)])
    if args.policy_path:
        add_cmd.extend(["--policy-path", args.policy_path])
    return _run(add_cmd)


if __name__ == "__main__":
    raise SystemExit(main())
