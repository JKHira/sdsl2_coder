#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sdslv2_builder.errors import Diagnostic, json_pointer
from sdslv2_builder.op_yaml import load_yaml
from sdslv2_builder.refs import (
    CONTRACT_TOKEN_RE,
    RELID_RE,
    SSOT_TOKEN_RE,
    parse_internal_ref,
)

PLACEHOLDERS = {"none", "tbd", "opaque"}


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
    return isinstance(value, str) and value.strip().lower() in PLACEHOLDERS


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


def _ensure_list(value: object, path: str, diags: list[Diagnostic]) -> list[object]:
    if isinstance(value, list):
        return value
    _diag(diags, "E_CONTRACT_DECISIONS_FIELD_TYPE", "Expected list", "list", type(value).__name__, path)
    return []


def _ensure_dict(value: object, path: str, diags: list[Diagnostic]) -> dict[str, object]:
    if isinstance(value, dict):
        return value
    _diag(diags, "E_CONTRACT_DECISIONS_FIELD_TYPE", "Expected object", "object", type(value).__name__, path)
    return {}


def _has_symlink_parent(path: Path, stop: Path) -> bool:
    for parent in [path, *path.parents]:
        if parent == stop:
            break
        if parent.is_symlink():
            return True
    return False


def _validate_scope(
    scope: dict,
    project_root: Path,
    diags: list[Diagnostic],
) -> dict[str, str]:
    kind = scope.get("kind")
    value = scope.get("value")
    if kind not in {"file", "id_prefix"}:
        _diag(
            diags,
            "E_CONTRACT_DECISIONS_SCOPE_INVALID",
            "scope.kind invalid",
            "file|id_prefix",
            str(kind),
            json_pointer("scope", "kind"),
        )
    if not isinstance(value, str) or not value.strip():
        _diag(
            diags,
            "E_CONTRACT_DECISIONS_SCOPE_INVALID",
            "scope.value must be non-empty string",
            "non-empty string",
            str(value),
            json_pointer("scope", "value"),
        )
        value = ""
    if _is_placeholder(kind) or _is_placeholder(value):
        _diag(
            diags,
            "E_CONTRACT_DECISIONS_PLACEHOLDER_FORBIDDEN",
            "Placeholders are forbidden in decisions",
            "no None/TBD/Opaque",
            str(value),
            json_pointer("scope"),
        )
    if kind == "file" and value:
        if value.startswith("/") or ".." in Path(value).parts:
            _diag(
                diags,
                "E_CONTRACT_DECISIONS_SCOPE_INVALID",
                "scope.value must be repo-relative path",
                "sdsl2/contract/*.sdsl2",
                value,
                json_pointer("scope", "value"),
            )
        full = (project_root / value).resolve()
        try:
            full.relative_to(project_root.resolve())
        except ValueError:
            _diag(
                diags,
                "E_CONTRACT_DECISIONS_SCOPE_INVALID",
                "scope.value outside project_root",
                "project_root/...",
                str(full),
                json_pointer("scope", "value"),
            )
        if full.is_symlink() or _has_symlink_parent(full, project_root):
            _diag(
                diags,
                "E_CONTRACT_DECISIONS_SCOPE_INVALID",
                "scope.value must not be symlink",
                "non-symlink",
                str(full),
                json_pointer("scope", "value"),
            )
        if not value.startswith("sdsl2/contract/") or not value.endswith(".sdsl2"):
            _diag(
                diags,
                "E_CONTRACT_DECISIONS_SCOPE_INVALID",
                "scope.value must be sdsl2/contract/*.sdsl2",
                "sdsl2/contract/*.sdsl2",
                value,
                json_pointer("scope", "value"),
            )
        if not full.exists():
            _diag(
                diags,
                "E_CONTRACT_DECISIONS_SCOPE_INVALID",
                "scope.value must exist",
                "existing file",
                str(full),
                json_pointer("scope", "value"),
            )
        elif not full.is_file():
            _diag(
                diags,
                "E_CONTRACT_DECISIONS_SCOPE_INVALID",
                "scope.value must be file",
                "file",
                str(full),
                json_pointer("scope", "value"),
            )
    if kind == "id_prefix" and value and not RELID_RE.match(value):
        _diag(
            diags,
            "E_CONTRACT_DECISIONS_SCOPE_INVALID",
            "scope.value must be RELID",
            "UPPER_SNAKE_CASE",
            value,
            json_pointer("scope", "value"),
        )
    return {"kind": str(kind or ""), "value": str(value or "")}


def parse_contract_decisions_file(
    path: Path,
    project_root: Path,
) -> tuple[dict[str, object] | None, list[Diagnostic]]:
    diags: list[Diagnostic] = []
    try:
        data = load_yaml(path)
    except Exception as exc:
        _diag(
            diags,
            "E_CONTRACT_DECISIONS_SCHEMA_INVALID",
            "decisions yaml parse failed",
            "valid YAML",
            str(exc),
            json_pointer(),
        )
        return None, diags
    if not isinstance(data, dict):
        _diag(
            diags,
            "E_CONTRACT_DECISIONS_SCHEMA_INVALID",
            "decisions root must be object",
            "object",
            type(data).__name__,
            json_pointer(),
        )
        return None, diags

    allowed_keys = {"schema_version", "provenance", "scope", "structures", "rules"}
    for key in data.keys():
        if key not in allowed_keys:
            _diag(
                diags,
                "E_CONTRACT_DECISIONS_UNKNOWN_FIELD",
                "Unknown top-level key",
                ",".join(sorted(allowed_keys)),
                key,
                json_pointer(key),
            )

    schema_version = data.get("schema_version")
    if not isinstance(schema_version, str) or not schema_version.strip():
        _diag(
            diags,
            "E_CONTRACT_DECISIONS_SCHEMA_INVALID",
            "schema_version must be non-empty string",
            "non-empty string",
            str(schema_version),
            json_pointer("schema_version"),
        )
    if _is_placeholder(schema_version):
        _diag(
            diags,
            "E_CONTRACT_DECISIONS_PLACEHOLDER_FORBIDDEN",
            "Placeholders are forbidden in decisions",
            "no None/TBD/Opaque",
            str(schema_version),
            json_pointer("schema_version"),
        )

    provenance = data.get("provenance")
    if not isinstance(provenance, dict):
        _diag(
            diags,
            "E_CONTRACT_DECISIONS_SCHEMA_INVALID",
            "provenance must be object",
            "object",
            type(provenance).__name__,
            json_pointer("provenance"),
        )
        provenance = {}
    allowed_prov = {"author", "reviewed_by", "source_link"}
    for key in provenance.keys():
        if key not in allowed_prov:
            _diag(
                diags,
                "E_CONTRACT_DECISIONS_UNKNOWN_FIELD",
                "Unknown provenance key",
                ",".join(sorted(allowed_prov)),
                key,
                json_pointer("provenance", key),
            )
    for key in sorted(allowed_prov):
        value = provenance.get(key)
        if not isinstance(value, str) or not value.strip():
            _diag(
                diags,
                "E_CONTRACT_DECISIONS_FIELD_INVALID",
                "provenance field must be non-empty string",
                "non-empty string",
                str(value),
                json_pointer("provenance", key),
            )
        if _is_placeholder(value):
            _diag(
                diags,
                "E_CONTRACT_DECISIONS_PLACEHOLDER_FORBIDDEN",
                "Placeholders are forbidden in decisions",
                "no None/TBD/Opaque",
                str(value),
                json_pointer("provenance", key),
            )

    scope_raw = data.get("scope")
    if not isinstance(scope_raw, dict):
        _diag(
            diags,
            "E_CONTRACT_DECISIONS_SCOPE_INVALID",
            "scope must be object",
            "object",
            type(scope_raw).__name__,
            json_pointer("scope"),
        )
        scope_raw = {}
    scope = _validate_scope(scope_raw, project_root, diags)

    structures_raw = _ensure_list(data.get("structures"), json_pointer("structures"), diags)
    structures: list[dict[str, str]] = []
    for idx, item in enumerate(structures_raw):
        obj = _ensure_dict(item, json_pointer("structures", str(idx)), diags)
        allowed_struct = {"id", "decl", "decl_lines"}
        for key in obj.keys():
            if key not in allowed_struct:
                _diag(
                    diags,
                    "E_CONTRACT_DECISIONS_UNKNOWN_FIELD",
                    "Unknown structure key",
                    ",".join(sorted(allowed_struct)),
                    key,
                    json_pointer("structures", str(idx), key),
                )
        rel_id = obj.get("id")
        decl = obj.get("decl")
        decl_lines = obj.get("decl_lines")
        if not isinstance(rel_id, str) or not RELID_RE.match(rel_id):
            _diag(
                diags,
                "E_CONTRACT_DECISIONS_FIELD_INVALID",
                "Structure id must be RELID",
                "UPPER_SNAKE_CASE",
                str(rel_id),
                json_pointer("structures", str(idx), "id"),
            )
            rel_id = ""
        if decl is not None and decl_lines is not None:
            _diag(
                diags,
                "E_CONTRACT_DECISIONS_FIELD_INVALID",
                "Provide either decl or decl_lines, not both",
                "decl|decl_lines",
                "both",
                json_pointer("structures", str(idx)),
            )
        if decl_lines is not None:
            lines = _ensure_list(decl_lines, json_pointer("structures", str(idx), "decl_lines"), diags)
            text_lines: list[str] = []
            for l_idx, line in enumerate(lines):
                value = None
                if isinstance(line, dict) and "line" in line:
                    value = line.get("line")
                elif isinstance(line, str):
                    value = line
                if not isinstance(value, str) or not value.strip():
                    _diag(
                        diags,
                        "E_CONTRACT_DECISIONS_FIELD_INVALID",
                        "decl_lines must be non-empty strings",
                        "non-empty string",
                        str(line),
                        json_pointer("structures", str(idx), "decl_lines", str(l_idx)),
                    )
                else:
                    text_lines.append(value)
            decl = "\n".join(text_lines)
        if not isinstance(decl, str) or not decl.strip():
            _diag(
                diags,
                "E_CONTRACT_DECISIONS_FIELD_INVALID",
                "Structure decl must be non-empty string",
                "non-empty string",
                str(decl),
                json_pointer("structures", str(idx), "decl"),
            )
            decl = ""
        if _is_placeholder(rel_id) or _is_placeholder(decl):
            _diag(
                diags,
                "E_CONTRACT_DECISIONS_PLACEHOLDER_FORBIDDEN",
                "Placeholders are forbidden in decisions",
                "no None/TBD/Opaque",
                str(rel_id or decl),
                json_pointer("structures", str(idx)),
            )
        structures.append({"id": rel_id, "decl": decl})
    structures_sorted = sorted(structures, key=lambda s: s.get("id", ""))
    if structures != structures_sorted:
        _diag(
            diags,
            "E_CONTRACT_DECISIONS_LIST_NOT_SORTED",
            "structures must be sorted by id",
            "sorted",
            "unsorted",
            json_pointer("structures"),
        )
    structure_ids = [s.get("id") for s in structures_sorted if s.get("id")]
    if len(structure_ids) != len(set(structure_ids)):
        _diag(
            diags,
            "E_CONTRACT_DECISIONS_DUPLICATE_ID",
            "Structure ids must be unique",
            "unique ids",
            "duplicate",
            json_pointer("structures"),
        )

    rules_raw = _ensure_list(data.get("rules"), json_pointer("rules"), diags)
    rules: list[dict[str, object]] = []
    for idx, item in enumerate(rules_raw):
        obj = _ensure_dict(item, json_pointer("rules", str(idx)), diags)
        allowed_rule = {"id", "bind", "refs", "contract", "ssot"}
        for key in obj.keys():
            if key not in allowed_rule:
                _diag(
                    diags,
                    "E_CONTRACT_DECISIONS_UNKNOWN_FIELD",
                    "Unknown rule key",
                    ",".join(sorted(allowed_rule)),
                    key,
                    json_pointer("rules", str(idx), key),
                )
        rel_id = obj.get("id")
        bind = obj.get("bind")
        if not isinstance(rel_id, str) or not RELID_RE.match(rel_id):
            _diag(
                diags,
                "E_CONTRACT_DECISIONS_FIELD_INVALID",
                "Rule id must be RELID",
                "UPPER_SNAKE_CASE",
                str(rel_id),
                json_pointer("rules", str(idx), "id"),
            )
            rel_id = ""
        if not isinstance(bind, str) or not parse_internal_ref(bind):
            _diag(
                diags,
                "E_CONTRACT_DECISIONS_FIELD_INVALID",
                "bind must be InternalRef",
                "@Kind.RELID",
                str(bind),
                json_pointer("rules", str(idx), "bind"),
            )
            bind = ""
        refs_raw = _ensure_list(obj.get("refs"), json_pointer("rules", str(idx), "refs"), diags)
        refs: list[str] = []
        for r_idx, ref in enumerate(refs_raw):
            if not isinstance(ref, str) or not parse_internal_ref(ref):
                _diag(
                    diags,
                    "E_CONTRACT_DECISIONS_FIELD_INVALID",
                    "refs must be InternalRef list",
                    "@Kind.RELID",
                    str(ref),
                    json_pointer("rules", str(idx), "refs", str(r_idx)),
                )
            else:
                refs.append(ref)
        refs_sorted = sorted(dict.fromkeys(refs))
        if refs != refs_sorted:
            _diag(
                diags,
                "E_CONTRACT_DECISIONS_LIST_NOT_SORTED",
                "refs must be sorted and deduped",
                "sorted",
                "unsorted",
                json_pointer("rules", str(idx), "refs"),
            )
        contract_raw = _ensure_list(
            obj.get("contract"),
            json_pointer("rules", str(idx), "contract"),
            diags,
        )
        contract: list[str] = []
        for c_idx, token in enumerate(contract_raw):
            if not isinstance(token, str) or not CONTRACT_TOKEN_RE.match(token):
                _diag(
                    diags,
                    "E_CONTRACT_DECISIONS_FIELD_INVALID",
                    "contract must be CONTRACT.* list",
                    "CONTRACT.*",
                    str(token),
                    json_pointer("rules", str(idx), "contract", str(c_idx)),
                )
            else:
                contract.append(token)
        contract_sorted = sorted(dict.fromkeys(contract))
        if contract != contract_sorted:
            _diag(
                diags,
                "E_CONTRACT_DECISIONS_LIST_NOT_SORTED",
                "contract must be sorted and deduped",
                "sorted",
                "unsorted",
                json_pointer("rules", str(idx), "contract"),
            )
        ssot_raw = _ensure_list(obj.get("ssot"), json_pointer("rules", str(idx), "ssot"), diags)
        ssot: list[str] = []
        for s_idx, token in enumerate(ssot_raw):
            if not isinstance(token, str) or not SSOT_TOKEN_RE.match(token):
                _diag(
                    diags,
                    "E_CONTRACT_DECISIONS_FIELD_INVALID",
                    "ssot must be SSOT.* list",
                    "SSOT.*",
                    str(token),
                    json_pointer("rules", str(idx), "ssot", str(s_idx)),
                )
            else:
                ssot.append(token)
        ssot_sorted = sorted(dict.fromkeys(ssot))
        if ssot != ssot_sorted:
            _diag(
                diags,
                "E_CONTRACT_DECISIONS_LIST_NOT_SORTED",
                "ssot must be sorted and deduped",
                "sorted",
                "unsorted",
                json_pointer("rules", str(idx), "ssot"),
            )
        if _is_placeholder(rel_id) or _is_placeholder(bind):
            _diag(
                diags,
                "E_CONTRACT_DECISIONS_PLACEHOLDER_FORBIDDEN",
                "Placeholders are forbidden in decisions",
                "no None/TBD/Opaque",
                str(rel_id or bind),
                json_pointer("rules", str(idx)),
            )
        rules.append(
            {
                "id": rel_id,
                "bind": bind,
                "refs": refs_sorted,
                "contract": contract_sorted,
                "ssot": ssot_sorted,
            }
        )
    rules_sorted = sorted(rules, key=lambda r: str(r.get("id", "")))
    if rules != rules_sorted:
        _diag(
            diags,
            "E_CONTRACT_DECISIONS_LIST_NOT_SORTED",
            "rules must be sorted by id",
            "sorted",
            "unsorted",
            json_pointer("rules"),
        )
    rule_ids = [r.get("id") for r in rules_sorted if r.get("id")]
    if len(rule_ids) != len(set(rule_ids)):
        _diag(
            diags,
            "E_CONTRACT_DECISIONS_DUPLICATE_ID",
            "Rule ids must be unique",
            "unique ids",
            "duplicate",
            json_pointer("rules"),
        )

    normalized = {
        "schema_version": schema_version,
        "provenance": provenance,
        "scope": scope,
        "structures": structures_sorted,
        "rules": rules_sorted,
    }
    return normalized, diags


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--input",
        default="decisions/contracts.yaml",
        help="decisions/contracts.yaml path",
    )
    ap.add_argument(
        "--allow-nonstandard-path",
        action="store_true",
        help="Allow decisions file outside decisions/contracts.yaml",
    )
    ap.add_argument(
        "--project-root",
        default=None,
        help="Project root (defaults to repo root); inputs can be relative to it",
    )
    args = ap.parse_args()

    project_root = Path(args.project_root).resolve() if args.project_root else ROOT
    path = _resolve_path(project_root, args.input)
    try:
        _ensure_inside(project_root, path, "E_CONTRACT_DECISIONS_INPUT_OUTSIDE_PROJECT")
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    if not path.exists():
        print("E_CONTRACT_DECISIONS_NOT_FOUND", file=sys.stderr)
        return 2
    if path.is_dir():
        print("E_CONTRACT_DECISIONS_IS_DIR", file=sys.stderr)
        return 2
    if path.is_symlink():
        print("E_CONTRACT_DECISIONS_SYMLINK", file=sys.stderr)
        return 2
    if not args.allow_nonstandard_path:
        expected = (project_root / "decisions" / "contracts.yaml").resolve()
        if path.resolve() != expected:
            print("E_CONTRACT_DECISIONS_NOT_STANDARD_PATH", file=sys.stderr)
            return 2

    _, diags = parse_contract_decisions_file(path, project_root)
    if diags:
        _print_diags(diags)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
