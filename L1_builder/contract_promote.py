#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import difflib
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from L1_builder.contract_decisions_lint import parse_contract_decisions_file
from sdslv2_builder.contract import Decl, Rule
from sdslv2_builder.contract_writer import _format_decl, _format_rule
from sdslv2_builder.lint import _capture_metadata, _parse_metadata_pairs
from sdslv2_builder.refs import parse_contract_ref, parse_internal_ref, parse_ssot_ref

ANNOTATION_KIND_RE = re.compile(r"^\s*@(?P<kind>[A-Za-z_][A-Za-z0-9_]*)\b")
DECL_KINDS = {"Structure", "Interface", "Function", "Const", "Type"}


@dataclass(frozen=True)
class Block:
    kind: str
    rel_id: str
    start: int
    end: int


def _resolve_path(project_root: Path, raw: str) -> Path:
    path = Path(raw)
    if not path.is_absolute():
        path = (project_root / path).resolve()
    return path


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


def _first_statement(lines: list[str]) -> int | None:
    for idx, line in enumerate(lines):
        if line.strip() == "" or line.lstrip().startswith("//"):
            continue
        return idx
    return None


def _file_header(lines: list[str]) -> tuple[int, int, dict[str, str]]:
    file_lines = [idx for idx, line in enumerate(lines) if line.lstrip().startswith("@File")]
    if not file_lines:
        raise ValueError("E_CONTRACT_PROMOTE_FILE_HEADER_MISSING")
    if len(file_lines) > 1:
        raise ValueError("E_CONTRACT_PROMOTE_FILE_HEADER_DUPLICATE")
    first = _first_statement(lines)
    if first is not None and file_lines[0] != first:
        raise ValueError("E_CONTRACT_PROMOTE_FILE_HEADER_NOT_FIRST")
    idx = file_lines[0]
    brace_idx = lines[idx].find("{")
    if brace_idx == -1:
        raise ValueError("E_CONTRACT_PROMOTE_FILE_HEADER_INVALID")
    meta, end_line = _capture_metadata(lines, idx, brace_idx)
    pairs = _parse_metadata_pairs(meta)
    meta_map: dict[str, str] = {}
    for key, value in pairs:
        if key in meta_map:
            raise ValueError("E_CONTRACT_PROMOTE_DUPLICATE_KEY")
        meta_map[key] = value
    return idx, end_line, meta_map


def _strip_quotes(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] == '"':
        return value[1:-1]
    return value


def _parse_annotations(lines: list[str]) -> list[tuple[str, dict[str, str], int, int]]:
    annotations: list[tuple[str, dict[str, str], int, int]] = []
    for idx, line in enumerate(lines):
        stripped = line.lstrip()
        if stripped == "" or stripped.startswith("//"):
            continue
        if not stripped.startswith("@"):
            continue
        match = ANNOTATION_KIND_RE.match(stripped)
        if not match:
            continue
        kind = match.group("kind")
        brace_idx = line.find("{")
        if brace_idx == -1:
            raise ValueError(f"E_CONTRACT_PROMOTE_METADATA_MISSING: line {idx + 1}")
        meta, end_line = _capture_metadata(lines, idx, brace_idx)
        pairs = _parse_metadata_pairs(meta)
        meta_map: dict[str, str] = {}
        for key, value in pairs:
            if key in meta_map:
                raise ValueError(f"E_CONTRACT_PROMOTE_DUPLICATE_KEY: line {idx + 1} key {key}")
            meta_map[key] = value
        annotations.append((kind, meta_map, idx, end_line))
    return annotations


def _find_decl_end(lines: list[str], start: int) -> int:
    idx = start + 1
    while idx < len(lines):
        stripped = lines[idx].lstrip()
        if stripped.startswith("@"):
            return idx - 1
        idx += 1
    return len(lines) - 1


def _collect_blocks(lines: list[str]) -> list[Block]:
    annotations = _parse_annotations(lines)
    blocks: list[Block] = []
    for kind, meta, start, end_meta in annotations:
        rel_id = _strip_quotes(meta.get("id")) or ""
        if kind in DECL_KINDS:
            end = _find_decl_end(lines, end_meta)
            blocks.append(Block(kind=kind, rel_id=rel_id, start=start, end=end))
        else:
            blocks.append(Block(kind=kind, rel_id=rel_id, start=start, end=end_meta))
    return blocks


def _find_target_contract_file(project_root: Path, scope: dict[str, str]) -> Path:
    kind = scope.get("kind")
    value = scope.get("value")
    if not kind or not value:
        raise ValueError("E_CONTRACT_PROMOTE_SCOPE_INVALID")
    if kind == "file":
        path = _resolve_path(project_root, value)
        _ensure_inside(project_root, path, "E_CONTRACT_PROMOTE_SCOPE_OUTSIDE_PROJECT")
        if _has_symlink_parent(path, project_root) or path.is_symlink():
            raise ValueError("E_CONTRACT_PROMOTE_SCOPE_SYMLINK")
        if not path.exists():
            raise ValueError("E_CONTRACT_PROMOTE_SCOPE_FILE_NOT_FOUND")
        return path
    if kind != "id_prefix":
        raise ValueError("E_CONTRACT_PROMOTE_SCOPE_INVALID")

    ssot_root = (project_root / "sdsl2" / "contract").resolve()
    if _has_symlink_parent(ssot_root, project_root) or ssot_root.is_symlink():
        raise ValueError("E_CONTRACT_PROMOTE_SCOPE_SYMLINK")
    try:
        ssot_root.relative_to(project_root.resolve())
    except ValueError:
        raise ValueError("E_CONTRACT_PROMOTE_SCOPE_SYMLINK")
    if not ssot_root.exists():
        raise ValueError("E_CONTRACT_PROMOTE_SCOPE_FILE_NOT_FOUND")

    candidates: list[Path] = []
    for path in sorted(ssot_root.rglob("*.sdsl2")):
        if not path.is_file() or path.is_symlink():
            continue
        if _has_symlink_parent(path, ssot_root):
            raise ValueError("E_CONTRACT_PROMOTE_SCOPE_SYMLINK")
        lines = path.read_text(encoding="utf-8").splitlines()
        _, _, meta = _file_header(lines)
        profile = _strip_quotes(meta.get("profile")) or ""
        id_prefix = _strip_quotes(meta.get("id_prefix")) or ""
        if profile != "contract":
            continue
        if id_prefix == value:
            candidates.append(path)
    if len(candidates) != 1:
        raise ValueError("E_CONTRACT_PROMOTE_SCOPE_AMBIGUOUS")
    return candidates[0]


def _build_structure_lines(item: dict[str, object]) -> list[str]:
    rel_id = str(item.get("id", ""))
    decl = str(item.get("decl", ""))
    decl_obj = Decl(
        kind="Structure",
        rel_id=rel_id,
        decl=decl,
        bind=None,
        title=None,
        desc=None,
        refs=[],
        contract=[],
        ssot=[],
    )
    return _format_decl(decl_obj)


def _build_rule_lines(item: dict[str, object]) -> list[str]:
    rel_id = str(item.get("id", ""))
    bind_raw = str(item.get("bind", ""))
    bind = parse_internal_ref(bind_raw)
    if not bind:
        raise ValueError("E_CONTRACT_PROMOTE_RULE_BIND_INVALID")
    refs_raw = item.get("refs", [])
    refs = [parse_internal_ref(r) for r in refs_raw] if isinstance(refs_raw, list) else []
    refs = [r for r in refs if r is not None]
    contract_raw = item.get("contract", [])
    contract = [parse_contract_ref(c) for c in contract_raw] if isinstance(contract_raw, list) else []
    contract = [c for c in contract if c is not None]
    ssot_raw = item.get("ssot", [])
    ssot = [parse_ssot_ref(s) for s in ssot_raw] if isinstance(ssot_raw, list) else []
    ssot = [s for s in ssot if s is not None]
    rule_obj = Rule(
        rel_id=rel_id,
        bind=bind,
        refs=refs,
        contract=contract,
        ssot=ssot,
    )
    return _format_rule(rule_obj)


def _insert_blocks_in_order(
    new_lines: list[str],
    blocks: list[Block],
    new_items: list[dict[str, object]],
    build_lines,
    block_kind: str,
    insert_at_default: int,
) -> None:
    block_items = [b for b in blocks if b.kind == block_kind]
    if block_items:
        block_items = sorted(block_items, key=lambda b: b.start)
        existing_ids = [b.rel_id for b in block_items]
        if existing_ids != sorted(existing_ids):
            raise ValueError(f"E_CONTRACT_PROMOTE_{block_kind.upper()}_ORDER_INVALID")
        for item in new_items:
            rel_id = str(item.get("id", ""))
            idx = 0
            while idx < len(existing_ids) and existing_ids[idx] < rel_id:
                idx += 1
            insert_at = block_items[idx - 1].end + 1 if idx > 0 else block_items[0].start
            block_lines = build_lines(item)
            new_lines[insert_at:insert_at] = block_lines
            for j in range(idx, len(block_items)):
                block_items[j] = Block(
                    kind=block_items[j].kind,
                    rel_id=block_items[j].rel_id,
                    start=block_items[j].start + len(block_lines),
                    end=block_items[j].end + len(block_lines),
                )
            block_items.insert(
                idx,
                Block(
                    kind=block_kind,
                    rel_id=rel_id,
                    start=insert_at,
                    end=insert_at + len(block_lines) - 1,
                ),
            )
            existing_ids.insert(idx, rel_id)
        return

    insert_at = insert_at_default
    block_lines: list[str] = []
    for item in sorted(new_items, key=lambda i: str(i.get("id", ""))):
        block_lines.extend(build_lines(item))
    new_lines[insert_at:insert_at] = block_lines


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--decisions-path",
        default="decisions/contracts.yaml",
        help="decisions/contracts.yaml path",
    )
    ap.add_argument(
        "--allow-nonstandard-path",
        action="store_true",
        help="Allow decisions file outside decisions/contracts.yaml",
    )
    ap.add_argument(
        "--project-root",
        default=None,
        help="Project root (defaults to repo root); inputs can be relative to it",
    )
    ap.add_argument(
        "--out",
        default=None,
        help="Optional diff output under OUTPUT/ (default: stdout)",
    )
    args = ap.parse_args()

    project_root = Path(args.project_root).resolve() if args.project_root else ROOT
    decisions_path = _resolve_path(project_root, args.decisions_path)
    try:
        _ensure_inside(project_root, decisions_path, "E_CONTRACT_PROMOTE_INPUT_OUTSIDE_PROJECT")
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    if not decisions_path.exists():
        print("E_CONTRACT_PROMOTE_DECISIONS_NOT_FOUND", file=sys.stderr)
        return 2
    if decisions_path.is_dir():
        print("E_CONTRACT_PROMOTE_DECISIONS_IS_DIR", file=sys.stderr)
        return 2
    if decisions_path.is_symlink():
        print("E_CONTRACT_PROMOTE_DECISIONS_SYMLINK", file=sys.stderr)
        return 2
    if not args.allow_nonstandard_path:
        expected = (project_root / "decisions" / "contracts.yaml").resolve()
        if decisions_path.resolve() != expected:
            print("E_CONTRACT_PROMOTE_DECISIONS_NOT_STANDARD_PATH", file=sys.stderr)
            return 2

    decisions, diags = parse_contract_decisions_file(decisions_path, project_root)
    if diags:
        payload = [d.to_dict() for d in diags]
        print(json.dumps(payload, ensure_ascii=False, indent=2), file=sys.stderr)
        return 2
    scope = decisions.get("scope", {})
    try:
        target_path = _find_target_contract_file(project_root, scope)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    if target_path.is_symlink():
        print("E_CONTRACT_PROMOTE_SCOPE_SYMLINK", file=sys.stderr)
        return 2

    lines = target_path.read_text(encoding="utf-8").splitlines()
    try:
        file_start, file_end, file_meta = _file_header(lines)
        profile = _strip_quotes(file_meta.get("profile")) or ""
        if profile != "contract":
            print("E_CONTRACT_PROMOTE_PROFILE_INVALID", file=sys.stderr)
            return 2
        blocks = _collect_blocks(lines)
    except ValueError:
        print("E_CONTRACT_PROMOTE_PARSE_ERROR", file=sys.stderr)
        return 2

    docmeta_blocks = [b for b in blocks if b.kind == "DocMeta"]
    docmeta_end = docmeta_blocks[0].end if docmeta_blocks else file_end

    decl_blocks = [b for b in blocks if b.kind in DECL_KINDS]
    structure_blocks = [b for b in blocks if b.kind == "Structure"]
    dep_blocks = [b for b in blocks if b.kind == "Dep"]
    rule_blocks = [b for b in blocks if b.kind == "Rule"]

    existing_struct_ids = {b.rel_id for b in structure_blocks if b.rel_id}
    existing_rule_ids = {b.rel_id for b in rule_blocks if b.rel_id}

    new_structures = []
    for item in decisions.get("structures", []):
        if not isinstance(item, dict):
            continue
        rel_id = str(item.get("id", ""))
        if rel_id in existing_struct_ids:
            print("E_CONTRACT_PROMOTE_STRUCTURE_EXISTS", file=sys.stderr)
            return 2
        new_structures.append(item)

    new_rules = []
    for item in decisions.get("rules", []):
        if not isinstance(item, dict):
            continue
        rel_id = str(item.get("id", ""))
        if rel_id in existing_rule_ids:
            print("E_CONTRACT_PROMOTE_RULE_EXISTS", file=sys.stderr)
            return 2
        new_rules.append(item)

    if not new_structures and not new_rules:
        print("E_CONTRACT_PROMOTE_NO_CHANGE", file=sys.stderr)
        return 2

    new_lines = list(lines)

    if decl_blocks:
        first_non_structure = min(
            (b.start for b in decl_blocks if b.kind != "Structure"),
            default=None,
        )
        insert_struct_at = first_non_structure if first_non_structure is not None else decl_blocks[-1].end + 1
    else:
        insert_struct_at = docmeta_end + 1
    _insert_blocks_in_order(
        new_lines,
        blocks,
        sorted(new_structures, key=lambda i: str(i.get("id", ""))),
        _build_structure_lines,
        "Structure",
        insert_struct_at,
    )

    if rule_blocks:
        insert_rule_at = rule_blocks[-1].end + 1
    elif dep_blocks:
        insert_rule_at = dep_blocks[-1].end + 1
    elif decl_blocks:
        insert_rule_at = decl_blocks[-1].end + 1
    else:
        insert_rule_at = docmeta_end + 1

    updated_blocks = _collect_blocks(new_lines)
    _insert_blocks_in_order(
        new_lines,
        updated_blocks,
        sorted(new_rules, key=lambda i: str(i.get("id", ""))),
        _build_rule_lines,
        "Rule",
        insert_rule_at,
    )

    diff = difflib.unified_diff(
        lines,
        new_lines,
        fromfile=str(target_path),
        tofile=str(target_path),
        lineterm="",
    )
    output = "\n".join(diff)
    if not output:
        print("E_CONTRACT_PROMOTE_NO_CHANGE", file=sys.stderr)
        return 2

    if args.out:
        out_path = _resolve_path(project_root, args.out)
        try:
            _ensure_inside(project_root, out_path, "E_CONTRACT_PROMOTE_OUTPUT_OUTSIDE_PROJECT")
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 2
        allowed_root = project_root / "OUTPUT"
        try:
            out_path.resolve().relative_to(allowed_root.resolve())
        except ValueError:
            print("E_CONTRACT_PROMOTE_OUTPUT_OUTSIDE_OUTPUT", file=sys.stderr)
            return 2
        if out_path.exists() and out_path.is_dir():
            print("E_CONTRACT_PROMOTE_OUTPUT_IS_DIR", file=sys.stderr)
            return 2
        if out_path.exists() and out_path.is_symlink():
            print("E_CONTRACT_PROMOTE_OUTPUT_SYMLINK", file=sys.stderr)
            return 2
        if _has_symlink_parent(out_path, project_root):
            print("E_CONTRACT_PROMOTE_OUTPUT_SYMLINK", file=sys.stderr)
            return 2
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(output + "\n", encoding="utf-8")
        return 0

    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
