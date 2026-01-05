#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _run(cmd: list[str]) -> int:
    return subprocess.run(cmd).returncode


def _has_symlink_parent(path: Path, stop: Path) -> bool:
    for parent in [path, *path.parents]:
        if parent == stop:
            break
        if parent.is_symlink():
            return True
    return False


def _ensure_under_root(path: Path, root: Path, code: str) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        print(code, file=sys.stderr)
        return False
    return True


def _collect_sdsl2_files(root: Path, ssot_root: Path) -> list[Path] | None:
    files: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        current = Path(dirpath)
        for name in dirnames:
            if (current / name).is_symlink():
                print("E_LINT_INPUT_SYMLINK", file=sys.stderr)
                return None
        for name in filenames:
            if not name.endswith(".sdsl2"):
                continue
            file_path = current / name
            if file_path.is_symlink():
                print("E_LINT_INPUT_SYMLINK", file=sys.stderr)
                return None
            if _has_symlink_parent(file_path, ssot_root):
                print("E_LINT_INPUT_SYMLINK_PARENT", file=sys.stderr)
                return None
            files.append(file_path)
    return sorted(files)


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
    ssot_root = (project_root / "sdsl2").resolve()
    if ssot_root.is_symlink():
        print("E_LINT_SSOT_ROOT_SYMLINK", file=sys.stderr)
        return 2

    files: list[Path] = []
    for raw in args.input:
        path = Path(raw)
        if not path.is_absolute():
            path = (project_root / path).resolve()
        if not _ensure_under_root(path, project_root, "E_LINT_INPUT_OUTSIDE_PROJECT"):
            return 2
        if not _ensure_under_root(path, ssot_root, "E_LINT_INPUT_NOT_SSOT"):
            return 2
        if path.is_symlink() or _has_symlink_parent(path, ssot_root):
            print("E_LINT_INPUT_SYMLINK", file=sys.stderr)
            return 2
        if path.is_dir():
            collected = _collect_sdsl2_files(path, ssot_root)
            if collected is None:
                return 2
            files.extend(collected)
        elif path.is_file():
            if path.suffix != ".sdsl2":
                print("E_LINT_INPUT_NOT_SDSL2", file=sys.stderr)
                return 2
            files.append(path)
        else:
            print("E_LINT_INPUT_NOT_FILE", file=sys.stderr)
            return 2

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
