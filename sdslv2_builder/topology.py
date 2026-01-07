from __future__ import annotations

import hashlib
from dataclasses import dataclass

from .jcs import dumps as jcs_dumps
from .ledger import EdgeInput, NodeInput, TopologyInput


@dataclass(frozen=True)
class Node:
    rel_id: str
    kind: str
    bind: str | None


@dataclass(frozen=True)
class Edge:
    edge_id: str
    from_id: str
    to_id: str
    direction: str
    contract_refs: list[str]


@dataclass(frozen=True)
class TopologyModel:
    id_prefix: str
    stage: str | None
    nodes: list[Node]
    edges: list[Edge]


def _edge_pk(edge: EdgeInput) -> dict[str, object]:
    return {
        "from": edge.from_id,
        "to": edge.to_id,
        "direction": edge.direction,
        "contract_refs": [ref.token for ref in edge.contract_refs],
    }


def compute_edge_id(edge: EdgeInput) -> str:
    pk = _edge_pk(edge)
    payload = jcs_dumps(pk).encode("utf-8")
    digest = hashlib.sha256(payload).hexdigest()[:16].upper()
    return f"E_{digest}"


def build_topology_model(input_data: TopologyInput) -> TopologyModel:
    nodes: list[Node] = []
    for node in input_data.nodes:
        bind = node.bind.to_string() if node.bind else None
        nodes.append(Node(rel_id=node.rel_id, kind=node.kind, bind=bind))

    edges: list[Edge] = []
    for edge in input_data.edges:
        edge_id = compute_edge_id(edge)
        edges.append(
            Edge(
                edge_id=edge_id,
                from_id=edge.from_id,
                to_id=edge.to_id,
                direction=edge.direction,
                contract_refs=[ref.token for ref in edge.contract_refs],
            )
        )

    return TopologyModel(
        id_prefix=input_data.id_prefix,
        stage=input_data.stage,
        nodes=nodes,
        edges=edges,
    )
