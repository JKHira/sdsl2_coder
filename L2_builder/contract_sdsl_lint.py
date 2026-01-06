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

from L2_builder.common import ROOT as REPO_ROOT, ensure_inside, has_symlink_parent, resolve_path
from sdslv2_builder.errors import Diagnostic, json_pointer
from sdslv2_builder.lint import _capture_metadata, _parse_metadata_pairs
from sdslv2_builder.refs import RELID_RE

KIND_RE = re.compile(r"^\s*@(?P<kind>[A-Za-z_][A-Za-z0-9_]*)\b")
PLACEHOLDER_RE = re.compile(r"\b(None|TBD|Opaque)\b")

CONTRACT_KINDS = {
    "File",
    "DocMeta",
    "Structure",
    "Interface",
    "Function",
    "Const",
    "Type",
    "Dep",
    "Rule",
}


def _diag(diags: list[Diagnostic], code: str, message: str, expected: str, got: str, path: str) -> None:
    diags.append(Diagnostic(code=code, message=message, expected=expected, got=got, path=path))


def _print_diags(diags: list[Diagnostic]) -> None:
    payload = [d.to_dict() for d in diags]
    print(json.dumps(payload, ensure_ascii=False, indent=2), file=sys.stderr)


def _strip_quotes(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] == '"':
        return value[1:-1]
    return value


def _strip_strings(text: str) -> str:
    out: list[str] = []
    in_str = False
    escape = False
    for ch in text:
        if in_str:
            if escape:
                escape = False
                continue
            if ch == "\\":
                escape = True
                continue
            if ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
            continue
        out.append(ch)
    return "".join(out)


def _strip_block_comments(text: str, in_block: bool) -> tuple[str, bool]:
    out: list[str] = []
    i = 0
    while i < len(text):
        if in_block:
            end = text.find("*/", i)
            if end == -1:
                return "".join(out), True
            i = end + 2
            in_block = False
            continue
        start = text.find("/*", i)
        if start == -1:
            out.append(text[i:])
            break
        out.append(text[i:start])
        i = start + 2
        in_block = True
    return "".join(out), in_block


def _first_stmt_line(lines: list[str]) -> int | None:
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if stripped == "" or stripped.startswith("//"):
            continue
        return idx
    return None


def _file_meta(lines: list[str], diags: list[Diagnostic]) -> tuple[str | None, str | None, str | None]:
    file_lines = [idx for idx, line in enumerate(lines) if line.lstrip().startswith("@File")]
    if not file_lines:
        _diag(diags, "E_FILE_HEADER_MISSING", "Missing @File header", "@File", "missing", json_pointer())
        return None, None, None

    first_stmt = _first_stmt_line(lines)
    if first_stmt is not None and file_lines[0] != first_stmt:
        _diag(
            diags,
            "E_FILE_HEADER_NOT_FIRST",
            "@File must be first non-blank statement",
            "first statement",
            "later statement",
            json_pointer(),
        )
    if len(file_lines) > 1:
        _diag(
            diags,
            "E_FILE_HEADER_DUPLICATE",
            "Duplicate @File header",
            "single @File",
            "multiple",
            json_pointer(),
        )

    idx = file_lines[0]
    line = lines[idx]
    brace_idx = line.find("{")
    if brace_idx == -1:
        return None, None, None
    meta, _ = _capture_metadata(lines, idx, brace_idx)
    pairs = _parse_metadata_pairs(meta)
    profile = None
    id_prefix = None
    stage = None
    for key, value in pairs:
        if key == "profile":
            profile = _strip_quotes(value)
        elif key == "id_prefix":
            id_prefix = _strip_quotes(value)
        elif key == "stage":
            stage = _strip_quotes(value)
    return profile, id_prefix, stage


def _check_placeholders(lines: list[str], diags: list[Diagnostic]) -> None:
    in_block = False
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if stripped == "" or stripped.startswith("//"):
            continue
        line, in_block = _strip_block_comments(line, in_block)
        if line.strip() == "":
            continue
        if "//" in line:
            line = line.split("//", 1)[0]
        candidate = _strip_strings(line)
        if PLACEHOLDER_RE.search(candidate):
            _diag(
                diags,
                "ADD_PLACEHOLDER_IN_SDSL",
                "Placeholder not allowed in SDSL statements",
                "no placeholders",
                stripped,
                json_pointer("statements", str(idx)),
            )


def check_file(path: Path) -> list[Diagnostic]:
    diags: list[Diagnostic] = []
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()

    profile, id_prefix, stage = _file_meta(lines, diags)

    if stage is not None:
        _diag(
            diags,
            "ADD_STAGE_IN_CONTRACT_PROFILE",
            "@File.stage not allowed in contract profile",
            "omit stage",
            str(stage),
            json_pointer("file_header", "stage"),
        )

    if profile is None:
        _diag(
            diags,
            "E_PROFILE_INVALID",
            "profile must be contract",
            "contract",
            "missing",
            json_pointer("file_header", "profile"),
        )
    elif profile != "contract":
        _diag(
            diags,
            "E_PROFILE_INVALID",
            "profile must be contract",
            "contract",
            profile,
            json_pointer("file_header", "profile"),
        )

    if not id_prefix or not RELID_RE.match(id_prefix):
        _diag(
            diags,
            "E_ID_FORMAT_INVALID",
            "id_prefix must be UPPER_SNAKE_CASE",
            "UPPER_SNAKE_CASE",
            id_prefix or "missing",
            json_pointer("file_header", "id_prefix"),
        )

    for idx, line in enumerate(lines):
        match = KIND_RE.match(line)
        if not match:
            continue
        kind = match.group("kind")
        if kind == "EdgeIntent":
            _diag(
                diags,
                "ADD_EDGEINTENT_PROFILE",
                "@EdgeIntent forbidden outside topology",
                "no @EdgeIntent",
                "@EdgeIntent",
                json_pointer("annotations", str(idx)),
            )
        if kind not in CONTRACT_KINDS:
            _diag(
                diags,
                "E_PROFILE_KIND_FORBIDDEN",
                "Kind not allowed for contract profile",
                ",".join(sorted(CONTRACT_KINDS)),
                kind,
                json_pointer("annotations", str(idx)),
            )

    _check_placeholders(lines, diags)
    return diags


def iter_sdsl_files(path: Path, project_root: Path) -> list[Path]:
    if path.is_file():
        if path.is_symlink() or has_symlink_parent(path, project_root):
            return []
        return [path]
    return sorted(
        p
        for p in path.rglob("*.sdsl2")
        if p.is_file() and not p.is_symlink() and not has_symlink_parent(p, project_root)
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", action="append", required=True, help="File or directory path.")
    ap.add_argument("--project-root", default=str(REPO_ROOT), help="Project root for path resolution.")
    args = ap.parse_args()

    project_root = Path(args.project_root).resolve()

    files: list[Path] = []
    for raw in args.input:
        raw_path = Path(raw)
        if not raw_path.is_absolute():
            raw_path = project_root / raw_path
        if raw_path.is_symlink() or has_symlink_parent(raw_path, project_root):
            print("E_CONTRACT_LINT_INPUT_SYMLINK", file=sys.stderr)
            return 2
        input_path = resolve_path(project_root, raw)
        try:
            ensure_inside(project_root, input_path, "E_CONTRACT_LINT_INPUT_OUTSIDE_PROJECT")
        except ValueError:
            print("E_CONTRACT_LINT_INPUT_OUTSIDE_PROJECT", file=sys.stderr)
            return 2
        files.extend(iter_sdsl_files(input_path, project_root))

    if not files:
        print("E_INPUT_NOT_FOUND: no .sdsl2 files", file=sys.stderr)
        return 2

    for path in files:
        if path.is_symlink():
            print("E_CONTRACT_LINT_INPUT_SYMLINK", file=sys.stderr)
            return 2
        try:
            ensure_inside(project_root, path, "E_CONTRACT_LINT_INPUT_OUTSIDE_PROJECT")
        except ValueError:
            print("E_CONTRACT_LINT_INPUT_OUTSIDE_PROJECT", file=sys.stderr)
            return 2

    all_diags: list[Diagnostic] = []
    for path in files:
        all_diags.extend(check_file(path))

    if all_diags:
        _print_diags(all_diags)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
