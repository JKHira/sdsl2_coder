#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import difflib
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sdslv2_builder.contract import Decl
from sdslv2_builder.contract_writer import _format_decl
from sdslv2_builder.errors import Diagnostic, json_pointer
from sdslv2_builder.input_hash import InputHashResult, compute_input_hash
from sdslv2_builder.io_atomic import atomic_write_text
from sdslv2_builder.op_yaml import DuplicateKey, load_yaml_with_duplicates
from sdslv2_builder.refs import RELID_RE

TOOL_NAME = "contract_error_model_builder"
STAGE = "L1"
DEFAULT_OUT_REL = Path("OUTPUT") / "contract_error_model.patch"
PROFILE_REL_PATH = Path("policy") / "contract_resolution_profile.yaml"
PLACEHOLDERS = {"none", "null", "tbd", "opaque"}
ALLOWED_TOP_KEYS = {"schema_version", "target", "error_code", "retry_policy"}
ALLOWED_MODEL_KEYS = {"values"}


def _diag(
    diags: list[Diagnostic],
    code: str,
    message: str,
    expected: str,
    got: str,
    path: str,
) -> None:
    diags.append(Diagnostic(code=code, message=message, expected=expected, got=got, path=path))


def _emit_result(
    status: str,
    diags: list[Diagnostic],
    inputs: list[str],
    outputs: list[str],
    diff_paths: list[str],
    source_rev: str | None = None,
    input_hash: InputHashResult | None = None,
    summary: str | None = None,
    next_actions: list[str] | None = None,
    gaps_missing: list[str] | None = None,
    gaps_invalid: list[str] | None = None,
) -> None:
    codes = sorted({diag.code for diag in diags})
    payload = {
        "status": status,
        "tool": TOOL_NAME,
        "stage": STAGE,
        "source_rev": source_rev,
        "input_hash": input_hash.input_hash if input_hash else None,
        "inputs": inputs,
        "outputs": outputs,
        "diff_paths": diff_paths,
        "diagnostics": {"count": len(diags), "codes": codes},
        "gaps": {
            "missing": gaps_missing or [],
            "invalid": gaps_invalid or [],
        },
        "next_actions": next_actions or [],
    }
    print(json.dumps(payload, ensure_ascii=False))
    if summary:
        print(summary, file=sys.stderr)


def _resolve_path(base: Path, raw: str) -> Path:
    path = Path(raw)
    if not path.is_absolute():
        path = (base / path).resolve()
    return path


def _rel_path(project_root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(project_root.resolve()).as_posix()
    except ValueError:
        return str(path)


def _has_symlink_parent(path: Path, stop: Path) -> bool:
    for parent in [path, *path.parents]:
        if parent == stop:
            break
        if parent.is_symlink():
            return True
    return False


def _dup_path(prefix: str, dup: DuplicateKey) -> str:
    if prefix:
        if dup.path:
            return prefix + dup.path
        return prefix
    return dup.path


def _git_rev(root: Path) -> str:
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return "UNKNOWN"
    if proc.returncode != 0:
        return "UNKNOWN"
    return proc.stdout.strip() or "UNKNOWN"


def _build_source_rev(git_rev: str, generator_id: str) -> str:
    return f"{git_rev}|gen:{generator_id}"


def _is_placeholder(value: str) -> bool:
    return value.strip().strip('"').strip("'").lower() in PLACEHOLDERS


def _escape_literal(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _load_profile(project_root: Path, diags: list[Diagnostic]) -> dict[str, object] | None:
    path = project_root / PROFILE_REL_PATH
    if not path.exists():
        _diag(
            diags,
            "E_CONTRACT_ERROR_MODEL_PROFILE_MISSING",
            "contract profile is required",
            "policy/contract_resolution_profile.yaml",
            "missing",
            json_pointer("profile"),
        )
        return None
    try:
        path.resolve().relative_to(project_root.resolve())
    except ValueError:
        _diag(
            diags,
            "E_CONTRACT_ERROR_MODEL_PROFILE_OUTSIDE_PROJECT",
            "contract profile must be under project_root",
            "project_root/...",
            str(path),
            json_pointer("profile"),
        )
        return None
    if path.is_symlink() or _has_symlink_parent(path, project_root):
        _diag(
            diags,
            "E_CONTRACT_ERROR_MODEL_PROFILE_SYMLINK",
            "contract profile must not be symlink",
            "non-symlink",
            str(path),
            json_pointer("profile"),
        )
        return None
    try:
        data, duplicates = load_yaml_with_duplicates(path, allow_duplicates=True)
    except Exception as exc:
        _diag(
            diags,
            "E_CONTRACT_ERROR_MODEL_PROFILE_PARSE_FAILED",
            "contract profile parse failed",
            "valid YAML",
            str(exc),
            json_pointer("profile"),
        )
        return None
    if duplicates:
        for dup in duplicates:
            _diag(
                diags,
                "E_CONTRACT_ERROR_MODEL_PROFILE_DUPLICATE_KEY",
                "duplicate key in contract profile",
                "unique key",
                dup.key,
                _dup_path(json_pointer("profile"), dup),
            )
        return None
    if not isinstance(data, dict):
        _diag(
            diags,
            "E_CONTRACT_ERROR_MODEL_PROFILE_INVALID",
            "contract profile must be object",
            "object",
            type(data).__name__,
            json_pointer("profile"),
        )
        return None
    return data


def _read_error_model_profile(profile: dict[str, object], diags: list[Diagnostic]) -> tuple[str, str]:
    error_model = profile.get("error_model")
    if not isinstance(error_model, dict):
        _diag(
            diags,
            "E_CONTRACT_ERROR_MODEL_PROFILE_INVALID",
            "error_model must be object",
            "object",
            str(error_model),
            json_pointer("profile", "error_model"),
        )
        return "", ""
    error_code = error_model.get("error_code")
    retry_policy = error_model.get("retry_policy")
    if not isinstance(error_code, dict) or not isinstance(retry_policy, dict):
        _diag(
            diags,
            "E_CONTRACT_ERROR_MODEL_PROFILE_INVALID",
            "error_model.error_code and error_model.retry_policy must be objects",
            "object",
            "invalid",
            json_pointer("profile", "error_model"),
        )
        return "", ""
    error_id = error_code.get("id")
    retry_id = retry_policy.get("id")
    if not isinstance(error_id, str) or not error_id.strip():
        _diag(
            diags,
            "E_CONTRACT_ERROR_MODEL_PROFILE_INVALID",
            "error_model.error_code.id must be non-empty string",
            "string",
            str(error_id),
            json_pointer("profile", "error_model", "error_code", "id"),
        )
    elif not RELID_RE.match(error_id.strip()):
        _diag(
            diags,
            "E_CONTRACT_ERROR_MODEL_PROFILE_INVALID",
            "error_model.error_code.id must be RELID",
            "UPPER_SNAKE_CASE",
            str(error_id),
            json_pointer("profile", "error_model", "error_code", "id"),
        )
    if not isinstance(retry_id, str) or not retry_id.strip():
        _diag(
            diags,
            "E_CONTRACT_ERROR_MODEL_PROFILE_INVALID",
            "error_model.retry_policy.id must be non-empty string",
            "string",
            str(retry_id),
            json_pointer("profile", "error_model", "retry_policy", "id"),
        )
    elif not RELID_RE.match(retry_id.strip()):
        _diag(
            diags,
            "E_CONTRACT_ERROR_MODEL_PROFILE_INVALID",
            "error_model.retry_policy.id must be RELID",
            "UPPER_SNAKE_CASE",
            str(retry_id),
            json_pointer("profile", "error_model", "retry_policy", "id"),
        )
    for key, target in (("error_code", error_code), ("retry_policy", retry_policy)):
        fmt = target.get("format")
        if fmt != "string_union":
            _diag(
                diags,
                "E_CONTRACT_ERROR_MODEL_PROFILE_INVALID",
                f"error_model.{key}.format must be string_union",
                "string_union",
                str(fmt),
                json_pointer("profile", "error_model", key, "format"),
            )
    return str(error_id or ""), str(retry_id or "")


def _read_input(
    path: Path,
    diags: list[Diagnostic],
) -> tuple[str | None, list[str], list[str]]:
    try:
        data, duplicates = load_yaml_with_duplicates(path, allow_duplicates=True)
    except Exception as exc:
        _diag(
            diags,
            "E_CONTRACT_ERROR_MODEL_INPUT_PARSE_FAILED",
            "input must be valid YAML",
            "valid YAML",
            str(exc),
            json_pointer("input"),
        )
        return None, [], []
    if duplicates:
        for dup in duplicates:
            _diag(
                diags,
                "E_CONTRACT_ERROR_MODEL_INPUT_DUPLICATE_KEY",
                "duplicate key in input",
                "unique key",
                dup.key,
                _dup_path(json_pointer("input"), dup),
            )
        return None, [], []
    if not isinstance(data, dict):
        _diag(
            diags,
            "E_CONTRACT_ERROR_MODEL_INPUT_INVALID",
            "input must be object",
            "object",
            type(data).__name__,
            json_pointer("input"),
        )
        return None, [], []
    unknown_keys = sorted(set(data.keys()) - ALLOWED_TOP_KEYS)
    if unknown_keys:
        _diag(
            diags,
            "E_CONTRACT_ERROR_MODEL_INPUT_INVALID",
            "input has unknown keys",
            ",".join(sorted(ALLOWED_TOP_KEYS)),
            ",".join(unknown_keys),
            json_pointer("input"),
        )
        return None, [], []
    schema_version = data.get("schema_version")
    if not isinstance(schema_version, str) or not schema_version.strip():
        _diag(
            diags,
            "E_CONTRACT_ERROR_MODEL_INPUT_INVALID",
            "schema_version must be non-empty string",
            "string",
            str(schema_version),
            json_pointer("input", "schema_version"),
        )
    elif schema_version != "1.0":
        _diag(
            diags,
            "E_CONTRACT_ERROR_MODEL_INPUT_INVALID",
            "schema_version must be 1.0",
            "1.0",
            schema_version,
            json_pointer("input", "schema_version"),
        )
    target = data.get("target")
    if not isinstance(target, str) or not target.strip():
        _diag(
            diags,
            "E_CONTRACT_ERROR_MODEL_INPUT_INVALID",
            "target must be non-empty string",
            "sdsl2/contract/*.sdsl2",
            str(target),
            json_pointer("input", "target"),
        )
        target = None
    error_cfg = data.get("error_code")
    retry_cfg = data.get("retry_policy")
    error_values = _read_values(error_cfg, diags, "error_code")
    retry_values = _read_values(retry_cfg, diags, "retry_policy")
    return target, error_values, retry_values


def _read_values(value: object, diags: list[Diagnostic], key: str) -> list[str]:
    if not isinstance(value, dict):
        _diag(
            diags,
            "E_CONTRACT_ERROR_MODEL_INPUT_INVALID",
            f"{key} must be object",
            "object",
            str(value),
            json_pointer("input", key),
        )
        return []
    unknown = sorted(set(value.keys()) - ALLOWED_MODEL_KEYS)
    if unknown:
        _diag(
            diags,
            "E_CONTRACT_ERROR_MODEL_INPUT_INVALID",
            f"{key} has unknown keys",
            ",".join(sorted(ALLOWED_MODEL_KEYS)),
            ",".join(unknown),
            json_pointer("input", key),
        )
        return []
    raw_values = value.get("values")
    if not isinstance(raw_values, list) or not raw_values:
        _diag(
            diags,
            "E_CONTRACT_ERROR_MODEL_INPUT_INVALID",
            f"{key}.values must be non-empty list",
            "list[str]",
            str(raw_values),
            json_pointer("input", key, "values"),
        )
        return []
    cleaned: list[str] = []
    seen: set[str] = set()
    for idx, item in enumerate(raw_values):
        if not isinstance(item, str) or not item.strip():
            _diag(
                diags,
                "E_CONTRACT_ERROR_MODEL_INPUT_INVALID",
                f"{key}.values items must be non-empty strings",
                "string",
                str(item),
                json_pointer("input", key, "values", str(idx)),
            )
            continue
        if _is_placeholder(item):
            _diag(
                diags,
                "E_CONTRACT_ERROR_MODEL_INPUT_INVALID",
                f"{key}.values must not include placeholders",
                "non-placeholder",
                item,
                json_pointer("input", key, "values", str(idx)),
            )
            continue
        if item in seen:
            _diag(
                diags,
                "E_CONTRACT_ERROR_MODEL_INPUT_INVALID",
                f"{key}.values must be unique",
                "unique items",
                item,
                json_pointer("input", key, "values", str(idx)),
            )
            continue
        if "\n" in item:
            _diag(
                diags,
                "E_CONTRACT_ERROR_MODEL_INPUT_INVALID",
                f"{key}.values must be single-line strings",
                "single-line",
                item,
                json_pointer("input", key, "values", str(idx)),
            )
            continue
        seen.add(item)
        cleaned.append(item)
    return cleaned


def _format_union_expr(values: list[str]) -> str:
    return " | ".join(f"\"{_escape_literal(value)}\"" for value in values)


def _replace_type_decl(
    lines: list[str],
    type_name: str,
    new_decl: str,
    diags: list[Diagnostic],
    path_ref: str,
) -> bool:
    pattern = re.compile(rf"^(?P<indent>[ \t]*)type\s+{re.escape(type_name)}\s*=")
    matches: list[int] = []
    for idx, line in enumerate(lines):
        if pattern.match(line):
            matches.append(idx)
    if not matches:
        return False
    if len(matches) > 1:
        _diag(
            diags,
            "E_CONTRACT_ERROR_MODEL_DUPLICATE",
            "multiple type declarations found",
            "single declaration",
            type_name,
            path_ref,
        )
        return False
    idx = matches[0]
    match = pattern.match(lines[idx])
    indent = match.group("indent") if match else ""
    end_idx = idx
    in_union = False
    j = idx + 1
    while j < len(lines):
        nxt = lines[j].strip()
        if nxt == "" or nxt.startswith("//"):
            if in_union:
                end_idx = j
            j += 1
            continue
        if nxt.startswith("|"):
            in_union = True
            end_idx = j
            j += 1
            continue
        break
    lines[idx] = f"{indent}{new_decl}"
    if end_idx > idx:
        del lines[idx + 1 : end_idx + 1]
    return True


def _find_decl_insert_index(lines: list[str]) -> int:
    for idx, line in enumerate(lines):
        stripped = line.lstrip()
        if stripped.startswith("@Dep") or stripped.startswith("@Rule"):
            return idx
    return len(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="Error model input YAML")
    ap.add_argument("--out", default=None, help="Unified diff output path (default: OUTPUT/contract_error_model.patch)")
    ap.add_argument("--generator-id", default="contract_error_model_builder_v0_1", help="generator id")
    ap.add_argument("--project-root", default=None, help="Project root (defaults to repo root)")
    args = ap.parse_args()

    project_root = Path(args.project_root).resolve() if args.project_root else ROOT
    input_path = _resolve_path(project_root, args.input)
    out_path = _resolve_path(project_root, args.out) if args.out else project_root / DEFAULT_OUT_REL

    inputs = [_rel_path(project_root, input_path)]
    outputs = [_rel_path(project_root, out_path)]
    diff_paths = [_rel_path(project_root, out_path)]

    diags: list[Diagnostic] = []
    if not input_path.exists():
        _diag(
            diags,
            "E_CONTRACT_ERROR_MODEL_INPUT_NOT_FOUND",
            "input not found",
            "existing file",
            str(input_path),
            json_pointer("input"),
        )
    if input_path.exists() and input_path.is_dir():
        _diag(
            diags,
            "E_CONTRACT_ERROR_MODEL_INPUT_IS_DIR",
            "input must be file",
            "file",
            str(input_path),
            json_pointer("input"),
        )
    if input_path.exists() and (input_path.is_symlink() or _has_symlink_parent(input_path, project_root)):
        _diag(
            diags,
            "E_CONTRACT_ERROR_MODEL_INPUT_SYMLINK",
            "input must not be symlink",
            "non-symlink",
            str(input_path),
            json_pointer("input"),
        )
    if input_path.exists():
        try:
            input_path.resolve().relative_to(project_root.resolve())
        except ValueError:
            _diag(
                diags,
                "E_CONTRACT_ERROR_MODEL_INPUT_OUTSIDE_PROJECT",
                "input must be under project_root",
                "project_root/...",
                str(input_path),
                json_pointer("input"),
            )

    profile_diags: list[Diagnostic] = []
    profile = _load_profile(project_root, profile_diags)
    if profile_diags:
        _emit_result(
            "fail",
            profile_diags,
            inputs,
            outputs,
            diff_paths,
            summary=f"{TOOL_NAME}: profile validation failed",
        )
        return 2

    if diags:
        _emit_result(
            "fail",
            diags,
            inputs,
            outputs,
            diff_paths,
            summary=f"{TOOL_NAME}: input validation failed",
        )
        return 2

    error_id, retry_id = _read_error_model_profile(profile, diags)
    if diags or not error_id or not retry_id:
        _emit_result(
            "fail",
            diags,
            inputs,
            outputs,
            diff_paths,
            summary=f"{TOOL_NAME}: profile error_model invalid",
        )
        return 2

    target_raw, error_values, retry_values = _read_input(input_path, diags)
    if diags:
        _emit_result(
            "fail",
            diags,
            inputs,
            outputs,
            diff_paths,
            summary=f"{TOOL_NAME}: input parse failed",
        )
        return 2

    if not target_raw:
        _emit_result(
            "fail",
            [
                Diagnostic(
                    code="E_CONTRACT_ERROR_MODEL_TARGET_MISSING",
                    message="target contract path required",
                    expected="sdsl2/contract/*.sdsl2",
                    got="missing",
                    path=json_pointer("target"),
                )
            ],
            inputs,
            outputs,
            diff_paths,
            summary=f"{TOOL_NAME}: missing target",
        )
        return 2

    if not error_values or not retry_values:
        _emit_result(
            "fail",
            [
                Diagnostic(
                    code="E_CONTRACT_ERROR_MODEL_INPUT_INVALID",
                    message="error_code.values and retry_policy.values are required",
                    expected="non-empty lists",
                    got="missing",
                    path=json_pointer("input"),
                )
            ],
            inputs,
            outputs,
            diff_paths,
            summary=f"{TOOL_NAME}: missing values",
        )
        return 2

    source_rev = _build_source_rev(_git_rev(project_root), args.generator_id)
    try:
        input_hash = compute_input_hash(
            project_root,
            include_decisions=False,
            extra_inputs=[input_path, project_root / PROFILE_REL_PATH],
        )
    except (FileNotFoundError, ValueError, OSError, UnicodeDecodeError) as exc:
        _emit_result(
            "fail",
            [
                Diagnostic(
                    code="E_CONTRACT_ERROR_MODEL_INPUT_HASH_FAILED",
                    message="input_hash calculation failed",
                    expected="valid inputs",
                    got=str(exc),
                    path=json_pointer("input_hash"),
                )
            ],
            inputs,
            outputs,
            diff_paths,
            source_rev=source_rev,
            summary=f"{TOOL_NAME}: input_hash failed",
        )
        return 2

    target_path = _resolve_path(project_root, target_raw)
    try:
        target_path.resolve().relative_to(project_root.resolve())
    except ValueError:
        _emit_result(
            "fail",
            [
                Diagnostic(
                    code="E_CONTRACT_ERROR_MODEL_TARGET_OUTSIDE_PROJECT",
                    message="target must be under project_root",
                    expected="project_root/...",
                    got=str(target_path),
                    path=json_pointer("target"),
                )
            ],
            inputs,
            outputs,
            diff_paths,
            source_rev=source_rev,
            input_hash=input_hash,
            summary=f"{TOOL_NAME}: invalid target",
        )
        return 2
    contract_root = project_root / "sdsl2" / "contract"
    try:
        target_path.resolve().relative_to(contract_root.resolve())
    except ValueError:
        _emit_result(
            "fail",
            [
                Diagnostic(
                    code="E_CONTRACT_ERROR_MODEL_TARGET_NOT_CONTRACT",
                    message="target must be under sdsl2/contract",
                    expected="sdsl2/contract/...",
                    got=str(target_path),
                    path=json_pointer("target"),
                )
            ],
            inputs,
            outputs,
            diff_paths,
            source_rev=source_rev,
            input_hash=input_hash,
            summary=f"{TOOL_NAME}: invalid target",
        )
        return 2
    if target_path.is_symlink() or _has_symlink_parent(target_path, project_root):
        _emit_result(
            "fail",
            [
                Diagnostic(
                    code="E_CONTRACT_ERROR_MODEL_TARGET_SYMLINK",
                    message="target must not be symlink",
                    expected="non-symlink",
                    got=str(target_path),
                    path=json_pointer("target"),
                )
            ],
            inputs,
            outputs,
            diff_paths,
            source_rev=source_rev,
            input_hash=input_hash,
            summary=f"{TOOL_NAME}: invalid target",
        )
        return 2

    if not target_path.exists():
        _emit_result(
            "fail",
            [
                Diagnostic(
                    code="E_CONTRACT_ERROR_MODEL_TARGET_MISSING",
                    message="target contract file is missing",
                    expected="existing contract file",
                    got=str(target_path),
                    path=json_pointer("target"),
                )
            ],
            inputs,
            outputs,
            diff_paths,
            source_rev=source_rev,
            input_hash=input_hash,
            summary=f"{TOOL_NAME}: target missing",
            next_actions=[f"tool:contract_scaffold_gen --out {target_raw} --id-prefix <ID_PREFIX>"],
        )
        return 2

    try:
        old_text = target_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        _emit_result(
            "fail",
            [
                Diagnostic(
                    code="E_CONTRACT_ERROR_MODEL_READ_FAILED",
                    message="target contract must be readable UTF-8",
                    expected="readable UTF-8 file",
                    got=str(exc),
                    path=json_pointer("target"),
                )
            ],
            inputs,
            outputs,
            diff_paths,
            source_rev=source_rev,
            input_hash=input_hash,
            summary=f"{TOOL_NAME}: read failed",
        )
        return 2

    lines = old_text.splitlines()
    error_decl = f"type {error_id} = {_format_union_expr(error_values)}"
    retry_decl = f"type {retry_id} = {_format_union_expr(retry_values)}"

    error_replaced = _replace_type_decl(
        lines,
        error_id,
        error_decl,
        diags,
        json_pointer("target", error_id),
    )
    retry_replaced = _replace_type_decl(
        lines,
        retry_id,
        retry_decl,
        diags,
        json_pointer("target", retry_id),
    )
    if diags:
        _emit_result(
            "fail",
            diags,
            inputs,
            outputs,
            diff_paths,
            source_rev=source_rev,
            input_hash=input_hash,
            summary=f"{TOOL_NAME}: update failed",
        )
        return 2

    new_lines = lines[:]
    insert_blocks: list[list[str]] = []
    if not error_replaced:
        insert_blocks.append(
            _format_decl(
                Decl(
                    kind="Type",
                    rel_id=error_id,
                    decl=error_decl,
                    bind=None,
                    title=None,
                    desc=None,
                    refs=[],
                    contract=[],
                    ssot=[],
                )
            )
        )
    if not retry_replaced:
        insert_blocks.append(
            _format_decl(
                Decl(
                    kind="Type",
                    rel_id=retry_id,
                    decl=retry_decl,
                    bind=None,
                    title=None,
                    desc=None,
                    refs=[],
                    contract=[],
                    ssot=[],
                )
            )
        )
    if insert_blocks:
        insert_at = _find_decl_insert_index(new_lines)
        insert_lines: list[str] = []
        for block in insert_blocks:
            if insert_lines:
                insert_lines.append("")
            insert_lines.extend(block)
        if insert_at > 0 and new_lines[insert_at - 1].strip():
            insert_lines = [""] + insert_lines
        new_lines[insert_at:insert_at] = insert_lines

    new_text = "\n".join(new_lines).rstrip() + "\n"
    diff = difflib.unified_diff(
        old_text.splitlines(),
        new_text.splitlines(),
        fromfile=str(target_path),
        tofile=str(target_path),
        lineterm="",
    )
    output = "\n".join(diff)
    if not output:
        _emit_result(
            "fail",
            [
                Diagnostic(
                    code="E_CONTRACT_ERROR_MODEL_NO_CHANGE",
                    message="no error model updates required",
                    expected="missing or outdated error model",
                    got="no change",
                    path=json_pointer("target"),
                )
            ],
            inputs,
            outputs,
            diff_paths,
            source_rev=source_rev,
            input_hash=input_hash,
            summary=f"{TOOL_NAME}: no changes required",
        )
        return 2

    try:
        out_path.resolve().relative_to(project_root.resolve())
    except ValueError:
        _emit_result(
            "fail",
            [
                Diagnostic(
                    code="E_CONTRACT_ERROR_MODEL_OUTSIDE_PROJECT",
                    message="out must be under project_root",
                    expected="project_root/...",
                    got=str(out_path),
                    path=json_pointer("out"),
                )
            ],
            inputs,
            outputs,
            diff_paths,
            source_rev=source_rev,
            input_hash=input_hash,
            summary=f"{TOOL_NAME}: invalid output path",
        )
        return 2
    if out_path.exists() and out_path.is_dir():
        _emit_result(
            "fail",
            [
                Diagnostic(
                    code="E_CONTRACT_ERROR_MODEL_OUT_IS_DIR",
                    message="out must be file",
                    expected="file",
                    got=str(out_path),
                    path=json_pointer("out"),
                )
            ],
            inputs,
            outputs,
            diff_paths,
            source_rev=source_rev,
            input_hash=input_hash,
            summary=f"{TOOL_NAME}: invalid output path",
        )
        return 2
    if out_path.exists() and out_path.is_symlink():
        _emit_result(
            "fail",
            [
                Diagnostic(
                    code="E_CONTRACT_ERROR_MODEL_OUT_SYMLINK",
                    message="out must not be symlink",
                    expected="non-symlink",
                    got=str(out_path),
                    path=json_pointer("out"),
                )
            ],
            inputs,
            outputs,
            diff_paths,
            source_rev=source_rev,
            input_hash=input_hash,
            summary=f"{TOOL_NAME}: invalid output path",
        )
        return 2
    if _has_symlink_parent(out_path, project_root):
        _emit_result(
            "fail",
            [
                Diagnostic(
                    code="E_CONTRACT_ERROR_MODEL_OUT_SYMLINK_PARENT",
                    message="out parent must not be symlink",
                    expected="non-symlink",
                    got=str(out_path),
                    path=json_pointer("out"),
                )
            ],
            inputs,
            outputs,
            diff_paths,
            source_rev=source_rev,
            input_hash=input_hash,
            summary=f"{TOOL_NAME}: invalid output path",
        )
        return 2
    out_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        atomic_write_text(out_path, output + "\n", symlink_code="E_CONTRACT_ERROR_MODEL_OUT_SYMLINK")
    except ValueError as exc:
        _emit_result(
            "fail",
            [
                Diagnostic(
                    code=str(exc),
                    message="out must not be symlink",
                    expected="non-symlink",
                    got=str(out_path),
                    path=json_pointer("out"),
                )
            ],
            inputs,
            outputs,
            diff_paths,
            source_rev=source_rev,
            input_hash=input_hash,
            summary=f"{TOOL_NAME}: output write blocked",
        )
        return 2

    _emit_result(
        "ok",
        [],
        inputs,
        outputs,
        diff_paths,
        source_rev=source_rev,
        input_hash=input_hash,
        summary=f"{TOOL_NAME}: diff written",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
