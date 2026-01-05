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

from L2_builder.common import ROOT as REPO_ROOT, ensure_inside, has_symlink_parent, resolve_path
from sdslv2_builder.errors import Diagnostic, json_pointer
from sdslv2_builder.input_hash import compute_input_hash
from sdslv2_builder.lint import _capture_metadata, _parse_metadata_pairs
from sdslv2_builder.op_yaml import load_yaml

DEFAULT_INPUT = "OUTPUT/implementation_skeleton.yaml"


def _diag(diags: list[Diagnostic], code: str, message: str, expected: str, got: str, path: str) -> None:
    diags.append(Diagnostic(code=code, message=message, expected=expected, got=got, path=path))


def _print_diags(diags: list[Diagnostic]) -> None:
    payload = [d.to_dict() for d in diags]
    print(json.dumps(payload, ensure_ascii=False, indent=2), file=sys.stderr)


def _git_rev(project_root: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(project_root), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise ValueError("E_CONFORMANCE_SOURCE_REV_MISSING")
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
    ap.add_argument("--input", default=DEFAULT_INPUT, help="Skeleton file path.")
    ap.add_argument("--project-root", default=str(REPO_ROOT), help="Project root.")
    ap.add_argument("--no-decisions", action="store_true", help="Exclude decisions/edges.yaml from input_hash.")
    ap.add_argument("--check-source-rev", action="store_true", help="Check source_rev against git.")
    args = ap.parse_args()

    project_root = Path(args.project_root).resolve()
    input_path = resolve_path(project_root, args.input)

    try:
        ensure_inside(project_root, input_path, "E_CONFORMANCE_INPUT_OUTSIDE_PROJECT")
    except ValueError:
        print("E_CONFORMANCE_INPUT_OUTSIDE_PROJECT", file=sys.stderr)
        return 2

    expected = (project_root / DEFAULT_INPUT).resolve()
    if input_path != expected:
        print("E_CONFORMANCE_INPUT_PATH_INVALID", file=sys.stderr)
        return 2

    if has_symlink_parent(input_path, project_root) or input_path.is_symlink():
        print("E_CONFORMANCE_INPUT_SYMLINK", file=sys.stderr)
        return 2

    if not input_path.exists():
        print("E_CONFORMANCE_INPUT_NOT_FOUND", file=sys.stderr)
        return 2

    try:
        data = load_yaml(input_path)
    except Exception as exc:
        print(f"E_CONFORMANCE_PARSE_FAILED:{exc}", file=sys.stderr)
        return 2

    if not isinstance(data, dict):
        print("E_CONFORMANCE_SCHEMA_INVALID", file=sys.stderr)
        return 2

    diags: list[Diagnostic] = []

    input_hash = data.get("input_hash")
    if not isinstance(input_hash, str) or not input_hash:
        _diag(diags, "E_CONFORMANCE_INPUT_HASH_INVALID", "input_hash missing", "sha256:*", str(input_hash), json_pointer("input_hash"))

    source_rev = data.get("source_rev")
    if args.check_source_rev:
        try:
            current = _git_rev(project_root)
        except ValueError as exc:
            _diag(diags, str(exc), "git rev missing", "git rev", "missing", json_pointer("source_rev"))
            current = None
        if current and source_rev != current:
            _diag(diags, "E_CONFORMANCE_SOURCE_REV_MISMATCH", "source_rev mismatch", current, str(source_rev), json_pointer("source_rev"))

    try:
        result = compute_input_hash(project_root, include_decisions=not args.no_decisions)
    except Exception as exc:
        print(f"E_CONFORMANCE_INPUT_HASH_FAILED:{exc}", file=sys.stderr)
        return 2

    if isinstance(input_hash, str) and input_hash != result.input_hash:
        _diag(diags, "E_CONFORMANCE_INPUT_HASH_MISMATCH", "input_hash mismatch", result.input_hash, input_hash, json_pointer("input_hash"))

    contract_root = project_root / "sdsl2" / "contract"
    contract_files = sorted(p for p in contract_root.rglob("*.sdsl2") if p.is_file())
    structures: set[str] = set()
    rules: set[str] = set()
    for path in contract_files:
        if has_symlink_parent(path, project_root) or path.is_symlink():
            print("E_CONFORMANCE_CONTRACT_SYMLINK", file=sys.stderr)
            return 2
        text = path.read_text(encoding="utf-8")
        lines = text.splitlines()
        structures.update(_collect_ids(lines, "Structure"))
        rules.update(_collect_ids(lines, "Rule"))

    expected_structures = sorted(structures)
    expected_rules = sorted(rules)

    got_structures = data.get("structures")
    if got_structures != expected_structures:
        _diag(diags, "E_CONFORMANCE_STRUCTURES_MISMATCH", "structures mismatch", str(expected_structures), str(got_structures), json_pointer("structures"))

    got_rules = data.get("rules")
    if got_rules != expected_rules:
        _diag(diags, "E_CONFORMANCE_RULES_MISMATCH", "rules mismatch", str(expected_rules), str(got_rules), json_pointer("rules"))

    if diags:
        _print_diags(diags)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
