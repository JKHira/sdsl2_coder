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

from sdslv2_builder.errors import Diagnostic, json_pointer
from sdslv2_builder.input_hash import InputHashResult, compute_input_hash
from sdslv2_builder.io_atomic import atomic_write_text
from sdslv2_builder.lint import DIRECTION_VOCAB, _capture_metadata, _parse_metadata_pairs
from sdslv2_builder.op_yaml import DuplicateKey, load_yaml_with_duplicates
from sdslv2_builder.refs import RELID_RE, parse_internal_ref

PLACEHOLDERS = {"none", "null", "tbd", "opaque"}
TOOL_NAME = "topology_channel_builder"
STAGE = "L1"
DEFAULT_OUT_REL = Path("OUTPUT") / "topology_channel.patch"


@dataclass(frozen=True)
class EdgeKey:
    edge_id: str | None
    from_id: str | None
    to_id: str | None
    direction: str | None


@dataclass(frozen=True)
class EdgeChannelSpec:
    key: EdgeKey
    channel: str
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


def _rel_path(project_root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(project_root.resolve()).as_posix()
    except ValueError:
        return str(path)


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


def _has_symlink_parent(path: Path, stop: Path) -> bool:
    for parent in [path, *path.parents]:
        if parent == stop:
            break
        if parent.is_symlink():
            return True
    return False


def _strip_quotes(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


def _is_placeholder(value: str) -> bool:
    return value.strip().strip('"').strip("'").lower() in PLACEHOLDERS


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _line_offsets(lines: list[str]) -> list[int]:
    offsets: list[int] = []
    pos = 0
    for line in lines:
        offsets.append(pos)
        pos += len(line) + 1
    return offsets


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


def _read_channel_map(path: Path, diags: list[Diagnostic]) -> list[EdgeChannelSpec]:
    try:
        data, duplicates = load_yaml_with_duplicates(path, allow_duplicates=True)
    except Exception as exc:
        _diag(
            diags,
            "E_TOPOLOGY_CHANNEL_MAP_PARSE_FAILED",
            "channel map must be valid YAML",
            "valid YAML",
            str(exc),
            json_pointer("map"),
        )
        return []
    if duplicates:
        for dup in duplicates:
            _diag(
                diags,
                "E_TOPOLOGY_CHANNEL_MAP_DUPLICATE_KEY",
                "duplicate key in channel map",
                "unique key",
                dup.key,
                _dup_path(json_pointer("map"), dup),
            )
        return []

    items: list[dict[str, object]] = []
    if isinstance(data, dict) and "edges" in data:
        edges = data.get("edges")
        if isinstance(edges, list):
            items = [item for item in edges if isinstance(item, dict)]
        elif isinstance(edges, dict):
            for edge_id, payload in edges.items():
                if isinstance(payload, str):
                    items.append({"id": edge_id, "channel": payload})
                elif isinstance(payload, dict):
                    entry = dict(payload)
                    entry.setdefault("id", edge_id)
                    items.append(entry)
    elif isinstance(data, list):
        items = [item for item in data if isinstance(item, dict)]
    else:
        _diag(
            diags,
            "E_TOPOLOGY_CHANNEL_MAP_INVALID",
            "channel map must be list or {edges:[...]}",
            "list",
            type(data).__name__,
            json_pointer("map"),
        )
        return []

    specs: list[EdgeChannelSpec] = []
    seen_ids: set[str] = set()
    seen_triplets: set[tuple[str, str, str]] = set()
    for idx, item in enumerate(items):
        edge_id = item.get("id")
        from_id = item.get("from")
        to_id = item.get("to")
        direction = item.get("direction")
        channel = item.get("channel")
        path_ref = json_pointer("map", "edges", str(idx))

        if channel is None or not isinstance(channel, str) or not channel.strip():
            _diag(
                diags,
                "E_TOPOLOGY_CHANNEL_MAP_INVALID",
                "channel must be non-empty string",
                "string",
                str(channel),
                json_pointer("map", "edges", str(idx), "channel"),
            )
            continue
        if _is_placeholder(channel):
            _diag(
                diags,
                "E_TOPOLOGY_CHANNEL_MAP_PLACEHOLDER_FORBIDDEN",
                "channel must not be placeholder",
                "non-placeholder",
                channel,
                json_pointer("map", "edges", str(idx), "channel"),
            )
            continue

        if edge_id is not None:
            if not isinstance(edge_id, str) or not RELID_RE.match(edge_id):
                _diag(
                    diags,
                    "E_TOPOLOGY_CHANNEL_MAP_ID_INVALID",
                    "edge id must be RELID",
                    "UPPER_SNAKE_CASE",
                    str(edge_id),
                    json_pointer("map", "edges", str(idx), "id"),
                )
                continue
            if edge_id in seen_ids:
                _diag(
                    diags,
                    "E_TOPOLOGY_CHANNEL_MAP_ID_DUPLICATE",
                    "duplicate edge id in map",
                    "unique id",
                    edge_id,
                    json_pointer("map", "edges", str(idx), "id"),
                )
                continue
            seen_ids.add(edge_id)
            specs.append(
                EdgeChannelSpec(
                    key=EdgeKey(edge_id=edge_id, from_id=None, to_id=None, direction=None),
                    channel=channel.strip(),
                    path_ref=path_ref,
                )
            )
            continue

        missing_fields = []
        for field_name, value in [("from", from_id), ("to", to_id), ("direction", direction)]:
            if not isinstance(value, str) or not value.strip():
                missing_fields.append(field_name)
        if missing_fields:
            _diag(
                diags,
                "E_TOPOLOGY_CHANNEL_MAP_INVALID",
                "map entries must specify id or from/to/direction",
                "id or from/to/direction",
                ",".join(missing_fields),
                path_ref,
            )
            continue
        if not isinstance(from_id, str) or not RELID_RE.match(from_id):
            _diag(
                diags,
                "E_TOPOLOGY_CHANNEL_MAP_INVALID",
                "from must be RELID",
                "UPPER_SNAKE_CASE",
                str(from_id),
                json_pointer("map", "edges", str(idx), "from"),
            )
            continue
        if not isinstance(to_id, str) or not RELID_RE.match(to_id):
            _diag(
                diags,
                "E_TOPOLOGY_CHANNEL_MAP_INVALID",
                "to must be RELID",
                "UPPER_SNAKE_CASE",
                str(to_id),
                json_pointer("map", "edges", str(idx), "to"),
            )
            continue
        if not isinstance(direction, str) or direction not in DIRECTION_VOCAB:
            _diag(
                diags,
                "E_TOPOLOGY_CHANNEL_MAP_INVALID",
                "direction invalid",
                ",".join(sorted(DIRECTION_VOCAB)),
                str(direction),
                json_pointer("map", "edges", str(idx), "direction"),
            )
            continue
        triplet = (from_id, to_id, direction)
        if triplet in seen_triplets:
            _diag(
                diags,
                "E_TOPOLOGY_CHANNEL_MAP_DUPLICATE",
                "duplicate edge triplet in map",
                "unique tuple",
                f"{from_id},{to_id},{direction}",
                path_ref,
            )
            continue
        seen_triplets.add(triplet)
        specs.append(
            EdgeChannelSpec(
                key=EdgeKey(edge_id=None, from_id=from_id, to_id=to_id, direction=direction),
                channel=channel.strip(),
                path_ref=path_ref,
            )
        )
    return specs


def _collect_edges(
    lines: list[str],
    offsets: list[int],
    rel_path: str,
    diags: list[Diagnostic],
) -> list[dict[str, object]]:
    edges: list[dict[str, object]] = []
    for idx, line in enumerate(lines):
        stripped = line.lstrip()
        if not stripped.startswith("@Edge"):
            continue
        brace_idx = line.find("{")
        if brace_idx == -1:
            _diag(
                diags,
                "E_TOPOLOGY_CHANNEL_EDGE_INVALID",
                "Edge must have metadata object",
                "{...}",
                line.strip(),
                json_pointer("topology", rel_path, "edges", str(idx)),
            )
            continue
        try:
            meta, end_line = _capture_metadata(lines, idx, brace_idx)
        except ValueError as exc:
            _diag(
                diags,
                "E_TOPOLOGY_CHANNEL_EDGE_INVALID",
                "Edge metadata parse failed",
                "valid metadata",
                str(exc),
                json_pointer("topology", rel_path, "edges", str(idx)),
            )
            continue
        pairs = _parse_metadata_pairs(meta)
        meta_map: dict[str, str] = {}
        for key, value in pairs:
            if key in meta_map:
                _diag(
                    diags,
                    "E_TOPOLOGY_CHANNEL_EDGE_INVALID",
                    "duplicate metadata key",
                    "unique key",
                    key,
                    json_pointer("topology", rel_path, "edges", str(idx), key),
                )
                meta_map = {}
                break
            meta_map[key] = value
        if not meta_map:
            continue
        start_offset = offsets[idx] + brace_idx
        end_offset = start_offset + len(meta)
        edges.append(
            {
                "line": idx,
                "start_offset": start_offset,
                "end_offset": end_offset,
                "meta": meta,
                "meta_map": meta_map,
                "path": rel_path,
                "end_line": end_line,
            }
        )
    return edges


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="Topology file or directory")
    ap.add_argument("--map", required=True, help="Edge channel map YAML")
    ap.add_argument("--out", default=None, help="Unified diff output path (default: stdout)")
    ap.add_argument("--generator-id", default="topology_channel_builder_v0_1", help="generator id")
    ap.add_argument("--fail-on-unused", action="store_true", help="Treat unused map entries as failure")
    ap.add_argument("--project-root", default=None, help="Project root (defaults to repo root)")
    args = ap.parse_args()

    project_root = Path(args.project_root).resolve() if args.project_root else ROOT
    topo_root = project_root / "sdsl2" / "topology"
    diags: list[Diagnostic] = []
    if topo_root.is_symlink() or _has_symlink_parent(topo_root, project_root):
        _diag(
            diags,
            "E_TOPOLOGY_CHANNEL_SSOT_ROOT_SYMLINK",
            "sdsl2/topology must not be symlink",
            "non-symlink",
            str(topo_root),
            json_pointer("input"),
        )

    input_path = _resolve_path(project_root, args.input)
    map_path = _resolve_path(project_root, args.map)
    out_path = _resolve_path(project_root, args.out) if args.out else project_root / DEFAULT_OUT_REL

    inputs = [_rel_path(project_root, input_path), _rel_path(project_root, map_path)]
    outputs = [_rel_path(project_root, out_path)]
    diff_paths = [_rel_path(project_root, out_path)]

    if not input_path.exists():
        _diag(
            diags,
            "E_TOPOLOGY_CHANNEL_INPUT_NOT_FOUND",
            "input not found",
            "existing file or dir",
            str(input_path),
            json_pointer("input"),
        )
    if input_path.exists() and (input_path.is_symlink() or _has_symlink_parent(input_path, project_root)):
        _diag(
            diags,
            "E_TOPOLOGY_CHANNEL_INPUT_SYMLINK",
            "input must not be symlink",
            "non-symlink",
            str(input_path),
            json_pointer("input"),
        )
    if input_path.exists():
        try:
            input_path.resolve().relative_to(topo_root.resolve())
        except ValueError:
            _diag(
                diags,
                "E_TOPOLOGY_CHANNEL_INPUT_NOT_SSOT",
                "input must be under sdsl2/topology",
                "sdsl2/topology/...",
                str(input_path),
                json_pointer("input"),
            )

    if not map_path.exists():
        _diag(
            diags,
            "E_TOPOLOGY_CHANNEL_MAP_NOT_FOUND",
            "channel map not found",
            "existing file",
            str(map_path),
            json_pointer("map"),
        )
    if map_path.exists() and map_path.is_dir():
        _diag(
            diags,
            "E_TOPOLOGY_CHANNEL_MAP_IS_DIR",
            "channel map must be file",
            "file",
            str(map_path),
            json_pointer("map"),
        )
    if map_path.exists() and (map_path.is_symlink() or _has_symlink_parent(map_path, project_root)):
        _diag(
            diags,
            "E_TOPOLOGY_CHANNEL_MAP_SYMLINK",
            "channel map must not be symlink",
            "non-symlink",
            str(map_path),
            json_pointer("map"),
        )
    if map_path.exists():
        try:
            map_path.resolve().relative_to(project_root.resolve())
        except ValueError:
            _diag(
                diags,
                "E_TOPOLOGY_CHANNEL_MAP_OUTSIDE_PROJECT",
                "channel map must be under project_root",
                "project_root/...",
                str(map_path),
                json_pointer("map"),
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

    input_hash = None
    source_rev = _build_source_rev(_git_rev(project_root), args.generator_id)
    try:
        input_hash = compute_input_hash(
            project_root,
            include_decisions=False,
            extra_inputs=[map_path],
        )
    except (FileNotFoundError, ValueError, OSError, UnicodeDecodeError) as exc:
        _emit_result(
            "fail",
            [
                Diagnostic(
                    code="E_TOPOLOGY_CHANNEL_INPUT_HASH_FAILED",
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
            summary=f"{TOOL_NAME}: input validation failed",
        )
        return 2

    specs = _read_channel_map(map_path, diags)
    if diags:
        _emit_result(
            "fail",
            diags,
            inputs,
            outputs,
            diff_paths,
            source_rev=source_rev,
            input_hash=input_hash,
            summary=f"{TOOL_NAME}: map parsing failed",
        )
        return 2

    by_id: dict[str, EdgeChannelSpec] = {}
    by_triplet: dict[tuple[str, str, str], EdgeChannelSpec] = {}
    for spec in specs:
        if spec.key.edge_id:
            by_id[spec.key.edge_id] = spec
        else:
            triplet = (spec.key.from_id or "", spec.key.to_id or "", spec.key.direction or "")
            by_triplet[triplet] = spec

    paths: list[Path] = []
    if input_path.is_dir():
        for path in sorted(input_path.rglob("*.sdsl2")):
            if path.is_file():
                if path.is_symlink() or _has_symlink_parent(path, topo_root):
                    _diag(
                        diags,
                        "E_TOPOLOGY_CHANNEL_INPUT_SYMLINK",
                        "input must not be symlink",
                        "non-symlink",
                        str(path),
                        json_pointer("input"),
                    )
                    continue
                paths.append(path)
    else:
        paths = [input_path]

    if not paths:
        _diag(
            diags,
            "E_TOPOLOGY_CHANNEL_INPUT_EMPTY",
            "no topology files found",
            "*.sdsl2",
            str(input_path),
            json_pointer("input"),
        )
        _emit_result(
            "fail",
            diags,
            inputs,
            outputs,
            diff_paths,
            source_rev=source_rev,
            input_hash=input_hash,
            summary=f"{TOOL_NAME}: no topology files found",
        )
        return 2

    unused_specs = set(specs)
    diffs: list[str] = []
    for path in paths:
        rel_path = path.resolve().relative_to(project_root.resolve()).as_posix()
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            _diag(
                diags,
                "E_TOPOLOGY_CHANNEL_READ_FAILED",
                "topology file must be readable UTF-8",
                "readable UTF-8 file",
                str(exc),
                json_pointer("topology", rel_path),
            )
            continue
        lines = text.splitlines()
        offsets = _line_offsets(lines)
        edges = _collect_edges(lines, offsets, rel_path, diags)
        if diags:
            continue

        replacements: list[tuple[int, int, str]] = []
        for edge_idx, edge in enumerate(edges):
            meta_map = edge["meta_map"]
            edge_id = _strip_quotes(meta_map.get("id") or "")
            raw_from = meta_map.get("from")
            raw_to = meta_map.get("to")
            direction = _strip_quotes(meta_map.get("direction"))
            channel = _strip_quotes(meta_map.get("channel"))

            from_ref = parse_internal_ref(raw_from) if raw_from else None
            to_ref = parse_internal_ref(raw_to) if raw_to else None
            from_id = from_ref.rel_id if from_ref and from_ref.kind == "Node" else None
            to_id = to_ref.rel_id if to_ref and to_ref.kind == "Node" else None

            spec = None
            if edge_id and edge_id in by_id:
                spec = by_id.get(edge_id)
            elif from_id and to_id and direction:
                spec = by_triplet.get((from_id, to_id, direction))

            if spec:
                unused_specs.discard(spec)
                if channel and not _is_placeholder(channel):
                    if channel != spec.channel:
                        _diag(
                            diags,
                            "E_TOPOLOGY_CHANNEL_CONFLICT",
                            "edge channel conflicts with map",
                            spec.channel,
                            channel,
                            json_pointer("topology", rel_path, "edges", str(edge_idx), "channel"),
                        )
                    continue
                new_meta = _insert_fields(edge["meta"], [("channel", spec.channel)])
                if new_meta != edge["meta"]:
                    replacements.append(
                        (edge["start_offset"], edge["end_offset"], new_meta)
                    )
            else:
                if channel is None or _is_placeholder(channel):
                    _diag(
                        diags,
                        "E_TOPOLOGY_CHANNEL_MISSING",
                        "edge channel missing and no map entry",
                        "map entry",
                        edge_id or "",
                        json_pointer("topology", rel_path, "edges", str(edge_idx), "channel"),
                    )
                else:
                    _diag(
                        diags,
                        "E_TOPOLOGY_CHANNEL_UNMAPPED",
                        "edge channel present without explicit map entry",
                        "map entry",
                        channel,
                        json_pointer("topology", rel_path, "edges", str(edge_idx), "channel"),
                    )

        if replacements:
            new_text = text
            for start, end, new_meta in sorted(replacements, key=lambda item: item[0], reverse=True):
                new_text = new_text[:start] + new_meta + new_text[end:]
            diff = difflib.unified_diff(
                text.splitlines(),
                new_text.splitlines(),
                fromfile=str(path),
                tofile=str(path),
                lineterm="",
            )
            diffs.append("\n".join(diff))

    unused_diags: list[Diagnostic] = []
    if unused_specs:
        for spec in sorted(unused_specs, key=lambda item: (item.key.edge_id or "", item.path_ref)):
            unused_diags.append(
                Diagnostic(
                    code="E_TOPOLOGY_CHANNEL_UNUSED",
                    message="channel map entry did not match any edge",
                    expected="matching edge",
                    got=spec.channel,
                    path=spec.path_ref,
                )
            )

    if diags:
        missing = []
        invalid = []
        codes = {diag.code for diag in diags}
        if {"E_TOPOLOGY_CHANNEL_MISSING", "E_TOPOLOGY_CHANNEL_UNMAPPED"} & codes:
            missing.append("channel")
        if "E_TOPOLOGY_CHANNEL_CONFLICT" in codes:
            invalid.append("channel")
        _emit_result(
            "fail",
            diags,
            inputs,
            outputs,
            diff_paths,
            source_rev=source_rev,
            input_hash=input_hash,
            summary=f"{TOOL_NAME}: diagnostics detected",
            gaps_missing=sorted(set(missing)),
            gaps_invalid=sorted(set(invalid)),
        )
        return 2
    if unused_diags:
        status = "fail" if args.fail_on_unused else "diag"
        _emit_result(
            status,
            unused_diags,
            inputs,
            outputs,
            diff_paths,
            source_rev=source_rev,
            input_hash=input_hash,
            summary=f"{TOOL_NAME}: unused map entries",
        )
        return 2 if status == "fail" else 0

    output = "\n".join([diff for diff in diffs if diff])
    if not output:
        no_change = [
            Diagnostic(
                code="E_TOPOLOGY_CHANNEL_NO_CHANGE",
                message="no channel updates required",
                expected="missing channel entries",
                got="no change",
                path=json_pointer("topology"),
            )
        ]
        _emit_result(
            "fail",
            no_change,
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
        _diag(
            diags,
            "E_TOPOLOGY_CHANNEL_OUTSIDE_PROJECT",
            "out must be under project_root",
            "project_root/...",
            str(out_path),
            json_pointer("out"),
        )
    if out_path.exists() and out_path.is_dir():
        _diag(
            diags,
            "E_TOPOLOGY_CHANNEL_OUT_IS_DIR",
            "out must be file",
            "file",
            str(out_path),
            json_pointer("out"),
        )
    if out_path.exists() and out_path.is_symlink():
        _diag(
            diags,
            "E_TOPOLOGY_CHANNEL_OUT_SYMLINK",
            "out must not be symlink",
            "non-symlink",
            str(out_path),
            json_pointer("out"),
        )
    if _has_symlink_parent(out_path, project_root):
        _diag(
            diags,
            "E_TOPOLOGY_CHANNEL_OUT_SYMLINK_PARENT",
            "out parent must not be symlink",
            "non-symlink",
            str(out_path),
            json_pointer("out"),
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
            summary=f"{TOOL_NAME}: invalid output path",
        )
        return 2

    out_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        atomic_write_text(out_path, output + "\n", symlink_code="E_TOPOLOGY_CHANNEL_OUT_SYMLINK")
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
