#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from L2_builder.common import ROOT as REPO_ROOT, ensure_inside, has_symlink_parent, resolve_path
from sdslv2_builder.addendum_policy import load_addendum_policy
from sdslv2_builder.errors import Diagnostic, json_pointer
from sdslv2_builder.op_yaml import load_yaml

INPUT_HASH_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
TARGETS_ALLOWED = {"EVIDENCE-COVERAGE", "DRAFT-SCHEMA", "SCHEMA-MIGRATION"}
REASON_CODES = {"LEGACY_MIGRATION", "EXTERNAL_APPROVAL", "SCHEMA_SYNC"}
SCOPE_KINDS = {"file", "id_prefix", "component"}


def _diag(diags: list[Diagnostic], code: str, message: str, expected: str, got: str, path: str) -> None:
    diags.append(Diagnostic(code=code, message=message, expected=expected, got=got, path=path))


def _print_diags(diags: list[Diagnostic]) -> None:
    payload = [d.to_dict() for d in diags]
    print(json.dumps(payload, ensure_ascii=False, indent=2), file=sys.stderr)


def _parse_date(value: str) -> date | None:
    if not DATE_RE.match(value):
        return None
    try:
        y, m, d = value.split("-")
        return date(int(y), int(m), int(d))
    except ValueError:
        return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default="policy/exceptions.yaml", help="Exception file path.")
    ap.add_argument("--project-root", default=str(REPO_ROOT), help="Project root.")
    ap.add_argument("--policy-path", default=None, help="Explicit policy path.")
    ap.add_argument("--allow-nonstandard-path", action="store_true", help="Allow non-standard exception path.")
    ap.add_argument("--today", default=None, help="Override current date (YYYY-MM-DD).")
    args = ap.parse_args()

    project_root = Path(args.project_root).resolve()
    input_path = resolve_path(project_root, args.input)

    try:
        ensure_inside(project_root, input_path, "E_EXCEPTION_INPUT_OUTSIDE_PROJECT")
    except ValueError:
        print("E_EXCEPTION_INPUT_OUTSIDE_PROJECT", file=sys.stderr)
        return 2

    expected = (project_root / "policy" / "exceptions.yaml").resolve()
    if not args.allow_nonstandard_path and input_path != expected:
        print("E_EXCEPTION_PATH_INVALID", file=sys.stderr)
        return 2

    if not input_path.exists():
        return 0

    if has_symlink_parent(input_path, project_root) or input_path.is_symlink():
        print("E_EXCEPTION_SYMLINK", file=sys.stderr)
        return 2

    policy_path = Path(args.policy_path) if args.policy_path else None
    policy_result = load_addendum_policy(policy_path, project_root)

    diags: list[Diagnostic] = []
    diags.extend(policy_result.diagnostics)

    try:
        data = load_yaml(input_path)
    except Exception as exc:
        _diag(diags, "E_EXCEPTION_PARSE_FAILED", "exceptions.yaml parse failed", "valid YAML", str(exc), json_pointer())
        _print_diags(diags)
        return 2

    if not isinstance(data, dict):
        _diag(diags, "E_EXCEPTION_SCHEMA_INVALID", "root must be object", "object", type(data).__name__, json_pointer())
        _print_diags(diags)
        return 2

    required = {"schema_version", "source_rev", "input_hash", "exceptions"}
    for key in required:
        if key not in data:
            _diag(diags, "E_EXCEPTION_REQUIRED_MISSING", "missing required key", ",".join(sorted(required)), key, json_pointer(key))
    for key in data.keys():
        if key not in required:
            _diag(diags, "E_EXCEPTION_UNKNOWN_KEY", "unknown top-level key", ",".join(sorted(required)), key, json_pointer(key))

    schema_version = data.get("schema_version")
    if not isinstance(schema_version, str) or not schema_version.strip():
        _diag(diags, "E_EXCEPTION_SCHEMA_VERSION_INVALID", "schema_version must be non-empty string", "non-empty string", str(schema_version), json_pointer("schema_version"))

    source_rev = data.get("source_rev")
    if not isinstance(source_rev, str) or not source_rev.strip():
        _diag(diags, "E_EXCEPTION_SOURCE_REV_INVALID", "source_rev must be non-empty string", "non-empty string", str(source_rev), json_pointer("source_rev"))

    input_hash = data.get("input_hash")
    if not isinstance(input_hash, str) or not INPUT_HASH_RE.match(input_hash):
        _diag(diags, "E_EXCEPTION_INPUT_HASH_INVALID", "input_hash must be sha256:<64hex>", "sha256:<64hex>", str(input_hash), json_pointer("input_hash"))

    exceptions = data.get("exceptions")
    if not isinstance(exceptions, list):
        _diag(diags, "E_EXCEPTION_LIST_INVALID", "exceptions must be list", "list", type(exceptions).__name__, json_pointer("exceptions"))
        exceptions = []

    if args.today is None:
        print("E_EXCEPTION_TODAY_REQUIRED", file=sys.stderr)
        return 2
    today = _parse_date(args.today)
    if today is None:
        _diag(diags, "E_EXCEPTION_TODAY_INVALID", "--today must be YYYY-MM-DD", "YYYY-MM-DD", args.today, json_pointer("today"))

    seen_ids: set[str] = set()
    active_by_scope_target: set[tuple[str, str, str]] = set()
    active_by_scope: dict[tuple[str, str], int] = {}

    for idx, item in enumerate(exceptions):
        path = json_pointer("exceptions", str(idx))
        if not isinstance(item, dict):
            _diag(diags, "E_EXCEPTION_ITEM_INVALID", "exception entry must be object", "object", type(item).__name__, path)
            continue

        required_keys = [
            "id",
            "scope",
            "targets",
            "reason_code",
            "owner",
            "expires",
            "exit_criteria",
            "extend_count",
            "progress_note",
        ]
        for key in required_keys:
            if key not in item:
                _diag(diags, "E_EXCEPTION_REQUIRED_MISSING", "missing required key", ",".join(required_keys), key, f"{path}/{key}")

        exc_id = item.get("id")
        if not isinstance(exc_id, str) or not exc_id:
            _diag(diags, "E_EXCEPTION_ID_INVALID", "id must be non-empty string", "non-empty string", str(exc_id), f"{path}/id")
        else:
            if exc_id in seen_ids:
                _diag(diags, "E_EXCEPTION_ID_DUPLICATE", "id must be unique", "unique id", exc_id, f"{path}/id")
            seen_ids.add(exc_id)

        scope = item.get("scope")
        scope_kind = None
        scope_value = None
        if not isinstance(scope, dict):
            _diag(diags, "E_EXCEPTION_SCOPE_INVALID", "scope must be object", "object", type(scope).__name__, f"{path}/scope")
        else:
            scope_kind = scope.get("kind")
            scope_value = scope.get("value")
            if scope_kind not in SCOPE_KINDS:
                _diag(diags, "E_EXCEPTION_SCOPE_KIND_INVALID", "scope.kind invalid", "file|id_prefix|component", str(scope_kind), f"{path}/scope/kind")
            if not isinstance(scope_value, str) or not scope_value:
                _diag(diags, "E_EXCEPTION_SCOPE_VALUE_INVALID", "scope.value must be non-empty string", "non-empty string", str(scope_value), f"{path}/scope/value")
            elif scope_kind == "file" and not scope_value.endswith(".sdsl2"):
                _diag(diags, "E_EXCEPTION_SCOPE_VALUE_INVALID", "scope.value must be .sdsl2 path", "*.sdsl2", scope_value, f"{path}/scope/value")

        targets = item.get("targets")
        if not isinstance(targets, list) or not targets:
            _diag(diags, "E_EXCEPTION_TARGETS_INVALID", "targets must be non-empty list", "non-empty list", str(targets), f"{path}/targets")
            targets = []
        else:
            for t_idx, target in enumerate(targets):
                if target not in TARGETS_ALLOWED:
                    _diag(diags, "E_EXCEPTION_TARGET_INVALID", "invalid target", ",".join(sorted(TARGETS_ALLOWED)), str(target), f"{path}/targets/{t_idx}")

        reason = item.get("reason_code")
        if reason not in REASON_CODES:
            _diag(diags, "E_EXCEPTION_REASON_INVALID", "invalid reason_code", ",".join(sorted(REASON_CODES)), str(reason), f"{path}/reason_code")

        owner = item.get("owner")
        if not isinstance(owner, str) or not owner:
            _diag(diags, "E_EXCEPTION_OWNER_INVALID", "owner must be non-empty string", "non-empty string", str(owner), f"{path}/owner")

        expires = item.get("expires")
        expires_date = None
        if not isinstance(expires, str) or not expires:
            _diag(diags, "E_EXCEPTION_EXPIRES_INVALID", "expires must be YYYY-MM-DD", "YYYY-MM-DD", str(expires), f"{path}/expires")
        else:
            expires_date = _parse_date(expires)
            if not expires_date:
                _diag(diags, "E_EXCEPTION_EXPIRES_INVALID", "expires must be YYYY-MM-DD", "YYYY-MM-DD", expires, f"{path}/expires")

        exit_criteria = item.get("exit_criteria")
        if not isinstance(exit_criteria, str) or not exit_criteria:
            _diag(diags, "E_EXCEPTION_EXIT_CRITERIA_INVALID", "exit_criteria must be non-empty string", "non-empty string", str(exit_criteria), f"{path}/exit_criteria")

        extend_count = item.get("extend_count")
        if extend_count not in (0, 1):
            _diag(diags, "E_EXCEPTION_EXTEND_COUNT_INVALID", "extend_count must be 0 or 1", "0|1", str(extend_count), f"{path}/extend_count")

        progress_note = item.get("progress_note")
        if extend_count == 1:
            if not isinstance(progress_note, str) or not progress_note:
                _diag(diags, "E_EXCEPTION_PROGRESS_NOTE_REQUIRED", "progress_note required when extend_count=1", "non-empty string", str(progress_note), f"{path}/progress_note")
        elif extend_count == 0 and progress_note not in (None, ""):
            _diag(diags, "E_EXCEPTION_PROGRESS_NOTE_FORBIDDEN", "progress_note must be omitted when extend_count=0", "omit", str(progress_note), f"{path}/progress_note")

        is_active = expires_date is not None and today is not None and expires_date >= today
        if is_active and scope_kind and scope_value:
            for target in targets:
                key = (scope_kind, scope_value, target)
                if key in active_by_scope_target:
                    _diag(diags, "E_EXCEPTION_DUPLICATE_ACTIVE_TARGET", "only one active exception per scope+target", "unique", f"{scope_kind}:{scope_value}:{target}", f"{path}/targets")
                active_by_scope_target.add(key)
            scope_key = (scope_kind, scope_value)
            active_by_scope[scope_key] = active_by_scope.get(scope_key, 0) + 1

    cap = None
    scope_cap = None
    policy = policy_result.policy if policy_result.policy else {}
    cap = _get_nested(policy, ["dod", "l2_exception_cap"], None)
    scope_cap = _get_nested(policy, ["dod", "l2_exception_scope_cap"], None)

    if isinstance(cap, int) and cap >= 0:
        total_active = sum(active_by_scope.values())
        if total_active > cap:
            _diag(diags, "E_EXCEPTION_CAP_EXCEEDED", "active exceptions exceed cap", str(cap), str(total_active), json_pointer("exceptions"))
    if isinstance(scope_cap, int) and scope_cap >= 0:
        for scope_key, count in active_by_scope.items():
            if count > scope_cap:
                _diag(diags, "E_EXCEPTION_SCOPE_CAP_EXCEEDED", "active exceptions exceed scope cap", str(scope_cap), str(count), json_pointer("exceptions"))

    kept = diags
    failed = [d for d in diags if not d.code.startswith("ADD_POLICY_")]
    if kept:
        _print_diags(kept)
    return 2 if failed else 0


def _get_nested(data: dict, keys: list[str], default):
    cur = data
    for key in keys:
        if not isinstance(cur, dict) or key not in cur:
            return default
        cur = cur[key]
    return cur


if __name__ == "__main__":
    raise SystemExit(main())
