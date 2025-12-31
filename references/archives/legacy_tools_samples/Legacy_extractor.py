#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Deterministic v1 (legacy-tagged TS/MD) contract extractor -> YAML ledger.

Design goals:
- Deterministic parsing (no heuristics that depend on runtime environment).
- Closed-set legacy tag recognition (regex-fixed).
- Explicit attribution rules (tag -> next decl head only, strict adjacency).
- Stable-ID normalization: rel_id = strip(id_prefix + "_") if present.
 - Evidence extraction from closed-set tags only (@Rule/@SSOTRef).

This script is intentionally "parseable-first": it does NOT enforce canonical lint.

Usage example (scope/module/id_prefix inferred from filename):
python Legacy_extractor.py --input P0_SAFETY_FOUNDATION_SDSL_CONTRACT.md \
  --output-contract-v2-path ./out/contracts \
  --output-ledger-path ./out/ledgers

If you want strict enforcement that scope is Pn:
python Legacy_extractor.py --input P0_SAFETY_FOUNDATION_SDSL_CONTRACT.md \
  --output-contract-v2-path ./out/contracts \
  --output-ledger-path ./out/ledgers \
  --strict-scope-pn
"""

from __future__ import annotations

import argparse
from pathlib import Path
import re
import sys
from dataclasses import dataclass
from typing import List, Optional, Dict, Any, Tuple


# ----------------------------
# Fixed closed-set vocab
# ----------------------------

ANCHOR_KINDS = ("DocMeta", "Structure", "Interface", "Class", "Function", "Const", "Type")
EVIDENCE_TAG_KINDS = ("Rule", "SSOTRef")

DECL_KIND_BY_DECL_HEAD = {
    "enum": "enum",
    "struct": "struct",
    "interface": "interface",
    "class": "class",
    "const": "const",
    "type": "type",
    "f": "function",
    "C": "class",  # legacy "C Name { ... }"
}

ANCHOR_KIND_BY_DECL_KIND = {
    "docmeta": "DocMeta",
    "enum": "Structure",
    "struct": "Structure",
    "interface": "Interface",
    "class": "Class",
    "function": "Function",
    "const": "Const",
    "type": "Type",
}

RELID_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")
DOCMETA_RELID_RE = re.compile(r"^SEC[0-9]+(?:_.*)?$")

# Legacy tag line: // @Kind.ID or // @Kind.ID: optional_title
# - Kind is closed set (DocMeta/Structure/Interface/Class/Function/Const)
# - ID is UPPER_SNAKE_CASE-ish token (we accept A-Z0-9_ only)
LEGACY_TAG_RE = re.compile(
    r"""^\s*(?P<prefix>//\s*)?@(?P<kind>DocMeta|Structure|Interface|Class|Function|Const|Type)\.(?P<id>[A-Z0-9_]+)(?:\s*:\s*(?P<title>.*))?\s*$"""
)
LEGACY_TAG_INLINE_RE = re.compile(
    r"""@(?P<kind>DocMeta|Structure|Interface|Class|Function|Const|Type)\.(?P<id>[A-Z0-9_]+)"""
)
LEGACY_EVIDENCE_TAG_RE = re.compile(
    r"""^\s*(?P<prefix>//\s*)?@(?P<kind>Rule|SSOTRef)\.(?P<id>[A-Z0-9_]+)(?:\s*:\s*(?P<body>.*))?\s*$"""
)

EVIDENCE_INTERNAL_REF_RE = re.compile(
    r"""@(?P<kind>[A-Za-z_][A-Za-z0-9_]*)\s*(?:\.|::)\s*(?P<id>[A-Za-z0-9_]+)"""
)
EVIDENCE_CONTRACT_TOKEN_RE = re.compile(r"\b(CONTRACT)\.([A-Za-z0-9_]+)\b", re.IGNORECASE)
EVIDENCE_SSOT_TOKEN_RE = re.compile(r"\b(SSOT)\.([A-Za-z0-9_]+)\b", re.IGNORECASE)

# Declaration heads (closed-set; keep simple, parseable-first)
ENUM_HEAD_RE = re.compile(r"^\s*enum\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\{?")
STRUCT_HEAD_RE = re.compile(r"^\s*struct\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\{?")
INTERFACE_HEAD_RE = re.compile(
    r"^\s*interface\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\{?"
)
CLASS_HEAD_RE = re.compile(r"^\s*class\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*(?:\(|\{)?")
C_CLASS_HEAD_RE = re.compile(r"^\s*C\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*(?:\(|\{)?")
CONST_HEAD_RE = re.compile(r"^\s*const\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b")
TYPE_HEAD_RE = re.compile(r"^\s*type\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b")
FUNC_HEAD_RE = re.compile(
    r"^\s*(?:@classmethod\s+)?(?:async\s+)?f\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\("
)


# ----------------------------
# Data model
# ----------------------------


@dataclass(frozen=True)
class LegacyTag:
    kind: str  # Anchor kind (CamelCase)
    stable_id: str  # e.g., P0_C_KSDC_KILL_LEVEL
    title: str  # remainder after colon
    line_no: int  # 1-based
    raw: str
    is_comment: bool


@dataclass(frozen=True)
class EvidenceTag:
    kind: str  # Rule | SSOTRef
    stable_id: str
    body: str
    line_no: int
    raw: str
    is_comment: bool


@dataclass(frozen=True)
class DeclHead:
    decl_kind: str  # lowercase (enum|struct|interface|class|function|const)
    decl_name: str  # as appears in v1
    line_no: int
    raw: str


@dataclass(frozen=True)
class Attribution:
    tag: LegacyTag
    decl: Optional[DeclHead]  # None if unattrib
    reason: str  # "ATTRIBUTED" | "UNATTRIBUTED"
    dup_decl_line: Optional[int] = None


# ----------------------------
# Utilities
# ----------------------------


def upper_snake(s: str) -> str:
    # Deterministic, minimal: split CamelCase and non-alnum to underscores, then upper.
    s = re.sub(r"[^A-Za-z0-9]+", "_", s)
    s = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s.upper() if s else "UNNAMED"


def normalize_rel_id(stable_id: str, legacy_id_prefix: str) -> str:
    # Policy: strip legacy_id_prefix_ if present; else strip Pn_C_ if present; else keep verbatim.
    pfx = legacy_id_prefix + "_"
    if stable_id.startswith(pfx):
        return stable_id[len(pfx) :]
    m = re.match(r"^P[0-9]+_C_(.+)$", stable_id)
    if m:
        return m.group(1)
    return stable_id


def infer_header_from_input_path(input_path: str) -> Tuple[str, str, str, str]:
    stem = Path(input_path).stem
    upper = stem.upper()
    if "CONTRACT" not in upper:
        raise ValueError("INPUT_FILENAME_MISSING_CONTRACT_TOKEN")

    if upper.startswith("SHARED_INFRA"):
        if not re.match(r"^SHARED_INFRA(?:_SDSL)?_CONTRACT$", upper):
            raise ValueError("INPUT_FILENAME_SHARED_INFRA_FORMAT_INVALID")
        scope = "SI"
        module = "SHARED_INFRA"
    else:
        m = re.match(r"^(P[0-9]+)_([A-Z0-9_]+)_(SDSL_CONTRACT|CONTRACT)$", upper)
        if not m:
            raise ValueError("INPUT_FILENAME_FORMAT_INVALID")
        scope = m.group(1)
        module = m.group(2)
        if module.endswith("_SDSL"):
            module = module[: -len("_SDSL")]

    id_prefix = f"{scope}_C_{module}"
    legacy_id_prefix = f"{scope}_C"
    return scope, module, id_prefix, legacy_id_prefix


def infer_output_stem(input_path: str) -> str:
    stem = Path(input_path).stem
    upper = stem.upper()
    if upper.endswith("_SDSLV2_CONTRACT"):
        return stem
    if upper.endswith("_SDSL_CONTRACT"):
        return stem[: -len("_SDSL_CONTRACT")] + "_SDSLv2_CONTRACT"
    if upper.endswith("_CONTRACT"):
        return stem[: -len("_CONTRACT")] + "_SDSLv2_CONTRACT"
    return stem + "_SDSLv2_CONTRACT"


def resolve_output_path(output_path: str, input_path: str, suffix: str) -> Path:
    out = Path(output_path)
    if out.suffix and not out.is_dir():
        out.parent.mkdir(parents=True, exist_ok=True)
        return out
    out.mkdir(parents=True, exist_ok=True)
    stem = infer_output_stem(input_path)
    return out / f"{stem}{suffix}"


def is_blank(line: str) -> bool:
    return line.strip() == ""


def is_comment(line: str) -> bool:
    return line.lstrip().startswith("//")


def is_nonblank_noncomment(line: str) -> bool:
    return (not is_blank(line)) and (not is_comment(line))


def extract_ts_regions_from_markdown(text: str) -> str:
    """
    If input is markdown containing fenced code blocks (ts/typescript/sdsl/sdsl2),
    return a line-aligned view where only those blocks are kept and all other lines
    are blanked. Otherwise, return input as-is.
    """
    lines = text.split("\n")
    fence_langs = {"typescript", "ts", "sdsl", "sdsl2"}
    fence_re = re.compile(r"^\s*```(?P<lang>[A-Za-z0-9_+-]*)\s*$")
    in_fence = False
    capture = False
    saw_fence = False
    saw_supported_fence = False
    out: List[str] = []

    for line in lines:
        m = fence_re.match(line)
        if m:
            saw_fence = True
            if not in_fence:
                lang = m.group("lang").lower()
                capture = lang in fence_langs
                if capture:
                    saw_supported_fence = True
                in_fence = True
            else:
                in_fence = False
                capture = False
            out.append("")
            continue

        if in_fence and capture:
            out.append(line)
        else:
            out.append("")

    if not saw_fence or not saw_supported_fence:
        return text
    return "\n".join(out)


def scan_legacy_tags(lines: List[str]) -> List[LegacyTag]:
    out: List[LegacyTag] = []
    for i, line in enumerate(lines, start=1):
        m = LEGACY_TAG_RE.match(line)
        if m:
            out.append(
                LegacyTag(
                    kind=m.group("kind"),
                    stable_id=m.group("id"),
                    title=(m.group("title") or "").strip(),
                    line_no=i,
                    raw=line.rstrip("\n"),
                    is_comment=bool(m.group("prefix")),
                )
            )
            continue

        if is_comment(line):
            continue

        sanitized = _strip_strings_and_line_comment(line)
        for inline in LEGACY_TAG_INLINE_RE.finditer(sanitized):
            out.append(
                LegacyTag(
                    kind=inline.group("kind"),
                    stable_id=inline.group("id"),
                    title="",
                    line_no=i,
                    raw=line.rstrip("\n"),
                    is_comment=False,
                )
            )
    return out


def scan_evidence_tags(lines: List[str]) -> List[EvidenceTag]:
    out: List[EvidenceTag] = []
    for i, line in enumerate(lines, start=1):
        m = LEGACY_EVIDENCE_TAG_RE.match(line)
        if not m:
            continue
        out.append(
            EvidenceTag(
                kind=m.group("kind"),
                stable_id=m.group("id"),
                body=(m.group("body") or "").strip(),
                line_no=i,
                raw=line.rstrip("\n"),
                is_comment=bool(m.group("prefix")),
            )
        )
    return out


def _strip_line_comment(line: str) -> str:
    if "//" not in line:
        return line
    in_string = False
    string_char = ""
    escaped = False
    for i, ch in enumerate(line):
        if in_string:
            if escaped:
                escaped = False
                continue
            if ch == "\\":
                escaped = True
                continue
            if ch == string_char:
                in_string = False
                string_char = ""
            continue
        if ch in ('"', "'"):
            in_string = True
            string_char = ch
            continue
        if ch == "/" and i + 1 < len(line) and line[i + 1] == "/":
            return line[:i]
    return line


def _strip_strings_and_line_comment(line: str) -> str:
    out: List[str] = []
    in_string: Optional[str] = None
    escaped = False
    i = 0
    while i < len(line):
        ch = line[i]
        if in_string is not None:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == in_string:
                in_string = None
            out.append(" ")
            i += 1
            continue
        if ch in ('"', "'", "`"):
            in_string = ch
            out.append(" ")
            i += 1
            continue
        if ch == "/" and i + 1 < len(line) and line[i + 1] == "/":
            break
        out.append(ch)
        i += 1
    return "".join(out)


def _count_brace_delta(line: str) -> int:
    line = _strip_line_comment(line)
    return line.count("{") - line.count("}")


@dataclass
class BraceScanState:
    in_string: Optional[str] = None
    in_block_comment: bool = False
    in_regex: bool = False
    escaped: bool = False
    prev_nonspace: Optional[str] = None


def _looks_like_regex_start(prev_nonspace: Optional[str]) -> bool:
    if prev_nonspace is None:
        return True
    return prev_nonspace in "([{:;,=!?&|+-*%^~"


def _count_brace_delta_with_state(line: str, state: BraceScanState) -> int:
    delta = 0
    i = 0
    if not state.in_string and not state.in_regex and not state.in_block_comment:
        state.prev_nonspace = None
    while i < len(line):
        ch = line[i]
        if state.in_block_comment:
            if ch == "*" and i + 1 < len(line) and line[i + 1] == "/":
                state.in_block_comment = False
                i += 2
                continue
            i += 1
            continue
        if state.in_string is not None:
            if state.escaped:
                state.escaped = False
            elif ch == "\\":
                state.escaped = True
            elif ch == state.in_string:
                state.in_string = None
            i += 1
            continue
        if state.in_regex:
            if state.escaped:
                state.escaped = False
            elif ch == "\\":
                state.escaped = True
            elif ch == "/":
                state.in_regex = False
            i += 1
            continue
        if ch == "/" and i + 1 < len(line):
            nxt = line[i + 1]
            if nxt == "/":
                break
            if nxt == "*":
                state.in_block_comment = True
                i += 2
                continue
            if _looks_like_regex_start(state.prev_nonspace):
                state.in_regex = True
                state.escaped = False
                i += 1
                continue
        if ch in ('"', "'", "`"):
            state.in_string = ch
            state.escaped = False
            i += 1
            continue
        if ch == "{":
            delta += 1
        elif ch == "}":
            delta -= 1
        if not ch.isspace():
            state.prev_nonspace = ch
        i += 1
    return delta


def _scan_decl_head_in_text(text: str, line_no: int) -> Optional[DeclHead]:
    if is_blank(text):
        return None
    m = ENUM_HEAD_RE.match(text)
    if m:
        return DeclHead("enum", m.group("name"), line_no, text.rstrip("\n"))
    m = STRUCT_HEAD_RE.match(text)
    if m:
        return DeclHead("struct", m.group("name"), line_no, text.rstrip("\n"))
    m = INTERFACE_HEAD_RE.match(text)
    if m:
        return DeclHead("interface", m.group("name"), line_no, text.rstrip("\n"))
    m = CLASS_HEAD_RE.match(text)
    if m:
        return DeclHead("class", m.group("name"), line_no, text.rstrip("\n"))
    m = C_CLASS_HEAD_RE.match(text)
    if m:
        return DeclHead("class", m.group("name"), line_no, text.rstrip("\n"))
    m = CONST_HEAD_RE.match(text)
    if m:
        return DeclHead("const", m.group("name"), line_no, text.rstrip("\n"))
    m = TYPE_HEAD_RE.match(text)
    if m:
        return DeclHead("type", m.group("name"), line_no, text.rstrip("\n"))
    m = FUNC_HEAD_RE.match(text)
    if m:
        return DeclHead("function", m.group("name"), line_no, text.rstrip("\n"))
    return None


def scan_decl_heads(lines: List[str]) -> List[DeclHead]:
    out: List[DeclHead] = []
    brace_depth = 0
    state = BraceScanState()
    for i, line in enumerate(lines, start=1):
        if brace_depth == 0 and not state.in_block_comment and not state.in_string and not state.in_regex:
            if is_comment(line) or is_blank(line):
                brace_depth += _count_brace_delta_with_state(line, state)
                continue
            head = _scan_decl_head_in_text(line, i)
            if head:
                out.append(head)

        brace_depth += _count_brace_delta_with_state(line, state)

    return out


def attribute_tags_to_decls(
    lines: List[str], tags: List[LegacyTag], decls: List[DeclHead]
) -> List[Attribution]:
    """
    Strict adjacency attribution:
    - A tag applies only to the next non-blank, non-comment line.
    - That next line must be a recognized decl head; otherwise UNATTRIBUTED.
    - Any blank line between tag and next decl breaks adjacency (i.e., unattrib).
      (Because blanks are non-comment, but we treat blank as a hard separator.)
    """
    # Map line_no -> decl head if exists on that line
    decl_by_line: Dict[int, DeclHead] = {d.line_no: d for d in decls}
    tagged_decl_lines: set[int] = set()

    out: List[Attribution] = []
    n = len(lines)

    for t in tags:
        if t.kind == "DocMeta":
            out.append(Attribution(t, None, "DOCMETA_STANDALONE"))
            continue
        j = t.line_no
        line = lines[j - 1]

        if not t.is_comment:
            matches = list(LEGACY_TAG_INLINE_RE.finditer(line))
            if matches:
                tail = line[matches[-1].end() :].lstrip()
                inline_decl = _scan_decl_head_in_text(tail, j)
                if inline_decl is not None:
                    if inline_decl.line_no in tagged_decl_lines:
                        out.append(
                            Attribution(
                                t,
                                None,
                                "UNATTRIBUTED_DUPLICATE_TAG",
                                dup_decl_line=inline_decl.line_no,
                            )
                        )
                        continue
                    tagged_decl_lines.add(inline_decl.line_no)
                    out.append(Attribution(t, inline_decl, "ATTRIBUTED_SAME_LINE"))
                    continue
        # next physical line
        if j >= n:
            out.append(Attribution(t, None, "UNATTRIBUTED_EOF"))
            continue

        # Walk to next non-comment line, but blank line breaks adjacency immediately.
        k = j + 1
        while k <= n:
            line = lines[k - 1]
            if is_blank(line):
                out.append(Attribution(t, None, "UNATTRIBUTED_BLANK_LINE_BREAK"))
                break
            if is_comment(line):
                k += 1
                continue
            # non-comment, non-blank
            d = decl_by_line.get(k)
            if d is None:
                out.append(Attribution(t, None, "UNATTRIBUTED_NEXT_LINE_NOT_DECL"))
            else:
                if d.line_no in tagged_decl_lines:
                    out.append(
                        Attribution(
                            t,
                            None,
                            "UNATTRIBUTED_DUPLICATE_TAG",
                            dup_decl_line=d.line_no,
                        )
                    )
                    break
                tagged_decl_lines.add(d.line_no)
                out.append(Attribution(t, d, "ATTRIBUTED"))
            break
        else:
            out.append(Attribution(t, None, "UNATTRIBUTED_NO_FOLLOWING_LINE"))

    return out


def attribute_evidence_to_decls(
    lines: List[str], tags: List[EvidenceTag], decls: List[DeclHead]
) -> Tuple[Dict[int, List[EvidenceTag]], List[str], List[Dict[str, Any]]]:
    decl_by_line: Dict[int, DeclHead] = {d.line_no: d for d in decls}
    evidence_by_decl: Dict[int, List[EvidenceTag]] = {}
    diagnostics: List[str] = []
    diagnostic_details: List[Dict[str, Any]] = []
    n = len(lines)

    for t in tags:
        j = t.line_no
        if j >= n:
            diagnostics.append("MIG_LEGACY_EVIDENCE_UNATTRIBUTABLE")
            diagnostic_details.append(
                {
                    "code": "MIG_LEGACY_EVIDENCE_UNATTRIBUTABLE",
                    "line": t.line_no,
                    "snippet": t.raw.strip()[:10],
                    "tag_kind": t.kind,
                    "tag_id": t.stable_id,
                }
            )
            continue
        k = j + 1
        while k <= n:
            line = lines[k - 1]
            if is_blank(line):
                diagnostics.append("MIG_LEGACY_EVIDENCE_UNATTRIBUTABLE")
                diagnostic_details.append(
                    {
                        "code": "MIG_LEGACY_EVIDENCE_UNATTRIBUTABLE",
                        "line": t.line_no,
                        "snippet": t.raw.strip()[:10],
                        "tag_kind": t.kind,
                        "tag_id": t.stable_id,
                    }
                )
                break
            if is_comment(line):
                k += 1
                continue
            d = decl_by_line.get(k)
            if d is None:
                diagnostics.append("MIG_LEGACY_EVIDENCE_UNATTRIBUTABLE")
                diagnostic_details.append(
                    {
                        "code": "MIG_LEGACY_EVIDENCE_UNATTRIBUTABLE",
                        "line": t.line_no,
                        "snippet": t.raw.strip()[:10],
                        "tag_kind": t.kind,
                        "tag_id": t.stable_id,
                    }
                )
            else:
                evidence_by_decl.setdefault(d.line_no, []).append(t)
            break
        else:
            diagnostics.append("MIG_LEGACY_EVIDENCE_UNATTRIBUTABLE")
            diagnostic_details.append(
                {
                    "code": "MIG_LEGACY_EVIDENCE_UNATTRIBUTABLE",
                    "line": t.line_no,
                    "snippet": t.raw.strip()[:10],
                    "tag_kind": t.kind,
                    "tag_id": t.stable_id,
                }
            )

    return evidence_by_decl, diagnostics, diagnostic_details


def extract_evidence_refs(
    text: str, legacy_id_prefix: str
) -> Tuple[List[str], List[str], List[str], List[str], List[str]]:
    internal_refs: List[str] = []
    contract_tokens: List[str] = []
    ssot_tokens: List[str] = []
    invalid_internal: List[str] = []
    invalid_tokens: List[str] = []

    for m in EVIDENCE_INTERNAL_REF_RE.finditer(text):
        kind = m.group("kind")
        if kind not in ANCHOR_KINDS:
            continue
        stable_id = m.group("id")
        rel_id = normalize_rel_id(stable_id, legacy_id_prefix)
        if not RELID_RE.match(rel_id):
            invalid_internal.append(f"@{kind}.{stable_id}")
            continue
        internal_refs.append(f"@{kind}.{rel_id}")

    for m in EVIDENCE_CONTRACT_TOKEN_RE.finditer(text):
        token = m.group(2)
        if not re.match(r"^[A-Z0-9_]+$", token):
            invalid_tokens.append(f"CONTRACT.{token}")
        contract_tokens.append(f"CONTRACT.{token}")

    for m in EVIDENCE_SSOT_TOKEN_RE.finditer(text):
        token = m.group(2)
        if not re.match(r"^[A-Z0-9_]+$", token):
            invalid_tokens.append(f"SSOT.{token}")
        ssot_tokens.append(f"SSOT.{token}")

    internal_refs = sorted(set(internal_refs))
    contract_tokens = sorted(set(contract_tokens))
    ssot_tokens = sorted(set(ssot_tokens))
    invalid_internal = sorted(set(invalid_internal))
    invalid_tokens = sorted(set(invalid_tokens))

    return internal_refs, contract_tokens, ssot_tokens, invalid_internal, invalid_tokens


def build_evidence_for_decl(
    tags: List[EvidenceTag],
    legacy_id_prefix: str,
    diagnostics: List[str],
    diagnostic_details: List[Dict[str, Any]],
) -> Tuple[List[str], List[str], List[str], List[Dict[str, Any]]]:
    internal_refs: List[str] = []
    contract_tokens: List[str] = []
    ssot_tokens: List[str] = []
    events: List[Dict[str, Any]] = []

    for tag in tags:
        refs_internal, refs_contract, refs_ssot, invalid_internal, invalid_tokens = (
            extract_evidence_refs(tag.body, legacy_id_prefix)
        )
        if invalid_internal:
            diagnostics.append("MIG_EVIDENCE_INTERNAL_INVALID")
            diagnostic_details.append(
                {
                    "code": "MIG_EVIDENCE_INTERNAL_INVALID",
                    "line": tag.line_no,
                    "snippet": tag.raw.strip()[:10],
                    "tag_kind": tag.kind,
                    "tag_id": tag.stable_id,
                    "invalid_internal": invalid_internal,
                }
            )
        if invalid_tokens:
            diagnostics.append("MIG_EVIDENCE_TOKEN_NONCANON")
            diagnostic_details.append(
                {
                    "code": "MIG_EVIDENCE_TOKEN_NONCANON",
                    "line": tag.line_no,
                    "snippet": tag.raw.strip()[:10],
                    "tag_kind": tag.kind,
                    "tag_id": tag.stable_id,
                    "invalid_tokens": invalid_tokens,
                }
            )
        if tag.body and not (refs_internal or refs_contract or refs_ssot or invalid_internal or invalid_tokens):
            diagnostics.append("MIG_EVIDENCE_EMPTY")
            diagnostic_details.append(
                {
                    "code": "MIG_EVIDENCE_EMPTY",
                    "line": tag.line_no,
                    "snippet": tag.raw.strip()[:10],
                    "tag_kind": tag.kind,
                    "tag_id": tag.stable_id,
                }
            )
        internal_refs.extend(refs_internal)
        contract_tokens.extend(refs_contract)
        ssot_tokens.extend(refs_ssot)
        events.append(
            {
                "source": "legacy_rule" if tag.kind == "Rule" else "legacy_ssotref",
                "tag_id": tag.stable_id,
                "line": tag.line_no,
                "raw": tag.raw,
                "body": tag.body,
                "refs_internal": refs_internal,
                "refs_contract": refs_contract,
                "refs_ssot": refs_ssot,
            }
        )

    internal_refs = sorted(set(internal_refs))
    contract_tokens = sorted(set(contract_tokens))
    ssot_tokens = sorted(set(ssot_tokens))

    return internal_refs, contract_tokens, ssot_tokens, events


def stable_sort_declarations(decls: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    # Deterministic ordering: by evidence line, then decl_kind, then decl_name
    def key_fn(d: Dict[str, Any]) -> Tuple[int, str, str]:
        loc = d.get("evidence", {}).get("location_hint", "line:999999")
        m = re.match(r"line:(\d+)", str(loc))
        ln = int(m.group(1)) if m else 999999
        return (ln, d.get("decl_kind", ""), d.get("decl_name", ""))

    return sorted(decls, key=key_fn)


# ----------------------------
# Ledger generation
# ----------------------------


def build_ledger(
    source_text: str,
    input_path: str,
    manual_path: str,
    output_contract_v2_path: str,
    output_ledger_path: str,
    profile: str,
    scope: str,
    domain: str,
    module: str,
    id_prefix: str,
    legacy_id_prefix: str,
    strict_scope_pn: bool = False,
) -> Dict[str, Any]:
    if strict_scope_pn and not re.match(r"^P[0-9]+$", scope):
        # parseable-first still emits YAML, but flags it.
        scope_invalid = True
    else:
        scope_invalid = False

    ts_text = extract_ts_regions_from_markdown(source_text)
    lines = ts_text.splitlines()

    tags = scan_legacy_tags(lines)
    evidence_tags = scan_evidence_tags(lines)
    decl_heads = scan_decl_heads(lines)
    attributions = attribute_tags_to_decls(lines, tags, decl_heads)
    evidence_by_decl_line, evidence_diags, evidence_details = attribute_evidence_to_decls(
        lines, evidence_tags, decl_heads
    )

    diagnostics: List[str] = []
    diagnostic_details: List[Dict[str, Any]] = []
    if scope_invalid:
        diagnostics.append("REQ_FILE_HEADER_SCOPE_INVALID")
    diagnostics.extend(evidence_diags)
    diagnostic_details.extend(evidence_details)

    declarations: List[Dict[str, Any]] = []
    entry_by_decl_line: Dict[int, Dict[str, Any]] = {}
    duplicate_details_by_decl_line: Dict[int, List[Dict[str, Any]]] = {}

    tagged_decl_lines = {a.decl.line_no for a in attributions if a.decl is not None}

    # For tags attributed to decls: emit a declaration entry anchored by that tag.
    # For DocMeta tags that are un-attributed: still emit docmeta entries (they are standalone anchors in v2).
    # For non-DocMeta un-attributed tags: emit diagnostics only (parseable-first, minimal).
    for a in attributions:
        if a.reason == "UNATTRIBUTED_DUPLICATE_TAG":
            if a.dup_decl_line is not None:
                duplicate_details_by_decl_line.setdefault(a.dup_decl_line, []).append(
                    {
                        "code": "MIG_DUPLICATE_TAG_SAME_DECL",
                        "tag_kind": a.tag.kind,
                        "tag_id": a.tag.stable_id,
                        "tag_line": a.tag.line_no,
                    }
                )
            diagnostics.append("MIG_DUPLICATE_TAG_SAME_DECL")
            continue

        if a.decl is not None:
            decl_kind = a.decl.decl_kind
            anchor_kind = ANCHOR_KIND_BY_DECL_KIND[decl_kind]
            raw_rel_id = normalize_rel_id(a.tag.stable_id, legacy_id_prefix)
            notes: List[str] = []
            entry_diagnostic_details: List[Dict[str, Any]] = []
            if a.tag.kind != anchor_kind:
                notes.append("MIG_TAG_KIND_MISMATCH")
                diagnostics.append("MIG_TAG_KIND_MISMATCH")
                entry_diagnostic_details.append(
                    {
                        "code": "MIG_TAG_KIND_MISMATCH",
                        "tag_kind": a.tag.kind,
                        "tag_id": a.tag.stable_id,
                        "expected_kind": anchor_kind,
                    }
                )
            if not a.tag.stable_id.startswith(legacy_id_prefix + "_"):
                notes.append("MIG_LEGACY_PREFIX_NOT_STRIPPED")

            entry: Dict[str, Any] = {
                    "decl_kind": decl_kind,
                    "decl_name": a.decl.decl_name,
                    "legacy_stable_id": a.tag.stable_id,
                    "anchor_kind": anchor_kind,
                    "raw_rel_id": raw_rel_id,
                    "decl_line_no": a.decl.line_no,
                    "evidence": {
                        "kind": "code",
                        "location_hint": f"line:{a.tag.line_no}",
                    },
                    "notes": notes,
                }
            refs_internal, refs_contract, refs_ssot, events = build_evidence_for_decl(
                evidence_by_decl_line.get(a.decl.line_no, []),
                legacy_id_prefix,
                diagnostics,
                diagnostic_details,
            )
            entry["evidence_refs_internal"] = refs_internal
            entry["evidence_refs_contract"] = refs_contract
            entry["evidence_refs_ssot"] = refs_ssot
            entry["evidence_events"] = events
            if entry_diagnostic_details:
                entry["diagnostic_details"] = entry_diagnostic_details
            declarations.append(entry)
            entry_by_decl_line[a.decl.line_no] = entry
        else:
            # Unattributed tag
            if a.tag.kind == "DocMeta":
                raw_rel_id = normalize_rel_id(a.tag.stable_id, legacy_id_prefix)
                notes: List[str] = ["MIG_DOCMETA_STANDALONE"]
                if not a.tag.stable_id.startswith(legacy_id_prefix + "_"):
                    notes.append("MIG_LEGACY_PREFIX_NOT_STRIPPED")

                # Use title if present, else fall back to stable id token.
                decl_name = a.tag.title if a.tag.title else a.tag.stable_id
                declarations.append(
                    {
                    "decl_kind": "docmeta",
                    "decl_name": decl_name,
                    "legacy_stable_id": a.tag.stable_id,
                    "anchor_kind": "DocMeta",
                    "raw_rel_id": raw_rel_id,
                        "evidence": {
                            "kind": "code",
                            "location_hint": f"line:{a.tag.line_no}",
                        },
                        "notes": notes,
                        "evidence_refs_internal": [],
                        "evidence_refs_contract": [],
                        "evidence_refs_ssot": [],
                        "evidence_events": [],
                    }
                )
            else:
                # keep diagnostics minimal, token-only
                diagnostics.append("MIG_LEGACY_TAG_UNATTRIBUTABLE")
                line_text = lines[a.tag.line_no - 1] if 0 < a.tag.line_no <= len(lines) else ""
                snippet = line_text.strip()[:10]
                diagnostic_details.append(
                    {
                        "code": "MIG_LEGACY_TAG_UNATTRIBUTABLE",
                        "line": a.tag.line_no,
                        "snippet": snippet,
                        "tag_kind": a.tag.kind,
                        "tag_id": a.tag.stable_id,
                    }
                )

    # Emit untagged decl heads with derived rel_id
    for decl in decl_heads:
        if decl.line_no in tagged_decl_lines:
            continue
        anchor_kind = ANCHOR_KIND_BY_DECL_KIND[decl.decl_kind]
        raw_rel_id = upper_snake(decl.decl_name)
        refs_internal, refs_contract, refs_ssot, events = build_evidence_for_decl(
            evidence_by_decl_line.get(decl.line_no, []),
            legacy_id_prefix,
            diagnostics,
            diagnostic_details,
        )
        declarations.append(
            {
                "decl_kind": decl.decl_kind,
                "decl_name": decl.decl_name,
                "legacy_stable_id": None,
                "anchor_kind": anchor_kind,
                "raw_rel_id": raw_rel_id,
                "evidence": {
                    "kind": "code",
                    "location_hint": f"line:{decl.line_no}",
                },
                "notes": [],
                "evidence_refs_internal": refs_internal,
                "evidence_refs_contract": refs_contract,
                "evidence_refs_ssot": refs_ssot,
                "evidence_events": events,
            }
        )

    for decl_line, details in duplicate_details_by_decl_line.items():
        entry = entry_by_decl_line.get(decl_line)
        if not entry:
            continue
        entry.setdefault("diagnostic_details", []).extend(details)

    for entry in declarations:
        if entry.get("anchor_kind") == "DocMeta":
            entry.setdefault("evidence_refs_internal", [])
            entry.setdefault("evidence_refs_contract", [])
            entry.setdefault("evidence_refs_ssot", [])
            entry.setdefault("evidence_events", [])

    declarations = stable_sort_declarations(declarations)
    unnamed_counters: Dict[str, int] = {}
    for entry in declarations:
        raw_rel_id = entry.pop("raw_rel_id", "")
        if raw_rel_id == "":
            kind = entry.get("anchor_kind", "UNKNOWN").upper()
            unnamed_counters[kind] = unnamed_counters.get(kind, 0) + 1
            entry["rel_id"] = f"UNNAMED_{kind}_{unnamed_counters[kind]}"
            entry.setdefault("notes", []).append("MIG_EMPTY_RELID_AFTER_STRIP")
            diagnostics.append("MIG_EMPTY_RELID_AFTER_STRIP")
            continue
        if not RELID_RE.match(raw_rel_id):
            kind = entry.get("anchor_kind", "UNKNOWN").upper()
            unnamed_counters[kind] = unnamed_counters.get(kind, 0) + 1
            entry["rel_id"] = f"UNNAMED_{kind}_{unnamed_counters[kind]}"
            entry.setdefault("notes", []).append("MIG_RELID_INVALID_FORMAT")
            diagnostics.append("MIG_RELID_INVALID_FORMAT")
            continue
        entry["rel_id"] = raw_rel_id
        entry["canon_id"] = f"{id_prefix}_{entry['rel_id']}"

    for entry in declarations:
        if entry.get("anchor_kind") != "DocMeta":
            continue
        rel_id = entry.get("rel_id", "")
        if rel_id and not DOCMETA_RELID_RE.match(rel_id):
            entry.setdefault("notes", []).append("MIG_DOCMETA_ID_PATTERN_INVALID")
            diagnostics.append("MIG_DOCMETA_ID_PATTERN_INVALID")

    seen: Dict[Tuple[str, str], int] = {}
    has_duplicates = False
    for entry in declarations:
        key = (entry.get("anchor_kind", ""), entry.get("rel_id", ""))
        if key in seen:
            entry.setdefault("notes", []).append("MIG_DUPLICATE_RELID")
            diagnostics.append("MIG_DUPLICATE_RELID")
            has_duplicates = True
        else:
            seen[key] = 1

    ledger: Dict[str, Any] = {
        "version": "contract-ledger-v1",
        "schema_revision": 2,
        "source": {
            "input_path": input_path,
            "manual_path": manual_path,
        },
        "output": {
            "contract_v2_path": output_contract_v2_path,
            "ledger_path": output_ledger_path,
        },
        "file_header": {
            "profile": profile,
            "scope": scope,
            "domain": domain,
            "module": module,
            "id_prefix": id_prefix,
            "legacy_id_prefix": legacy_id_prefix,
        },
        "relid_rule": {
            "primary": "TAG_PREFERRED: rel_id = normalize(legacy_id) if tagged; else UPPER_SNAKE_CASE(decl_name); invalid/empty -> UNNAMED_<KIND>_<n>",
            "collision_policy": "HARD_ERROR",
            "collision_diagnostic": "MIG_DUPLICATE_RELID",
        },
        "canon_id_rule": "file_header.id_prefix + '_' + rel_id",
        "declarations": declarations,
        "diagnostics": diagnostics,
        "diagnostic_details": diagnostic_details,
        "has_duplicates": has_duplicates,
    }
    return ledger


# ----------------------------
# YAML emission (no external deps required)
# ----------------------------


def yaml_escape(s: str) -> str:
    # Always double-quote strings that contain special chars.
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
    # Fallback
    return sp + yaml_escape(str(obj)) + "\n"


def write_contract_stub(
    output_path: Path, profile: str, scope: str, domain: str, module: str, id_prefix: str
) -> None:
    expected_header = (
        f'@File {{ profile:"{profile}", scope:"{scope}", domain:"{domain}", '
        f'module:"{module}", id_prefix:"{id_prefix}" }}'
    )
    expected_docmeta = f'@DocMeta {{ id:"DOC_{id_prefix}" }}'
    if output_path.exists():
        text = output_path.read_text(encoding="utf-8")
        lines = text.splitlines()
        first_two: List[str] = []
        in_block_comment = False
        for line in lines:
            stripped = line.strip()
            if in_block_comment:
                if "*/" in stripped:
                    in_block_comment = False
                continue
            if stripped.startswith("/*"):
                if "*/" not in stripped:
                    in_block_comment = True
                continue
            if stripped == "" or stripped.startswith("//"):
                continue
            first_two.append(stripped)
            if len(first_two) >= 2:
                break
        if len(first_two) < 2 or first_two[0] != expected_header or first_two[1] != expected_docmeta:
            raise SystemExit("OUTPUT_CONTRACT_HEADER_MISMATCH")
        return
    content = f"{expected_header}\n{expected_docmeta}\n"
    output_path.write_text(content, encoding="utf-8")


# ----------------------------
# CLI
# ----------------------------


def main(argv: List[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--input",
        required=True,
        help="Path to v1 contract (ts or md), a directory to batch-process, or '-' for stdin.",
    )
    ap.add_argument("--manual-path", default=None)
    ap.add_argument(
        "--output-contract-v2-path",
        required=True,
        help="Output directory for v2 contract (file name auto-derived).",
    )
    ap.add_argument(
        "--output-ledger-path",
        required=True,
        help="Output directory for ledger YAML (file name auto-derived).",
    )

    ap.add_argument("--profile", default="contract")
    ap.add_argument(
        "--scope",
        default=None,
        help='e.g. "P0" or "P1" or "SI" (use --strict-scope-pn to enforce Pn only)',
    )
    ap.add_argument("--domain", default="C")
    ap.add_argument("--module", default=None)
    ap.add_argument(
        "--id-prefix", default=None, help='e.g. "P0_C_X" or "P1_C_Y" or "SI_C_Z"'
    )
    ap.add_argument(
        "--legacy-id-prefix", default=None, help='e.g. "P0_C" or "SI_C"'
    )

    ap.add_argument(
        "--strict-scope-pn",
        action="store_true",
        help="If set, requires scope to match ^P[0-9]+$ (else emits REQ_FILE_HEADER_SCOPE_INVALID).",
    )
    ap.add_argument(
        "--allow-duplicates",
        action="store_true",
        help="If set, allows duplicate rel_id entries (default: fail when duplicates exist).",
    )
    args = ap.parse_args(argv)

    if args.manual_path is None:
        default_manual = (
            Path(__file__).resolve().parent.parent / "SDSL_v2_Manual_Compact.md"
        )
        args.manual_path = str(default_manual)

    def process_file(input_file: Path, emit_stdout: bool) -> Tuple[bool, str]:
        with open(input_file, "r", encoding="utf-8") as f:
            text = f.read()

        auto_scope, auto_module, auto_id_prefix, auto_legacy_prefix = (
            infer_header_from_input_path(str(input_file))
        )
        if args.scope and args.scope != auto_scope:
            raise SystemExit("SCOPE_MISMATCH_WITH_FILENAME")
        if args.module and args.module != auto_module:
            raise SystemExit("MODULE_MISMATCH_WITH_FILENAME")
        if args.id_prefix and args.id_prefix != auto_id_prefix:
            raise SystemExit("ID_PREFIX_MISMATCH_WITH_FILENAME")
        if args.legacy_id_prefix and args.legacy_id_prefix != auto_legacy_prefix:
            raise SystemExit("LEGACY_ID_PREFIX_MISMATCH_WITH_FILENAME")

        scope = args.scope or auto_scope
        module = args.module or auto_module
        id_prefix = args.id_prefix or auto_id_prefix
        legacy_id_prefix = args.legacy_id_prefix or auto_legacy_prefix

        contract_output_path = resolve_output_path(
            args.output_contract_v2_path, str(input_file), ".sdsl2"
        )
        ledger_output_path = resolve_output_path(
            args.output_ledger_path, str(input_file), ".yaml"
        )

        ledger = build_ledger(
            source_text=text,
            input_path=str(input_file),
            manual_path=args.manual_path,
            output_contract_v2_path=str(contract_output_path),
            output_ledger_path=str(ledger_output_path),
            profile=args.profile,
            scope=scope,
            domain=args.domain,
            module=module,
            id_prefix=id_prefix,
            legacy_id_prefix=legacy_id_prefix,
            strict_scope_pn=args.strict_scope_pn,
        )

        ledger_text = emit_yaml(ledger)
        has_duplicates = bool(ledger.get("has_duplicates"))
        ledger_output_path.write_text(ledger_text, encoding="utf-8")
        write_contract_stub(
            contract_output_path, args.profile, scope, args.domain, module, id_prefix
        )
        if emit_stdout:
            sys.stdout.write(ledger_text)
        if not args.allow_duplicates and has_duplicates:
            return False, "MIG_DUPLICATE_RELID"
        return True, ""

    if args.input == "-":
        text = sys.stdin.read()
        input_path = "<STDIN>"
    else:
        input_path = args.input

    if input_path == "<STDIN>":
        if not (args.scope and args.module and args.id_prefix):
            raise SystemExit("STDIN requires --scope, --module, and --id-prefix.")
        if not args.legacy_id_prefix:
            raise SystemExit("STDIN requires --legacy-id-prefix.")
        if not (
            Path(args.output_contract_v2_path).suffix
            and Path(args.output_ledger_path).suffix
        ):
            raise SystemExit("STDIN requires explicit output file paths.")
        scope = args.scope
        module = args.module
        id_prefix = args.id_prefix
        legacy_id_prefix = args.legacy_id_prefix
        ledger = build_ledger(
            source_text=text,
            input_path=input_path,
            manual_path=args.manual_path,
            output_contract_v2_path=args.output_contract_v2_path,
            output_ledger_path=args.output_ledger_path,
            profile=args.profile,
            scope=scope,
            domain=args.domain,
            module=module,
            id_prefix=id_prefix,
            legacy_id_prefix=legacy_id_prefix,
            strict_scope_pn=args.strict_scope_pn,
        )

        ledger_text = emit_yaml(ledger)
        has_duplicates = bool(ledger.get("has_duplicates"))
        if not args.allow_duplicates and has_duplicates:
            sys.stdout.write(ledger_text)
            return 2
        sys.stdout.write(ledger_text)
        return 0

    input_path_obj = Path(input_path)
    if input_path_obj.is_dir():
        candidates = sorted(p for p in input_path_obj.iterdir() if p.is_file())
        matched: List[Path] = []
        for cand in candidates:
            try:
                infer_header_from_input_path(str(cand))
                matched.append(cand)
            except ValueError:
                continue

        if not matched:
            raise SystemExit("NO_MATCHING_CONTRACT_FILES")

        ok_count = 0
        fail_count = 0
        for file_path in matched:
            try:
                ok, _ = process_file(file_path, emit_stdout=False)
                if ok:
                    ok_count += 1
                else:
                    fail_count += 1
            except SystemExit:
                fail_count += 1
            except Exception:
                fail_count += 1

        sys.stdout.write(f"processed={ok_count} failed={fail_count}\n")
        return 2 if fail_count > 0 else 0

    ok, _ = process_file(input_path_obj, emit_stdout=True)
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
