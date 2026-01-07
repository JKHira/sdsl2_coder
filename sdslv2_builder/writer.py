from __future__ import annotations

from dataclasses import dataclass

from .topology import Edge, Node, TopologyModel


def _format_kv(key: str, value: str) -> str:
    return f'{key}:{value}'


def _format_contract_refs(items: list[str]) -> str:
    inner = ",".join(f'"{item}"' for item in items)
    return f'[{inner}]'


def _format_node(node: Node) -> list[str]:
    pairs = [
        _format_kv("id", f'"{node.rel_id}"'),
        _format_kv("kind", f'"{node.kind}"'),
    ]
    if node.bind:
        pairs.append(_format_kv("bind", node.bind))

    if len(pairs) <= 2:
        inner = ", ".join(pairs)
        return [f"@Node {{ {inner} }}"]

    lines = ["@Node {"]
    for pair in pairs:
        lines.append(f"  {pair},")
    lines.append("}")
    return lines


def _format_edge(edge: Edge) -> list[str]:
    lines = [
        "@Edge {",
        f'  id:"{edge.edge_id}",',
        f"  from:@Node.{edge.from_id},",
        f"  to:@Node.{edge.to_id},",
        f'  direction:"{edge.direction}",',
        f"  contract_refs:{_format_contract_refs(edge.contract_refs)},",
        "}",
    ]
    return lines


def _sort_nodes(nodes: list[Node]) -> list[Node]:
    return sorted(nodes, key=lambda n: n.rel_id)


def _sort_edges(edges: list[Edge]) -> list[Edge]:
    return sorted(edges, key=lambda e: (e.from_id, e.to_id, e.direction, tuple(e.contract_refs)))


def write_topology(model: TopologyModel) -> str:
    if not isinstance(model, TopologyModel):
        raise TypeError("MODEL_TYPE_INVALID")

    lines: list[str] = []
    header_parts = [
        'profile:"topology"',
        f'id_prefix:"{model.id_prefix}"',
    ]
    if model.stage:
        header_parts.append(f'stage:"{model.stage}"')
    lines.append(f"@File {{ {', '.join(header_parts)} }}")

    for node in _sort_nodes(model.nodes):
        lines.extend(_format_node(node))
    for edge in _sort_edges(model.edges):
        lines.extend(_format_edge(edge))

    text = "\n".join(lines).rstrip() + "\n"
    return text
