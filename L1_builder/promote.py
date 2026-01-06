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

from L1_builder.decisions_lint import parse_decisions_file
from sdslv2_builder.lint import _capture_metadata, _parse_metadata_pairs, _split_list_items
from sdslv2_builder.refs import parse_internal_ref

ANNOTATION_KIND_RE = re.compile(r"^\s*@(?P<kind>[A-Za-z_][A-Za-z0-9_]*)\b")


@dataclass(frozen=True)
class EdgeBlock:
    edge_id: str
    from_id: str
    to_id: str
    direction: str
    contract_refs: tuple[str, ...]
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
            raise ValueError(f"E_PROMOTE_METADATA_MISSING: line {idx + 1}")
        meta, end_line = _capture_metadata(lines, idx, brace_idx)
        pairs = _parse_metadata_pairs(meta)
        meta_map: dict[str, str] = {}
        for key, value in pairs:
            if key in meta_map:
                raise ValueError(f"E_PROMOTE_DUPLICATE_KEY: line {idx + 1} key {key}")
            meta_map[key] = value
        annotations.append((kind, meta_map, idx, end_line))
    return annotations


def _first_statement(lines: list[str]) -> int | None:
    for idx, line in enumerate(lines):
        if line.strip() == "" or line.lstrip().startswith("//"):
            continue
        return idx
    return None


def _find_file_header(lines: list[str]) -> tuple[int, int, dict[str, str]]:
    file_lines = [idx for idx, line in enumerate(lines) if line.lstrip().startswith("@File")]
    if not file_lines:
        raise ValueError("E_PROMOTE_FILE_HEADER_MISSING")
    if len(file_lines) > 1:
        raise ValueError("E_PROMOTE_FILE_HEADER_DUPLICATE")
    first = _first_statement(lines)
    if first is not None and file_lines[0] != first:
        raise ValueError("E_PROMOTE_FILE_HEADER_NOT_FIRST")
    idx = file_lines[0]
    brace_idx = lines[idx].find("{")
    if brace_idx == -1:
        raise ValueError("E_PROMOTE_FILE_HEADER_INVALID")
    meta, end_line = _capture_metadata(lines, idx, brace_idx)
    pairs = _parse_metadata_pairs(meta)
    meta_map: dict[str, str] = {}
    for key, value in pairs:
        meta_map[key] = value
    return idx, end_line, meta_map


def _strip_quotes(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] == '"':
        return value[1:-1]
    return value


def _parse_edges(
    annotations: list[tuple[str, dict[str, str], int, int]],
) -> list[EdgeBlock]:
    edges: list[EdgeBlock] = []
    for kind, meta, start, end in annotations:
        if kind != "Edge":
            continue
        edge_id = _strip_quotes(meta.get("id")) or ""
        raw_from = meta.get("from")
        raw_to = meta.get("to")
        direction = _strip_quotes(meta.get("direction")) or ""
        contract_raw = meta.get("contract_refs")
        if not raw_from or not raw_to:
            continue
        from_ref = parse_internal_ref(raw_from)
        to_ref = parse_internal_ref(raw_to)
        if not from_ref or not to_ref or from_ref.kind != "Node" or to_ref.kind != "Node":
            raise ValueError("E_PROMOTE_EDGE_FROM_TO_INVALID")
        contract_refs: list[str] = []
        if contract_raw:
            for item in _split_list_items(contract_raw):
                contract_refs.append(_strip_quotes(item) or "")
        contract_refs = sorted(dict.fromkeys([c for c in contract_refs if c]))
        edges.append(
            EdgeBlock(
                edge_id=edge_id,
                from_id=from_ref.rel_id,
                to_id=to_ref.rel_id,
                direction=direction,
                contract_refs=tuple(contract_refs),
                start=start,
                end=end,
            )
        )
    return edges


def _parse_nodes(
    annotations: list[tuple[str, dict[str, str], int, int]],
) -> set[str]:
    nodes: set[str] = set()
    for kind, meta, _, _ in annotations:
        if kind != "Node":
            continue
        rel_id = _strip_quotes(meta.get("id"))
        if rel_id:
            nodes.add(rel_id)
    return nodes


def _edge_tuple(edge: EdgeBlock) -> tuple[str, str, str, tuple[str, ...]]:
    return (edge.from_id, edge.to_id, edge.direction, edge.contract_refs)


def _format_contract_refs_lines(items: list[str]) -> list[str]:
    lines = ["  contract_refs:["]
    for item in items:
        lines.append(f'    "{item}",')
    lines.append("  ],")
    return lines


def _format_edge_lines(edge: dict[str, object]) -> list[str]:
    contract_refs = edge.get("contract_refs", [])
    items = list(contract_refs) if isinstance(contract_refs, list) else []
    lines = [
        "@Edge {",
        f'  id:"{edge["id"]}",',
        f"  from:@Node.{edge['from']},",
        f"  to:@Node.{edge['to']},",
        f'  direction:"{edge["direction"]}",',
    ]
    lines.extend(_format_contract_refs_lines(items))
    lines.append("}")
    return lines


def _update_file_stage(lines: list[str], start: int, end: int, stage_value: str) -> None:
    if start == end:
        line = lines[start]
        if "stage" in line:
            lines[start] = re.sub(r'stage\s*:\s*"[^"]*"', f'stage:"{stage_value}"', line)
            return
        if "}" in line:
            lines[start] = line.replace("}", f', stage:"{stage_value}" }}', 1)
        return

    stage_line = None
    for idx in range(start, end + 1):
        if "stage" in lines[idx]:
            stage_line = idx
            break
    if stage_line is not None:
        lines[stage_line] = re.sub(
            r'stage\s*:\s*"[^"]*"',
            f'stage:"{stage_value}"',
            lines[stage_line],
        )
        return
    for idx in range(end, start - 1, -1):
        if "}" in lines[idx]:
            indent = " " * (len(lines[idx]) - len(lines[idx].lstrip(" ")))
            lines.insert(idx, f'{indent}  stage:"{stage_value}",')
            return


def _edge_run_bounds(lines: list[str], edges: list[EdgeBlock]) -> tuple[int, int] | None:
    if not edges:
        return None
    starts = [e.start for e in edges]
    ends = [e.end for e in edges]
    run_start, run_end = min(starts), max(ends)
    return run_start, run_end


def _find_insert_index_after_nodes(lines: list[str]) -> int:
    last = -1
    idx = 0
    while idx < len(lines):
        stripped = lines[idx].lstrip()
        if stripped.startswith("@Node"):
            last = idx
            brace_idx = lines[idx].find("{")
            if brace_idx != -1:
                _, end_line = _capture_metadata(lines, idx, brace_idx)
                last = end_line
                idx = end_line + 1
                continue
        idx += 1
    return last + 1


def _find_target_file_by_scope(
    project_root: Path,
    scope: dict[str, str],
) -> Path:
    kind = scope.get("kind")
    value = scope.get("value")
    if not kind or not value:
        raise ValueError("E_PROMOTE_SCOPE_INVALID")
    if kind == "file":
        path = _resolve_path(project_root, value)
        _ensure_inside(project_root, path, "E_PROMOTE_SCOPE_OUTSIDE_PROJECT")
        if _has_symlink_parent(path, project_root):
            raise ValueError("E_PROMOTE_SCOPE_SYMLINK")
        if not path.exists():
            raise ValueError("E_PROMOTE_SCOPE_FILE_NOT_FOUND")
        return path

    candidates: list[Path] = []
    ssot_root = project_root / "sdsl2" / "topology"
    if _has_symlink_parent(ssot_root, project_root):
        raise ValueError("E_PROMOTE_SCOPE_SYMLINK")
    if ssot_root.is_symlink():
        raise ValueError("E_PROMOTE_SCOPE_SYMLINK")
    ssot_root_resolved = ssot_root.resolve()
    try:
        ssot_root_resolved.relative_to(project_root.resolve())
    except ValueError:
        raise ValueError("E_PROMOTE_SCOPE_SYMLINK")
    for path in sorted(ssot_root.rglob("*.sdsl2")):
        if not path.is_file() or path.is_symlink():
            continue
        try:
            resolved = path.resolve()
            resolved.relative_to(ssot_root_resolved)
        except ValueError:
            raise ValueError("E_PROMOTE_SCOPE_SYMLINK")
        for parent in path.parents:
            if parent == ssot_root:
                break
            if parent.is_symlink():
                raise ValueError("E_PROMOTE_SCOPE_SYMLINK")
        lines = path.read_text(encoding="utf-8").splitlines()
        annotations = _parse_annotations(lines)
        nodes = _parse_nodes(annotations)
        if kind == "component":
            if value in nodes:
                candidates.append(path)
        if kind == "id_prefix":
            file_idx, _, meta = _find_file_header(lines)
            file_idx = file_idx
            _ = file_idx
            id_prefix = _strip_quotes(meta.get("id_prefix")) or ""
            if id_prefix == value:
                candidates.append(path)
    if len(candidates) != 1:
        raise ValueError("E_PROMOTE_SCOPE_AMBIGUOUS")
    return candidates[0]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--decisions-path",
        default="decisions/edges.yaml",
        help="decisions/edges.yaml path",
    )
    ap.add_argument(
        "--project-root",
        default=None,
        help="Project root (defaults to repo root); inputs can be relative to it",
    )
    ap.add_argument(
        "--allow-nonstandard-path",
        action="store_true",
        help="Allow decisions file outside decisions/edges.yaml",
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
        _ensure_inside(project_root, decisions_path, "E_PROMOTE_INPUT_OUTSIDE_PROJECT")
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    if not decisions_path.exists():
        print("E_PROMOTE_DECISIONS_NOT_FOUND", file=sys.stderr)
        return 2
    if decisions_path.exists() and decisions_path.is_dir():
        print("E_PROMOTE_DECISIONS_IS_DIR", file=sys.stderr)
        return 2
    if decisions_path.is_symlink():
        print("E_PROMOTE_DECISIONS_SYMLINK", file=sys.stderr)
        return 2
    if not args.allow_nonstandard_path:
        expected = (project_root / "decisions" / "edges.yaml").resolve()
        if decisions_path.resolve() != expected:
            print("E_PROMOTE_DECISIONS_NOT_STANDARD_PATH", file=sys.stderr)
            return 2

    decisions, diags = parse_decisions_file(decisions_path, project_root)
    if diags:
        payload = [d.to_dict() for d in diags]
        print(json.dumps(payload, ensure_ascii=False, indent=2), file=sys.stderr)
        return 2

    scope = decisions.get("scope", {})
    try:
        target_path = _find_target_file_by_scope(project_root, scope)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    if target_path.is_symlink():
        print("E_PROMOTE_SCOPE_SYMLINK", file=sys.stderr)
        return 2

    lines = target_path.read_text(encoding="utf-8").splitlines()
    try:
        annotations = _parse_annotations(lines)
        for kind, _, _, _ in annotations:
            if kind in {"EdgeIntent", "Flow"}:
                print("E_PROMOTE_FORBIDDEN_KIND", file=sys.stderr)
                return 2

        file_start, file_end, file_meta = _find_file_header(lines)
        profile = _strip_quotes(file_meta.get("profile")) or ""
        stage = _strip_quotes(file_meta.get("stage")) or ""
        if profile != "topology":
            print("E_PROMOTE_PROFILE_INVALID", file=sys.stderr)
            return 2

        nodes = _parse_nodes(annotations)
        edges = _parse_edges(annotations)
        edge_run = _edge_run_bounds(lines, edges)
    except ValueError:
        print("E_PROMOTE_PARSE_ERROR", file=sys.stderr)
        return 2

    existing_ids = [e.edge_id for e in edges if e.edge_id]
    if existing_ids and existing_ids != sorted(existing_ids):
        print("E_PROMOTE_EDGE_ORDER_INVALID", file=sys.stderr)
        return 2

    existing_by_id = {e.edge_id: e for e in edges if e.edge_id}
    existing_by_tuple = {_edge_tuple(e): e for e in edges}

    new_edges: list[dict[str, object]] = []
    for edge in decisions.get("edges", []):
        if not isinstance(edge, dict):
            continue
        decision_id = edge.get("id")
        if not decision_id:
            continue
        if edge.get("from") not in nodes or edge.get("to") not in nodes:
            print("E_PROMOTE_NODE_NOT_FOUND", file=sys.stderr)
            return 2
        tup = (
            edge.get("from"),
            edge.get("to"),
            edge.get("direction"),
            tuple(edge.get("contract_refs", [])),
        )
        if tup in existing_by_tuple:
            continue
        if decision_id in existing_by_id:
            existing = existing_by_id[decision_id]
            if _edge_tuple(existing) != tup:
                print("E_PROMOTE_EDGE_CONFLICT", file=sys.stderr)
                return 2
            continue
        new_edges.append(edge)

    if not new_edges:
        print("E_PROMOTE_NO_CHANGE", file=sys.stderr)
        return 2

    new_lines = list(lines)
    if stage == "L0":
        _update_file_stage(new_lines, file_start, file_end, "L1")

    new_edges_sorted = sorted(new_edges, key=lambda e: str(e.get("id", "")))
    if edges:
        edge_blocks = sorted(edges, key=lambda e: e.start)
        existing_ids = [e.edge_id for e in edge_blocks]
        for edge in new_edges_sorted:
            edge_id = edge.get("id", "")
            idx = 0
            while idx < len(existing_ids) and existing_ids[idx] < edge_id:
                idx += 1
            if idx == 0:
                insert_at = edge_blocks[0].start
            else:
                insert_at = edge_blocks[idx - 1].end + 1
            block = _format_edge_lines(edge)
            new_lines[insert_at:insert_at] = block
            for j in range(idx, len(edge_blocks)):
                edge_blocks[j] = EdgeBlock(
                    edge_id=edge_blocks[j].edge_id,
                    from_id=edge_blocks[j].from_id,
                    to_id=edge_blocks[j].to_id,
                    direction=edge_blocks[j].direction,
                    contract_refs=edge_blocks[j].contract_refs,
                    start=edge_blocks[j].start + len(block),
                    end=edge_blocks[j].end + len(block),
                )
            edge_blocks.insert(
                idx,
                EdgeBlock(
                    edge_id=edge_id,
                    from_id=edge.get("from", ""),
                    to_id=edge.get("to", ""),
                    direction=edge.get("direction", ""),
                    contract_refs=tuple(edge.get("contract_refs", [])),
                    start=insert_at,
                    end=insert_at + len(block) - 1,
                ),
            )
            existing_ids.insert(idx, edge_id)
    else:
        insert_at = _find_insert_index_after_nodes(new_lines)
        block_lines: list[str] = []
        for edge in new_edges_sorted:
            block_lines.extend(_format_edge_lines(edge))
        new_lines[insert_at:insert_at] = block_lines

    diff = difflib.unified_diff(
        lines,
        new_lines,
        fromfile=str(target_path),
        tofile=str(target_path),
        lineterm="",
    )
    output = "\n".join(diff)
    if not output:
        print("E_PROMOTE_NO_CHANGE", file=sys.stderr)
        return 2

    if args.out:
        out_path = _resolve_path(project_root, args.out)
        try:
            _ensure_inside(project_root, out_path, "E_PROMOTE_OUTPUT_OUTSIDE_PROJECT")
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 2
        allowed_root = project_root / "OUTPUT"
        try:
            out_path.resolve().relative_to(allowed_root.resolve())
        except ValueError:
            print("E_PROMOTE_OUTPUT_OUTSIDE_OUTPUT", file=sys.stderr)
            return 2
        if out_path.exists() and out_path.is_dir():
            print("E_PROMOTE_OUTPUT_IS_DIR", file=sys.stderr)
            return 2
        if out_path.exists() and out_path.is_symlink():
            print("E_PROMOTE_OUTPUT_SYMLINK", file=sys.stderr)
            return 2
        if _has_symlink_parent(out_path, project_root):
            print("E_PROMOTE_OUTPUT_SYMLINK", file=sys.stderr)
            return 2
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(output + "\n", encoding="utf-8")
        return 0

    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
