#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from L1_builder.decisions_lint import parse_decisions_file
from sdslv2_builder.errors import Diagnostic, json_pointer
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


def _diag(diags: list[Diagnostic], code: str, message: str, expected: str, got: str, path: str) -> None:
    diags.append(Diagnostic(code=code, message=message, expected=expected, got=got, path=path))


def _print_diags(diags: list[Diagnostic]) -> None:
    payload = [d.to_dict() for d in diags]
    print(json.dumps(payload, ensure_ascii=False, indent=2), file=sys.stderr)


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
            raise ValueError(f"E_DRIFT_METADATA_MISSING: line {idx + 1}")
        meta, end_line = _capture_metadata(lines, idx, brace_idx)
        pairs = _parse_metadata_pairs(meta)
        meta_map: dict[str, str] = {}
        for key, value in pairs:
            if key in meta_map:
                raise ValueError(f"E_DRIFT_DUPLICATE_KEY: line {idx + 1} key {key}")
            meta_map[key] = value
        annotations.append((kind, meta_map, idx, end_line))
    return annotations


def _first_statement(lines: list[str]) -> int | None:
    for idx, line in enumerate(lines):
        if line.strip() == "" or line.lstrip().startswith("//"):
            continue
        return idx
    return None


def _find_file_header(lines: list[str]) -> dict[str, str]:
    file_lines = [idx for idx, line in enumerate(lines) if line.lstrip().startswith("@File")]
    if not file_lines:
        raise ValueError("E_DRIFT_FILE_HEADER_MISSING")
    if len(file_lines) > 1:
        raise ValueError("E_DRIFT_FILE_HEADER_DUPLICATE")
    first = _first_statement(lines)
    if first is not None and file_lines[0] != first:
        raise ValueError("E_DRIFT_FILE_HEADER_NOT_FIRST")
    idx = file_lines[0]
    brace_idx = lines[idx].find("{")
    if brace_idx == -1:
        raise ValueError("E_DRIFT_FILE_HEADER_INVALID")
    meta, _ = _capture_metadata(lines, idx, brace_idx)
    pairs = _parse_metadata_pairs(meta)
    meta_map: dict[str, str] = {}
    for key, value in pairs:
        if key in meta_map:
            raise ValueError(f"E_DRIFT_DUPLICATE_KEY: line {idx + 1} key {key}")
        meta_map[key] = value
    return meta_map


def _strip_quotes(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] == '"':
        return value[1:-1]
    return value


def _parse_edges(annotations: list[tuple[str, dict[str, str], int, int]]) -> list[EdgeBlock]:
    edges: list[EdgeBlock] = []
    for kind, meta, _, _ in annotations:
        if kind != "Edge":
            continue
        edge_id = _strip_quotes(meta.get("id")) or ""
        raw_from = meta.get("from")
        raw_to = meta.get("to")
        direction = _strip_quotes(meta.get("direction")) or ""
        contract_raw = meta.get("contract_refs")
        if not edge_id or not raw_from or not raw_to:
            continue
        from_ref = parse_internal_ref(raw_from)
        to_ref = parse_internal_ref(raw_to)
        if not from_ref or not to_ref or from_ref.kind != "Node" or to_ref.kind != "Node":
            continue
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
            )
        )
    return edges


def _missing_contract_refs(annotations: list[tuple[str, dict[str, str], int, int]]) -> list[tuple[int, str | None]]:
    missing: list[tuple[int, str | None]] = []
    for kind, meta, idx, _ in annotations:
        if kind != "Edge":
            continue
        if meta is None:
            missing.append((idx, None))
            continue
        raw = meta.get("contract_refs")
        if raw is None:
            missing.append((idx, _strip_quotes(meta.get("id"))))
            continue
        items = _split_list_items(raw)
        if not items:
            missing.append((idx, _strip_quotes(meta.get("id"))))
    return missing


def _edge_tuple(edge_id: str, from_id: str, to_id: str, direction: str, contract_refs: list[str]) -> tuple[str, str, str, str, tuple[str, ...]]:
    return (edge_id, from_id, to_id, direction, tuple(contract_refs))


def _find_target_file_by_scope(project_root: Path, scope: dict[str, str]) -> Path:
    kind = scope.get("kind")
    value = scope.get("value")
    if not kind or not value:
        raise ValueError("E_DRIFT_SCOPE_INVALID")
    if kind == "file":
        path = _resolve_path(project_root, value)
        _ensure_inside(project_root, path, "E_DRIFT_SCOPE_OUTSIDE_PROJECT")
        if _has_symlink_parent(path, project_root):
            raise ValueError("E_DRIFT_SCOPE_SYMLINK")
        if not path.exists():
            raise ValueError("E_DRIFT_SCOPE_FILE_NOT_FOUND")
        return path

    candidates: list[Path] = []
    ssot_root = project_root / "sdsl2" / "topology"
    if _has_symlink_parent(ssot_root, project_root):
        raise ValueError("E_DRIFT_SCOPE_SYMLINK")
    if ssot_root.is_symlink():
        raise ValueError("E_DRIFT_SCOPE_SYMLINK")
    ssot_root_resolved = ssot_root.resolve()
    try:
        ssot_root_resolved.relative_to(project_root.resolve())
    except ValueError as exc:
        raise ValueError("E_DRIFT_SCOPE_SYMLINK") from exc

    for path in sorted(ssot_root.rglob("*.sdsl2")):
        if not path.is_file() or path.is_symlink():
            continue
        try:
            resolved = path.resolve()
            resolved.relative_to(ssot_root_resolved)
        except ValueError:
            raise ValueError("E_DRIFT_SCOPE_SYMLINK")
        for parent in path.parents:
            if parent == ssot_root:
                break
            if parent.is_symlink():
                raise ValueError("E_DRIFT_SCOPE_SYMLINK")
        lines = path.read_text(encoding="utf-8").splitlines()
        annotations = _parse_annotations(lines)
        nodes = {(_strip_quotes(meta.get("id")) or "") for kind, meta, _, _ in annotations if kind == "Node"}
        if kind == "component":
            if value in nodes:
                candidates.append(path)
        if kind == "id_prefix":
            meta = _find_file_header(lines)
            id_prefix = _strip_quotes(meta.get("id_prefix")) or ""
            if id_prefix == value:
                candidates.append(path)
    if len(candidates) != 1:
        raise ValueError("E_DRIFT_SCOPE_AMBIGUOUS")
    return candidates[0]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--decisions-path",
        default="decisions/edges.yaml",
        help="decisions/edges.yaml path",
    )
    ap.add_argument(
        "--allow-nonstandard-path",
        action="store_true",
        help="Allow decisions file outside decisions/edges.yaml",
    )
    ap.add_argument(
        "--project-root",
        default=None,
        help="Project root (defaults to repo root); inputs can be relative to it",
    )
    args = ap.parse_args()

    project_root = Path(args.project_root).resolve() if args.project_root else ROOT
    decisions_path = _resolve_path(project_root, args.decisions_path)
    try:
        _ensure_inside(project_root, decisions_path, "E_DRIFT_INPUT_OUTSIDE_PROJECT")
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    if not decisions_path.exists():
        print("E_DRIFT_DECISIONS_NOT_FOUND", file=sys.stderr)
        return 2
    if decisions_path.is_dir():
        print("E_DRIFT_DECISIONS_IS_DIR", file=sys.stderr)
        return 2
    if decisions_path.is_symlink():
        print("E_DRIFT_DECISIONS_SYMLINK", file=sys.stderr)
        return 2
    if not args.allow_nonstandard_path:
        expected = (project_root / "decisions" / "edges.yaml").resolve()
        if decisions_path.resolve() != expected:
            print("E_DRIFT_DECISIONS_NOT_STANDARD_PATH", file=sys.stderr)
            return 2

    decisions, diags = parse_decisions_file(decisions_path, project_root)
    if diags:
        _print_diags(diags)
        return 2
    scope = decisions.get("scope", {}) if isinstance(decisions, dict) else {}
    try:
        target_path = _find_target_file_by_scope(project_root, scope)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    if _has_symlink_parent(target_path, project_root) or target_path.is_symlink():
        print("E_DRIFT_SCOPE_SYMLINK", file=sys.stderr)
        return 2

    lines = target_path.read_text(encoding="utf-8").splitlines()
    try:
        file_meta = _find_file_header(lines)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    profile = _strip_quotes(file_meta.get("profile"))
    if profile != "topology":
        print("E_DRIFT_PROFILE_INVALID", file=sys.stderr)
        return 2

    try:
        annotations = _parse_annotations(lines)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    missing_refs = _missing_contract_refs(annotations)
    if missing_refs:
        for idx, edge_id in missing_refs:
            if edge_id:
                print(f"E_DRIFT_CONTRACT_REFS_MISSING: line {idx + 1} id {edge_id}", file=sys.stderr)
            else:
                print(f"E_DRIFT_CONTRACT_REFS_MISSING: line {idx + 1}", file=sys.stderr)
        return 2
    edges = _parse_edges(annotations)

    topo_by_id = {edge.edge_id: edge for edge in edges}
    topo_tuples = {
        _edge_tuple(edge.edge_id, edge.from_id, edge.to_id, edge.direction, list(edge.contract_refs))
        for edge in edges
    }

    decision_edges = decisions.get("edges", []) if isinstance(decisions, dict) else []
    decision_tuples = set()
    decision_by_id = {}
    for edge in decision_edges:
        if not isinstance(edge, dict):
            continue
        edge_id = edge.get("id")
        from_id = edge.get("from")
        to_id = edge.get("to")
        direction = edge.get("direction")
        contract_refs = edge.get("contract_refs", [])
        if not all(isinstance(x, str) for x in [edge_id, from_id, to_id, direction]):
            continue
        if not isinstance(contract_refs, list):
            contract_refs = []
        refs = [ref for ref in contract_refs if isinstance(ref, str)]
        tup = _edge_tuple(edge_id, from_id, to_id, direction, refs)
        decision_tuples.add(tup)
        decision_by_id[edge_id] = tup

    drift_diags: list[Diagnostic] = []
    for edge_id, tup in decision_by_id.items():
        topo_edge = topo_by_id.get(edge_id)
        if topo_edge is None:
            _diag(
                drift_diags,
                "E_DRIFT_DECISION_NOT_REFLECTED",
                "Decision not reflected in SSOT",
                "matching @Edge in topology",
                edge_id,
                json_pointer("edges", edge_id),
            )
            continue
        topo_tup = _edge_tuple(
            topo_edge.edge_id,
            topo_edge.from_id,
            topo_edge.to_id,
            topo_edge.direction,
            list(topo_edge.contract_refs),
        )
        if topo_tup != tup:
            _diag(
                drift_diags,
                "E_DRIFT_EDGE_CONFLICT",
                "Decision edge conflicts with SSOT edge",
                str(tup),
                str(topo_tup),
                json_pointer("edges", edge_id),
            )

    for edge in edges:
        tup = _edge_tuple(edge.edge_id, edge.from_id, edge.to_id, edge.direction, list(edge.contract_refs))
        if tup not in decision_tuples:
            _diag(
                drift_diags,
                "E_DRIFT_MANUAL_EDGE",
                "SSOT edge missing from decisions",
                "matching EdgeDecision",
                edge.edge_id,
                json_pointer("ssot_edges", edge.edge_id),
            )

    if drift_diags:
        _print_diags(drift_diags)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
