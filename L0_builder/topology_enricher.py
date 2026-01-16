#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ruff: noqa: E402

from __future__ import annotations

import argparse
import csv
import difflib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sdslv2_builder.errors import Diagnostic, json_pointer
from sdslv2_builder.input_hash import compute_input_hash
from sdslv2_builder.io_atomic import atomic_write_text
from sdslv2_builder.lint import _capture_metadata, _parse_metadata_pairs
from sdslv2_builder.op_yaml import DuplicateKey, load_yaml_with_duplicates
from sdslv2_builder.refs import RELID_RE

TOOL_NAME = "topology_enricher"
STAGE = "L0"
DEFAULT_OUT_REL = Path("OUTPUT") / "topology_enricher.patch"

PLACEHOLDERS = {"none", "null", "tbd", "opaque"}


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


def _strip_quotes(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


def _is_placeholder(value: str) -> bool:
    return value.strip().strip('"').strip("'").lower() in PLACEHOLDERS


def _value_missing(value: str | None) -> bool:
    if value is None:
        return True
    stripped = value.strip()
    if stripped == "":
        return True
    lowered = stripped.strip('"').strip("'").lower()
    return lowered in PLACEHOLDERS


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


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


def _dup_path(prefix: str, dup: DuplicateKey) -> str:
    if prefix:
        if dup.path:
            return prefix + dup.path
        return prefix
    return dup.path


def _load_map(path: Path, project_root: Path, diags: list[Diagnostic]) -> dict[str, dict[str, str]]:
    if not path.exists():
        _diag(
            diags,
            "E_TOPOLOGY_ENRICH_MAP_NOT_FOUND",
            "map file not found",
            "existing file",
            str(path),
            json_pointer("map"),
        )
        return {}
    if path.is_dir():
        _diag(
            diags,
            "E_TOPOLOGY_ENRICH_MAP_IS_DIR",
            "map must be file",
            "file",
            str(path),
            json_pointer("map"),
        )
        return {}
    if path.is_symlink() or _has_symlink_parent(path, project_root):
        _diag(
            diags,
            "E_TOPOLOGY_ENRICH_MAP_SYMLINK",
            "map must not be symlink",
            "non-symlink",
            str(path),
            json_pointer("map"),
        )
        return {}

    entries: dict[str, dict[str, str]] = {}
    if path.suffix.lower() == ".csv":
        try:
            with path.open("r", encoding="utf-8", newline="") as handle:
                reader = csv.DictReader(handle)
                for idx, row in enumerate(reader):
                    rel_id = (row.get("id") or "").strip()
                    summary = (row.get("summary") or "").strip()
                    io_value = (row.get("io") or "").strip()
                    if not rel_id or not RELID_RE.match(rel_id):
                        _diag(
                            diags,
                            "E_TOPOLOGY_ENRICH_MAP_ID_INVALID",
                            "map id must be RELID",
                            "UPPER_SNAKE_CASE",
                            rel_id,
                            json_pointer("map", "csv", str(idx), "id"),
                        )
                        continue
                    if rel_id in entries:
                        _diag(
                            diags,
                            "E_TOPOLOGY_ENRICH_MAP_ID_DUPLICATE",
                            "duplicate map id",
                            "unique id",
                            rel_id,
                            json_pointer("map", "csv", str(idx), "id"),
                        )
                        continue
                    if summary:
                        if _is_placeholder(summary):
                            _diag(
                                diags,
                                "E_TOPOLOGY_ENRICH_PLACEHOLDER_FORBIDDEN",
                                "summary must not be placeholder",
                                "non-placeholder",
                                summary,
                                json_pointer("map", "csv", str(idx), "summary"),
                            )
                        else:
                            entries.setdefault(rel_id, {})["summary"] = summary
                    if io_value:
                        if _is_placeholder(io_value):
                            _diag(
                                diags,
                                "E_TOPOLOGY_ENRICH_PLACEHOLDER_FORBIDDEN",
                                "io must not be placeholder",
                                "non-placeholder",
                                io_value,
                                json_pointer("map", "csv", str(idx), "io"),
                            )
                        else:
                            entries.setdefault(rel_id, {})["io"] = io_value
        except (OSError, UnicodeDecodeError) as exc:
            _diag(
                diags,
                "E_TOPOLOGY_ENRICH_MAP_READ_FAILED",
                "map must be readable UTF-8 CSV",
                "readable CSV",
                str(exc),
                json_pointer("map"),
            )
            return {}
        return entries

    try:
        data, duplicates = load_yaml_with_duplicates(path, allow_duplicates=True)
    except Exception as exc:
        _diag(
            diags,
            "E_TOPOLOGY_ENRICH_MAP_PARSE_FAILED",
            "map must be valid YAML",
            "valid YAML",
            str(exc),
            json_pointer("map"),
        )
        return {}
    if duplicates:
        for dup in duplicates:
            _diag(
                diags,
                "E_TOPOLOGY_ENRICH_MAP_DUPLICATE_KEY",
                "duplicate key in map YAML",
                "unique key",
                dup.key,
                _dup_path(json_pointer("map"), dup),
            )
        return {}

    items: list[dict[str, object]] = []
    if isinstance(data, dict) and "nodes" in data:
        nodes = data.get("nodes")
        if isinstance(nodes, dict):
            for rel_id, payload in nodes.items():
                items.append({"id": rel_id, "value": payload})
        elif isinstance(nodes, list):
            for item in nodes:
                if isinstance(item, dict):
                    items.append(item)
    elif isinstance(data, dict):
        for rel_id, payload in data.items():
            items.append({"id": rel_id, "value": payload})
    elif isinstance(data, list):
        items = [item for item in data if isinstance(item, dict)]

    for idx, item in enumerate(items):
        rel_id = item.get("id")
        if rel_id is None and "value" in item and isinstance(item.get("value"), dict):
            rel_id = item.get("id")
        if not isinstance(rel_id, str) or not RELID_RE.match(rel_id):
            _diag(
                diags,
                "E_TOPOLOGY_ENRICH_MAP_ID_INVALID",
                "map id must be RELID",
                "UPPER_SNAKE_CASE",
                str(rel_id),
                json_pointer("map", str(idx), "id"),
            )
            continue
        if rel_id in entries:
            _diag(
                diags,
                "E_TOPOLOGY_ENRICH_MAP_ID_DUPLICATE",
                "duplicate map id",
                "unique id",
                rel_id,
                json_pointer("map", str(idx), "id"),
            )
            continue
        summary = item.get("summary")
        io_value = item.get("io")
        if isinstance(item.get("value"), dict):
            payload = item.get("value", {})
            if summary is None:
                summary = payload.get("summary")
            if io_value is None:
                io_value = payload.get("io")
        entry: dict[str, str] = {}
        if isinstance(summary, str) and summary.strip():
            if _is_placeholder(summary):
                _diag(
                    diags,
                    "E_TOPOLOGY_ENRICH_PLACEHOLDER_FORBIDDEN",
                    "summary must not be placeholder",
                    "non-placeholder",
                    summary,
                    json_pointer("map", str(idx), "summary"),
                )
            else:
                entry["summary"] = summary.strip()
        if isinstance(io_value, str) and io_value.strip():
            if _is_placeholder(io_value):
                _diag(
                    diags,
                    "E_TOPOLOGY_ENRICH_PLACEHOLDER_FORBIDDEN",
                    "io must not be placeholder",
                    "non-placeholder",
                    io_value,
                    json_pointer("map", str(idx), "io"),
                )
            else:
                entry["io"] = io_value.strip()
        if entry:
            entries[rel_id] = entry
    return entries


def _load_intent_overrides(
    paths: list[Path],
    project_root: Path,
    diags: list[Diagnostic],
) -> dict[str, dict[str, str]]:
    overrides: dict[str, dict[str, str]] = {}
    for path in paths:
        if not path.exists() or not path.is_file():
            _diag(
                diags,
                "E_TOPOLOGY_ENRICH_INTENT_NOT_FOUND",
                "intent file not found",
                "existing file",
                str(path),
                json_pointer("intent"),
            )
            continue
        if path.is_symlink() or _has_symlink_parent(path, project_root):
            _diag(
                diags,
                "E_TOPOLOGY_ENRICH_INTENT_SYMLINK",
                "intent file must not be symlink",
                "non-symlink",
                str(path),
                json_pointer("intent"),
            )
            continue
        try:
            data, duplicates = load_yaml_with_duplicates(path, allow_duplicates=True)
        except Exception as exc:
            _diag(
                diags,
                "E_TOPOLOGY_ENRICH_INTENT_PARSE_FAILED",
                "intent must be valid YAML",
                "valid YAML",
                str(exc),
                json_pointer("intent"),
            )
            continue
        if duplicates:
            for dup in duplicates:
                _diag(
                    diags,
                    "E_TOPOLOGY_ENRICH_INTENT_DUPLICATE_KEY",
                    "duplicate key in intent YAML",
                    "unique key",
                    dup.key,
                    _dup_path(json_pointer("intent"), dup),
                )
            continue
        if not isinstance(data, dict):
            _diag(
                diags,
                "E_TOPOLOGY_ENRICH_INTENT_INVALID",
                "intent root must be object",
                "object",
                type(data).__name__,
                json_pointer("intent", path.name),
            )
            continue
        nodes = data.get("nodes_proposed")
        if not isinstance(nodes, list):
            _diag(
                diags,
                "E_TOPOLOGY_ENRICH_INTENT_INVALID",
                "nodes_proposed must be list",
                "list",
                type(nodes).__name__,
                json_pointer("intent", path.name, "nodes_proposed"),
            )
            continue
        for idx, node in enumerate(nodes):
            if not isinstance(node, dict):
                _diag(
                    diags,
                    "E_TOPOLOGY_ENRICH_INTENT_INVALID",
                    "nodes_proposed entries must be object",
                    "object",
                    type(node).__name__,
                    json_pointer("intent", path.name, "nodes_proposed", str(idx)),
                )
                continue
            rel_id = node.get("id")
            if not isinstance(rel_id, str) or not RELID_RE.match(rel_id):
                _diag(
                    diags,
                    "E_TOPOLOGY_ENRICH_INTENT_ID_INVALID",
                    "nodes_proposed.id must be RELID",
                    "UPPER_SNAKE_CASE",
                    str(rel_id),
                    json_pointer("intent", path.name, "nodes_proposed", str(idx), "id"),
                )
                continue
            summary = node.get("summary")
            io_value = node.get("io")
            entry: dict[str, str] = {}
            if summary is not None:
                if not isinstance(summary, str):
                    _diag(
                        diags,
                        "E_TOPOLOGY_ENRICH_INTENT_INVALID",
                        "summary must be string",
                        "string",
                        type(summary).__name__,
                        json_pointer("intent", path.name, "nodes_proposed", str(idx), "summary"),
                    )
                elif summary.strip():
                    if _is_placeholder(summary):
                        _diag(
                            diags,
                            "E_TOPOLOGY_ENRICH_PLACEHOLDER_FORBIDDEN",
                            "summary must not be placeholder",
                            "non-placeholder",
                            summary,
                            json_pointer("intent", path.name, "nodes_proposed", str(idx), "summary"),
                        )
                    else:
                        entry["summary"] = summary.strip()
            if io_value is not None:
                if not isinstance(io_value, str):
                    _diag(
                        diags,
                        "E_TOPOLOGY_ENRICH_INTENT_INVALID",
                        "io must be string",
                        "string",
                        type(io_value).__name__,
                        json_pointer("intent", path.name, "nodes_proposed", str(idx), "io"),
                    )
                elif io_value.strip():
                    if _is_placeholder(io_value):
                        _diag(
                            diags,
                            "E_TOPOLOGY_ENRICH_PLACEHOLDER_FORBIDDEN",
                            "io must not be placeholder",
                            "non-placeholder",
                            io_value,
                            json_pointer("intent", path.name, "nodes_proposed", str(idx), "io"),
                        )
                    else:
                        entry["io"] = io_value.strip()
            if entry:
                overrides[rel_id] = entry
    return overrides


def _insert_fields(meta: str, additions: list[tuple[str, str]]) -> str:
    if not additions:
        return meta
    if not (meta.startswith("{") and meta.endswith("}")):
        return meta
    if "\n" in meta:
        lines = meta.splitlines()
        if not lines:
            return meta
        closing = lines[-1]
        closing_indent = closing[: len(closing) - len(closing.lstrip(" "))]
        field_indent = None
        for line in lines[1:-1]:
            stripped = line.lstrip(" ")
            if stripped and ":" in stripped:
                field_indent = line[: len(line) - len(stripped)]
                break
        if field_indent is None:
            field_indent = closing_indent + "  "
        insert_lines = [f'{field_indent}{k}:"{_escape(v)}",' for k, v in additions]
        new_lines = lines[:-1] + insert_lines + [closing]
        return "\n".join(new_lines)

    end = meta.rfind("}")
    head = meta[:end]
    tail = meta[end:]
    trimmed = head.rstrip()
    insert = ", ".join(f'{k}:"{_escape(v)}"' for k, v in additions)
    if trimmed.endswith("{") or trimmed.endswith(","):
        sep = " "
    else:
        sep = ", "
    return trimmed + sep + insert + tail


def _line_offsets(lines: list[str]) -> list[int]:
    offsets: list[int] = []
    pos = 0
    for line in lines:
        offsets.append(pos)
        pos += len(line) + 1
    return offsets


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="Topology file or directory")
    ap.add_argument("--map", default=None, help="CSV/YAML map for summary/io")
    ap.add_argument("--intent", default=None, help="Intent YAML file or dir (optional overrides)")
    ap.add_argument(
        "--out",
        default=None,
        help="Unified diff output path (default: OUTPUT/topology_enricher.patch)",
    )
    ap.add_argument("--project-root", default=None, help="Project root (defaults to repo root)")
    args = ap.parse_args()

    project_root = Path(args.project_root).resolve() if args.project_root else ROOT
    topo_root = project_root / "sdsl2" / "topology"
    input_path = _resolve_path(project_root, args.input)
    diff_out = _resolve_path(project_root, args.out) if args.out else project_root / DEFAULT_OUT_REL
    inputs = [_rel_path(project_root, input_path)]
    outputs = [_rel_path(project_root, diff_out)]
    diff_paths = [_rel_path(project_root, diff_out)]

    if topo_root.is_symlink() or _has_symlink_parent(topo_root, project_root):
        _emit_result(
            "fail",
            [
                Diagnostic(
                    code="E_TOPOLOGY_ENRICH_SSOT_ROOT_SYMLINK",
                    message="sdsl2/topology must not be symlink",
                    expected="non-symlink",
                    got=str(topo_root),
                    path=json_pointer("input"),
                )
            ],
            inputs,
            outputs,
            diff_paths,
            summary=f"{TOOL_NAME}: topo root invalid",
        )
        return 2

    if not input_path.exists():
        _emit_result(
            "fail",
            [
                Diagnostic(
                    code="E_TOPOLOGY_ENRICH_INPUT_NOT_FOUND",
                    message="input not found",
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
                    code="E_TOPOLOGY_ENRICH_INPUT_SYMLINK",
                    message="input must not be symlink",
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
        input_path.resolve().relative_to(topo_root.resolve())
    except ValueError:
        _emit_result(
            "fail",
            [
                Diagnostic(
                    code="E_TOPOLOGY_ENRICH_INPUT_NOT_SSOT",
                    message="input must be under sdsl2/topology",
                    expected="sdsl2/topology/...",
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

    paths: list[Path] = []
    if input_path.is_dir():
        for path in sorted(input_path.rglob("*.sdsl2")):
            if path.is_file():
                if path.is_symlink() or _has_symlink_parent(path, topo_root):
                    _emit_result(
                        "fail",
                        [
                            Diagnostic(
                                code="E_TOPOLOGY_ENRICH_INPUT_SYMLINK",
                                message="input must not be symlink",
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
                paths.append(path)
    else:
        paths = [input_path]

    if not paths:
        _emit_result(
            "fail",
            [
                Diagnostic(
                    code="E_TOPOLOGY_ENRICH_INPUT_EMPTY",
                    message="no topology files found",
                    expected="*.sdsl2",
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
    map_entries: dict[str, dict[str, str]] = {}
    map_path: Path | None = None
    if args.map:
        map_path = _resolve_path(project_root, args.map)
        try:
            map_path.resolve().relative_to(project_root.resolve())
        except ValueError:
            _diag(
                diags,
                "E_TOPOLOGY_ENRICH_MAP_OUTSIDE_PROJECT",
                "map must be under project_root",
                "project_root/...",
                str(map_path),
                json_pointer("map"),
            )
        else:
            map_entries = _load_map(map_path, project_root, diags)
            inputs.append(_rel_path(project_root, map_path))

    intent_entries: dict[str, dict[str, str]] = {}
    intent_paths: list[Path] = []
    if args.intent:
        intent_path = _resolve_path(project_root, args.intent)
        try:
            intent_path.resolve().relative_to(project_root.resolve())
        except ValueError:
            _diag(
                diags,
                "E_TOPOLOGY_ENRICH_INTENT_OUTSIDE_PROJECT",
                "intent must be under project_root",
                "project_root/...",
                str(intent_path),
                json_pointer("intent"),
            )
        else:
            if intent_path.is_dir():
                for path in sorted(intent_path.rglob("*.yaml")):
                    if path.is_file():
                        intent_paths.append(path)
            else:
                intent_paths = [intent_path]
            intent_entries = _load_intent_overrides(intent_paths, project_root, diags)
            inputs.extend(_rel_path(project_root, path) for path in intent_paths)

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

    overrides = dict(map_entries)
    for rel_id, payload in intent_entries.items():
        overrides.setdefault(rel_id, {}).update(payload)

    try:
        extra_inputs: list[Path] = list(paths)
        if map_path is not None:
            extra_inputs.append(map_path)
        extra_inputs.extend(intent_paths)
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
                    code="E_TOPOLOGY_ENRICH_INPUT_HASH_FAILED",
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

    if not overrides:
        _emit_result(
            "fail",
            [
                Diagnostic(
                    code="E_TOPOLOGY_ENRICH_NO_OVERRIDES",
                    message="no overrides provided",
                    expected="map or intent overrides",
                    got="missing",
                    path=json_pointer("overrides"),
                )
            ],
            inputs,
            outputs,
            diff_paths,
            input_hash=input_hash.input_hash,
            summary=f"{TOOL_NAME}: no overrides",
        )
        return 2

    output_chunks: list[str] = []
    changed = False
    for path in paths:
        text = path.read_text(encoding="utf-8")
        lines = text.splitlines()
        offsets = _line_offsets(lines)
        replacements: list[tuple[int, int, str]] = []
        for idx, line in enumerate(lines):
            if not line.lstrip().startswith("@Node"):
                continue
            brace_idx = line.find("{")
            if brace_idx == -1:
                continue
            meta, end_line = _capture_metadata(lines, idx, brace_idx)
            pairs = _parse_metadata_pairs(meta)
            meta_map = {k: v for k, v in pairs}
            rel_id = _strip_quotes(meta_map.get("id"))
            if not rel_id or not RELID_RE.match(rel_id):
                _diag(
                    diags,
                    "E_TOPOLOGY_ENRICH_NODE_ID_INVALID",
                    "node id must be RELID",
                    "UPPER_SNAKE_CASE",
                    str(rel_id),
                    json_pointer("nodes", str(idx), "id"),
                )
                continue
            override = overrides.get(rel_id, {})
            additions: list[tuple[str, str]] = []
            for field in ("summary", "io"):
                current = _strip_quotes(meta_map.get(field))
                if _value_missing(current):
                    value = override.get(field)
                    if isinstance(value, str) and value.strip():
                        additions.append((field, value.strip()))
            if not additions:
                continue
            start_offset = offsets[idx] + brace_idx
            end_offset = start_offset + len(meta)
            new_meta = _insert_fields(meta, additions)
            replacements.append((start_offset, end_offset, new_meta))

        if diags:
            _emit_result(
                "fail",
                diags,
                inputs,
                outputs,
                diff_paths,
                input_hash=input_hash.input_hash,
                summary=f"{TOOL_NAME}: topology parse failed",
            )
            return 2

        if not replacements:
            continue

        new_text = text
        for start, end, replacement in sorted(replacements, key=lambda item: item[0], reverse=True):
            new_text = new_text[:start] + replacement + new_text[end:]
        diff = difflib.unified_diff(
            text.splitlines(),
            new_text.splitlines(),
            fromfile=str(path),
            tofile=str(path),
            lineterm="",
        )
        chunk = "\n".join(diff)
        if chunk:
            output_chunks.append(chunk)
            changed = True

    if not changed:
        _emit_result(
            "diag",
            [
                Diagnostic(
                    code="E_TOPOLOGY_ENRICH_NO_CHANGE",
                    message="no enrichments applied",
                    expected="missing summary/io with overrides",
                    got="no change",
                    path=json_pointer(),
                )
            ],
            inputs,
            outputs,
            diff_paths,
            input_hash=input_hash.input_hash,
            summary=f"{TOOL_NAME}: no changes required",
        )
        return 0

    output = "\n".join(output_chunks)
    output_root = project_root / "OUTPUT"
    try:
        diff_out.resolve().relative_to(project_root.resolve())
    except ValueError:
        _emit_result(
            "fail",
            [
                Diagnostic(
                    code="E_TOPOLOGY_ENRICH_OUTPUT_OUTSIDE_PROJECT",
                    message="out must be under project_root",
                    expected="project_root/...",
                    got=str(diff_out),
                    path=json_pointer("out"),
                )
            ],
            inputs,
            outputs,
            diff_paths,
            input_hash=input_hash.input_hash,
            summary=f"{TOOL_NAME}: invalid output path",
        )
        return 2
    try:
        diff_out.resolve().relative_to(output_root.resolve())
    except ValueError:
        _emit_result(
            "fail",
            [
                Diagnostic(
                    code="E_TOPOLOGY_ENRICH_OUT_NOT_OUTPUT",
                    message="out must be under OUTPUT/",
                    expected="OUTPUT/...",
                    got=str(diff_out),
                    path=json_pointer("out"),
                )
            ],
            inputs,
            outputs,
            diff_paths,
            input_hash=input_hash.input_hash,
            summary=f"{TOOL_NAME}: output must be under OUTPUT",
        )
        return 2
    if diff_out.exists() and diff_out.is_dir():
        _emit_result(
            "fail",
            [
                Diagnostic(
                    code="E_TOPOLOGY_ENRICH_OUTPUT_IS_DIR",
                    message="out must be file",
                    expected="file",
                    got=str(diff_out),
                    path=json_pointer("out"),
                )
            ],
            inputs,
            outputs,
            diff_paths,
            input_hash=input_hash.input_hash,
            summary=f"{TOOL_NAME}: invalid output path",
        )
        return 2
    if diff_out.exists() and diff_out.is_symlink():
        _emit_result(
            "fail",
            [
                Diagnostic(
                    code="E_TOPOLOGY_ENRICH_OUTPUT_SYMLINK",
                    message="out must not be symlink",
                    expected="non-symlink",
                    got=str(diff_out),
                    path=json_pointer("out"),
                )
            ],
            inputs,
            outputs,
            diff_paths,
            input_hash=input_hash.input_hash,
            summary=f"{TOOL_NAME}: invalid output path",
        )
        return 2
    if _has_symlink_parent(diff_out, project_root):
        _emit_result(
            "fail",
            [
                Diagnostic(
                    code="E_TOPOLOGY_ENRICH_OUTPUT_SYMLINK_PARENT",
                    message="out parent must not be symlink",
                    expected="non-symlink",
                    got=str(diff_out),
                    path=json_pointer("out"),
                )
            ],
            inputs,
            outputs,
            diff_paths,
            input_hash=input_hash.input_hash,
            summary=f"{TOOL_NAME}: invalid output path",
        )
        return 2
    diff_out.parent.mkdir(parents=True, exist_ok=True)
    try:
        atomic_write_text(diff_out, output + "\n", symlink_code="E_TOPOLOGY_ENRICH_OUTPUT_SYMLINK")
    except ValueError as exc:
        _emit_result(
            "fail",
            [
                Diagnostic(
                    code=str(exc),
                    message="output must not be symlink",
                    expected="non-symlink",
                    got=str(diff_out),
                    path=json_pointer("out"),
                )
            ],
            inputs,
            outputs,
            diff_paths,
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
        input_hash=input_hash.input_hash,
        summary=f"{TOOL_NAME}: diff written",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
