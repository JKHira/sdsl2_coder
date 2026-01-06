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

from sdslv2_builder.errors import Diagnostic
from sdslv2_builder.input_hash import compute_input_hash
from sdslv2_builder.io_atomic import atomic_write_text
from sdslv2_builder.intent_schema import normalize_intent, REQUIRED_TOP_KEYS
from sdslv2_builder.op_yaml import load_yaml, dump_yaml
from sdslv2_builder.schema_versions import INTENT_SCHEMA_VERSION


def _git_rev(root: Path) -> str:
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
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
        path = (base / path).resolve()
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


def _ensure_file_path(path: Path, label: str) -> bool:
    if path.exists() and path.is_dir():
        print(f"E_{label}_IS_DIRECTORY", file=sys.stderr)
        return False
    return True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="Intent YAML path")
    ap.add_argument("--out", default=None, help="Output path (defaults to input)")
    ap.add_argument("--generator-id", default="intent_builder_v1_0", help="Generator id")
    ap.add_argument("--scope-from", default=None, help="Topology file path to derive scope")
    ap.add_argument("--scope-kind", default=None, help="Override scope.kind when missing")
    ap.add_argument("--scope-value", default=None, help="Override scope.value when missing")
    ap.add_argument(
        "--project-root",
        default=None,
        help="Project root (defaults to repo root); outputs must stay under project_root/drafts/intent",
    )
    args = ap.parse_args()

    project_root = Path(args.project_root).resolve() if args.project_root else ROOT
    intent_root = project_root / "drafts" / "intent"
    if intent_root.is_symlink():
        print("E_INTENT_INTENT_ROOT_SYMLINK", file=sys.stderr)
        return 2

    path = _resolve_path(project_root, args.input)
    if not _ensure_under_root(path, intent_root, "E_INTENT_INPUT_NOT_INTENT_ROOT"):
        return 2
    if not path.exists():
        print("E_INTENT_INPUT_NOT_FOUND", file=sys.stderr)
        return 2
    if not path.is_file():
        print("E_INTENT_INPUT_NOT_FILE", file=sys.stderr)
        return 2
    if path.is_symlink():
        print("E_INTENT_INPUT_SYMLINK", file=sys.stderr)
        return 2
    if _has_symlink_parent(path, intent_root):
        print("E_INTENT_INPUT_SYMLINK_PARENT", file=sys.stderr)
        return 2

    data = load_yaml(path)
    if not isinstance(data, dict):
        print(
            json.dumps(
                [
                    {
                        "code": "E_INTENT_SCHEMA_INVALID",
                        "message": "Intent root must be object",
                        "expected": "object",
                        "got": type(data).__name__,
                        "path": "",
                    }
                ],
                ensure_ascii=False,
                indent=2,
            ),
            file=sys.stderr,
        )
        return 2

    for key in REQUIRED_TOP_KEYS:
        if key not in data:
            if key in {"nodes_proposed", "edge_intents_proposed", "questions", "conflicts"}:
                data[key] = []
            elif key == "schema_version":
                data[key] = INTENT_SCHEMA_VERSION
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
                                "code": "E_INTENT_SCOPE_OUTSIDE_PROJECT",
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
                            "code": "E_INTENT_REQUIRED_FIELD_MISSING",
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
                                "code": "E_INTENT_SCOPE_NOT_SSOT",
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

    normalized, diags = normalize_intent(data, fill_missing=False)
    if diags:
        print(json.dumps(_diag_to_dict(diags), ensure_ascii=False, indent=2), file=sys.stderr)
        return 2

    if args.out:
        out_path = _resolve_path(project_root, args.out)
    else:
        out_path = path
    if not _ensure_under_root(out_path, intent_root, "E_INTENT_OUTPUT_OUTSIDE_PROJECT"):
        return 2
    if not _ensure_file_path(out_path, "INTENT_OUTPUT"):
        return 2
    if out_path.is_symlink():
        print("E_INTENT_OUTPUT_SYMLINK", file=sys.stderr)
        return 2
    if _has_symlink_parent(out_path, intent_root):
        print("E_INTENT_OUTPUT_SYMLINK_PARENT", file=sys.stderr)
        return 2

    out_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        atomic_write_text(out_path, dump_yaml(normalized), symlink_code="E_INTENT_OUTPUT_SYMLINK")
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"E_INTENT_WRITE_FAILED:{exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
