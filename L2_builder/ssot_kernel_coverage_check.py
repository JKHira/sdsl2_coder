#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from L2_builder.common import ROOT as REPO_ROOT, ensure_inside, has_symlink_parent, resolve_path
from sdslv2_builder.errors import Diagnostic, json_pointer
from sdslv2_builder.op_yaml import load_yaml

DEFAULT_PROFILE = "policy/ssot_kernel_profile.yaml"
DEFAULT_DEFINITIONS = "OUTPUT/ssot/ssot_definitions.json"


def _diag(diags: list[Diagnostic], code: str, message: str, expected: str, got: str, path: str) -> None:
    diags.append(Diagnostic(code=code, message=message, expected=expected, got=got, path=path))


def _print_diags(diags: list[Diagnostic]) -> None:
    payload = [d.to_dict() for d in diags]
    print(json.dumps(payload, ensure_ascii=False, indent=2), file=sys.stderr)


def _decode_json_pointer(pointer: str) -> list[str] | None:
    if pointer == "/":
        return []
    if not pointer.startswith("/"):
        return None
    parts = pointer.split("/")[1:]
    decoded: list[str] = []
    for part in parts:
        if "~" in part:
            i = 0
            while i < len(part):
                if part[i] != "~":
                    i += 1
                    continue
                if i + 1 >= len(part) or part[i + 1] not in {"0", "1"}:
                    return None
                i += 2
            part = part.replace("~1", "/").replace("~0", "~")
        decoded.append(part)
    return decoded


def _resolve_pointer(data: object, pointer: str) -> bool:
    parts = _decode_json_pointer(pointer)
    if parts is None:
        return False
    current: object = data
    for segment in parts:
        if isinstance(current, dict):
            if segment not in current:
                return False
            current = current[segment]
            continue
        if isinstance(current, list):
            if not segment.isdigit():
                return False
            idx = int(segment)
            if idx < 0 or idx >= len(current):
                return False
            current = current[idx]
            continue
        return False
    return True


def _load_profile(project_root: Path, profile: str, diags: list[Diagnostic]) -> dict[str, object] | None:
    profile_path = resolve_path(project_root, profile)
    if not profile_path.exists():
        _diag(
            diags,
            "E_SSOT_COVERAGE_PROFILE_MISSING",
            "profile not found",
            "existing file",
            str(profile_path),
            json_pointer("profile"),
        )
        return None
    try:
        ensure_inside(project_root, profile_path, "E_SSOT_COVERAGE_PROFILE_OUTSIDE_PROJECT")
    except ValueError:
        _diag(
            diags,
            "E_SSOT_COVERAGE_PROFILE_OUTSIDE_PROJECT",
            "profile path outside project",
            "project_root/...",
            str(profile_path),
            json_pointer("profile"),
        )
        return None
    if has_symlink_parent(profile_path, project_root) or profile_path.is_symlink():
        _diag(
            diags,
            "E_SSOT_COVERAGE_PROFILE_SYMLINK",
            "profile must not be symlink",
            "non-symlink",
            str(profile_path),
            json_pointer("profile"),
        )
        return None
    try:
        data = load_yaml(profile_path)
    except Exception as exc:
        _diag(
            diags,
            "E_SSOT_COVERAGE_PROFILE_PARSE_FAILED",
            "profile parse failed",
            "valid YAML",
            str(exc),
            json_pointer("profile"),
        )
        return None
    if not isinstance(data, dict):
        _diag(
            diags,
            "E_SSOT_COVERAGE_PROFILE_INVALID",
            "profile must be object",
            "object",
            type(data).__name__,
            json_pointer("profile"),
        )
        return None
    required_paths = data.get("required_paths")
    if not isinstance(required_paths, list) or not all(isinstance(p, str) and p.startswith("/") for p in required_paths):
        _diag(
            diags,
            "E_SSOT_COVERAGE_PROFILE_INVALID",
            "required_paths must be list of JSON pointers",
            "list of strings starting with '/'",
            str(required_paths),
            json_pointer("profile", "required_paths"),
        )
        return None
    for idx, pointer in enumerate(required_paths):
        if _decode_json_pointer(pointer) is None:
            _diag(
                diags,
                "E_SSOT_COVERAGE_PROFILE_INVALID",
                "required_paths contains invalid JSON pointer",
                "RFC6901 pointer",
                pointer,
                json_pointer("profile", "required_paths", str(idx)),
            )
            return None
    required_artifacts: list[dict[str, str]] = []
    raw_artifacts = data.get("required_artifacts")
    if raw_artifacts is not None:
        if not isinstance(raw_artifacts, list):
            _diag(
                diags,
                "E_SSOT_COVERAGE_PROFILE_INVALID",
                "required_artifacts must be list",
                "list of {id,pointer}",
                str(raw_artifacts),
                json_pointer("profile", "required_artifacts"),
            )
            return None
        for idx, item in enumerate(raw_artifacts):
            if not isinstance(item, dict):
                _diag(
                    diags,
                    "E_SSOT_COVERAGE_PROFILE_INVALID",
                    "required_artifacts item must be object",
                    "object",
                    str(item),
                    json_pointer("profile", "required_artifacts", str(idx)),
                )
                return None
            artifact_id = item.get("id")
            pointer = item.get("pointer")
            if not isinstance(artifact_id, str) or not artifact_id.strip():
                _diag(
                    diags,
                    "E_SSOT_COVERAGE_PROFILE_INVALID",
                    "required_artifacts.id must be non-empty string",
                    "string",
                    str(artifact_id),
                    json_pointer("profile", "required_artifacts", str(idx), "id"),
                )
                return None
            if not isinstance(pointer, str) or not pointer.startswith("/"):
                _diag(
                    diags,
                    "E_SSOT_COVERAGE_PROFILE_INVALID",
                    "required_artifacts.pointer must be JSON pointer",
                    "string starting with '/'",
                    str(pointer),
                    json_pointer("profile", "required_artifacts", str(idx), "pointer"),
                )
                return None
            if _decode_json_pointer(pointer) is None:
                _diag(
                    diags,
                    "E_SSOT_COVERAGE_PROFILE_INVALID",
                    "required_artifacts.pointer must be valid JSON pointer",
                    "RFC6901 pointer",
                    pointer,
                    json_pointer("profile", "required_artifacts", str(idx), "pointer"),
                )
                return None
            required_artifacts.append({"id": artifact_id, "pointer": pointer})

    determinism_specs: list[dict[str, str]] = []
    raw_specs = data.get("determinism_specs")
    if raw_specs is not None:
        if not isinstance(raw_specs, list):
            _diag(
                diags,
                "E_SSOT_COVERAGE_PROFILE_INVALID",
                "determinism_specs must be list",
                "list of {id,pointer}",
                str(raw_specs),
                json_pointer("profile", "determinism_specs"),
            )
            return None
        for idx, item in enumerate(raw_specs):
            if not isinstance(item, dict):
                _diag(
                    diags,
                    "E_SSOT_COVERAGE_PROFILE_INVALID",
                    "determinism_specs item must be object",
                    "object",
                    str(item),
                    json_pointer("profile", "determinism_specs", str(idx)),
                )
                return None
            spec_id = item.get("id")
            pointer = item.get("pointer")
            if not isinstance(spec_id, str) or not spec_id.strip():
                _diag(
                    diags,
                    "E_SSOT_COVERAGE_PROFILE_INVALID",
                    "determinism_specs.id must be non-empty string",
                    "string",
                    str(spec_id),
                    json_pointer("profile", "determinism_specs", str(idx), "id"),
                )
                return None
            if not isinstance(pointer, str) or not pointer.startswith("/"):
                _diag(
                    diags,
                    "E_SSOT_COVERAGE_PROFILE_INVALID",
                    "determinism_specs.pointer must be JSON pointer",
                    "string starting with '/'",
                    str(pointer),
                    json_pointer("profile", "determinism_specs", str(idx), "pointer"),
                )
                return None
            if _decode_json_pointer(pointer) is None:
                _diag(
                    diags,
                    "E_SSOT_COVERAGE_PROFILE_INVALID",
                    "determinism_specs.pointer must be valid JSON pointer",
                    "RFC6901 pointer",
                    pointer,
                    json_pointer("profile", "determinism_specs", str(idx), "pointer"),
                )
                return None
            determinism_specs.append({"id": spec_id, "pointer": pointer})

    return {
        "required_paths": required_paths,
        "required_artifacts": required_artifacts,
        "determinism_specs": determinism_specs,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project-root", default=str(REPO_ROOT), help="Project root.")
    ap.add_argument("--profile", default=DEFAULT_PROFILE, help="Profile path.")
    ap.add_argument("--definitions", default=DEFAULT_DEFINITIONS, help="SSOT definitions JSON path.")
    args = ap.parse_args()

    project_root = Path(args.project_root).resolve()
    diags: list[Diagnostic] = []
    profile_data = _load_profile(project_root, args.profile, diags)
    if diags:
        _print_diags(diags)
        return 2
    if profile_data is None:
        _print_diags([
            Diagnostic(
                code="E_SSOT_COVERAGE_PROFILE_MISSING",
                message="profile not loaded",
                expected="valid profile",
                got=str(args.profile),
                path=json_pointer("profile"),
            )
        ])
        return 2

    definitions_path = resolve_path(project_root, args.definitions)
    try:
        ensure_inside(project_root, definitions_path, "E_SSOT_COVERAGE_INPUT_OUTSIDE_PROJECT")
    except ValueError:
        print("E_SSOT_COVERAGE_INPUT_OUTSIDE_PROJECT", file=sys.stderr)
        return 2
    if not definitions_path.exists():
        _print_diags([
            Diagnostic(
                code="E_SSOT_COVERAGE_INPUT_NOT_FOUND",
                message="ssot_definitions.json not found",
                expected="existing file",
                got=str(definitions_path),
                path=json_pointer(),
            )
        ])
        return 2
    if definitions_path.is_dir():
        print("E_SSOT_COVERAGE_INPUT_IS_DIRECTORY", file=sys.stderr)
        return 2
    if has_symlink_parent(definitions_path, project_root) or definitions_path.is_symlink():
        print("E_SSOT_COVERAGE_INPUT_SYMLINK", file=sys.stderr)
        return 2

    try:
        raw = definitions_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        _print_diags([
            Diagnostic(
                code="E_SSOT_COVERAGE_READ_FAILED",
                message="ssot_definitions.json read failed",
                expected="readable UTF-8 file",
                got=str(exc),
                path=json_pointer(),
            )
        ])
        return 2
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        _print_diags([
            Diagnostic(
                code="E_SSOT_COVERAGE_JSON_INVALID",
                message="ssot_definitions.json must be valid JSON",
                expected="valid JSON object",
                got=str(exc),
                path=json_pointer(),
            )
        ])
        return 2
    if not isinstance(data, dict):
        _print_diags([
            Diagnostic(
                code="E_SSOT_COVERAGE_JSON_INVALID",
                message="ssot_definitions.json must be JSON object",
                expected="object",
                got=type(data).__name__,
                path=json_pointer(),
            )
        ])
        return 2

    required_paths = profile_data.get("required_paths", [])
    for idx, pointer in enumerate(required_paths):
        if not _resolve_pointer(data, pointer):
            _diag(
                diags,
                "E_SSOT_COVERAGE_PATH_MISSING",
                "required path missing in ssot_definitions",
                pointer,
                "missing",
                json_pointer("required_paths", str(idx)),
            )

    required_artifacts = profile_data.get("required_artifacts", [])
    for item in required_artifacts:
        if not isinstance(item, dict):
            continue
        pointer = item.get("pointer", "")
        artifact_id = item.get("id", "")
        if not isinstance(pointer, str):
            continue
        if not _resolve_pointer(data, pointer):
            _diag(
                diags,
                "E_SSOT_COVERAGE_ARTIFACT_MISSING",
                "required artifact definition missing in ssot_definitions",
                pointer,
                "missing",
                json_pointer("required_artifacts", str(artifact_id)),
            )

    determinism_specs = profile_data.get("determinism_specs", [])
    for item in determinism_specs:
        if not isinstance(item, dict):
            continue
        pointer = item.get("pointer", "")
        spec_id = item.get("id", "")
        if not isinstance(pointer, str):
            continue
        if not _resolve_pointer(data, pointer):
            _diag(
                diags,
                "E_SSOT_COVERAGE_DETERMINISM_MISSING",
                "required determinism spec missing in ssot_definitions",
                pointer,
                "missing",
                json_pointer("determinism_specs", str(spec_id)),
            )

    if diags:
        _print_diags(diags)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
