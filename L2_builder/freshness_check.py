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

DEFAULT_INPUT = "OUTPUT/bundle_doc.yaml"


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
        raise ValueError("E_FRESHNESS_SOURCE_REV_MISSING")
    return result.stdout.strip()


def _parse_provenance(lines: list[str]) -> dict[str, object] | None:
    start = None
    for idx, line in enumerate(lines):
        if line.strip() == "Supplementary: provenance":
            start = idx + 1
            break
    if start is None:
        return None

    data: dict[str, object] = {}
    i = start
    while i < len(lines):
        line = lines[i]
        if line.strip().startswith("Supplementary:") and i > start:
            break
        if line.strip() == "---" and i > start:
            break
        if line.strip() == "":
            i += 1
            continue
        if line.startswith("inputs:"):
            i += 1
            items: list[str] = []
            while i < len(lines):
                sub = lines[i]
                if not sub.startswith("  - "):
                    break
                value = sub[len("  - "):].strip()
                if len(value) >= 2 and value[0] == value[-1] == '"':
                    value = value[1:-1]
                items.append(value)
                i += 1
            data["inputs"] = items
            continue
        if ":" in line:
            key, rest = line.split(":", 1)
            value = rest.strip()
            if len(value) >= 2 and value[0] == value[-1] == '"':
                value = value[1:-1]
            data[key.strip()] = value
        i += 1
    return data


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default=DEFAULT_INPUT, help="Bundle Doc path.")
    ap.add_argument("--project-root", default=str(REPO_ROOT), help="Project root.")
    ap.add_argument("--no-decisions", action="store_true", help="Exclude decisions/edges.yaml from input_hash.")
    ap.add_argument(
        "--include-decisions",
        action="store_true",
        help="Include decisions/edges.yaml in input_hash (default: excluded).",
    )
    ap.add_argument("--include-policy", action="store_true", help="Include policy files in input_hash.")
    ap.add_argument("--allow-missing", action="store_true", help="Return OK if bundle doc missing.")
    ap.add_argument("--check-source-rev", action="store_true", help="Check source_rev against git.")
    args = ap.parse_args()

    project_root = Path(args.project_root).resolve()
    input_path = resolve_path(project_root, args.input)

    try:
        ensure_inside(project_root, input_path, "E_FRESHNESS_INPUT_OUTSIDE_PROJECT")
    except ValueError:
        print("E_FRESHNESS_INPUT_OUTSIDE_PROJECT", file=sys.stderr)
        return 2

    expected = (project_root / DEFAULT_INPUT).resolve()
    if input_path != expected:
        print("E_FRESHNESS_INPUT_PATH_INVALID", file=sys.stderr)
        return 2

    if not input_path.exists():
        return 0 if args.allow_missing else 2

    if has_symlink_parent(input_path, project_root) or input_path.is_symlink():
        print("E_FRESHNESS_INPUT_SYMLINK", file=sys.stderr)
        return 2

    output_root = (project_root / "OUTPUT").resolve()
    decisions_needed_path = (project_root / "OUTPUT" / "decisions_needed.yaml").resolve()
    diagnostics_summary_path = (project_root / "OUTPUT" / "diagnostics_summary.yaml").resolve()
    extra_inputs: list[Path] = []
    for path in [decisions_needed_path, diagnostics_summary_path]:
        if not path.exists():
            continue
        try:
            path.resolve().relative_to(output_root)
        except ValueError:
            print("E_FRESHNESS_SUPPLEMENTARY_OUTSIDE_OUTPUT", file=sys.stderr)
            return 2
        if has_symlink_parent(path, project_root) or path.is_symlink():
            print("E_FRESHNESS_SUPPLEMENTARY_SYMLINK", file=sys.stderr)
            return 2
        if path.is_dir():
            print("E_FRESHNESS_SUPPLEMENTARY_IS_DIRECTORY", file=sys.stderr)
            return 2
        extra_inputs.append(path)

    lines = input_path.read_text(encoding="utf-8").splitlines()
    provenance = _parse_provenance(lines)
    if provenance is None:
        print("E_FRESHNESS_PROVENANCE_MISSING", file=sys.stderr)
        return 2

    diags: list[Diagnostic] = []
    source_rev = provenance.get("source_rev")
    if args.check_source_rev:
        try:
            current = _git_rev(project_root)
        except ValueError as exc:
            _diag(diags, str(exc), "git rev missing", "git rev", "missing", json_pointer("provenance", "source_rev"))
            current = None
        if current and source_rev != current:
            _diag(diags, "E_FRESHNESS_SOURCE_REV_MISMATCH", "source_rev mismatch", current, str(source_rev), json_pointer("provenance", "source_rev"))

    inputs = provenance.get("inputs")
    input_hash = None
    if isinstance(inputs, list):
        for item in inputs:
            if isinstance(item, str) and item.startswith("input_hash:"):
                input_hash = item.split(":", 1)[1]
                break
    if not input_hash:
        _diag(diags, "E_FRESHNESS_INPUT_HASH_MISSING", "input_hash missing in provenance.inputs", "input_hash:<sha256>", "missing", json_pointer("provenance", "inputs"))

    if args.no_decisions and args.include_decisions:
        print("E_FRESHNESS_DECISIONS_FLAG_CONFLICT", file=sys.stderr)
        return 2
    include_decisions = bool(args.include_decisions)
    try:
        result = compute_input_hash(
            project_root,
            include_decisions=include_decisions,
            include_policy=args.include_policy,
            extra_inputs=extra_inputs,
        )
    except Exception as exc:
        print(f"E_FRESHNESS_INPUT_HASH_FAILED:{exc}", file=sys.stderr)
        return 2

    if input_hash and input_hash != result.input_hash:
        _diag(diags, "E_FRESHNESS_INPUT_HASH_MISMATCH", "input_hash mismatch", result.input_hash, input_hash, json_pointer("provenance", "inputs"))

    if diags:
        _print_diags(diags)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
