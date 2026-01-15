#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ruff: noqa: E402

from __future__ import annotations

import argparse
import difflib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sdslv2_builder.errors import Diagnostic, json_pointer
from sdslv2_builder.input_hash import compute_input_hash
from sdslv2_builder.intent_schema import normalize_intent
from sdslv2_builder.io_atomic import atomic_write_text
from sdslv2_builder.op_yaml import DuplicateKey, dump_yaml, load_yaml, load_yaml_with_duplicates
from sdslv2_builder.refs import parse_contract_ref

TOOL_NAME = "decisions_from_intent_gen"
STAGE = "L1"
DEFAULT_OUT_REL = Path("OUTPUT") / "decisions_edges.patch"


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


def _emit_result(
    status: str,
    diags: list[Diagnostic],
    inputs: list[str],
    outputs: list[str],
    diff_paths: list[str],
    source_rev: str | None = None,
    input_hash: str | None = None,
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
        "input_hash": input_hash,
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


def _build_source_link(
    user_link: str,
    generator_id: str,
    source_rev: str,
    input_hash: str,
) -> str:
    parts = [f"gen:{generator_id}", f"rev:{source_rev}", f"input:{input_hash}"]
    link = user_link.strip()
    if link and link != "UNSPECIFIED":
        parts.append(f"link:{link}")
    return ";".join(parts)


def _dup_path(prefix: str, dup: DuplicateKey) -> str:
    if prefix:
        if dup.path:
            return prefix + dup.path
        return prefix
    return dup.path


def _load_contract_map(path: Path, project_root: Path, diags: list[Diagnostic]) -> dict[str, list[str]]:
    mapping: dict[str, list[str]] = {}
    if not path.exists():
        _diag(
            diags,
            "E_DECISIONS_FROM_INTENT_MAP_NOT_FOUND",
            "contract map not found",
            "existing file",
            str(path),
            json_pointer("contract_map"),
        )
        return mapping
    if path.is_dir():
        _diag(
            diags,
            "E_DECISIONS_FROM_INTENT_MAP_IS_DIR",
            "contract map must be file",
            "file",
            str(path),
            json_pointer("contract_map"),
        )
        return mapping
    if path.is_symlink() or _has_symlink_parent(path, project_root):
        _diag(
            diags,
            "E_DECISIONS_FROM_INTENT_MAP_SYMLINK",
            "contract map must not be symlink",
            "non-symlink",
            str(path),
            json_pointer("contract_map"),
        )
        return mapping
    try:
        data, duplicates = load_yaml_with_duplicates(path, allow_duplicates=True)
    except Exception as exc:
        _diag(
            diags,
            "E_DECISIONS_FROM_INTENT_MAP_PARSE_FAILED",
            "contract map must be valid YAML",
            "valid YAML",
            str(exc),
            json_pointer("contract_map"),
        )
        return mapping
    if duplicates:
        for dup in duplicates:
            _diag(
                diags,
                "E_DECISIONS_FROM_INTENT_MAP_DUPLICATE_KEY",
                "duplicate key in contract map",
                "unique key",
                dup.key,
                _dup_path(json_pointer("contract_map"), dup),
            )
        return mapping

    items: list[dict[str, object]] = []
    if isinstance(data, dict) and "edges" in data and isinstance(data.get("edges"), list):
        items = [item for item in data["edges"] if isinstance(item, dict)]
    elif isinstance(data, list):
        items = [item for item in data if isinstance(item, dict)]
    elif isinstance(data, dict):
        for edge_id, refs in data.items():
            items.append({"id": edge_id, "contract_refs": refs})

    seen_ids: set[str] = set()
    for idx, item in enumerate(items):
        edge_id = item.get("id")
        if not isinstance(edge_id, str) or not edge_id.strip():
            _diag(
                diags,
                "E_DECISIONS_FROM_INTENT_MAP_ID_INVALID",
                "edge id must be non-empty string",
                "string",
                str(edge_id),
                json_pointer("contract_map", str(idx), "id"),
            )
            continue
        if edge_id in seen_ids:
            _diag(
                diags,
                "E_DECISIONS_FROM_INTENT_MAP_ID_DUPLICATE",
                "duplicate edge id in contract map",
                "unique id",
                edge_id,
                json_pointer("contract_map", str(idx), "id"),
            )
            continue
        seen_ids.add(edge_id)
        raw_refs = item.get("contract_refs")
        if not isinstance(raw_refs, list):
            _diag(
                diags,
                "E_DECISIONS_FROM_INTENT_MAP_REFS_INVALID",
                "contract_refs must be list",
                "list",
                type(raw_refs).__name__,
                json_pointer("contract_map", str(idx), "contract_refs"),
            )
            continue
        refs: list[str] = []
        for ref_idx, ref in enumerate(raw_refs):
            if not isinstance(ref, str) or not parse_contract_ref(ref):
                _diag(
                    diags,
                    "E_DECISIONS_FROM_INTENT_MAP_REFS_INVALID",
                    "contract_refs must be CONTRACT.* tokens",
                    "CONTRACT.*",
                    str(ref),
                    json_pointer("contract_map", str(idx), "contract_refs", str(ref_idx)),
                )
                continue
            refs.append(ref)
        if refs:
            mapping[edge_id] = sorted(set(refs))
    return mapping


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="Intent YAML file or dir")
    ap.add_argument("--target", default="decisions/edges.yaml", help="Decisions target path")
    ap.add_argument(
        "--out",
        default=None,
        help="Unified diff output path (default: OUTPUT/decisions_edges.patch)",
    )
    ap.add_argument("--contract-map", default=None, help="YAML map of edge id -> contract_refs")
    ap.add_argument("--omit-without-contract", action="store_true", help="Omit edges with no contract_refs")
    ap.add_argument(
        "--allow-empty-contract-refs",
        action="store_true",
        help="Allow empty contract_refs (default: fail on missing)",
    )
    ap.add_argument("--allow-empty", action="store_true", help="Allow empty edge list")
    ap.add_argument("--author", default="UNSPECIFIED", help="provenance.author")
    ap.add_argument("--reviewed-by", default="UNSPECIFIED", help="provenance.reviewed_by")
    ap.add_argument("--source-link", default="UNSPECIFIED", help="provenance.source_link")
    ap.add_argument("--generator-id", default="decisions_from_intent_gen_v0_1", help="generator id")
    ap.add_argument("--schema-version", default="1.0", help="decisions schema_version")
    ap.add_argument("--project-root", default=None, help="Project root (defaults to repo root)")
    args = ap.parse_args()

    project_root = Path(args.project_root).resolve() if args.project_root else ROOT
    intent_root = project_root / "drafts" / "intent"
    input_path = _resolve_path(project_root, args.input)
    out_path = _resolve_path(project_root, args.out) if args.out else project_root / DEFAULT_OUT_REL
    inputs = [_rel_path(project_root, input_path)]
    outputs = [_rel_path(project_root, out_path)]
    diff_paths = [_rel_path(project_root, out_path)]

    if intent_root.is_symlink() or _has_symlink_parent(intent_root, project_root):
        _emit_result(
            "fail",
            [
                Diagnostic(
                    code="E_DECISIONS_FROM_INTENT_INTENT_ROOT_SYMLINK",
                    message="drafts/intent must not be symlink",
                    expected="non-symlink",
                    got=str(intent_root),
                    path=json_pointer("input"),
                )
            ],
            inputs,
            outputs,
            diff_paths,
            summary=f"{TOOL_NAME}: input root invalid",
        )
        return 2

    if not input_path.exists():
        _emit_result(
            "fail",
            [
                Diagnostic(
                    code="E_DECISIONS_FROM_INTENT_INPUT_NOT_FOUND",
                    message="intent input not found",
                    expected="existing file or dir",
                    got=str(input_path),
                    path=json_pointer("input"),
                )
            ],
            inputs,
            outputs,
            diff_paths,
            summary=f"{TOOL_NAME}: input not found",
        )
        return 2
    if input_path.is_symlink() or _has_symlink_parent(input_path, project_root):
        _emit_result(
            "fail",
            [
                Diagnostic(
                    code="E_DECISIONS_FROM_INTENT_INPUT_SYMLINK",
                    message="intent input must not be symlink",
                    expected="non-symlink",
                    got=str(input_path),
                    path=json_pointer("input"),
                )
            ],
            inputs,
            outputs,
            diff_paths,
            summary=f"{TOOL_NAME}: input symlink blocked",
        )
        return 2
    try:
        input_path.resolve().relative_to(intent_root.resolve())
    except ValueError:
        _emit_result(
            "fail",
            [
                Diagnostic(
                    code="E_DECISIONS_FROM_INTENT_INPUT_NOT_INTENT_ROOT",
                    message="intent input must be under drafts/intent",
                    expected="drafts/intent/...",
                    got=str(input_path),
                    path=json_pointer("input"),
                )
            ],
            inputs,
            outputs,
            diff_paths,
            summary=f"{TOOL_NAME}: input out of scope",
        )
        return 2

    intent_paths: list[Path] = []
    if input_path.is_dir():
        for path in sorted(input_path.rglob("*.yaml")):
            if path.is_file():
                if path.is_symlink() or _has_symlink_parent(path, intent_root):
                    _emit_result(
                        "fail",
                        [
                            Diagnostic(
                                code="E_DECISIONS_FROM_INTENT_INPUT_SYMLINK",
                                message="intent input must not be symlink",
                                expected="non-symlink",
                                got=str(path),
                                path=json_pointer("input"),
                            )
                        ],
                        inputs,
                        outputs,
                        diff_paths,
                        summary=f"{TOOL_NAME}: input symlink blocked",
                    )
                    return 2
                intent_paths.append(path)
    else:
        intent_paths = [input_path]

    if not intent_paths:
        _emit_result(
            "fail",
            [
                Diagnostic(
                    code="E_DECISIONS_FROM_INTENT_INPUT_EMPTY",
                    message="no intent files found",
                    expected="*.yaml",
                    got=str(input_path),
                    path=json_pointer("input"),
                )
            ],
            inputs,
            outputs,
            diff_paths,
            summary=f"{TOOL_NAME}: input empty",
        )
        return 2

    diags: list[Diagnostic] = []
    contract_map: dict[str, list[str]] = {}
    map_path: Path | None = None
    inputs = [_rel_path(project_root, path) for path in intent_paths]
    if args.contract_map:
        map_path = _resolve_path(project_root, args.contract_map)
        try:
            map_path.resolve().relative_to(project_root.resolve())
        except ValueError:
            _diag(
                diags,
                "E_DECISIONS_FROM_INTENT_MAP_OUTSIDE_PROJECT",
                "contract map must be under project_root",
                "project_root/...",
                str(map_path),
                json_pointer("contract_map"),
            )
        else:
            contract_map = _load_contract_map(map_path, project_root, diags)
        inputs.append(_rel_path(project_root, map_path))
    if not args.contract_map and not args.allow_empty_contract_refs and not args.omit_without_contract:
        _diag(
            diags,
            "E_DECISIONS_FROM_INTENT_CONTRACT_MAP_REQUIRED",
            "contract map required (or allow empty contract_refs)",
            "contract_map",
            "missing",
            json_pointer("contract_map"),
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

    try:
        extra_inputs = list(intent_paths)
        if map_path is not None:
            extra_inputs.append(map_path)
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
                    code="E_DECISIONS_FROM_INTENT_INPUT_HASH_FAILED",
                    message="input_hash calculation failed",
                    expected="valid inputs",
                    got=str(exc),
                    path=json_pointer("input_hash"),
                )
            ],
            inputs,
            outputs,
            diff_paths,
            summary=f"{TOOL_NAME}: input_hash failed",
        )
        return 2

    source_rev = _git_rev(project_root)
    source_link = _build_source_link(
        args.source_link,
        args.generator_id,
        source_rev,
        input_hash.input_hash,
    )

    edges: list[dict[str, object]] = []
    scope_value: dict[str, object] | None = None
    seen_edge_ids: set[str] = set()
    for path in intent_paths:
        path_label = path.name
        try:
            data = load_yaml(path)
        except Exception as exc:
            _diag(
                diags,
                "E_DECISIONS_FROM_INTENT_PARSE_FAILED",
                "intent must be valid YAML",
                "valid YAML",
                str(exc),
                json_pointer("input", path.name),
            )
            continue
        if not isinstance(data, dict):
            _diag(
                diags,
                "E_DECISIONS_FROM_INTENT_INVALID",
                "intent root must be object",
                "object",
                type(data).__name__,
                json_pointer("input", path.name),
            )
            continue
        normalized, intent_diags = normalize_intent(data, fill_missing=False)
        if intent_diags:
            diags.extend(intent_diags)
            continue
        scope = normalized.get("scope")
        if scope_value is None:
            scope_value = scope
        elif scope_value != scope:
            _diag(
                diags,
                "E_DECISIONS_FROM_INTENT_SCOPE_MISMATCH",
                "intent scopes must match",
                "single scope",
                json.dumps(scope, ensure_ascii=False),
                json_pointer("input", path_label, "scope"),
            )
            continue
        for idx, intent in enumerate(normalized.get("edge_intents_proposed", [])):
            if not isinstance(intent, dict):
                _diag(
                    diags,
                    "E_DECISIONS_FROM_INTENT_INVALID",
                    "edge_intents_proposed entries must be object",
                    "object",
                    type(intent).__name__,
                    json_pointer("input", path_label, "edge_intents_proposed", str(idx)),
                )
                continue
            edge_id = intent.get("id", "")
            from_id = intent.get("from", "")
            to_id = intent.get("to", "")
            direction = intent.get("direction")
            if edge_id in seen_edge_ids:
                _diag(
                    diags,
                    "E_DECISIONS_FROM_INTENT_DUPLICATE_ID",
                    "duplicate edge_intents_proposed id",
                    "unique id",
                    edge_id,
                    json_pointer("input", path_label, "edge_intents_proposed", str(idx), "id"),
                )
                continue
            seen_edge_ids.add(edge_id)
            if not direction:
                _diag(
                    diags,
                    "E_DECISIONS_FROM_INTENT_DIRECTION_MISSING",
                    "direction is required for decisions",
                    "direction value",
                    "missing",
                    json_pointer("input", path_label, "edge_intents_proposed", str(idx), "direction"),
                )
                continue
            contract_refs = contract_map.get(edge_id, [])
            if not contract_refs and args.omit_without_contract:
                continue
            if not contract_refs and not args.allow_empty_contract_refs:
                _diag(
                    diags,
                    "E_DECISIONS_FROM_INTENT_CONTRACT_MISSING",
                    "contract_refs required for decisions edge",
                    "contract_refs",
                    edge_id,
                    json_pointer("contract_map", edge_id),
                )
                continue
            edges.append(
                {
                    "id": edge_id,
                    "from": from_id,
                    "to": to_id,
                    "direction": direction,
                    "contract_refs": contract_refs,
                }
            )

    if diags:
        _emit_result(
            "fail",
            diags,
            inputs,
            outputs,
            diff_paths,
            source_rev=source_rev,
            input_hash=input_hash.input_hash,
            summary=f"{TOOL_NAME}: intent processing failed",
        )
        return 2
    if scope_value is None:
        _emit_result(
            "fail",
            [
                Diagnostic(
                    code="E_DECISIONS_FROM_INTENT_SCOPE_MISSING",
                    message="scope missing from intents",
                    expected="scope",
                    got="missing",
                    path=json_pointer("scope"),
                )
            ],
            inputs,
            outputs,
            diff_paths,
            source_rev=source_rev,
            input_hash=input_hash.input_hash,
            summary=f"{TOOL_NAME}: scope missing",
        )
        return 2

    edges_sorted = sorted(edges, key=lambda e: str(e.get("id", "")))
    if not edges_sorted and not args.allow_empty:
        _emit_result(
            "fail",
            [
                Diagnostic(
                    code="E_DECISIONS_FROM_INTENT_EMPTY",
                    message="no edges generated",
                    expected="edge_intents_proposed",
                    got="empty",
                    path=json_pointer("edges"),
                )
            ],
            inputs,
            outputs,
            diff_paths,
            source_rev=source_rev,
            input_hash=input_hash.input_hash,
            summary=f"{TOOL_NAME}: no edges",
        )
        return 2

    decisions = {
        "schema_version": args.schema_version,
        "provenance": {
            "author": args.author,
            "reviewed_by": args.reviewed_by,
            "source_link": source_link,
        },
        "scope": scope_value,
        "edges": edges_sorted,
    }

    target_path = _resolve_path(project_root, args.target)
    try:
        target_path.resolve().relative_to((project_root / "decisions").resolve())
    except ValueError:
        _emit_result(
            "fail",
            [
                Diagnostic(
                    code="E_DECISIONS_FROM_INTENT_TARGET_NOT_DECISIONS",
                    message="target must be under decisions/",
                    expected="decisions/...",
                    got=str(target_path),
                    path=json_pointer("target"),
                )
            ],
            inputs,
            outputs,
            diff_paths,
            source_rev=source_rev,
            input_hash=input_hash.input_hash,
            summary=f"{TOOL_NAME}: invalid target",
        )
        return 2
    if target_path.exists() and target_path.is_symlink():
        _emit_result(
            "fail",
            [
                Diagnostic(
                    code="E_DECISIONS_FROM_INTENT_TARGET_SYMLINK",
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
            input_hash=input_hash.input_hash,
            summary=f"{TOOL_NAME}: invalid target",
        )
        return 2
    if _has_symlink_parent(target_path, project_root):
        _emit_result(
            "fail",
            [
                Diagnostic(
                    code="E_DECISIONS_FROM_INTENT_TARGET_SYMLINK_PARENT",
                    message="target parent must not be symlink",
                    expected="non-symlink",
                    got=str(target_path),
                    path=json_pointer("target"),
                )
            ],
            inputs,
            outputs,
            diff_paths,
            source_rev=source_rev,
            input_hash=input_hash.input_hash,
            summary=f"{TOOL_NAME}: invalid target",
        )
        return 2

    old_text = ""
    if target_path.exists():
        try:
            old_text = target_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            _emit_result(
                "fail",
                [
                    Diagnostic(
                        code="E_DECISIONS_FROM_INTENT_TARGET_READ_FAILED",
                        message="target must be readable UTF-8",
                        expected="readable UTF-8 file",
                        got=str(exc),
                        path=json_pointer("target"),
                    )
                ],
                inputs,
                outputs,
                diff_paths,
                source_rev=source_rev,
                input_hash=input_hash.input_hash,
                summary=f"{TOOL_NAME}: target read failed",
            )
            return 2
    new_text = dump_yaml(decisions)
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
            "diag",
            [
                Diagnostic(
                    code="E_DECISIONS_FROM_INTENT_NO_CHANGE",
                    message="no change in decisions",
                    expected="diff",
                    got="no change",
                    path=json_pointer("target"),
                )
            ],
            inputs,
            outputs,
            diff_paths,
            source_rev=source_rev,
            input_hash=input_hash.input_hash,
            summary=f"{TOOL_NAME}: no changes required",
        )
        return 0

    try:
        out_path.resolve().relative_to(project_root.resolve())
    except ValueError:
        _emit_result(
            "fail",
            [
                Diagnostic(
                    code="E_DECISIONS_FROM_INTENT_OUTSIDE_PROJECT",
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
            input_hash=input_hash.input_hash,
            summary=f"{TOOL_NAME}: invalid output path",
        )
        return 2
    if out_path.exists() and out_path.is_dir():
        _emit_result(
            "fail",
            [
                Diagnostic(
                    code="E_DECISIONS_FROM_INTENT_OUT_IS_DIR",
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
            input_hash=input_hash.input_hash,
            summary=f"{TOOL_NAME}: invalid output path",
        )
        return 2
    if out_path.exists() and out_path.is_symlink():
        _emit_result(
            "fail",
            [
                Diagnostic(
                    code="E_DECISIONS_FROM_INTENT_OUT_SYMLINK",
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
            input_hash=input_hash.input_hash,
            summary=f"{TOOL_NAME}: invalid output path",
        )
        return 2
    if _has_symlink_parent(out_path, project_root):
        _emit_result(
            "fail",
            [
                Diagnostic(
                    code="E_DECISIONS_FROM_INTENT_OUT_SYMLINK_PARENT",
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
            input_hash=input_hash.input_hash,
            summary=f"{TOOL_NAME}: invalid output path",
        )
        return 2
    out_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        atomic_write_text(out_path, output + "\n", symlink_code="E_DECISIONS_FROM_INTENT_OUT_SYMLINK")
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
            input_hash=input_hash.input_hash,
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
        input_hash=input_hash.input_hash,
        summary=f"{TOOL_NAME}: diff written",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
