#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sdslv2_builder.errors import Diagnostic, json_pointer
from sdslv2_builder.op_yaml import DuplicateKey, load_yaml_with_duplicates


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


def _has_symlink_parent(path: Path, stop: Path) -> bool:
    for parent in [path, *path.parents]:
        if parent == stop:
            break
        if parent.is_symlink():
            return True
    return False


def _iter_yaml_files(path: Path) -> list[Path]:
    exts = {".yaml", ".yml", ".json"}
    if path.is_file():
        return [path] if path.suffix.lower() in exts else []
    return sorted(p for p in path.rglob("*") if p.is_file() and p.suffix.lower() in exts)


def _collect_inputs(
    inputs: list[str],
    project_root: Path,
) -> tuple[list[Path], list[Diagnostic]]:
    files: list[Path] = []
    diags: list[Diagnostic] = []
    for raw in inputs:
        path = Path(raw)
        if not path.is_absolute():
            path = (project_root / path).resolve()
        try:
            path.resolve().relative_to(project_root.resolve())
        except ValueError:
            _diag(
                diags,
                "E_DUPLICATE_KEY_INPUT_OUTSIDE_PROJECT",
                "input must be under project_root",
                "project_root/...",
                str(path),
                json_pointer(),
            )
            continue
        if not path.exists():
            continue
        if path.is_symlink() or _has_symlink_parent(path, project_root):
            continue
        files.extend(_iter_yaml_files(path))
    return files, diags


def _format_got(path: Path, dup: DuplicateKey, project_root: Path) -> str:
    try:
        rel = path.resolve().relative_to(project_root.resolve()).as_posix()
    except ValueError:
        rel = str(path)
    return f"{rel} line {dup.line} key {dup.key}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", action="append", required=True, help="YAML file or directory path.")
    ap.add_argument(
        "--project-root",
        default=None,
        help="Project root (defaults to repo root); inputs can be relative to it",
    )
    args = ap.parse_args()

    project_root = Path(args.project_root).resolve() if args.project_root else ROOT
    files, diags = _collect_inputs(args.input, project_root)
    if diags:
        _print_diags(diags)
        return 2

    dup_diags: list[Diagnostic] = []
    for path in files:
        try:
            _, duplicates = load_yaml_with_duplicates(path, allow_duplicates=True)
        except Exception as exc:
            _diag(
                dup_diags,
                "E_DUPLICATE_KEY_PARSE_FAILED",
                "yaml parse failed",
                "valid YAML",
                f"{path}: {exc}",
                json_pointer(),
            )
            continue
        for dup in duplicates:
            _diag(
                dup_diags,
                "E_YAML_DUPLICATE_KEY",
                "duplicate key in mapping; remove the duplicate entry",
                "single key within mapping",
                _format_got(path, dup, project_root),
                dup.path or json_pointer(),
            )

    if dup_diags:
        _print_diags(dup_diags)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
