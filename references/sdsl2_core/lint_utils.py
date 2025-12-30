from __future__ import annotations

from typing import Iterable, Optional

from .lint_constants import (
    BLOCK_HEAD_PATTERN,
    CONST_TYPE_PATTERN,
    FIELD_TYPE_PATTERN,
    FUNC_HEAD_PATTERN,
)


def iter_line_contexts(
    lines: list[str],
) -> Iterable[tuple[int, str, Optional[str], int, str]]:
    block_kind: Optional[str] = None
    block_depth = 0
    for line_no, line in enumerate(lines, start=1):
        cleaned = strip_inline_comments(line)
        stripped = cleaned.lstrip()
        brace_delta = count_brace_delta(cleaned)

        yield line_no, stripped, block_kind, block_depth, cleaned

        if block_kind is None:
            head_match = BLOCK_HEAD_PATTERN.match(cleaned)
            if head_match and "{" in cleaned and brace_delta > 0:
                block_kind = head_match.group(1)
                block_depth = brace_delta
            continue

        block_depth += brace_delta
        if block_depth <= 0:
            block_kind = None
            block_depth = 0


def strip_inline_comments(line: str) -> str:
    result = []
    index = 0
    in_string: Optional[str] = None
    escape = False
    in_block = False
    while index < len(line):
        ch = line[index]
        next_two = line[index : index + 2]
        if in_block:
            if next_two == "*/":
                in_block = False
                index += 2
                continue
            index += 1
            continue
        if in_string:
            result.append(ch)
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == in_string:
                in_string = None
            index += 1
            continue
        if next_two == "//":
            break
        if next_two == "/*":
            in_block = True
            index += 2
            continue
        if ch in ("\"", "'"):
            in_string = ch
            result.append(ch)
            index += 1
            continue
        result.append(ch)
        index += 1
    return "".join(result)


def count_brace_delta(line: str) -> int:
    delta = 0
    index = 0
    in_string: Optional[str] = None
    escape = False
    in_block = False
    while index < len(line):
        ch = line[index]
        next_two = line[index : index + 2]
        if in_block:
            if next_two == "*/":
                in_block = False
                index += 2
                continue
            index += 1
            continue
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == in_string:
                in_string = None
            index += 1
            continue
        if next_two == "//":
            break
        if next_two == "/*":
            in_block = True
            index += 2
            continue
        if ch in ("\"", "'"):
            in_string = ch
            index += 1
            continue
        if ch == "{":
            delta += 1
        elif ch == "}":
            delta -= 1
        index += 1
    return delta


def count_bracket_delta(line: str) -> int:
    delta = 0
    index = 0
    in_string: Optional[str] = None
    escape = False
    in_block = False
    while index < len(line):
        ch = line[index]
        next_two = line[index : index + 2]
        if in_block:
            if next_two == "*/":
                in_block = False
                index += 2
                continue
            index += 1
            continue
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == in_string:
                in_string = None
            index += 1
            continue
        if next_two == "//":
            break
        if next_two == "/*":
            in_block = True
            index += 2
            continue
        if ch in ("\"", "'"):
            in_string = ch
            index += 1
            continue
        if ch == "[":
            delta += 1
        elif ch == "]":
            delta -= 1
        index += 1
    return delta


def normalize_type_region(type_text: str, base_col: int) -> tuple[str, int]:
    leading = len(type_text) - len(type_text.lstrip())
    return type_text.lstrip().rstrip(), base_col + leading


def extract_return_type(line: str) -> Optional[tuple[str, int]]:
    arrow_index = line.find("->")
    if arrow_index == -1:
        return None
    after = line[arrow_index + 2 :]
    if not after.strip():
        return None
    trimmed = after.split("{", 1)[0].split("=", 1)[0].strip()
    if not trimmed:
        return None
    leading = len(after) - len(after.lstrip())
    col = arrow_index + 2 + leading + 1
    return trimmed, col


def extract_param_list(line: str) -> Optional[str]:
    start = line.find("(")
    if start == -1:
        return None
    depth = 0
    in_string: Optional[str] = None
    escape = False
    for index in range(start, len(line)):
        ch = line[index]
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
        if ch == "(":
            depth += 1
            continue
        if ch == ")":
            depth -= 1
            if depth == 0:
                return line[start + 1 : index]
    return None


def iter_type_regions(lines: list[str]) -> Iterable[tuple[int, int, str]]:
    block_depth = 0
    for line_no, line in enumerate(lines, start=1):
        cleaned = strip_inline_comments(line)
        stripped = cleaned.lstrip()
        brace_delta = count_brace_delta(cleaned)

        is_block_header = False
        if block_depth == 0 and BLOCK_HEAD_PATTERN.match(cleaned) and "{" in cleaned:
            is_block_header = True

        const_match = CONST_TYPE_PATTERN.search(cleaned)
        if const_match:
            type_text, col = normalize_type_region(
                const_match.group("type"), const_match.start("type") + 1
            )
            if type_text:
                yield line_no, col, type_text

        if FUNC_HEAD_PATTERN.match(cleaned):
            return_type = extract_return_type(cleaned)
            if return_type:
                type_text, col = return_type
                yield line_no, col, type_text

        if block_depth == 1 and not is_block_header:
            if stripped and not stripped.startswith(
                (
                    "}",
                    "f ",
                    "async f",
                    "enum ",
                    "struct ",
                    "interface ",
                    "class ",
                    "const ",
                )
            ):
                field_match = FIELD_TYPE_PATTERN.search(cleaned)
                if field_match:
                    type_text, col = normalize_type_region(
                        field_match.group("type"), field_match.start("type") + 1
                    )
                    if type_text:
                        yield line_no, col, type_text

        if block_depth > 0 or is_block_header:
            block_depth += brace_delta
            if block_depth <= 0:
                block_depth = 0


def extract_code_segments(line: str) -> list[tuple[str, int]]:
    segments: list[tuple[str, int]] = []
    current = ""
    start_col = 1
    in_string: Optional[str] = None
    escape = False
    index = 0

    while index < len(line):
        ch = line[index]
        next_two = line[index : index + 2]
        if not in_string and next_two == "//":
            if current:
                segments.append((current, start_col))
            return segments

        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == in_string:
                in_string = None
            index += 1
            continue

        if ch in ("\"", "'"):
            if current:
                segments.append((current, start_col))
                current = ""
            in_string = ch
            index += 1
            start_col = index + 1
            continue

        if not current:
            start_col = index + 1
        current += ch
        index += 1

    if current:
        segments.append((current, start_col))
    return segments


def has_single_quoted_string(line: str) -> bool:
    in_double = False
    escape = False
    for ch in line:
        if in_double:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == "\"":
                in_double = False
            continue
        if ch == "\"":
            in_double = True
            continue
        if ch == "'":
            return True
    return False


def find_single_quote_col(line: str) -> Optional[int]:
    in_double = False
    escape = False
    for index, ch in enumerate(line):
        if in_double:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == "\"":
                in_double = False
            continue
        if ch == "\"":
            in_double = True
            continue
        if ch == "'":
            return index + 1
    return None


def iter_const_literal_lines(lines: list[str]) -> Iterable[int]:
    in_const_literal = False
    literal_depth = 0
    for line_no, line in enumerate(lines, start=1):
        cleaned = strip_inline_comments(line)
        if not in_const_literal:
            if cleaned.lstrip().startswith("const ") and "=" in cleaned:
                eq_index = cleaned.find("=")
                rhs = cleaned[eq_index + 1 :]
                rhs_strip = rhs.lstrip()
                if rhs_strip.startswith(("{", "[")):
                    in_const_literal = True
                    literal_depth = count_brace_delta(rhs_strip) + count_bracket_delta(rhs_strip)
                    continue
        else:
            yield line_no
            literal_depth += count_brace_delta(cleaned) + count_bracket_delta(cleaned)
            if literal_depth <= 0:
                in_const_literal = False
                literal_depth = 0


def iter_string_literals(text: str) -> Iterable[tuple[str, int]]:
    index = 0
    in_string: Optional[str] = None
    escape = False
    start = 0
    while index < len(text):
        ch = text[index]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == in_string:
                yield text[start + 1 : index], start + 2
                in_string = None
            index += 1
            continue
        if ch in ("\"", "'"):
            in_string = ch
            start = index
        index += 1


def is_mixed_case(token: str) -> bool:
    return any(ch.islower() for ch in token) and any(ch.isupper() for ch in token)
