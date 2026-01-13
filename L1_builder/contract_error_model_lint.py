#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sdslv2_builder.errors import Diagnostic, json_pointer
from sdslv2_builder.op_yaml import load_yaml


PROFILE_REL_PATH = Path("policy") / "contract_resolution_profile.yaml"
TYPE_DECL_START_RE = re.compile(r"^\s*type\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b(?P<rest>.*)$")


def _emit_diag(
    diags: list[Diagnostic],
    code: str,
    message: str,
    expected: str,
    got: str,
    path: str,
) -> None:
    diags.append(Diagnostic(code=code, message=message, expected=expected, got=got, path=path))


def _print_diags(diags: list[Diagnostic]) -> None:
    payload = [d.to_dict() for d in diags]
    print(json.dumps(payload, ensure_ascii=False, indent=2), file=sys.stderr)


def _has_symlink_parent(path: Path, stop: Path) -> bool:
    for parent in [path, *path.parents]:
        if parent == stop:
            break
        if parent.is_symlink():
            return True
    return False


def _load_profile(project_root: Path, diags: list[Diagnostic]) -> dict[str, object] | None:
    path = project_root / PROFILE_REL_PATH
    if not path.exists():
        return None
    try:
        path.resolve().relative_to(project_root.resolve())
    except ValueError:
        _emit_diag(
            diags,
            "E_CONTRACT_ERROR_PROFILE_OUTSIDE_PROJECT",
            "Contract profile must be under project_root",
            "project_root/...",
            str(path),
            json_pointer("profile"),
        )
        return None
    if path.is_symlink() or _has_symlink_parent(path, project_root):
        _emit_diag(
            diags,
            "E_CONTRACT_ERROR_PROFILE_SYMLINK",
            "Contract profile must not be symlink",
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
            "E_CONTRACT_ERROR_PROFILE_PARSE_FAILED",
            "Contract profile parse failed",
            "valid YAML",
            str(exc),
            json_pointer("profile"),
        )
        return None
    if not isinstance(data, dict):
        _emit_diag(
            diags,
            "E_CONTRACT_ERROR_PROFILE_INVALID",
            "Contract profile must be object",
            "object",
            type(data).__name__,
            json_pointer("profile"),
        )
        return None
    return data


def _collect_contract_files(project_root: Path, inputs: list[str]) -> tuple[list[Path] | None, list[Diagnostic]]:
    diags: list[Diagnostic] = []
    files: list[Path] = []
    contract_root = (project_root / "sdsl2" / "contract").absolute()
    if contract_root.is_symlink() or _has_symlink_parent(contract_root, project_root):
        _emit_diag(
            diags,
            "E_CONTRACT_ERROR_CONTRACT_ROOT_SYMLINK",
            "Contract root must not be symlink",
            "non-symlink",
            str(contract_root),
            json_pointer("inputs"),
        )
        return None, diags
    for raw in inputs:
        path = Path(raw)
        if not path.is_absolute():
            path = (project_root / path).absolute()
        if path.is_symlink() or _has_symlink_parent(path, contract_root):
            _emit_diag(
                diags,
                "E_CONTRACT_ERROR_INPUT_SYMLINK",
                "Input must not be symlink",
                "non-symlink",
                str(path),
                json_pointer("inputs"),
            )
            return None, diags
        try:
            path.resolve().relative_to(project_root.resolve())
        except ValueError:
            _emit_diag(
                diags,
                "E_CONTRACT_ERROR_INPUT_OUTSIDE_PROJECT",
                "Input must be under project_root",
                "project_root/...",
                str(path),
                json_pointer("inputs"),
            )
            return None, diags
        try:
            path.resolve().relative_to(contract_root.resolve())
        except ValueError:
            _emit_diag(
                diags,
                "E_CONTRACT_ERROR_INPUT_NOT_CONTRACT",
                "Input must be under sdsl2/contract",
                "sdsl2/contract/...",
                str(path),
                json_pointer("inputs"),
            )
            return None, diags
        if path.is_dir():
            for file_path in sorted(path.rglob("*.sdsl2")):
                if file_path.is_symlink() or _has_symlink_parent(file_path, contract_root):
                    _emit_diag(
                        diags,
                        "E_CONTRACT_ERROR_INPUT_SYMLINK",
                        "Input must not be symlink",
                        "non-symlink",
                        str(file_path),
                        json_pointer("inputs"),
                    )
                    return None, diags
                if file_path.is_file():
                    files.append(file_path)
        elif path.is_file():
            if path.suffix != ".sdsl2":
                _emit_diag(
                    diags,
                    "E_CONTRACT_ERROR_INPUT_NOT_SDSL2",
                    "Input must be .sdsl2 file",
                    ".sdsl2",
                    str(path),
                    json_pointer("inputs"),
                )
                return None, diags
            files.append(path)
        else:
            _emit_diag(
                diags,
                "E_CONTRACT_ERROR_INPUT_NOT_FILE",
                "Input must be file or directory",
                "file/dir",
                str(path),
                json_pointer("inputs"),
            )
            return None, diags
    if not files:
        _emit_diag(
            diags,
            "E_CONTRACT_ERROR_INPUT_NOT_FOUND",
            "No contract files found",
            "existing .sdsl2 files",
            "missing",
            json_pointer("inputs"),
        )
        return None, diags
    return files, diags


def _strip_comments(lines: list[str]) -> list[str]:
    cleaned: list[str] = []
    in_block = False
    for line in lines:
        in_string: str | None = None
        escaped = False
        i = 0
        out: list[str] = []
        while i < len(line):
            ch = line[i]
            nxt = line[i + 1] if i + 1 < len(line) else ""
            if in_block:
                if ch == "*" and nxt == "/":
                    in_block = False
                    i += 2
                    continue
                i += 1
                continue
            if in_string:
                out.append(ch)
                if escaped:
                    escaped = False
                elif ch == "\\":
                    escaped = True
                elif ch == in_string:
                    in_string = None
                i += 1
                continue
            if ch in ('"', "'"):
                in_string = ch
                out.append(ch)
                i += 1
                continue
            if ch == "/" and nxt == "/":
                break
            if ch == "/" and nxt == "*":
                in_block = True
                i += 2
                continue
            out.append(ch)
            i += 1
        cleaned.append("".join(out))
    return cleaned


def _strip_outer_parens(expr: str) -> str:
    expr = expr.strip()
    while expr.startswith("(") and expr.endswith(")"):
        depth = 0
        in_string: str | None = None
        escaped = False
        valid = True
        for idx, ch in enumerate(expr):
            if in_string:
                if escaped:
                    escaped = False
                elif ch == "\\":
                    escaped = True
                elif ch == in_string:
                    in_string = None
                continue
            if ch in ('"', "'"):
                in_string = ch
                continue
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0 and idx != len(expr) - 1:
                    valid = False
                    break
        if not valid or depth != 0:
            break
        expr = expr[1:-1].strip()
    return expr


def _is_string_union(expr: str) -> bool:
    expr = _strip_outer_parens(expr)
    if not expr:
        return False
    i = 0
    expect_literal = True
    while i < len(expr):
        while i < len(expr) and expr[i].isspace():
            i += 1
        if i >= len(expr):
            break
        if expect_literal:
            if expr[i] != '"':
                return False
            i += 1
            escaped = False
            while i < len(expr):
                ch = expr[i]
                if escaped:
                    escaped = False
                elif ch == "\\":
                    escaped = True
                elif ch == '"':
                    i += 1
                    break
                i += 1
            else:
                return False
            expect_literal = False
        else:
            while i < len(expr) and expr[i].isspace():
                i += 1
            if i >= len(expr):
                break
            if expr[i] != "|":
                return False
            i += 1
            expect_literal = True
    return not expect_literal


def _read_error_model(
    profile: dict[str, object] | None,
    diags: list[Diagnostic],
) -> tuple[str, str, str, str]:
    error_code_id = "ERROR_CODE"
    retry_policy_id = "RETRY_POLICY"
    error_format = "string_union"
    retry_format = "string_union"
    if not profile:
        return error_code_id, retry_policy_id, error_format, retry_format
    error_model = profile.get("error_model")
    if error_model is None:
        return error_code_id, retry_policy_id, error_format, retry_format
    if not isinstance(error_model, dict):
        _emit_diag(
            diags,
            "E_CONTRACT_ERROR_PROFILE_INVALID",
            "error_model must be object",
            "object",
            str(error_model),
            json_pointer("profile", "error_model"),
        )
        return error_code_id, retry_policy_id, error_format, retry_format
    for key, target in (("error_code", "ERROR_CODE"), ("retry_policy", "RETRY_POLICY")):
        cfg = error_model.get(key)
        if cfg is None:
            continue
        if not isinstance(cfg, dict):
            _emit_diag(
                diags,
                "E_CONTRACT_ERROR_PROFILE_INVALID",
                f"error_model.{key} must be object",
                "object",
                str(cfg),
                json_pointer("profile", "error_model", key),
            )
            continue
        raw_id = cfg.get("id")
        raw_format = cfg.get("format")
        if raw_id is not None:
            if not isinstance(raw_id, str) or not raw_id.strip():
                _emit_diag(
                    diags,
                    "E_CONTRACT_ERROR_PROFILE_INVALID",
                    f"error_model.{key}.id must be non-empty string",
                    "string",
                    str(raw_id),
                    json_pointer("profile", "error_model", key, "id"),
                )
            else:
                if key == "error_code":
                    error_code_id = raw_id.strip()
                else:
                    retry_policy_id = raw_id.strip()
        if raw_format is not None:
            if not isinstance(raw_format, str) or not raw_format.strip():
                _emit_diag(
                    diags,
                    "E_CONTRACT_ERROR_PROFILE_INVALID",
                    f"error_model.{key}.format must be string",
                    "string",
                    str(raw_format),
                    json_pointer("profile", "error_model", key, "format"),
                )
            else:
                if key == "error_code":
                    error_format = raw_format.strip()
                else:
                    retry_format = raw_format.strip()
    return error_code_id, retry_policy_id, error_format, retry_format


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", action="append", required=True, help="Contract .sdsl2 file or directory")
    ap.add_argument(
        "--project-root",
        default=None,
        help="Project root (defaults to repo root); inputs can be relative to it",
    )
    args = ap.parse_args()

    project_root = Path(args.project_root).resolve() if args.project_root else ROOT
    files, file_diags = _collect_contract_files(project_root, args.input)
    if file_diags:
        _print_diags(file_diags)
        return 2
    if files is None:
        return 2

    profile_diags: list[Diagnostic] = []
    profile = _load_profile(project_root, profile_diags)
    error_code_id, retry_policy_id, error_format, retry_format = _read_error_model(profile, profile_diags)
    if profile_diags:
        _print_diags(profile_diags)
        return 2

    type_exprs: dict[str, str] = {}
    duplicate_types: set[str] = set()
    for path in sorted(files, key=lambda p: p.as_posix()):
        try:
            raw_lines = path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError) as exc:
            _emit_diag(
                profile_diags,
                "E_CONTRACT_ERROR_READ_FAILED",
                "Failed to read contract file",
                "readable UTF-8 file",
                f"{path}: {exc}",
                json_pointer(),
            )
            continue
        lines = _strip_comments(raw_lines)
        current_name: str | None = None
        expr_parts: list[str] = []
        awaiting_equals = False
        for line in lines:
            stripped = line.strip()
            match = TYPE_DECL_START_RE.match(line)
            if match:
                if current_name is not None:
                    expr = " ".join(part.strip() for part in expr_parts if part.strip())
                    if current_name in type_exprs:
                        duplicate_types.add(current_name)
                    else:
                        type_exprs[current_name] = expr
                current_name = match.group("name")
                expr_parts = []
                rest = match.group("rest") or ""
                if "=" in rest:
                    after = rest.split("=", 1)[1].strip()
                    if after:
                        expr_parts.append(after)
                    awaiting_equals = False
                else:
                    awaiting_equals = True
                continue
            if current_name is None:
                continue
            if awaiting_equals:
                if "=" in line:
                    after = line.split("=", 1)[1].strip()
                    if after:
                        expr_parts.append(after)
                    awaiting_equals = False
                continue
            if stripped:
                expr_parts.append(stripped)
        if current_name is not None:
            expr = " ".join(part.strip() for part in expr_parts if part.strip())
            if current_name in type_exprs:
                duplicate_types.add(current_name)
            else:
                type_exprs[current_name] = expr

    if profile_diags:
        _print_diags(profile_diags)
        return 2

    diags: list[Diagnostic] = []
    for name, fmt in ((error_code_id, error_format), (retry_policy_id, retry_format)):
        if name in duplicate_types:
            _emit_diag(
                diags,
                "E_CONTRACT_ERROR_MODEL_DECL_DUPLICATE",
                "Duplicate type alias declaration",
                "unique type alias",
                name,
                json_pointer("types", name),
            )
        expr = type_exprs.get(name)
        if not expr:
            _emit_diag(
                diags,
                "E_CONTRACT_ERROR_MODEL_DECL_MISSING",
                "Type alias missing",
                f"type {name} = ...",
                "missing",
                json_pointer("types", name),
            )
            continue
        if fmt != "string_union":
            _emit_diag(
                diags,
                "E_CONTRACT_ERROR_MODEL_FORMAT_UNSUPPORTED",
                "Unsupported error_model format",
                "string_union",
                fmt,
                json_pointer("types", name),
            )
            continue
        if not _is_string_union(expr):
            _emit_diag(
                diags,
                "E_CONTRACT_ERROR_MODEL_FORMAT_INVALID",
                "Type alias must be string literal union",
                "\"A\"|\"B\"|...",
                expr,
                json_pointer("types", name),
            )

    if diags:
        _print_diags(diags)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
