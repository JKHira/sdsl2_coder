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

from sdslv2_builder.draft_schema import normalize_draft, REQUIRED_TOP_KEYS
from sdslv2_builder.errors import Diagnostic
from sdslv2_builder.input_hash import compute_input_hash
from sdslv2_builder.io_atomic import atomic_write_text
from sdslv2_builder.op_yaml import load_yaml, dump_yaml
from sdslv2_builder.schema_versions import DRAFT_SCHEMA_VERSION


def _git_rev(root: Path) -> str:
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return "UNKNOWN"
    if proc.returncode != 0:
        return "UNKNOWN"
    return proc.stdout.strip() or "UNKNOWN"


def _diag_to_dict(diags: list[Diagnostic]) -> list[dict]:
    return [d.to_dict() for d in diags]


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


def _ensure_under(path: Path, root: Path, label: str) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        print(f"E_DRAFT_{label}_OUTSIDE_PROJECT", file=sys.stderr)
        return False
    return True


def _ensure_under_root(path: Path, root: Path, code: str) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        print(code, file=sys.stderr)
        return False
    return True


def _ensure_file_path(path: Path, label: str) -> bool:
    if path.exists() and path.is_dir():
        print(f"E_{label}_IS_DIRECTORY", file=sys.stderr)
        return False
    return True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="Draft YAML path")
    ap.add_argument("--out", default=None, help="Output path (defaults to input)")
    ap.add_argument("--generator-id", default="draft_builder_v0_1", help="Generator id")
    ap.add_argument("--scope-from", default=None, help="Topology file path to derive scope")
    ap.add_argument("--scope-kind", default=None, help="Override scope.kind when missing")
    ap.add_argument("--scope-value", default=None, help="Override scope.value when missing")
    ap.add_argument(
        "--project-root",
        default=None,
        help="Project root (defaults to repo root); outputs must stay under project_root/drafts",
    )
    args = ap.parse_args()

    project_root = Path(args.project_root).resolve() if args.project_root else ROOT
    drafts_root = project_root / "drafts"
    if drafts_root.is_symlink():
        print("E_DRAFT_DRAFTS_ROOT_SYMLINK", file=sys.stderr)
        return 2

    path = _resolve_path(project_root, args.input)
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

    # Fill missing keys before normalization.
    for key in REQUIRED_TOP_KEYS:
        if key not in data:
            if key in {"nodes_proposed", "edge_intents_proposed", "contract_candidates", "questions", "conflicts"}:
                data[key] = []
            elif key == "schema_version":
                data[key] = DRAFT_SCHEMA_VERSION
            else:
                data[key] = ""

    if "scope" not in data or not isinstance(data.get("scope"), dict):
        scope_kind = args.scope_kind
        scope_value = args.scope_value
        if args.scope_from:
            scope_kind = scope_kind or "file"
            scope_path = _resolve_path(project_root, args.scope_from)
            try:
                scope_value = str(scope_path.resolve().relative_to(project_root.resolve()))
            except ValueError:
                print(
                    json.dumps(
                        [
                            {
                                "code": "E_DRAFT_SCOPE_OUTSIDE_PROJECT",
                                "message": "scope_from must be under project_root",
                                "expected": "project_root relative path",
                                "got": str(scope_path),
                                "path": "/scope",
                            }
                        ],
                        ensure_ascii=False,
                        indent=2,
                    ),
                    file=sys.stderr,
                )
                return 2
        if not scope_kind or not scope_value:
            print(
                json.dumps(
                    [
                        {
                            "code": "E_DRAFT_REQUIRED_FIELD_MISSING",
                            "message": "scope must be present",
                            "expected": "object",
                            "got": type(data.get("scope")).__name__,
                            "path": "/scope",
                        }
                    ],
                    ensure_ascii=False,
                    indent=2,
                ),
                file=sys.stderr,
            )
            return 2
        if scope_kind == "file":
            normalized = scope_value.replace("\\", "/")
            if not normalized.startswith("sdsl2/topology/") or not normalized.endswith(".sdsl2"):
                print(
                    json.dumps(
                        [
                            {
                                "code": "E_DRAFT_SCOPE_NOT_SSOT",
                                "message": "scope.kind=file must point to sdsl2/topology",
                                "expected": "sdsl2/topology/<file>.sdsl2",
                                "got": scope_value,
                                "path": "/scope/value",
                            }
                        ],
                        ensure_ascii=False,
                        indent=2,
                    ),
                    file=sys.stderr,
                )
                return 2
        data["scope"] = {"kind": scope_kind, "value": scope_value}

    data["generator_id"] = args.generator_id or data.get("generator_id", "")
    data["source_rev"] = _git_rev(project_root)

    try:
        input_hash = compute_input_hash(
            project_root,
            include_decisions=False,
        )
    except (FileNotFoundError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    data["input_hash"] = input_hash.input_hash

    normalized, diags = normalize_draft(data, fill_missing=False)
    if diags:
        print(json.dumps(_diag_to_dict(diags), ensure_ascii=False, indent=2), file=sys.stderr)
        return 2

    if args.out:
        out_path = _resolve_path(project_root, args.out)
    else:
        out_path = path
    if not _ensure_under(out_path, drafts_root, "DRAFTS"):
        return 2
    if not _ensure_file_path(out_path, "DRAFT_OUTPUT"):
        return 2
    if out_path.is_symlink():
        print("E_DRAFT_OUTPUT_SYMLINK", file=sys.stderr)
        return 2
    if _has_symlink_parent(out_path, drafts_root):
        print("E_DRAFT_OUTPUT_SYMLINK_PARENT", file=sys.stderr)
        return 2
    out_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        atomic_write_text(out_path, dump_yaml(normalized), symlink_code="E_DRAFT_OUTPUT_SYMLINK")
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"E_DRAFT_WRITE_FAILED:{exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
