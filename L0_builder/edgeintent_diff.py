#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import difflib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sdslv2_builder.intent_schema import normalize_intent
from sdslv2_builder.lint import _capture_metadata, _parse_metadata_pairs
from sdslv2_builder.op_yaml import load_yaml

EDGEINTENT_KIND = "EdgeIntent"


def _escape(value: str) -> str:
    value = value.replace("\\", "\\\\").replace('"', '\\"')
    value = value.replace("\n", "\\n")
    return value


def _strip_quotes(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


def _extract_edgeintents(lines: list[str]) -> dict[str, tuple[int, int]]:
    intents: dict[str, tuple[int, int]] = {}
    for idx, line in enumerate(lines):
        if not line.lstrip().startswith("@EdgeIntent"):
            continue
        brace_idx = line.find("{")
        if brace_idx == -1:
            continue
        meta, end_line = _capture_metadata(lines, idx, brace_idx)
        pairs = _parse_metadata_pairs(meta)
        meta_map = {k: v for k, v in pairs}
        intent_id = meta_map.get("id")
        if not intent_id:
            continue
        intent_id = _strip_quotes(intent_id)
        intents[intent_id] = (idx, end_line)
    return intents


def _format_intent_lines(intent: dict[str, str]) -> list[str]:
    parts: list[str] = [
        f'  id:"{_escape(intent["id"])}",',
        f'  from:@Node.{intent["from"]},',
        f'  to:@Node.{intent["to"]},',
    ]
    if intent.get("direction"):
        parts.append(f'  direction:"{_escape(intent["direction"])}",')
    if intent.get("channel"):
        parts.append(f'  channel:"{_escape(intent["channel"])}",')
    if intent.get("note"):
        parts.append(f'  note:"{_escape(intent["note"])}",')
    return ["@EdgeIntent {"] + parts + ["}"]


def _find_insert_index(lines: list[str]) -> int:
    last = -1
    idx = 0
    while idx < len(lines):
        stripped = lines[idx].lstrip()
        if stripped.startswith("@Node") or stripped.startswith("@EdgeIntent"):
            last = idx
            if stripped.startswith("@EdgeIntent"):
                brace_idx = lines[idx].find("{")
                if brace_idx != -1:
                    _, end_line = _capture_metadata(lines, idx, brace_idx)
                    last = end_line
                    idx = end_line + 1
                    continue
        idx += 1
    return last + 1


def _has_symlink_parent(path: Path, stop: Path) -> bool:
    for parent in [path, *path.parents]:
        if parent == stop:
            break
        if parent.is_symlink():
            return True
    return False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="Topology .sdsl2 file")
    ap.add_argument("--draft", required=True, help="Draft YAML with edge_intents_proposed")
    ap.add_argument(
        "--project-root",
        default=None,
        help="Project root (defaults to repo root); input paths can be relative to it",
    )
    args = ap.parse_args()

    project_root = Path(args.project_root).resolve() if args.project_root else ROOT
    topo_path = Path(args.input)
    if not topo_path.is_absolute():
        topo_path = (project_root / topo_path).absolute()
    draft_path = Path(args.draft)
    if not draft_path.is_absolute():
        draft_path = (project_root / draft_path).absolute()
    try:
        topo_path.resolve().relative_to(project_root.resolve())
        draft_path.resolve().relative_to(project_root.resolve())
    except ValueError:
        print("E_EDGEINTENT_DIFF_INPUT_OUTSIDE_PROJECT", file=sys.stderr)
        return 2
    ssot_root = (project_root / "sdsl2" / "topology").absolute()
    if ssot_root.is_symlink() or _has_symlink_parent(ssot_root, project_root):
        print("E_EDGEINTENT_DIFF_SSOT_ROOT_SYMLINK", file=sys.stderr)
        return 2
    try:
        topo_path.resolve().relative_to(ssot_root)
    except ValueError:
        print("E_EDGEINTENT_DIFF_INPUT_NOT_SSOT", file=sys.stderr)
        return 2
    if not topo_path.is_file() or topo_path.suffix != ".sdsl2":
        print("E_EDGEINTENT_DIFF_INPUT_NOT_SSOT", file=sys.stderr)
        return 2
    if topo_path.is_symlink() or _has_symlink_parent(topo_path, project_root):
        print("E_EDGEINTENT_DIFF_INPUT_SYMLINK", file=sys.stderr)
        return 2
    intent_root = (project_root / "drafts" / "intent").absolute()
    if intent_root.is_symlink() or _has_symlink_parent(intent_root, project_root):
        print("E_EDGEINTENT_DIFF_INTENT_ROOT_SYMLINK", file=sys.stderr)
        return 2
    try:
        draft_path.resolve().relative_to(intent_root)
    except ValueError:
        print("E_EDGEINTENT_DIFF_DRAFT_NOT_INTENT_ROOT", file=sys.stderr)
        return 2
    if draft_path.is_symlink() or _has_symlink_parent(draft_path, intent_root):
        print("E_EDGEINTENT_DIFF_DRAFT_SYMLINK", file=sys.stderr)
        return 2
    if not draft_path.exists():
        print("E_EDGEINTENT_DIFF_INPUT_NOT_FOUND", file=sys.stderr)
        return 2

    preview_path = (project_root / "OUTPUT" / "intent_preview.sdsl2").absolute()
    try:
        preview_path.relative_to(project_root.resolve())
    except ValueError:
        print("E_EDGEINTENT_DIFF_PREVIEW_OUTSIDE_PROJECT", file=sys.stderr)
        return 2
    if preview_path.exists() and preview_path.is_symlink():
        print("E_EDGEINTENT_DIFF_PREVIEW_SYMLINK", file=sys.stderr)
        return 2
    if _has_symlink_parent(preview_path, project_root):
        print("E_EDGEINTENT_DIFF_PREVIEW_SYMLINK_PARENT", file=sys.stderr)
        return 2
    if preview_path.exists() and preview_path.is_dir():
        print("E_EDGEINTENT_DIFF_PREVIEW_IS_DIR", file=sys.stderr)
        return 2

    draft_data = load_yaml(draft_path)
    if not isinstance(draft_data, dict):
        print("E_EDGEINTENT_DIFF_DRAFT_INVALID", file=sys.stderr)
        return 2

    normalized, diags = normalize_intent(draft_data, fill_missing=False)
    if diags:
        print("E_EDGEINTENT_DIFF_DRAFT_LINT", file=sys.stderr)
        return 2

    intents = normalized.get("edge_intents_proposed", [])
    if not intents:
        print("E_EDGEINTENT_DIFF_EMPTY", file=sys.stderr)
        return 2
    intent_ids = [intent.get("id") for intent in intents]
    if len(intent_ids) != len(set(intent_ids)):
        print("E_EDGEINTENT_DIFF_DUPLICATE_ID", file=sys.stderr)
        return 2

    base_lines = topo_path.read_text(encoding="utf-8").splitlines()
    existing = _extract_edgeintents(base_lines)
    new_lines = list(base_lines)

    # Replace existing blocks from bottom to top to avoid index shifts.
    replacements: list[tuple[int, int, dict[str, str]]] = []
    for intent in intents:
        intent_id = intent["id"]
        if intent_id in existing:
            start, end = existing[intent_id]
            replacements.append((start, end, intent))
    for start, end, intent in sorted(replacements, key=lambda item: item[0], reverse=True):
        block = _format_intent_lines(intent)
        new_lines[start : end + 1] = block

    new_blocks = [intent for intent in intents if intent["id"] not in existing]
    if new_blocks:
        insert_at = _find_insert_index(new_lines)
        block_lines: list[str] = []
        for intent in sorted(new_blocks, key=lambda i: i.get("id", "")):
            block_lines.extend(_format_intent_lines(intent))
        new_lines[insert_at:insert_at] = block_lines

    old_lines: list[str] = []
    if preview_path.exists():
        old_lines = preview_path.read_text(encoding="utf-8").splitlines()

    diff = difflib.unified_diff(
        old_lines,
        new_lines,
        fromfile=str(preview_path),
        tofile=str(preview_path),
        lineterm="",
    )
    output = "\n".join(diff)
    if output:
        print(output)
        return 0
    print("E_EDGEINTENT_DIFF_NO_CHANGE", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
