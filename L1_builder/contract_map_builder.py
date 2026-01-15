#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import difflib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sdslv2_builder.errors import Diagnostic, json_pointer
from sdslv2_builder.io_atomic import atomic_write_text
from sdslv2_builder.op_yaml import DuplicateKey, dump_yaml, load_yaml_with_duplicates
from sdslv2_builder.refs import RELID_RE, parse_contract_ref


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


def _dup_path(prefix: str, dup: DuplicateKey) -> str:
    if prefix:
        if dup.path:
            return prefix + dup.path
        return prefix
    return dup.path


def _load_contract_map_input(path: Path, diags: list[Diagnostic]) -> list[dict[str, object]]:
    try:
        data, duplicates = load_yaml_with_duplicates(path, allow_duplicates=True)
    except Exception as exc:
        _diag(
            diags,
            "E_CONTRACT_MAP_INPUT_PARSE_FAILED",
            "contract_map input must be valid YAML",
            "valid YAML",
            str(exc),
            json_pointer("input"),
        )
        return []
    if duplicates:
        for dup in duplicates:
            _diag(
                diags,
                "E_CONTRACT_MAP_INPUT_DUPLICATE_KEY",
                "duplicate key in contract_map input",
                "unique key",
                dup.key,
                _dup_path(json_pointer("input"), dup),
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
            "E_CONTRACT_MAP_INPUT_INVALID",
            "contract_map input must be list or {edges:[...]}",
            "list",
            type(data).__name__,
            json_pointer("input"),
        )
        return []

    seen_ids: set[str] = set()
    edges: list[dict[str, object]] = []
    for idx, item in enumerate(items):
        edge_id = item.get("id")
        if not isinstance(edge_id, str) or not RELID_RE.match(edge_id):
            _diag(
                diags,
                "E_CONTRACT_MAP_INPUT_ID_INVALID",
                "edge id must be RELID",
                "UPPER_SNAKE_CASE",
                str(edge_id),
                json_pointer("input", str(idx), "id"),
            )
            continue
        if edge_id in seen_ids:
            _diag(
                diags,
                "E_CONTRACT_MAP_INPUT_ID_DUPLICATE",
                "duplicate edge id in input",
                "unique id",
                edge_id,
                json_pointer("input", str(idx), "id"),
            )
            continue
        seen_ids.add(edge_id)
        refs = item.get("contract_refs")
        if not isinstance(refs, list) or not refs:
            _diag(
                diags,
                "E_CONTRACT_MAP_INPUT_REFS_INVALID",
                "contract_refs must be non-empty list",
                "list",
                str(refs),
                json_pointer("input", str(idx), "contract_refs"),
            )
            continue
        cleaned: list[str] = []
        for ref_idx, ref in enumerate(refs):
            if not isinstance(ref, str) or not parse_contract_ref(ref):
                _diag(
                    diags,
                    "E_CONTRACT_MAP_INPUT_REF_INVALID",
                    "contract_refs must be CONTRACT.* tokens",
                    "CONTRACT.*",
                    str(ref),
                    json_pointer("input", str(idx), "contract_refs", str(ref_idx)),
                )
                continue
            cleaned.append(ref)
        if cleaned:
            edges.append({"id": edge_id, "contract_refs": sorted(set(cleaned))})
    return edges


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="Explicit contract_map YAML")
    ap.add_argument("--target", default="drafts/contract_map.yaml", help="Target map path under drafts/")
    ap.add_argument("--out", default=None, help="Unified diff output path (default: stdout)")
    ap.add_argument("--project-root", default=None, help="Project root (defaults to repo root)")
    args = ap.parse_args()

    project_root = Path(args.project_root).resolve() if args.project_root else ROOT
    drafts_root = project_root / "drafts"
    if drafts_root.is_symlink() or _has_symlink_parent(drafts_root, project_root):
        _print_diags(
            [
                Diagnostic(
                    code="E_CONTRACT_MAP_DRAFTS_ROOT_SYMLINK",
                    message="drafts must not be symlink",
                    expected="non-symlink",
                    got=str(drafts_root),
                    path=json_pointer("target"),
                )
            ]
        )
        return 2

    input_path = _resolve_path(project_root, args.input)
    try:
        input_path.resolve().relative_to(project_root.resolve())
    except ValueError:
        _print_diags(
            [
                Diagnostic(
                    code="E_CONTRACT_MAP_INPUT_OUTSIDE_PROJECT",
                    message="input must be under project_root",
                    expected="project_root/...",
                    got=str(input_path),
                    path=json_pointer("input"),
                )
            ]
        )
        return 2
    if not input_path.exists():
        _print_diags(
            [
                Diagnostic(
                    code="E_CONTRACT_MAP_INPUT_NOT_FOUND",
                    message="input not found",
                    expected="existing file",
                    got=str(input_path),
                    path=json_pointer("input"),
                )
            ]
        )
        return 2
    if input_path.is_dir():
        _print_diags(
            [
                Diagnostic(
                    code="E_CONTRACT_MAP_INPUT_IS_DIR",
                    message="input must be file",
                    expected="file",
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
                    code="E_CONTRACT_MAP_INPUT_SYMLINK",
                    message="input must not be symlink",
                    expected="non-symlink",
                    got=str(input_path),
                    path=json_pointer("input"),
                )
            ]
        )
        return 2

    target_path = _resolve_path(project_root, args.target)
    try:
        target_path.resolve().relative_to(drafts_root.resolve())
    except ValueError:
        _print_diags(
            [
                Diagnostic(
                    code="E_CONTRACT_MAP_TARGET_NOT_DRAFTS",
                    message="target must be under drafts/",
                    expected="drafts/...",
                    got=str(target_path),
                    path=json_pointer("target"),
                )
            ]
        )
        return 2
    if target_path.exists() and target_path.is_dir():
        _print_diags(
            [
                Diagnostic(
                    code="E_CONTRACT_MAP_TARGET_IS_DIR",
                    message="target must be file",
                    expected="file",
                    got=str(target_path),
                    path=json_pointer("target"),
                )
            ]
        )
        return 2
    if target_path.exists() and target_path.is_symlink():
        _print_diags(
            [
                Diagnostic(
                    code="E_CONTRACT_MAP_TARGET_SYMLINK",
                    message="target must not be symlink",
                    expected="non-symlink",
                    got=str(target_path),
                    path=json_pointer("target"),
                )
            ]
        )
        return 2
    if _has_symlink_parent(target_path, project_root):
        _print_diags(
            [
                Diagnostic(
                    code="E_CONTRACT_MAP_TARGET_SYMLINK_PARENT",
                    message="target parent must not be symlink",
                    expected="non-symlink",
                    got=str(target_path),
                    path=json_pointer("target"),
                )
            ]
        )
        return 2

    diags: list[Diagnostic] = []
    edges = _load_contract_map_input(input_path, diags)
    if diags:
        _print_diags(diags)
        return 2
    if not edges:
        _print_diags(
            [
                Diagnostic(
                    code="E_CONTRACT_MAP_INPUT_EMPTY",
                    message="no contract_map edges",
                    expected="non-empty edges",
                    got="empty",
                    path=json_pointer("input"),
                )
            ]
        )
        return 2

    edges_sorted = sorted(edges, key=lambda e: str(e.get("id", "")))
    output_map = {"edges": edges_sorted}
    new_text = dump_yaml(output_map)

    old_text = ""
    if target_path.exists():
        try:
            old_text = target_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            _print_diags(
                [
                    Diagnostic(
                        code="E_CONTRACT_MAP_TARGET_READ_FAILED",
                        message="target must be readable UTF-8",
                        expected="readable UTF-8 file",
                        got=str(exc),
                        path=json_pointer("target"),
                    )
                ]
            )
            return 2
    diff = difflib.unified_diff(
        old_text.splitlines(),
        new_text.splitlines(),
        fromfile=str(target_path),
        tofile=str(target_path),
        lineterm="",
    )
    output = "\n".join(diff)
    if not output:
        _print_diags(
            [
                Diagnostic(
                    code="E_CONTRACT_MAP_NO_CHANGE",
                    message="no change in contract_map",
                    expected="diff",
                    got="no change",
                    path=json_pointer("target"),
                )
            ]
        )
        return 2

    if args.out:
        out_path = _resolve_path(project_root, args.out)
        try:
            out_path.resolve().relative_to(project_root.resolve())
        except ValueError:
            _print_diags(
                [
                    Diagnostic(
                        code="E_CONTRACT_MAP_OUTSIDE_PROJECT",
                        message="out must be under project_root",
                        expected="project_root/...",
                        got=str(out_path),
                        path=json_pointer("out"),
                    )
                ]
            )
            return 2
        if out_path.exists() and out_path.is_dir():
            _print_diags(
                [
                    Diagnostic(
                        code="E_CONTRACT_MAP_OUT_IS_DIR",
                        message="out must be file",
                        expected="file",
                        got=str(out_path),
                        path=json_pointer("out"),
                    )
                ]
            )
            return 2
        if out_path.exists() and out_path.is_symlink():
            _print_diags(
                [
                    Diagnostic(
                        code="E_CONTRACT_MAP_OUT_SYMLINK",
                        message="out must not be symlink",
                        expected="non-symlink",
                        got=str(out_path),
                        path=json_pointer("out"),
                    )
                ]
            )
            return 2
        if _has_symlink_parent(out_path, project_root):
            _print_diags(
                [
                    Diagnostic(
                        code="E_CONTRACT_MAP_OUT_SYMLINK_PARENT",
                        message="out parent must not be symlink",
                        expected="non-symlink",
                        got=str(out_path),
                        path=json_pointer("out"),
                    )
                ]
            )
            return 2
        out_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            atomic_write_text(out_path, output + "\n", symlink_code="E_CONTRACT_MAP_OUT_SYMLINK")
        except ValueError as exc:
            _print_diags(
                [
                    Diagnostic(
                        code=str(exc),
                        message="out must not be symlink",
                        expected="non-symlink",
                        got=str(out_path),
                        path=json_pointer("out"),
                    )
                ]
            )
            return 2
    else:
        print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
