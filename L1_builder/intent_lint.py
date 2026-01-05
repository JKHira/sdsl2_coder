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
from sdslv2_builder.intent_schema import normalize_intent
from sdslv2_builder.op_yaml import load_yaml


def _diag(diags: list[Diagnostic], code: str, message: str, expected: str, got: str, path: str) -> None:
    diags.append(Diagnostic(code=code, message=message, expected=expected, got=got, path=path))


def _print_diags(diags: list[Diagnostic]) -> None:
    payload = [d.to_dict() for d in diags]
    print(json.dumps(payload, ensure_ascii=False, indent=2), file=sys.stderr)


def _resolve_path(project_root: Path, raw: str) -> Path:
    path = Path(raw)
    if not path.is_absolute():
        path = (project_root / path).resolve()
    return path


def _ensure_inside(project_root: Path, path: Path, code: str) -> None:
    try:
        path.resolve().relative_to(project_root.resolve())
    except ValueError as exc:
        raise ValueError(code) from exc


def _has_symlink_parent(path: Path, stop: Path) -> bool:
    for parent in [path, *path.parents]:
        if parent == stop:
            break
        if parent.is_symlink():
            return True
    return False


def _collect_inputs(
    inputs: list[str],
    project_root: Path,
    intent_root: Path,
    allow_nonstandard: bool,
    allow_empty: bool,
) -> tuple[list[Path], list[Diagnostic]]:
    files: list[Path] = []
    diags: list[Diagnostic] = []

    for raw in inputs:
        path = _resolve_path(project_root, raw)
        try:
            _ensure_inside(project_root, path, "E_INTENT_INPUT_OUTSIDE_PROJECT")
        except ValueError as exc:
            _diag(diags, str(exc), "input must be under project_root", "project_root/...", str(path), json_pointer())
            continue
        if not path.exists():
            _diag(diags, "E_INTENT_INPUT_NOT_FOUND", "input not found", "existing file/dir", str(path), json_pointer())
            continue
        if path.is_symlink() or _has_symlink_parent(path, project_root):
            _diag(diags, "E_INTENT_INPUT_SYMLINK", "symlink not allowed", "non-symlink", str(path), json_pointer())
            continue
        if path.is_dir():
            for file_path in sorted(path.rglob("*.yaml")):
                if file_path.is_symlink() or _has_symlink_parent(file_path, project_root):
                    _diag(
                        diags,
                        "E_INTENT_INPUT_SYMLINK",
                        "symlink not allowed",
                        "non-symlink",
                        str(file_path),
                        json_pointer(),
                    )
                    continue
                files.append(file_path)
        elif path.is_file():
            files.append(path)
        else:
            _diag(diags, "E_INTENT_INPUT_NOT_FILE", "input must be file or dir", "file|dir", str(path), json_pointer())

    if not files and not allow_empty and not diags:
        _diag(diags, "E_INTENT_INPUT_NOT_FOUND", "no intent yaml found", "drafts/intent/*.yaml", "empty", json_pointer())

    if not allow_nonstandard:
        for file_path in files:
            try:
                file_path.resolve().relative_to(intent_root.resolve())
            except ValueError:
                _diag(
                    diags,
                    "E_INTENT_INPUT_NOT_STANDARD_PATH",
                    "intent must be under drafts/intent",
                    "drafts/intent/*.yaml",
                    str(file_path),
                    json_pointer(),
                )
    return files, diags


def _lint_file(path: Path) -> list[Diagnostic]:
    diags: list[Diagnostic] = []
    try:
        data = load_yaml(path)
    except Exception as exc:
        _diag(
            diags,
            "E_INTENT_PARSE_FAILED",
            "intent yaml parse failed",
            "valid yaml",
            str(exc),
            json_pointer(),
        )
        return diags
    if not isinstance(data, dict):
        _diag(
            diags,
            "E_INTENT_SCHEMA_INVALID",
            "Intent root must be object",
            "object",
            type(data).__name__,
            json_pointer(),
        )
        return diags
    _, file_diags = normalize_intent(data, fill_missing=False)
    diags.extend(file_diags)
    return diags


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", action="append", required=True, help="Intent YAML file or directory")
    ap.add_argument(
        "--allow-nonstandard-path",
        action="store_true",
        help="Allow intent yaml outside drafts/intent",
    )
    ap.add_argument(
        "--allow-empty",
        action="store_true",
        help="Exit 0 when no intent yaml is found",
    )
    ap.add_argument(
        "--project-root",
        default=None,
        help="Project root (defaults to repo root); inputs can be relative to it",
    )
    args = ap.parse_args()

    project_root = Path(args.project_root).resolve() if args.project_root else ROOT
    intent_root = (project_root / "drafts" / "intent").resolve()

    files, diags = _collect_inputs(
        args.input,
        project_root,
        intent_root,
        args.allow_nonstandard_path,
        args.allow_empty,
    )
    if diags:
        _print_diags(diags)
        return 2

    all_diags: list[Diagnostic] = []
    for file_path in files:
        all_diags.extend(_lint_file(file_path))

    if all_diags:
        _print_diags(all_diags)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
