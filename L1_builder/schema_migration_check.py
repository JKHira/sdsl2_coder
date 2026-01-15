#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sdslv2_builder.errors import Diagnostic, json_pointer
from sdslv2_builder.op_yaml import load_yaml

VERSION_RE = re.compile(r"^(?P<major>\d+)\.(?P<minor>\d+)$")


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


def _collect_yaml_files(
    root: Path,
    project_root: Path,
    diags: list[Diagnostic],
    group: str,
    exclude_dirs: list[Path] | None = None,
) -> list[Path]:
    files: list[Path] = []
    if not root.exists():
        return files
    if root.is_symlink() or _has_symlink_parent(root, project_root):
        _diag(
            diags,
            "E_SCHEMA_MIGRATION_SYMLINK",
            "symlink not allowed in input root",
            "non-symlink",
            str(root),
            json_pointer(group),
        )
        return files
    for path in sorted(root.rglob("*.yaml")):
        if exclude_dirs and any(exclude_dir in path.parents for exclude_dir in exclude_dirs):
            continue
        if path.is_symlink() or _has_symlink_parent(path, project_root):
            _diag(
                diags,
                "E_SCHEMA_MIGRATION_SYMLINK",
                "symlink not allowed in inputs",
                "non-symlink",
                str(path),
                json_pointer(group, path.as_posix()),
            )
            continue
        try:
            _ensure_inside(project_root, path, "E_SCHEMA_MIGRATION_INPUT_OUTSIDE_PROJECT")
        except ValueError as exc:
            _diag(
                diags,
                str(exc),
                "input must be under project_root",
                "project_root/...",
                str(path),
                json_pointer(group, path.as_posix()),
            )
            continue
        if path.is_file():
            files.append(path)
    return files


def _load_schema_version(path: Path, diags: list[Diagnostic]) -> int | None:
    try:
        data = load_yaml(path)
    except Exception as exc:
        _diag(
            diags,
            "E_SCHEMA_MIGRATION_PARSE_FAILED",
            "YAML parse failed",
            "valid YAML",
            str(exc),
            json_pointer(),
        )
        return None
    if not isinstance(data, dict):
        _diag(
            diags,
            "E_SCHEMA_MIGRATION_SCHEMA_INVALID",
            "root must be object",
            "object",
            type(data).__name__,
            json_pointer(),
        )
        return None
    raw = data.get("schema_version")
    if not isinstance(raw, str):
        _diag(
            diags,
            "E_SCHEMA_MIGRATION_SCHEMA_INVALID",
            "schema_version must be string",
            "MAJOR.MINOR",
            str(raw),
            json_pointer("schema_version"),
        )
        return None
    m = VERSION_RE.match(raw.strip())
    if not m:
        _diag(
            diags,
            "E_SCHEMA_MIGRATION_SCHEMA_INVALID",
            "schema_version must be MAJOR.MINOR",
            "MAJOR.MINOR",
            raw,
            json_pointer("schema_version"),
        )
        return None
    return int(m.group("major"))


def _check_group(name: str, files: list[Path], diags: list[Diagnostic]) -> None:
    majors: list[int] = []
    majors_by_file: dict[Path, int] = {}
    for path in files:
        major = _load_schema_version(path, diags)
        if major is None:
            continue
        majors.append(major)
        majors_by_file[path] = major
    if not majors:
        return
    unique = sorted(set(majors))
    if len(unique) <= 1:
        return
    counts = {major: majors.count(major) for major in unique}
    canonical = sorted(counts.items(), key=lambda item: (-item[1], item[0]))[0][0]
    for path, major in majors_by_file.items():
        if major != canonical:
            _diag(
                diags,
                "E_SCHEMA_MIGRATION_MAJOR_MISMATCH",
                f"schema_version major mismatch in {name}",
                f"major {canonical}",
                f"major {major}",
                json_pointer(name, path.as_posix()),
            )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--project-root",
        default=None,
        help="Project root (defaults to repo root)",
    )
    ap.add_argument(
        "--decisions-path",
        default="decisions/edges.yaml",
        help="decisions/edges.yaml path",
    )
    ap.add_argument(
        "--evidence-path",
        default="decisions/evidence.yaml",
        help="decisions/evidence.yaml path",
    )
    ap.add_argument(
        "--contracts-path",
        default="decisions/contracts.yaml",
        help="decisions/contracts.yaml path",
    )
    ap.add_argument(
        "--exceptions-path",
        default="policy/exceptions.yaml",
        help="policy/exceptions.yaml path",
    )
    args = ap.parse_args()

    project_root = Path(args.project_root).resolve() if args.project_root else ROOT
    diags: list[Diagnostic] = []

    drafts_root = project_root / "drafts"
    intent_root = drafts_root / "intent"
    ledger_root = drafts_root / "ledger"
    skip_draft_names = {"contract_map.yaml"}
    draft_files = _collect_yaml_files(
        drafts_root,
        project_root,
        diags,
        "drafts",
        exclude_dirs=[intent_root, ledger_root],
    )
    if skip_draft_names:
        draft_files = [path for path in draft_files if path.name not in skip_draft_names]
    intent_files = _collect_yaml_files(intent_root, project_root, diags, "intent")

    decision_files: list[Path] = []
    evidence_files: list[Path] = []
    contract_files: list[Path] = []
    exception_files: list[Path] = []

    for raw, target, name in [
        (args.decisions_path, decision_files, "decisions"),
        (args.evidence_path, evidence_files, "evidence"),
        (args.contracts_path, contract_files, "contracts"),
        (args.exceptions_path, exception_files, "exceptions"),
    ]:
        path = _resolve_path(project_root, raw)
        try:
            _ensure_inside(project_root, path, "E_SCHEMA_MIGRATION_INPUT_OUTSIDE_PROJECT")
        except ValueError as exc:
            _diag(
                diags,
                str(exc),
                "input must be under project_root",
                "project_root/...",
                str(path),
                json_pointer(name),
            )
            continue
        if path.exists():
            if path.is_symlink() or _has_symlink_parent(path, project_root):
                _diag(
                    diags,
                    "E_SCHEMA_MIGRATION_SYMLINK",
                    "symlink not allowed in inputs",
                    "non-symlink",
                    str(path),
                    json_pointer(name),
                )
                continue
            if path.is_file():
                target.append(path)
            else:
                _diag(
                    diags,
                    "E_SCHEMA_MIGRATION_INPUT_NOT_FILE",
                    "input must be file",
                    "file",
                    str(path),
                    json_pointer(name),
                )
    _check_group("drafts", draft_files, diags)
    _check_group("intent", intent_files, diags)
    _check_group("decisions", decision_files, diags)
    _check_group("evidence", evidence_files, diags)
    _check_group("contracts", contract_files, diags)
    _check_group("exceptions", exception_files, diags)

    if diags:
        _print_diags(diags)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
