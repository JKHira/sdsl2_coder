#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from L1_builder.decisions_lint import parse_decisions_file
from L1_builder.evidence_lint import validate_evidence_data
from sdslv2_builder.errors import Diagnostic, json_pointer
from sdslv2_builder.lint import DIRECTION_VOCAB
from sdslv2_builder.op_yaml import load_yaml
from sdslv2_builder.refs import CONTRACT_TOKEN_RE, RELID_RE

PLACEHOLDERS = {"None", "TBD", "Opaque"}


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


def _is_placeholder(value: object) -> bool:
    return isinstance(value, str) and value in PLACEHOLDERS


def _has_symlink_parent(path: Path, stop: Path) -> bool:
    for parent in [path, *path.parents]:
        if parent == stop:
            break
        if parent.is_symlink():
            return True
    return False


def _load_intent_files(project_root: Path) -> tuple[list[dict], list[Diagnostic]]:
    diags: list[Diagnostic] = []
    intent_root = project_root / "drafts" / "intent"
    if not intent_root.exists():
        _diag(
            diags,
            "E_READINESS_INTENT_MISSING",
            "drafts/intent/ not found",
            "drafts/intent/ with intent files",
            "missing",
            json_pointer(),
        )
        return [], diags
    if _has_symlink_parent(intent_root, project_root):
        _diag(
            diags,
            "E_READINESS_INTENT_SYMLINK",
            "drafts/intent must not be under symlinked parent",
            "non-symlink parents",
            str(intent_root),
            json_pointer(),
        )
        return [], diags
    if intent_root.is_symlink():
        _diag(
            diags,
            "E_READINESS_INTENT_SYMLINK",
            "drafts/intent/ must not be symlink",
            "non-symlink",
            "symlink",
            json_pointer(),
        )
        return [], diags

    intents: list[dict] = []
    root_resolved = intent_root.resolve()
    for path in sorted(intent_root.glob("*.yaml")):
        if not path.is_file():
            continue
        if path.is_symlink():
            _diag(
                diags,
                "E_READINESS_INTENT_SYMLINK",
                "Intent YAML must not be symlink",
                "non-symlink",
                str(path),
                json_pointer(),
            )
            continue
        if _has_symlink_parent(path, intent_root):
            _diag(
                diags,
                "E_READINESS_INTENT_SYMLINK",
                "Intent YAML parent must not be symlink",
                "non-symlink",
                str(path),
                json_pointer(),
            )
            continue
        try:
            resolved = path.resolve()
            resolved.relative_to(root_resolved)
        except ValueError:
            _diag(
                diags,
                "E_READINESS_INTENT_OUTSIDE_ROOT",
                "Intent YAML must be under drafts/intent",
                str(root_resolved),
                str(path),
                json_pointer(),
            )
            continue
        data = load_yaml(path)
        if not isinstance(data, dict):
            _diag(
                diags,
                "E_READINESS_INTENT_INVALID",
                "Intent YAML must be object",
                "object",
                type(data).__name__,
                json_pointer(),
            )
            continue
        intents.append({"path": path, "data": data})
    if not intents:
        _diag(
            diags,
            "E_READINESS_INTENT_MISSING",
            "No Intent YAML files found",
            "drafts/intent/*.yaml",
            "empty",
            json_pointer(),
        )
    return intents, diags


def _validate_intent_data(data: dict, path: Path) -> tuple[dict[str, object], list[Diagnostic]]:
    diags: list[Diagnostic] = []
    allowed_keys = {
        "schema_version",
        "source_rev",
        "input_hash",
        "generator_id",
        "scope",
        "nodes_proposed",
        "edge_intents_proposed",
        "questions",
        "conflicts",
    }
    for key in data.keys():
        if key not in allowed_keys:
            _diag(
                diags,
                "E_READINESS_INTENT_INVALID",
                "Unknown intent top-level key",
                ",".join(sorted(allowed_keys)),
                key,
                json_pointer(key),
            )

    required = {"schema_version", "source_rev", "input_hash", "generator_id", "scope", "edge_intents_proposed"}
    for key in required:
        if key not in data:
            _diag(
                diags,
                "E_READINESS_INTENT_INVALID",
                "Missing required intent key",
                "present",
                "missing",
                json_pointer(key),
            )

    schema_version = data.get("schema_version")
    if not isinstance(schema_version, str) or not schema_version.strip():
        _diag(
            diags,
            "E_READINESS_INTENT_INVALID",
            "schema_version must be non-empty string",
            "non-empty string",
            str(schema_version),
            json_pointer("schema_version"),
        )
    if _is_placeholder(schema_version):
        _diag(
            diags,
            "E_READINESS_INTENT_INVALID",
            "Placeholders are forbidden in intent",
            "no None/TBD/Opaque",
            str(schema_version),
            json_pointer("schema_version"),
        )

    source_rev = data.get("source_rev")
    if not isinstance(source_rev, str) or not source_rev.strip():
        _diag(
            diags,
            "E_READINESS_INTENT_INVALID",
            "source_rev must be non-empty string",
            "non-empty string",
            str(source_rev),
            json_pointer("source_rev"),
        )
    if _is_placeholder(source_rev):
        _diag(
            diags,
            "E_READINESS_INTENT_INVALID",
            "Placeholders are forbidden in intent",
            "no None/TBD/Opaque",
            str(source_rev),
            json_pointer("source_rev"),
        )

    input_hash = data.get("input_hash")
    if not isinstance(input_hash, str) or not input_hash.startswith("sha256:"):
        _diag(
            diags,
            "E_READINESS_INTENT_INVALID",
            "input_hash must start with sha256:",
            "sha256:<hex>",
            str(input_hash),
            json_pointer("input_hash"),
        )
    if _is_placeholder(input_hash):
        _diag(
            diags,
            "E_READINESS_INTENT_INVALID",
            "Placeholders are forbidden in intent",
            "no None/TBD/Opaque",
            str(input_hash),
            json_pointer("input_hash"),
        )

    generator_id = data.get("generator_id")
    if not isinstance(generator_id, str) or not generator_id.strip():
        _diag(
            diags,
            "E_READINESS_INTENT_INVALID",
            "generator_id must be non-empty string",
            "non-empty string",
            str(generator_id),
            json_pointer("generator_id"),
        )
    if _is_placeholder(generator_id):
        _diag(
            diags,
            "E_READINESS_INTENT_INVALID",
            "Placeholders are forbidden in intent",
            "no None/TBD/Opaque",
            str(generator_id),
            json_pointer("generator_id"),
        )

    scope = data.get("scope")
    if not isinstance(scope, dict):
        _diag(
            diags,
            "E_READINESS_INTENT_INVALID",
            "scope must be object",
            "object",
            type(scope).__name__,
            json_pointer("scope"),
        )
        scope = {}
    scope_kind = scope.get("kind")
    scope_value = scope.get("value")
    if scope_kind not in {"file", "id_prefix", "component"}:
        _diag(
            diags,
            "E_READINESS_INTENT_INVALID",
            "scope.kind invalid",
            "file|id_prefix|component",
            str(scope_kind),
            json_pointer("scope", "kind"),
        )
    if not isinstance(scope_value, str) or not scope_value.strip():
        _diag(
            diags,
            "E_READINESS_INTENT_INVALID",
            "scope.value must be non-empty string",
            "non-empty string",
            str(scope_value),
            json_pointer("scope", "value"),
        )
    if _is_placeholder(scope_kind) or _is_placeholder(scope_value):
        _diag(
            diags,
            "E_READINESS_INTENT_INVALID",
            "Placeholders are forbidden in intent",
            "no None/TBD/Opaque",
            str(scope_value),
            json_pointer("scope"),
        )

    intents_raw = data.get("edge_intents_proposed")
    if not isinstance(intents_raw, list):
        _diag(
            diags,
            "E_READINESS_INTENT_INVALID",
            "edge_intents_proposed must be list",
            "list",
            type(intents_raw).__name__,
            json_pointer("edge_intents_proposed"),
        )
        intents_raw = []
    intents: list[dict[str, object]] = []
    ids: list[str] = []
    for idx, intent in enumerate(intents_raw):
        if not isinstance(intent, dict):
            _diag(
                diags,
                "E_READINESS_INTENT_INVALID",
                "edge_intent must be object",
                "object",
                type(intent).__name__,
                json_pointer("edge_intents_proposed", str(idx)),
            )
            continue
        allowed = {"id", "from", "to", "direction", "channel", "note"}
        for key in intent.keys():
            if key not in allowed:
                _diag(
                    diags,
                    "E_READINESS_INTENT_INVALID",
                    "Unknown edge_intent key",
                    ",".join(sorted(allowed)),
                    key,
                    json_pointer("edge_intents_proposed", str(idx), key),
                )
        rel_id = intent.get("id")
        from_id = intent.get("from")
        to_id = intent.get("to")
        if not isinstance(rel_id, str) or not RELID_RE.match(rel_id):
            _diag(
                diags,
                "E_READINESS_INTENT_INVALID",
                "id must be RELID",
                "UPPER_SNAKE_CASE",
                str(rel_id),
                json_pointer("edge_intents_proposed", str(idx), "id"),
            )
            rel_id = ""
        if not isinstance(from_id, str) or not RELID_RE.match(from_id):
            _diag(
                diags,
                "E_READINESS_INTENT_INVALID",
                "from must be RELID",
                "UPPER_SNAKE_CASE",
                str(from_id),
                json_pointer("edge_intents_proposed", str(idx), "from"),
            )
            from_id = ""
        if not isinstance(to_id, str) or not RELID_RE.match(to_id):
            _diag(
                diags,
                "E_READINESS_INTENT_INVALID",
                "to must be RELID",
                "UPPER_SNAKE_CASE",
                str(to_id),
                json_pointer("edge_intents_proposed", str(idx), "to"),
            )
            to_id = ""
        direction = intent.get("direction")
        if direction is not None and direction not in DIRECTION_VOCAB:
            _diag(
                diags,
                "E_READINESS_INTENT_INVALID",
                "direction invalid",
                ",".join(sorted(DIRECTION_VOCAB)),
                str(direction),
                json_pointer("edge_intents_proposed", str(idx), "direction"),
            )
        if _is_placeholder(rel_id) or _is_placeholder(from_id) or _is_placeholder(to_id):
            _diag(
                diags,
                "E_READINESS_INTENT_INVALID",
                "Placeholders are forbidden in intent",
                "no None/TBD/Opaque",
                str(rel_id),
                json_pointer("edge_intents_proposed", str(idx)),
            )
        if rel_id:
            ids.append(rel_id)
        intents.append(
            {
                "id": rel_id,
                "from": from_id,
                "to": to_id,
                "direction": direction,
            }
        )

    if ids and ids != sorted(ids):
        _diag(
            diags,
            "E_READINESS_INTENT_INVALID",
            "edge_intents_proposed must be sorted by id",
            "sorted by id",
            "unsorted",
            json_pointer("edge_intents_proposed"),
        )
    if len(ids) != len(set(ids)):
        _diag(
            diags,
            "E_READINESS_INTENT_DUPLICATE_ID",
            "Intent ids must be unique within file",
            "unique",
            "duplicate",
            json_pointer("edge_intents_proposed"),
        )

    return {"scope": {"kind": scope_kind, "value": scope_value}, "intents": intents}, diags


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--decisions-path",
        default="decisions/edges.yaml",
        help="decisions/edges.yaml path",
    )
    ap.add_argument(
        "--evidence-path",
        default="decisions/evidence.yaml",
        help="decisions/evidence.yaml path",
    )
    ap.add_argument(
        "--allow-nonstandard-path",
        action="store_true",
        help="Allow decisions/evidence outside standard paths",
    )
    ap.add_argument(
        "--project-root",
        default=None,
        help="Project root (defaults to repo root); inputs can be relative to it",
    )
    args = ap.parse_args()

    project_root = Path(args.project_root).resolve() if args.project_root else ROOT
    decisions_path = _resolve_path(project_root, args.decisions_path)
    evidence_path = _resolve_path(project_root, args.evidence_path)
    try:
        _ensure_inside(project_root, decisions_path, "E_READINESS_INPUT_OUTSIDE_PROJECT")
        _ensure_inside(project_root, evidence_path, "E_READINESS_INPUT_OUTSIDE_PROJECT")
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    if not decisions_path.exists():
        print("E_READINESS_DECISIONS_NOT_FOUND", file=sys.stderr)
        return 2
    if decisions_path.exists() and decisions_path.is_dir():
        print("E_READINESS_DECISIONS_IS_DIR", file=sys.stderr)
        return 2
    if decisions_path.is_symlink():
        print("E_READINESS_DECISIONS_SYMLINK", file=sys.stderr)
        return 2
    if not args.allow_nonstandard_path:
        expected_decisions = (project_root / "decisions" / "edges.yaml").resolve()
        if decisions_path.resolve() != expected_decisions:
            print("E_READINESS_DECISIONS_NOT_STANDARD_PATH", file=sys.stderr)
            return 2

    decisions, decision_diags = parse_decisions_file(decisions_path, project_root)
    if decision_diags:
        _print_diags(decision_diags)
        return 2

    if not evidence_path.exists():
        print("E_READINESS_EVIDENCE_NOT_FOUND", file=sys.stderr)
        return 2
    if evidence_path.exists() and evidence_path.is_dir():
        print("E_READINESS_EVIDENCE_IS_DIR", file=sys.stderr)
        return 2
    if evidence_path.is_symlink():
        print("E_READINESS_EVIDENCE_SYMLINK", file=sys.stderr)
        return 2
    if not args.allow_nonstandard_path:
        expected_evidence = (project_root / "decisions" / "evidence.yaml").resolve()
        if evidence_path.resolve() != expected_evidence:
            print("E_READINESS_EVIDENCE_NOT_STANDARD_PATH", file=sys.stderr)
            return 2

    evidence_data = load_yaml(evidence_path)
    _, evidence_diags = validate_evidence_data(evidence_data, decisions, project_root)
    if evidence_diags:
        _print_diags(evidence_diags)
        return 2

    intents_files, intent_root_diags = _load_intent_files(project_root)
    if intent_root_diags:
        _print_diags(intent_root_diags)
        return 2

    decisions_scope = decisions.get("scope", {})
    decisions_edges = decisions.get("edges", [])
    decision_by_id = {
        edge["id"]: edge for edge in decisions_edges if isinstance(edge, dict)
    }

    intents_by_scope_id: dict[tuple[str, str, str], dict[str, object]] = {}
    for entry in intents_files:
        path = entry["path"]
        data = entry["data"]
        intent, diags = _validate_intent_data(data, path)
        if diags:
            _print_diags(diags)
            return 2
        scope = intent.get("scope", {})
        if scope != decisions_scope:
            continue
        for item in intent.get("intents", []):
            intent_id = item.get("id")
            scope_key = (
                scope.get("kind", ""),
                scope.get("value", ""),
                str(intent_id),
            )
            if scope_key in intents_by_scope_id:
                _print_diags([
                    Diagnostic(
                        code="E_READINESS_INTENT_DUPLICATE_ID",
                        message="Duplicate Intent id across drafts/intent",
                        expected="unique per scope",
                        got=str(intent_id),
                        path=json_pointer("edge_intents_proposed"),
                    )
                ])
                return 2
            intents_by_scope_id[scope_key] = item

    diags: list[Diagnostic] = []

    evidence_map = evidence_data.get("evidence", {}) if isinstance(evidence_data, dict) else {}
    for decision_id, edge in decision_by_id.items():
        scope_key = (
            decisions_scope.get("kind", ""),
            decisions_scope.get("value", ""),
            decision_id,
        )
        intent = intents_by_scope_id.get(scope_key)
        if not intent:
            _diag(
                diags,
                "E_READINESS_INTENT_MISSING",
                "Intent entry missing for decision",
                "matching intent",
                decision_id,
                json_pointer("edge_intents_proposed"),
            )
        else:
            if intent.get("from") != edge.get("from") or intent.get("to") != edge.get("to"):
                _diag(
                    diags,
                    "E_READINESS_INTENT_MISMATCH",
                    "Intent from/to mismatch with decision",
                    "matching from/to",
                    f"{intent.get('from')}->{intent.get('to')}",
                    json_pointer("edge_intents_proposed"),
                )

        evidence_items = evidence_map.get(decision_id, [])
        if not evidence_items:
            _diag(
                diags,
                "E_READINESS_EVIDENCE_MISSING",
                "Evidence missing for decision",
                "evidence items",
                decision_id,
                json_pointer("evidence", str(decision_id)),
            )
            continue
        contract_refs = edge.get("contract_refs", [])
        claims = []
        for item in evidence_items:
            if isinstance(item, dict):
                for claim in item.get("claims", []):
                    if isinstance(claim, dict):
                        claims.append(claim)
        for ref in contract_refs:
            if not CONTRACT_TOKEN_RE.match(str(ref)):
                continue
            matched = any(
                isinstance(c, dict)
                and c.get("kind") == "contract_ref"
                and c.get("decision_id") == decision_id
                and c.get("value") == ref
                for c in claims
            )
            if not matched:
                _diag(
                    diags,
                    "E_READINESS_EVIDENCE_COVERAGE",
                    "Missing contract_ref evidence",
                    "evidence claim for contract_ref",
                    str(ref),
                    json_pointer("evidence", str(decision_id)),
                )

    if diags:
        _print_diags(diags)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
