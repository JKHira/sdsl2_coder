from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from sdslv2_builder.errors import Diagnostic, json_pointer
from sdslv2_builder.lint import _capture_metadata, _parse_metadata_pairs, _split_list_items, DIRECTION_VOCAB
from sdslv2_builder.refs import RELID_RE, parse_contract_ref, parse_internal_ref


@dataclass(frozen=True)
class GapItem:
    kind: str
    line: int
    ident: str | None
    missing: list[str]
    from_id: str | None = None
    to_id: str | None = None
    direction: str | None = None


def _strip_quotes(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] == '"':
        return value[1:-1]
    return value


def _value_missing(value: str | None) -> bool:
    if value is None:
        return True
    value = value.strip()
    if value == "":
        return True
    lowered = value.strip('"').lower()
    return lowered in {"none", "null"}


def _iter_annotations(lines: list[str]) -> list[tuple[str, dict[str, str] | None, int, int, list[str]]]:
    annotations: list[tuple[str, dict[str, str] | None, int, int, list[str]]] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.lstrip().startswith("@"):
            i += 1
            continue
        kind = line.lstrip().split(None, 1)[0][1:]
        brace_idx = line.find("{")
        if brace_idx == -1:
            annotations.append((kind, None, i, i, []))
            i += 1
            continue
        meta, end_line = _capture_metadata(lines, i, brace_idx)
        meta = meta.strip()
        pairs = _parse_metadata_pairs(meta)
        meta_map: dict[str, str] = {}
        dupes: list[str] = []
        for key, value in pairs:
            if key in meta_map and key not in dupes:
                dupes.append(key)
            meta_map[key] = value
        annotations.append((kind, meta_map, i, end_line, dupes))
        i = end_line + 1
    return annotations


def _emit_diag(
    diags: list[Diagnostic],
    code: str,
    message: str,
    expected: str,
    got: str,
    path: str,
) -> None:
    diags.append(Diagnostic(code=code, message=message, expected=expected, got=got, path=path))


def analyze_topology_files(
    project_root: Path,
    files: list[Path],
) -> tuple[list[Diagnostic], list[Diagnostic], list[dict]]:
    hard_diags: list[Diagnostic] = []
    soft_diags: list[Diagnostic] = []
    gaps: list[dict] = []

    for path in sorted(files, key=lambda p: p.as_posix()):
        rel_path = path.resolve().relative_to(project_root.resolve()).as_posix()
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            _emit_diag(
                hard_diags,
                "E_TOPO_RES_READ_FAILED",
                "Failed to read topology file",
                "readable UTF-8 file",
                f"{rel_path}: {exc}",
                json_pointer(),
            )
            continue
        lines = text.splitlines()
        annotations = _iter_annotations(lines)

        profile = None
        stage = None
        for _, meta, idx, _, dupes in annotations:
            if meta is None:
                continue
            if dupes:
                for key in dupes:
                    _emit_diag(
                        hard_diags,
                        "E_TOPO_RES_METADATA_DUPLICATE_KEY",
                        "Duplicate metadata key",
                        "unique key",
                        key,
                        json_pointer("annotations", str(idx), key),
                    )
            if lines[idx].lstrip().startswith("@File"):
                if profile is None:
                    profile = _strip_quotes(meta.get("profile"))
                    stage = _strip_quotes(meta.get("stage"))

        if profile is None:
            _emit_diag(
                hard_diags,
                "E_TOPO_RES_FILE_HEADER_MISSING",
                "Missing @File header",
                "@File { profile:\"topology\" }",
                "missing",
                json_pointer(),
            )
            continue
        if profile != "topology":
            _emit_diag(
                hard_diags,
                "E_TOPO_RES_PROFILE_INVALID",
                "profile must be topology",
                "topology",
                str(profile),
                json_pointer("file_header", "profile"),
            )
            continue

        node_ids: set[str] = set()
        node_index = 0
        edge_index = 0
        node_gaps: list[GapItem] = []
        edge_gaps: list[GapItem] = []

        for kind, meta, idx, _, dupes in annotations:
            if meta is None:
                if lines[idx].lstrip().startswith("@"):
                    _emit_diag(
                        hard_diags,
                        "E_TOPO_RES_METADATA_MISSING",
                        "Annotation must include metadata object",
                        "{...}",
                        "missing",
                        json_pointer("annotations", str(idx)),
                    )
                continue
            if dupes:
                continue

            if kind == "Node":
                missing: list[str] = []
                raw_id = _strip_quotes(meta.get("id"))
                raw_kind = _strip_quotes(meta.get("kind"))
                summary = _strip_quotes(meta.get("summary"))
                io_value = _strip_quotes(meta.get("io"))

                if _value_missing(raw_id):
                    missing.append("id")
                elif not RELID_RE.match(raw_id or ""):
                    _emit_diag(
                        soft_diags,
                        "E_TOPO_RES_NODE_ID_INVALID",
                        "Node id must be RELID",
                        "UPPER_SNAKE_CASE",
                        raw_id or "",
                        json_pointer("nodes", str(node_index), "id"),
                    )
                if _value_missing(raw_kind):
                    missing.append("kind")
                if _value_missing(summary):
                    missing.append("summary")
                if _value_missing(io_value):
                    missing.append("io")

                if raw_id:
                    if raw_id in node_ids:
                        _emit_diag(
                            soft_diags,
                            "E_TOPO_RES_NODE_ID_DUPLICATE",
                            "Duplicate node id",
                            "unique id",
                            raw_id,
                            json_pointer("nodes", str(node_index), "id"),
                        )
                    node_ids.add(raw_id)

                if missing:
                    node_gaps.append(
                        GapItem(
                            kind="Node",
                            line=idx + 1,
                            ident=raw_id,
                            missing=sorted(missing),
                        )
                    )
                    for field in missing:
                        _emit_diag(
                            soft_diags,
                            "E_TOPO_RES_NODE_FIELD_MISSING",
                            "Node missing required field",
                            field,
                            "missing",
                            json_pointer("nodes", str(node_index), field),
                        )
                node_index += 1
                continue

            if kind != "Edge":
                continue

            missing: list[str] = []
            raw_id = _strip_quotes(meta.get("id"))
            raw_from = _strip_quotes(meta.get("from"))
            raw_to = _strip_quotes(meta.get("to"))
            raw_direction = _strip_quotes(meta.get("direction"))
            raw_channel = _strip_quotes(meta.get("channel"))
            raw_contract_refs = meta.get("contract_refs")

            if _value_missing(raw_from):
                missing.append("from")
            else:
                ref = parse_internal_ref(raw_from or "")
                if not ref or ref.kind != "Node":
                    _emit_diag(
                        soft_diags,
                        "E_TOPO_RES_EDGE_FROM_INVALID",
                        "Edge from must be @Node.<RELID>",
                        "@Node.<RELID>",
                        raw_from or "",
                        json_pointer("edges", str(edge_index), "from"),
                    )

            if _value_missing(raw_to):
                missing.append("to")
            else:
                ref = parse_internal_ref(raw_to or "")
                if not ref or ref.kind != "Node":
                    _emit_diag(
                        soft_diags,
                        "E_TOPO_RES_EDGE_TO_INVALID",
                        "Edge to must be @Node.<RELID>",
                        "@Node.<RELID>",
                        raw_to or "",
                        json_pointer("edges", str(edge_index), "to"),
                    )

            if _value_missing(raw_direction):
                missing.append("direction")
            elif raw_direction not in DIRECTION_VOCAB:
                _emit_diag(
                    soft_diags,
                    "E_TOPO_RES_EDGE_DIRECTION_INVALID",
                    "Edge direction invalid",
                    "pub|sub|req|rep|rw|call",
                    raw_direction or "",
                    json_pointer("edges", str(edge_index), "direction"),
                )

            if _value_missing(raw_channel):
                missing.append("channel")

            if raw_contract_refs is None:
                missing.append("contract_refs")
            else:
                items = _split_list_items(raw_contract_refs)
                if not items:
                    missing.append("contract_refs")
                else:
                    for idx_item, raw in enumerate(items):
                        item = raw.strip().strip('"')
                        if not parse_contract_ref(item):
                            _emit_diag(
                                soft_diags,
                                "E_TOPO_RES_CONTRACT_REFS_INVALID",
                                "contract_refs items must be CONTRACT.* tokens",
                                "CONTRACT.*",
                                item,
                                json_pointer("edges", str(edge_index), "contract_refs", str(idx_item)),
                            )

            if missing:
                edge_gaps.append(
                    GapItem(
                        kind="Edge",
                        line=idx + 1,
                        ident=raw_id,
                        missing=sorted(missing),
                        from_id=raw_from,
                        to_id=raw_to,
                        direction=raw_direction,
                    )
                )
                for field in missing:
                    _emit_diag(
                        soft_diags,
                        "E_TOPO_RES_EDGE_FIELD_MISSING",
                        "Edge missing required field",
                        field,
                        "missing",
                        json_pointer("edges", str(edge_index), field),
                    )
            edge_index += 1

        if node_gaps or edge_gaps:
            entry: dict[str, object] = {
                "path": rel_path,
                "stage": stage,
                "nodes": [],
                "edges": [],
            }
            if node_gaps:
                nodes_payload = []
                for gap in sorted(node_gaps, key=lambda g: (g.ident or "", g.line)):
                    nodes_payload.append(
                        {
                            "id": gap.ident,
                            "line": gap.line,
                            "missing": sorted(gap.missing),
                        }
                    )
                entry["nodes"] = nodes_payload
            if edge_gaps:
                edges_payload = []
                for gap in sorted(edge_gaps, key=lambda g: (g.ident or "", g.line)):
                    edges_payload.append(
                        {
                            "id": gap.ident,
                            "line": gap.line,
                            "from": gap.from_id,
                            "to": gap.to_id,
                            "direction": gap.direction,
                            "missing": sorted(gap.missing),
                        }
                    )
                entry["edges"] = edges_payload
            gaps.append(entry)

    return hard_diags, soft_diags, gaps
