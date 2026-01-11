#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sdslv2_builder.draft_schema import normalize_draft
from sdslv2_builder.errors import Diagnostic
from sdslv2_builder.op_yaml import load_yaml


def _diag_to_dict(diags: list[Diagnostic]) -> list[dict]:
    return [d.to_dict() for d in diags]


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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="Draft YAML path")
    ap.add_argument(
        "--project-root",
        default=None,
        help="Project root (defaults to repo root); input can be relative to it",
    )
    args = ap.parse_args()

    project_root = Path(args.project_root).resolve() if args.project_root else ROOT
    drafts_root = project_root / "drafts"
    if drafts_root.is_symlink():
        print("E_DRAFT_DRAFTS_ROOT_SYMLINK", file=sys.stderr)
        return 2
    path = Path(args.input)
    if not path.is_absolute():
        path = (project_root / path).absolute()
    if not _ensure_under_root(path, drafts_root, "E_DRAFT_INPUT_NOT_DRAFTS_ROOT"):
        return 2
    if not path.exists():
        print("E_DRAFT_INPUT_NOT_FOUND", file=sys.stderr)
        return 2
    if not path.is_file():
        print("E_DRAFT_INPUT_NOT_FILE", file=sys.stderr)
        return 2
    if path.is_symlink():
        print("E_DRAFT_INPUT_SYMLINK", file=sys.stderr)
        return 2
    if _has_symlink_parent(path, drafts_root):
        print("E_DRAFT_INPUT_SYMLINK_PARENT", file=sys.stderr)
        return 2

    data = load_yaml(path)
    if not isinstance(data, dict):
        print(json.dumps([{
            "code": "E_DRAFT_SCHEMA_INVALID",
            "message": "Draft root must be object",
            "expected": "object",
            "got": type(data).__name__,
            "path": "",
        }], ensure_ascii=False, indent=2), file=sys.stderr)
        return 2

    _, diags = normalize_draft(data, fill_missing=False)
    if diags:
        print(json.dumps(_diag_to_dict(diags), ensure_ascii=False, indent=2), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
