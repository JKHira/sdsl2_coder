from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

from sdslv2_builder.errors import Diagnostic, json_pointer
from sdslv2_builder.lint import _capture_metadata, _parse_metadata_pairs, _split_list_items, DIRECTION_VOCAB
from sdslv2_builder.refs import RELID_RE, parse_contract_ref, parse_internal_ref
from sdslv2_builder.op_yaml import load_yaml


@dataclass(frozen=True)
class GapItem:
    kind: str
    line: int
    ident: str | None
    missing: list[str]
    invalid_vocab: list[str]
    invalid_format: list[str]
    from_id: str | None = None
    to_id: str | None = None
    direction: str | None = None


PROFILE_REL_PATH = Path("policy") / "resolution_profile.yaml"
ANNOTATION_KIND_RE = re.compile(r"^\s*@(?P<kind>[A-Za-z_][A-Za-z0-9_]*)\b")


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


def _has_symlink_parent(path: Path, stop: Path) -> bool:
    for parent in [path, *path.parents]:
        if parent == stop:
            break
        if parent.is_symlink():
            return True
    return False


def _iter_annotations(lines: list[str]) -> list[tuple[str, dict[str, str] | None, int, int, list[str]]]:
    annotations: list[tuple[str, dict[str, str] | None, int, int, list[str]]] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.lstrip()
        if not stripped.startswith("@"):
            i += 1
            continue
        match = ANNOTATION_KIND_RE.match(stripped)
        if match:
            kind = match.group("kind")
        else:
            kind = stripped.split(None, 1)[0][1:]
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


def _read_vocab(
    value: object,
    diags: list[Diagnostic],
    path: str,
) -> set[str] | None:
    if value is None:
        return None
    if not isinstance(value, list) or not value or not all(isinstance(item, str) and item.strip() for item in value):
        _emit_diag(
            diags,
            "E_TOPO_RES_PROFILE_INVALID",
            "Profile vocab must be non-empty string list",
            "list[str]",
            str(value),
            path,
        )
        return None
    return {item.strip() for item in value}


def _read_required_fields(
    value: object,
    diags: list[Diagnostic],
    path: str,
    allowed: set[str],
) -> set[str] | None:
    if value is None:
        return None
    if not isinstance(value, list) or not value or not all(isinstance(item, str) and item.strip() for item in value):
        _emit_diag(
            diags,
            "E_TOPO_RES_PROFILE_INVALID",
            "Profile required_fields must be non-empty string list",
            "list[str]",
            str(value),
            path,
        )
        return None
    normalized = {item.strip() for item in value}
    invalid = sorted(field for field in normalized if field not in allowed)
    if invalid:
        _emit_diag(
            diags,
            "E_TOPO_RES_PROFILE_INVALID",
            "Profile required_fields contains unknown field",
            ",".join(sorted(allowed)),
            ",".join(invalid),
            path,
        )
        return None
    return normalized


def _read_pattern(
    value: object,
    diags: list[Diagnostic],
    path: str,
) -> re.Pattern[str] | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        _emit_diag(
            diags,
            "E_TOPO_RES_PROFILE_INVALID",
            "Profile pattern must be non-empty string",
            "string",
            str(value),
            path,
        )
        return None
    try:
        return re.compile(value)
    except re.error as exc:
        _emit_diag(
            diags,
            "E_TOPO_RES_PROFILE_INVALID",
            "Profile pattern invalid",
            "valid regex",
            str(exc),
            path,
        )
        return None


def _load_resolution_profile(project_root: Path, diags: list[Diagnostic]) -> dict[str, object] | None:
    path = project_root / PROFILE_REL_PATH
    if not path.exists():
        return None
    try:
        path.resolve().relative_to(project_root.resolve())
    except ValueError:
        _emit_diag(
            diags,
            "E_TOPO_RES_PROFILE_OUTSIDE_PROJECT",
            "Resolution profile must be under project_root",
            "project_root/...",
            str(path),
            json_pointer("profile"),
        )
        return None
    if path.is_symlink() or _has_symlink_parent(path, project_root):
        _emit_diag(
            diags,
            "E_TOPO_RES_PROFILE_SYMLINK",
            "Resolution profile must not be symlink",
            "non-symlink",
            str(path),
            json_pointer("profile"),
        )
        return None
    try:
        data = load_yaml(path)
    except Exception as exc:
        _emit_diag(
            diags,
            "E_TOPO_RES_PROFILE_PARSE_FAILED",
            "Resolution profile parse failed",
            "valid YAML",
            str(exc),
            json_pointer("profile"),
        )
        return None
    if not isinstance(data, dict):
        _emit_diag(
            diags,
            "E_TOPO_RES_PROFILE_INVALID",
            "Resolution profile must be object",
            "object",
            type(data).__name__,
            json_pointer("profile"),
        )
        return None
    return data


def _first_stmt_line(lines: list[str]) -> int | None:
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if stripped == "" or stripped.startswith("//"):
            continue
        return idx
    return None


def analyze_topology_files(
    project_root: Path,
    files: list[Path],
) -> tuple[list[Diagnostic], list[Diagnostic], list[dict]]:
    hard_diags: list[Diagnostic] = []
    soft_diags: list[Diagnostic] = []
    gaps: list[dict] = []

    profile = _load_resolution_profile(project_root, hard_diags)
    if hard_diags:
        return hard_diags, soft_diags, gaps

    node_kind_vocab: set[str] | None = None
    edge_channel_vocab: set[str] | None = None
    summary_max_len: int | None = None
    summary_pattern: re.Pattern[str] | None = None
    io_pattern: re.Pattern[str] | None = None
    node_required_fields = {"id", "kind", "summary", "io"}
    edge_required_fields = {"from", "to", "direction", "channel", "contract_refs"}
    if profile:
        node_cfg = profile.get("node")
        if isinstance(node_cfg, dict):
            node_kind_vocab = _read_vocab(node_cfg.get("kind_vocab"), hard_diags, json_pointer("profile", "node", "kind_vocab"))
            required_fields = _read_required_fields(
                node_cfg.get("required_fields"),
                hard_diags,
                json_pointer("profile", "node", "required_fields"),
                {"id", "kind", "summary", "io"},
            )
            if required_fields is not None:
                node_required_fields = required_fields
            summary_cfg = node_cfg.get("summary")
            if isinstance(summary_cfg, dict):
                max_len = summary_cfg.get("max_len")
                if max_len is not None:
                    if isinstance(max_len, int) and max_len > 0:
                        summary_max_len = max_len
                    else:
                        _emit_diag(
                            hard_diags,
                            "E_TOPO_RES_PROFILE_INVALID",
                            "summary.max_len must be positive int",
                            "positive int",
                            str(max_len),
                            json_pointer("profile", "node", "summary", "max_len"),
                        )
                summary_pattern = _read_pattern(
                    summary_cfg.get("pattern"),
                    hard_diags,
                    json_pointer("profile", "node", "summary", "pattern"),
                )
            io_cfg = node_cfg.get("io")
            if isinstance(io_cfg, dict):
                io_pattern = _read_pattern(io_cfg.get("pattern"), hard_diags, json_pointer("profile", "node", "io", "pattern"))
        edge_cfg = profile.get("edge")
        if isinstance(edge_cfg, dict):
            edge_channel_vocab = _read_vocab(edge_cfg.get("channel_vocab"), hard_diags, json_pointer("profile", "edge", "channel_vocab"))
            required_fields = _read_required_fields(
                edge_cfg.get("required_fields"),
                hard_diags,
                json_pointer("profile", "edge", "required_fields"),
                {"from", "to", "direction", "channel", "contract_refs"},
            )
            if required_fields is not None:
                edge_required_fields = required_fields

    if hard_diags:
        return hard_diags, soft_diags, gaps

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
        first_stmt = _first_stmt_line(lines)

        profile = None
        stage = None
        file_headers: list[tuple[dict[str, str], int]] = []
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

        for kind, meta, idx, _, _ in annotations:
            if kind != "File":
                continue
            if meta is None:
                continue
            file_headers.append((meta, idx))

        if len(file_headers) > 1:
            _emit_diag(
                hard_diags,
                "E_TOPO_RES_FILE_HEADER_DUPLICATE",
                "Duplicate @File headers",
                "single @File",
                ",".join(str(item[1] + 1) for item in file_headers),
                json_pointer("file_header"),
            )
            continue
        if file_headers:
            file_meta, _ = file_headers[0]
            if first_stmt is not None and file_headers[0][1] != first_stmt:
                _emit_diag(
                    hard_diags,
                    "E_TOPO_RES_FILE_HEADER_NOT_FIRST",
                    "@File must be the first non-comment statement",
                    "first statement is @File",
                    str(file_headers[0][1] + 1),
                    json_pointer("file_header"),
                )
                continue
            profile = _strip_quotes(file_meta.get("profile"))
            stage = _strip_quotes(file_meta.get("stage"))

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
        edge_entries: list[dict[str, object]] = []
        edge_ids: set[str] = set()
        edges_for_node_check: list[tuple[int, str | None, str | None]] = []

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
                invalid_vocab: set[str] = set()
                invalid_format: set[str] = set()
                raw_id = _strip_quotes(meta.get("id"))
                raw_kind = _strip_quotes(meta.get("kind"))
                summary = _strip_quotes(meta.get("summary"))
                io_value = _strip_quotes(meta.get("io"))

                if _value_missing(raw_id):
                    if "id" in node_required_fields:
                        missing.append("id")
                elif not RELID_RE.match(raw_id or ""):
                    invalid_format.add("id")
                    _emit_diag(
                        soft_diags,
                        "E_TOPO_RES_NODE_ID_INVALID",
                        "Node id must be RELID",
                        "UPPER_SNAKE_CASE",
                        raw_id or "",
                        json_pointer("nodes", str(node_index), "id"),
                    )
                if _value_missing(raw_kind):
                    if "kind" in node_required_fields:
                        missing.append("kind")
                elif node_kind_vocab and raw_kind not in node_kind_vocab:
                    invalid_vocab.add("kind")
                    _emit_diag(
                        soft_diags,
                        "E_TOPO_RES_NODE_KIND_INVALID",
                        "Node kind not in vocab",
                        "vocab",
                        raw_kind or "",
                        json_pointer("nodes", str(node_index), "kind"),
                    )
                if _value_missing(summary):
                    if "summary" in node_required_fields:
                        missing.append("summary")
                else:
                    if summary_max_len is not None and summary is not None and len(summary) > summary_max_len:
                        invalid_format.add("summary")
                        _emit_diag(
                            soft_diags,
                            "E_TOPO_RES_NODE_SUMMARY_TOO_LONG",
                            "Node summary exceeds max length",
                            str(summary_max_len),
                            str(len(summary)),
                            json_pointer("nodes", str(node_index), "summary"),
                        )
                    if summary_pattern is not None and summary is not None and not summary_pattern.match(summary):
                        invalid_format.add("summary")
                        _emit_diag(
                            soft_diags,
                            "E_TOPO_RES_NODE_SUMMARY_FORMAT_INVALID",
                            "Node summary format invalid",
                            "pattern match",
                            summary,
                            json_pointer("nodes", str(node_index), "summary"),
                        )
                if _value_missing(io_value):
                    if "io" in node_required_fields:
                        missing.append("io")
                else:
                    if io_pattern is not None and io_value is not None and not io_pattern.match(io_value):
                        invalid_format.add("io")
                        _emit_diag(
                            soft_diags,
                            "E_TOPO_RES_NODE_IO_FORMAT_INVALID",
                            "Node io format invalid",
                            "pattern match",
                            io_value,
                            json_pointer("nodes", str(node_index), "io"),
                        )

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

                missing_fields = sorted(set(missing))
                if missing_fields:
                    for field in missing_fields:
                        _emit_diag(
                            soft_diags,
                            "E_TOPO_RES_NODE_FIELD_MISSING",
                            "Node missing required field",
                            field,
                            "missing",
                            json_pointer("nodes", str(node_index), field),
                        )
                if missing_fields or invalid_vocab or invalid_format:
                    node_gaps.append(
                        GapItem(
                            kind="Node",
                            line=idx + 1,
                            ident=raw_id,
                            missing=missing_fields,
                            invalid_vocab=sorted(invalid_vocab),
                            invalid_format=sorted(invalid_format),
                        )
                    )
                node_index += 1
                continue

            if kind != "Edge":
                continue

            missing: list[str] = []
            invalid_vocab: set[str] = set()
            invalid_format: set[str] = set()
            raw_id = _strip_quotes(meta.get("id"))
            raw_from = _strip_quotes(meta.get("from"))
            raw_to = _strip_quotes(meta.get("to"))
            raw_direction = _strip_quotes(meta.get("direction"))
            raw_channel = _strip_quotes(meta.get("channel"))
            raw_contract_refs = meta.get("contract_refs")
            from_ref = None
            to_ref = None

            if not _value_missing(raw_id):
                if raw_id in edge_ids:
                    _emit_diag(
                        soft_diags,
                        "E_TOPO_RES_EDGE_ID_DUPLICATE",
                        "Duplicate edge id",
                        "unique id",
                        raw_id,
                        json_pointer("edges", str(edge_index), "id"),
                    )
                edge_ids.add(raw_id)

            if _value_missing(raw_from):
                if "from" in edge_required_fields:
                    missing.append("from")
            else:
                from_ref = parse_internal_ref(raw_from or "")
                if not from_ref or from_ref.kind != "Node":
                    invalid_format.add("from")
                    _emit_diag(
                        soft_diags,
                        "E_TOPO_RES_EDGE_FROM_INVALID",
                        "Edge from must be @Node.RELID",
                        "@Node.RELID",
                        raw_from or "",
                        json_pointer("edges", str(edge_index), "from"),
                    )

            if _value_missing(raw_to):
                if "to" in edge_required_fields:
                    missing.append("to")
            else:
                to_ref = parse_internal_ref(raw_to or "")
                if not to_ref or to_ref.kind != "Node":
                    invalid_format.add("to")
                    _emit_diag(
                        soft_diags,
                        "E_TOPO_RES_EDGE_TO_INVALID",
                        "Edge to must be @Node.RELID",
                        "@Node.RELID",
                        raw_to or "",
                        json_pointer("edges", str(edge_index), "to"),
                    )

            if _value_missing(raw_direction):
                if "direction" in edge_required_fields:
                    missing.append("direction")
            elif raw_direction not in DIRECTION_VOCAB:
                invalid_vocab.add("direction")
                _emit_diag(
                    soft_diags,
                    "E_TOPO_RES_EDGE_DIRECTION_INVALID",
                    "Edge direction invalid",
                    "pub|sub|req|rep|rw|call",
                    raw_direction or "",
                    json_pointer("edges", str(edge_index), "direction"),
                )

            if _value_missing(raw_channel):
                if "channel" in edge_required_fields:
                    missing.append("channel")
            elif edge_channel_vocab and raw_channel not in edge_channel_vocab:
                invalid_vocab.add("channel")
                _emit_diag(
                    soft_diags,
                    "E_TOPO_RES_EDGE_CHANNEL_INVALID",
                    "Edge channel not in vocab",
                    "vocab",
                    raw_channel or "",
                    json_pointer("edges", str(edge_index), "channel"),
                )

            if raw_contract_refs is None:
                if "contract_refs" in edge_required_fields:
                    missing.append("contract_refs")
            else:
                raw_contract_refs = raw_contract_refs.strip()
                if not (raw_contract_refs.startswith("[") and raw_contract_refs.endswith("]")):
                    invalid_format.add("contract_refs")
                items = _split_list_items(raw_contract_refs)
                if not items:
                    if "contract_refs" in edge_required_fields and "contract_refs" not in invalid_format:
                        missing.append("contract_refs")
                else:
                    for idx_item, raw in enumerate(items):
                        item = raw.strip().strip('"')
                        if not parse_contract_ref(item):
                            invalid_format.add("contract_refs")
                            _emit_diag(
                                soft_diags,
                                "E_TOPO_RES_CONTRACT_REFS_INVALID",
                                "contract_refs items must be CONTRACT.* tokens",
                                "CONTRACT.*",
                                item,
                                json_pointer("edges", str(edge_index), "contract_refs", str(idx_item)),
                            )

            missing_fields = sorted(set(missing))
            if missing_fields:
                for field in missing_fields:
                    _emit_diag(
                        soft_diags,
                        "E_TOPO_RES_EDGE_FIELD_MISSING",
                        "Edge missing required field",
                        field,
                        "missing",
                        json_pointer("edges", str(edge_index), field),
                    )
            edge_entries.append(
                {
                    "id": raw_id,
                    "line": idx + 1,
                    "from": raw_from,
                    "to": raw_to,
                    "direction": raw_direction,
                    "missing": missing_fields,
                    "invalid_vocab": invalid_vocab,
                    "invalid_format": invalid_format,
                }
            )
            edge_index += 1
            edges_for_node_check.append(
                (
                    edge_index - 1,
                    from_ref.rel_id if from_ref else None,
                    to_ref.rel_id if to_ref else None,
                )
            )

        for edge_idx, from_id, to_id in edges_for_node_check:
            if from_id and from_id not in node_ids:
                entry = edge_entries[edge_idx]
                invalid_format = entry["invalid_format"]
                if isinstance(invalid_format, set):
                    invalid_format.add("from")
                _emit_diag(
                    soft_diags,
                    "E_TOPO_RES_EDGE_FROM_UNKNOWN",
                    "Edge from refers to unknown Node",
                    "existing @Node.RELID",
                    from_id,
                    json_pointer("edges", str(edge_idx), "from"),
                )
            if to_id and to_id not in node_ids:
                entry = edge_entries[edge_idx]
                invalid_format = entry["invalid_format"]
                if isinstance(invalid_format, set):
                    invalid_format.add("to")
                _emit_diag(
                    soft_diags,
                    "E_TOPO_RES_EDGE_TO_UNKNOWN",
                    "Edge to refers to unknown Node",
                    "existing @Node.RELID",
                    to_id,
                    json_pointer("edges", str(edge_idx), "to"),
                )

        edge_gaps: list[GapItem] = []
        for entry in edge_entries:
            missing_fields = entry["missing"]
            invalid_vocab = entry["invalid_vocab"]
            invalid_format = entry["invalid_format"]
            if not isinstance(missing_fields, list):
                continue
            invalid_vocab_fields = sorted(invalid_vocab) if isinstance(invalid_vocab, set) else []
            invalid_format_fields = sorted(invalid_format) if isinstance(invalid_format, set) else []
            if missing_fields or invalid_vocab_fields or invalid_format_fields:
                edge_gaps.append(
                    GapItem(
                        kind="Edge",
                        line=int(entry["line"]),
                        ident=entry["id"] if isinstance(entry["id"], str) else None,
                        missing=missing_fields,
                        invalid_vocab=invalid_vocab_fields,
                        invalid_format=invalid_format_fields,
                        from_id=entry["from"] if isinstance(entry["from"], str) else None,
                        to_id=entry["to"] if isinstance(entry["to"], str) else None,
                        direction=entry["direction"] if isinstance(entry["direction"], str) else None,
                    )
                )

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
                    payload = {
                        "id": gap.ident,
                        "line": gap.line,
                        "missing": gap.missing,
                    }
                    if gap.invalid_vocab:
                        payload["invalid_vocab"] = gap.invalid_vocab
                    if gap.invalid_format:
                        payload["invalid_format"] = gap.invalid_format
                    nodes_payload.append(payload)
                entry["nodes"] = nodes_payload
            if edge_gaps:
                edges_payload = []
                for gap in sorted(edge_gaps, key=lambda g: (g.ident or "", g.line)):
                    payload = {
                        "id": gap.ident,
                        "line": gap.line,
                        "from": gap.from_id,
                        "to": gap.to_id,
                        "direction": gap.direction,
                        "missing": gap.missing,
                    }
                    if gap.invalid_vocab:
                        payload["invalid_vocab"] = gap.invalid_vocab
                    if gap.invalid_format:
                        payload["invalid_format"] = gap.invalid_format
                    edges_payload.append(payload)
                entry["edges"] = edges_payload
            gaps.append(entry)

    return hard_diags, soft_diags, gaps
