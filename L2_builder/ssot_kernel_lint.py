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

from L2_builder.common import ROOT as REPO_ROOT, ensure_inside, has_symlink_parent, resolve_path
from sdslv2_builder.errors import Diagnostic, json_pointer

DEFAULT_INPUT = "OUTPUT/ssot/ssot_definitions.json"
INPUT_HASH_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


def _diag(diags: list[Diagnostic], code: str, message: str, expected: str, got: str, path: str) -> None:
    diags.append(Diagnostic(code=code, message=message, expected=expected, got=got, path=path))


def _print_diags(diags: list[Diagnostic]) -> None:
    payload = [d.to_dict() for d in diags]
    print(json.dumps(payload, ensure_ascii=False, indent=2), file=sys.stderr)


def _canonical_json(data: object) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default=DEFAULT_INPUT, help="SSOT definitions JSON path.")
    ap.add_argument("--project-root", default=str(REPO_ROOT), help="Project root.")
    ap.add_argument("--allow-missing", action="store_true", help="Return OK if definitions missing.")
    args = ap.parse_args()

    project_root = Path(args.project_root).resolve()
    input_path = resolve_path(project_root, args.input)

    try:
        ensure_inside(project_root, input_path, "E_SSOT_KERNEL_INPUT_OUTSIDE_PROJECT")
    except ValueError:
        print("E_SSOT_KERNEL_INPUT_OUTSIDE_PROJECT", file=sys.stderr)
        return 2

    expected = (project_root / DEFAULT_INPUT).resolve()
    if input_path != expected:
        print("E_SSOT_KERNEL_INPUT_PATH_INVALID", file=sys.stderr)
        return 2

    if not input_path.exists():
        if args.allow_missing:
            return 0
        _print_diags([
            Diagnostic(
                code="E_SSOT_KERNEL_INPUT_NOT_FOUND",
                message="SSOT definitions file not found",
                expected="existing file",
                got=str(input_path),
                path=json_pointer(),
            )
        ])
        return 2
    if input_path.is_dir():
        print("E_SSOT_KERNEL_INPUT_IS_DIRECTORY", file=sys.stderr)
        return 2
    if has_symlink_parent(input_path, project_root) or input_path.is_symlink():
        print("E_SSOT_KERNEL_INPUT_SYMLINK", file=sys.stderr)
        return 2

    text = input_path.read_text(encoding="utf-8")
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    try:
        data = json.loads(normalized)
    except json.JSONDecodeError as exc:
        _print_diags([
            Diagnostic(
                code="E_SSOT_KERNEL_JSON_INVALID",
                message="SSOT definitions must be valid JSON",
                expected="valid JSON object",
                got=str(exc),
                path=json_pointer(),
            )
        ])
        return 2

    diags: list[Diagnostic] = []
    if not isinstance(data, dict):
        _diag(
            diags,
            "E_SSOT_KERNEL_SCHEMA_INVALID",
            "SSOT definitions root must be object",
            "object",
            type(data).__name__,
            json_pointer(),
        )
    else:
        schema_version = data.get("schema_version")
        if not isinstance(schema_version, str) or not schema_version:
            _diag(
                diags,
                "E_SSOT_KERNEL_SCHEMA_VERSION_INVALID",
                "schema_version missing or invalid",
                "non-empty string",
                str(schema_version),
                json_pointer("schema_version"),
            )
        source_rev = data.get("source_rev")
        if not isinstance(source_rev, str) or not source_rev:
            _diag(
                diags,
                "E_SSOT_KERNEL_SOURCE_REV_INVALID",
                "source_rev missing or invalid",
                "non-empty string",
                str(source_rev),
                json_pointer("source_rev"),
            )
        input_hash = data.get("input_hash")
        if not isinstance(input_hash, str) or not INPUT_HASH_RE.match(input_hash):
            _diag(
                diags,
                "E_SSOT_KERNEL_INPUT_HASH_INVALID",
                "input_hash missing or invalid",
                "sha256:<64hex>",
                str(input_hash),
                json_pointer("input_hash"),
            )
        generator_id = data.get("generator_id")
        if not isinstance(generator_id, str) or not generator_id:
            _diag(
                diags,
                "E_SSOT_KERNEL_GENERATOR_ID_INVALID",
                "generator_id missing or invalid",
                "non-empty string",
                str(generator_id),
                json_pointer("generator_id"),
            )

    canonical = _canonical_json(data)
    if normalized != canonical:
        _diag(
            diags,
            "E_SSOT_KERNEL_NOT_CANONICAL",
            "SSOT definitions must use canonical JSON",
            "canonical JSON (sorted keys, no extra spaces, LF, trailing newline)",
            "non-canonical",
            json_pointer(),
        )

    if diags:
        _print_diags(diags)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
