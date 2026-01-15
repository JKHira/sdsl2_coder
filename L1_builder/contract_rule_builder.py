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

from sdslv2_builder.contract import Rule
from sdslv2_builder.contract_writer import _format_rule
from sdslv2_builder.errors import Diagnostic, json_pointer
from sdslv2_builder.input_hash import InputHashResult, compute_input_hash
from sdslv2_builder.io_atomic import atomic_write_text
from sdslv2_builder.lint import _capture_metadata, _parse_metadata_pairs
from sdslv2_builder.op_yaml import DuplicateKey, load_yaml_with_duplicates
from sdslv2_builder.refs import RELID_RE, parse_contract_ref, parse_internal_ref, parse_ssot_ref

TOOL_NAME = "contract_rule_builder"
STAGE = "L1"
DEFAULT_OUT_REL = Path("OUTPUT") / "contract_rules.patch"
DEFAULT_RULE_BIND_KINDS = {"Interface", "Function", "Structure", "Type", "Const"}
PROFILE_REL_PATH = Path("policy") / "contract_resolution_profile.yaml"


@dataclass(frozen=True)
class RuleSpec:
    rel_id: str
    bind: str
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


def _collect_rule_ids(text: str) -> set[str]:
    lines = text.splitlines()
    rule_ids: set[str] = set()
    for idx, line in enumerate(lines):
        stripped = line.lstrip()
        if not stripped.startswith("@Rule"):
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
            rule_ids.add(rel_id)
    return rule_ids


def _load_profile(project_root: Path, diags: list[Diagnostic]) -> dict[str, object] | None:
    path = project_root / PROFILE_REL_PATH
    if not path.exists():
        _diag(
            diags,
            "E_CONTRACT_RULE_PROFILE_MISSING",
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
            "E_CONTRACT_RULE_PROFILE_OUTSIDE_PROJECT",
            "contract profile must be under project_root",
            "project_root/...",
            str(path),
            json_pointer("profile"),
        )
        return None
    if path.is_symlink() or _has_symlink_parent(path, project_root):
        _diag(
            diags,
            "E_CONTRACT_RULE_PROFILE_SYMLINK",
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
            "E_CONTRACT_RULE_PROFILE_PARSE_FAILED",
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
                "E_CONTRACT_RULE_PROFILE_DUPLICATE_KEY",
                "duplicate key in contract profile",
                "unique key",
                dup.key,
                _dup_path(json_pointer("profile"), dup),
            )
        return None
    if not isinstance(data, dict):
        _diag(
            diags,
            "E_CONTRACT_RULE_PROFILE_INVALID",
            "contract profile must be object",
            "object",
            type(data).__name__,
            json_pointer("profile"),
        )
        return None
    return data


def _read_rule_prefix_bindings(profile: dict[str, object] | None) -> dict[str, list[str]]:
    if not profile:
        return {}
    rule_naming = profile.get("rule_naming")
    if not isinstance(rule_naming, dict):
        return {}
    raw = rule_naming.get("prefix_bindings")
    if not isinstance(raw, dict):
        return {}
    bindings: dict[str, list[str]] = {}
    for key, value in raw.items():
        if not isinstance(key, str) or not isinstance(value, list):
            continue
        kinds = [item for item in value if isinstance(item, str)]
        if kinds:
            bindings[key] = kinds
    return bindings


def _dedupe_list(items: list[object]) -> tuple[list[object], bool]:
    seen: set[object] = set()
    deduped: list[object] = []
    duplicate = False
    for item in items:
        if item in seen:
            duplicate = True
            continue
        seen.add(item)
        deduped.append(item)
    return deduped, duplicate


def _read_rule_specs(path: Path, diags: list[Diagnostic]) -> tuple[str | None, list[RuleSpec]]:
    try:
        data, duplicates = load_yaml_with_duplicates(path, allow_duplicates=True)
    except Exception as exc:
        _diag(
            diags,
            "E_CONTRACT_RULE_INPUT_PARSE_FAILED",
            "rule input must be valid YAML",
            "valid YAML",
            str(exc),
            json_pointer("rules"),
        )
        return None, []
    if duplicates:
        for dup in duplicates:
            _diag(
                diags,
                "E_CONTRACT_RULE_INPUT_DUPLICATE_KEY",
                "duplicate key in rule input",
                "unique key",
                dup.key,
                _dup_path(json_pointer("rules"), dup),
            )
        return None, []

    target: str | None = None
    rules: list[dict[str, object]] = []
    if isinstance(data, dict):
        raw_target = data.get("target")
        if isinstance(raw_target, str) and raw_target.strip():
            target = raw_target.strip()
        raw_rules = data.get("rules")
        if isinstance(raw_rules, list):
            rules = [item for item in raw_rules if isinstance(item, dict)]
    elif isinstance(data, list):
        rules = [item for item in data if isinstance(item, dict)]
    else:
        _diag(
            diags,
            "E_CONTRACT_RULE_INPUT_INVALID",
            "rule input must be list or {rules:[...]}",
            "list",
            type(data).__name__,
            json_pointer("rules"),
        )
        return target, []

    specs: list[RuleSpec] = []
    seen_ids: set[str] = set()
    for idx, item in enumerate(rules):
        rel_id = item.get("id")
        bind = item.get("bind")
        refs = item.get("refs", [])
        contract = item.get("contract", [])
        ssot = item.get("ssot", [])
        path_ref = json_pointer("rules", str(idx))

        if not isinstance(rel_id, str) or not RELID_RE.match(rel_id):
            _diag(
                diags,
                "E_CONTRACT_RULE_INPUT_INVALID",
                "rule id must be RELID",
                "UPPER_SNAKE_CASE",
                str(rel_id),
                json_pointer("rules", str(idx), "id"),
            )
            continue
        if rel_id in seen_ids:
            _diag(
                diags,
                "E_CONTRACT_RULE_INPUT_DUPLICATE",
                "duplicate rule id in input",
                "unique id",
                rel_id,
                json_pointer("rules", str(idx), "id"),
            )
            continue
        seen_ids.add(rel_id)
        if not isinstance(bind, str) or not parse_internal_ref(bind):
            _diag(
                diags,
                "E_CONTRACT_RULE_INPUT_INVALID",
                "bind must be InternalRef",
                "@Kind.RELID",
                str(bind),
                json_pointer("rules", str(idx), "bind"),
            )
            continue
        if refs is None:
            refs = []
        if contract is None:
            contract = []
        if ssot is None:
            ssot = []
        if not isinstance(refs, list) or not all(isinstance(item, str) for item in refs):
            _diag(
                diags,
                "E_CONTRACT_RULE_INPUT_INVALID",
                "refs must be list[str]",
                "list[str]",
                str(refs),
                json_pointer("rules", str(idx), "refs"),
            )
            continue
        if not isinstance(contract, list) or not all(isinstance(item, str) for item in contract):
            _diag(
                diags,
                "E_CONTRACT_RULE_INPUT_INVALID",
                "contract must be list[str]",
                "list[str]",
                str(contract),
                json_pointer("rules", str(idx), "contract"),
            )
            continue
        if not isinstance(ssot, list) or not all(isinstance(item, str) for item in ssot):
            _diag(
                diags,
                "E_CONTRACT_RULE_INPUT_INVALID",
                "ssot must be list[str]",
                "list[str]",
                str(ssot),
                json_pointer("rules", str(idx), "ssot"),
            )
            continue
        specs.append(
            RuleSpec(
                rel_id=rel_id,
                bind=bind,
                refs=refs,
                contract=contract,
                ssot=ssot,
                path_ref=path_ref,
            )
        )
    return target, specs


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="Rule input YAML")
    ap.add_argument("--out", default=None, help="Unified diff output path (default: OUTPUT/contract_rules.patch)")
    ap.add_argument("--generator-id", default="contract_rule_builder_v0_1", help="generator id")
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
            "E_CONTRACT_RULE_INPUT_NOT_FOUND",
            "input not found",
            "existing file",
            str(input_path),
            json_pointer("input"),
        )
    if input_path.exists() and input_path.is_dir():
        _diag(
            diags,
            "E_CONTRACT_RULE_INPUT_IS_DIR",
            "input must be file",
            "file",
            str(input_path),
            json_pointer("input"),
        )
    if input_path.exists() and (input_path.is_symlink() or _has_symlink_parent(input_path, project_root)):
        _diag(
            diags,
            "E_CONTRACT_RULE_INPUT_SYMLINK",
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
                "E_CONTRACT_RULE_INPUT_OUTSIDE_PROJECT",
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
    prefix_bindings = _read_rule_prefix_bindings(profile)
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
                    code="E_CONTRACT_RULE_INPUT_HASH_FAILED",
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

    target_path_raw, specs = _read_rule_specs(input_path, diags)
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
                    code="E_CONTRACT_RULE_INPUT_EMPTY",
                    message="no rules in input",
                    expected="rules list",
                    got="empty",
                    path=json_pointer("rules"),
                )
            ],
            inputs,
            outputs,
            diff_paths,
            source_rev=source_rev,
            input_hash=input_hash,
            summary=f"{TOOL_NAME}: no rules provided",
        )
        return 2

    if not target_path_raw:
        _emit_result(
            "fail",
            [
                Diagnostic(
                    code="E_CONTRACT_RULE_TARGET_MISSING",
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
    try:
        target_path.resolve().relative_to(project_root.resolve())
    except ValueError:
        _emit_result(
            "fail",
            [
                Diagnostic(
                    code="E_CONTRACT_RULE_TARGET_OUTSIDE_PROJECT",
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
                    code="E_CONTRACT_RULE_TARGET_NOT_CONTRACT",
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
                    code="E_CONTRACT_RULE_TARGET_SYMLINK",
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
                    code="E_CONTRACT_RULE_TARGET_NOT_FOUND",
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
                    code="E_CONTRACT_RULE_READ_FAILED",
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

    existing_rule_ids = _collect_rule_ids(old_text)
    new_rules: list[Rule] = []
    for spec in specs:
        if spec.rel_id in existing_rule_ids:
            continue
        bind_ref = parse_internal_ref(spec.bind)
        if not bind_ref:
            _diag(
                diags,
                "E_CONTRACT_RULE_INPUT_INVALID",
                "bind must be InternalRef",
                "@Kind.RELID",
                spec.bind,
                spec.path_ref,
            )
            continue
        allowed_kinds = DEFAULT_RULE_BIND_KINDS
        matched_prefix = None
        for prefix in sorted(prefix_bindings.keys(), key=len, reverse=True):
            if spec.rel_id.startswith(prefix):
                matched_prefix = prefix
                break
        if matched_prefix:
            allowed_kinds = set(prefix_bindings.get(matched_prefix, [])) or DEFAULT_RULE_BIND_KINDS
        if bind_ref.kind not in allowed_kinds:
            _diag(
                diags,
                "E_CONTRACT_RULE_BIND_KIND_INVALID",
                "bind kind not allowed for rule id",
                ",".join(sorted(allowed_kinds)),
                bind_ref.kind,
                spec.path_ref,
            )
            continue
        ref_items = []
        ref_values = spec.refs if isinstance(spec.refs, list) else []
        ref_values, dup_refs = _dedupe_list(ref_values)
        if dup_refs:
            _diag(
                diags,
                "E_CONTRACT_RULE_REFS_DUPLICATE",
                "refs must be unique",
                "unique refs",
                "duplicate",
                spec.path_ref,
            )
        for ref in ref_values:
            parsed = parse_internal_ref(ref)
            if not parsed:
                _diag(
                    diags,
                    "E_CONTRACT_RULE_INPUT_INVALID",
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
                    "E_CONTRACT_RULE_INPUT_INVALID",
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
                    "E_CONTRACT_RULE_INPUT_INVALID",
                    "ssot must be SSOT.*",
                    "SSOT.*",
                    ref,
                    spec.path_ref,
                )
                continue
            ssot_items.append(parsed)
        new_rules.append(
            Rule(
                rel_id=spec.rel_id,
                bind=bind_ref,
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

    if not new_rules:
        _emit_result(
            "fail",
            [
                Diagnostic(
                    code="E_CONTRACT_RULE_NO_CHANGE",
                    message="no rule updates required",
                    expected="missing rules",
                    got="no change",
                    path=json_pointer("rules"),
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
    for rule in sorted(new_rules, key=lambda item: item.rel_id):
        new_lines.extend(_format_rule(rule))
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
                    code="E_CONTRACT_RULE_NO_CHANGE",
                    message="no rule updates required",
                    expected="missing rules",
                    got="no change",
                    path=json_pointer("rules"),
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
                    code="E_CONTRACT_RULE_OUTSIDE_PROJECT",
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
                    code="E_CONTRACT_RULE_OUT_IS_DIR",
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
                    code="E_CONTRACT_RULE_OUT_SYMLINK",
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
                    code="E_CONTRACT_RULE_OUT_SYMLINK_PARENT",
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
        atomic_write_text(out_path, output + "\n", symlink_code="E_CONTRACT_RULE_OUT_SYMLINK")
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
