from __future__ import annotations

from typing import Optional

from .lint_constants import (
    LITERAL_FORBIDDEN_PATTERNS,
    NON_DETERMINISTIC_DEFAULT_PATTERN,
    OPTIONAL_MARKER_PATTERN,
    OPTIONAL_MARKER_SPACING_PATTERN,
    SPREAD_LITERAL_PATTERN,
    STRUCT_HEAD_PARAMS_PATTERN,
    TODO_STRING_IN_CONST_PATTERN,
    TYPE_FORBIDDEN_PATTERNS,
    TYPE_INVALID_CHAR_PATTERN,
    TYPE_SPACED_IDENT_PATTERN,
)
from .lint_utils import (
    extract_code_segments,
    find_single_quote_col,
    has_single_quoted_string,
    iter_type_regions,
    strip_inline_comments,
)
from .models import Diagnostic


def rule_forbidden_patterns(lines: list[str], path: str) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    for line_no, col, type_text in iter_type_regions(lines):
        for pattern, code in TYPE_FORBIDDEN_PATTERNS:
            for match in pattern.finditer(type_text):
                matched = match.group(0)
                message = f"FORBIDDEN_PATTERN: {matched}"
                if code == "SDSL2E5002":
                    lower = matched.lower()
                    if "tuple" in lower:
                        message = (
                            "FORBIDDEN_TYPE_TUPLE_GENERIC: use (T1,T2,...) "
                            "e.g., (s,i,ts)"
                        )
                    elif matched.lstrip().startswith("["):
                        message = (
                            "FORBIDDEN_TYPE_BRACKET_ARRAY: use T[] "
                            "e.g., s[]"
                        )
                    elif lower.startswith("list"):
                        message = (
                            "FORBIDDEN_TYPE_LIST_GENERIC: use T[] "
                            "e.g., Operator[]"
                        )
                    elif lower.startswith("dict") or lower.startswith("map"):
                        message = (
                            "FORBIDDEN_TYPE_MAP_GENERIC: use d[K,V] or d"
                        )
                if code == "SDSL2E5206":
                    message = "FORBIDDEN_TYPE_DATETIME: use ts"
                diagnostics.append(
                    Diagnostic(
                        path=path,
                        line=line_no,
                        col=col + match.start(),
                        severity="error",
                        code=code,
                        message=message,
                    )
                )

    for line_no, line in enumerate(lines, start=1):
        segments = extract_code_segments(line)
        for segment_text, segment_col in segments:
            for pattern, code in LITERAL_FORBIDDEN_PATTERNS:
                for match in pattern.finditer(segment_text):
                    matched = match.group(0)
                    message = f"FORBIDDEN_PATTERN: {matched}"
                    diagnostics.append(
                        Diagnostic(
                            path=path,
                            line=line_no,
                            col=segment_col + match.start(),
                            severity="error",
                            code=code,
                            message=message,
                        )
                    )
            spread_match = SPREAD_LITERAL_PATTERN.search(segment_text)
            if spread_match:
                dot_index = spread_match.start() + spread_match.group(0).find("..")
                diagnostics.append(
                    Diagnostic(
                        path=path,
                        line=line_no,
                        col=segment_col + dot_index,
                        severity="error",
                        code="SDSL2E5207",
                        message="SPREAD_IN_LITERAL_FORBIDDEN: expand elements explicitly",
                    )
                )
        if has_single_quoted_string(line):
            col = find_single_quote_col(line)
            if col:
                diagnostics.append(
                    Diagnostic(
                        path=path,
                        line=line_no,
                        col=col,
                        severity="error",
                        code="SDSL2E5101",
                        message="FORBIDDEN_LITERAL_TRUE_FALSE_NULL_SINGLE_QUOTES: single-quoted string. Example: use \"text\" / T / F / None",
                    )
                )
    return diagnostics


def rule_invalid_optional_marker(lines: list[str], path: str) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    for line_no, line in enumerate(lines, start=1):
        cleaned = strip_inline_comments(line)
        match = OPTIONAL_MARKER_PATTERN.search(cleaned)
        if not match:
            continue
        diagnostics.append(
            Diagnostic(
                path=path,
                line=line_no,
                col=match.start() + 1,
                severity="error",
                code="SDSL2E5202",
                message="FIELD_OPTIONAL_MARKER_POSITION_INVALID: use name: Type? e.g., sequence_id: i?",
            )
        )
    return diagnostics


def rule_ellipsis_in_type(lines: list[str], path: str) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    for line_no, col, type_text in iter_type_regions(lines):
        dot_index = type_text.find("...")
        if dot_index == -1:
            continue
        diagnostics.append(
            Diagnostic(
                path=path,
                line=line_no,
                col=col + dot_index,
                severity="error",
                code="SDSL2E5203",
                message="ELLIPSIS_IN_TYPE_FORBIDDEN: use T[] for variable-length lists",
            )
        )
    return diagnostics


def rule_struct_head_params(lines: list[str], path: str) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    for line_no, line in enumerate(lines, start=1):
        cleaned = strip_inline_comments(line)
        if STRUCT_HEAD_PARAMS_PATTERN.search(cleaned):
            diagnostics.append(
                Diagnostic(
                    path=path,
                    line=line_no,
                    col=cleaned.find("struct") + 1,
                    severity="error",
                    code="SDSL2E5204",
                    message="STRUCT_HEAD_PARAMS_FORBIDDEN: use struct Name { ... } (move extras to metadata if needed)",
                )
            )
    return diagnostics


def rule_non_deterministic_defaults(lines: list[str], path: str) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    for line_no, line in enumerate(lines, start=1):
        cleaned = strip_inline_comments(line)
        stripped = cleaned.lstrip()
        if stripped.startswith("const ") or stripped.startswith("f ") or stripped.startswith("async f"):
            continue
        match = NON_DETERMINISTIC_DEFAULT_PATTERN.search(cleaned)
        if not match:
            continue
        diagnostics.append(
            Diagnostic(
                path=path,
                line=line_no,
                col=match.start(1) + 1,
                severity="error",
                code="SDSL2E5205",
                message="NON_DETERMINISTIC_DEFAULT_FORBIDDEN: use a literal or omit default",
            )
        )
    return diagnostics


def rule_todo_string_in_consts(
    lines: list[str], path: str, profile: Optional[str]
) -> list[Diagnostic]:
    if profile != "contract":
        return []
    diagnostics: list[Diagnostic] = []
    for line_no, line in enumerate(lines, start=1):
        cleaned = strip_inline_comments(line)
        match = TODO_STRING_IN_CONST_PATTERN.search(cleaned)
        if not match:
            continue
        diagnostics.append(
            Diagnostic(
                path=path,
                line=line_no,
                col=match.start("todo") + 1,
                severity="warning",
                code="SDSL2W5201",
                message="TODO_STRING_LITERAL_IN_CONST: use None for unknown. Example: const X: s? = None",
            )
        )
    return diagnostics


def rule_type_invalid_chars(lines: list[str], path: str) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    for line_no, col, type_text in iter_type_regions(lines):
        bad_match = TYPE_INVALID_CHAR_PATTERN.search(type_text)
        if not bad_match:
            continue
        diagnostics.append(
            Diagnostic(
                path=path,
                line=line_no,
                col=col + bad_match.start(),
                severity="error",
                code="SDSL2E5218",
                message="TYPE_TOKEN_INVALID_CHAR: remove invalid characters from type",
            )
        )
    return diagnostics


def rule_type_spacing(lines: list[str], path: str) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    for line_no, col, type_text in iter_type_regions(lines):
        if OPTIONAL_MARKER_SPACING_PATTERN.search(type_text) or TYPE_SPACED_IDENT_PATTERN.search(
            type_text
        ):
            diagnostics.append(
                Diagnostic(
                    path=path,
                    line=line_no,
                    col=col,
                    severity="error",
                    code="SDSL2E5210",
                    message="TYPE_TOKEN_SPACING_INVALID: remove spaces inside type tokens. Example: ts or s?",
                )
            )
    return diagnostics
