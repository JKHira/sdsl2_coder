from __future__ import annotations

import re

from .lint_constants import (
    CONST_DECL_PATTERN,
    FIELD_DECL_PATTERN,
    FUNC_HEAD_PATTERN,
    IDENTIFIER_PATTERN,
    INVALID_LITERAL_TOKEN_PATTERN,
    LOWER_ONLY_IDENTIFIER_PATTERN,
    TOKEN_LIKE_STRING_PATTERN,
)
from .lint_utils import (
    extract_code_segments,
    iter_const_literal_lines,
    iter_line_contexts,
    iter_string_literals,
    is_mixed_case,
    strip_inline_comments,
)
from .models import Diagnostic


STRING_LITERAL_PATTERN = re.compile(r'^\s*"(?:[^"\\]|\\.)*"\s*$')
IDENTIFIER_ALLOWED_PATTERN = re.compile(r"^[A-Za-z0-9_]+$")


def rule_scalar_literal_wrapping(lines: list[str], path: str) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    for line_no, stripped, block_kind, block_depth, cleaned in iter_line_contexts(lines):
        if not cleaned.strip():
            continue
        match = None
        if block_kind in {"struct", "interface", "class"} and block_depth == 1:
            if FUNC_HEAD_PATTERN.match(stripped):
                continue
            match = FIELD_DECL_PATTERN.match(cleaned)
        if block_kind is None and cleaned.lstrip().startswith("const "):
            match = CONST_DECL_PATTERN.match(cleaned)
        if not match or match.group("expr") is None:
            continue

        type_text = match.group("type").strip()
        expr = match.group("expr")
        if expr is None:
            continue
        expr_clean = expr.strip().rstrip(",")
        if not expr_clean:
            continue

        is_optional = type_text.endswith("?")
        base_type = type_text[:-1].strip() if is_optional else type_text
        if is_optional and expr_clean == "None":
            continue

        has_structure = False
        for segment_text, _segment_col in extract_code_segments(expr_clean):
            if any(ch in segment_text for ch in "{}[]"):
                has_structure = True
                break
            if "," in segment_text:
                has_structure = True
                break
        if has_structure:
            continue

        if base_type == "s" and "\"" in expr_clean:
            if not STRING_LITERAL_PATTERN.fullmatch(expr_clean):
                col = match.start("expr") + expr.find("\"") + 1
                diagnostics.append(
                    Diagnostic(
                        path=path,
                        line=line_no,
                        col=col,
                        severity="error",
                        code="SDSL2E5232",
                        message="STRING_LITERAL_WRAPPING_INVALID: use a single \"value\" literal",
                    )
                )
        if base_type == "b":
            if expr_clean not in {"T", "F"} and expr_clean[:1] in {"T", "F"}:
                col = match.start("expr") + len(expr) - len(expr.lstrip()) + 1
                diagnostics.append(
                    Diagnostic(
                        path=path,
                        line=line_no,
                        col=col,
                        severity="error",
                        code="SDSL2E5232",
                        message="BOOLEAN_LITERAL_INVALID: use T or F only",
                    )
                )
    return diagnostics


def rule_invalid_literal_spacing(lines: list[str], path: str) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    const_literal_lines = set(iter_const_literal_lines(lines))
    for line_no, stripped, block_kind, block_depth, cleaned in iter_line_contexts(lines):
        expr = None
        expr_start = 0
        if block_kind in {"struct", "interface", "class"} and block_depth == 1:
            if FUNC_HEAD_PATTERN.match(stripped):
                continue
            match = FIELD_DECL_PATTERN.match(cleaned)
            if match and match.group("expr") is not None:
                expr = match.group("expr")
                expr_start = match.start("expr")
        if block_kind is None and cleaned.lstrip().startswith("const "):
            match = CONST_DECL_PATTERN.match(cleaned)
            if match and match.group("expr") is not None:
                expr = match.group("expr")
                expr_start = match.start("expr")
        if expr is not None:
            for segment_text, segment_col in extract_code_segments(expr):
                bad_match = INVALID_LITERAL_TOKEN_PATTERN.search(segment_text)
                if not bad_match:
                    continue
                diagnostics.append(
                    Diagnostic(
                        path=path,
                        line=line_no,
                        col=expr_start + segment_col + bad_match.start(),
                        severity="error",
                        code="SDSL2E5219",
                        message="LITERAL_TOKEN_SPACING_INVALID: remove spaces inside tokens",
                    )
                )
                break

        if line_no in const_literal_lines:
            for segment_text, segment_col in extract_code_segments(cleaned):
                bad_match = INVALID_LITERAL_TOKEN_PATTERN.search(segment_text)
                if not bad_match:
                    continue
                diagnostics.append(
                    Diagnostic(
                        path=path,
                        line=line_no,
                        col=segment_col + bad_match.start(),
                        severity="error",
                        code="SDSL2E5219",
                        message="LITERAL_TOKEN_SPACING_INVALID: remove spaces inside tokens",
                    )
                )
                break
    return diagnostics


def rule_enum_string_values(lines: list[str], path: str) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    for line_no, _stripped, block_kind, block_depth, cleaned in iter_line_contexts(lines):
        if block_kind != "enum" or block_depth != 1:
            continue
        if "=" not in cleaned:
            continue
        _, value = cleaned.split("=", 1)
        value = value.strip().rstrip(",")
        if len(value) < 2 or value[0] not in {"\"", "'"}:
            continue
        quote = value[0]
        end_index = value.find(quote, 1)
        if end_index == -1:
            continue
        content = value[1:end_index]
        if any(ch.isspace() for ch in content):
            diagnostics.append(
                Diagnostic(
                    path=path,
                    line=line_no,
                    col=cleaned.find(value) + 1,
                    severity="error",
                    code="SDSL2E5222",
                    message="ENUM_STRING_VALUE_WHITESPACE_FORBIDDEN: remove spaces in enum string values",
                )
            )
    return diagnostics


def rule_enum_string_value_symbols(lines: list[str], path: str) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    for line_no, _stripped, block_kind, block_depth, cleaned in iter_line_contexts(lines):
        if block_kind != "enum" or block_depth != 1:
            continue
        if "=" not in cleaned:
            continue
        _, value = cleaned.split("=", 1)
        value = value.strip().rstrip(",")
        if len(value) < 2 or value[0] not in {"\"", "'"}:
            continue
        quote = value[0]
        end_index = value.find(quote, 1)
        if end_index == -1:
            continue
        content = value[1:end_index]
        if content and not IDENTIFIER_ALLOWED_PATTERN.fullmatch(content):
            diagnostics.append(
                Diagnostic(
                    path=path,
                    line=line_no,
                    col=cleaned.find(value) + 1,
                    severity="error",
                    code="SDSL2E5233",
                    message="ENUM_STRING_VALUE_INVALID_SYMBOL: use letters/digits/_ only",
                )
            )
    return diagnostics


def rule_string_literal_token_spacing(lines: list[str], path: str) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    const_literal_lines = set(iter_const_literal_lines(lines))
    for line_no, stripped, block_kind, block_depth, cleaned in iter_line_contexts(lines):
        expr = None
        expr_start = 0
        if block_kind in {"struct", "interface", "class"} and block_depth == 1:
            if FUNC_HEAD_PATTERN.match(stripped):
                continue
            match = FIELD_DECL_PATTERN.match(cleaned)
            if match and match.group("expr") is not None:
                expr = match.group("expr")
                expr_start = match.start("expr")
        if block_kind is None and cleaned.lstrip().startswith("const "):
            match = CONST_DECL_PATTERN.match(cleaned)
            if match and match.group("expr") is not None:
                expr = match.group("expr")
                expr_start = match.start("expr")
        if expr is not None:
            for content, offset in iter_string_literals(expr):
                if not any(ch.isspace() for ch in content):
                    continue
                normalized = "".join(ch for ch in content if not ch.isspace())
                if TOKEN_LIKE_STRING_PATTERN.match(normalized):
                    diagnostics.append(
                        Diagnostic(
                            path=path,
                            line=line_no,
                            col=expr_start + offset,
                            severity="error",
                            code="SDSL2E5225",
                            message="STRING_TOKEN_SPACING_INVALID: remove spaces inside token strings",
                        )
                    )

        if line_no in const_literal_lines:
            for content, offset in iter_string_literals(cleaned):
                if not any(ch.isspace() for ch in content):
                    continue
                normalized = "".join(ch for ch in content if not ch.isspace())
                if TOKEN_LIKE_STRING_PATTERN.match(normalized):
                    diagnostics.append(
                        Diagnostic(
                            path=path,
                            line=line_no,
                            col=offset + 1,
                            severity="error",
                            code="SDSL2E5225",
                            message="STRING_TOKEN_SPACING_INVALID: remove spaces inside token strings",
                        )
                    )
    return diagnostics


def rule_enum_string_value_wrapping(lines: list[str], path: str) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    for line_no, _stripped, block_kind, block_depth, cleaned in iter_line_contexts(lines):
        if block_kind != "enum" or block_depth != 1:
            continue
        if "=" not in cleaned:
            continue
        _, value = cleaned.split("=", 1)
        value = value.rstrip().rstrip(",")
        if "\"" not in value and "'" not in value:
            continue
        if re.match(r'^\s*"(?:[^"\\]|\\.)*"\s*$', value) or re.match(
            r"^\s*'(?:[^'\\]|\\.)*'\s*$", value
        ):
            continue
        diagnostics.append(
            Diagnostic(
                path=path,
                line=line_no,
                col=cleaned.find("=") + 1,
                severity="error",
                code="SDSL2E5226",
                message="ENUM_STRING_VALUE_WRAPPING_INVALID: use = \"value\"",
            )
        )
    return diagnostics


def rule_literal_invalid_chars(lines: list[str], path: str) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    const_literal_lines = set(iter_const_literal_lines(lines))
    invalid_chars = {"@", ";", "`", "*"}
    for line_no, stripped, block_kind, block_depth, cleaned in iter_line_contexts(lines):
        expr = None
        expr_start = 0
        if block_kind in {"struct", "interface", "class"} and block_depth == 1:
            if FUNC_HEAD_PATTERN.match(stripped):
                continue
            match = FIELD_DECL_PATTERN.match(cleaned)
            if match and match.group("expr") is not None:
                expr = match.group("expr")
                expr_start = match.start("expr")
        if block_kind is None and cleaned.lstrip().startswith("const "):
            match = CONST_DECL_PATTERN.match(cleaned)
            if match and match.group("expr") is not None:
                expr = match.group("expr")
                expr_start = match.start("expr")
        if expr is not None:
            for segment_text, segment_col in extract_code_segments(expr):
                for index, ch in enumerate(segment_text):
                    if ch in invalid_chars:
                        diagnostics.append(
                            Diagnostic(
                                path=path,
                                line=line_no,
                                col=expr_start + segment_col + index,
                                severity="error",
                                code="SDSL2E5227",
                                message="LITERAL_INVALID_CHAR: remove invalid characters",
                            )
                        )
                        break

        if line_no in const_literal_lines:
            for segment_text, segment_col in extract_code_segments(cleaned):
                for index, ch in enumerate(segment_text):
                    if ch in invalid_chars:
                        diagnostics.append(
                            Diagnostic(
                                path=path,
                                line=line_no,
                                col=segment_col + index,
                                severity="error",
                                code="SDSL2E5227",
                                message="LITERAL_INVALID_CHAR: remove invalid characters",
                            )
                        )
                        break
    return diagnostics


def rule_unquoted_identifier_symbols(lines: list[str], path: str) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    for line_no, stripped, block_kind, block_depth, cleaned in iter_line_contexts(lines):
        if block_kind not in {"struct", "interface", "class"} or block_depth != 1:
            continue
        if not stripped or stripped.startswith(("}", "//", "/*")):
            continue
        if FUNC_HEAD_PATTERN.match(stripped):
            continue
        match = FIELD_DECL_PATTERN.match(cleaned)
        if not match or match.group("expr") is None:
            continue
        expr = match.group("expr")
        expr_clean = expr.strip().rstrip(",")
        if not expr_clean:
            continue
        if any(ch in expr_clean for ch in "{}[]()"):
            continue
        if "\"" in expr_clean or "'" in expr_clean:
            continue
        if any(ch.isspace() for ch in expr_clean):
            continue
        if any(ch.isalpha() for ch in expr_clean) and not IDENTIFIER_ALLOWED_PATTERN.fullmatch(
            expr_clean
        ):
            diagnostics.append(
                Diagnostic(
                    path=path,
                    line=line_no,
                    col=match.start("expr") + 1,
                    severity="error",
                    code="SDSL2E5234",
                    message="IDENTIFIER_LITERAL_INVALID_SYMBOL: use letters/digits/_ only",
                )
            )
    return diagnostics


def rule_const_literal_identifier_tokens(lines: list[str], path: str) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    const_literal_lines = set(iter_const_literal_lines(lines))
    list_depth = 0

    for line_no, line in enumerate(lines, start=1):
        if line_no not in const_literal_lines:
            continue
        cleaned = strip_inline_comments(line)
        if not cleaned.strip():
            continue

        delta, has_open_bracket = _count_square_bracket_delta(cleaned)
        inside_list = list_depth > 0 or has_open_bracket

        key_part = None
        value_part = cleaned
        if ":" in cleaned:
            key_part, value_part = cleaned.split(":", 1)
            key_token = key_part.strip().strip("{[(").strip()
            if key_token and IDENTIFIER_PATTERN.match(key_token):
                if is_mixed_case(key_token):
                    diagnostics.append(
                        Diagnostic(
                            path=path,
                            line=line_no,
                            col=cleaned.find(key_token) + 1,
                            severity="error",
                            code="SDSL2E5229",
                            message="LITERAL_KEY_MIXED_CASE: remove mixed-case token",
                        )
                    )

        list_has_identifier = False
        numeric_tokens: list[tuple[int, int]] = []

        for segment_text, segment_col in extract_code_segments(value_part):
            for token in segment_text.split(","):
                candidate_raw = token.strip()
                if not candidate_raw:
                    continue
                if any(ch.isspace() for ch in candidate_raw):
                    if any(sym in candidate_raw for sym in (":", "{", "}", "[", "]", "(", ")")):
                        continue
                    diagnostics.append(
                        Diagnostic(
                            path=path,
                            line=line_no,
                            col=segment_col + segment_text.find(candidate_raw),
                            severity="error",
                            code="SDSL2E5231",
                            message="LITERAL_TOKEN_WHITESPACE_INVALID: add commas or remove spaces",
                        )
                    )
                    continue
                candidate = candidate_raw.strip("[]{}()")
                if not candidate:
                    continue
                if candidate in {"T", "F", "None"}:
                    continue
                if "{" in candidate_raw or "}" in candidate_raw:
                    continue
                if candidate.isdigit():
                    if inside_list:
                        numeric_tokens.append(
                            (segment_col + segment_text.find(candidate), len(candidate))
                        )
                    continue
                if IDENTIFIER_PATTERN.match(candidate):
                    if inside_list:
                        list_has_identifier = True
                    if is_mixed_case(candidate):
                        diagnostics.append(
                            Diagnostic(
                                path=path,
                                line=line_no,
                                col=segment_col + segment_text.find(candidate),
                                severity="error",
                                code="SDSL2E5228",
                                message="LITERAL_TOKEN_MIXED_CASE: remove mixed-case token",
                            )
                        )
                    elif LOWER_ONLY_IDENTIFIER_PATTERN.match(candidate):
                        diagnostics.append(
                            Diagnostic(
                                path=path,
                                line=line_no,
                                col=segment_col + segment_text.find(candidate),
                                severity="error",
                                code="SDSL2E5230",
                                message="LITERAL_TOKEN_LOWERCASE_FORBIDDEN: use UPPER_SNAKE tokens",
                            )
                        )
        if inside_list and list_has_identifier:
            for col, _length in numeric_tokens:
                diagnostics.append(
                    Diagnostic(
                        path=path,
                        line=line_no,
                        col=col,
                        severity="error",
                        code="SDSL2E5208",
                        message="NUMERIC_LITERAL_INVALID: remove stray numbers from identifier lists",
                    )
                )
        list_depth += delta
        if list_depth < 0:
            list_depth = 0
    return diagnostics


def _count_square_bracket_delta(line: str) -> tuple[int, bool]:
    delta = 0
    has_open = False
    in_string: str | None = None
    escape = False
    for ch in line:
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == in_string:
                in_string = None
            continue
        if ch in ("\"", "'"):
            in_string = ch
            continue
        if ch == "[":
            delta += 1
            has_open = True
        elif ch == "]":
            delta -= 1
    return delta, has_open
