from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

from .lint import _capture_metadata, _parse_metadata_pairs, _split_list_items
from .refs import parse_internal_ref


ANNOTATION_KIND_RE = re.compile(r"^\s*@(?P<kind>[A-Za-z_][A-Za-z0-9_]*)\b")


@dataclass(frozen=True)
class NodeEntry:
    rel_id: str


@dataclass(frozen=True)
class EdgeEntry:
    from_id: str
    to_id: str
    direction: str | None
    channel: str | None
    contract_refs: tuple[str, ...]


@dataclass(frozen=True)
class EdgeIntentEntry:
    intent_id: str
    from_id: str
    to_id: str
    direction: str | None
    channel: str | None
    note: str | None
    owner: str | None
    contract_hint: str | None


def _strip_quotes(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] == '"':
        return value[1:-1]
    return value


def _quote(value: str) -> str:
    value = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{value}"'


def _parse_annotations(lines: list[str]) -> list[tuple[str, dict[str, str], int]]:
    annotations: list[tuple[str, dict[str, str], int]] = []
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
            raise ValueError(f"E_CONTEXT_PACK_METADATA_MISSING: line {idx + 1}")
        meta, _ = _capture_metadata(lines, idx, brace_idx)
        pairs = _parse_metadata_pairs(meta)
        meta_map: dict[str, str] = {}
        for key, value in pairs:
            if key in meta_map:
                raise ValueError(
                    f"E_CONTEXT_PACK_DUPLICATE_KEY: line {idx + 1} key {key}"
                )
            meta_map[key] = value
        annotations.append((kind, meta_map, idx))
    return annotations


def _parse_file_header(
    annotations: list[tuple[str, dict[str, str], int]],
    first_stmt: int | None,
) -> tuple[str | None, str | None, str | None]:
    file_entries = [(meta, idx) for kind, meta, idx in annotations if kind == "File"]
    if not file_entries:
        return None, None, None
    if len(file_entries) > 1:
        raise ValueError("E_CONTEXT_PACK_DUPLICATE_FILE_HEADER")
    meta, idx = file_entries[0]
    if first_stmt is not None and idx != first_stmt:
        raise ValueError("E_CONTEXT_PACK_FILE_HEADER_NOT_FIRST")
    profile = meta.get("profile")
    stage = meta.get("stage")
    id_prefix = meta.get("id_prefix")
    profile = _strip_quotes(profile) if profile else None
    stage = _strip_quotes(stage) if stage else None
    id_prefix = _strip_quotes(id_prefix) if id_prefix else None
    return profile, stage, id_prefix


def _parse_nodes(annotations: list[tuple[str, dict[str, str], int]]) -> list[NodeEntry]:
    nodes: list[NodeEntry] = []
    for kind, meta, _ in annotations:
        if kind != "Node":
            continue
        rel_id = meta.get("id")
        if not rel_id:
            continue
        rel_id = _strip_quotes(rel_id)
        nodes.append(NodeEntry(rel_id=rel_id))
    return nodes


def _parse_edges(
    annotations: list[tuple[str, dict[str, str], int]],
    node_ids: set[str],
) -> list[EdgeEntry]:
    edges: list[EdgeEntry] = []
    for kind, meta, _ in annotations:
        if kind != "Edge":
            continue
        raw_from = meta.get("from")
        raw_to = meta.get("to")
        if not raw_from or not raw_to:
            continue
        from_ref = parse_internal_ref(raw_from)
        to_ref = parse_internal_ref(raw_to)
        if not from_ref or not to_ref or from_ref.kind != "Node" or to_ref.kind != "Node":
            raise ValueError("E_CONTEXT_PACK_EDGE_FROM_TO_INVALID")
        if from_ref.rel_id not in node_ids or to_ref.rel_id not in node_ids:
            raise ValueError("E_CONTEXT_PACK_EDGE_NODE_UNDECLARED")
        direction = meta.get("direction")
        direction = _strip_quotes(direction) if direction else None
        channel = meta.get("channel")
        channel = _strip_quotes(channel) if channel else None
        contract_refs: list[str] = []
        raw_contract_refs = meta.get("contract_refs")
        if not raw_contract_refs:
            raise ValueError("E_CONTEXT_PACK_EDGE_CONTRACT_REFS_MISSING")
        if raw_contract_refs:
            for item in _split_list_items(raw_contract_refs):
                contract_refs.append(_strip_quotes(item))
        if not contract_refs:
            raise ValueError("E_CONTEXT_PACK_EDGE_CONTRACT_REFS_EMPTY")
        contract_refs = sorted(dict.fromkeys(contract_refs))
        edges.append(
            EdgeEntry(
                from_id=from_ref.rel_id,
                to_id=to_ref.rel_id,
                direction=direction,
                channel=channel,
                contract_refs=tuple(contract_refs),
            )
        )
    return edges


def _parse_edge_intents(
    annotations: list[tuple[str, dict[str, str], int]],
    node_ids: set[str],
) -> list[EdgeIntentEntry]:
    intents: list[EdgeIntentEntry] = []
    for kind, meta, _ in annotations:
        if kind != "EdgeIntent":
            continue
        raw_from = meta.get("from")
        raw_to = meta.get("to")
        raw_id = meta.get("id")
        if not raw_from or not raw_to or not raw_id:
            continue
        from_ref = parse_internal_ref(raw_from)
        to_ref = parse_internal_ref(raw_to)
        if not from_ref or not to_ref or from_ref.kind != "Node" or to_ref.kind != "Node":
            raise ValueError("E_CONTEXT_PACK_EDGEINTENT_FROM_TO_INVALID")
        if from_ref.rel_id not in node_ids or to_ref.rel_id not in node_ids:
            raise ValueError("E_CONTEXT_PACK_EDGEINTENT_NODE_UNDECLARED")
        direction = meta.get("direction")
        channel = meta.get("channel")
        note = meta.get("note")
        owner = meta.get("owner")
        contract_hint = meta.get("contract_hint")
        intents.append(
            EdgeIntentEntry(
                intent_id=_strip_quotes(raw_id),
                from_id=from_ref.rel_id,
                to_id=to_ref.rel_id,
                direction=_strip_quotes(direction) if direction else None,
                channel=_strip_quotes(channel) if channel else None,
                note=_strip_quotes(note) if note else None,
                owner=_strip_quotes(owner) if owner else None,
                contract_hint=_strip_quotes(contract_hint) if contract_hint else None,
            )
        )
    return intents


def _edge_sort_key(edge: EdgeEntry, node_sort_id: dict[str, str]) -> tuple[str, str, str, str, tuple[str, ...]]:
    return (
        node_sort_id.get(edge.from_id, edge.from_id),
        node_sort_id.get(edge.to_id, edge.to_id),
        edge.direction or "",
        edge.channel or "",
        edge.contract_refs,
    )


def _format_edge_intent(intent: EdgeIntentEntry) -> str:
    parts = [
        f'id:{_quote(intent.intent_id)}',
        f'from:@Node.{intent.from_id}',
        f'to:@Node.{intent.to_id}',
    ]
    if intent.direction:
        parts.append(f'direction:{_quote(intent.direction)}')
    if intent.channel:
        parts.append(f'channel:{_quote(intent.channel)}')
    if intent.note:
        parts.append(f'note:{_quote(intent.note)}')
    if intent.owner:
        parts.append(f'owner:{_quote(intent.owner)}')
    if intent.contract_hint:
        parts.append(f'contract_hint:{_quote(intent.contract_hint)}')
    return "@EdgeIntent { " + ", ".join(parts) + " }"


def _first_stmt_line(lines: list[str]) -> int | None:
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if stripped == "" or stripped.startswith("//"):
            continue
        return idx
    return None


def extract_context_pack(path: Path, target: str, hops: int = 1) -> str:
    text = path.read_text(encoding="utf-8")
    if "/*" in text or "*/" in text:
        raise ValueError("E_CONTEXT_PACK_BLOCK_COMMENT_UNSUPPORTED")
    lines = text.splitlines()
    annotations = _parse_annotations(lines)
    first_stmt = _first_stmt_line(lines)
    profile, stage, id_prefix = _parse_file_header(annotations, first_stmt)
    if profile is None:
        raise ValueError("E_CONTEXT_PACK_FILE_HEADER_MISSING")
    if profile != "topology":
        raise ValueError(f"E_CONTEXT_PACK_PROFILE_INVALID: {profile}")
    if not id_prefix:
        raise ValueError("E_CONTEXT_PACK_ID_PREFIX_MISSING")

    target_ref = parse_internal_ref(target)
    if not target_ref or target_ref.kind != "Node":
        raise ValueError(f"E_CONTEXT_PACK_TARGET_INVALID: {target}")

    for kind, _, _ in annotations:
        if kind in {"Flow", "Terminal"}:
            raise ValueError(f"E_CONTEXT_PACK_UNSUPPORTED_KIND: {kind}")

    nodes = _parse_nodes(annotations)
    node_ids = {node.rel_id for node in nodes}
    if target_ref.rel_id not in node_ids:
        raise ValueError(f"E_CONTEXT_PACK_TARGET_NOT_FOUND: {target_ref.rel_id}")

    edges = _parse_edges(annotations, node_ids)
    intents = _parse_edge_intents(annotations, node_ids)

    adjacency: dict[str, set[str]] = {node.rel_id: set() for node in nodes}
    for edge in edges:
        adjacency.setdefault(edge.from_id, set()).add(edge.to_id)
        adjacency.setdefault(edge.to_id, set()).add(edge.from_id)

    visited = {target_ref.rel_id}
    frontier = {target_ref.rel_id}
    for _ in range(max(0, hops)):
        next_frontier: set[str] = set()
        for node_id in frontier:
            next_frontier.update(adjacency.get(node_id, set()))
        next_frontier -= visited
        visited.update(next_frontier)
        frontier = next_frontier

    node_sort_id = {node.rel_id: f"{id_prefix}_{node.rel_id}" for node in nodes}
    scope_nodes = [node for node in nodes if node.rel_id in visited]
    scope_nodes.sort(key=lambda n: node_sort_id.get(n.rel_id, n.rel_id))

    scope_edges = [edge for edge in edges if edge.from_id in visited and edge.to_id in visited]
    scope_edges.sort(key=lambda e: _edge_sort_key(e, node_sort_id))

    contracts: list[str] = []
    for edge in scope_edges:
        for token in edge.contract_refs:
            contracts.append(token)
    contracts = sorted(dict.fromkeys(contracts))

    scope_intents = [
        intent
        for intent in intents
        if intent.from_id in visited and intent.to_id in visited
    ]
    scope_intents.sort(key=lambda i: i.intent_id)

    stage_value = stage or "L2"

    out: list[str] = [
        "Context Pack",
        "Header:",
        f"  target: @Node.{target_ref.rel_id}",
        f"  profile: {profile}",
        f"  stage: {stage_value}",
        "Nodes:",
    ]
    if not scope_nodes:
        out.append("  []")
    else:
        for node in scope_nodes:
            canon_id = node_sort_id.get(node.rel_id, "None")
            out.append(f"  - rel_id: {node.rel_id}")
            out.append(f"    canon_id: {canon_id}")

    out.append("Edges:")
    if not scope_edges:
        out.append("  []")
    else:
        for edge in scope_edges:
            direction = _quote(edge.direction) if edge.direction else "None"
            channel = _quote(edge.channel) if edge.channel else "None"
            out.append(f"  - from: @Node.{edge.from_id}")
            out.append(f"    to: @Node.{edge.to_id}")
            out.append(f"    direction: {direction}")
            out.append(f"    channel: {channel}")
            out.append("    contract_refs:")
            if edge.contract_refs:
                for token in edge.contract_refs:
                    out.append(f"      - {_quote(token)}")
            else:
                out.append("      []")

    out.append("Contracts:")
    if not contracts:
        out.append("  []")
    else:
        for token in contracts:
            out.append(f"  - {_quote(token)}")

    out.append("Authz:")
    out.append("  []")
    out.append("Invariants:")
    out.append("  []")

    if scope_intents:
        out.append("Open TODO:")
        out.append("  edge_intents:")
        for intent in scope_intents:
            out.append(f"    - {intent.intent_id}")
    else:
        out.append("Open TODO: {}")

    return "\n".join(out) + "\n"
