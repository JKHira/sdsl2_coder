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

DEFAULT_CONTEXT = "OUTPUT/context_pack.yaml"
DEFAULT_OUT = "OUTPUT/bundle_doc.yaml"
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


def _git_rev(project_root: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(project_root), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise ValueError("E_BUNDLE_DOC_SOURCE_REV_MISSING")
    return result.stdout.strip()


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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--context-pack", default=DEFAULT_CONTEXT, help="Context Pack path.")
    ap.add_argument("--out", default=DEFAULT_OUT, help="Bundle Doc output path.")
    ap.add_argument("--project-root", default=str(REPO_ROOT), help="Project root.")
    ap.add_argument("--source-rev", default=None, help="Override git source_rev.")
    ap.add_argument("--no-decisions", action="store_true", help="Exclude decisions/edges.yaml from input_hash.")
    ap.add_argument("--include-policy", action="store_true", help="Include policy files in input_hash.")
    args = ap.parse_args()

    project_root = Path(args.project_root).resolve()
    context_path = resolve_path(project_root, args.context_pack)
    out_path = resolve_path(project_root, args.out)

    expected_context = (project_root / DEFAULT_CONTEXT).resolve()
    expected_out = (project_root / DEFAULT_OUT).resolve()

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

    try:
        source_rev = args.source_rev or _git_rev(project_root)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    try:
        result = compute_input_hash(
            project_root,
            include_decisions=not args.no_decisions,
            include_policy=args.include_policy,
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
    if "provenance" not in existing_keys:
        if existing_keys and SUPPLEMENTARY_ORDER.index(existing_keys[-1]) > SUPPLEMENTARY_ORDER.index("provenance"):
            print("E_BUNDLE_DOC_SUPPLEMENTARY_ORDER", file=sys.stderr)
            return 2
        supplement_lines.extend(_render_provenance(source_rev, inputs_rel))
        supplement_lines.append("")

    supplement = "\n".join(supplement_lines)
    separator = ""
    if supplement and not raw_text.endswith("\n"):
        separator = "\n"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(raw_text + separator + supplement, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
