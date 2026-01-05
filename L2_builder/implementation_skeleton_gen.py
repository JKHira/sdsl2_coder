#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from L2_builder.common import ROOT as REPO_ROOT, ensure_inside, has_symlink_parent, resolve_path
from sdslv2_builder.input_hash import compute_input_hash
from sdslv2_builder.lint import _capture_metadata, _parse_metadata_pairs
from sdslv2_builder.op_yaml import dump_yaml

DEFAULT_OUT = "OUTPUT/implementation_skeleton.yaml"
GENERATOR_ID = "L2_builder.implementation_skeleton_gen"


def _git_rev(project_root: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(project_root), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise ValueError("E_SKELETON_SOURCE_REV_MISSING")
    return result.stdout.strip()


def _collect_ids(lines: list[str], kind: str) -> list[str]:
    ids: list[str] = []
    for idx, line in enumerate(lines):
        if not line.lstrip().startswith(f"@{kind}"):
            continue
        brace_idx = line.find("{")
        if brace_idx == -1:
            continue
        meta, _ = _capture_metadata(lines, idx, brace_idx)
        pairs = _parse_metadata_pairs(meta)
        for key, value in pairs:
            if key == "id":
                value = value.strip()
                if len(value) >= 2 and value[0] == value[-1] == '"':
                    value = value[1:-1]
                ids.append(value)
                break
    return ids


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project-root", default=str(REPO_ROOT), help="Project root.")
    ap.add_argument("--out", default=DEFAULT_OUT, help="Output file path.")
    ap.add_argument("--source-rev", default=None, help="Override git source_rev.")
    ap.add_argument("--no-decisions", action="store_true", help="Exclude decisions/edges.yaml from input_hash.")
    args = ap.parse_args()

    project_root = Path(args.project_root).resolve()
    out_path = resolve_path(project_root, args.out)
    expected = (project_root / DEFAULT_OUT).resolve()

    try:
        ensure_inside(project_root, out_path, "E_SKELETON_OUTPUT_OUTSIDE_PROJECT")
    except ValueError:
        print("E_SKELETON_OUTPUT_OUTSIDE_PROJECT", file=sys.stderr)
        return 2

    if out_path != expected:
        print("E_SKELETON_OUTPUT_PATH_INVALID", file=sys.stderr)
        return 2

    if has_symlink_parent(out_path.parent, project_root):
        print("E_SKELETON_OUTPUT_SYMLINK", file=sys.stderr)
        return 2

    if out_path.exists() and out_path.is_symlink():
        print("E_SKELETON_OUTPUT_SYMLINK", file=sys.stderr)
        return 2
    if out_path.exists() and out_path.is_dir():
        print("E_SKELETON_OUTPUT_IS_DIRECTORY", file=sys.stderr)
        return 2
    if out_path.parent.exists() and not out_path.parent.is_dir():
        print("E_SKELETON_OUTPUT_PARENT_NOT_DIR", file=sys.stderr)
        return 2

    contract_root = project_root / "sdsl2" / "contract"
    if not contract_root.exists():
        print("E_SKELETON_CONTRACT_ROOT_MISSING", file=sys.stderr)
        return 2
    if not contract_root.is_dir():
        print("E_SKELETON_CONTRACT_ROOT_NOT_DIR", file=sys.stderr)
        return 2

    contract_files = sorted(p for p in contract_root.rglob("*.sdsl2") if p.is_file())
    if not contract_files:
        print("E_SKELETON_CONTRACT_FILES_MISSING", file=sys.stderr)
        return 2

    for path in contract_files:
        if has_symlink_parent(path, project_root) or path.is_symlink():
            print("E_SKELETON_CONTRACT_SYMLINK", file=sys.stderr)
            return 2

    try:
        source_rev = args.source_rev or _git_rev(project_root)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    try:
        result = compute_input_hash(project_root, include_decisions=not args.no_decisions)
    except Exception as exc:
        print(f"E_SKELETON_INPUT_HASH_FAILED:{exc}", file=sys.stderr)
        return 2

    structures: set[str] = set()
    rules: set[str] = set()
    for path in contract_files:
        text = path.read_text(encoding="utf-8")
        lines = text.splitlines()
        structures.update(_collect_ids(lines, "Structure"))
        rules.update(_collect_ids(lines, "Rule"))

    payload = {
        "schema_version": "1.0",
        "source_rev": source_rev,
        "input_hash": result.input_hash,
        "generator_id": GENERATOR_ID,
        "structures": sorted(structures),
        "rules": sorted(rules),
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(dump_yaml(payload), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
