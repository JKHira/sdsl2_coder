#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Gate B3: Generate @Dep from ledger evidence only (no inference).

Evidence sources (closed set):
- Gate A ledger evidence_refs_internal / evidence_refs_contract / evidence_refs_ssot only.

Input:
  --input <file-or-dir> (B2 output .sdsl2)
  --ledger <file-or-dir> (Gate A ledger .yaml/.yml/.json)
Output:
  --out <dir-or-file> optional; if omitted, overwrites input.
Diagnostics:
  Written as <same-stem>.yaml in the B3 output directory.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Tuple, Dict, Any, Set
ANNOTATION_RE = re.compile(r"^\s*@(?P<kind>[A-Za-z_][A-Za-z0-9_]*)\b")

ENUM_HEAD_RE = re.compile(r"^\s*enum\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b")
STRUCT_HEAD_RE = re.compile(r"^\s*struct\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b")
INTERFACE_HEAD_RE = re.compile(r"^\s*interface\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b")
CLASS_HEAD_RE = re.compile(r"^\s*class\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b")
C_CLASS_HEAD_RE = re.compile(r"^\s*C\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b")
CONST_HEAD_RE = re.compile(r"^\s*const\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b")
FUNC_HEAD_RE = re.compile(r"^\s*(?:async\s+)?f\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\(")
TYPE_ALIAS_RE = re.compile(r"^\s*type\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*=\s*(?P<rhs>.+)")

ANCHOR_KINDS = {"DocMeta", "Structure", "Interface", "Class", "Function", "Const", "Type"}
DEP_ELIGIBLE_KINDS = {"Structure", "Interface", "Class", "Function", "Const", "Type"}
CONTRACT_TOKEN_RE = re.compile(r"^CONTRACT\.[A-Za-z0-9_]+$")
SSOT_TOKEN_RE = re.compile(r"^SSOT\.[A-Za-z0-9_]+$")
INTERNAL_REF_RE = re.compile(
    r"^@(?P<kind>[A-Za-z_][A-Za-z0-9_]*)\s*(?:\.|::)\s*(?P<id>[A-Za-z0-9_]+)$"
)

DECL_KIND_TO_ANCHOR = {
    "enum": "Structure",
    "struct": "Structure",
    "interface": "Interface",
    "class": "Class",
    "function": "Function",
    "const": "Const",
    "type": "Type",
}



@dataclass(frozen=True)
class Annotation:
    kind: str
    meta: str
    line_no: int
    pairs: List[Tuple[str, str]]


@dataclass(frozen=True)
class Statement:
    annotations: List[Annotation]
    start_line: int
    end_line: int
    decl_line: Optional[int]
    annotated_decl: bool


@dataclass(frozen=True)
class DeclSite:
    anchor_kind: str
    rel_id: str
    start_line: int
    decl_line: int


@dataclass(frozen=True)
class EvidenceEntry:
    internal_refs: List[str]
    contract_refs: List[str]
    ssot_refs: List[str]


def is_blank(line: str) -> bool:
    return line.strip() == ""


def is_line_comment(line: str) -> bool:
    return line.lstrip().startswith("//")


def safe_snippet(line: str, max_len: int = 80) -> str:
    snippet = line.strip()
    if len(snippet) > max_len:
        snippet = snippet[: max_len - 3] + "..."
    return "".join(ch if ord(ch) < 128 else "?" for ch in snippet)


def _scan_decl_head(line: str) -> Optional[Tuple[str, str]]:
    if m := ENUM_HEAD_RE.match(line):
        return "enum", m.group("name")
    if m := STRUCT_HEAD_RE.match(line):
        return "struct", m.group("name")
    if m := INTERFACE_HEAD_RE.match(line):
        return "interface", m.group("name")
    if m := CLASS_HEAD_RE.match(line):
        return "class", m.group("name")
    if m := C_CLASS_HEAD_RE.match(line):
        return "class", m.group("name")
    if m := CONST_HEAD_RE.match(line):
        return "const", m.group("name")
    if m := FUNC_HEAD_RE.match(line):
        return "function", m.group("name")
    if m := TYPE_ALIAS_RE.match(line):
        return "type", m.group("name")
    return None


def iter_input_files(path: Path) -> Iterable[Path]:
    if path.is_file():
        return [path]
    files: List[Path] = []
    for p in sorted(path.iterdir()):
        if not p.is_file():
            continue
        if p.suffix.lower() != ".sdsl2":
            continue
        if "CONTRACT" not in p.name.upper():
            continue
        files.append(p)
    return files


def resolve_output_path(input_path: Path, out_arg: str | None) -> Path:
    if out_arg is None:
        return input_path
    out = Path(out_arg)
    if out.is_dir() or not out.suffix:
        out.mkdir(parents=True, exist_ok=True)
        return out / input_path.name
    return out


def atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(text, encoding="utf-8")
    os.replace(tmp_path, path)


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
        return s[1:-1].replace(r"\\", "\\").replace(r"\"", '"')
    if re.match(r"^-?\d+$", s):
        return int(s)
    if re.match(r"^-?\d+\.\d+$", s):
        return float(s)
    return s


def _count_indent(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


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
        cur_indent = _count_indent(line)
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
                value, i = _parse_block(lines, i + 1, indent + 2)
            else:
                value = _parse_scalar(rest)
                i += 1
            items.append(value)
            continue

        if block_type is None and ":" not in content:
            return _parse_scalar(content), i + 1

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
            value, i = _parse_block(lines, i + 1, indent + 2)
        else:
            value = _parse_scalar(rest)
            i += 1
        mapping[key] = value
    return (items if block_type == "list" else mapping), i


def load_ledger(path: Path) -> Dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        data = json.loads(text)
    else:
        lines = text.splitlines()
        data, _ = _parse_block(lines, 0, 0)
    if not isinstance(data, dict):
        raise ValueError("LEDGER_TOP_LEVEL_NOT_DICT")
    return data


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


def _extract_id_value(value: str) -> Optional[str]:
    value = value.strip()
    if value.startswith('"') and value.endswith('"') and len(value) >= 2:
        return value[1:-1]
    m = re.match(r"^([A-Za-z0-9_]+)", value)
    return m.group(1) if m else None


def parse_statements(lines: List[str]) -> List[Statement]:
    statements: List[Statement] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if is_blank(line) or is_line_comment(line):
            i += 1
            continue
        m = ANNOTATION_RE.match(line)
        if not m:
            i += 1
            continue
        annotations: List[Annotation] = []
        start_line = i + 1
        end_line = start_line
        while i < len(lines):
            line = lines[i]
            m = ANNOTATION_RE.match(line)
            if not m:
                break
            kind = m.group("kind")
            brace_idx = line.find("{", m.end())
            if brace_idx == -1:
                meta = ""
                end_at = i
            else:
                meta, end_at = _capture_metadata(lines, i, brace_idx)
            pairs = _parse_metadata_pairs(meta)
            ann = Annotation(kind=kind, meta=meta, line_no=i + 1, pairs=pairs)
            annotations.append(ann)
            i = end_at + 1
            end_line = i
        decl_line = None
        annotated_decl = False
        if i < len(lines) and not is_blank(lines[i]) and not is_line_comment(lines[i]):
            if _scan_decl_head(lines[i]):
                annotated_decl = True
                decl_line = i + 1
        statements.append(
            Statement(
                annotations=annotations,
                start_line=start_line,
                end_line=end_line,
                decl_line=decl_line,
                annotated_decl=annotated_decl,
            )
        )
    return statements


def detect_profile(lines: List[str]) -> str:
    file_re = re.compile(r"^\s*@File\b")
    for i, line in enumerate(lines):
        if is_blank(line) or is_line_comment(line):
            continue
        if not file_re.match(line):
            break
        brace_idx = line.find("{")
        if brace_idx == -1:
            break
        meta, _ = _capture_metadata(lines, i, brace_idx)
        pairs = _parse_metadata_pairs(meta)
        for key, value in pairs:
            if key != "profile":
                continue
            raw = value.strip()
            if raw.startswith('"') and raw.endswith('"'):
                raw = raw[1:-1]
            return raw.lower()
        break
    return "contract"


def resolve_ledger_path(input_path: Path, ledger_arg: str) -> Path:
    ledger = Path(ledger_arg)
    if ledger.is_dir() or not ledger.suffix:
        for ext in (".yaml", ".yml", ".json"):
            candidate = ledger / f"{input_path.stem}{ext}"
            if candidate.exists():
                return candidate
        raise FileNotFoundError(f"LEDGER_NOT_FOUND: {input_path.stem}")
    return ledger


def _normalize_internal_ref(value: str) -> Optional[Tuple[str, str]]:
    m = INTERNAL_REF_RE.match(value.strip())
    if not m:
        return None
    return m.group("kind"), m.group("id")


def _dep_id(from_rel_id: str, from_ref: str, to_norm: str) -> str:
    digest = hashlib.sha256(f"{from_ref}->{to_norm}".encode("utf-8")).hexdigest()[:12]
    return f"DEP_{from_rel_id}_{digest}"


def _ensure_str_list(
    value: Any,
    code: str,
    diagnostics: List[str],
    details: List[Dict[str, Any]],
    **ctx: Any,
) -> List[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        diagnostics.append(code)
        item = {"code": code}
        item.update(ctx)
        details.append(item)
        return []
    out: List[str] = []
    for item in value:
        if isinstance(item, str):
            out.append(item)
        else:
            diagnostics.append(code)
            detail = {"code": code}
            detail.update(ctx)
            detail["invalid_value"] = item
            details.append(detail)
    return out


def build_decl_sites(
    lines: List[str], statements: List[Statement]
) -> Tuple[List[DeclSite], Dict[Tuple[str, str], int], Dict[Tuple[str, str], int]]:
    sites: List[DeclSite] = []
    targets: Dict[Tuple[str, str], int] = {}
    line_map: Dict[Tuple[str, str], int] = {}
    for stmt in statements:
        if not stmt.annotated_decl or stmt.decl_line is None:
            continue
        decl_line = lines[stmt.decl_line - 1]
        decl = _scan_decl_head(decl_line)
        if not decl:
            continue
        decl_kind, _ = decl
        anchor_kind = DECL_KIND_TO_ANCHOR.get(decl_kind)
        if anchor_kind is None:
            continue
        rel_id = None
        for ann in stmt.annotations:
            if ann.kind != anchor_kind:
                continue
            for key, value in ann.pairs:
                if key == "id":
                    rel_id = _extract_id_value(value)
                    break
            if rel_id:
                break
        if not rel_id:
            continue
        site = DeclSite(
            anchor_kind=anchor_kind,
            rel_id=rel_id,
            start_line=stmt.start_line,
            decl_line=stmt.decl_line,
        )
        sites.append(site)
        targets[(anchor_kind, rel_id)] = stmt.start_line
        line_map[(anchor_kind, rel_id)] = stmt.decl_line
    return sites, targets, line_map


def build_evidence_map(
    ledger: Dict[str, Any],
    diagnostics: List[str],
    details: List[Dict[str, Any]],
) -> Dict[Tuple[str, str], EvidenceEntry]:
    evidence_map: Dict[Tuple[str, str], EvidenceEntry] = {}
    decls = ledger.get("declarations", [])
    if not isinstance(decls, list):
        diagnostics.append("REQ_DEP_EVIDENCE_INVALID")
        details.append({"code": "REQ_DEP_EVIDENCE_INVALID", "reason": "DECLARATIONS_NOT_LIST"})
        return evidence_map
    for entry in decls:
        if not isinstance(entry, dict):
            diagnostics.append("REQ_DEP_EVIDENCE_INVALID")
            details.append({"code": "REQ_DEP_EVIDENCE_INVALID", "reason": "DECL_ENTRY_NOT_DICT"})
            continue
        anchor_kind = entry.get("anchor_kind")
        rel_id = entry.get("rel_id")
        if not anchor_kind or not rel_id:
            diagnostics.append("REQ_DEP_EVIDENCE_INVALID")
            details.append(
                {
                    "code": "REQ_DEP_EVIDENCE_INVALID",
                    "reason": "MISSING_ANCHOR_OR_RELID",
                    "entry": str(entry.get("decl_name", "")),
                }
            )
            continue
        internal_refs = _ensure_str_list(
            entry.get("evidence_refs_internal"),
            "REQ_DEP_EVIDENCE_INVALID",
            diagnostics,
            details,
            anchor_kind=anchor_kind,
            rel_id=rel_id,
            field="evidence_refs_internal",
        )
        contract_refs = _ensure_str_list(
            entry.get("evidence_refs_contract"),
            "REQ_DEP_EVIDENCE_INVALID",
            diagnostics,
            details,
            anchor_kind=anchor_kind,
            rel_id=rel_id,
            field="evidence_refs_contract",
        )
        ssot_refs = _ensure_str_list(
            entry.get("evidence_refs_ssot"),
            "REQ_DEP_EVIDENCE_INVALID",
            diagnostics,
            details,
            anchor_kind=anchor_kind,
            rel_id=rel_id,
            field="evidence_refs_ssot",
        )
        key = (str(anchor_kind), str(rel_id))
        if key in evidence_map:
            diagnostics.append("REQ_DEP_EVIDENCE_INVALID")
            details.append(
                {
                    "code": "REQ_DEP_EVIDENCE_INVALID",
                    "reason": "DUPLICATE_EVIDENCE_ENTRY",
                    "anchor_kind": anchor_kind,
                    "rel_id": rel_id,
                }
            )
            continue
        evidence_map[key] = EvidenceEntry(
            internal_refs=internal_refs,
            contract_refs=contract_refs,
            ssot_refs=ssot_refs,
        )
    return evidence_map


def detect_cycles(graph: Dict[Tuple[str, str], Set[Tuple[str, str]]]) -> List[List[Tuple[str, str]]]:
    visited: Set[Tuple[str, str]] = set()
    stack: Set[Tuple[str, str]] = set()
    cycles: List[List[Tuple[str, str]]] = []

    def dfs(node: Tuple[str, str], path: List[Tuple[str, str]]) -> None:
        if node in stack:
            if node in path:
                idx = path.index(node)
                cycles.append(path[idx:] + [node])
            return
        if node in visited:
            return
        visited.add(node)
        stack.add(node)
        for nxt in graph.get(node, set()):
            dfs(nxt, path + [nxt])
        stack.remove(node)

    for node in graph:
        dfs(node, [node])
    return cycles


def build_deps_and_diagnostics(
    lines: List[str], statements: List[Statement], ledger: Dict[str, Any]
) -> Tuple[Dict[int, List[str]], List[str], List[Dict[str, Any]]]:
    diagnostics: List[str] = []
    details: List[Dict[str, Any]] = []
    insert_map: Dict[int, List[str]] = {}

    def add_diag(code: str, line_no: int, snippet: str, **kwargs: Any) -> None:
        diagnostics.append(code)
        item: Dict[str, Any] = {"code": code, "line": line_no, "snippet": snippet}
        item.update(kwargs)
        details.append(item)

    profile = detect_profile(lines)
    if profile != "contract":
        add_diag("REQ_PROFILE_UNSUPPORTED", 1, "", profile=profile)
        return insert_map, diagnostics, details

    # NOTE: B2 surface is scanned only to locate insert sites (no evidence extraction).
    sites, targets, line_map = build_decl_sites(lines, statements)
    evidence_map = build_evidence_map(ledger, diagnostics, details)
    dep_graph: Dict[Tuple[str, str], Set[Tuple[str, str]]] = {}

    for site in sites:
        from_ref = f"@{site.anchor_kind}.{site.rel_id}"
        snippet = safe_snippet(lines[site.decl_line - 1])
        evidence = evidence_map.get((site.anchor_kind, site.rel_id))
        if evidence is None:
            add_diag(
                "REQ_DEP_EVIDENCE_INVALID",
                site.decl_line,
                snippet,
                reason="LEDGER_ENTRY_MISSING",
                ref=from_ref,
            )
            continue

        internal_refs = sorted(set(evidence.internal_refs))
        contract_refs = sorted(set(evidence.contract_refs))
        ssot_refs = sorted(set(evidence.ssot_refs))

        if not internal_refs and not contract_refs:
            if ssot_refs:
                add_diag(
                    "MIG_DEP_SSOT_ONLY",
                    site.decl_line,
                    snippet,
                    ssot=ssot_refs,
                )
            elif site.anchor_kind in DEP_ELIGIBLE_KINDS:
                add_diag("MIG_DEP_EVIDENCE_MISSING", site.decl_line, snippet)
            continue

        dep_targets: List[Tuple[str, str, bool]] = []
        seen_targets: Set[str] = set()

        for ref in internal_refs:
            norm = _normalize_internal_ref(ref)
            if not norm:
                add_diag("REQ_DEP_EVIDENCE_INVALID", site.decl_line, snippet, ref=ref)
                continue
            kind, rel_id = norm
            if kind not in ANCHOR_KINDS:
                add_diag("REQ_DEP_EVIDENCE_INVALID", site.decl_line, snippet, ref=ref)
                continue
            to_norm = f"@{kind}.{rel_id}"
            if to_norm == from_ref:
                add_diag("MIG_DEP_SELF_REFERENCE", site.decl_line, snippet, ref=to_norm)
                continue
            if (kind, rel_id) not in targets:
                add_diag("REQ_DEP_UNRESOLVED_INTERNAL_REF", site.decl_line, snippet, ref=to_norm)
                continue
            if to_norm in seen_targets:
                add_diag("REQ_DEP_DUPLICATE", site.decl_line, snippet, ref=to_norm)
                continue
            seen_targets.add(to_norm)
            dep_targets.append((to_norm, to_norm, True))
            dep_graph.setdefault((site.anchor_kind, site.rel_id), set()).add((kind, rel_id))

        for token in contract_refs:
            if not CONTRACT_TOKEN_RE.match(token):
                add_diag("REQ_DEP_EVIDENCE_INVALID", site.decl_line, snippet, ref=token)
                continue
            if token in seen_targets:
                add_diag("REQ_DEP_DUPLICATE", site.decl_line, snippet, ref=token)
                continue
            seen_targets.add(token)
            dep_targets.append((token, f'"{token}"', False))

        valid_ssot: List[str] = []
        for token in ssot_refs:
            if not SSOT_TOKEN_RE.match(token):
                add_diag("REQ_DEP_EVIDENCE_INVALID", site.decl_line, snippet, ref=token)
                continue
            valid_ssot.append(token)

        dep_targets.sort(key=lambda item: item[0])
        if dep_targets:
            dep_lines: List[str] = []
            for to_norm, to_value, _ in dep_targets:
                dep_id = _dep_id(site.rel_id, from_ref, to_norm)
                parts = [
                    f'id:"{dep_id}"',
                    f"bind:{from_ref}",
                    f"from:{from_ref}",
                    f"to:{to_value}",
                ]
                if valid_ssot:
                    ssot_list = ",".join(valid_ssot)
                    parts.append(f"ssot:[{ssot_list}]")
                dep_lines.append("@Dep { " + ", ".join(parts) + " }")
            insert_map[site.start_line] = dep_lines

    cycles = detect_cycles(dep_graph)
    if cycles:
        for cycle in cycles:
            head = cycle[0]
            line_no = line_map.get(head, 1)
            add_diag(
                "REQ_DEP_CYCLE_DETECTED",
                line_no,
                safe_snippet(lines[line_no - 1]) if line_no - 1 < len(lines) else "",
                cycle=[f"{k}.{v}" for k, v in cycle],
            )

    return insert_map, diagnostics, details


def _is_generated_dep_line(line: str) -> bool:
    return bool(
        re.search(
            r'^\s*@Dep\b.*\bid\s*:\s*"DEP_[A-Z0-9_]+_(?:\d+|[a-f0-9]{12})"\b',
            line,
        )
    )


def render_with_deps(lines: List[str], insert_map: Dict[int, List[str]]) -> List[str]:
    out: List[str] = []
    skip_blank = False
    for line_no, line in enumerate(lines, start=1):
        if _is_generated_dep_line(line):
            skip_blank = True
            continue
        if skip_blank and is_blank(line):
            skip_blank = False
            continue
        skip_blank = False
        if line_no in insert_map:
            out.extend(insert_map[line_no])
            out.append("")
        out.append(line)
    return out


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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="File or directory (B2 .sdsl2)")
    ap.add_argument("--ledger", required=True, help="Ledger file or directory")
    ap.add_argument("--out", default=None, help="Output file or directory")
    args = ap.parse_args()

    input_path = Path(args.input)
    files = iter_input_files(input_path)
    if not files:
        raise SystemExit("NO_INPUT_FILES")
    ledger_root = Path(args.ledger)
    if ledger_root.is_file() and len(files) > 1:
        raise SystemExit("LEDGER_FILE_WITH_MULTI_INPUT")

    failures = 0
    for path in files:
        try:
            text = path.read_text(encoding="utf-8")
            lines = text.splitlines()
            statements = parse_statements(lines)
            ledger_path = resolve_ledger_path(path, args.ledger)
            ledger_data = load_ledger(ledger_path)
            insert_map, diagnostics, details = build_deps_and_diagnostics(
                lines, statements, ledger_data
            )
            rendered = render_with_deps(lines, insert_map)
            req_count = sum(1 for code in diagnostics if code.startswith("REQ_"))

            out_path = resolve_output_path(path, args.out)
            atomic_write(out_path, "\n".join(rendered) + "\n")

            diag_path = out_path.with_suffix(".yaml")
            diag = {
                "version": "gate-b3-diagnostics-v2",
                "input_path": str(path),
                "ledger_path": str(ledger_path),
                "output_path": str(out_path),
                "diagnostics": diagnostics,
                "diagnostic_details": details,
            }
            diag_text = emit_yaml(diag)
            diag_path.write_text(diag_text, encoding="utf-8")
            if req_count:
                failures += 1
        except Exception as exc:
            failures += 1
            print(f"[gate-b3] ERROR {path.name}: {exc}")
    return 2 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
