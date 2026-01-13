#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sdslv2_builder.errors import Diagnostic, json_pointer
from sdslv2_builder.op_yaml import load_yaml

LOCATOR_RE = re.compile(r"^L(?P<start>\d+)-L(?P<end>\d+)$|^H:(?P<head>[^#]+)#L(?P<start_h>\d+)-L(?P<end_h>\d+)$")
ALLOWED_PREFIXES = ("design/", "docs/", "specs/", "src/", "policy/attestations/")
FORBIDDEN_ROOTS = ("drafts/", "OUTPUT/", "sdsl2/", "decisions/")


@dataclass(frozen=True)
class Locator:
    start: int
    end: int
    heading: str | None


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


def _parse_locator(value: str) -> Locator | None:
    m = LOCATOR_RE.match(value.strip())
    if not m:
        return None
    if m.group("start") and m.group("end"):
        return Locator(start=int(m.group("start")), end=int(m.group("end")), heading=None)
    return Locator(
        start=int(m.group("start_h")),
        end=int(m.group("end_h")),
        heading=m.group("head"),
    )


def _normalize_text(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _compute_content_hash(path: Path, locator: Locator) -> str:
    text = path.read_text(encoding="utf-8")
    normalized = _normalize_text(text)
    lines = normalized.split("\n")
    if locator.start < 1 or locator.end < locator.start or locator.end > len(lines):
        raise ValueError("E_EVIDENCE_LOCATOR_RANGE")
    selected = lines[locator.start - 1 : locator.end]
    trimmed = [line.rstrip(" \t") for line in selected]
    payload = "\n".join(trimmed)
    digest = sha256(payload.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def _hash_for_item(
    project_root: Path,
    source_path: str,
    locator_str: str,
    path_ref: str,
    diags: list[Diagnostic],
) -> str | None:
    if not isinstance(source_path, str) or not source_path.strip():
        _diag(diags, "E_EVIDENCE_SOURCE_INVALID", "source_path required", "path", str(source_path), path_ref)
        return None
    if source_path.startswith("/") or ".." in Path(source_path).parts:
        _diag(
            diags,
            "E_EVIDENCE_SOURCE_INVALID",
            "source_path must be repo-relative",
            "design/|docs/|specs/|src/|policy/attestations/",
            source_path,
            path_ref,
        )
        return None
    if source_path.startswith(FORBIDDEN_ROOTS):
        _diag(
            diags,
            "E_EVIDENCE_SOURCE_INVALID",
            "source_path forbidden root",
            "design/|docs/|specs/|src/|policy/attestations/",
            source_path,
            path_ref,
        )
        return None
    if not source_path.startswith(ALLOWED_PREFIXES):
        _diag(
            diags,
            "E_EVIDENCE_SOURCE_INVALID",
            "source_path must start with allowed prefix",
            "design/|docs/|specs/|src/|policy/attestations/",
            source_path,
            path_ref,
        )
        return None
    if not isinstance(locator_str, str) or not locator_str.strip():
        _diag(diags, "E_EVIDENCE_LOCATOR_INVALID", "locator required", "Lx-Ly", str(locator_str), path_ref)
        return None
    locator = _parse_locator(locator_str)
    if locator is None:
        _diag(diags, "E_EVIDENCE_LOCATOR_INVALID", "locator invalid", "Lx-Ly or H:...#Lx-Ly", locator_str, path_ref)
        return None
    source = _resolve_path(project_root, source_path)
    try:
        _ensure_inside(project_root, source, "E_EVIDENCE_SOURCE_OUTSIDE_PROJECT")
    except ValueError as exc:
        _diag(diags, str(exc), "source_path must be under project_root", "project_root/...", str(source), path_ref)
        return None
    if not source.exists():
        _diag(diags, "E_EVIDENCE_SOURCE_NOT_FOUND", "source_path not found", "existing file", str(source), path_ref)
        return None
    if not source.is_file():
        _diag(diags, "E_EVIDENCE_SOURCE_NOT_FILE", "source_path must be file", "file", str(source), path_ref)
        return None
    if source.is_symlink() or _has_symlink_parent(source, project_root):
        _diag(diags, "E_EVIDENCE_SOURCE_SYMLINK", "source_path must not be symlink", "non-symlink", str(source), path_ref)
        return None
    try:
        return _compute_content_hash(source, locator)
    except (OSError, UnicodeDecodeError) as exc:
        _diag(
            diags,
            "E_EVIDENCE_SOURCE_READ_FAILED",
            "source_path must be readable UTF-8 file",
            "readable UTF-8 file",
            str(exc),
            path_ref,
        )
        return None
    except ValueError as exc:
        _diag(diags, str(exc), "locator in range", "valid range", locator_str, path_ref)
        return None


def _verify_evidence_file(project_root: Path, evidence_path: Path) -> int:
    diags: list[Diagnostic] = []
    try:
        data = load_yaml(evidence_path)
    except Exception as exc:
        _diag(
            diags,
            "E_EVIDENCE_SCHEMA_INVALID",
            "evidence yaml parse failed",
            "valid YAML",
            str(exc),
            json_pointer(),
        )
        _print_diags(diags)
        return 2
    if not isinstance(data, dict):
        _diag(diags, "E_EVIDENCE_SCHEMA_INVALID", "evidence root must be object", "object", type(data).__name__, json_pointer())
        _print_diags(diags)
        return 2
    evidence = data.get("evidence", {})
    if not isinstance(evidence, dict):
        _diag(diags, "E_EVIDENCE_SCHEMA_INVALID", "evidence must be object", "object", type(evidence).__name__, json_pointer("evidence"))
        _print_diags(diags)
        return 2

    for decision_id, items in evidence.items():
        if not isinstance(items, list):
            _diag(
                diags,
                "E_EVIDENCE_SCHEMA_INVALID",
                "evidence list must be list",
                "list",
                type(items).__name__,
                json_pointer("evidence", str(decision_id)),
            )
            continue
        for idx, item in enumerate(items):
            if not isinstance(item, dict):
                _diag(
                    diags,
                    "E_EVIDENCE_SCHEMA_INVALID",
                    "evidence item must be object",
                    "object",
                    type(item).__name__,
                    json_pointer("evidence", str(decision_id), str(idx)),
                )
                continue
            source_path = item.get("source_path", "")
            locator = item.get("locator", "")
            expected_hash = item.get("content_hash", "")
            path_ref = json_pointer("evidence", str(decision_id), str(idx))
            actual = _hash_for_item(project_root, source_path, locator, path_ref, diags)
            if actual is None:
                continue
            if not isinstance(expected_hash, str) or not expected_hash.startswith("sha256:"):
                _diag(
                    diags,
                    "E_EVIDENCE_FIELD_INVALID",
                    "content_hash must start with sha256:",
                    "sha256:<hex>",
                    str(expected_hash),
                    json_pointer("evidence", str(decision_id), str(idx), "content_hash"),
                )
                continue
            if actual != expected_hash:
                _diag(
                    diags,
                    "E_EVIDENCE_HASH_MISMATCH",
                    "content_hash mismatch",
                    expected_hash,
                    actual,
                    json_pointer("evidence", str(decision_id), str(idx), "content_hash"),
                )

    if diags:
        _print_diags(diags)
        return 2
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Compute or verify evidence content_hash values.",
        epilog=(
            "Normalization rules:\n"
            "- CRLF/CR are normalized to LF.\n"
            "- Line numbers are 1-based on normalized text; range is inclusive.\n"
            "- Trailing spaces/tabs are trimmed per line before hashing.\n"
            "- Selected lines are joined with '\\n' (no extra newline).\n"
            "- If a file ends with '\\n', the final empty line counts.\n"
        ),
    )
    ap.add_argument("--source-path", default=None, help="Source file path (repo-relative)")
    ap.add_argument("--locator", default=None, help="Locator (Lx-Ly or H:...#Lx-Ly) on normalized text")
    ap.add_argument("--verify", default=None, help="Evidence YAML path to verify")
    ap.add_argument(
        "--project-root",
        default=None,
        help="Project root (defaults to repo root); inputs can be relative to it",
    )
    args = ap.parse_args()

    project_root = Path(args.project_root).resolve() if args.project_root else ROOT

    if args.verify:
        evidence_path = _resolve_path(project_root, args.verify)
        try:
            _ensure_inside(project_root, evidence_path, "E_EVIDENCE_INPUT_OUTSIDE_PROJECT")
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 2
        if not evidence_path.exists():
            print("E_EVIDENCE_INPUT_NOT_FOUND", file=sys.stderr)
            return 2
        if evidence_path.is_dir():
            print("E_EVIDENCE_INPUT_IS_DIR", file=sys.stderr)
            return 2
        if evidence_path.is_symlink():
            print("E_EVIDENCE_INPUT_SYMLINK", file=sys.stderr)
            return 2
        if _has_symlink_parent(evidence_path, project_root):
            print("E_EVIDENCE_INPUT_SYMLINK_PARENT", file=sys.stderr)
            return 2
        return _verify_evidence_file(project_root, evidence_path)

    if not args.source_path or not args.locator:
        print("E_EVIDENCE_HASH_ARGS_MISSING", file=sys.stderr)
        return 2
    diags: list[Diagnostic] = []
    content_hash = _hash_for_item(
        project_root,
        args.source_path,
        args.locator,
        json_pointer(),
        diags,
    )
    if diags or content_hash is None:
        _print_diags(diags)
        return 2
    print(content_hash)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
