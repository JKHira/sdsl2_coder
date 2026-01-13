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


def _is_under_root(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def _collect_sdsl2_files(root: Path, ssot_root: Path, symlink_mode: str) -> list[Path] | None:
    files: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        current = Path(dirpath)
        for name in list(dirnames):
            candidate = current / name
            if candidate.is_symlink():
                if symlink_mode == "skip":
                    dirnames.remove(name)
                    print(f"W_LINT_INPUT_SYMLINK_SKIPPED:{candidate}", file=sys.stderr)
                    continue
                print("E_LINT_INPUT_SYMLINK", file=sys.stderr)
                return None
        for name in filenames:
            if not name.endswith(".sdsl2"):
                continue
            file_path = current / name
            if file_path.is_symlink():
                if symlink_mode == "skip":
                    print(f"W_LINT_INPUT_SYMLINK_SKIPPED:{file_path}", file=sys.stderr)
                    continue
                print("E_LINT_INPUT_SYMLINK", file=sys.stderr)
                return None
            if _has_symlink_parent(file_path, ssot_root):
                if symlink_mode == "skip":
                    print(f"W_LINT_INPUT_SYMLINK_PARENT_SKIPPED:{file_path}", file=sys.stderr)
                    continue
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
    ap.add_argument(
        "--skip-resolution-lint",
        action="store_true",
        help="Skip topology resolution lint",
    )
    ap.add_argument(
        "--fail-on-missing",
        action="store_true",
        help="Fail on missing topology resolution fields",
    )
    ap.add_argument(
        "--skip-resolution-gaps",
        action="store_true",
        help="Skip topology resolution gap report",
    )
    ap.add_argument(
        "--resolution-gaps-out",
        default="OUTPUT/resolution_gaps.yaml",
        help="Output path for resolution gap report (under OUTPUT/)",
    )
    ap.add_argument(
        "--symlink-mode",
        choices=["fail", "skip"],
        default="fail",
        help="How to handle symlink entries during input scan (fail|skip)",
    )
    args = ap.parse_args()

    project_root = Path(args.project_root).resolve() if args.project_root else ROOT
    ssot_root = (project_root / "sdsl2").absolute()
    if ssot_root.is_symlink() or _has_symlink_parent(ssot_root, project_root):
        print("E_LINT_SSOT_ROOT_SYMLINK", file=sys.stderr)
        return 2

    files: list[Path] = []
    for raw in args.input:
        path = Path(raw)
        if not path.is_absolute():
            path = (project_root / path).absolute()
        if not _ensure_under_root(path, project_root, "E_LINT_INPUT_OUTSIDE_PROJECT"):
            return 2
        if not _ensure_under_root(path, ssot_root, "E_LINT_INPUT_NOT_SSOT"):
            return 2
        if path.is_symlink() or _has_symlink_parent(path, ssot_root):
            if args.symlink_mode == "skip":
                print(f"W_LINT_INPUT_SYMLINK_SKIPPED:{path}", file=sys.stderr)
                continue
            print("E_LINT_INPUT_SYMLINK", file=sys.stderr)
            return 2
        if path.is_dir():
            collected = _collect_sdsl2_files(path, ssot_root, args.symlink_mode)
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

    policy_path = None
    if args.policy_path:
        policy_path = Path(args.policy_path)
        if not policy_path.is_absolute():
            policy_path = (project_root / policy_path).absolute()
        if policy_path.is_symlink() or _has_symlink_parent(policy_path, project_root):
            print("E_LINT_POLICY_SYMLINK", file=sys.stderr)
            return 2
        if not _ensure_under_root(policy_path, project_root, "E_LINT_POLICY_OUTSIDE_PROJECT"):
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
    if policy_path:
        add_cmd.extend(["--policy-path", str(policy_path)])
    rc = _run(add_cmd)
    if rc != 0:
        return rc

    topo_root = (project_root / "sdsl2" / "topology").absolute()
    topo_files = [path for path in files if _is_under_root(path, topo_root)]
    if topo_files and not args.skip_resolution_lint:
        profile_cmd = [sys.executable, str(ROOT / "L0_builder" / "resolution_profile_lint.py")]
        profile_cmd.extend(["--project-root", str(project_root)])
        rc = _run(profile_cmd)
        if rc != 0:
            return rc
        lint_cmd = [sys.executable, str(ROOT / "L0_builder" / "topology_resolution_lint.py")]
        for path in topo_files:
            lint_cmd.extend(["--input", str(path)])
        lint_cmd.extend(["--project-root", str(project_root)])
        if args.fail_on_missing:
            lint_cmd.append("--fail-on-missing")
        rc = _run(lint_cmd)
        if rc != 0:
            return rc

    if topo_files and not args.skip_resolution_gaps:
        report_cmd = [sys.executable, str(ROOT / "L0_builder" / "resolution_gap_report.py")]
        for path in topo_files:
            report_cmd.extend(["--input", str(path)])
        report_cmd.extend(["--project-root", str(project_root), "--out", args.resolution_gaps_out])
        rc = _run(report_cmd)
        if rc != 0:
            return rc

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
