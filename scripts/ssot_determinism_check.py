#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import hashlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def run(cmd: list[str]) -> int:
    print("+", " ".join(cmd))
    return subprocess.call(cmd)


def snapshot(output_root: Path, files: list[Path]) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for path in files:
        if not path.exists():
            raise SystemExit(f"SSOT_OUTPUT_MISSING: {path}")
        if not path.is_file():
            raise SystemExit(f"SSOT_OUTPUT_NOT_FILE: {path}")
        rel = path.resolve().relative_to(output_root.resolve()).as_posix()
        hashes[rel] = sha256_file(path)
    return hashes


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

    project_root = Path(args.project_root).resolve() if args.project_root else ROOT
    output_root = (project_root / "OUTPUT" / "ssot").resolve()
    expected_files = [
        output_root / "ssot_definitions.json",
        output_root / "ssot_registry_map.json",
        output_root / "ssot_registry.json",
        output_root / "contract_definitions.json",
        output_root / "contract_registry_map.json",
        output_root / "contract_registry.json",
    ]

    py = sys.executable
    publish_cmd = [
        py,
        str(ROOT / "scripts" / "ssot_publish.py"),
        "--today",
        args.today,
    ]
    if args.project_root:
        publish_cmd.extend(["--project-root", args.project_root])
    if args.kernel_root:
        publish_cmd.extend(["--kernel-root", args.kernel_root])
    if args.policy_path:
        publish_cmd.extend(["--policy-path", args.policy_path])
    if args.allow_nonstandard_path:
        publish_cmd.append("--allow-nonstandard-path")
    if args.verbose:
        publish_cmd.append("--verbose")

    if run(publish_cmd) != 0:
        return 2
    first = snapshot(output_root, expected_files)

    if run(publish_cmd) != 0:
        return 2
    second = snapshot(output_root, expected_files)

    if first != second:
        print("SSOT_OUTPUT_NON_DETERMINISTIC", file=sys.stderr)
        for key in sorted(set(first.keys()) | set(second.keys())):
            if first.get(key) != second.get(key):
                print(f"- {key}", file=sys.stderr)
        return 2

    print("SSOT_OUTPUT_DETERMINISTIC")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
