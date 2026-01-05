#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from L1_builder.decisions_lint import parse_decisions_file
from sdslv2_builder.errors import Diagnostic, json_pointer
from sdslv2_builder.op_yaml import load_yaml
from sdslv2_builder.refs import CONTRACT_TOKEN_RE

PLACEHOLDERS = {"None", "TBD", "Opaque"}
LOCATOR_RE = re.compile(r"^L\d+-L\d+$|^H:[^#]+#L\d+-L\d+$")
CONTENT_HASH_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
ALLOWED_PREFIXES = ("design/", "docs/", "specs/", "src/", "policy/attestations/")


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


def _is_placeholder(value: object) -> bool:
    return isinstance(value, str) and value in PLACEHOLDERS


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


def validate_evidence_data(
    data: object,
    decisions: dict[str, object],
    project_root: Path,
) -> tuple[dict[str, object] | None, list[Diagnostic]]:
    diags: list[Diagnostic] = []
    if not isinstance(data, dict):
        _diag(
            diags,
            "E_EVIDENCE_SCHEMA_INVALID",
            "evidence root must be object",
            "object",
            type(data).__name__,
            json_pointer(),
        )
        return None, diags

    allowed_keys = {"schema_version", "source_rev", "input_hash", "scope", "evidence"}
    for key in data.keys():
        if key not in allowed_keys:
            _diag(
                diags,
                "E_EVIDENCE_UNKNOWN_FIELD",
                "Unknown top-level key",
                ",".join(sorted(allowed_keys)),
                key,
                json_pointer(key),
            )

    schema_version = data.get("schema_version")
    if not isinstance(schema_version, str) or not schema_version.strip():
        _diag(
            diags,
            "E_EVIDENCE_SCHEMA_INVALID",
            "schema_version must be non-empty string",
            "non-empty string",
            str(schema_version),
            json_pointer("schema_version"),
        )
    if _is_placeholder(schema_version):
        _diag(
            diags,
            "E_EVIDENCE_PLACEHOLDER_FORBIDDEN",
            "Placeholders are forbidden in evidence",
            "no None/TBD/Opaque",
            str(schema_version),
            json_pointer("schema_version"),
        )

    source_rev = data.get("source_rev")
    if not isinstance(source_rev, str) or not source_rev.strip():
        _diag(
            diags,
            "E_EVIDENCE_FIELD_INVALID",
            "source_rev must be non-empty string",
            "non-empty string",
            str(source_rev),
            json_pointer("source_rev"),
        )
    if _is_placeholder(source_rev):
        _diag(
            diags,
            "E_EVIDENCE_PLACEHOLDER_FORBIDDEN",
            "Placeholders are forbidden in evidence",
            "no None/TBD/Opaque",
            str(source_rev),
            json_pointer("source_rev"),
        )

    input_hash = data.get("input_hash")
    if not isinstance(input_hash, str) or not input_hash.startswith("sha256:"):
        _diag(
            diags,
            "E_EVIDENCE_FIELD_INVALID",
            "input_hash must start with sha256:",
            "sha256:<hex>",
            str(input_hash),
            json_pointer("input_hash"),
        )
    if _is_placeholder(input_hash):
        _diag(
            diags,
            "E_EVIDENCE_PLACEHOLDER_FORBIDDEN",
            "Placeholders are forbidden in evidence",
            "no None/TBD/Opaque",
            str(input_hash),
            json_pointer("input_hash"),
        )

    scope = data.get("scope")
    if not isinstance(scope, dict):
        _diag(
            diags,
            "E_EVIDENCE_SCHEMA_INVALID",
            "scope must be object",
            "object",
            type(scope).__name__,
            json_pointer("scope"),
        )
        scope = {}
    decision_scope = decisions.get("scope", {})
    if scope != decision_scope:
        _diag(
            diags,
            "E_EVIDENCE_SCOPE_MISMATCH",
            "Evidence scope must match decisions scope",
            "decisions scope",
            json.dumps(decision_scope, ensure_ascii=False),
            json_pointer("scope"),
        )

    evidence = data.get("evidence")
    if not isinstance(evidence, dict):
        _diag(
            diags,
            "E_EVIDENCE_SCHEMA_INVALID",
            "evidence must be object",
            "object",
            type(evidence).__name__,
            json_pointer("evidence"),
        )
        evidence = {}
    keys_in_order = list(evidence.keys())
    if keys_in_order != sorted(keys_in_order):
        _diag(
            diags,
            "E_EVIDENCE_LIST_NOT_SORTED",
            "evidence keys must be sorted lexically",
            "sorted keys",
            "unsorted",
            json_pointer("evidence"),
        )

    decision_edges = decisions.get("edges", [])
    decision_ids = {edge["id"] for edge in decision_edges if isinstance(edge, dict)}

    for key in evidence.keys():
        if key not in decision_ids:
            _diag(
                diags,
                "E_EVIDENCE_DECISION_UNKNOWN",
                "decision_id missing from decisions",
                "known decision id",
                key,
                json_pointer("evidence", key),
            )

    for decision_id, items in evidence.items():
        if not isinstance(items, list):
            _diag(
                diags,
                "E_EVIDENCE_SCHEMA_INVALID",
                "Evidence list must be list",
                "list",
                type(items).__name__,
                json_pointer("evidence", str(decision_id)),
            )
            continue
        seen_items: set[tuple[object, ...]] = set()
        order_keys: list[tuple[object, ...]] = []
        for idx, item in enumerate(items):
            if not isinstance(item, dict):
                _diag(
                    diags,
                    "E_EVIDENCE_SCHEMA_INVALID",
                    "Evidence item must be object",
                    "object",
                    type(item).__name__,
                    json_pointer("evidence", str(decision_id), str(idx)),
                )
                continue
            allowed_item = {"source_path", "locator", "content_hash", "note", "claims"}
            for key in item.keys():
                if key not in allowed_item:
                    _diag(
                        diags,
                        "E_EVIDENCE_UNKNOWN_FIELD",
                        "Unknown evidence item key",
                        ",".join(sorted(allowed_item)),
                        key,
                        json_pointer("evidence", str(decision_id), str(idx), key),
                    )

            source_path = item.get("source_path")
            if not isinstance(source_path, str) or not source_path.strip():
                _diag(
                    diags,
                    "E_EVIDENCE_FIELD_INVALID",
                    "source_path must be non-empty string",
                    "non-empty string",
                    str(source_path),
                    json_pointer("evidence", str(decision_id), str(idx), "source_path"),
                )
            if _is_placeholder(source_path):
                _diag(
                    diags,
                    "E_EVIDENCE_PLACEHOLDER_FORBIDDEN",
                    "Placeholders are forbidden in evidence",
                    "no None/TBD/Opaque",
                    str(source_path),
                    json_pointer("evidence", str(decision_id), str(idx), "source_path"),
                )
            if isinstance(source_path, str):
                if source_path.startswith("/") or ".." in Path(source_path).parts:
                    _diag(
                        diags,
                        "E_EVIDENCE_FIELD_INVALID",
                        "source_path must be repo-relative",
                        "design/|docs/|specs/|src/|policy/attestations/",
                        source_path,
                        json_pointer("evidence", str(decision_id), str(idx), "source_path"),
                    )
                if not source_path.startswith(ALLOWED_PREFIXES):
                    _diag(
                        diags,
                        "E_EVIDENCE_FIELD_INVALID",
                        "source_path must start with allowed prefix",
                        "|".join(ALLOWED_PREFIXES),
                        source_path,
                        json_pointer("evidence", str(decision_id), str(idx), "source_path"),
                    )
                if source_path.startswith(("drafts/", "OUTPUT/", "sdsl2/", "decisions/")):
                    _diag(
                        diags,
                        "E_EVIDENCE_FIELD_INVALID",
                        "source_path forbidden root",
                        "design/|docs/|specs/|src/|policy/attestations/",
                        source_path,
                        json_pointer("evidence", str(decision_id), str(idx), "source_path"),
                    )
                full = (project_root / source_path).resolve()
                try:
                    full.relative_to(project_root.resolve())
                except ValueError:
                    _diag(
                        diags,
                        "E_EVIDENCE_FIELD_INVALID",
                        "source_path outside project_root",
                        "project_root/...",
                        str(full),
                        json_pointer("evidence", str(decision_id), str(idx), "source_path"),
                    )

            locator = item.get("locator")
            if not isinstance(locator, str) or not LOCATOR_RE.match(locator):
                _diag(
                    diags,
                    "E_EVIDENCE_FIELD_INVALID",
                    "locator invalid",
                    "L<start>-L<end> or H:<heading>#L<start>-L<end>",
                    str(locator),
                    json_pointer("evidence", str(decision_id), str(idx), "locator"),
                )
            if _is_placeholder(locator):
                _diag(
                    diags,
                    "E_EVIDENCE_PLACEHOLDER_FORBIDDEN",
                    "Placeholders are forbidden in evidence",
                    "no None/TBD/Opaque",
                    str(locator),
                    json_pointer("evidence", str(decision_id), str(idx), "locator"),
                )

            content_hash = item.get("content_hash")
            if not isinstance(content_hash, str) or not CONTENT_HASH_RE.match(content_hash):
                _diag(
                    diags,
                    "E_EVIDENCE_FIELD_INVALID",
                    "content_hash invalid",
                    "sha256:<hex>",
                    str(content_hash),
                    json_pointer("evidence", str(decision_id), str(idx), "content_hash"),
                )
            if _is_placeholder(content_hash):
                _diag(
                    diags,
                    "E_EVIDENCE_PLACEHOLDER_FORBIDDEN",
                    "Placeholders are forbidden in evidence",
                    "no None/TBD/Opaque",
                    str(content_hash),
                    json_pointer("evidence", str(decision_id), str(idx), "content_hash"),
                )

            note = item.get("note")
            if note is not None and not isinstance(note, str):
                _diag(
                    diags,
                    "E_EVIDENCE_FIELD_INVALID",
                    "note must be string",
                    "string",
                    str(note),
                    json_pointer("evidence", str(decision_id), str(idx), "note"),
                )
            if _is_placeholder(note):
                _diag(
                    diags,
                    "E_EVIDENCE_PLACEHOLDER_FORBIDDEN",
                    "Placeholders are forbidden in evidence",
                    "no None/TBD/Opaque",
                    str(note),
                    json_pointer("evidence", str(decision_id), str(idx), "note"),
                )

            claims = item.get("claims")
            if not isinstance(claims, list) or not claims:
                _diag(
                    diags,
                    "E_EVIDENCE_FIELD_INVALID",
                    "claims must be non-empty list",
                    "non-empty list",
                    str(claims),
                    json_pointer("evidence", str(decision_id), str(idx), "claims"),
                )
                claims = []
            claim_keys = []
            for cidx, claim in enumerate(claims):
                if not isinstance(claim, dict):
                    _diag(
                        diags,
                        "E_EVIDENCE_FIELD_INVALID",
                        "claim must be object",
                        "object",
                        type(claim).__name__,
                        json_pointer("evidence", str(decision_id), str(idx), "claims", str(cidx)),
                    )
                    continue
                allowed_claim = {"kind", "decision_id", "value"}
                for key in claim.keys():
                    if key not in allowed_claim:
                        _diag(
                            diags,
                            "E_EVIDENCE_UNKNOWN_FIELD",
                            "Unknown claim key",
                            ",".join(sorted(allowed_claim)),
                            key,
                            json_pointer("evidence", str(decision_id), str(idx), "claims", str(cidx), key),
                        )
                kind = claim.get("kind")
                if kind not in {"edge", "contract_ref"}:
                    _diag(
                        diags,
                        "E_EVIDENCE_FIELD_INVALID",
                        "claim.kind invalid",
                        "edge|contract_ref",
                        str(kind),
                        json_pointer("evidence", str(decision_id), str(idx), "claims", str(cidx), "kind"),
                    )
                decision_id_val = claim.get("decision_id")
                if not isinstance(decision_id_val, str) or decision_id_val != decision_id:
                    _diag(
                        diags,
                        "E_EVIDENCE_FIELD_INVALID",
                        "claim.decision_id must match evidence key",
                        decision_id,
                        str(decision_id_val),
                        json_pointer("evidence", str(decision_id), str(idx), "claims", str(cidx), "decision_id"),
                    )
                value = claim.get("value")
                if kind == "contract_ref":
                    if not isinstance(value, str) or not CONTRACT_TOKEN_RE.match(value):
                        _diag(
                            diags,
                            "E_EVIDENCE_FIELD_INVALID",
                            "claim.value must be CONTRACT.*",
                            "CONTRACT.*",
                            str(value),
                            json_pointer("evidence", str(decision_id), str(idx), "claims", str(cidx), "value"),
                        )
                else:
                    if value is not None:
                        _diag(
                            diags,
                            "E_EVIDENCE_FIELD_INVALID",
                            "claim.value must be omitted for edge",
                            "omitted",
                            str(value),
                            json_pointer("evidence", str(decision_id), str(idx), "claims", str(cidx), "value"),
                        )
                if _is_placeholder(value):
                    _diag(
                        diags,
                        "E_EVIDENCE_PLACEHOLDER_FORBIDDEN",
                        "Placeholders are forbidden in evidence",
                        "no None/TBD/Opaque",
                        str(value),
                        json_pointer("evidence", str(decision_id), str(idx), "claims", str(cidx), "value"),
                    )
                kind_order = 0 if kind == "edge" else 1
                claim_keys.append((kind_order, str(decision_id_val or ""), str(value or "")))
            if claim_keys and claim_keys != sorted(claim_keys):
                _diag(
                    diags,
                    "E_EVIDENCE_LIST_NOT_SORTED",
                    "claims must be ordered by (kind,decision_id,value)",
                    "stable order",
                    "unsorted",
                    json_pointer("evidence", str(decision_id), str(idx), "claims"),
                )

            item_key = (
                str(source_path or ""),
                str(locator or ""),
                str(content_hash or ""),
                str(note or ""),
                tuple(claim_keys),
            )
            if item_key in seen_items:
                _diag(
                    diags,
                    "E_EVIDENCE_DUPLICATE_ITEM",
                    "Duplicate evidence item",
                    "unique item",
                    "duplicate",
                    json_pointer("evidence", str(decision_id), str(idx)),
                )
            seen_items.add(item_key)
            order_keys.append(item_key)
        if order_keys and order_keys != sorted(order_keys):
            _diag(
                diags,
                "E_EVIDENCE_LIST_NOT_SORTED",
                "Evidence items must be stable-ordered",
                "stable order",
                "unsorted",
                json_pointer("evidence", str(decision_id)),
            )

    return data, diags


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
        _ensure_inside(project_root, decisions_path, "E_EVIDENCE_INPUT_OUTSIDE_PROJECT")
        _ensure_inside(project_root, evidence_path, "E_EVIDENCE_INPUT_OUTSIDE_PROJECT")
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    if not decisions_path.exists():
        print("E_EVIDENCE_DECISIONS_NOT_FOUND", file=sys.stderr)
        return 2
    if decisions_path.exists() and decisions_path.is_dir():
        print("E_EVIDENCE_DECISIONS_IS_DIR", file=sys.stderr)
        return 2
    if decisions_path.is_symlink():
        print("E_EVIDENCE_DECISIONS_SYMLINK", file=sys.stderr)
        return 2
    if not args.allow_nonstandard_path:
        expected_decisions = (project_root / "decisions" / "edges.yaml").resolve()
        if decisions_path.resolve() != expected_decisions:
            print("E_EVIDENCE_DECISIONS_NOT_STANDARD_PATH", file=sys.stderr)
            return 2

    decisions, decision_diags = parse_decisions_file(decisions_path, project_root)
    if decision_diags:
        _print_diags(decision_diags)
        return 2

    if not evidence_path.exists():
        print("E_EVIDENCE_INPUT_NOT_FOUND", file=sys.stderr)
        return 2
    if evidence_path.exists() and evidence_path.is_dir():
        print("E_EVIDENCE_INPUT_IS_DIR", file=sys.stderr)
        return 2
    if evidence_path.is_symlink():
        print("E_EVIDENCE_INPUT_SYMLINK", file=sys.stderr)
        return 2
    if not args.allow_nonstandard_path:
        expected_evidence = (project_root / "decisions" / "evidence.yaml").resolve()
        if evidence_path.resolve() != expected_evidence:
            print("E_EVIDENCE_INPUT_NOT_STANDARD_PATH", file=sys.stderr)
            return 2

    data = load_yaml(evidence_path)
    _, diags = validate_evidence_data(data, decisions, project_root)
    if diags:
        _print_diags(diags)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
