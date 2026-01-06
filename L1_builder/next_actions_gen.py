#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from L1_builder.decisions_lint import parse_decisions_file
from L1_builder.readiness_check import _load_intent_files, _validate_intent_data
from sdslv2_builder.io_atomic import atomic_write_text
from sdslv2_builder.op_yaml import dump_yaml

DEFAULT_DECISIONS = "decisions/edges.yaml"
DEFAULT_INTENT_ROOT = "drafts/intent"
DEFAULT_OUT_DECISIONS = "OUTPUT/decisions_needed.yaml"
DEFAULT_OUT_DIAGNOSTICS = "OUTPUT/diagnostics_summary.yaml"


def _ensure_inside(project_root: Path, path: Path, code: str) -> None:
    try:
        path.resolve().relative_to(project_root.resolve())
    except ValueError as exc:
        raise ValueError(code) from exc


def _has_symlink_parent(path: Path, stop: Path) -> bool:
    for parent in [path, *path.parents]:
        if parent == stop:
            break
        if parent.is_symlink():
            return True
    return False


def _collect_intents(project_root: Path) -> tuple[list[str], list[str]]:
    intent_ids: list[str] = []
    codes: list[str] = []
    intents, diags = _load_intent_files(project_root)
    codes.extend([d.code for d in diags])
    for entry in intents:
        normalized, file_diags = _validate_intent_data(entry["data"], entry["path"])
        codes.extend([d.code for d in file_diags])
        for intent in normalized.get("intents", []):
            intent_id = intent.get("id")
            if isinstance(intent_id, str) and intent_id:
                intent_ids.append(intent_id)
    return sorted(set(intent_ids)), codes


def _collect_decisions(project_root: Path, decisions_path: Path) -> tuple[list[str], list[str]]:
    codes: list[str] = []
    if not decisions_path.exists():
        codes.append("E_NEXT_ACTIONS_DECISIONS_MISSING")
        return [], codes
    if decisions_path.is_dir():
        codes.append("E_NEXT_ACTIONS_DECISIONS_IS_DIRECTORY")
        return [], codes
    if decisions_path.is_symlink() or _has_symlink_parent(decisions_path, project_root):
        raise ValueError("E_NEXT_ACTIONS_DECISIONS_SYMLINK")

    data, diags = parse_decisions_file(decisions_path, project_root)
    codes.extend([d.code for d in diags])
    if not data:
        return [], codes
    edges = data.get("edges")
    if not isinstance(edges, list):
        codes.append("E_NEXT_ACTIONS_DECISIONS_INVALID")
        return [], codes
    decision_ids = []
    for edge in edges:
        if not isinstance(edge, dict):
            continue
        rel_id = edge.get("id")
        if isinstance(rel_id, str) and rel_id:
            decision_ids.append(rel_id)
    return sorted(set(decision_ids)), codes


def _write_output(path: Path, payload: str, symlink_code: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(path, payload, symlink_code=symlink_code)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project-root", default=str(ROOT), help="Project root")
    ap.add_argument("--intent-root", default=DEFAULT_INTENT_ROOT, help="drafts/intent root")
    ap.add_argument("--decisions-path", default=DEFAULT_DECISIONS, help="decisions/edges.yaml path")
    ap.add_argument("--out-decisions", default=DEFAULT_OUT_DECISIONS, help="OUTPUT/decisions_needed.yaml")
    ap.add_argument("--out-diagnostics", default=DEFAULT_OUT_DIAGNOSTICS, help="OUTPUT/diagnostics_summary.yaml")
    args = ap.parse_args()

    project_root = Path(args.project_root).resolve()
    intent_root = (project_root / args.intent_root).resolve()
    decisions_path = (project_root / args.decisions_path).resolve()
    out_decisions = (project_root / args.out_decisions).resolve()
    out_diagnostics = (project_root / args.out_diagnostics).resolve()

    try:
        _ensure_inside(project_root, intent_root, "E_NEXT_ACTIONS_INTENT_OUTSIDE_PROJECT")
        _ensure_inside(project_root, decisions_path, "E_NEXT_ACTIONS_DECISIONS_OUTSIDE_PROJECT")
        _ensure_inside(project_root, out_decisions, "E_NEXT_ACTIONS_OUTPUT_OUTSIDE_PROJECT")
        _ensure_inside(project_root, out_diagnostics, "E_NEXT_ACTIONS_OUTPUT_OUTSIDE_PROJECT")
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    output_root = (project_root / "OUTPUT").resolve()
    for out_path in (out_decisions, out_diagnostics):
        try:
            out_path.resolve().relative_to(output_root)
        except ValueError:
            print("E_NEXT_ACTIONS_OUTPUT_OUTSIDE_OUTPUT", file=sys.stderr)
            return 2
        if out_path.exists() and out_path.is_dir():
            print("E_NEXT_ACTIONS_OUTPUT_IS_DIRECTORY", file=sys.stderr)
            return 2
        if out_path.is_symlink() or _has_symlink_parent(out_path, project_root):
            print("E_NEXT_ACTIONS_OUTPUT_SYMLINK", file=sys.stderr)
            return 2
        if out_path.parent.exists() and not out_path.parent.is_dir():
            print("E_NEXT_ACTIONS_OUTPUT_PARENT_NOT_DIR", file=sys.stderr)
            return 2

    if intent_root.exists():
        if intent_root.is_symlink() or _has_symlink_parent(intent_root, project_root):
            print("E_NEXT_ACTIONS_INTENT_SYMLINK", file=sys.stderr)
            return 2
    expected_intent = (project_root / DEFAULT_INTENT_ROOT).resolve()
    if intent_root != expected_intent:
        print("E_NEXT_ACTIONS_INTENT_PATH_INVALID", file=sys.stderr)
        return 2

    intent_ids, intent_codes = _collect_intents(project_root)

    decisions_ids, decision_codes = _collect_decisions(project_root, decisions_path)

    codes = sorted(set(intent_codes + decision_codes))
    errors = sorted({code for code in codes if code.startswith("E_")})
    diagnostics = sorted({code for code in codes if not code.startswith("E_")})

    missing = [intent_id for intent_id in intent_ids if intent_id not in set(decisions_ids)]
    decisions_needed = [
        {"id": intent_id, "summary": f"missing decision for edge_intent {intent_id}", "scope": "topology"}
        for intent_id in missing
    ]

    diagnostics_summary = {"errors": errors, "diagnostics": diagnostics}

    try:
        _write_output(out_decisions, dump_yaml(decisions_needed), "E_NEXT_ACTIONS_OUTPUT_SYMLINK")
        _write_output(out_diagnostics, dump_yaml(diagnostics_summary), "E_NEXT_ACTIONS_OUTPUT_SYMLINK")
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"E_NEXT_ACTIONS_WRITE_FAILED:{exc}", file=sys.stderr)
        return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
