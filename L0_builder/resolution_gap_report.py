#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from L0_builder.topology_resolution import analyze_topology_files
from sdslv2_builder.io_atomic import atomic_write_text
from sdslv2_builder.input_hash import compute_input_hash
from sdslv2_builder.op_yaml import dump_yaml

DEFAULT_OUT = "OUTPUT/resolution_gaps.yaml"


def _resolve_path(base: Path, raw: str) -> Path:
    path = Path(raw)
    if not path.is_absolute():
        path = (base / path).absolute()
    return path


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


def _collect_files(project_root: Path, inputs: list[str]) -> list[Path] | None:
    files: list[Path] = []
    topo_root = (project_root / "sdsl2" / "topology").absolute()
    if topo_root.is_symlink() or _has_symlink_parent(topo_root, project_root):
        print("E_GAP_REPORT_TOPOLOGY_ROOT_SYMLINK", file=sys.stderr)
        return None
    for raw in inputs:
        path = Path(raw)
        if not path.is_absolute():
            path = (project_root / path).absolute()
        if not _ensure_under_root(path, project_root, "E_GAP_REPORT_INPUT_OUTSIDE_PROJECT"):
            return None
        if not _ensure_under_root(path, topo_root, "E_GAP_REPORT_INPUT_NOT_TOPOLOGY"):
            return None
        if path.is_symlink() or _has_symlink_parent(path, topo_root):
            print("E_GAP_REPORT_INPUT_SYMLINK", file=sys.stderr)
            return None
        if path.is_dir():
            for file_path in sorted(path.rglob("*.sdsl2")):
                if file_path.is_symlink() or _has_symlink_parent(file_path, topo_root):
                    print("E_GAP_REPORT_INPUT_SYMLINK", file=sys.stderr)
                    return None
                if file_path.is_file():
                    files.append(file_path)
        elif path.is_file():
            if path.suffix != ".sdsl2":
                print("E_GAP_REPORT_INPUT_NOT_SDSL2", file=sys.stderr)
                return None
            files.append(path)
        else:
            print("E_GAP_REPORT_INPUT_NOT_FILE", file=sys.stderr)
            return None
    if not files:
        print("E_GAP_REPORT_INPUT_NOT_FOUND", file=sys.stderr)
        return None
    return files


def _git_rev(project_root: Path) -> tuple[str, str | None]:
    try:
        result = subprocess.run(
            ["git", "-C", str(project_root), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        return "UNKNOWN", "E_GAP_REPORT_SOURCE_REV_GIT_MISSING"
    if result.returncode != 0:
        return "UNKNOWN", "E_GAP_REPORT_SOURCE_REV_MISSING"
    rev = result.stdout.strip()
    if not rev:
        return "UNKNOWN", "E_GAP_REPORT_SOURCE_REV_EMPTY"
    return rev, None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", action="append", required=True, help="Topology .sdsl2 file or directory")
    ap.add_argument(
        "--out",
        default=DEFAULT_OUT,
        help="Output path under OUTPUT/",
    )
    ap.add_argument(
        "--project-root",
        default=None,
        help="Project root (defaults to repo root); inputs can be relative to it",
    )
    args = ap.parse_args()

    project_root = Path(args.project_root).resolve() if args.project_root else ROOT
    files = _collect_files(project_root, args.input)
    if files is None:
        return 2

    hard_diags, _, gaps = analyze_topology_files(project_root, files)
    if hard_diags:
        payload = [d.to_dict() for d in hard_diags]
        print(json.dumps(payload, ensure_ascii=False, indent=2), file=sys.stderr)
        return 2

    out_path = _resolve_path(project_root, args.out)
    output_root = project_root / "OUTPUT"
    if output_root.is_symlink() or _has_symlink_parent(output_root, project_root):
        print("E_GAP_REPORT_OUTPUT_SYMLINK", file=sys.stderr)
        return 2
    output_root = output_root.resolve()
    try:
        out_path.resolve().relative_to(output_root)
    except ValueError:
        print("E_GAP_REPORT_OUTPUT_OUTSIDE_OUTPUT", file=sys.stderr)
        return 2
    if _has_symlink_parent(out_path, project_root):
        print("E_GAP_REPORT_OUTPUT_SYMLINK", file=sys.stderr)
        return 2
    if out_path.exists() and out_path.is_symlink():
        print("E_GAP_REPORT_OUTPUT_SYMLINK", file=sys.stderr)
        return 2
    if out_path.exists() and out_path.is_dir():
        print("E_GAP_REPORT_OUTPUT_IS_DIRECTORY", file=sys.stderr)
        return 2
    if out_path.parent.exists() and not out_path.parent.is_dir():
        print("E_GAP_REPORT_OUTPUT_PARENT_NOT_DIR", file=sys.stderr)
        return 2

    source_rev, warn = _git_rev(project_root)
    if warn:
        print(warn, file=sys.stderr)
    try:
        result = compute_input_hash(
            project_root,
            include_decisions=False,
            include_policy=False,
        )
    except Exception as exc:
        print(f"E_GAP_REPORT_INPUT_HASH_FAILED:{exc}", file=sys.stderr)
        return 2

    payload: dict[str, object] = {
        "schema_version": "1.0",
        "generator_id": "L0_builder.resolution_gap_report",
        "source_rev": source_rev,
        "input_hash": result.input_hash,
        "files": gaps,
    }

    output = dump_yaml(payload)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        atomic_write_text(out_path, output, symlink_code="E_GAP_REPORT_OUTPUT_SYMLINK")
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"E_GAP_REPORT_WRITE_FAILED:{exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
