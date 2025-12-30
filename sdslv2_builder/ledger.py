from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .errors import Diagnostic, json_pointer
from .refs import ContractRef, InternalRef, parse_contract_ref, parse_internal_ref


RELID_RE = re.compile(r"^[A-Z][A-Z0-9_]{2,63}$")
DIRECTION_VOCAB = {"pub", "sub", "req", "rep", "rw", "call"}


@dataclass(frozen=True)
class NodeInput:
    rel_id: str
    kind: str
    bind: InternalRef | None


@dataclass(frozen=True)
class EdgeInput:
    from_id: str
    to_id: str
    direction: str
    contract_refs: list[ContractRef]


@dataclass(frozen=True)
class TopologyInput:
    id_prefix: str
    nodes: list[NodeInput]
    edges: list[EdgeInput]
    output_path: Path | None


def _parse_scalar(value: str) -> Any:
    value = value.strip()
    if value == "null":
        return None
    if value == "true":
        return True
    if value == "false":
        return False
    if value == "[]":
        return []
    if value == "{}":
        return {}
    if len(value) >= 2 and value[0] == '"' and value[-1] == '"':
        return value[1:-1].replace(r"\\", "\\").replace(r"\"", '"')
    if re.match(r"^-?\d+$", value):
        return int(value)
    if re.match(r"^-?\d+\.\d+$", value):
        return float(value)
    return value


def _count_indent(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def _parse_block(lines: list[str], start: int, indent: int) -> tuple[Any, int]:
    i = start
    block_type = None
    items: list[Any] = []
    mapping: dict[str, Any] = {}

    while i < len(lines):
        line = lines[i]
        if line.strip() == "":
            i += 1
            continue
        cur_indent = _count_indent(line)
        if cur_indent < indent:
            break
        if cur_indent > indent:
            raise ValueError(f"YAML_INDENT_ERROR:{i + 1}")
        content = line[cur_indent:]
        if content.startswith("-"):
            if block_type is None:
                block_type = "list"
            if block_type != "list":
                raise ValueError(f"YAML_MIXED_BLOCK:{i + 1}")
            rest = content[1:].lstrip()
            if rest == "":
                value, i = _parse_block(lines, i + 1, indent + 2)
            else:
                if ":" in rest:
                    key, tail = rest.split(":", 1)
                    key = key.strip()
                    tail = tail.lstrip()
                    if not key:
                        raise ValueError(f"YAML_MISSING_KEY:{i + 1}")
                    value = {}
                    if tail == "":
                        nested, i = _parse_block(lines, i + 1, indent + 2)
                        value[key] = nested
                    else:
                        value[key] = _parse_scalar(tail)
                        i += 1

                    probe = i
                    while probe < len(lines) and lines[probe].strip() == "":
                        probe += 1
                    if probe < len(lines):
                        probe_indent = _count_indent(lines[probe])
                        if probe_indent == indent + 2 and not lines[probe].lstrip().startswith("-"):
                            extra, i = _parse_block(lines, probe, indent + 2)
                            if not isinstance(extra, dict):
                                raise ValueError(f"YAML_LIST_ITEM_NOT_DICT:{probe + 1}")
                            value.update(extra)
                        elif probe_indent > indent and lines[probe].lstrip().startswith("-"):
                            raise ValueError(f"YAML_UNSUPPORTED_LIST_ITEM:{probe + 1}")
                else:
                    value = _parse_scalar(rest)
                    i += 1
            items.append(value)
            continue

        if block_type is None and ":" not in content:
            return _parse_scalar(content), i + 1

        if block_type is None:
            block_type = "dict"
        if block_type != "dict":
            raise ValueError(f"YAML_MIXED_BLOCK:{i + 1}")
        if ":" not in content:
            raise ValueError(f"YAML_MISSING_COLON:{i + 1}")
        key, rest = content.split(":", 1)
        key = key.strip()
        rest = rest.lstrip()
        if rest == "":
            value, i = _parse_block(lines, i + 1, indent + 2)
        else:
            value = _parse_scalar(rest)
            i += 1
        mapping[key] = value
    return (items if block_type == "list" else mapping), i


def load_ledger(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        return json.loads(text)
    lines = text.splitlines()
    data, _ = _parse_block(lines, 0, 0)
    if not isinstance(data, dict):
        raise ValueError("LEDGER_TOP_LEVEL_NOT_DICT")
    return data


def _add_diag(
    diagnostics: list[Diagnostic],
    code: str,
    message: str,
    expected: str,
    got: str,
    path: str,
) -> None:
    diagnostics.append(
        Diagnostic(
            code=code,
            message=message,
            expected=expected,
            got=got,
            path=path,
        )
    )


def _ensure_dict(value: Any, diagnostics: list[Diagnostic], path: str) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    _add_diag(
        diagnostics,
        "E_LEDGER_FIELD_TYPE_INVALID",
        "Ledger field must be an object",
        "object",
        type(value).__name__,
        path,
    )
    return {}


def _ensure_list(value: Any, diagnostics: list[Diagnostic], path: str) -> list[Any]:
    if isinstance(value, list):
        return value
    _add_diag(
        diagnostics,
        "E_LEDGER_FIELD_TYPE_INVALID",
        "Ledger field must be a list",
        "list",
        type(value).__name__,
        path,
    )
    return []


def validate_ledger(data: dict[str, Any], output_root: Path) -> tuple[TopologyInput | None, list[Diagnostic]]:
    diagnostics: list[Diagnostic] = []

    if not isinstance(data, dict):
        _add_diag(
            diagnostics,
            "E_LEDGER_SCHEMA_INVALID",
            "Ledger root must be an object",
            "object",
            type(data).__name__,
            json_pointer(),
        )
        return None, diagnostics

    required_keys = {"version", "schema_revision", "file_header", "nodes", "edges"}
    optional_keys = {"source", "output"}
    for key in required_keys:
        if key not in data:
            _add_diag(
                diagnostics,
                "E_LEDGER_REQUIRED_FIELD_MISSING",
                "Missing required ledger field",
                key,
                "missing",
                json_pointer(key),
            )
    for key in data.keys():
        if key not in required_keys and key not in optional_keys:
            _add_diag(
                diagnostics,
                "E_LEDGER_UNKNOWN_FIELD",
                "Unknown ledger field",
                "known top-level fields",
                key,
                json_pointer(key),
            )

    if data.get("version") != "topology-ledger-v0.1":
        _add_diag(
            diagnostics,
            "E_LEDGER_SCHEMA_INVALID",
            "Ledger version mismatch",
            "topology-ledger-v0.1",
            str(data.get("version")),
            json_pointer("version"),
        )

    file_header = _ensure_dict(data.get("file_header"), diagnostics, json_pointer("file_header"))
    header_allowed = {"profile", "id_prefix"}
    for key in file_header.keys():
        if key not in header_allowed:
            _add_diag(
                diagnostics,
                "E_LEDGER_UNKNOWN_FIELD",
                "Unknown file_header field",
                "profile,id_prefix",
                key,
                json_pointer("file_header", key),
            )

    profile = file_header.get("profile")
    if profile != "topology":
        _add_diag(
            diagnostics,
            "E_PROFILE_INVALID",
            "profile must be topology",
            "topology",
            str(profile),
            json_pointer("file_header", "profile"),
        )

    id_prefix = file_header.get("id_prefix")
    if not isinstance(id_prefix, str) or not id_prefix.strip():
        _add_diag(
            diagnostics,
            "E_ID_FORMAT_INVALID",
            "id_prefix must be a non-empty string",
            "non-empty string",
            str(id_prefix),
            json_pointer("file_header", "id_prefix"),
        )
        id_prefix = ""

    nodes_raw = _ensure_list(data.get("nodes"), diagnostics, json_pointer("nodes"))
    edges_raw = _ensure_list(data.get("edges"), diagnostics, json_pointer("edges"))

    nodes: list[NodeInput] = []
    node_ids: set[str] = set()

    for idx, node in enumerate(nodes_raw):
        path = json_pointer("nodes", str(idx))
        node_obj = _ensure_dict(node, diagnostics, path)
        allowed = {"id", "kind", "bind"}
        for key in node_obj.keys():
            if key not in allowed:
                _add_diag(
                    diagnostics,
                    "E_LEDGER_UNKNOWN_FIELD",
                    "Unknown node field",
                    "id,kind,bind",
                    key,
                    json_pointer("nodes", str(idx), key),
                )
        rel_id = node_obj.get("id")
        if not isinstance(rel_id, str) or not RELID_RE.match(rel_id):
            _add_diag(
                diagnostics,
                "E_ID_FORMAT_INVALID",
                "Node id must be RELID",
                "UPPER_SNAKE_CASE",
                str(rel_id),
                json_pointer("nodes", str(idx), "id"),
            )
            rel_id = ""
        if rel_id and rel_id in node_ids:
            _add_diag(
                diagnostics,
                "E_ID_DUPLICATE",
                "Duplicate node id",
                "unique id",
                rel_id,
                json_pointer("nodes", str(idx), "id"),
            )
        node_ids.add(rel_id)

        kind = node_obj.get("kind")
        if not isinstance(kind, str) or not kind.strip():
            _add_diag(
                diagnostics,
                "E_LEDGER_REQUIRED_FIELD_MISSING",
                "Node kind is required",
                "non-empty string",
                str(kind),
                json_pointer("nodes", str(idx), "kind"),
            )
            kind = ""

        bind_value = node_obj.get("bind")
        bind_ref = None
        if bind_value is not None:
            if not isinstance(bind_value, str):
                _add_diag(
                    diagnostics,
                    "E_BIND_TARGET_NOT_FOUND",
                    "bind must be an InternalRef string",
                    "@Kind.RELID",
                    type(bind_value).__name__,
                    json_pointer("nodes", str(idx), "bind"),
                )
            else:
                bind_ref = parse_internal_ref(bind_value)
                if not bind_ref:
                    _add_diag(
                        diagnostics,
                        "E_BIND_TARGET_NOT_FOUND",
                        "bind must be an InternalRef string",
                        "@Kind.RELID",
                        bind_value,
                        json_pointer("nodes", str(idx), "bind"),
                    )

        nodes.append(NodeInput(rel_id=rel_id, kind=kind, bind=bind_ref))

    edges: list[EdgeInput] = []
    edge_pk_seen: set[tuple[str, str, str, tuple[str, ...]]] = set()

    for idx, edge in enumerate(edges_raw):
        path = json_pointer("edges", str(idx))
        edge_obj = _ensure_dict(edge, diagnostics, path)
        allowed = {"from", "to", "direction", "contract_refs"}
        for key in edge_obj.keys():
            if key not in allowed:
                _add_diag(
                    diagnostics,
                    "E_LEDGER_UNKNOWN_FIELD",
                    "Unknown edge field",
                    "from,to,direction,contract_refs",
                    key,
                    json_pointer("edges", str(idx), key),
                )

        from_id = edge_obj.get("from")
        to_id = edge_obj.get("to")
        direction = edge_obj.get("direction")
        refs_raw = edge_obj.get("contract_refs")

        if not isinstance(from_id, str):
            _add_diag(
                diagnostics,
                "E_EDGE_MISSING_FIELD",
                "Edge from is required",
                "string",
                str(from_id),
                json_pointer("edges", str(idx), "from"),
            )
            from_id = ""
        if not isinstance(to_id, str):
            _add_diag(
                diagnostics,
                "E_EDGE_MISSING_FIELD",
                "Edge to is required",
                "string",
                str(to_id),
                json_pointer("edges", str(idx), "to"),
            )
            to_id = ""
        if not isinstance(direction, str) or direction not in DIRECTION_VOCAB:
            _add_diag(
                diagnostics,
                "E_EDGE_DIRECTION_INVALID",
                "Edge direction invalid",
                "pub|sub|req|rep|rw|call",
                str(direction),
                json_pointer("edges", str(idx), "direction"),
            )
            direction = ""

        if from_id and from_id not in node_ids:
            _add_diag(
                diagnostics,
                "E_EDGE_FROM_TO_UNRESOLVED",
                "Edge from must reference existing node",
                "existing node id",
                from_id,
                json_pointer("edges", str(idx), "from"),
            )
        if to_id and to_id not in node_ids:
            _add_diag(
                diagnostics,
                "E_EDGE_FROM_TO_UNRESOLVED",
                "Edge to must reference existing node",
                "existing node id",
                to_id,
                json_pointer("edges", str(idx), "to"),
            )

        contract_refs: list[ContractRef] = []
        if not isinstance(refs_raw, list):
            _add_diag(
                diagnostics,
                "E_CONTRACT_REFS_INVALID",
                "contract_refs must be a list",
                "list of CONTRACT.*",
                type(refs_raw).__name__,
                json_pointer("edges", str(idx), "contract_refs"),
            )
        else:
            if not refs_raw:
                _add_diag(
                    diagnostics,
                    "E_EDGE_CONTRACT_REFS_EMPTY",
                    "contract_refs must be non-empty",
                    "non-empty list",
                    "empty",
                    json_pointer("edges", str(idx), "contract_refs"),
                )
            seen = set()
            for ref_idx, raw in enumerate(refs_raw):
                if not isinstance(raw, str):
                    _add_diag(
                        diagnostics,
                        "E_CONTRACT_REFS_INVALID",
                        "contract_refs items must be CONTRACT.* tokens",
                        "CONTRACT.*",
                        type(raw).__name__,
                        json_pointer("edges", str(idx), "contract_refs", str(ref_idx)),
                    )
                    continue
                parsed = parse_contract_ref(raw)
                if not parsed:
                    _add_diag(
                        diagnostics,
                        "E_CONTRACT_REFS_INVALID",
                        "contract_refs items must be CONTRACT.* tokens",
                        "CONTRACT.*",
                        raw,
                        json_pointer("edges", str(idx), "contract_refs", str(ref_idx)),
                    )
                    continue
                if parsed.token in seen:
                    _add_diag(
                        diagnostics,
                        "E_CONTRACT_REFS_INVALID",
                        "contract_refs must be unique",
                        "unique list",
                        parsed.token,
                        json_pointer("edges", str(idx), "contract_refs"),
                    )
                    continue
                seen.add(parsed.token)
                contract_refs.append(parsed)

        contract_refs_sorted = sorted(contract_refs, key=lambda r: r.token)
        pk = (from_id, to_id, direction, tuple(r.token for r in contract_refs_sorted))
        if pk in edge_pk_seen:
            _add_diag(
                diagnostics,
                "E_EDGE_DUPLICATE",
                "Duplicate edge (same PK)",
                "unique PK",
                f"{from_id}->{to_id}",
                json_pointer("edges", str(idx)),
            )
        edge_pk_seen.add(pk)

        edges.append(
            EdgeInput(
                from_id=from_id,
                to_id=to_id,
                direction=direction,
                contract_refs=contract_refs_sorted,
            )
        )

    output_path = None
    output_field = data.get("output")
    if output_field is not None:
        output_obj = _ensure_dict(output_field, diagnostics, json_pointer("output"))
        raw_path = output_obj.get("topology_v2_path")
        if raw_path is not None:
            if not isinstance(raw_path, str):
                _add_diag(
                    diagnostics,
                    "E_LEDGER_FIELD_TYPE_INVALID",
                    "output.topology_v2_path must be a string",
                    "string",
                    type(raw_path).__name__,
                    json_pointer("output", "topology_v2_path"),
                )
            else:
                if raw_path.startswith("OUTPUT/"):
                    candidate = Path(raw_path)
                else:
                    candidate = output_root / raw_path
                candidate = candidate.resolve()
                root = output_root.resolve()
                if root not in candidate.parents and root != candidate:
                    _add_diag(
                        diagnostics,
                        "E_LEDGER_SCHEMA_INVALID",
                        "output.topology_v2_path must be under OUTPUT",
                        "OUTPUT/...",
                        raw_path,
                        json_pointer("output", "topology_v2_path"),
                    )
                else:
                    output_path = candidate

    if diagnostics:
        return None, diagnostics

    return TopologyInput(
        id_prefix=id_prefix,
        nodes=nodes,
        edges=edges,
        output_path=output_path,
    ), diagnostics
