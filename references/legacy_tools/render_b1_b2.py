#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Unified Pipeline: Renderer -> Gate B1 -> Gate B2 (Aggregated Diagnostics)

Description:
  1. Renderer: Converts Ledger (YAML/JSON) to SDSL v2 surface.
  2. Gate B1: Applies canonical normalization (types, quotes, literals).
  3. Gate B2: Performs token placement and binding checks.
  4. Output:
     - Writes individual normalized .sdsl2 files.
     - Writes a SINGLE aggregated .yaml diagnostic file for the whole batch.

Usage:
  python3 pipeline.py --ledger <path_to_ledger_or_dir> --out <output_dir>
  python3 pipeline.py --b2 --ledger <path_to_sdsl2_or_dir> --out <output_dir_or_file>
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple, Set


# ==============================================================================
# SHARED UTILS
# ==============================================================================


def atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(text, encoding="utf-8")
    os.replace(tmp_path, path)


def yaml_escape(s: str) -> str:
    if (
        s == ""
        or re.search(r'[:\-\{\}\[\],#&\*\!\|\>\<\=\?%@`"\n\r\t]', s)
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


# ==============================================================================
# COMPONENT: RENDERER (Ledger -> Raw SDSL String)
# ==============================================================================


class Renderer:
    """Handles parsing YAML/JSON ledgers and rendering to initial SDSL string."""

    DECL_ANCHOR_BY_KIND = {
        "enum": "Structure",
        "struct": "Structure",
        "interface": "Interface",
        "class": "Class",
        "function": "Function",
        "const": "Const",
        "type": "Type",
    }

    @staticmethod
    def _unescape_quoted(s: str) -> str:
        return s.replace(r"\\", "\\").replace(r"\"", '"')

    @staticmethod
    def _parse_scalar(s: str) -> Any:
        s = s.strip()
        if s == "null":
            return None
        if s == "true":
            return True
        if s == "false":
            return False
        if s == "[]":
            return []
        if s == "{}":
            return {}
        if len(s) >= 2 and s[0] == '"' and s[-1] == '"':
            return Renderer._unescape_quoted(s[1:-1])
        if re.match(r"^-?\d+$", s):
            return int(s)
        if re.match(r"^-?\d+\.\d+$", s):
            return float(s)
        return s

    @staticmethod
    def _count_indent(line: str) -> int:
        return len(line) - len(line.lstrip(" "))

    @staticmethod
    def _parse_block(lines: List[str], start: int, indent: int) -> Tuple[Any, int]:
        i = start
        block_type = None
        items: List[Any] = []
        mapping: Dict[str, Any] = {}

        while i < len(lines):
            line = lines[i]
            if line.strip() == "":
                i += 1
                continue
            cur_indent = Renderer._count_indent(line)
            if cur_indent < indent:
                break
            if cur_indent > indent:
                raise ValueError(f"YAML indent error at line {i + 1}")
            content = line[cur_indent:]
            if content.startswith("-"):
                if block_type is None:
                    block_type = "list"
                if block_type != "list":
                    raise ValueError(f"YAML mixed block types at line {i + 1}")
                rest = content[1:].lstrip()
                if rest == "":
                    value, i = Renderer._parse_block(lines, i + 1, indent + 2)
                else:
                    value = Renderer._parse_scalar(rest)
                    i += 1
                items.append(value)
                continue

            if block_type is None and ":" not in content:
                return Renderer._parse_scalar(content), i + 1

            if block_type is None:
                block_type = "dict"
            if block_type != "dict":
                raise ValueError(f"YAML mixed block types at line {i + 1}")
            if ":" not in content:
                raise ValueError(f"YAML missing ':' at line {i + 1}")
            key, rest = content.split(":", 1)
            key = key.strip()
            rest = rest.lstrip()
            if rest == "":
                value, i = Renderer._parse_block(lines, i + 1, indent + 2)
            else:
                value = Renderer._parse_scalar(rest)
                i += 1
            mapping[key] = value
        return (items if block_type == "list" else mapping), i

    @staticmethod
    def load_ledger(path: Path) -> Dict[str, Any]:
        text = path.read_text(encoding="utf-8")
        if path.suffix.lower() == ".json":
            data = json.loads(text)
        else:
            lines = text.splitlines()
            data, _ = Renderer._parse_block(lines, 0, 0)
        if not isinstance(data, dict):
            raise ValueError("LEDGER_TOP_LEVEL_NOT_DICT")
        return data

    @staticmethod
    def render_decl(entry: Dict[str, Any]) -> List[str]:
        kind = entry.get("decl_kind", "")
        name = str(entry.get("decl_name", "") or "UNNAMED")
        rel_id = str(entry.get("rel_id") or entry.get("raw_rel_id") or "UNNAMED")
        anchor_kind = entry.get("anchor_kind") or Renderer.DECL_ANCHOR_BY_KIND.get(
            kind, "Structure"
        )

        if kind == "docmeta":
            return [f'@DocMeta {{ id:"{rel_id}" }}']

        anchor = f'@{anchor_kind} {{ id:"{rel_id}" }}'
        if kind == "enum":
            decl = f"enum {name} {{ }}"
        elif kind == "struct":
            decl = f"struct {name} {{ }}"
        elif kind == "interface":
            decl = f"interface {name} {{ }}"
        elif kind == "class":
            decl = f"class {name} {{ }}"
        elif kind == "function":
            decl = f"f {name}() -> d {{ ... }}"
        elif kind == "const":
            decl = f"const {name}: d = None"
        elif kind == "type":
            decl = f'type {name} = "PH_TYPE"'
        else:
            raise ValueError(f"UNSUPPORTED_DECL_KIND: {kind}")
        return [anchor, decl]

    @staticmethod
    def render(ledger: Dict[str, Any]) -> str:
        header = ledger.get("file_header") or {}
        profile = header.get("profile", "contract")
        scope = header.get("scope", "")
        domain = header.get("domain", "C")
        module = header.get("module", "")
        id_prefix = header.get("id_prefix", "")

        lines: List[str] = []
        lines.append(
            f'@File {{ profile:"{profile}", scope:"{scope}", domain:"{domain}", '
            f'module:"{module}", id_prefix:"{id_prefix}" }}'
        )
        lines.append(f'@DocMeta {{ id:"DOC_{id_prefix}" }}')
        lines.append("")

        entries = list(ledger.get("declarations", []))

        # Stable sort
        def key_fn(entry: Dict[str, Any]) -> Tuple[int, str, str]:
            loc = (entry.get("evidence") or {}).get("location_hint", "")
            m = re.match(r"line:(\d+)", str(loc))
            line_no = int(m.group(1)) if m else 999999
            return (
                line_no,
                str(entry.get("decl_kind", "")),
                str(entry.get("decl_name", "")),
            )

        entries = sorted(entries, key=key_fn)

        for entry in entries:
            stmt_lines = Renderer.render_decl(entry)
            lines.extend(stmt_lines)
            lines.append("")

        while lines and lines[-1] == "":
            lines.pop()
        return "\n".join(lines) + "\n"


# ==============================================================================
# COMPONENT: GATE B1 (Canonical Normalization)
# ==============================================================================


class GateB1:
    """Normalizes syntax (quotes, type notation, literals) strictly."""

    LIST_RE = re.compile(r"\bList\s*\[\s*([A-Za-z_][A-Za-z0-9_]*)\s*\]")
    LIST_RE_LOWER = re.compile(r"\blist\s*\[\s*([A-Za-z_][A-Za-z0-9_]*)\s*\]")
    DICT_RE = re.compile(r"\b(Dict|Map)\s*\[([^\[\]]+?)\]")
    SET_RE = re.compile(r"\bSet\s*\[")
    BARE_BRACKET_RE = re.compile(r"(?<![A-Za-z0-9_])\[\s*([A-Za-z_][A-Za-z0-9_]*)\s*\]")

    @staticmethod
    def normalize_single_quotes(line: str) -> str:
        out: List[str] = []
        i = 0
        in_double = False
        escaped = False
        while i < len(line):
            ch = line[i]
            if not in_double and ch == "/" and i + 1 < len(line) and line[i + 1] == "/":
                out.append(line[i:])
                return "".join(out)
            if in_double:
                out.append(ch)
                if escaped:
                    escaped = False
                elif ch == "\\":
                    escaped = True
                elif ch == '"':
                    in_double = False
                i += 1
                continue
            if ch == '"':
                in_double = True
                out.append(ch)
                i += 1
                continue
            if ch == "'" and not in_double:
                j = i + 1
                escaped = False
                has_backslash = False
                has_dquote = False
                while j < len(line):
                    cj = line[j]
                    if escaped:
                        has_backslash = True
                        escaped = False
                        j += 1
                        continue
                    if cj == "\\":
                        has_backslash = True
                        escaped = True
                        j += 1
                        continue
                    if cj == '"':
                        has_dquote = True
                    if cj == "'":
                        break
                    j += 1
                if j >= len(line):
                    out.append(ch)
                    i += 1
                    continue
                content = line[i + 1 : j]
                if not has_backslash and not has_dquote:
                    out.append(f'"{content}"')
                else:
                    out.append(line[i : j + 1])
                i = j + 1
                continue
            out.append(ch)
            i += 1
        return "".join(out)

    @staticmethod
    def _tokenize_ident(line: str, i: int) -> Tuple[str, int]:
        j = i
        while j < len(line) and (line[j].isalnum() or line[j] == "_"):
            j += 1
        return line[i:j], j

    @staticmethod
    def normalize_literals(line: str) -> str:
        out: List[str] = []
        i = 0
        stack: List[str] = []
        value_expected = False
        in_string: str | None = None
        escaped = False

        while i < len(line):
            ch = line[i]
            if (
                in_string is None
                and ch == "/"
                and i + 1 < len(line)
                and line[i + 1] == "/"
            ):
                out.append(line[i:])
                return "".join(out)
            if in_string is not None:
                out.append(ch)
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
                out.append(ch)
                if value_expected:
                    value_expected = False
                i += 1
                continue
            if ch == "{":
                stack.append("object")
                value_expected = False
                out.append(ch)
                i += 1
                continue
            if ch == "[":
                stack.append("array")
                value_expected = True
                out.append(ch)
                i += 1
                continue
            if ch == "(":
                stack.append("paren")
                value_expected = True
                out.append(ch)
                i += 1
                continue
            if ch == "}" or ch == "]" or ch == ")":
                if stack:
                    stack.pop()
                value_expected = False
                out.append(ch)
                i += 1
                continue
            if ch == ":" or ch == "=":
                value_expected = True
                out.append(ch)
                i += 1
                continue
            if ch == ",":
                if stack and stack[-1] in ("array", "paren"):
                    value_expected = True
                else:
                    value_expected = False
                out.append(ch)
                i += 1
                continue

            if ch.isalnum() or ch == "_":
                tok, j = GateB1._tokenize_ident(line, i)
                if value_expected:
                    if tok == "true":
                        out.append("T")
                    elif tok == "false":
                        out.append("F")
                    elif tok == "null":
                        out.append("None")
                    else:
                        out.append(tok)
                    value_expected = False
                else:
                    out.append(tok)
                i = j
                continue
            if ch.isdigit():
                j = i + 1
                while j < len(line) and (line[j].isdigit() or line[j] == "."):
                    j += 1
                out.append(line[i:j])
                if value_expected:
                    value_expected = False
                i = j
                continue
            out.append(ch)
            i += 1
        return "".join(out)

    @staticmethod
    def _split_before_equals_outside_strings(line: str) -> Tuple[str, str]:
        in_string: str | None = None
        escaped = False
        for i, ch in enumerate(line):
            if in_string is not None:
                if escaped:
                    escaped = False
                elif ch == "\\":
                    escaped = True
                elif ch == in_string:
                    in_string = None
                continue
            if ch in ('"', "'"):
                in_string = ch
                continue
            if ch == "=":
                return line[:i], line[i:]
        return line, ""

    @staticmethod
    def _normalize_type_expr(expr: str) -> str:
        expr = GateB1.SET_RE.sub("set[", expr)
        expr = GateB1.DICT_RE.sub(lambda m: f"d[{m.group(2).strip()}]", expr)
        expr = GateB1.LIST_RE.sub(lambda m: f"{m.group(1)}[]", expr)
        expr = GateB1.LIST_RE_LOWER.sub(lambda m: f"{m.group(1)}[]", expr)
        expr = GateB1.BARE_BRACKET_RE.sub(lambda m: f"{m.group(1)}[]", expr)
        return expr

    @staticmethod
    def _normalize_type_spans(prefix: str) -> str:
        out: List[str] = []
        i = 0
        in_string: str | None = None
        escaped = False
        while i < len(prefix):
            ch = prefix[i]
            if in_string is not None:
                out.append(ch)
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
                out.append(ch)
                i += 1
                continue
            if ch == "/" and i + 1 < len(prefix) and prefix[i + 1] == "/":
                out.append(prefix[i:])
                return "".join(out)
            if ch == "-" and i + 1 < len(prefix) and prefix[i + 1] == ">":
                out.append("->")
                i += 2
                ws_start = i
                while i < len(prefix) and prefix[i].isspace():
                    i += 1
                out.append(prefix[ws_start:i])
                type_start = i
                while i < len(prefix) and prefix[i] not in "={}/,":
                    if prefix[i] == "{" or prefix[i] == "}":
                        break
                    i += 1
                type_expr = prefix[type_start:i]
                out.append(GateB1._normalize_type_expr(type_expr))
                continue
            if ch == ":":
                out.append(ch)
                i += 1
                ws_start = i
                while i < len(prefix) and prefix[i].isspace():
                    i += 1
                out.append(prefix[ws_start:i])
                type_start = i
                while i < len(prefix) and prefix[i] not in ",)={}/":
                    if prefix[i] == "{" or prefix[i] == "}":
                        break
                    i += 1
                type_expr = prefix[type_start:i]
                out.append(GateB1._normalize_type_expr(type_expr))
                continue
            out.append(ch)
            i += 1
        return "".join(out)

    @staticmethod
    def normalize_types(line: str) -> str:
        stripped = line.lstrip()
        if stripped.startswith("@") or stripped.startswith("//"):
            return line
        prefix, rest = GateB1._split_before_equals_outside_strings(line)
        if stripped.startswith("type "):
            if rest:
                return prefix + "=" + GateB1._normalize_type_expr(rest[1:])
            return line
        prefix = GateB1._normalize_type_spans(prefix)
        return prefix + rest

    @staticmethod
    def process(text: str) -> str:
        lines = text.splitlines()
        normalized = []
        for line in lines:
            line = GateB1.normalize_single_quotes(line)
            line = GateB1.normalize_literals(line)
            line = GateB1.normalize_types(line)
            normalized.append(line)
        out = "\n".join(normalized)
        if text.endswith("\n"):
            out += "\n"
        return out


# ==============================================================================
# COMPONENT: GATE B2 (Binding & Token Checks)
# ==============================================================================


@dataclass(frozen=True)
class Annotation:
    kind: str
    meta: str
    line_no: int
    pairs: List[Tuple[str, str]]


@dataclass(frozen=True)
class Statement:
    annotations: List[Annotation]
    decl_line: Optional[int]
    annotated_decl: bool


class GateB2:
    """Performs token placement and binding checks on SDSL v2 text."""

    TOKEN_PREFIX_RE = re.compile(r"\b(CONTRACT|SSOT|SYSTEM)\.[A-Za-z0-9_]+")
    ANNOTATION_RE = re.compile(r"^\s*@(?P<kind>[A-Za-z_][A-Za-z0-9_]*)\b")
    FILE_RE = re.compile(r"^\s*@File\b")

    HEAD_PATTERNS = [
        re.compile(r"^\s*enum\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b"),
        re.compile(r"^\s*struct\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b"),
        re.compile(r"^\s*interface\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b"),
        re.compile(r"^\s*class\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b"),
        re.compile(r"^\s*C\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b"),
        re.compile(r"^\s*const\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b"),
        re.compile(r"^\s*(?:async\s+)?f\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\("),
        re.compile(r"^\s*type\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b"),
    ]

    ANCHOR_KINDS = {"DocMeta", "Structure", "Interface", "Class", "Function", "Const", "Type"}
    REFERENCE_KEYS = {"refs", "contract", "contract_refs", "ssot", "from", "to"}

    @staticmethod
    def _scan_decl_head(line: str) -> Optional[Tuple[str, str]]:
        for p in GateB2.HEAD_PATTERNS:
            if m := p.match(line):
                return "decl", m.group("name")
        return None

    @staticmethod
    def _capture_metadata(
        lines: List[str], start_line: int, start_col: int
    ) -> Tuple[str, int]:
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

    @staticmethod
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
                if (
                    depth_brace == 0
                    and depth_bracket == 0
                    and depth_paren == 0
                    and ch == ","
                ):
                    break
                i += 1
            value = inner[val_start:i].strip()
            pairs.append((key, value))
            if i < len(inner) and inner[i] == ",":
                i += 1
        return pairs

    @staticmethod
    def _extract_tokens(value: str) -> List[Tuple[str, bool]]:
        tokens: List[Tuple[str, bool]] = []
        buf: List[str] = []
        in_string: str | None = None
        escaped = False
        string_buf: List[str] = []
        i = 0
        while i < len(value):
            ch = value[i]
            if in_string is not None:
                if escaped:
                    string_buf.append(ch)
                    escaped = False
                elif ch == "\\":
                    string_buf.append(ch)
                    escaped = True
                elif ch == in_string:
                    content = "".join(string_buf)
                    for m in GateB2.TOKEN_PREFIX_RE.finditer(content):
                        tokens.append((m.group(0), True))
                    string_buf = []
                    in_string = None
                else:
                    string_buf.append(ch)
                i += 1
                continue
            if ch == "/" and i + 1 < len(value) and value[i + 1] == "/":
                break
            if ch in ('"', "'"):
                segment = "".join(buf)
                for m in GateB2.TOKEN_PREFIX_RE.finditer(segment):
                    tokens.append((m.group(0), False))
                buf = []
                in_string = ch
                i += 1
                continue
            buf.append(ch)
            i += 1
        if buf:
            segment = "".join(buf)
            for m in GateB2.TOKEN_PREFIX_RE.finditer(segment):
                tokens.append((m.group(0), False))
        return tokens

    @staticmethod
    def _extract_internal_refs(value: str) -> List[Tuple[str, str]]:
        refs: List[Tuple[str, str]] = []
        buf: List[str] = []
        in_string: str | None = None
        escaped = False
        i = 0
        while i < len(value):
            ch = value[i]
            if in_string is not None:
                if escaped:
                    escaped = False
                elif ch == "\\":
                    escaped = True
                elif ch == in_string:
                    in_string = None
                i += 1
                continue
            if ch == "/" and i + 1 < len(value) and value[i + 1] == "/":
                break
            if ch in ('"', "'"):
                in_string = ch
                i += 1
                continue
            buf.append(ch)
            i += 1
        text = "".join(buf)
        for m in re.finditer(
            r"@([A-Za-z_][A-Za-z0-9_]*)\s*(?:\.|::)\s*([A-Za-z0-9_]+|\"[^\"]+\")", text
        ):
            kind = m.group(1)
            ident = m.group(2)
            if ident.startswith('"') and ident.endswith('"'):
                ident = ident[1:-1]
            refs.append((kind, ident))
        return refs

    @staticmethod
    def _extract_id_value(value: str) -> Optional[str]:
        value = value.strip()
        if value.startswith('"') and value.endswith('"') and len(value) >= 2:
            return value[1:-1]
        m = re.match(r"^([A-Za-z0-9_]+)", value)
        return m.group(1) if m else None

    @staticmethod
    def _detect_profile(lines: List[str]) -> str:
        for i, line in enumerate(lines):
            if line.strip() == "" or line.lstrip().startswith("//"):
                continue
            m = GateB2.FILE_RE.match(line)
            if not m:
                break
            brace_idx = line.find("{", m.end())
            if brace_idx == -1:
                break
            meta, _ = GateB2._capture_metadata(lines, i, brace_idx)
            pairs = GateB2._parse_metadata_pairs(meta)
            for key, value in pairs:
                if key != "profile":
                    continue
                raw = value.strip()
                if raw.startswith('"') and raw.endswith('"'):
                    raw = raw[1:-1]
                return raw.lower()
            break
        return "contract"

    @staticmethod
    def parse_statements(
        lines: List[str],
    ) -> Tuple[List[Statement], Dict[Tuple[str, str], int]]:
        statements: List[Statement] = []
        targets: Dict[Tuple[str, str], int] = {}
        i = 0
        while i < len(lines):
            line = lines[i]
            if line.strip() == "" or line.lstrip().startswith("//"):
                i += 1
                continue
            m = GateB2.ANNOTATION_RE.match(line)
            if not m:
                i += 1
                continue
            annotations: List[Annotation] = []
            while i < len(lines):
                line = lines[i]
                m = GateB2.ANNOTATION_RE.match(line)
                if not m:
                    break
                kind = m.group("kind")
                brace_idx = line.find("{", m.end())
                if brace_idx == -1:
                    meta = ""
                    end_line = i
                else:
                    meta, end_line = GateB2._capture_metadata(lines, i, brace_idx)
                pairs = GateB2._parse_metadata_pairs(meta)
                ann = Annotation(kind=kind, meta=meta, line_no=i + 1, pairs=pairs)
                annotations.append(ann)
                i = end_line + 1
            decl_line = None
            annotated_decl = False
            if (
                i < len(lines)
                and lines[i].strip()
                and not lines[i].lstrip().startswith("//")
            ):
                if GateB2._scan_decl_head(lines[i]):
                    annotated_decl = True
                    decl_line = i + 1
            statements.append(
                Statement(
                    annotations=annotations,
                    decl_line=decl_line,
                    annotated_decl=annotated_decl,
                )
            )
            for ann in annotations:
                if ann.kind not in GateB2.ANCHOR_KINDS:
                    continue
                for key, value in ann.pairs:
                    if key != "id":
                        continue
                    ident = GateB2._extract_id_value(value)
                    if ident:
                        targets[(ann.kind, ident)] = ann.line_no
        return statements, targets

    @staticmethod
    def check(text: str) -> Tuple[List[str], List[Dict[str, Any]]]:
        lines = text.splitlines()
        profile = GateB2._detect_profile(lines)
        statements, targets = GateB2.parse_statements(lines)
        diagnostics: List[str] = []
        details: List[Dict[str, Any]] = []

        def add_diag(code: str, line_no: int, snippet: str, **kwargs: Any) -> None:
            diagnostics.append(code)
            item = {"code": code, "line": line_no, "snippet": snippet}
            item.update(kwargs)
            details.append(item)

        def safe_snippet(line: str, max_len: int = 80) -> str:
            snippet = line.strip()
            if len(snippet) > max_len:
                snippet = snippet[: max_len - 3] + "..."
            return "".join(ch if ord(ch) < 128 else "?" for ch in snippet)

        for stmt in statements:
            has_bind = False
            binding_refs: List[str] = []
            bind_values: List[str] = []
            for ann in stmt.annotations:
                for key, value in ann.pairs:
                    if key == "bind":
                        has_bind = True
                        bind_values.append(value)
                    if key in GateB2.REFERENCE_KEYS:
                        binding_refs.extend(
                            [
                                f"{k}.{v}"
                                for k, v in GateB2._extract_internal_refs(value)
                            ]
                        )

                    tokens = GateB2._extract_tokens(value)
                    for tok, in_string in tokens:
                        if profile == "contract" and key == "contract_refs":
                            add_diag(
                                "REQ_CONTRACT_REFS_FORBIDDEN",
                                ann.line_no,
                                safe_snippet(lines[ann.line_no - 1]),
                                annotation_kind=ann.kind,
                                key=key,
                                token=tok,
                                in_string=in_string,
                            )
                            continue
                        prefix = tok.split(".", 1)[0]
                        allowed: Set[str] = set()
                        if prefix == "CONTRACT":
                            allowed = {"contract"} if profile == "contract" else {"contract_refs"}
                            if ann.kind == "Dep":
                                allowed.add("to")
                        elif prefix == "SSOT":
                            allowed = {"ssot"}
                        if (
                            prefix in ("CONTRACT", "SSOT", "SYSTEM")
                            and key not in allowed
                        ):
                            add_diag(
                                "REQ_TOKEN_PLACEMENT_VIOLATION",
                                ann.line_no,
                                safe_snippet(lines[ann.line_no - 1]),
                                annotation_kind=ann.kind,
                                key=key,
                                token=tok,
                                in_string=in_string,
                            )

            if stmt.annotated_decl:
                continue
            if all(ann.kind == "DocMeta" for ann in stmt.annotations):
                continue
            if not binding_refs:
                continue
            if not has_bind:
                code = (
                    "REQ_DETACHED_BIND_AMBIGUOUS"
                    if len(set(binding_refs)) > 1
                    else "REQ_DETACHED_BIND_MISSING"
                )
                add_diag(
                    code,
                    stmt.annotations[0].line_no,
                    safe_snippet(lines[stmt.annotations[0].line_no - 1]),
                    refs=sorted(set(binding_refs)),
                )
                continue
            for value in bind_values:
                if value.strip().startswith("["):
                    add_diag(
                        "REQ_MULTI_TARGET_RULE_UNSUPPORTED",
                        stmt.annotations[0].line_no,
                        safe_snippet(lines[stmt.annotations[0].line_no - 1]),
                        bind=value.strip(),
                    )
                    continue
                for kind, ident in GateB2._extract_internal_refs(value):
                    if (kind, ident) not in targets:
                        add_diag(
                            "REQ_DETACHED_BIND_TARGET_NOT_FOUND",
                            stmt.annotations[0].line_no,
                            safe_snippet(lines[stmt.annotations[0].line_no - 1]),
                            bind=f"@{kind}.{ident}",
                        )

        return diagnostics, details


# ==============================================================================
# MAIN ORCHESTRATOR
# ==============================================================================


def _infer_output_stem(input_path: str) -> str:
    stem = Path(input_path).stem
    upper = stem.upper()
    if upper.endswith("_SDSLV2_CONTRACT"):
        return stem
    if upper.endswith("_SDSL_CONTRACT"):
        return stem[: -len("_SDSL_CONTRACT")] + "_SDSLv2_CONTRACT"
    if upper.endswith("_CONTRACT"):
        return stem[: -len("_CONTRACT")] + "_SDSLv2_CONTRACT"
    return stem + "_SDSLv2_CONTRACT"


def _is_ledger_filename(name: str) -> bool:
    upper = name.upper()
    if not upper.endswith((".YAML", ".YML", ".JSON")):
        return False
    if "CONTRACT" not in upper:
        return False
    if upper.startswith("SHARED_INFRA"):
        return True
    return re.match(r"^P[0-9]+_", upper) is not None


def iter_ledger_files(path: Path) -> Iterable[Path]:
    if path.is_file():
        return [path]
    return sorted(
        [p for p in path.iterdir() if p.is_file() and _is_ledger_filename(p.name)],
        key=lambda p: p.name,
    )


def iter_sdsl_files(path: Path) -> Iterable[Path]:
    if path.is_file():
        return [path]
    return sorted(
        [p for p in path.iterdir() if p.is_file() and p.suffix.lower() == ".sdsl2"],
        key=lambda p: p.name,
    )


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Unified Renderer -> Gate B1 -> Gate B2 Pipeline (Aggregated Diagnostics)"
    )
    ap.add_argument(
        "--b2",
        action="store_true",
        help="Run Gate B2 only against .sdsl2 inputs (skip renderer and B1).",
    )
    ap.add_argument("--ledger", required=True, help="Input Ledger file or directory")
    ap.add_argument("--out", required=True, help="Output directory")
    args = ap.parse_args()

    ledger_path = Path(args.ledger)
    out_dir = Path(args.out)

    if args.b2:
        if ledger_path.is_dir() and out_dir.suffix:
            print(
                "ERROR: --out must be a directory when --ledger is a directory.",
                file=sys.stderr,
            )
            return 1
        files = list(iter_sdsl_files(ledger_path))
        if not files:
            print("NO_SDSL_FILES_FOUND", file=sys.stderr)
            return 1
    else:
        # Validation
        if ledger_path.is_dir() and out_dir.suffix:
            print(
                "ERROR: --out must be a directory when --ledger is a directory.",
                file=sys.stderr,
            )
            return 1

        files = list(iter_ledger_files(ledger_path))
        if not files:
            print("NO_LEDGER_FILES_FOUND", file=sys.stderr)
            return 1

    failures = 0
    all_results = []

    print(f"Processing {len(files)} files...")

    for path in files:
        result_entry = {"source": path.name, "status": "OK", "diagnostics_count": 0}

        try:
            if args.b2:
                # Gate B2 only: input is already .sdsl2
                text = path.read_text(encoding="utf-8")
                diags, details = GateB2.check(text)
            else:
                # 1. Render
                ledger_data = Renderer.load_ledger(path)
                rendered_text = Renderer.render(ledger_data)

                # 2. Gate B1: Normalize
                normalized_text = GateB1.process(rendered_text)

                # Determine Output Paths
                out_stem = _infer_output_stem(str(path))
                if out_dir.suffix and not out_dir.is_dir():
                    out_sdsl = out_dir
                else:
                    out_sdsl = out_dir / f"{out_stem}.sdsl2"

                # 3. Write Normalized SDSL
                atomic_write(out_sdsl, normalized_text)
                result_entry["output"] = out_sdsl.name

                # 4. Gate B2: Check & Collect Diagnostics (Do not write individual yaml)
                diags, details = GateB2.check(normalized_text)

            req_diags = [code for code in diags if code.startswith("REQ_")]
            if diags:
                result_entry["diagnostics_count"] = len(diags)
                result_entry["req_count"] = len(req_diags)
                result_entry["diagnostics_codes"] = diags
                result_entry["details"] = details
            if req_diags:
                result_entry["status"] = "ERROR"
                failures += 1

            if args.b2:
                print(f"[OK] {path.name} (Errors: {len(req_diags)})")
            else:
                print(f"[OK] {path.name} -> {out_sdsl.name} (Errors: {len(req_diags)})")

        except Exception as exc:
            failures += 1
            result_entry["status"] = "CRASH"
            result_entry["error_message"] = str(exc)
            print(f"[ERROR] {path.name}: {exc}", file=sys.stderr)

        all_results.append(result_entry)

    # 5. Write Aggregated Diagnostics
    aggregated_report = {
        "version": "gate-b2-only-aggregated-v1" if args.b2 else "gate-b2-aggregated-v1",
        "total_files": len(files),
        "total_failures": failures,
        "results": all_results,
    }

    if out_dir.suffix and not out_dir.is_dir():
        out_yaml = out_dir.with_suffix(".yaml")
    else:
        out_yaml = out_dir / "all_diagnostics.yaml"

    atomic_write(out_yaml, emit_yaml(aggregated_report))
    print(f"\nAggregated diagnostics written to: {out_yaml}")

    return 2 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
