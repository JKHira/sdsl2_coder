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
from sdslv2_builder.lint import _capture_metadata, _parse_metadata_pairs


KIND_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")
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
TOPOLOGY_KINDS = {
    "File",
    "DocMeta",
    "Node",
    "Edge",
    "Rule",
}


def iter_sdsl_files(path: Path) -> list[Path]:
    if path.is_file():
        return [path]
    return sorted(p for p in path.rglob("*.sdsl2") if p.is_file())


def _diag(diags: list[Diagnostic], code: str, message: str, expected: str, got: str, path: str) -> None:
    diags.append(Diagnostic(code=code, message=message, expected=expected, got=got, path=path))


def _strip_quotes(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] == '"':
        return value[1:-1]
    return value


def _first_stmt_line(lines: list[str]) -> int | None:
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if stripped == "" or stripped.startswith("//"):
            continue
        return idx
    return None


def _check_metadata(
    lines: list[str],
    line_index: int,
    line: str,
    diags: list[Diagnostic],
) -> tuple[str | None, dict[str, str] | None]:
    if "/*" in line or "*/" in line:
        _diag(
            diags,
            "E_METADATA_OBJECT_INVALID",
            "Inline block comments are not allowed",
            "no /* */",
            "block comment",
            json_pointer("annotations", str(line_index)),
        )
    brace_idx = line.find("{")
    if brace_idx == -1:
        _diag(
            diags,
            "E_METADATA_OBJECT_INVALID",
            "Annotation must include metadata object",
            "{...}",
            "missing",
            json_pointer("annotations", str(line_index)),
        )
        return None, None
    meta, end_line = _capture_metadata(lines, line_index, brace_idx)
    meta = meta.strip()
    if not meta or not meta.startswith("{") or not meta.endswith("}"):
        _diag(
            diags,
            "E_METADATA_OBJECT_INVALID",
            "Metadata object is not parseable",
            "{...}",
            meta,
            json_pointer("annotations", str(line_index)),
        )
        return None, None
    pairs = _parse_metadata_pairs(meta)
    return meta, {k: v for k, v in pairs}


def check_file(path: Path) -> list[Diagnostic]:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    diags: list[Diagnostic] = []

    file_lines = [idx for idx, line in enumerate(lines) if line.lstrip().startswith("@File")]
    first_stmt = _first_stmt_line(lines)

    if not file_lines:
        _diag(diags, "E_FILE_HEADER_MISSING", "Missing @File header", "@File", "missing", json_pointer())
        return diags
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

    profile = None
    annotations: list[tuple[int, str, dict[str, str] | None]] = []

    for idx, line in enumerate(lines):
        if not line.lstrip().startswith("@"):
            continue
        kind = line.lstrip().split(None, 1)[0][1:]
        if not KIND_RE.match(kind):
            _diag(
                diags,
                "E_METADATA_OBJECT_INVALID",
                "Invalid annotation kind",
                "alnum kind",
                kind,
                json_pointer("annotations", str(idx)),
            )
            continue
        _, kv = _check_metadata(lines, idx, line, diags)
        if kv is None:
            continue
        if kind == "File":
            raw = kv.get("profile")
            if raw is None:
                _diag(
                    diags,
                    "E_PROFILE_INVALID",
                    "profile must be contract or topology",
                    "contract|topology",
                    "missing",
                    json_pointer("file_header", "profile"),
                )
            else:
                profile = _strip_quotes(raw)
        annotations.append((idx, kind, kv))

    if profile not in {"contract", "topology"}:
        if profile is not None:
            _diag(
                diags,
                "E_PROFILE_INVALID",
                "profile must be contract or topology",
                "contract|topology",
                str(profile),
                json_pointer("file_header", "profile"),
            )
        return diags

    allowed = CONTRACT_KINDS if profile == "contract" else TOPOLOGY_KINDS
    for idx, kind, _ in annotations:
        if kind not in allowed:
            _diag(
                diags,
                "E_PROFILE_KIND_FORBIDDEN",
                "Kind not allowed for profile",
                ",".join(sorted(allowed)),
                kind,
                json_pointer("annotations", str(idx)),
            )

    return diags


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", action="append", required=True, help="File or directory path.")
    args = ap.parse_args()

    files: list[Path] = []
    for raw in args.input:
        files.extend(iter_sdsl_files(Path(raw)))

    if not files:
        print("E_INPUT_NOT_FOUND: no .sdsl2 files", file=sys.stderr)
        return 2

    all_diags: list[Diagnostic] = []
    for path in files:
        all_diags.extend(check_file(path))

    if all_diags:
        payload = [d.to_dict() for d in all_diags]
        print(json.dumps(payload, ensure_ascii=False, indent=2), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
