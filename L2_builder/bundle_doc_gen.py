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
from sdslv2_builder.io_atomic import atomic_write_text
from sdslv2_builder.input_hash import compute_input_hash
from sdslv2_builder.op_yaml import dump_yaml, load_yaml

DEFAULT_CONTEXT = "OUTPUT/context_pack.yaml"
DEFAULT_OUT = "OUTPUT/bundle_doc.yaml"
DEFAULT_DECISIONS_NEEDED = "OUTPUT/decisions_needed.yaml"
DEFAULT_DIAGNOSTICS_SUMMARY = "OUTPUT/diagnostics_summary.yaml"
GENERATOR_ID = "L2_builder.bundle_doc_gen"
SUPPLEMENTARY_ORDER = [
    "decisions_needed",
    "provenance",
    "diagnostics_summary",
    "links",
    "decision_log",
]


def _quote(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _git_rev(project_root: Path) -> tuple[str, str | None]:
    try:
        result = subprocess.run(
            ["git", "-C", str(project_root), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        return "UNKNOWN", "E_BUNDLE_DOC_SOURCE_REV_GIT_MISSING"
    if result.returncode != 0:
        return "UNKNOWN", "E_BUNDLE_DOC_SOURCE_REV_MISSING"
    rev = result.stdout.strip()
    if not rev:
        return "UNKNOWN", "E_BUNDLE_DOC_SOURCE_REV_EMPTY"
    return rev, None


def _split_context_and_supplementary(text: str) -> tuple[str, list[str]]:
    lines = text.splitlines(keepends=True)
    for idx, line in enumerate(lines):
        if line.strip() == "---":
            return "".join(lines[:idx]), lines[idx:]
    return text, []


def _parse_supplementary_blocks(lines: list[str]) -> list[tuple[str, list[str]]]:
    blocks: list[tuple[str, list[str]]] = []
    idx = 0
    while idx < len(lines):
        line = lines[idx]
        if line.strip() == "":
            idx += 1
            continue
        if line.strip() != "---":
            raise ValueError("E_BUNDLE_DOC_SUPPLEMENTARY_DELIMITER_INVALID")
        if idx + 1 >= len(lines):
            raise ValueError("E_BUNDLE_DOC_SUPPLEMENTARY_HEADER_MISSING")
        header = lines[idx + 1].strip()
        if not header.startswith("Supplementary: "):
            raise ValueError("E_BUNDLE_DOC_SUPPLEMENTARY_HEADER_INVALID")
        key = header.split("Supplementary: ", 1)[1].strip()
        if key not in SUPPLEMENTARY_ORDER:
            raise ValueError(f"E_BUNDLE_DOC_SUPPLEMENTARY_KEY_INVALID:{key}")
        start = idx
        idx += 2
        while idx < len(lines) and lines[idx].strip() != "---":
            idx += 1
        block = lines[start:idx]
        if any(existing_key == key for existing_key, _ in blocks):
            raise ValueError(f"E_BUNDLE_DOC_SUPPLEMENTARY_DUPLICATE:{key}")
        blocks.append((key, block))
    return blocks


def _validate_supplementary_order(keys: list[str]) -> None:
    order = [SUPPLEMENTARY_ORDER.index(key) for key in keys]
    if order != sorted(order):
        raise ValueError("E_BUNDLE_DOC_SUPPLEMENTARY_ORDER")


def _render_provenance(source_rev: str, inputs: list[str]) -> list[str]:
    lines = [
        "---",
        "Supplementary: provenance",
        f"generator: {_quote(GENERATOR_ID)}",
        f"source_rev: {_quote(source_rev)}",
        "inputs:",
    ]
    for item in inputs:
        lines.append(f"  - {_quote(item)}")
    return lines


def _load_supplementary_yaml(path: Path, key: str) -> list[str]:
    data = load_yaml(path)
    if key == "decisions_needed":
        if not isinstance(data, list):
            raise ValueError("E_BUNDLE_DOC_DECISIONS_NEEDED_INVALID")
        if not data:
            return []
    if key == "diagnostics_summary":
        if not isinstance(data, dict):
            raise ValueError("E_BUNDLE_DOC_DIAGNOSTICS_SUMMARY_INVALID")
        errors = data.get("errors")
        diagnostics = data.get("diagnostics")
        if not isinstance(errors, list) or not isinstance(diagnostics, list):
            raise ValueError("E_BUNDLE_DOC_DIAGNOSTICS_SUMMARY_INVALID")
        if not errors and not diagnostics:
            return []
    text = dump_yaml(data).rstrip("\n")
    return text.splitlines() if text else ["[]"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--context-pack", default=DEFAULT_CONTEXT, help="Context Pack path.")
    ap.add_argument("--out", default=DEFAULT_OUT, help="Bundle Doc output path.")
    ap.add_argument("--project-root", default=str(REPO_ROOT), help="Project root.")
    ap.add_argument("--source-rev", default=None, help="Override git source_rev.")
    ap.add_argument(
        "--allow-unknown-source-rev",
        action="store_true",
        help="Allow UNKNOWN source_rev when git rev is unavailable.",
    )
    ap.add_argument("--no-decisions", action="store_true", help="Exclude decisions/edges.yaml from input_hash.")
    ap.add_argument("--include-policy", action="store_true", help="Include policy files in input_hash.")
    args = ap.parse_args()

    project_root = Path(args.project_root).resolve()
    context_path = resolve_path(project_root, args.context_pack)
    out_path = resolve_path(project_root, args.out)

    expected_context = (project_root / DEFAULT_CONTEXT).resolve()
    expected_out = (project_root / DEFAULT_OUT).resolve()
    decisions_needed_path = (project_root / DEFAULT_DECISIONS_NEEDED).resolve()
    diagnostics_summary_path = (project_root / DEFAULT_DIAGNOSTICS_SUMMARY).resolve()

    try:
        ensure_inside(project_root, context_path, "E_BUNDLE_DOC_CONTEXT_OUTSIDE_PROJECT")
        ensure_inside(project_root, out_path, "E_BUNDLE_DOC_OUTPUT_OUTSIDE_PROJECT")
    except ValueError:
        print("E_BUNDLE_DOC_PATH_OUTSIDE_PROJECT", file=sys.stderr)
        return 2

    if context_path != expected_context:
        print("E_BUNDLE_DOC_CONTEXT_PATH_INVALID", file=sys.stderr)
        return 2
    if out_path != expected_out:
        print("E_BUNDLE_DOC_OUTPUT_PATH_INVALID", file=sys.stderr)
        return 2

    if has_symlink_parent(context_path, project_root) or has_symlink_parent(out_path.parent, project_root):
        print("E_BUNDLE_DOC_SYMLINK", file=sys.stderr)
        return 2

    if not context_path.exists():
        print("E_BUNDLE_DOC_CONTEXT_NOT_FOUND", file=sys.stderr)
        return 2
    if context_path.is_dir():
        print("E_BUNDLE_DOC_CONTEXT_IS_DIRECTORY", file=sys.stderr)
        return 2
    if out_path.exists() and out_path.is_symlink():
        print("E_BUNDLE_DOC_OUTPUT_SYMLINK", file=sys.stderr)
        return 2
    if out_path.exists() and out_path.is_dir():
        print("E_BUNDLE_DOC_OUTPUT_IS_DIRECTORY", file=sys.stderr)
        return 2
    if out_path.parent.exists() and not out_path.parent.is_dir():
        print("E_BUNDLE_DOC_OUTPUT_PARENT_NOT_DIR", file=sys.stderr)
        return 2

    output_root = (project_root / "OUTPUT").resolve()

    if decisions_needed_path.exists():
        try:
            ensure_inside(project_root, decisions_needed_path, "E_BUNDLE_DOC_DECISIONS_NEEDED_OUTSIDE_PROJECT")
        except ValueError:
            print("E_BUNDLE_DOC_DECISIONS_NEEDED_OUTSIDE_PROJECT", file=sys.stderr)
            return 2
        try:
            decisions_needed_path.resolve().relative_to(output_root)
        except ValueError:
            print("E_BUNDLE_DOC_DECISIONS_NEEDED_OUTSIDE_OUTPUT", file=sys.stderr)
            return 2
        if has_symlink_parent(decisions_needed_path, project_root) or decisions_needed_path.is_symlink():
            print("E_BUNDLE_DOC_DECISIONS_NEEDED_SYMLINK", file=sys.stderr)
            return 2
        if decisions_needed_path.is_dir():
            print("E_BUNDLE_DOC_DECISIONS_NEEDED_IS_DIRECTORY", file=sys.stderr)
            return 2

    if diagnostics_summary_path.exists():
        try:
            ensure_inside(project_root, diagnostics_summary_path, "E_BUNDLE_DOC_DIAGNOSTICS_SUMMARY_OUTSIDE_PROJECT")
        except ValueError:
            print("E_BUNDLE_DOC_DIAGNOSTICS_SUMMARY_OUTSIDE_PROJECT", file=sys.stderr)
            return 2
        try:
            diagnostics_summary_path.resolve().relative_to(output_root)
        except ValueError:
            print("E_BUNDLE_DOC_DIAGNOSTICS_SUMMARY_OUTSIDE_OUTPUT", file=sys.stderr)
            return 2
        if has_symlink_parent(diagnostics_summary_path, project_root) or diagnostics_summary_path.is_symlink():
            print("E_BUNDLE_DOC_DIAGNOSTICS_SUMMARY_SYMLINK", file=sys.stderr)
            return 2
        if diagnostics_summary_path.is_dir():
            print("E_BUNDLE_DOC_DIAGNOSTICS_SUMMARY_IS_DIRECTORY", file=sys.stderr)
            return 2

    extra_inputs: list[Path] = []
    if decisions_needed_path.exists():
        extra_inputs.append(decisions_needed_path)
    if diagnostics_summary_path.exists():
        extra_inputs.append(diagnostics_summary_path)

    if args.source_rev is not None:
        source_rev = args.source_rev.strip()
        if not source_rev:
            print("E_BUNDLE_DOC_SOURCE_REV_INVALID", file=sys.stderr)
            return 2
        if source_rev == "UNKNOWN" and not args.allow_unknown_source_rev:
            print("E_BUNDLE_DOC_SOURCE_REV_UNKNOWN", file=sys.stderr)
            return 2
    else:
        source_rev, warn = _git_rev(project_root)
        if warn:
            print(warn, file=sys.stderr)
            if not args.allow_unknown_source_rev:
                return 2

    try:
        result = compute_input_hash(
            project_root,
            include_decisions=not args.no_decisions,
            include_policy=args.include_policy,
            extra_inputs=extra_inputs,
        )
    except Exception as exc:  # pragma: no cover - defensive
        print(f"E_BUNDLE_DOC_INPUT_HASH_FAILED:{exc}", file=sys.stderr)
        return 2

    inputs_rel = []
    for path in result.inputs:
        rel = path.resolve().relative_to(project_root.resolve()).as_posix()
        inputs_rel.append(rel)
    inputs_rel.append(f"input_hash:{result.input_hash}")

    raw_text = context_path.read_text(encoding="utf-8")
    _, sup_lines = _split_context_and_supplementary(raw_text)
    try:
        existing_blocks = _parse_supplementary_blocks(sup_lines) if sup_lines else []
        existing_keys = [key for key, _ in existing_blocks]
        if existing_keys:
            _validate_supplementary_order(existing_keys)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    supplement_lines: list[str] = []

    added_keys: list[str] = []
    last_existing_index = -1
    if existing_keys:
        last_existing_index = max(SUPPLEMENTARY_ORDER.index(key) for key in existing_keys)

    def append_block(key: str, lines: list[str]) -> bool:
        nonlocal supplement_lines
        if not lines:
            return False
        if key in existing_keys:
            return False
        if SUPPLEMENTARY_ORDER.index(key) < last_existing_index:
            print("E_BUNDLE_DOC_SUPPLEMENTARY_ORDER", file=sys.stderr)
            raise ValueError("E_BUNDLE_DOC_SUPPLEMENTARY_ORDER")
        supplement_lines.extend(["---", f"Supplementary: {key}"])
        supplement_lines.extend(lines)
        supplement_lines.append("")
        added_keys.append(key)
        return True

    try:
        if decisions_needed_path.exists():
            decisions_lines = _load_supplementary_yaml(decisions_needed_path, "decisions_needed")
            append_block("decisions_needed", decisions_lines)
        if "provenance" not in existing_keys:
            append_block("provenance", _render_provenance(source_rev, inputs_rel)[2:])
        if diagnostics_summary_path.exists():
            diagnostics_lines = _load_supplementary_yaml(diagnostics_summary_path, "diagnostics_summary")
            append_block("diagnostics_summary", diagnostics_lines)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    supplement = "\n".join(supplement_lines)
    separator = ""
    if supplement and not raw_text.endswith("\n"):
        separator = "\n"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        atomic_write_text(out_path, raw_text + separator + supplement, symlink_code="E_BUNDLE_DOC_OUTPUT_SYMLINK")
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"E_BUNDLE_DOC_WRITE_FAILED:{exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
