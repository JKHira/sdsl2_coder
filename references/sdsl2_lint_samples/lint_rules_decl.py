from __future__ import annotations

import re
from typing import Optional

from .lint_constants import (
    CONST_DECL_PATTERN,
    CONST_HEAD_PATTERN,
    DECL_HEAD_PATTERN,
    FIELD_DECL_PATTERN,
    FUNC_HEAD_PATTERN,
    IDENTIFIER_PATTERN,
    INVALID_META_KEY_SPACING_PATTERN,
    NUMERIC_DOT_SPACING_PATTERN,
    NUMERIC_SPACED_DIGITS_PATTERN,
    NUMERIC_TRAILING_ALPHA_PATTERN,
)
from .lint_parse import metadata_line_numbers
from .lint_utils import (
    extract_code_segments,
    extract_param_list,
    extract_return_type,
    iter_const_literal_lines,
    iter_line_contexts,
    strip_inline_comments,
)
from .models import AnnotationBlock, Diagnostic


def rule_enum_member_names(lines: list[str], path: str) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    for line_no, stripped, block_kind, block_depth, cleaned in iter_line_contexts(lines):
        if block_kind != "enum" or block_depth != 1:
            continue
        if not stripped or stripped.startswith(("}", "//", "/*")):
            continue
        content = cleaned.strip()
        if not content or content.startswith("}"):
            continue
        token = content.split("=", 1)[0].strip().rstrip(",")
        if not IDENTIFIER_PATTERN.match(token):
            diagnostics.append(
                Diagnostic(
                    path=path,
                    line=line_no,
                    col=cleaned.find(token) + 1 if token else 1,
                    severity="error",
                    code="SDSL2E5215",
                    message="ENUM_MEMBER_NAME_INVALID: use a single identifier (no spaces). Example: SCHEDULED",
                )
            )
    return diagnostics


def rule_field_name_and_type(lines: list[str], path: str) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    for line_no, stripped, block_kind, block_depth, cleaned in iter_line_contexts(lines):
        if block_kind not in {"struct", "interface", "class"} or block_depth != 1:
            continue
        if not stripped or stripped.startswith(("}", "//", "/*")):
            continue
        if FUNC_HEAD_PATTERN.match(stripped):
            continue
        if ":" not in cleaned:
            continue
        match = FIELD_DECL_PATTERN.match(cleaned)
        if not match:
            name_part = cleaned.split(":", 1)[0].strip()
            if name_part and not IDENTIFIER_PATTERN.match(name_part):
                diagnostics.append(
                    Diagnostic(
                        path=path,
                        line=line_no,
                        col=cleaned.find(name_part) + 1,
                        severity="error",
                        code="SDSL2E5216",
                        message="FIELD_NAME_INVALID: use a single identifier before ':'. Example: error_rate_threshold: f",
                    )
                )
            continue
        type_text = match.group("type").strip()
        if not type_text or type_text.startswith("="):
            diagnostics.append(
                Diagnostic(
                    path=path,
                    line=line_no,
                    col=cleaned.find(":") + 1,
                    severity="error",
                    code="SDSL2E5209",
                    message="TYPE_MISSING: use name: Type. Example: created_at: ts",
                )
            )
    return diagnostics


def rule_missing_default_values(lines: list[str], path: str) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    for line_no, stripped, block_kind, block_depth, cleaned in iter_line_contexts(lines):
        if not cleaned.strip():
            continue
        if block_kind in {"struct", "interface", "class"} and block_depth == 1:
            if FUNC_HEAD_PATTERN.match(stripped):
                continue
            match = FIELD_DECL_PATTERN.match(cleaned)
            if match and match.group("expr") is not None and not match.group("expr").strip():
                diagnostics.append(
                    Diagnostic(
                        path=path,
                        line=line_no,
                        col=cleaned.find("=") + 1,
                        severity="error",
                        code="SDSL2E5211",
                        message="DEFAULT_VALUE_MISSING: add a literal or remove '='",
                    )
                )
        if block_kind is None and cleaned.lstrip().startswith("const "):
            match = CONST_DECL_PATTERN.match(cleaned)
            if match and match.group("expr") is not None and not match.group("expr").strip():
                diagnostics.append(
                    Diagnostic(
                        path=path,
                        line=line_no,
                        col=cleaned.find("=") + 1,
                        severity="error",
                        code="SDSL2E5211",
                        message="DEFAULT_VALUE_MISSING: add a literal or remove '='",
                    )
                )
            if match and (not match.group("type") or not match.group("type").strip()):
                diagnostics.append(
                    Diagnostic(
                        path=path,
                        line=line_no,
                        col=cleaned.find(":") + 1,
                        severity="error",
                        code="SDSL2E5209",
                        message="TYPE_MISSING: use const NAME: Type = Value",
                    )
                )
    return diagnostics


def rule_invalid_numeric_literals(lines: list[str], path: str) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    for line_no, stripped, block_kind, block_depth, cleaned in iter_line_contexts(lines):
        if not cleaned.strip():
            continue
        match: Optional[re.Match[str]] = None
        type_text: Optional[str] = None
        if block_kind in {"struct", "interface", "class"} and block_depth == 1:
            if FUNC_HEAD_PATTERN.match(stripped):
                continue
            match = FIELD_DECL_PATTERN.match(cleaned)
        if block_kind is None and cleaned.lstrip().startswith("const "):
            match = CONST_DECL_PATTERN.match(cleaned)
        if not match or match.group("expr") is None:
            continue
        type_text = match.group("type")
        expr = match.group("expr")
        if not expr or not expr.strip():
            continue
        expr_start = match.start("expr")
        expr_clean = expr.strip().rstrip(",")
        if type_text:
            type_token = type_text.strip()
            is_optional = type_token.endswith("?")
            base_type = type_token[:-1].strip() if is_optional else type_token
            if base_type in {"i", "f"} and any(ch.isdigit() for ch in expr_clean):
                if is_optional and expr_clean == "None":
                    continue
                if not re.fullmatch(r"[-+]?\d+(?:\.\d+)?", expr_clean):
                    diagnostics.append(
                        Diagnostic(
                            path=path,
                            line=line_no,
                            col=expr_start + 1,
                            severity="error",
                            code="SDSL2E5208",
                            message="NUMERIC_LITERAL_INVALID: use digits without extra symbols",
                        )
                    )
                    continue
        for segment_text, segment_col in extract_code_segments(expr):
            for pattern in (
                NUMERIC_TRAILING_ALPHA_PATTERN,
                NUMERIC_SPACED_DIGITS_PATTERN,
                NUMERIC_DOT_SPACING_PATTERN,
            ):
                bad_match = pattern.search(segment_text)
                if not bad_match:
                    continue
                diagnostics.append(
                    Diagnostic(
                        path=path,
                        line=line_no,
                        col=expr_start + segment_col + bad_match.start(),
                        severity="error",
                        code="SDSL2E5208",
                        message="NUMERIC_LITERAL_INVALID: use digits without spaces or suffix letters",
                    )
                )
                break
    return diagnostics


def rule_function_signatures(lines: list[str], path: str) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    for line_no, stripped, _block_kind, _block_depth, cleaned in iter_line_contexts(lines):
        if not FUNC_HEAD_PATTERN.match(stripped):
            continue
        name_match = re.match(r"^(async\s+)?f\s+([A-Za-z_][A-Za-z0-9_]*)(?P<rest>.*)$", stripped)
        if not name_match:
            diagnostics.append(
                Diagnostic(
                    path=path,
                    line=line_no,
                    col=cleaned.find("f") + 1,
                    severity="error",
                    code="SDSL2E5217",
                    message="FUNCTION_NAME_INVALID: use f name(...)",
                )
            )
            continue
        rest = name_match.group("rest")
        if "(" in rest:
            before_paren = rest.split("(", 1)[0]
            if before_paren.strip():
                diagnostics.append(
                    Diagnostic(
                        path=path,
                        line=line_no,
                        col=cleaned.find(name_match.group(2)) + 1,
                        severity="error",
                        code="SDSL2E5217",
                        message="FUNCTION_NAME_INVALID: use f name(...)",
                    )
                )
        else:
            diagnostics.append(
                Diagnostic(
                    path=path,
                    line=line_no,
                    col=cleaned.find(name_match.group(2)) + 1,
                    severity="error",
                    code="SDSL2E5217",
                    message="FUNCTION_NAME_INVALID: use f name(...)",
                )
            )
        arrow_line = None
        arrow_line_no = line_no
        if "->" in cleaned:
            arrow_line = cleaned
        else:
            arrow_line_no, arrow_line = _find_return_arrow_line(lines, line_no - 1)
        if arrow_line is None:
            diagnostics.append(
                Diagnostic(
                    path=path,
                    line=line_no,
                    col=cleaned.find("f") + 1,
                    severity="error",
                    code="SDSL2E5212",
                    message="FUNCTION_RETURN_ARROW_MISSING: use '-> Type'",
                )
            )
            continue
        return_type = extract_return_type(arrow_line)
        if not return_type:
            diagnostics.append(
                Diagnostic(
                    path=path,
                    line=arrow_line_no,
                    col=arrow_line.find("->") + 1,
                    severity="error",
                    code="SDSL2E5213",
                    message="FUNCTION_RETURN_TYPE_MISSING: provide a return type after '->'",
                )
            )
        else:
            _type_text, _type_col = return_type

        params = extract_param_list(cleaned)
        if params is None:
            continue
        for match in re.finditer(r":\s*(?=$|,)", params):
            diagnostics.append(
                Diagnostic(
                    path=path,
                    line=line_no,
                    col=cleaned.find("(") + match.start() + 2,
                    severity="error",
                    code="SDSL2E5214",
                    message="FUNCTION_PARAM_TYPE_MISSING: use name: Type",
                )
            )
    return diagnostics


def _find_return_arrow_line(
    lines: list[str], start_index: int
) -> tuple[int, Optional[str]]:
    max_lines = 20
    paren_depth = 0
    saw_paren = False
    for offset in range(max_lines):
        index = start_index + offset
        if index >= len(lines):
            break
        raw = strip_inline_comments(lines[index])
        line = raw.rstrip("\n")
        if not line.strip():
            continue
        if offset > 0 and line.lstrip().startswith(("@", "struct ", "enum ", "interface ", "class ", "const ")):
            break
        for ch in line:
            if ch == "(":
                paren_depth += 1
                saw_paren = True
            elif ch == ")":
                paren_depth = max(paren_depth - 1, 0)
        if "->" in line and saw_paren and paren_depth == 0:
            return index + 1, line
        if saw_paren and paren_depth == 0 and "{" in line:
            break
        if saw_paren and paren_depth == 0 and line.strip().startswith("}"):
            break
    return start_index + 1, None


def rule_metadata_key_invalid(
    lines: list[str], path: str, annotations: list[AnnotationBlock]
) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    for ann in annotations:
        if not ann.meta_text or ann.meta_start_line is None or ann.meta_start_col is None:
            continue
        meta_lines = ann.meta_text.splitlines()
        for index, line in enumerate(meta_lines):
            match = INVALID_META_KEY_SPACING_PATTERN.search(line)
            if not match:
                continue
            col = (ann.meta_start_col if index == 0 else 1) + match.start()
            diagnostics.append(
                Diagnostic(
                    path=path,
                    line=ann.meta_start_line + index,
                    col=col,
                    severity="error",
                    code="SDSL2E5220",
                    message="METADATA_KEY_INVALID: remove spaces in key. Example: id:\"X\"",
                )
            )
    return diagnostics


def rule_decl_keyword_unknown(
    lines: list[str], path: str, annotations: list[AnnotationBlock]
) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    allowed = {"struct", "enum", "interface", "class", "C", "const", "f", "async"}
    const_literal_lines = set(iter_const_literal_lines(lines))
    meta_lines = metadata_line_numbers(annotations)
    for line_no, stripped, block_kind, _block_depth, cleaned in iter_line_contexts(lines):
        if block_kind is not None:
            continue
        if line_no in const_literal_lines:
            continue
        if line_no in meta_lines:
            continue
        if not stripped or stripped.startswith(("//", "/*", "@")):
            continue
        first = stripped.split(None, 1)[0]
        if first in allowed:
            continue
        if any(token in cleaned for token in ("{", ":", "(", "->")):
            diagnostics.append(
                Diagnostic(
                    path=path,
                    line=line_no,
                    col=cleaned.find(first) + 1,
                    severity="error",
                    code="SDSL2E5221",
                    message="DECLARATION_KEYWORD_UNKNOWN: use struct/enum/interface/class/const/f",
                )
            )
    return diagnostics


def rule_decl_name_invalid(lines: list[str], path: str) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    for line_no, stripped, block_kind, _block_depth, cleaned in iter_line_contexts(lines):
        if block_kind is not None:
            continue
        match = DECL_HEAD_PATTERN.match(cleaned)
        if not match:
            continue
        rest = match.group("rest")
        rest = rest.split("{", 1)[0].split("(", 1)[0].strip()
        if not rest:
            continue
        parts = rest.split()
        if len(parts) != 1 or not IDENTIFIER_PATTERN.match(parts[0]):
            diagnostics.append(
                Diagnostic(
                    path=path,
                    line=line_no,
                    col=cleaned.find(rest) + 1,
                    severity="error",
                    code="SDSL2E5223",
                    message="DECLARATION_NAME_INVALID: use a single identifier. Example: enum KillResult",
                )
            )
    return diagnostics


def rule_const_name_invalid(lines: list[str], path: str) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    for line_no, stripped, block_kind, _block_depth, cleaned in iter_line_contexts(lines):
        if block_kind is not None:
            continue
        match = CONST_HEAD_PATTERN.match(cleaned)
        if not match:
            continue
        rest = match.group("rest")
        name_part = rest.split(":", 1)[0].strip()
        if not name_part:
            continue
        parts = name_part.split()
        if len(parts) != 1 or not IDENTIFIER_PATTERN.match(parts[0]):
            diagnostics.append(
                Diagnostic(
                    path=path,
                    line=line_no,
                    col=cleaned.find(name_part) + 1,
                    severity="error",
                    code="SDSL2E5224",
                    message="CONST_NAME_INVALID: use const NAME: Type",
                )
            )
    return diagnostics
