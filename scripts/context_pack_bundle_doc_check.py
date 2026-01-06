#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import sys
from pathlib import Path


SECTION_ORDER = [
    "Header:",
    "Nodes:",
    "Edges:",
    "Contracts:",
    "Authz:",
    "Invariants:",
    "Open TODO",
]

SUPPLEMENTARY_ORDER = [
    "decisions_needed",
    "provenance",
    "diagnostics_summary",
    "links",
    "decision_log",
]
OPEN_TODO_KEYS = [
    "edge_intents",
    "missing_contract_defs",
    "missing_invariants",
    "missing_authz",
]
OPEN_TODO_MARKERS = {"None", "TBD", "Opaque"}


def _fail(message: str) -> int:
    print(message, file=sys.stderr)
    return 2


def _strip_quotes(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] == '"':
        return value[1:-1]
    if len(value) >= 2 and value[0] == value[-1] == "'":
        return value[1:-1]
    return value


def _strip_quoted(text: str) -> str:
    out: list[str] = []
    escaped = False
    in_string: str | None = None
    for ch in text:
        if escaped:
            escaped = False
            if in_string is None:
                out.append(ch)
            continue
        if ch == "\\":
            escaped = True
            if in_string is None:
                out.append(ch)
            continue
        if ch in {'"', "'"}:
            if in_string is None:
                in_string = ch
            elif in_string == ch:
                in_string = None
            continue
        if in_string is None:
            out.append(ch)
    return "".join(out)


def _has_flow_style_marker(line: str) -> bool:
    sanitized = _strip_quoted(line)
    stripped = sanitized.lstrip()
    if stripped.startswith("{") or stripped.startswith("["):
        return True
    if stripped.startswith("- "):
        rest = stripped[2:].lstrip()
        if rest.startswith("{") or rest.startswith("["):
            return True
    if ":" in stripped:
        _, rest = stripped.split(":", 1)
        rest = rest.lstrip()
        if rest.startswith("{") or rest.startswith("["):
            return True
    return False


def _parse_supplementary_blocks(lines: list[str]) -> list[tuple[str, list[str]]]:
    blocks: list[tuple[str, list[str]]] = []
    seen_keys: set[str] = set()
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
        if key in seen_keys:
            raise ValueError(f"E_BUNDLE_DOC_SUPPLEMENTARY_DUPLICATE:{key}")
        seen_keys.add(key)
        start = idx
        idx += 2
        while idx < len(lines) and lines[idx].strip() != "---":
            idx += 1
        block = lines[start:idx]
        blocks.append((key, block))
    return blocks


def _find_section_indexes(lines: list[str]) -> dict[str, int]:
    indexes: dict[str, int] = {}
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if stripped == "Open TODO:" or stripped.startswith("Open TODO:"):
            if "Open TODO" in indexes:
                raise ValueError("E_CONTEXT_PACK_SECTION_DUPLICATE: Open TODO")
            indexes["Open TODO"] = idx
            continue
        if stripped in SECTION_ORDER:
            if stripped in indexes:
                raise ValueError(f"E_CONTEXT_PACK_SECTION_DUPLICATE:{stripped}")
            indexes[stripped] = idx
    for key in SECTION_ORDER:
        if key == "Open TODO":
            if key not in indexes:
                raise ValueError("E_CONTEXT_PACK_SECTION_MISSING: Open TODO")
        elif key not in indexes:
            raise ValueError(f"E_CONTEXT_PACK_SECTION_MISSING:{key}")
    return indexes


def _section_slice(lines: list[str], start: int, end: int | None) -> list[str]:
    if end is None:
        return lines[start:]
    return lines[start:end]


def _parse_nodes(lines: list[str]) -> list[tuple[str, str]]:
    if not lines:
        return []
    if len(lines) == 1 and lines[0].strip() == "[]":
        return []
    nodes: list[tuple[str, str]] = []
    idx = 0
    while idx < len(lines):
        if lines[idx].strip() == "":
            idx += 1
            continue
        line = lines[idx].strip()
        if not line.startswith("- rel_id:"):
            raise ValueError("E_CONTEXT_PACK_NODES_INVALID")
        rel_id = line.split(":", 1)[1].strip()
        idx += 1
        if idx >= len(lines):
            raise ValueError("E_CONTEXT_PACK_NODES_CANON_ID_MISSING")
        while idx < len(lines) and lines[idx].strip() == "":
            idx += 1
        if idx >= len(lines):
            raise ValueError("E_CONTEXT_PACK_NODES_CANON_ID_MISSING")
        canon_line = lines[idx].strip()
        if not canon_line.startswith("canon_id:"):
            raise ValueError("E_CONTEXT_PACK_NODES_CANON_ID_INVALID")
        canon_id = canon_line.split(":", 1)[1].strip()
        nodes.append((rel_id, canon_id))
        idx += 1
    return nodes


def _parse_edges(lines: list[str]) -> list[dict[str, object]]:
    if not lines:
        return []
    if len(lines) == 1 and lines[0].strip() == "[]":
        return []
    edges: list[dict[str, object]] = []
    idx = 0
    while idx < len(lines):
        if lines[idx].strip() == "":
            idx += 1
            continue
        line = lines[idx].strip()
        if not line.startswith("- from:"):
            raise ValueError("E_CONTEXT_PACK_EDGES_INVALID")
        from_id = line.split("@Node.", 1)[1].strip()
        idx += 1
        if idx >= len(lines):
            raise ValueError("E_CONTEXT_PACK_EDGES_INVALID")
        to_line = lines[idx].strip()
        if not to_line.startswith("to: @Node."):
            raise ValueError("E_CONTEXT_PACK_EDGES_INVALID")
        to_id = to_line.split("@Node.", 1)[1].strip()
        idx += 1
        if idx >= len(lines):
            raise ValueError("E_CONTEXT_PACK_EDGES_INVALID")
        direction_line = lines[idx].strip()
        if not direction_line.startswith("direction:"):
            raise ValueError("E_CONTEXT_PACK_EDGES_INVALID")
        direction = direction_line.split(":", 1)[1].strip()
        idx += 1
        if idx >= len(lines):
            raise ValueError("E_CONTEXT_PACK_EDGES_INVALID")
        channel_line = lines[idx].strip()
        if not channel_line.startswith("channel:"):
            raise ValueError("E_CONTEXT_PACK_EDGES_INVALID")
        channel = channel_line.split(":", 1)[1].strip()
        idx += 1
        if idx >= len(lines):
            raise ValueError("E_CONTEXT_PACK_EDGES_INVALID")
        contract_header = lines[idx].strip()
        if contract_header != "contract_refs:":
            raise ValueError("E_CONTEXT_PACK_EDGES_INVALID")
        idx += 1
        contracts: list[str] = []
        if idx >= len(lines):
            raise ValueError("E_CONTEXT_PACK_EDGES_INVALID")
        if lines[idx].strip() == "[]":
            idx += 1
        else:
            while idx < len(lines) and lines[idx].lstrip().startswith("- "):
                token = lines[idx].strip()[2:].strip()
                contracts.append(_strip_quotes(token))
                idx += 1
        edges.append(
            {
                "from": from_id,
                "to": to_id,
                "direction": _strip_quotes(direction),
                "channel": _strip_quotes(channel),
                "contract_refs": contracts,
            }
        )
    return edges


def _parse_simple_list(lines: list[str]) -> list[str]:
    if not lines:
        raise ValueError("E_CONTEXT_PACK_LIST_EMPTY")
    nonempty = [line for line in lines if line.strip() != ""]
    if not nonempty:
        raise ValueError("E_CONTEXT_PACK_LIST_EMPTY")
    if len(nonempty) == 1 and nonempty[0].strip() == "[]":
        return []
    items: list[str] = []
    for line in nonempty:
        stripped = line.strip()
        if not stripped.startswith("- "):
            raise ValueError("E_CONTEXT_PACK_LIST_INVALID")
        items.append(_strip_quotes(stripped[2:].strip()))
    return items


def _check_sorted_unique(items: list[str]) -> None:
    if items != sorted(items):
        raise ValueError("E_CONTEXT_PACK_LIST_NOT_SORTED")
    if len(items) != len(set(items)):
        raise ValueError("E_CONTEXT_PACK_LIST_DUPLICATE")


def _check_context_pack(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    if not text.endswith("\n"):
        raise ValueError("E_CONTEXT_PACK_NO_TRAILING_NEWLINE")
    lines = text.splitlines()
    if not lines or lines[0].strip() != "Context Pack":
        raise ValueError("E_CONTEXT_PACK_HEADER_MISSING")

    indexes = _find_section_indexes(lines)
    order_positions = [
        indexes["Header:"],
        indexes["Nodes:"],
        indexes["Edges:"],
        indexes["Contracts:"],
        indexes["Authz:"],
        indexes["Invariants:"],
        indexes["Open TODO"],
    ]
    if order_positions != sorted(order_positions):
        raise ValueError("E_CONTEXT_PACK_SECTION_ORDER")

    header_lines = _section_slice(lines, indexes["Header:"] + 1, indexes["Nodes:"])
    nodes_lines = _section_slice(lines, indexes["Nodes:"] + 1, indexes["Edges:"])
    edges_lines = _section_slice(lines, indexes["Edges:"] + 1, indexes["Contracts:"])
    contracts_lines = _section_slice(
        lines, indexes["Contracts:"] + 1, indexes["Authz:"]
    )
    authz_lines = _section_slice(lines, indexes["Authz:"] + 1, indexes["Invariants:"])
    invariants_lines = _section_slice(
        lines, indexes["Invariants:"] + 1, indexes["Open TODO"]
    )
    open_todo_line = lines[indexes["Open TODO"]].strip()
    open_todo_lines = lines[indexes["Open TODO"] + 1 :]

    header_keys: set[str] = set()
    for line in header_lines:
        if line.strip() == "":
            continue
        if _has_flow_style_marker(line):
            raise ValueError("E_CONTEXT_PACK_HEADER_FLOW_STYLE")
        stripped = line.strip()
        if ":" not in stripped:
            raise ValueError("E_CONTEXT_PACK_HEADER_INVALID")
        key = stripped.split(":", 1)[0].strip()
        if key:
            header_keys.add(key)
    if not header_keys:
        raise ValueError("E_CONTEXT_PACK_HEADER_EMPTY")
    for key in ("target", "profile", "stage"):
        if key not in header_keys:
            raise ValueError(f"E_CONTEXT_PACK_HEADER_MISSING:{key}")

    nodes = _parse_nodes(nodes_lines)
    node_sort_id = {}
    for rel_id, canon_id in nodes:
        key = canon_id if canon_id != "None" else rel_id
        node_sort_id[rel_id] = key
    node_order = [node_sort_id[n[0]] for n in nodes]
    if node_order != sorted(node_order):
        raise ValueError("E_CONTEXT_PACK_NODES_NOT_SORTED")

    edges = _parse_edges(edges_lines)

    def edge_key(edge: dict[str, object]) -> tuple[str, str, str, str, str]:
        from_id = node_sort_id.get(edge["from"], edge["from"])
        to_id = node_sort_id.get(edge["to"], edge["to"])
        direction = str(edge["direction"])
        channel = str(edge["channel"])
        joined_contracts = "|".join(list(edge["contract_refs"]))
        return (from_id, to_id, direction, channel, joined_contracts)

    edge_keys = [edge_key(e) for e in edges]
    if edge_keys != sorted(edge_keys):
        raise ValueError("E_CONTEXT_PACK_EDGES_NOT_SORTED")
    for edge in edges:
        _check_sorted_unique(list(edge["contract_refs"]))

    contracts = _parse_simple_list(contracts_lines)
    _check_sorted_unique(contracts)

    _parse_simple_list(authz_lines)
    _parse_simple_list(invariants_lines)

    if open_todo_line == "Open TODO: {}":
        for line in open_todo_lines:
            if line.strip():
                raise ValueError("E_CONTEXT_PACK_OPEN_TODO_INVALID")
        return
    if open_todo_line != "Open TODO:":
        raise ValueError("E_CONTEXT_PACK_OPEN_TODO_INVALID")
    if not open_todo_lines:
        raise ValueError("E_CONTEXT_PACK_OPEN_TODO_INVALID")

    entries: dict[str, tuple[str, list[str] | str]] = {}
    idx = 0
    while idx < len(open_todo_lines):
        line = open_todo_lines[idx]
        if line.strip() == "":
            idx += 1
            continue
        if not line.startswith("  "):
            raise ValueError("E_CONTEXT_PACK_OPEN_TODO_INVALID")
        stripped = line.strip()
        if ":" not in stripped:
            raise ValueError("E_CONTEXT_PACK_OPEN_TODO_INVALID")
        key, rest = stripped.split(":", 1)
        key = key.strip()
        if key not in OPEN_TODO_KEYS:
            raise ValueError("E_CONTEXT_PACK_OPEN_TODO_INVALID")
        if key in entries:
            raise ValueError("E_CONTEXT_PACK_OPEN_TODO_INVALID")
        rest = rest.strip()
        idx += 1
        if rest == "":
            values: list[str] = []
            while idx < len(open_todo_lines):
                next_line = open_todo_lines[idx]
                if next_line.strip() == "":
                    idx += 1
                    continue
                if next_line.startswith("  ") and not next_line.startswith("    - "):
                    break
                if not next_line.startswith("    - "):
                    raise ValueError("E_CONTEXT_PACK_OPEN_TODO_INVALID")
                item = next_line.strip()[2:].strip()
                values.append(_strip_quotes(item))
                idx += 1
            entries[key] = ("list", values)
            continue
        if rest == "[]":
            entries[key] = ("list", [])
            continue
        normalized = _strip_quotes(rest)
        if normalized in OPEN_TODO_MARKERS:
            entries[key] = ("marker", normalized)
            continue
        raise ValueError("E_CONTEXT_PACK_OPEN_TODO_INVALID")

    for key, (kind, payload) in entries.items():
        if key == "edge_intents":
            if kind != "list":
                raise ValueError("E_CONTEXT_PACK_OPEN_TODO_INVALID")
            _check_sorted_unique(list(payload))
            continue
        if kind == "marker":
            if str(payload) not in OPEN_TODO_MARKERS:
                raise ValueError("E_CONTEXT_PACK_OPEN_TODO_INVALID")
            continue
        if kind == "list":
            _check_sorted_unique(list(payload))
            continue
        raise ValueError("E_CONTEXT_PACK_OPEN_TODO_INVALID")


def _check_bundle_doc(context_path: Path, bundle_path: Path) -> None:
    context_text = context_path.read_text(encoding="utf-8")
    bundle_text = bundle_path.read_text(encoding="utf-8")
    if not bundle_text.startswith(context_text):
        raise ValueError("E_BUNDLE_DOC_CONTEXT_MISMATCH")
    tail = bundle_text[len(context_text) :]
    sup_lines = tail.splitlines(keepends=True)
    blocks = _parse_supplementary_blocks(sup_lines) if sup_lines else []
    order = [key for key, _ in blocks]
    if "provenance" not in order:
        raise ValueError("E_BUNDLE_DOC_SUPPLEMENTARY_REQUIRED_MISSING:provenance")
    expected = [k for k in SUPPLEMENTARY_ORDER if k in order]
    if order != expected:
        raise ValueError("E_BUNDLE_DOC_SUPPLEMENTARY_ORDER")
    for _, block in blocks:
        for line in block[2:]:
            stripped = line.strip()
            if stripped == "":
                continue
            if _has_flow_style_marker(line):
                raise ValueError("E_BUNDLE_DOC_SUPPLEMENTARY_FLOW_STYLE")


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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project-root", required=True, help="Project root")
    ap.add_argument(
        "--context-pack", default="OUTPUT/context_pack.yaml", help="Context Pack path"
    )
    ap.add_argument(
        "--bundle-doc", default="OUTPUT/bundle_doc.yaml", help="Bundle Doc path"
    )
    args = ap.parse_args()

    project_root = Path(args.project_root).resolve()
    context_path = (project_root / args.context_pack).resolve()
    bundle_path = (project_root / args.bundle_doc).resolve()

    try:
        _ensure_inside(project_root, context_path, "E_CONTEXT_PACK_OUTSIDE_PROJECT")
        _ensure_inside(project_root, bundle_path, "E_BUNDLE_DOC_OUTSIDE_PROJECT")
    except ValueError as exc:
        return _fail(str(exc))

    if context_path.is_symlink() or _has_symlink_parent(context_path, project_root):
        return _fail("E_CONTEXT_PACK_SYMLINK")
    if bundle_path.is_symlink() or _has_symlink_parent(bundle_path, project_root):
        return _fail("E_BUNDLE_DOC_SYMLINK")

    if not context_path.exists():
        return _fail("E_CONTEXT_PACK_NOT_FOUND")
    if not bundle_path.exists():
        return _fail("E_BUNDLE_DOC_NOT_FOUND")

    try:
        _check_context_pack(context_path)
        _check_bundle_doc(context_path, bundle_path)
    except ValueError as exc:
        return _fail(str(exc))

    print("[OK] context_pack/bundle_doc checks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
