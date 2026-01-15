#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import difflib
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sdslv2_builder.contract import Decl
from sdslv2_builder.contract_writer import _format_decl
from sdslv2_builder.errors import Diagnostic, json_pointer
from sdslv2_builder.input_hash import InputHashResult, compute_input_hash
from sdslv2_builder.io_atomic import atomic_write_text
from sdslv2_builder.lint import _capture_metadata, _parse_metadata_pairs
from sdslv2_builder.op_yaml import DuplicateKey, load_yaml_with_duplicates
from sdslv2_builder.refs import RELID_RE, parse_contract_ref, parse_internal_ref, parse_ssot_ref

TOOL_NAME = "contract_api_builder"
STAGE = "L1"
DEFAULT_OUT_REL = Path("OUTPUT") / "contract_api.patch"
PROFILE_REL_PATH = Path("policy") / "contract_resolution_profile.yaml"
DECL_KIND_MAP = {
    "structures": "Structure",
    "interfaces": "Interface",
    "functions": "Function",
    "consts": "Const",
    "types": "Type",
}
PLACEHOLDERS = {"none", "null", "tbd", "opaque"}


@dataclass(frozen=True)
class DeclSpec:
    kind: str
    rel_id: str
    decl: str
    bind: str | None
    title: str | None
    desc: str | None
    refs: list[str]
    contract: list[str]
    ssot: list[str]
    path_ref: str


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


def _strip_quotes(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


def _is_placeholder(value: str) -> bool:
    return value.strip().strip('"').strip("'").lower() in PLACEHOLDERS


def _load_profile(project_root: Path, diags: list[Diagnostic]) -> dict[str, object] | None:
    path = project_root / PROFILE_REL_PATH
    if not path.exists():
        _diag(
            diags,
            "E_CONTRACT_API_PROFILE_MISSING",
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
            "E_CONTRACT_API_PROFILE_OUTSIDE_PROJECT",
            "contract profile must be under project_root",
            "project_root/...",
            str(path),
            json_pointer("profile"),
        )
        return None
    if path.is_symlink() or _has_symlink_parent(path, project_root):
        _diag(
            diags,
            "E_CONTRACT_API_PROFILE_SYMLINK",
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
            "E_CONTRACT_API_PROFILE_PARSE_FAILED",
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
                "E_CONTRACT_API_PROFILE_DUPLICATE_KEY",
                "duplicate key in contract profile",
                "unique key",
                dup.key,
                _dup_path(json_pointer("profile"), dup),
            )
        return None
    if not isinstance(data, dict):
        _diag(
            diags,
            "E_CONTRACT_API_PROFILE_INVALID",
            "contract profile must be object",
            "object",
            type(data).__name__,
            json_pointer("profile"),
        )
        return None
    return data


def _collect_decl_ids(text: str) -> set[tuple[str, str]]:
    lines = text.splitlines()
    decl_ids: set[tuple[str, str]] = set()
    for idx, line in enumerate(lines):
        stripped = line.lstrip()
        if not stripped.startswith("@"):
            continue
        kind = stripped.split(None, 1)[0][1:]
        if kind not in {"Structure", "Interface", "Function", "Const", "Type"}:
            continue
        brace_idx = line.find("{")
        if brace_idx == -1:
            continue
        try:
            meta, _ = _capture_metadata(lines, idx, brace_idx)
        except ValueError:
            continue
        pairs = _parse_metadata_pairs(meta)
        meta_map = {k: v for k, v in pairs}
        rel_id = _strip_quotes(meta_map.get("id"))
        if rel_id:
            decl_ids.add((kind, rel_id))
    return decl_ids


def _join_decl_lines(value: object, path_ref: str, diags: list[Diagnostic]) -> str | None:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        lines: list[str] = []
        for idx, item in enumerate(value):
            if isinstance(item, str):
                lines.append(item)
            elif isinstance(item, dict) and "line" in item:
                line_val = item.get("line")
                if isinstance(line_val, str):
                    lines.append(line_val)
                else:
                    _diag(
                        diags,
                        "E_CONTRACT_API_INPUT_INVALID",
                        "decl_lines items must be string",
                        "string",
                        str(line_val),
                        json_pointer(path_ref, "decl_lines", str(idx)),
                    )
                    return None
            else:
                _diag(
                    diags,
                    "E_CONTRACT_API_INPUT_INVALID",
                    "decl_lines items must be string",
                    "string",
                    str(item),
                    json_pointer(path_ref, "decl_lines", str(idx)),
                )
                return None
        return "\n".join(lines)
    return None


def _read_decl_specs(path: Path, diags: list[Diagnostic]) -> tuple[str | None, list[DeclSpec]]:
    try:
        data, duplicates = load_yaml_with_duplicates(path, allow_duplicates=True)
    except Exception as exc:
        _diag(
            diags,
            "E_CONTRACT_API_INPUT_PARSE_FAILED",
            "input must be valid YAML",
            "valid YAML",
            str(exc),
            json_pointer("input"),
        )
        return None, []
    if duplicates:
        for dup in duplicates:
            _diag(
                diags,
                "E_CONTRACT_API_INPUT_DUPLICATE_KEY",
                "duplicate key in input",
                "unique key",
                dup.key,
                _dup_path(json_pointer("input"), dup),
            )
        return None, []

    target: str | None = None
    decl_items: list[dict[str, object]] = []
    if isinstance(data, dict):
        raw_target = data.get("target")
        if isinstance(raw_target, str) and raw_target.strip():
            target = raw_target.strip()
        if "decls" in data and isinstance(data.get("decls"), list):
            decl_items = [item for item in data.get("decls", []) if isinstance(item, dict)]
        else:
            for key, kind in DECL_KIND_MAP.items():
                items = data.get(key)
                if isinstance(items, list):
                    for item in items:
                        if isinstance(item, dict):
                            entry = dict(item)
                            entry.setdefault("kind", kind)
                            decl_items.append(entry)
    elif isinstance(data, list):
        decl_items = [item for item in data if isinstance(item, dict)]
    else:
        _diag(
            diags,
            "E_CONTRACT_API_INPUT_INVALID",
            "input must be list or {decls:[...]}",
            "list",
            type(data).__name__,
            json_pointer("input"),
        )
        return target, []

    specs: list[DeclSpec] = []
    seen_ids: set[tuple[str, str]] = set()
    for idx, item in enumerate(decl_items):
        kind = item.get("kind")
        rel_id = item.get("id")
        bind = item.get("bind")
        title = item.get("title")
        desc = item.get("desc")
        refs = item.get("refs", [])
        contract = item.get("contract", [])
        ssot = item.get("ssot", [])
        path_ref = json_pointer("decls", str(idx))
        if kind is None:
            kind = item.get("kind")
        if not isinstance(kind, str) or kind not in {"Structure", "Interface", "Function", "Const", "Type"}:
            _diag(
                diags,
                "E_CONTRACT_API_INPUT_INVALID",
                "decl kind invalid",
                "Structure|Interface|Function|Const|Type",
                str(kind),
                json_pointer(path_ref, "kind"),
            )
            continue
        if not isinstance(rel_id, str) or not RELID_RE.match(rel_id):
            _diag(
                diags,
                "E_CONTRACT_API_INPUT_INVALID",
                "decl id must be RELID",
                "UPPER_SNAKE_CASE",
                str(rel_id),
                json_pointer(path_ref, "id"),
            )
            continue
        key = (kind, rel_id)
        if key in seen_ids:
            _diag(
                diags,
                "E_CONTRACT_API_INPUT_DUPLICATE",
                "duplicate decl id in input",
                "unique id",
                f"{kind}.{rel_id}",
                json_pointer(path_ref, "id"),
            )
            continue
        seen_ids.add(key)

        decl_value = item.get("decl")
        decl = _join_decl_lines(decl_value, path_ref, diags)
        if decl is None:
            decl_lines = item.get("decl_lines")
            decl = _join_decl_lines(decl_lines, path_ref, diags)
        if not decl or not isinstance(decl, str) or not decl.strip():
            _diag(
                diags,
                "E_CONTRACT_API_INPUT_INVALID",
                "decl is required",
                "non-empty string",
                str(decl_value),
                json_pointer(path_ref, "decl"),
            )
            continue
        if _is_placeholder(decl):
            _diag(
                diags,
                "E_CONTRACT_API_INPUT_INVALID",
                "decl must not be placeholder",
                "non-placeholder",
                decl,
                json_pointer(path_ref, "decl"),
            )
            continue

        bind_value = None
        if bind is not None:
            if not isinstance(bind, str) or not parse_internal_ref(bind):
                _diag(
                    diags,
                    "E_CONTRACT_API_INPUT_INVALID",
                    "bind must be InternalRef",
                    "@Kind.RELID",
                    str(bind),
                    json_pointer(path_ref, "bind"),
                )
                continue
            bind_value = bind
        if title is not None and (not isinstance(title, str) or not title.strip()):
            _diag(
                diags,
                "E_CONTRACT_API_INPUT_INVALID",
                "title must be non-empty string",
                "string",
                str(title),
                json_pointer(path_ref, "title"),
            )
            continue
        if desc is not None and (not isinstance(desc, str) or not desc.strip()):
            _diag(
                diags,
                "E_CONTRACT_API_INPUT_INVALID",
                "desc must be non-empty string",
                "string",
                str(desc),
                json_pointer(path_ref, "desc"),
            )
            continue
        if not isinstance(refs, list) or not all(isinstance(item, str) for item in refs):
            _diag(
                diags,
                "E_CONTRACT_API_INPUT_INVALID",
                "refs must be list[str]",
                "list[str]",
                str(refs),
                json_pointer(path_ref, "refs"),
            )
            continue
        if not isinstance(contract, list) or not all(isinstance(item, str) for item in contract):
            _diag(
                diags,
                "E_CONTRACT_API_INPUT_INVALID",
                "contract must be list[str]",
                "list[str]",
                str(contract),
                json_pointer(path_ref, "contract"),
            )
            continue
        if not isinstance(ssot, list) or not all(isinstance(item, str) for item in ssot):
            _diag(
                diags,
                "E_CONTRACT_API_INPUT_INVALID",
                "ssot must be list[str]",
                "list[str]",
                str(ssot),
                json_pointer(path_ref, "ssot"),
            )
            continue
        specs.append(
            DeclSpec(
                kind=kind,
                rel_id=rel_id,
                decl=decl,
                bind=bind_value,
                title=title,
                desc=desc,
                refs=refs,
                contract=contract,
                ssot=ssot,
                path_ref=path_ref,
            )
        )
    return target, specs


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="Contract API input YAML")
    ap.add_argument("--out", default=None, help="Unified diff output path (default: OUTPUT/contract_api.patch)")
    ap.add_argument("--generator-id", default="contract_api_builder_v0_1", help="generator id")
    ap.add_argument("--project-root", default=None, help="Project root (defaults to repo root)")
    args = ap.parse_args()

    project_root = Path(args.project_root).resolve() if args.project_root else ROOT
    input_path = _resolve_path(project_root, args.input)
    out_path = _resolve_path(project_root, args.out) if args.out else project_root / DEFAULT_OUT_REL
    profile_path = project_root / PROFILE_REL_PATH

    inputs = [_rel_path(project_root, input_path)]
    outputs = [_rel_path(project_root, out_path)]
    diff_paths = [_rel_path(project_root, out_path)]

    diags: list[Diagnostic] = []
    if not input_path.exists():
        _diag(
            diags,
            "E_CONTRACT_API_INPUT_NOT_FOUND",
            "input not found",
            "existing file",
            str(input_path),
            json_pointer("input"),
        )
    if input_path.exists() and input_path.is_dir():
        _diag(
            diags,
            "E_CONTRACT_API_INPUT_IS_DIR",
            "input must be file",
            "file",
            str(input_path),
            json_pointer("input"),
        )
    if input_path.exists() and (input_path.is_symlink() or _has_symlink_parent(input_path, project_root)):
        _diag(
            diags,
            "E_CONTRACT_API_INPUT_SYMLINK",
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
                "E_CONTRACT_API_INPUT_OUTSIDE_PROJECT",
                "input must be under project_root",
                "project_root/...",
                str(input_path),
                json_pointer("input"),
            )

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

    source_rev = _build_source_rev(_git_rev(project_root), args.generator_id)
    profile_diags: list[Diagnostic] = []
    profile = _load_profile(project_root, profile_diags)
    if profile_path.exists():
        inputs.append(_rel_path(project_root, profile_path))
    if profile_diags:
        _emit_result(
            "fail",
            profile_diags,
            inputs,
            outputs,
            diff_paths,
            source_rev=source_rev,
            summary=f"{TOOL_NAME}: profile invalid",
        )
        return 2

    extra_inputs = [input_path]
    if profile_path.exists():
        extra_inputs.append(profile_path)
    try:
        input_hash = compute_input_hash(
            project_root,
            include_decisions=False,
            extra_inputs=extra_inputs,
        )
    except (FileNotFoundError, ValueError, OSError, UnicodeDecodeError) as exc:
        _emit_result(
            "fail",
            [
                Diagnostic(
                    code="E_CONTRACT_API_INPUT_HASH_FAILED",
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

    target_path_raw, specs = _read_decl_specs(input_path, diags)
    if diags:
        _emit_result(
            "fail",
            diags,
            inputs,
            outputs,
            diff_paths,
            source_rev=source_rev,
            input_hash=input_hash,
            summary=f"{TOOL_NAME}: input parse failed",
        )
        return 2
    if not specs:
        _emit_result(
            "fail",
            [
                Diagnostic(
                    code="E_CONTRACT_API_INPUT_EMPTY",
                    message="no declarations in input",
                    expected="decls list",
                    got="empty",
                    path=json_pointer("decls"),
                )
            ],
            inputs,
            outputs,
            diff_paths,
            source_rev=source_rev,
            input_hash=input_hash,
            summary=f"{TOOL_NAME}: no declarations provided",
        )
        return 2
    if not target_path_raw:
        _emit_result(
            "fail",
            [
                Diagnostic(
                    code="E_CONTRACT_API_TARGET_MISSING",
                    message="target contract path required",
                    expected="sdsl2/contract/*.sdsl2",
                    got="missing",
                    path=json_pointer("target"),
                )
            ],
            inputs,
            outputs,
            diff_paths,
            source_rev=source_rev,
            input_hash=input_hash,
            summary=f"{TOOL_NAME}: missing target",
        )
        return 2

    target_path = _resolve_path(project_root, target_path_raw)
    contract_root = project_root / "sdsl2" / "contract"
    try:
        target_path.resolve().relative_to(project_root.resolve())
    except ValueError:
        _emit_result(
            "fail",
            [
                Diagnostic(
                    code="E_CONTRACT_API_TARGET_OUTSIDE_PROJECT",
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
    try:
        target_path.resolve().relative_to(contract_root.resolve())
    except ValueError:
        _emit_result(
            "fail",
            [
                Diagnostic(
                    code="E_CONTRACT_API_TARGET_NOT_CONTRACT",
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
                    code="E_CONTRACT_API_TARGET_SYMLINK",
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
                    code="E_CONTRACT_API_TARGET_NOT_FOUND",
                    message="target contract file not found",
                    expected="existing sdsl2/contract file",
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
            next_actions=[
                "tool:contract_scaffold_gen --out sdsl2/contract/<file>.sdsl2 --id-prefix <ID_PREFIX>",
            ],
        )
        return 2

    try:
        old_text = target_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        _emit_result(
            "fail",
            [
                Diagnostic(
                    code="E_CONTRACT_API_READ_FAILED",
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

    existing_ids = _collect_decl_ids(old_text)
    new_decls: list[Decl] = []
    for spec in specs:
        if (spec.kind, spec.rel_id) in existing_ids:
            continue
        bind_ref = parse_internal_ref(spec.bind) if spec.bind else None
        if spec.bind and not bind_ref:
            _diag(
                diags,
                "E_CONTRACT_API_INPUT_INVALID",
                "bind must be InternalRef",
                "@Kind.RELID",
                spec.bind,
                spec.path_ref,
            )
            continue
        ref_items = []
        for ref in spec.refs:
            parsed = parse_internal_ref(ref)
            if not parsed:
                _diag(
                    diags,
                    "E_CONTRACT_API_INPUT_INVALID",
                    "refs must be InternalRef",
                    "@Kind.RELID",
                    ref,
                    spec.path_ref,
                )
                continue
            ref_items.append(parsed)
        contract_items = []
        for ref in spec.contract:
            parsed = parse_contract_ref(ref)
            if not parsed:
                _diag(
                    diags,
                    "E_CONTRACT_API_INPUT_INVALID",
                    "contract must be CONTRACT.*",
                    "CONTRACT.*",
                    ref,
                    spec.path_ref,
                )
                continue
            contract_items.append(parsed)
        ssot_items = []
        for ref in spec.ssot:
            parsed = parse_ssot_ref(ref)
            if not parsed:
                _diag(
                    diags,
                    "E_CONTRACT_API_INPUT_INVALID",
                    "ssot must be SSOT.*",
                    "SSOT.*",
                    ref,
                    spec.path_ref,
                )
                continue
            ssot_items.append(parsed)
        new_decls.append(
            Decl(
                kind=spec.kind,
                rel_id=spec.rel_id,
                decl=spec.decl,
                bind=bind_ref,
                title=spec.title,
                desc=spec.desc,
                refs=ref_items,
                contract=contract_items,
                ssot=ssot_items,
            )
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
            summary=f"{TOOL_NAME}: input validation failed",
        )
        return 2
    if not new_decls:
        _emit_result(
            "fail",
            [
                Diagnostic(
                    code="E_CONTRACT_API_NO_CHANGE",
                    message="no contract updates required",
                    expected="missing declarations",
                    got="no change",
                    path=json_pointer("decls"),
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

    new_lines = old_text.rstrip().splitlines()
    if new_lines:
        new_lines.append("")
    for decl in sorted(new_decls, key=lambda item: (item.kind, item.rel_id)):
        new_lines.extend(_format_decl(decl))
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
                    code="E_CONTRACT_API_NO_CHANGE",
                    message="no contract updates required",
                    expected="missing declarations",
                    got="no change",
                    path=json_pointer("decls"),
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
                    code="E_CONTRACT_API_OUTSIDE_PROJECT",
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
                    code="E_CONTRACT_API_OUT_IS_DIR",
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
                    code="E_CONTRACT_API_OUT_SYMLINK",
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
                    code="E_CONTRACT_API_OUT_SYMLINK_PARENT",
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
        atomic_write_text(out_path, output + "\n", symlink_code="E_CONTRACT_API_OUT_SYMLINK")
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
