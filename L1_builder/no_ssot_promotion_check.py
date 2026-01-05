#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sdslv2_builder.errors import Diagnostic


def _diag(diags: list[Diagnostic], code: str, message: str, expected: str, got: str, path: str) -> None:
    diags.append(Diagnostic(code=code, message=message, expected=expected, got=got, path=path))


def _print_diags(diags: list[Diagnostic]) -> None:
    payload = [d.to_dict() for d in diags]
    print(json.dumps(payload, ensure_ascii=False, indent=2), file=sys.stderr)


def _walk_no_symlink(root: Path, diags: list[Diagnostic]) -> None:
    if not root.exists():
        return
    if root.is_symlink():
        _diag(
            diags,
            "E_NO_SSOT_PROMOTION_SYMLINK",
            "symlink not allowed under root",
            "non-symlink",
            str(root),
            str(root),
        )
        return
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        for name in dirnames + filenames:
            path = Path(dirpath) / name
            if path.is_symlink():
                _diag(
                    diags,
                    "E_NO_SSOT_PROMOTION_SYMLINK",
                    "symlink not allowed under root",
                    "non-symlink",
                    str(path),
                    str(path),
                )


def _scan_root_for_markers(
    root: Path,
    rel_root: str,
    diags: list[Diagnostic],
    draft_codes: tuple[str, str],
    evidence_code: str | None,
    exception_code: str | None,
) -> None:
    if not root.exists():
        return
    for path in root.rglob("*"):
        if not path.exists():
            continue
        try:
            rel = path.relative_to(root)
        except ValueError:
            continue
        parts = set(rel.parts)
        if "drafts" in parts or "intent" in parts:
            _diag(
                diags,
                draft_codes[0],
                draft_codes[1],
                "no drafts/intent under root",
                str(rel),
                f"{rel_root}/{rel.as_posix()}",
            )
        if evidence_code and path.name == "evidence.yaml":
            _diag(
                diags,
                evidence_code,
                "evidence.yaml must not be under root",
                "decisions/evidence.yaml only",
                str(rel),
                f"{rel_root}/{rel.as_posix()}",
            )
        if exception_code and path.name == "exceptions.yaml":
            _diag(
                diags,
                exception_code,
                "exceptions.yaml must not be under root",
                "policy/exceptions.yaml only",
                str(rel),
                f"{rel_root}/{rel.as_posix()}",
            )


def _check_exception_path(project_root: Path, diags: list[Diagnostic]) -> None:
    expected = (project_root / "policy" / "exceptions.yaml").resolve()
    for path in project_root.rglob("exceptions.yaml"):
        if path.resolve() == expected:
            continue
        _diag(
            diags,
            "E_NO_SSOT_PROMOTION_EXCEPTION_PATH_INVALID",
            "exceptions.yaml must be at policy/exceptions.yaml",
            "policy/exceptions.yaml",
            str(path),
            str(path),
        )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--project-root",
        default=None,
        help="Project root (defaults to repo root); checks apply under this root",
    )
    args = ap.parse_args()

    project_root = Path(args.project_root).resolve() if args.project_root else ROOT
    sdsl2_root = project_root / "sdsl2"
    decisions_root = project_root / "decisions"

    diags: list[Diagnostic] = []
    _walk_no_symlink(sdsl2_root, diags)
    _walk_no_symlink(decisions_root, diags)

    _scan_root_for_markers(
        sdsl2_root,
        "sdsl2",
        diags,
        ("E_NO_SSOT_PROMOTION_DRAFT_IN_SSOT", "drafts/intent under sdsl2 is forbidden"),
        "E_NO_SSOT_PROMOTION_EVIDENCE_IN_SSOT",
        "E_NO_SSOT_PROMOTION_EXCEPTION_IN_SSOT",
    )
    _scan_root_for_markers(
        decisions_root,
        "decisions",
        diags,
        ("E_NO_SSOT_PROMOTION_DRAFT_IN_DECISIONS", "drafts/intent under decisions is forbidden"),
        None,
        "E_NO_SSOT_PROMOTION_EXCEPTION_IN_DECISIONS",
    )
    _check_exception_path(project_root, diags)

    if diags:
        _print_diags(diags)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
