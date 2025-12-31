#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Gate C: SDSL v2 finalizer (Contract/Topology profile).

- Input: B3-post .sdsl2 file(s)
- Output: normalized .sdsl2 with deterministic spacing and diagnostics
- No inference, no ledger access
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

ANNOTATION_RE = re.compile(r"^\s*@(?P<kind>[A-Za-z_][A-Za-z0-9_]*)\b")

ENUM_HEAD_RE = re.compile(r"^\s*enum\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b")
STRUCT_HEAD_RE = re.compile(r"^\s*struct\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b")
INTERFACE_HEAD_RE = re.compile(r"^\s*interface\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b")
CLASS_HEAD_RE = re.compile(r"^\s*class\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b")
C_CLASS_HEAD_RE = re.compile(r"^\s*C\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b")
CONST_HEAD_RE = re.compile(r"^\s*const\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b")
FUNC_HEAD_RE = re.compile(r"^\s*(?:async\s+)?f\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\(")
TYPE_ALIAS_RE = re.compile(r"^\s*type\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*=\s*(?P<rhs>.+)")
TYPE_FORBIDDEN_RE = re.compile(r"\bany\b|tuple\s*\[|d<")
TYPE_LIST_RE = re.compile(r"\b(?:List|list)\s*\[([^\[\]]+)\]")
TYPE_DICT_RE = re.compile(r"\b(?:Dict|Map)\s*\[([^\[\]]+),\s*([^\[\]]+)\]")
TYPE_SET_RE = re.compile(r"\bSet\s*\[([^\[\]]+)\]")

INTERNAL_REF_RE = re.compile(
    r"^@(?P<kind>[A-Za-z_][A-Za-z0-9_]*)\s*(?:\.|::)\s*(?P<id>[A-Za-z0-9_]+)$"
)
CONTRACT_TOKEN_RE = re.compile(r"^CONTRACT\.[A-Za-z0-9_]+$")
SSOT_TOKEN_RE = re.compile(r"^SSOT\.[A-Za-z0-9_]+$")
CONTRACT_TOKEN_IN_VALUE_RE = re.compile(r"\bCONTRACT\.[A-Za-z0-9_]+\b")
SSOT_TOKEN_IN_VALUE_RE = re.compile(r"\bSSOT\.[A-Za-z0-9_]+\b")

REF_SEPARATOR_RE = re.compile(r"@([A-Za-z_][A-Za-z0-9_]*)::([A-Za-z0-9_]+)")


@dataclass(frozen=True)
class AnnotationInfo:
    kind: str
    meta: str
    line_no: int
    end_line: int
    pairs: List[Tuple[str, str]]


@dataclass(frozen=True)
class AnnotationGroup:
    start_line: int
    end_line: int
    annotated_decl: bool


def is_blank(line: str) -> bool:
    return line.strip() == ""


def is_line_comment(line: str) -> bool:
    return line.lstrip().startswith("//")


def _find_outside_strings(
    line: str, token: str, start: int = 0, stop_at_line_comment: bool = True
) -> int:
    in_string: str | None = None
    escaped = False
    i = start
    while i < len(line):
        ch = line[i]
        if in_string is not None:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == in_string:
                in_string = None
            i += 1
            continue
        if stop_at_line_comment and ch == "/" and i + 1 < len(line) and line[i + 1] == "/":
            break
        if ch in ('"', "'"):
            in_string = ch
            i += 1
            continue
        if line.startswith(token, i):
            return i
        i += 1
    return -1


def _block_comment_start_index(line: str) -> int:
    return _find_outside_strings(line, "/*", stop_at_line_comment=True)


def _block_comment_end_index(
    line: str, start: int = 0, stop_at_line_comment: bool = True
) -> int:
    return _find_outside_strings(line, "*/", start=start, stop_at_line_comment=stop_at_line_comment)


def _is_comment_only_block_line(line: str) -> bool:
    start = _block_comment_start_index(line)
    if start == -1:
        return False
    if any(not ch.isspace() for ch in line[:start]):
        return False
    end = _block_comment_end_index(line, start + 2, stop_at_line_comment=False)
    if end == -1:
        return True
    return all(ch.isspace() for ch in line[end + 2 :])


def _has_inline_block_comment(line: str) -> bool:
    start = _block_comment_start_index(line)
    end = _block_comment_end_index(line, stop_at_line_comment=False)
    if start == -1 and end == -1:
        return False
    if start != -1:
        if any(not ch.isspace() for ch in line[:start]):
            return True
        if end != -1 and any(not ch.isspace() for ch in line[end + 2 :]):
            return True
        return False
    return line.strip() != "*/"


def safe_snippet(line: str, max_len: int = 80) -> str:
    snippet = line.strip()
    if len(snippet) > max_len:
        snippet = snippet[: max_len - 3] + "..."
    return "".join(ch if ord(ch) < 128 else "?" for ch in snippet)


def atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(text, encoding="utf-8")
    os.replace(tmp_path, path)


def yaml_escape(s: str) -> str:
    if (
        s == ""
        or re.search(r"[:\-\{\}\[\],#&\*\!\|\>\<\=\?%@`\"\n\r\t]", s)
        or s.strip() != s
    ):
        s2 = s.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{s2}"'
    return s


def emit_yaml(obj: Any, indent: int = 0) -> str:
    sp = "  " * indent
    if obj is None:
        return sp + "null\n"
    if isinstance(obj, bool):
        return sp + ("true" if obj else "false") + "\n"
    if isinstance(obj, (int, float)):
        return sp + str(obj) + "\n"
    if isinstance(obj, str):
        return sp + yaml_escape(obj) + "\n"
    if isinstance(obj, list):
        if not obj:
            return sp + "[]\n"
        out = ""
        for item in obj:
            if isinstance(item, (dict, list)):
                out += sp + "-\n" + emit_yaml(item, indent + 1)
            else:
                out += sp + "- " + emit_yaml(item, 0).strip() + "\n"
        return out
    if isinstance(obj, dict):
        if not obj:
            return sp + "{}\n"
        out = ""
        for k, v in obj.items():
            if isinstance(v, (dict, list)):
                out += sp + f"{k}:\n" + emit_yaml(v, indent + 1)
            else:
                out += sp + f"{k}: " + emit_yaml(v, 0).strip() + "\n"
        return out
    return sp + yaml_escape(str(obj)) + "\n"


def _capture_metadata(lines: List[str], start_line: int, start_col: int) -> Tuple[str, int]:
    depth = 0
    in_string: str | None = None
    escaped = False
    in_block_comment = False
    out: List[str] = []
    for li in range(start_line, len(lines)):
        line = lines[li]
        j = start_col if li == start_line else 0
        while j < len(line):
            ch = line[j]
            if in_block_comment:
                if ch == "*" and j + 1 < len(line) and line[j + 1] == "/":
                    in_block_comment = False
                    j += 2
                    continue
                j += 1
                continue
            if in_string is not None:
                out.append(ch)
                if escaped:
                    escaped = False
                elif ch == "\\":
                    escaped = True
                elif ch == in_string:
                    in_string = None
                j += 1
                continue
            if ch == "/" and j + 1 < len(line) and line[j + 1] == "/":
                break
            if ch == "/" and j + 1 < len(line) and line[j + 1] == "*":
                in_block_comment = True
                j += 2
                continue
            if ch in ('"', "'"):
                in_string = ch
                out.append(ch)
                j += 1
                continue
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
            out.append(ch)
            j += 1
            if depth == 0:
                return "".join(out), li
        if depth > 0:
            out.append("\n")
    return "", start_line


def _capture_decl_block(lines: List[str], start_line: int) -> Tuple[List[str], int]:
    depth = 0
    in_string: str | None = None
    escaped = False
    in_block_comment = False
    out_lines: List[str] = []
    started = False
    last_line = start_line
    for li in range(start_line, len(lines)):
        line = lines[li]
        if (
            not started
            and li > start_line
            and not in_block_comment
            and not is_blank(line)
            and not is_line_comment(line)
            and not _is_comment_only_block_line(line)
            and (ANNOTATION_RE.match(line) or _scan_decl_head(line))
        ):
            break
        out_lines.append(line.rstrip())
        last_line = li
        j = 0
        while j < len(line):
            ch = line[j]
            if in_block_comment:
                if ch == "*" and j + 1 < len(line) and line[j + 1] == "/":
                    in_block_comment = False
                    j += 2
                    continue
                j += 1
                continue
            if in_string is not None:
                if escaped:
                    escaped = False
                elif ch == "\\":
                    escaped = True
                elif ch == in_string:
                    in_string = None
                j += 1
                continue
            if ch == "/" and j + 1 < len(line) and line[j + 1] == "/":
                break
            if ch == "/" and j + 1 < len(line) and line[j + 1] == "*":
                in_block_comment = True
                j += 2
                continue
            if ch in ('"', "'"):
                in_string = ch
                j += 1
                continue
            if ch == "{":
                depth += 1
                started = True
            elif ch == "}":
                depth -= 1
            j += 1
            if started and depth == 0:
                return out_lines, li
    if not started:
        return [lines[start_line].rstrip()], start_line
    return out_lines, last_line


def _parse_metadata_pairs(meta: str) -> List[Tuple[str, str]]:
    meta = meta.strip()
    if not (meta.startswith("{") and meta.endswith("}")):
        return []
    inner = meta[1:-1]
    pairs: List[Tuple[str, str]] = []
    i = 0
    in_string: str | None = None
    escaped = False
    depth_brace = 0
    depth_bracket = 0
    depth_paren = 0
    while i < len(inner):
        while i < len(inner) and inner[i] in " \t\r\n,":
            i += 1
        if i >= len(inner):
            break
        key_start = i
        while i < len(inner) and (inner[i].isalnum() or inner[i] == "_"):
            i += 1
        key = inner[key_start:i]
        if not key:
            break
        while i < len(inner) and inner[i].isspace():
            i += 1
        if i >= len(inner) or inner[i] != ":":
            break
        i += 1
        val_start = i
        in_string = None
        escaped = False
        depth_brace = 0
        depth_bracket = 0
        depth_paren = 0
        while i < len(inner):
            ch = inner[i]
            if in_string is not None:
                if escaped:
                    escaped = False
                elif ch == "\\":
                    escaped = True
                elif ch == in_string:
                    in_string = None
                i += 1
                continue
            if ch in ('"', "'"):
                in_string = ch
                i += 1
                continue
            if ch == "{":
                depth_brace += 1
            elif ch == "}":
                if depth_brace > 0:
                    depth_brace -= 1
            elif ch == "[":
                depth_bracket += 1
            elif ch == "]":
                if depth_bracket > 0:
                    depth_bracket -= 1
            elif ch == "(":
                depth_paren += 1
            elif ch == ")":
                if depth_paren > 0:
                    depth_paren -= 1
            if depth_brace == 0 and depth_bracket == 0 and depth_paren == 0 and ch == ",":
                break
            i += 1
        value = inner[val_start:i].strip()
        pairs.append((key, value))
        if i < len(inner) and inner[i] == ",":
            i += 1
    return pairs


def _scan_decl_head(line: str) -> bool:
    return any(
        regex.match(line)
        for regex in (
            ENUM_HEAD_RE,
            STRUCT_HEAD_RE,
            INTERFACE_HEAD_RE,
            CLASS_HEAD_RE,
            C_CLASS_HEAD_RE,
            CONST_HEAD_RE,
            FUNC_HEAD_RE,
            TYPE_ALIAS_RE,
        )
    )


def _extract_profile(pairs: List[Tuple[str, str]]) -> Optional[str]:
    for key, value in pairs:
        if key != "profile":
            continue
        v = value.strip()
        if v.startswith('"') and v.endswith('"') and len(v) >= 2:
            v = v[1:-1]
        return v
    return None


def _split_list_items(value: str) -> List[str]:
    value = value.strip()
    if not (value.startswith("[") and value.endswith("]")):
        return []
    inner = value[1:-1]
    items: List[str] = []
    i = 0
    in_string: str | None = None
    escaped = False
    start = 0
    while i < len(inner):
        ch = inner[i]
        if in_string is not None:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == in_string:
                in_string = None
            i += 1
            continue
        if ch in ('"', "'"):
            in_string = ch
            i += 1
            continue
        if ch == ",":
            items.append(inner[start:i].strip())
            i += 1
            start = i
            continue
        i += 1
    tail = inner[start:].strip()
    if tail:
        items.append(tail)
    return items


def _normalize_internal_ref(value: str) -> Tuple[Optional[str], bool]:
    value = value.strip()
    m = INTERNAL_REF_RE.match(value)
    if not m:
        return None, False
    sep = "::" if "::" in value else "."
    return f"@{m.group('kind')}.{m.group('id')}", sep == "::"


def _normalize_type_expr(expr: str) -> str:
    prev = None
    out = expr
    while out != prev:
        prev = out
        out = TYPE_LIST_RE.sub(r"\1[]", out)
        out = TYPE_DICT_RE.sub(r"d[\1,\2]", out)
        out = TYPE_SET_RE.sub(r"set[\1]", out)
    return out


def _detect_annotation_groups(lines: List[str]) -> List[AnnotationGroup]:
    groups: List[AnnotationGroup] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        m = ANNOTATION_RE.match(line)
        if not m:
            i += 1
            continue
        start = i
        end = i
        brace_idx = line.find("{")
        if brace_idx != -1:
            _, end_at = _capture_metadata(lines, i, brace_idx)
            end = end_at
            i = end_at + 1
        else:
            i += 1
        while i < len(lines):
            line = lines[i]
            if is_blank(line) or is_line_comment(line):
                break
            if ANNOTATION_RE.match(line):
                brace_idx = line.find("{")
                if brace_idx != -1:
                    _, end_at = _capture_metadata(lines, i, brace_idx)
                    end = end_at
                    i = end_at + 1
                else:
                    end = i
                    i += 1
                continue
            break
        annotated_decl = False
        next_line = end + 1
        if next_line < len(lines):
            if not is_blank(lines[next_line]) and not is_line_comment(lines[next_line]):
                if _scan_decl_head(lines[next_line]):
                    annotated_decl = True
        groups.append(AnnotationGroup(start_line=start, end_line=end, annotated_decl=annotated_decl))
    return groups


def _build_statements(lines: List[str], add_diag: Callable[..., None]) -> List[List[str]]:
    statements: List[List[str]] = []
    pending_comments: List[str] = []
    in_block_comment = False
    i = 0
    while i < len(lines):
        line = lines[i]
        if in_block_comment:
            pending_comments.append(line.rstrip())
            if _block_comment_end_index(line, stop_at_line_comment=False) != -1:
                in_block_comment = False
            i += 1
            continue
        if is_blank(line):
            if pending_comments:
                statements.append(pending_comments)
                pending_comments = []
            i += 1
            continue
        if _is_comment_only_block_line(line):
            pending_comments.append(line.rstrip())
            if _block_comment_end_index(line) == -1:
                in_block_comment = True
            i += 1
            continue
        if is_line_comment(line):
            pending_comments.append(line.rstrip())
            i += 1
            continue

        stmt_prefix: List[str] = []
        if pending_comments:
            stmt_prefix.extend(pending_comments)
            pending_comments = []

        if ANNOTATION_RE.match(line):
            blocks: List[Tuple[str, List[str], int]] = []
            j = i
            while j < len(lines):
                if not ANNOTATION_RE.match(lines[j]):
                    break
                start_line = j
                kind = ANNOTATION_RE.match(lines[j]).group("kind")
                block_lines = [lines[j].rstrip()]
                brace_idx = lines[j].find("{")
                if brace_idx != -1:
                    _, end_at = _capture_metadata(lines, j, brace_idx)
                    for k in range(j + 1, end_at + 1):
                        block_lines.append(lines[k].rstrip())
                    j = end_at + 1
                else:
                    j += 1
                blocks.append((kind, block_lines, start_line))
                if j >= len(lines) or is_blank(lines[j]) or is_line_comment(lines[j]):
                    break
                if not ANNOTATION_RE.match(lines[j]):
                    break

            decl_lines = None
            if j < len(lines) and not is_blank(lines[j]) and not is_line_comment(lines[j]):
                if _scan_decl_head(lines[j]):
                    decl_lines, decl_end = _capture_decl_block(lines, j)
                    j = decl_end + 1

            dep_index = next((idx for idx, (kind, _, _) in enumerate(blocks) if kind == "Dep"), None)

            if dep_index is None:
                stmt_lines = list(stmt_prefix)
                for _, block, _ in blocks:
                    stmt_lines.extend(block)
                if decl_lines is not None:
                    stmt_lines.extend(decl_lines)
                if stmt_lines:
                    statements.append(stmt_lines)
            else:
                dep_end = dep_index
                while dep_end < len(blocks) and blocks[dep_end][0] == "Dep":
                    dep_end += 1
                before_blocks = blocks[:dep_index]
                dep_blocks = blocks[dep_index:dep_end]
                after_blocks = blocks[dep_end:]

                if before_blocks:
                    before_lines = list(stmt_prefix)
                    for _, block, _ in before_blocks:
                        before_lines.extend(block)
                    if before_lines:
                        statements.append(before_lines)
                    stmt_prefix = []

                dep_lines = list(stmt_prefix)
                for _, block, _ in dep_blocks:
                    dep_lines.extend(block)
                if dep_lines:
                    statements.append(dep_lines)

                remaining: List[str] = []
                for _, block, _ in after_blocks:
                    remaining.extend(block)
                if decl_lines is not None:
                    remaining.extend(decl_lines)
                if remaining:
                    statements.append(remaining)
                elif decl_lines is not None:
                    statements.append(list(decl_lines))

            i = j
            continue

        if _scan_decl_head(line):
            decl_lines, decl_end = _capture_decl_block(lines, i)
            statements.append(stmt_prefix + decl_lines)
            i = decl_end + 1
            continue
        statements.append(stmt_prefix + [line.rstrip()])
        i += 1

    if pending_comments:
        statements.append(pending_comments)
    return statements


def _scan_annotations(lines: List[str]) -> List[AnnotationInfo]:
    annotations: List[AnnotationInfo] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        m = ANNOTATION_RE.match(line)
        if not m:
            i += 1
            continue
        kind = m.group("kind")
        brace_idx = line.find("{")
        if brace_idx == -1:
            annotations.append(
                AnnotationInfo(kind=kind, meta="", line_no=i + 1, end_line=i + 1, pairs=[])
            )
            i += 1
            continue
        meta, end_at = _capture_metadata(lines, i, brace_idx)
        pairs = _parse_metadata_pairs(meta)
        annotations.append(
            AnnotationInfo(kind=kind, meta=meta, line_no=i + 1, end_line=end_at + 1, pairs=pairs)
        )
        i = end_at + 1
    return annotations


def _normalize_blank_lines(lines: List[str]) -> List[str]:
    out: List[str] = []
    for line in lines:
        if is_blank(line):
            if not out or is_blank(out[-1]):
                continue
            out.append("")
        else:
            out.append(line.rstrip())
    while out and is_blank(out[0]):
        out.pop(0)
    return out


def _quote_contract_to(line: str) -> str:
    return re.sub(
        r"(\bto\s*:)\s*(CONTRACT\.[A-Za-z0-9_]+)\b",
        r'\1"\2"',
        line,
        count=1,
    )


def process_file(path: Path, out_path: Path, args: argparse.Namespace) -> Tuple[List[str], List[Dict[str, Any]], bool]:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    diagnostics: List[str] = []
    details: List[Dict[str, Any]] = []
    has_req = False

    def add_diag(code: str, line_no: int, snippet: str, **extra: Any) -> None:
        nonlocal has_req
        diagnostics.append(code)
        entry = {"code": code, "line": line_no, "snippet": snippet}
        entry.update(extra)
        details.append(entry)
        if code.startswith("REQ_"):
            has_req = True

    try:
        annotations = _scan_annotations(lines)
        line_replacements: Dict[int, str] = {}

        def update_line(idx: int, new_line: str) -> None:
            line_replacements[idx] = new_line

        inline_block_violation = False
        for idx, line in enumerate(lines):
            if _has_inline_block_comment(line):
                add_diag(
                    "REQ_BLOCK_COMMENT_INLINE_UNSUPPORTED",
                    idx + 1,
                    safe_snippet(line),
                )
                inline_block_violation = True


        file_lines = [idx for idx, line in enumerate(lines) if ANNOTATION_RE.match(line) and line.lstrip().startswith("@File")]
        if not file_lines:
            add_diag("REQ_FILE_HEADER_MISSING", 1, "")
        elif len(file_lines) > 1:
            add_diag("REQ_FILE_HEADER_MULTIPLE", file_lines[1] + 1, safe_snippet(lines[file_lines[1]]))
        # first non-comment non-empty line must be @File
        first_stmt = None
        in_block_comment = False
        for idx, line in enumerate(lines):
            if in_block_comment:
                if _block_comment_end_index(line, stop_at_line_comment=False) != -1:
                    in_block_comment = False
                continue
            if _is_comment_only_block_line(line):
                if _block_comment_end_index(line, stop_at_line_comment=False) == -1:
                    in_block_comment = True
                continue
            if is_blank(line) or is_line_comment(line):
                continue
            first_stmt = idx
            break
        if first_stmt is not None:
            if not lines[first_stmt].lstrip().startswith("@File"):
                add_diag("REQ_FILE_HEADER_NOT_FIRST", first_stmt + 1, safe_snippet(lines[first_stmt]))
        else:
            add_diag("REQ_FILE_HEADER_MISSING", 1, "")

        profile = None
        for ann in annotations:
            if ann.kind != "File":
                continue
            profile = _extract_profile(ann.pairs)
            if profile is None:
                add_diag("REQ_METADATA_OBJECT_INVALID", ann.line_no, safe_snippet(lines[ann.line_no - 1]))
            break
        if profile is not None:
            if profile not in ("contract", "topology"):
                add_diag("REQ_PROFILE_INVALID", 1, profile=profile)

        if profile == "contract":
            for ann in annotations:
                for key, _ in ann.pairs:
                    if key in {"contract", "contract_refs"}:
                        add_diag(
                            "REQ_CONTRACT_FIELD_FORBIDDEN",
                            ann.line_no,
                            safe_snippet(lines[ann.line_no - 1]),
                            key=key,
                        )

        if profile == "contract":
            for ann in annotations:
                for key, value in ann.pairs:
                    v = value.strip()
                    if v.startswith('"') and v.endswith('"') and len(v) >= 2:
                        continue
                    for match in CONTRACT_TOKEN_IN_VALUE_RE.finditer(value):
                        token = match.group(0)
                        if ann.kind == "Dep" and key == "to":
                            continue
                        add_diag(
                            "REQ_TOKEN_PLACEMENT_VIOLATION",
                            ann.line_no,
                            safe_snippet(lines[ann.line_no - 1]),
                            key=key,
                            token=token,
                        )
                    for match in SSOT_TOKEN_IN_VALUE_RE.finditer(value):
                        token = match.group(0)
                        if ann.kind == "Dep" and key == "ssot":
                            continue
                        add_diag(
                            "REQ_TOKEN_PLACEMENT_VIOLATION",
                            ann.line_no,
                            safe_snippet(lines[ann.line_no - 1]),
                            key=key,
                            token=token,
                        )

        # Normalize ref separator if enabled
        if args.normalize_ref_separator:
            for idx, line in enumerate(lines):
                new_line = REF_SEPARATOR_RE.sub(r"@\1.\2", line)
                if new_line != line:
                    update_line(idx, new_line)

        # metadata complexity
        for ann in annotations:
            if ann.meta.strip() == "{}":
                continue
            if ann.pairs:
                continue
            if args.strict_metadata:
                add_diag("REQ_METADATA_OBJECT_INVALID", ann.line_no, safe_snippet(lines[ann.line_no - 1]))
            else:
                add_diag("MIG_METADATA_COMPLEX", ann.line_no, safe_snippet(lines[ann.line_no - 1]))

        # Type normalization (type alias only)
        for idx, line in enumerate(lines):
            m = TYPE_ALIAS_RE.match(line)
            if not m:
                continue
            rhs = m.group("rhs")
            if TYPE_FORBIDDEN_RE.search(rhs):
                add_diag("REQ_TYPE_FORM_INVALID", idx + 1, safe_snippet(line))
            if not args.normalize_types:
                continue
            new_rhs = _normalize_type_expr(rhs)
            if new_rhs != rhs:
                indent = re.match(r"^\s*", line).group(0)
                update_line(idx, f"{indent}type {m.group('name')} = {new_rhs}")

        # @Dep validation
        dep_keys_required = {"id", "bind", "from", "to"}
        drop_lines: set[int] = set()
        seen_deps: set[Tuple[str, str, str]] = set()
        for ann in annotations:
            if ann.kind != "Dep":
                continue
            pairs = dict(ann.pairs)
            missing = [k for k in dep_keys_required if k not in pairs]
            if missing:
                add_diag(
                    "REQ_DEP_FORM_INVALID",
                    ann.line_no,
                    safe_snippet(lines[ann.line_no - 1]),
                    missing=",".join(sorted(missing)),
                )
                continue
            bind_val = pairs.get("bind", "").strip()
            from_val = pairs.get("from", "").strip()
            to_val = pairs.get("to", "").strip()

            bind_norm, bind_has_sep = _normalize_internal_ref(bind_val)
            from_norm, from_has_sep = _normalize_internal_ref(from_val)
            if bind_norm is None or from_norm is None:
                add_diag("REQ_DEP_FORM_INVALID", ann.line_no, safe_snippet(lines[ann.line_no - 1]))
                continue
            if bind_has_sep and not args.normalize_ref_separator:
                add_diag("MIG_REF_SEPARATOR_NONCANON", ann.line_no, safe_snippet(lines[ann.line_no - 1]))
            if from_has_sep and not args.normalize_ref_separator:
                add_diag("MIG_REF_SEPARATOR_NONCANON", ann.line_no, safe_snippet(lines[ann.line_no - 1]))

            to_norm = None
            if to_val.startswith("["):
                add_diag("REQ_DEP_TO_FORM_INVALID", ann.line_no, safe_snippet(lines[ann.line_no - 1]))
            else:
                to_internal, to_has_sep = _normalize_internal_ref(to_val)
                if to_internal is not None:
                    to_norm = to_internal
                    if to_has_sep and not args.normalize_ref_separator:
                        add_diag("MIG_REF_SEPARATOR_NONCANON", ann.line_no, safe_snippet(lines[ann.line_no - 1]))
                else:
                    if to_val.startswith('"') and to_val.endswith('"') and len(to_val) >= 2:
                        token = to_val[1:-1]
                        if CONTRACT_TOKEN_RE.match(token):
                            to_norm = f'"{token}"'
                        elif SSOT_TOKEN_RE.match(token):
                            add_diag(
                                "REQ_TOKEN_PLACEMENT_VIOLATION",
                                ann.line_no,
                                safe_snippet(lines[ann.line_no - 1]),
                                token=token,
                            )
                        else:
                            add_diag(
                                "REQ_DEP_TO_FORM_INVALID",
                                ann.line_no,
                                safe_snippet(lines[ann.line_no - 1]),
                            )
                    elif CONTRACT_TOKEN_RE.match(to_val):
                        # Safe auto-quote only if single-line annotation.
                        if ann.end_line == ann.line_no:
                            update_line(
                                ann.line_no - 1,
                                _quote_contract_to(
                                    line_replacements.get(ann.line_no - 1, lines[ann.line_no - 1])
                                ),
                            )
                            to_norm = f'"{to_val}"'
                        else:
                            add_diag(
                                "REQ_DEP_TO_FORM_INVALID",
                                ann.line_no,
                                safe_snippet(lines[ann.line_no - 1]),
                                token=to_val,
                            )
                    else:
                        add_diag(
                            "REQ_DEP_TO_FORM_INVALID",
                            ann.line_no,
                            safe_snippet(lines[ann.line_no - 1]),
                        )

            ssot_val = pairs.get("ssot")
            if ssot_val is not None:
                items = _split_list_items(ssot_val)
                if not items:
                    add_diag(
                        "REQ_TOKEN_PLACEMENT_VIOLATION",
                        ann.line_no,
                        safe_snippet(lines[ann.line_no - 1]),
                    )
                else:
                    for item in items:
                        if item.startswith('"') and item.endswith('"'):
                            add_diag(
                                "REQ_TOKEN_PLACEMENT_VIOLATION",
                                ann.line_no,
                                safe_snippet(lines[ann.line_no - 1]),
                                token=item,
                            )
                            continue
                        if not SSOT_TOKEN_RE.match(item):
                            add_diag(
                                "REQ_TOKEN_PLACEMENT_VIOLATION",
                                ann.line_no,
                                safe_snippet(lines[ann.line_no - 1]),
                                token=item,
                            )

            # Self-reference
            if to_norm is not None and to_norm == from_norm:
                for li in range(ann.line_no - 1, ann.end_line):
                    drop_lines.add(li)
                add_diag("MIG_DEP_SELF_REFERENCE_DROPPED", ann.line_no, safe_snippet(lines[ann.line_no - 1]))
                continue

            if to_norm is not None:
                key = (bind_norm, from_norm, to_norm)
                if key in seen_deps:
                    add_diag("REQ_DEP_DUPLICATE", ann.line_no, safe_snippet(lines[ann.line_no - 1]))
                else:
                    seen_deps.add(key)

        working_lines: List[str] = []
        for idx, line in enumerate(lines):
            if idx in drop_lines:
                continue
            working_lines.append(line_replacements.get(idx, line).rstrip())

        statements = _build_statements(working_lines, add_diag)
        out_lines: List[str] = []
        for stmt_idx, stmt in enumerate(statements):
            out_lines.extend(stmt)
            if stmt_idx < len(statements) - 1:
                out_lines.append("")
        output_text = "\n".join(out_lines).rstrip() + "\n"
        if inline_block_violation:
            output_text = "\n".join(lines) + ("\n" if text.endswith("\n") else "")

    except Exception as exc:
        add_diag("REQ_PARSE_FAILED", 1, "", error=str(exc))
        output_text = "\n".join(lines) + ("\n" if text.endswith("\n") else "")

    atomic_write(out_path, output_text)
    diag_path = out_path.with_suffix(".yaml")
    diag_doc = {
        "version": "gate-c-diagnostics-v1",
        "input_path": str(path),
        "output_path": str(out_path),
        "diagnostics": diagnostics,
        "diagnostic_details": details,
    }
    atomic_write(diag_path, emit_yaml(diag_doc))
    return diagnostics, details, has_req


def _collect_sdsl2_files(path: Path) -> List[Path]:
    if path.is_file():
        return [path]
    return sorted(p for p in path.rglob("*.sdsl2") if p.is_file())


def main() -> int:
    ap = argparse.ArgumentParser(description="Gate C: SDSL v2 finalizer")
    ap.add_argument("--input", required=True, help=".sdsl2 file or directory")
    ap.add_argument("--out", help="output file or directory (default: overwrite input)")
    ap.add_argument("--strict-metadata", action="store_true", help="enable strict metadata validation")
    ap.add_argument(
        "--normalize-ref-separator",
        action="store_true",
        help="normalize @Kind::RELID to @Kind.RELID",
    )
    ap.add_argument("--normalize-types", action="store_true", help="enable type normalization")
    ap.add_argument("--write-aggregated", help="write aggregated diagnostics YAML")
    args = ap.parse_args()

    in_path = Path(args.input)
    out_path = Path(args.out) if args.out else None

    if in_path.is_dir():
        if out_path is None:
            out_path = in_path
        if out_path.is_file():
            print("--out must be a directory when --input is a directory", file=sys.stderr)
            return 1
        files = _collect_sdsl2_files(in_path)
        if not files:
            print("No .sdsl2 files found", file=sys.stderr)
            return 1
        aggregated: Dict[str, Any] = {
            "version": "gate-c-aggregated-v1",
            "total_files": 0,
            "total_failures": 0,
            "results": [],
        }
        exit_code = 0
        for path in files:
            rel = path.relative_to(in_path)
            out_file = out_path / rel
            diags, _, has_req = process_file(path, out_file, args)
            status = "OK" if not has_req else "FAIL"
            aggregated["total_files"] += 1
            if has_req:
                aggregated["total_failures"] += 1
                exit_code = 2
            aggregated["results"].append(
                {
                    "source": path.name,
                    "status": status,
                    "diagnostics_count": len(diags),
                    "diagnostics_codes": diags,
                }
            )
        if args.write_aggregated:
            out_yaml = Path(args.write_aggregated)
            atomic_write(out_yaml, emit_yaml(aggregated))
        return exit_code

    if out_path is None:
        out_path = in_path
    elif out_path.is_dir():
        out_path = out_path / in_path.name

    diags, _, has_req = process_file(in_path, out_path, args)
    if args.write_aggregated:
        aggregated = {
            "version": "gate-c-aggregated-v1",
            "total_files": 1,
            "total_failures": 1 if has_req else 0,
            "results": [
                {
                    "source": in_path.name,
                    "status": "FAIL" if has_req else "OK",
                    "diagnostics_count": len(diags),
                    "diagnostics_codes": diags,
                }
            ],
        }
        atomic_write(Path(args.write_aggregated), emit_yaml(aggregated))
    return 2 if has_req else 0


if __name__ == "__main__":
    sys.exit(main())
