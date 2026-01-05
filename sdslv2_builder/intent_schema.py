from __future__ import annotations

import re
from typing import Any

from .errors import Diagnostic, json_pointer
from .lint import DIRECTION_VOCAB
from .refs import RELID_RE

SCHEMA_VERSION_RE = re.compile(r"^\d+\.\d+$")
PLACEHOLDERS = {"None", "TBD", "Opaque"}

REQUIRED_TOP_KEYS = [
    "schema_version",
    "source_rev",
    "input_hash",
    "generator_id",
    "scope",
    "nodes_proposed",
    "edge_intents_proposed",
    "questions",
    "conflicts",
]


def _diag(
    diags: list[Diagnostic],
    code: str,
    message: str,
    expected: str,
    got: str,
    path: str,
) -> None:
    diags.append(
        Diagnostic(code=code, message=message, expected=expected, got=got, path=path)
    )


def _check_placeholder(value: Any, path: str, diags: list[Diagnostic]) -> None:
    if isinstance(value, str) and value in PLACEHOLDERS:
        _diag(
            diags,
            "E_INTENT_PLACEHOLDER_FORBIDDEN",
            "Placeholders are forbidden in Intent YAML",
            "no None/TBD/Opaque",
            value,
            path,
        )


def _ensure_dict(value: Any, path: str, diags: list[Diagnostic]) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    _diag(diags, "E_INTENT_FIELD_TYPE", "Expected object", "object", type(value).__name__, path)
    return {}


def _ensure_list(value: Any, path: str, diags: list[Diagnostic]) -> list[Any]:
    if isinstance(value, list):
        return value
    _diag(diags, "E_INTENT_FIELD_TYPE", "Expected list", "list", type(value).__name__, path)
    return []


def normalize_intent(
    data: dict[str, Any],
    fill_missing: bool,
) -> tuple[dict[str, Any], list[Diagnostic]]:
    diags: list[Diagnostic] = []
    if not isinstance(data, dict):
        _diag(
            diags,
            "E_INTENT_SCHEMA_INVALID",
            "Intent root must be object",
            "object",
            type(data).__name__,
            json_pointer(),
        )
        return {}, diags

    normalized: dict[str, Any] = {}

    for key in data.keys():
        if key not in REQUIRED_TOP_KEYS:
            _diag(
                diags,
                "E_INTENT_UNKNOWN_FIELD",
                "Unknown intent top-level key",
                ",".join(REQUIRED_TOP_KEYS),
                key,
                json_pointer(key),
            )

    for key in REQUIRED_TOP_KEYS:
        if key not in data:
            if fill_missing:
                if key in {"nodes_proposed", "edge_intents_proposed", "questions", "conflicts"}:
                    normalized[key] = []
                    continue
                normalized[key] = ""
                continue
            _diag(
                diags,
                "E_INTENT_REQUIRED_FIELD_MISSING",
                "Missing required key",
                "present",
                "missing",
                json_pointer(key),
            )

    schema_version = data.get("schema_version", "")
    if not isinstance(schema_version, str) or not SCHEMA_VERSION_RE.match(schema_version):
        _diag(
            diags,
            "E_INTENT_SCHEMA_INVALID",
            "Invalid schema_version",
            "MAJOR.MINOR",
            str(schema_version),
            json_pointer("schema_version"),
        )
    _check_placeholder(schema_version, json_pointer("schema_version"), diags)
    normalized["schema_version"] = schema_version

    source_rev = data.get("source_rev", "")
    if not isinstance(source_rev, str) or not source_rev.strip():
        _diag(
            diags,
            "E_INTENT_FIELD_INVALID",
            "source_rev must be non-empty",
            "non-empty string",
            str(source_rev),
            json_pointer("source_rev"),
        )
    _check_placeholder(source_rev, json_pointer("source_rev"), diags)
    normalized["source_rev"] = source_rev

    input_hash = data.get("input_hash", "")
    if not isinstance(input_hash, str) or not input_hash.startswith("sha256:"):
        _diag(
            diags,
            "E_INTENT_FIELD_INVALID",
            "input_hash must start with sha256:",
            "sha256:<hex>",
            str(input_hash),
            json_pointer("input_hash"),
        )
    _check_placeholder(input_hash, json_pointer("input_hash"), diags)
    normalized["input_hash"] = input_hash

    generator_id = data.get("generator_id", "")
    if not isinstance(generator_id, str) or not generator_id.strip():
        _diag(
            diags,
            "E_INTENT_FIELD_INVALID",
            "generator_id must be non-empty",
            "non-empty string",
            str(generator_id),
            json_pointer("generator_id"),
        )
    _check_placeholder(generator_id, json_pointer("generator_id"), diags)
    normalized["generator_id"] = generator_id

    scope = _ensure_dict(data.get("scope"), json_pointer("scope"), diags)
    scope_kind = scope.get("kind")
    scope_value = scope.get("value")
    if scope_kind not in {"file", "id_prefix", "component"}:
        _diag(
            diags,
            "E_INTENT_FIELD_INVALID",
            "scope.kind invalid",
            "file|id_prefix|component",
            str(scope_kind),
            json_pointer("scope", "kind"),
        )
    if not isinstance(scope_value, str) or not scope_value.strip():
        _diag(
            diags,
            "E_INTENT_FIELD_INVALID",
            "scope.value must be non-empty",
            "non-empty string",
            str(scope_value),
            json_pointer("scope", "value"),
        )
    _check_placeholder(scope_kind, json_pointer("scope", "kind"), diags)
    _check_placeholder(scope_value, json_pointer("scope", "value"), diags)
    normalized["scope"] = {"kind": scope_kind or "", "value": scope_value or ""}

    nodes_raw = _ensure_list(data.get("nodes_proposed"), json_pointer("nodes_proposed"), diags)
    nodes: list[dict[str, Any]] = []
    for idx, node in enumerate(nodes_raw):
        node_obj = _ensure_dict(node, json_pointer("nodes_proposed", str(idx)), diags)
        rel_id = node_obj.get("id")
        if not isinstance(rel_id, str) or not RELID_RE.match(rel_id):
            _diag(
                diags,
                "E_INTENT_FIELD_INVALID",
                "Node id must be RELID",
                "UPPER_SNAKE_CASE",
                str(rel_id),
                json_pointer("nodes_proposed", str(idx), "id"),
            )
            rel_id = ""
        _check_placeholder(rel_id, json_pointer("nodes_proposed", str(idx), "id"), diags)
        item = {"id": rel_id}
        kind = node_obj.get("kind")
        if kind is not None:
            if not isinstance(kind, str) or not kind.strip():
                _diag(
                    diags,
                    "E_INTENT_FIELD_INVALID",
                    "Node kind must be string",
                    "string",
                    str(kind),
                    json_pointer("nodes_proposed", str(idx), "kind"),
                )
            _check_placeholder(kind, json_pointer("nodes_proposed", str(idx), "kind"), diags)
            item["kind"] = kind
        nodes.append(item)
    nodes_sorted = sorted(nodes, key=lambda n: n.get("id", ""))
    if nodes != nodes_sorted:
        _diag(
            diags,
            "E_INTENT_LIST_NOT_SORTED",
            "nodes_proposed must be sorted by id",
            "sorted",
            "unsorted",
            json_pointer("nodes_proposed"),
        )
    normalized["nodes_proposed"] = nodes_sorted

    intents_raw = _ensure_list(
        data.get("edge_intents_proposed"),
        json_pointer("edge_intents_proposed"),
        diags,
    )
    intents: list[dict[str, Any]] = []
    for idx, intent in enumerate(intents_raw):
        intent_obj = _ensure_dict(intent, json_pointer("edge_intents_proposed", str(idx)), diags)
        rel_id = intent_obj.get("id")
        from_id = intent_obj.get("from")
        to_id = intent_obj.get("to")
        for field, value in [("id", rel_id), ("from", from_id), ("to", to_id)]:
            if not isinstance(value, str) or not RELID_RE.match(value):
                _diag(
                    diags,
                    "E_INTENT_FIELD_INVALID",
                    f"{field} must be RELID",
                    "UPPER_SNAKE_CASE",
                    str(value),
                    json_pointer("edge_intents_proposed", str(idx), field),
                )
        item = {"id": rel_id or "", "from": from_id or "", "to": to_id or ""}
        direction = intent_obj.get("direction")
        if direction is not None:
            if direction not in DIRECTION_VOCAB:
                _diag(
                    diags,
                    "E_INTENT_FIELD_INVALID",
                    "direction invalid",
                    ",".join(sorted(DIRECTION_VOCAB)),
                    str(direction),
                    json_pointer("edge_intents_proposed", str(idx), "direction"),
                )
            item["direction"] = direction
        channel = intent_obj.get("channel")
        if channel is not None:
            if not isinstance(channel, str):
                _diag(
                    diags,
                    "E_INTENT_FIELD_INVALID",
                    "channel must be string",
                    "string",
                    str(channel),
                    json_pointer("edge_intents_proposed", str(idx), "channel"),
                )
            item["channel"] = channel
        note = intent_obj.get("note")
        if note is not None:
            if not isinstance(note, str):
                _diag(
                    diags,
                    "E_INTENT_FIELD_INVALID",
                    "note must be string",
                    "string",
                    str(note),
                    json_pointer("edge_intents_proposed", str(idx), "note"),
                )
            item["note"] = note
        intents.append(item)
    intents_sorted = sorted(intents, key=lambda i: i.get("id", ""))
    if intents != intents_sorted:
        _diag(
            diags,
            "E_INTENT_LIST_NOT_SORTED",
            "edge_intents_proposed must be sorted by id",
            "sorted",
            "unsorted",
            json_pointer("edge_intents_proposed"),
        )
    normalized["edge_intents_proposed"] = intents_sorted

    intent_ids: list[str] = [intent.get("id", "") for intent in intents_sorted]
    if len(intent_ids) != len(set(intent_ids)):
        _diag(
            diags,
            "E_INTENT_DUPLICATE_ID",
            "edge_intents_proposed.id must be unique",
            "unique ids",
            "duplicate",
            json_pointer("edge_intents_proposed"),
        )

    questions_raw = _ensure_list(data.get("questions"), json_pointer("questions"), diags)
    questions = [q for q in questions_raw if isinstance(q, str)]
    for idx, q in enumerate(questions_raw):
        if not isinstance(q, str):
            _diag(
                diags,
                "E_INTENT_FIELD_INVALID",
                "question must be string",
                "string",
                str(q),
                json_pointer("questions", str(idx)),
            )
        _check_placeholder(q, json_pointer("questions", str(idx)), diags)
    questions_sorted = sorted(questions)
    if questions != questions_sorted:
        _diag(
            diags,
            "E_INTENT_LIST_NOT_SORTED",
            "questions must be sorted",
            "sorted",
            "unsorted",
            json_pointer("questions"),
        )
    normalized["questions"] = questions_sorted

    conflicts_raw = _ensure_list(data.get("conflicts"), json_pointer("conflicts"), diags)
    conflicts = [c for c in conflicts_raw if isinstance(c, str)]
    for idx, c in enumerate(conflicts_raw):
        if not isinstance(c, str):
            _diag(
                diags,
                "E_INTENT_FIELD_INVALID",
                "conflict must be string",
                "string",
                str(c),
                json_pointer("conflicts", str(idx)),
            )
        _check_placeholder(c, json_pointer("conflicts", str(idx)), diags)
    conflicts_sorted = sorted(conflicts)
    if conflicts != conflicts_sorted:
        _diag(
            diags,
            "E_INTENT_LIST_NOT_SORTED",
            "conflicts must be sorted",
            "sorted",
            "unsorted",
            json_pointer("conflicts"),
        )
    normalized["conflicts"] = conflicts_sorted

    return normalized, diags
