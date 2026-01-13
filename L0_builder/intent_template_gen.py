#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
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


def _diag(
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
    return sorted(nodes, key=lambda item: item.get("id", ""))


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
    ap.add_argument("--out", default=None, help="Output YAML path (single input only)")
    ap.add_argument("--dry-run", action="store_true", help="Print YAML to stdout (single input only)")
    ap.add_argument("--generator-id", default="intent_template_gen_v0_1", help="Generator id")
    ap.add_argument("--project-root", default=None, help="Project root (defaults to repo root)")
    ap.add_argument("--overwrite", action="store_true", help="Allow overwriting existing output files")
    args = ap.parse_args()

    project_root = Path(args.project_root).resolve() if args.project_root else ROOT
    topo_root = project_root / "sdsl2" / "topology"
    intent_root = project_root / "drafts" / "intent"

    if topo_root.is_symlink() or _has_symlink_parent(topo_root, project_root):
        _print_diags(
            [
                Diagnostic(
                    code="E_INTENT_TEMPLATE_TOPO_ROOT_SYMLINK",
                    message="sdsl2/topology must not be symlink",
                    expected="non-symlink",
                    got=str(topo_root),
                    path=json_pointer("input"),
                )
            ]
        )
        return 2
    if intent_root.is_symlink() or _has_symlink_parent(intent_root, project_root):
        _print_diags(
            [
                Diagnostic(
                    code="E_INTENT_TEMPLATE_INTENT_ROOT_SYMLINK",
                    message="drafts/intent must not be symlink",
                    expected="non-symlink",
                    got=str(intent_root),
                    path=json_pointer("out"),
                )
            ]
        )
        return 2

    input_path = _resolve_path(project_root, args.input)
    if not input_path.exists():
        _print_diags(
            [
                Diagnostic(
                    code="E_INTENT_TEMPLATE_INPUT_NOT_FOUND",
                    message="input not found",
                    expected="existing file or dir",
                    got=str(input_path),
                    path=json_pointer("input"),
                )
            ]
        )
        return 2
    if input_path.is_symlink() or _has_symlink_parent(input_path, project_root):
        _print_diags(
            [
                Diagnostic(
                    code="E_INTENT_TEMPLATE_INPUT_SYMLINK",
                    message="input must not be symlink",
                    expected="non-symlink",
                    got=str(input_path),
                    path=json_pointer("input"),
                )
            ]
        )
        return 2
    try:
        input_path.resolve().relative_to(topo_root.resolve())
    except ValueError:
        _print_diags(
            [
                Diagnostic(
                    code="E_INTENT_TEMPLATE_INPUT_NOT_SSOT",
                    message="input must be under sdsl2/topology",
                    expected="sdsl2/topology/...",
                    got=str(input_path),
                    path=json_pointer("input"),
                )
            ]
        )
        return 2

    topo_paths: list[Path] = []
    if input_path.is_dir():
        for path in sorted(input_path.rglob("*.sdsl2")):
            if path.is_file():
                if path.is_symlink() or _has_symlink_parent(path, topo_root):
                    _print_diags(
                        [
                            Diagnostic(
                                code="E_INTENT_TEMPLATE_INPUT_SYMLINK",
                                message="input must not be symlink",
                                expected="non-symlink",
                                got=str(path),
                                path=json_pointer("input"),
                            )
                        ]
                    )
                    return 2
                topo_paths.append(path)
    else:
        topo_paths = [input_path]

    if not topo_paths:
        _print_diags(
            [
                Diagnostic(
                    code="E_INTENT_TEMPLATE_INPUT_EMPTY",
                    message="no topology files found",
                    expected="*.sdsl2",
                    got=str(input_path),
                    path=json_pointer("input"),
                )
            ]
        )
        return 2

    if args.out and len(topo_paths) != 1:
        _print_diags(
            [
                Diagnostic(
                    code="E_INTENT_TEMPLATE_OUT_MULTI",
                    message="--out requires single input",
                    expected="single file input",
                    got="multiple inputs",
                    path=json_pointer("out"),
                )
            ]
        )
        return 2
    if args.dry_run and len(topo_paths) != 1:
        _print_diags(
            [
                Diagnostic(
                    code="E_INTENT_TEMPLATE_DRYRUN_MULTI",
                    message="--dry-run requires single input",
                    expected="single file input",
                    got="multiple inputs",
                    path=json_pointer("dry_run"),
                )
            ]
        )
        return 2

    try:
        input_hash = compute_input_hash(project_root, include_decisions=False)
    except (FileNotFoundError, ValueError, OSError, UnicodeDecodeError) as exc:
        _print_diags(
            [
                Diagnostic(
                    code="E_INTENT_TEMPLATE_INPUT_HASH_FAILED",
                    message="input_hash calculation failed",
                    expected="valid ssot inputs",
                    got=str(exc),
                    path=json_pointer("input_hash"),
                )
            ]
        )
        return 2

    source_rev = _git_rev(project_root)
    diags: list[Diagnostic] = []
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
                json_pointer("nodes"),
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

        if args.out:
            out_path = _resolve_path(project_root, args.out)
        else:
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
        if out_path.exists() and not args.overwrite and not args.dry_run:
            _diag(
                file_diags,
                "E_INTENT_TEMPLATE_OUTPUT_EXISTS",
                "output already exists",
                "use --overwrite",
                str(out_path),
                json_pointer("out"),
            )
            diags.extend(file_diags)
            continue

        text = dump_yaml(payload)
        if args.dry_run:
            print(text, end="")
        else:
            out_path.parent.mkdir(parents=True, exist_ok=True)
            try:
                atomic_write_text(out_path, text, symlink_code="E_INTENT_TEMPLATE_OUTPUT_SYMLINK")
            except ValueError as exc:
                _diag(
                    file_diags,
                    str(exc),
                    "output must not be symlink",
                    "non-symlink",
                    str(out_path),
                    json_pointer("out"),
                )
                diags.extend(file_diags)
                continue
        if file_diags:
            diags.extend(file_diags)
            continue

    if diags:
        _print_diags(diags)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
