#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import difflib
import json
import re
import sys
from hashlib import sha256
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from L1_builder.decisions_lint import parse_decisions_file
from L1_builder.evidence_lint import validate_evidence_data
from sdslv2_builder.errors import Diagnostic, json_pointer
from sdslv2_builder.op_yaml import load_yaml, dump_yaml

LOCATOR_RE = re.compile(r"^L(?P<start>\d+)-L(?P<end>\d+)$|^H:(?P<head>[^#]+)#L(?P<start_h>\d+)-L(?P<end_h>\d+)$")
ALLOWED_PREFIXES = ("design/", "docs/", "specs/", "src/", "policy/attestations/")
FORBIDDEN_ROOTS = ("drafts/", "OUTPUT/", "sdsl2/", "decisions/")


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


class Locator:
    def __init__(self, start: int, end: int) -> None:
        self.start = start
        self.end = end


def _parse_locator(value: str) -> Locator | None:
    m = LOCATOR_RE.match(value.strip())
    if not m:
        return None
    if m.group("start") and m.group("end"):
        return Locator(start=int(m.group("start")), end=int(m.group("end")))
    return Locator(start=int(m.group("start_h")), end=int(m.group("end_h")))


def _normalize_text(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _compute_content_hash(path: Path, locator: Locator) -> str:
    text = path.read_text(encoding="utf-8")
    normalized = _normalize_text(text)
    lines = normalized.split("\n")
    if locator.start < 1 or locator.end < locator.start or locator.end > len(lines):
        raise ValueError("E_EVIDENCE_REPAIR_LOCATOR_RANGE")
    selected = lines[locator.start - 1 : locator.end]
    trimmed = [line.rstrip(" \t") for line in selected]
    payload = "\n".join(trimmed)
    digest = sha256(payload.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def _compute_hash(
    project_root: Path,
    source_path: str,
    locator_str: str,
    diags: list[Diagnostic],
    path_ref: str,
) -> str | None:
    if not isinstance(source_path, str) or not source_path.strip():
        _diag(diags, "E_EVIDENCE_REPAIR_SOURCE_INVALID", "source_path required", "path", str(source_path), path_ref)
        return None
    if source_path.startswith("/") or ".." in Path(source_path).parts:
        _diag(
            diags,
            "E_EVIDENCE_REPAIR_SOURCE_INVALID",
            "source_path must be repo-relative",
            "design/|docs/|specs/|src/|policy/attestations/",
            source_path,
            path_ref,
        )
        return None
    if source_path.startswith(FORBIDDEN_ROOTS):
        _diag(
            diags,
            "E_EVIDENCE_REPAIR_SOURCE_INVALID",
            "source_path forbidden root",
            "design/|docs/|specs/|src/|policy/attestations/",
            source_path,
            path_ref,
        )
        return None
    if not source_path.startswith(ALLOWED_PREFIXES):
        _diag(
            diags,
            "E_EVIDENCE_REPAIR_SOURCE_INVALID",
            "source_path must start with allowed prefix",
            "design/|docs/|specs/|src/|policy/attestations/",
            source_path,
            path_ref,
        )
        return None
    if not isinstance(locator_str, str) or not locator_str.strip():
        _diag(diags, "E_EVIDENCE_REPAIR_LOCATOR_INVALID", "locator required", "Lx-Ly", str(locator_str), path_ref)
        return None
    locator = _parse_locator(locator_str)
    if locator is None:
        _diag(diags, "E_EVIDENCE_REPAIR_LOCATOR_INVALID", "locator invalid", "Lx-Ly or H:...#Lx-Ly", locator_str, path_ref)
        return None
    source = _resolve_path(project_root, source_path)
    try:
        _ensure_inside(project_root, source, "E_EVIDENCE_REPAIR_SOURCE_OUTSIDE_PROJECT")
    except ValueError as exc:
        _diag(diags, str(exc), "source_path must be under project_root", "project_root/...", str(source), path_ref)
        return None
    if not source.exists():
        _diag(diags, "E_EVIDENCE_REPAIR_SOURCE_NOT_FOUND", "source_path not found", "existing file", str(source), path_ref)
        return None
    if not source.is_file():
        _diag(diags, "E_EVIDENCE_REPAIR_SOURCE_NOT_FILE", "source_path must be file", "file", str(source), path_ref)
        return None
    if source.is_symlink() or _has_symlink_parent(source, project_root):
        _diag(diags, "E_EVIDENCE_REPAIR_SOURCE_SYMLINK", "source_path must not be symlink", "non-symlink", str(source), path_ref)
        return None
    try:
        return _compute_content_hash(source, locator)
    except (OSError, UnicodeDecodeError) as exc:
        _diag(
            diags,
            "E_EVIDENCE_REPAIR_SOURCE_READ_FAILED",
            "source_path must be readable UTF-8 file",
            "readable UTF-8 file",
            str(exc),
            path_ref,
        )
        return None
    except ValueError as exc:
        _diag(diags, str(exc), "locator in range", "valid range", locator_str, path_ref)
        return None


def main() -> int:
    ap = argparse.ArgumentParser()
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
        "--allow-nonstandard-path",
        action="store_true",
        help="Allow decisions/evidence outside standard paths",
    )
    ap.add_argument(
        "--out",
        default=None,
        help="Write unified diff to this path (default: stdout)",
    )
    ap.add_argument(
        "--project-root",
        default=None,
        help="Project root (defaults to repo root); inputs can be relative to it",
    )
    ap.add_argument(
        "--allow-diff",
        action="store_true",
        help="Exit 0 even when a diff is produced",
    )
    args = ap.parse_args()

    project_root = Path(args.project_root).resolve() if args.project_root else ROOT
    decisions_path = _resolve_path(project_root, args.decisions_path)
    evidence_path = _resolve_path(project_root, args.evidence_path)
    try:
        _ensure_inside(project_root, decisions_path, "E_EVIDENCE_REPAIR_INPUT_OUTSIDE_PROJECT")
        _ensure_inside(project_root, evidence_path, "E_EVIDENCE_REPAIR_INPUT_OUTSIDE_PROJECT")
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    if not decisions_path.exists():
        print("E_EVIDENCE_REPAIR_DECISIONS_NOT_FOUND", file=sys.stderr)
        return 2
    if decisions_path.is_dir():
        print("E_EVIDENCE_REPAIR_DECISIONS_IS_DIR", file=sys.stderr)
        return 2
    if decisions_path.is_symlink():
        print("E_EVIDENCE_REPAIR_DECISIONS_SYMLINK", file=sys.stderr)
        return 2
    if not args.allow_nonstandard_path:
        expected_decisions = (project_root / "decisions" / "edges.yaml").resolve()
        if decisions_path.resolve() != expected_decisions:
            print("E_EVIDENCE_REPAIR_DECISIONS_NOT_STANDARD_PATH", file=sys.stderr)
            return 2

    if not evidence_path.exists():
        print("E_EVIDENCE_REPAIR_INPUT_NOT_FOUND", file=sys.stderr)
        return 2
    if evidence_path.is_dir():
        print("E_EVIDENCE_REPAIR_INPUT_IS_DIR", file=sys.stderr)
        return 2
    if evidence_path.is_symlink():
        print("E_EVIDENCE_REPAIR_INPUT_SYMLINK", file=sys.stderr)
        return 2
    if not args.allow_nonstandard_path:
        expected_evidence = (project_root / "decisions" / "evidence.yaml").resolve()
        if evidence_path.resolve() != expected_evidence:
            print("E_EVIDENCE_REPAIR_INPUT_NOT_STANDARD_PATH", file=sys.stderr)
            return 2

    decisions, decision_diags = parse_decisions_file(decisions_path, project_root)
    if decision_diags:
        _print_diags(decision_diags)
        return 2
    try:
        data = load_yaml(evidence_path)
    except Exception as exc:
        diags: list[Diagnostic] = []
        _diag(
            diags,
            "E_EVIDENCE_REPAIR_SCHEMA_INVALID",
            "evidence yaml parse failed",
            "valid YAML",
            str(exc),
            json_pointer(),
        )
        _print_diags(diags)
        return 2
    _, evidence_diags = validate_evidence_data(data, decisions, project_root)
    if evidence_diags:
        _print_diags(evidence_diags)
        return 2
    if not isinstance(data, dict):
        print("E_EVIDENCE_REPAIR_SCHEMA_INVALID", file=sys.stderr)
        return 2

    diags: list[Diagnostic] = []
    evidence = data.get("evidence", {})
    if not isinstance(evidence, dict):
        print("E_EVIDENCE_REPAIR_SCHEMA_INVALID", file=sys.stderr)
        return 2

    changed = False
    for decision_id, items in evidence.items():
        if not isinstance(items, list):
            continue
        for idx, item in enumerate(items):
            if not isinstance(item, dict):
                continue
            source_path = item.get("source_path", "")
            locator = item.get("locator", "")
            path_ref = json_pointer("evidence", str(decision_id), str(idx))
            actual = _compute_hash(project_root, source_path, locator, diags, path_ref)
            if actual is None:
                continue
            if item.get("content_hash") != actual:
                item["content_hash"] = actual
                changed = True

    if diags:
        _print_diags(diags)
        return 2
    if not changed:
        return 0

    new_text = dump_yaml(data)
    original_text = evidence_path.read_text(encoding="utf-8")
    diff = difflib.unified_diff(
        original_text.splitlines(),
        new_text.splitlines(),
        fromfile=str(evidence_path),
        tofile=str(evidence_path),
        lineterm="",
    )
    diff_text = "\n".join(diff) + "\n"

    if args.out:
        out_path = _resolve_path(project_root, args.out)
        try:
            _ensure_inside(project_root, out_path, "E_EVIDENCE_REPAIR_OUTPUT_OUTSIDE_PROJECT")
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 2
        allowed_output = (project_root / "OUTPUT").resolve()
        try:
            out_path.resolve().relative_to(allowed_output)
        except ValueError:
            print("E_EVIDENCE_REPAIR_OUTPUT_OUTSIDE_OUTPUT", file=sys.stderr)
            return 2
        if out_path.exists() and out_path.is_symlink():
            print("E_EVIDENCE_REPAIR_OUTPUT_SYMLINK", file=sys.stderr)
            return 2
        if _has_symlink_parent(out_path, project_root):
            print("E_EVIDENCE_REPAIR_OUTPUT_SYMLINK", file=sys.stderr)
            return 2
        out_path.write_text(diff_text, encoding="utf-8")
    else:
        print(diff_text, end="")
    return 0 if args.allow_diff else 2


if __name__ == "__main__":
    raise SystemExit(main())
