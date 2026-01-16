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
from sdslv2_builder.io_atomic import atomic_write_text
from sdslv2_builder.lint import _capture_metadata, _parse_metadata_pairs
from sdslv2_builder.op_yaml import dump_yaml
from sdslv2_builder.refs import RELID_RE
from sdslv2_builder.schema_versions import INTENT_SCHEMA_VERSION

TOOL_NAME = "intent_template_gen"
STAGE = "L0"
DEFAULT_OUT_REL = Path("OUTPUT") / "intent_template.patch"


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


def _strip_quotes(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


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


def _build_source_rev(git_rev: str, generator_id: str) -> str:
    return f"{git_rev}|gen:{generator_id}"


def _collect_nodes(lines: list[str], diags: list[Diagnostic], path_ref: str) -> list[dict[str, str]]:
    nodes: list[dict[str, str]] = []
    seen: set[str] = set()
    node_index = 0
    for idx, line in enumerate(lines):
        if not line.lstrip().startswith("@Node"):
            continue
        brace_idx = line.find("{")
        if brace_idx == -1:
            continue
        meta, _ = _capture_metadata(lines, idx, brace_idx)
        pairs = _parse_metadata_pairs(meta)
        meta_map = {k: v for k, v in pairs}
        rel_id = _strip_quotes(meta_map.get("id"))
        if not rel_id or not RELID_RE.match(rel_id):
            _diag(
                diags,
                "E_INTENT_TEMPLATE_NODE_ID_INVALID",
                "Node id must be RELID",
                "UPPER_SNAKE_CASE",
                str(rel_id),
                json_pointer(path_ref, "nodes", str(node_index), "id"),
            )
            node_index += 1
            continue
        if rel_id in seen:
            _diag(
                diags,
                "E_INTENT_TEMPLATE_NODE_ID_DUPLICATE",
                "Duplicate node id",
                "unique id",
                rel_id,
                json_pointer(path_ref, "nodes", str(node_index), "id"),
            )
            node_index += 1
            continue
        seen.add(rel_id)
        item = {"id": rel_id}
        kind = _strip_quotes(meta_map.get("kind"))
        if kind:
            item["kind"] = kind
        nodes.append(item)
        node_index += 1
    return nodes


def _default_out_path(project_root: Path, topo_path: Path) -> Path:
    stem = topo_path.stem
    name = f"{stem}_intent.yaml"
    topo_root = project_root / "sdsl2" / "topology"
    try:
        rel = topo_path.resolve().relative_to(topo_root.resolve())
        rel_parent = rel.parent
    except ValueError:
        rel_parent = Path()
    if str(rel_parent) in {"", "."}:
        return (project_root / "drafts" / "intent" / name).resolve()
    return (project_root / "drafts" / "intent" / rel_parent / name).resolve()


def _validate_file_header(lines: list[str], diags: list[Diagnostic], path_ref: str) -> bool:
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if stripped == "" or stripped.startswith("//"):
            continue
        if not stripped.startswith("@File"):
            _diag(
                diags,
                "E_INTENT_TEMPLATE_FILE_HEADER_MISSING",
                "@File header must be first statement",
                '@File { profile:"topology" }',
                stripped,
                json_pointer(path_ref, "file_header"),
            )
            return False
        brace_idx = line.find("{")
        if brace_idx == -1:
            _diag(
                diags,
                "E_INTENT_TEMPLATE_FILE_HEADER_INVALID",
                "@File header missing metadata",
                "{...}",
                line.strip(),
                json_pointer(path_ref, "file_header"),
            )
            return False
        meta, _ = _capture_metadata(lines, idx, brace_idx)
        pairs = _parse_metadata_pairs(meta)
        meta_map = {k: v for k, v in pairs}
        profile = _strip_quotes(meta_map.get("profile"))
        if profile != "topology":
            _diag(
                diags,
                "E_INTENT_TEMPLATE_PROFILE_INVALID",
                "profile must be topology",
                "topology",
                str(profile),
                json_pointer(path_ref, "file_header", "profile"),
            )
            return False
        return True
    _diag(
        diags,
        "E_INTENT_TEMPLATE_FILE_HEADER_MISSING",
        "Missing @File header",
        '@File { profile:"topology" }',
        "missing",
        json_pointer(path_ref, "file_header"),
    )
    return False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="Topology file or directory")
    ap.add_argument("--out", default=None, help="Diff output path (default: OUTPUT/intent_template.patch)")
    ap.add_argument("--dry-run", action="store_true", help="Do not write diff output (JSON-only)")
    ap.add_argument("--generator-id", default="intent_template_gen_v0_1", help="Generator id")
    ap.add_argument("--project-root", default=None, help="Project root (defaults to repo root)")
    ap.add_argument("--overwrite", action="store_true", help="Allow overwriting existing diff output")
    args = ap.parse_args()

    project_root = Path(args.project_root).resolve() if args.project_root else ROOT
    topo_root = project_root / "sdsl2" / "topology"
    intent_root = project_root / "drafts" / "intent"
    input_path = _resolve_path(project_root, args.input)
    diff_out = _resolve_path(project_root, args.out) if args.out else project_root / DEFAULT_OUT_REL
    inputs = [_rel_path(project_root, input_path)]
    outputs = [_rel_path(project_root, diff_out)]
    diff_paths = [_rel_path(project_root, diff_out)]
    source_rev = _build_source_rev(_git_rev(project_root), args.generator_id)

    if topo_root.is_symlink() or _has_symlink_parent(topo_root, project_root):
        _emit_result(
            "fail",
            [
                Diagnostic(
                    code="E_INTENT_TEMPLATE_TOPO_ROOT_SYMLINK",
                    message="sdsl2/topology must not be symlink",
                    expected="non-symlink",
                    got=str(topo_root),
                    path=json_pointer("input"),
                )
            ],
            inputs,
            outputs,
            diff_paths,
            source_rev=source_rev,
            summary=f"{TOOL_NAME}: topo root invalid",
        )
        return 2
    if intent_root.is_symlink() or _has_symlink_parent(intent_root, project_root):
        _emit_result(
            "fail",
            [
                Diagnostic(
                    code="E_INTENT_TEMPLATE_INTENT_ROOT_SYMLINK",
                    message="drafts/intent must not be symlink",
                    expected="non-symlink",
                    got=str(intent_root),
                    path=json_pointer("out"),
                )
            ],
            inputs,
            outputs,
            diff_paths,
            source_rev=source_rev,
            summary=f"{TOOL_NAME}: intent root invalid",
        )
        return 2

    if not input_path.exists():
        _emit_result(
            "fail",
            [
                Diagnostic(
                    code="E_INTENT_TEMPLATE_INPUT_NOT_FOUND",
                    message="input not found",
                    expected="existing file or dir",
                    got=str(input_path),
                    path=json_pointer("input"),
                )
            ],
            inputs,
            outputs,
            diff_paths,
            source_rev=source_rev,
            summary=f"{TOOL_NAME}: input not found",
        )
        return 2
    if input_path.is_symlink() or _has_symlink_parent(input_path, project_root):
        _emit_result(
            "fail",
            [
                Diagnostic(
                    code="E_INTENT_TEMPLATE_INPUT_SYMLINK",
                    message="input must not be symlink",
                    expected="non-symlink",
                    got=str(input_path),
                    path=json_pointer("input"),
                )
            ],
            inputs,
            outputs,
            diff_paths,
            source_rev=source_rev,
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
                    code="E_INTENT_TEMPLATE_INPUT_NOT_SSOT",
                    message="input must be under sdsl2/topology",
                    expected="sdsl2/topology/...",
                    got=str(input_path),
                    path=json_pointer("input"),
                )
            ],
            inputs,
            outputs,
            diff_paths,
            source_rev=source_rev,
            summary=f"{TOOL_NAME}: input out of scope",
        )
        return 2

    topo_paths: list[Path] = []
    if input_path.is_dir():
        for path in sorted(input_path.rglob("*.sdsl2")):
            if path.is_file():
                if path.is_symlink() or _has_symlink_parent(path, topo_root):
                    _emit_result(
                        "fail",
                        [
                            Diagnostic(
                                code="E_INTENT_TEMPLATE_INPUT_SYMLINK",
                                message="input must not be symlink",
                                expected="non-symlink",
                                got=str(path),
                                path=json_pointer("input"),
                            )
                        ],
                        inputs,
                        outputs,
                        diff_paths,
                        source_rev=source_rev,
                        summary=f"{TOOL_NAME}: input symlink blocked",
                    )
                    return 2
                topo_paths.append(path)
    else:
        topo_paths = [input_path]

    if not topo_paths:
        _emit_result(
            "fail",
            [
                Diagnostic(
                    code="E_INTENT_TEMPLATE_INPUT_EMPTY",
                    message="no topology files found",
                    expected="*.sdsl2",
                    got=str(input_path),
                    path=json_pointer("input"),
                )
            ],
            inputs,
            outputs,
            diff_paths,
            source_rev=source_rev,
            summary=f"{TOOL_NAME}: input empty",
        )
        return 2

    try:
        input_hash = compute_input_hash(
            project_root,
            include_decisions=False,
            extra_inputs=topo_paths,
        )
    except (FileNotFoundError, ValueError, OSError, UnicodeDecodeError) as exc:
        _emit_result(
            "fail",
            [
                Diagnostic(
                    code="E_INTENT_TEMPLATE_INPUT_HASH_FAILED",
                    message="input_hash calculation failed",
                    expected="valid ssot inputs",
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

    inputs = [_rel_path(project_root, path) for path in topo_paths]
    diags: list[Diagnostic] = []
    output_chunks: list[str] = []
    for topo_path in topo_paths:
        file_diags: list[Diagnostic] = []
        try:
            rel = topo_path.resolve().relative_to(project_root.resolve()).as_posix()
        except ValueError:
            _diag(
                file_diags,
                "E_INTENT_TEMPLATE_INPUT_OUTSIDE_PROJECT",
                "topology must be under project_root",
                "project_root/...",
                str(topo_path),
                json_pointer("input"),
            )
            diags.extend(file_diags)
            continue
        try:
            lines = topo_path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError) as exc:
            _diag(
                file_diags,
                "E_INTENT_TEMPLATE_INPUT_READ_FAILED",
                "topology file must be readable UTF-8",
                "readable UTF-8 file",
                str(exc),
                json_pointer(rel),
            )
            diags.extend(file_diags)
            continue
        if not _validate_file_header(lines, file_diags, rel):
            diags.extend(file_diags)
            continue
        nodes = _collect_nodes(lines, file_diags, rel)
        if not nodes:
            _diag(
                file_diags,
                "E_INTENT_TEMPLATE_NODES_EMPTY",
                "topology file must contain @Node entries",
                "non-empty @Node list",
                rel,
                json_pointer(rel, "nodes"),
            )
            diags.extend(file_diags)
            continue
        payload = {
            "schema_version": INTENT_SCHEMA_VERSION,
            "source_rev": source_rev,
            "input_hash": input_hash.input_hash,
            "generator_id": args.generator_id,
            "scope": {"kind": "file", "value": rel},
            "nodes_proposed": nodes,
            "edge_intents_proposed": [],
            "questions": [],
            "conflicts": [],
        }
        if file_diags:
            diags.extend(file_diags)
            continue

        out_path = _default_out_path(project_root, topo_path)
        try:
            out_path.resolve().relative_to(intent_root.resolve())
        except ValueError:
            _diag(
                file_diags,
                "E_INTENT_TEMPLATE_OUTPUT_NOT_INTENT_ROOT",
                "output must be under drafts/intent",
                "drafts/intent/...",
                str(out_path),
                json_pointer("out"),
            )
            diags.extend(file_diags)
            continue
        if out_path.exists() and out_path.is_dir():
            _diag(
                file_diags,
                "E_INTENT_TEMPLATE_OUTPUT_IS_DIR",
                "output must be file",
                "file",
                str(out_path),
                json_pointer("out"),
            )
            diags.extend(file_diags)
            continue
        if out_path.exists() and out_path.is_symlink():
            _diag(
                file_diags,
                "E_INTENT_TEMPLATE_OUTPUT_SYMLINK",
                "output must not be symlink",
                "non-symlink",
                str(out_path),
                json_pointer("out"),
            )
            diags.extend(file_diags)
            continue
        if _has_symlink_parent(out_path, intent_root):
            _diag(
                file_diags,
                "E_INTENT_TEMPLATE_OUTPUT_SYMLINK_PARENT",
                "output parent must not be symlink",
                "non-symlink",
                str(out_path),
                json_pointer("out"),
            )
            diags.extend(file_diags)
            continue

        try:
            old_text = out_path.read_text(encoding="utf-8") if out_path.exists() else ""
        except (OSError, UnicodeDecodeError) as exc:
            _diag(
                file_diags,
                "E_INTENT_TEMPLATE_OUTPUT_READ_FAILED",
                "output must be readable UTF-8",
                "readable UTF-8 file",
                str(exc),
                json_pointer("out"),
            )
            diags.extend(file_diags)
            continue
        new_text = dump_yaml(payload)
        diff = difflib.unified_diff(
            old_text.splitlines(),
            new_text.splitlines(),
            fromfile=str(out_path),
            tofile=str(out_path),
            lineterm="",
        )
        chunk = "\n".join(diff)
        if chunk:
            output_chunks.append(chunk)

        if file_diags:
            diags.extend(file_diags)
            continue

    if diags:
        _emit_result(
            "fail",
            diags,
            inputs,
            outputs,
            diff_paths,
            source_rev=source_rev,
            input_hash=input_hash.input_hash,
            summary=f"{TOOL_NAME}: generation failed",
        )
        return 2
    if not output_chunks:
        _emit_result(
            "diag",
            [
                Diagnostic(
                    code="E_INTENT_TEMPLATE_NO_CHANGE",
                    message="no intent updates required",
                    expected="diff",
                    got="no change",
                    path=json_pointer("out"),
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

    if args.dry_run:
        _emit_result(
            "diag",
            [
                Diagnostic(
                    code="E_INTENT_TEMPLATE_DRY_RUN",
                    message="dry-run: diff not written",
                    expected="write diff",
                    got="dry-run",
                    path=json_pointer("out"),
                )
            ],
            inputs,
            [],
            [],
            source_rev=source_rev,
            input_hash=input_hash.input_hash,
            summary=f"{TOOL_NAME}: dry-run",
            next_actions=[f"rerun without --dry-run to write {diff_out}"],
        )
        return 0

    output_root = project_root / "OUTPUT"
    try:
        diff_out.resolve().relative_to(project_root.resolve())
    except ValueError:
        _emit_result(
            "fail",
            [
                Diagnostic(
                    code="E_INTENT_TEMPLATE_OUTSIDE_PROJECT",
                    message="out must be under project_root",
                    expected="project_root/...",
                    got=str(diff_out),
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
    try:
        diff_out.resolve().relative_to(output_root.resolve())
    except ValueError:
        _emit_result(
            "fail",
            [
                Diagnostic(
                    code="E_INTENT_TEMPLATE_OUT_NOT_OUTPUT",
                    message="out must be under OUTPUT/",
                    expected="OUTPUT/...",
                    got=str(diff_out),
                    path=json_pointer("out"),
                )
            ],
            inputs,
            outputs,
            diff_paths,
            source_rev=source_rev,
            input_hash=input_hash.input_hash,
            summary=f"{TOOL_NAME}: output must be under OUTPUT",
        )
        return 2
    if diff_out.exists() and not args.overwrite:
        _emit_result(
            "fail",
            [
                Diagnostic(
                    code="E_INTENT_TEMPLATE_OUT_EXISTS",
                    message="out already exists (use --overwrite)",
                    expected="non-existing output",
                    got=str(diff_out),
                    path=json_pointer("out"),
                )
            ],
            inputs,
            outputs,
            diff_paths,
            source_rev=source_rev,
            input_hash=input_hash.input_hash,
            summary=f"{TOOL_NAME}: output exists",
        )
        return 2
    if diff_out.exists() and diff_out.is_dir():
        _emit_result(
            "fail",
            [
                Diagnostic(
                    code="E_INTENT_TEMPLATE_OUT_IS_DIR",
                    message="out must be file",
                    expected="file",
                    got=str(diff_out),
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
    if diff_out.exists() and diff_out.is_symlink():
        _emit_result(
            "fail",
            [
                Diagnostic(
                    code="E_INTENT_TEMPLATE_OUT_SYMLINK",
                    message="out must not be symlink",
                    expected="non-symlink",
                    got=str(diff_out),
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
    if _has_symlink_parent(diff_out, project_root):
        _emit_result(
            "fail",
            [
                Diagnostic(
                    code="E_INTENT_TEMPLATE_OUT_SYMLINK_PARENT",
                    message="out parent must not be symlink",
                    expected="non-symlink",
                    got=str(diff_out),
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
    diff_out.parent.mkdir(parents=True, exist_ok=True)
    try:
        atomic_write_text(diff_out, "\n".join(output_chunks) + "\n", symlink_code="E_INTENT_TEMPLATE_OUTPUT_SYMLINK")
    except ValueError as exc:
        _emit_result(
            "fail",
            [
                Diagnostic(
                    code=str(exc),
                    message="out must not be symlink",
                    expected="non-symlink",
                    got=str(diff_out),
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
