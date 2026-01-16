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
from sdslv2_builder.lint import DIRECTION_VOCAB
from sdslv2_builder.op_yaml import DuplicateKey, dump_yaml, load_yaml_with_duplicates
from sdslv2_builder.refs import RELID_RE

TOOL_NAME = "intent_edge_builder"
STAGE = "L1"
DEFAULT_OUT_REL = Path("OUTPUT") / "intent_edge.patch"

PLACEHOLDERS = {"none", "null", "tbd", "opaque"}
EDGE_FIELDS = {"id", "from", "to", "direction", "channel", "note"}


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


def _has_symlink_parent(path: Path, stop: Path) -> bool:
    for parent in [path, *path.parents]:
        if parent == stop:
            break
        if parent.is_symlink():
            return True
    return False


def _rel_path(project_root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(project_root.resolve()).as_posix()
    except ValueError:
        return str(path)


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


def _dup_path(prefix: str, dup: DuplicateKey) -> str:
    if prefix:
        if dup.path:
            return prefix + dup.path
        return prefix
    return dup.path


def _is_placeholder(value: str) -> bool:
    return value.strip().strip('"').strip("'").lower() in PLACEHOLDERS


def _load_edges_input(path: Path, diags: list[Diagnostic]) -> list[dict[str, object]]:
    try:
        data, duplicates = load_yaml_with_duplicates(path, allow_duplicates=True)
    except Exception as exc:
        _diag(
            diags,
            "E_INTENT_EDGE_INPUT_PARSE_FAILED",
            "edges input must be valid YAML",
            "valid YAML",
            str(exc),
            json_pointer("edges_input"),
        )
        return []
    if duplicates:
        for dup in duplicates:
            _diag(
                diags,
                "E_INTENT_EDGE_INPUT_DUPLICATE_KEY",
                "duplicate key in edges input",
                "unique key",
                dup.key,
                _dup_path(json_pointer("edges_input"), dup),
            )
        return []

    items: list[dict[str, object]] = []
    if isinstance(data, dict) and "edges" in data:
        edges = data.get("edges")
        if isinstance(edges, list):
            items = [item for item in edges if isinstance(item, dict)]
    elif isinstance(data, list):
        items = [item for item in data if isinstance(item, dict)]
    else:
        _diag(
            diags,
            "E_INTENT_EDGE_INPUT_INVALID",
            "edges input must be list or {edges:[...]}",
            "list",
            type(data).__name__,
            json_pointer("edges_input"),
        )
        return []

    seen_ids: set[str] = set()
    edges: list[dict[str, object]] = []
    for idx, item in enumerate(items):
        unknown = set(item.keys()) - EDGE_FIELDS
        if unknown:
            _diag(
                diags,
                "E_INTENT_EDGE_INPUT_UNKNOWN_FIELD",
                "unknown edge field",
                ",".join(sorted(EDGE_FIELDS)),
                ",".join(sorted(unknown)),
                json_pointer("edges_input", str(idx)),
            )
            continue
        edge_id = item.get("id")
        from_id = item.get("from")
        to_id = item.get("to")
        direction = item.get("direction")
        if not isinstance(edge_id, str) or not RELID_RE.match(edge_id):
            _diag(
                diags,
                "E_INTENT_EDGE_INPUT_ID_INVALID",
                "edge id must be RELID",
                "UPPER_SNAKE_CASE",
                str(edge_id),
                json_pointer("edges_input", str(idx), "id"),
            )
            continue
        if edge_id in seen_ids:
            _diag(
                diags,
                "E_INTENT_EDGE_INPUT_ID_DUPLICATE",
                "duplicate edge id in input",
                "unique id",
                edge_id,
                json_pointer("edges_input", str(idx), "id"),
            )
            continue
        seen_ids.add(edge_id)
        for field_name, value in [("from", from_id), ("to", to_id)]:
            if not isinstance(value, str) or not RELID_RE.match(value):
                _diag(
                    diags,
                    "E_INTENT_EDGE_INPUT_FIELD_INVALID",
                    f"{field_name} must be RELID",
                    "UPPER_SNAKE_CASE",
                    str(value),
                    json_pointer("edges_input", str(idx), field_name),
                )
        if not isinstance(direction, str) or direction not in DIRECTION_VOCAB:
            _diag(
                diags,
                "E_INTENT_EDGE_INPUT_DIRECTION_INVALID",
                "direction invalid",
                ",".join(sorted(DIRECTION_VOCAB)),
                str(direction),
                json_pointer("edges_input", str(idx), "direction"),
            )
        for field_name in ("id", "from", "to", "direction", "channel", "note"):
            value = item.get(field_name)
            if isinstance(value, str) and _is_placeholder(value):
                _diag(
                    diags,
                    "E_INTENT_EDGE_INPUT_PLACEHOLDER_FORBIDDEN",
                    "placeholders are forbidden in intent edges",
                    "no None/TBD/Opaque",
                    value,
                    json_pointer("edges_input", str(idx), field_name),
                )
        channel = item.get("channel")
        if channel is not None and not isinstance(channel, str):
            _diag(
                diags,
                "E_INTENT_EDGE_INPUT_CHANNEL_INVALID",
                "channel must be string",
                "string",
                str(channel),
                json_pointer("edges_input", str(idx), "channel"),
            )
        note = item.get("note")
        if note is not None and not isinstance(note, str):
            _diag(
                diags,
                "E_INTENT_EDGE_INPUT_NOTE_INVALID",
                "note must be string",
                "string",
                str(note),
                json_pointer("edges_input", str(idx), "note"),
            )
        edges.append(dict(item))
    return edges


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--intent", required=True, help="Target intent YAML under drafts/intent")
    ap.add_argument("--edges", required=True, help="Explicit edges input YAML")
    ap.add_argument(
        "--out",
        default=None,
        help="Unified diff output path (default: OUTPUT/intent_edge.patch)",
    )
    ap.add_argument("--generator-id", default="intent_edge_builder_v0_1", help="generator id")
    ap.add_argument("--project-root", default=None, help="Project root (defaults to repo root)")
    args = ap.parse_args()

    project_root = Path(args.project_root).resolve() if args.project_root else ROOT
    intent_root = project_root / "drafts" / "intent"

    intent_path = _resolve_path(project_root, args.intent)
    edges_path = _resolve_path(project_root, args.edges)
    out_path = _resolve_path(project_root, args.out) if args.out else project_root / DEFAULT_OUT_REL

    inputs = [_rel_path(project_root, intent_path), _rel_path(project_root, edges_path)]
    outputs = [_rel_path(project_root, out_path)]
    diff_paths = [_rel_path(project_root, out_path)]

    for label, path in [("intent", intent_path), ("edges", edges_path)]:
        try:
            path.resolve().relative_to(project_root.resolve())
        except ValueError:
            _emit_result(
                "fail",
                [
                    Diagnostic(
                        code=f"E_INTENT_EDGE_{label.upper()}_OUTSIDE_PROJECT",
                        message=f"{label} path must be under project_root",
                        expected="project_root/...",
                        got=str(path),
                        path=json_pointer(label),
                    )
                ],
                inputs,
                outputs,
                diff_paths,
                summary=f"{TOOL_NAME}: input outside project",
            )
            return 2
        if not path.exists():
            _emit_result(
                "fail",
                [
                    Diagnostic(
                        code=f"E_INTENT_EDGE_{label.upper()}_NOT_FOUND",
                        message=f"{label} path not found",
                        expected="existing file",
                        got=str(path),
                        path=json_pointer(label),
                    )
                ],
                inputs,
                outputs,
                diff_paths,
                summary=f"{TOOL_NAME}: input missing",
            )
            return 2
        if path.is_dir():
            _emit_result(
                "fail",
                [
                    Diagnostic(
                        code=f"E_INTENT_EDGE_{label.upper()}_IS_DIR",
                        message=f"{label} path must be file",
                        expected="file",
                        got=str(path),
                        path=json_pointer(label),
                    )
                ],
                inputs,
                outputs,
                diff_paths,
                summary=f"{TOOL_NAME}: input is dir",
            )
            return 2
        if path.is_symlink() or _has_symlink_parent(path, project_root):
            _emit_result(
                "fail",
                [
                    Diagnostic(
                        code=f"E_INTENT_EDGE_{label.upper()}_SYMLINK",
                        message=f"{label} path must not be symlink",
                        expected="non-symlink",
                        got=str(path),
                        path=json_pointer(label),
                    )
                ],
                inputs,
                outputs,
                diff_paths,
                summary=f"{TOOL_NAME}: symlink blocked",
            )
            return 2

    try:
        intent_path.resolve().relative_to(intent_root.resolve())
    except ValueError:
        _emit_result(
            "fail",
            [
                Diagnostic(
                    code="E_INTENT_EDGE_INTENT_NOT_INTENT_ROOT",
                    message="intent must be under drafts/intent",
                    expected="drafts/intent/...",
                    got=str(intent_path),
                    path=json_pointer("intent"),
                )
            ],
            inputs,
            outputs,
            diff_paths,
            summary=f"{TOOL_NAME}: intent out of scope",
        )
        return 2

    diags: list[Diagnostic] = []
    new_edges = _load_edges_input(edges_path, diags)
    if diags:
        _emit_result(
            "fail",
            diags,
            inputs,
            outputs,
            diff_paths,
            summary=f"{TOOL_NAME}: edge input invalid",
        )
        return 2

    try:
        intent_data, duplicates = load_yaml_with_duplicates(intent_path, allow_duplicates=True)
    except Exception as exc:
        _emit_result(
            "fail",
            [
                Diagnostic(
                    code="E_INTENT_EDGE_INTENT_PARSE_FAILED",
                    message="intent must be valid YAML",
                    expected="valid YAML",
                    got=str(exc),
                    path=json_pointer("intent"),
                )
            ],
            inputs,
            outputs,
            diff_paths,
            summary=f"{TOOL_NAME}: intent parse failed",
        )
        return 2
    if duplicates:
        dup_diags = [
            Diagnostic(
                code="E_INTENT_EDGE_INTENT_DUPLICATE_KEY",
                message="duplicate key in intent YAML",
                expected="unique key",
                got=dup.key,
                path=_dup_path(json_pointer("intent"), dup),
            )
            for dup in duplicates
        ]
        _emit_result(
            "fail",
            dup_diags,
            inputs,
            outputs,
            diff_paths,
            summary=f"{TOOL_NAME}: duplicate keys",
        )
        return 2
    if not isinstance(intent_data, dict):
        _emit_result(
            "fail",
            [
                Diagnostic(
                    code="E_INTENT_EDGE_INTENT_INVALID",
                    message="intent root must be object",
                    expected="object",
                    got=type(intent_data).__name__,
                    path=json_pointer("intent"),
                )
            ],
            inputs,
            outputs,
            diff_paths,
            summary=f"{TOOL_NAME}: intent invalid",
        )
        return 2

    normalized, intent_diags = normalize_intent(intent_data, fill_missing=False)
    if intent_diags:
        _emit_result(
            "fail",
            intent_diags,
            inputs,
            outputs,
            diff_paths,
            summary=f"{TOOL_NAME}: intent validation failed",
        )
        return 2

    node_ids = {
        node.get("id", "")
        for node in normalized.get("nodes_proposed", [])
        if isinstance(node, dict)
    }
    raw_existing_edges = normalized.get("edge_intents_proposed", [])
    if not isinstance(raw_existing_edges, list):
        _diag(
            diags,
            "E_INTENT_EDGE_INTENT_INVALID",
            "edge_intents_proposed must be list",
            "list",
            type(raw_existing_edges).__name__,
            json_pointer("intent", "edge_intents_proposed"),
        )
        _emit_result(
            "fail",
            diags,
            inputs,
            outputs,
            diff_paths,
            summary=f"{TOOL_NAME}: intent invalid",
        )
        return 2
    existing_edges = [edge for edge in raw_existing_edges if isinstance(edge, dict)]
    if len(existing_edges) != len(raw_existing_edges):
        _diag(
            diags,
            "E_INTENT_EDGE_INTENT_INVALID",
            "edge_intents_proposed entries must be object",
            "object",
            "non-object",
            json_pointer("intent", "edge_intents_proposed"),
        )
        _emit_result(
            "fail",
            diags,
            inputs,
            outputs,
            diff_paths,
            summary=f"{TOOL_NAME}: intent invalid",
        )
        return 2
    existing_ids = {edge.get("id", "") for edge in existing_edges}
    for idx, edge in enumerate(new_edges):
        edge_id = edge.get("id", "")
        from_id = edge.get("from", "")
        to_id = edge.get("to", "")
        if edge_id in existing_ids:
            _diag(
                diags,
                "E_INTENT_EDGE_DUPLICATE_ID",
                "edge id already exists in intent",
                "unique id",
                str(edge_id),
                json_pointer("edges_input", str(idx), "id"),
            )
        if from_id not in node_ids:
            _diag(
                diags,
                "E_INTENT_EDGE_FROM_UNKNOWN",
                "from must exist in nodes_proposed",
                "existing node id",
                str(from_id),
                json_pointer("edges_input", str(idx), "from"),
            )
        if to_id not in node_ids:
            _diag(
                diags,
                "E_INTENT_EDGE_TO_UNKNOWN",
                "to must exist in nodes_proposed",
                "existing node id",
                str(to_id),
                json_pointer("edges_input", str(idx), "to"),
            )
    if diags:
        _emit_result(
            "fail",
            diags,
            inputs,
            outputs,
            diff_paths,
            summary=f"{TOOL_NAME}: edge validation failed",
        )
        return 2

    merged_edges = list(existing_edges) + new_edges
    merged_edges = sorted(merged_edges, key=lambda e: str(e.get("id", "")))

    try:
        input_hash = compute_input_hash(
            project_root,
            include_decisions=False,
            extra_inputs=[intent_path, edges_path],
        )
    except (FileNotFoundError, ValueError, OSError, UnicodeDecodeError) as exc:
        _emit_result(
            "fail",
            [
                Diagnostic(
                    code="E_INTENT_EDGE_INPUT_HASH_FAILED",
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

    source_rev = _build_source_rev(_git_rev(project_root), args.generator_id)
    updated = {
        "schema_version": normalized.get("schema_version", ""),
        "source_rev": source_rev,
        "input_hash": input_hash.input_hash,
        "generator_id": args.generator_id,
        "scope": normalized.get("scope", {}),
        "nodes_proposed": normalized.get("nodes_proposed", []),
        "edge_intents_proposed": merged_edges,
        "questions": normalized.get("questions", []),
        "conflicts": normalized.get("conflicts", []),
    }

    try:
        old_text = intent_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        _emit_result(
            "fail",
            [
                Diagnostic(
                    code="E_INTENT_EDGE_INTENT_READ_FAILED",
                    message="intent must be readable UTF-8",
                    expected="readable UTF-8 file",
                    got=str(exc),
                    path=json_pointer("intent"),
                )
            ],
            inputs,
            outputs,
            diff_paths,
            summary=f"{TOOL_NAME}: intent read failed",
        )
        return 2
    new_text = dump_yaml(updated)
    diff = difflib.unified_diff(
        old_text.splitlines(),
        new_text.splitlines(),
        fromfile=str(intent_path),
        tofile=str(intent_path),
        lineterm="",
    )
    output = "\n".join(diff)
    if not output:
        _emit_result(
            "diag",
            [
                Diagnostic(
                    code="E_INTENT_EDGE_NO_CHANGE",
                    message="no change in intent",
                    expected="diff",
                    got="no change",
                    path=json_pointer("intent"),
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
                    code="E_INTENT_EDGE_OUTSIDE_PROJECT",
                    message="out must be under project_root",
                    expected="project_root/...",
                    got=str(out_path),
                    path=json_pointer("out"),
                )
            ],
            inputs,
            outputs,
            diff_paths,
            summary=f"{TOOL_NAME}: invalid output path",
        )
        return 2
    output_root = project_root / "OUTPUT"
    try:
        out_path.resolve().relative_to(output_root.resolve())
    except ValueError:
        _emit_result(
            "fail",
            [
                Diagnostic(
                    code="E_INTENT_EDGE_OUT_NOT_OUTPUT",
                    message="out must be under OUTPUT/",
                    expected="OUTPUT/...",
                    got=str(out_path),
                    path=json_pointer("out"),
                )
            ],
            inputs,
            outputs,
            diff_paths,
            summary=f"{TOOL_NAME}: output must be under OUTPUT",
        )
        return 2
    if out_path.exists() and out_path.is_dir():
        _emit_result(
            "fail",
            [
                Diagnostic(
                    code="E_INTENT_EDGE_OUT_IS_DIR",
                    message="out must be file",
                    expected="file",
                    got=str(out_path),
                    path=json_pointer("out"),
                )
            ],
            inputs,
            outputs,
            diff_paths,
            summary=f"{TOOL_NAME}: invalid output path",
        )
        return 2
    if out_path.exists() and out_path.is_symlink():
        _emit_result(
            "fail",
            [
                Diagnostic(
                    code="E_INTENT_EDGE_OUT_SYMLINK",
                    message="out must not be symlink",
                    expected="non-symlink",
                    got=str(out_path),
                    path=json_pointer("out"),
                )
            ],
            inputs,
            outputs,
            diff_paths,
            summary=f"{TOOL_NAME}: invalid output path",
        )
        return 2
    if _has_symlink_parent(out_path, project_root):
        _emit_result(
            "fail",
            [
                Diagnostic(
                    code="E_INTENT_EDGE_OUT_SYMLINK_PARENT",
                    message="out parent must not be symlink",
                    expected="non-symlink",
                    got=str(out_path),
                    path=json_pointer("out"),
                )
            ],
            inputs,
            outputs,
            diff_paths,
            summary=f"{TOOL_NAME}: invalid output path",
        )
        return 2
    out_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        atomic_write_text(out_path, output + "\n", symlink_code="E_INTENT_EDGE_OUT_SYMLINK")
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
