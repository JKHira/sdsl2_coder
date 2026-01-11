#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from L0_builder.topology_resolution import analyze_topology_files
from sdslv2_builder.errors import Diagnostic


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


def _print_diags(diags: list[Diagnostic]) -> None:
    payload = [d.to_dict() for d in diags]
    print(json.dumps(payload, ensure_ascii=False, indent=2), file=sys.stderr)


def _collect_files(project_root: Path, inputs: list[str]) -> list[Path] | None:
    files: list[Path] = []
    topo_root = (project_root / "sdsl2" / "topology").absolute()
    if topo_root.is_symlink() or _has_symlink_parent(topo_root, project_root):
        print("E_TOPO_RES_TOPOLOGY_ROOT_SYMLINK", file=sys.stderr)
        return None
    for raw in inputs:
        path = Path(raw)
        if not path.is_absolute():
            path = (project_root / path).absolute()
        if not _ensure_under_root(path, project_root, "E_TOPO_RES_INPUT_OUTSIDE_PROJECT"):
            return None
        if not _ensure_under_root(path, topo_root, "E_TOPO_RES_INPUT_NOT_TOPOLOGY"):
            return None
        if path.is_symlink() or _has_symlink_parent(path, topo_root):
            print("E_TOPO_RES_INPUT_SYMLINK", file=sys.stderr)
            return None
        if path.is_dir():
            for file_path in sorted(path.rglob("*.sdsl2")):
                if file_path.is_symlink() or _has_symlink_parent(file_path, topo_root):
                    print("E_TOPO_RES_INPUT_SYMLINK", file=sys.stderr)
                    return None
                if file_path.is_file():
                    files.append(file_path)
        elif path.is_file():
            if path.suffix != ".sdsl2":
                print("E_TOPO_RES_INPUT_NOT_SDSL2", file=sys.stderr)
                return None
            files.append(path)
        else:
            print("E_TOPO_RES_INPUT_NOT_FILE", file=sys.stderr)
            return None
    if not files:
        print("E_TOPO_RES_INPUT_NOT_FOUND", file=sys.stderr)
        return None
    return files


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", action="append", required=True, help="Topology .sdsl2 file or directory")
    ap.add_argument(
        "--project-root",
        default=None,
        help="Project root (defaults to repo root); inputs can be relative to it",
    )
    ap.add_argument(
        "--fail-on-missing",
        action="store_true",
        help="Treat missing resolution fields as failure",
    )
    args = ap.parse_args()

    project_root = Path(args.project_root).resolve() if args.project_root else ROOT
    files = _collect_files(project_root, args.input)
    if files is None:
        return 2

    hard_diags, soft_diags, _ = analyze_topology_files(project_root, files)
    if hard_diags:
        _print_diags(hard_diags + soft_diags)
        return 2
    if soft_diags:
        _print_diags(soft_diags)
        return 2 if args.fail_on_missing else 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
