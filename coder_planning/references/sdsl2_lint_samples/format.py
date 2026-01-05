from __future__ import annotations

import re
from typing import Iterable, Optional

from .config import Config
from .lint import parse_annotations


CANONICAL_META_KEY_ORDER = [
    "profile",
    "id_prefix",
    "id",
    "bind",
    "title",
    "desc",
    "refs",
    "contract",
    "ssot",
    "severity",
]
INDENT_UNIT = "  "


def format_text(text: str, config: Config) -> str:
    _ = config
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    raw_lines = normalized.splitlines(keepends=True)
    lines = [line[:-1] if line.endswith("\n") else line for line in raw_lines]

    annotations, _ = parse_annotations(lines)
    if not annotations:
        return _format_const_literals(normalized)

    line_starts = _line_start_offsets(raw_lines)
    replacements: list[tuple[int, int, str]] = []

    for ann in annotations:
        if not ann.meta_text or ann.meta_start_line is None or ann.meta_start_col is None:
            continue
        base_indent = " " * (ann.start_col - 1)
        formatted = format_metadata_object(
            ann.meta_text,
            base_indent,
            INDENT_UNIT,
            reorder_keys=True,
            value_formatter=format_value_metadata,
        )
        if formatted is None or formatted == ann.meta_text:
            continue

        start_offset = line_starts[ann.meta_start_line - 1] + (ann.meta_start_col - 1)
        end_line, end_col = _meta_end_position(
            ann.meta_text, ann.meta_start_line, ann.meta_start_col
        )
        end_offset = line_starts[end_line - 1] + end_col
        replacements.append((start_offset, end_offset, formatted))

    new_text = normalized
    for start, end, replacement in sorted(replacements, key=lambda item: item[0], reverse=True):
        new_text = new_text[:start] + replacement + new_text[end:]
    new_text = _format_const_literals(new_text)
    new_text = _normalize_spacing_and_indent(new_text)
    return _collapse_blank_lines_top_level(new_text)


def format_metadata_object(
    meta_text: str,
    base_indent: str,
    indent_unit: str,
    *,
    reorder_keys: bool,
    value_formatter,
) -> Optional[str]:
    stripped = meta_text.strip()
    if not (stripped.startswith("{") and stripped.endswith("}")):
        return None

    pairs = parse_metadata_pairs(stripped)
    if pairs is None:
        return None

    formatted_pairs = [
        (key, value_formatter(value, base_indent + indent_unit, indent_unit))
        for key, value in pairs
    ]
    use_multiline = len(formatted_pairs) > 2 or any(
        "\n" in value for _, value in formatted_pairs
    )

    ordered_pairs = _order_pairs(formatted_pairs) if reorder_keys else formatted_pairs

    if not use_multiline:
        inner = ", ".join(f"{key}: {value}" for key, value in ordered_pairs)
        return "{ " + inner + " }"

    lines = ["{"]
    for key, value in ordered_pairs:
        if "\n" in value:
            value_lines = value.splitlines()
            lines.append(f"{base_indent}{indent_unit}{key}: {value_lines[0]}")
            for mid in value_lines[1:-1]:
                lines.append(mid)
            lines.append(f"{value_lines[-1]},")
        else:
            lines.append(f"{base_indent}{indent_unit}{key}: {value},")
    lines.append(f"{base_indent}}}")
    return "\n".join(lines)


def format_value_metadata(value_text: str, base_indent: str, indent_unit: str) -> str:
    trimmed = value_text.strip()
    if trimmed.startswith("{") and trimmed.endswith("}"):
        formatted = format_metadata_object(
            trimmed,
            base_indent,
            indent_unit,
            reorder_keys=True,
            value_formatter=format_value_metadata,
        )
        if formatted is not None:
            return formatted
    if trimmed.startswith("[") and trimmed.endswith("]"):
        formatted = format_array(
            trimmed, base_indent, indent_unit, value_formatter=format_value_metadata
        )
        if formatted is not None:
            return formatted
    return trimmed


def format_value_literal(value_text: str, base_indent: str, indent_unit: str) -> str:
    trimmed = value_text.strip()
    typed_object = _split_typed_object_literal(trimmed)
    if typed_object:
        type_name, object_text = typed_object
        formatted_object = format_metadata_object(
            object_text,
            base_indent,
            indent_unit,
            reorder_keys=False,
            value_formatter=format_value_literal,
        )
        if formatted_object is not None:
            return _attach_type_prefix(type_name, formatted_object)
    if trimmed.startswith("{") and trimmed.endswith("}"):
        formatted = format_metadata_object(
            trimmed,
            base_indent,
            indent_unit,
            reorder_keys=False,
            value_formatter=format_value_literal,
        )
        if formatted is not None:
            return formatted
        formatted = format_literal_object(
            trimmed,
            base_indent,
            indent_unit,
            value_formatter=format_value_literal,
        )
        if formatted is not None:
            return formatted
    if trimmed.startswith("[") and trimmed.endswith("]"):
        formatted = format_array(
            trimmed, base_indent, indent_unit, value_formatter=format_value_literal
        )
        if formatted is not None:
            return formatted
    return trimmed


def _split_typed_object_literal(value_text: str) -> Optional[tuple[str, str]]:
    match = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)\s*(\{.*\})$", value_text, re.DOTALL)
    if not match:
        return None
    return match.group(1), match.group(2)


def _attach_type_prefix(type_name: str, formatted_object: str) -> str:
    if "\n" not in formatted_object:
        return f"{type_name}{formatted_object}"
    lines = formatted_object.splitlines()
    lines[0] = f"{type_name}{lines[0]}"
    return "\n".join(lines)


def format_literal_object(
    obj_text: str,
    base_indent: str,
    indent_unit: str,
    *,
    value_formatter,
) -> Optional[str]:
    stripped = obj_text.strip()
    if not (stripped.startswith("{") and stripped.endswith("}")):
        return None
    pairs = parse_literal_pairs(stripped)
    if pairs is None:
        return None

    formatted_pairs = [
        (key, value_formatter(value, base_indent + indent_unit, indent_unit))
        for key, value in pairs
    ]
    use_multiline = len(formatted_pairs) > 2 or any(
        "\n" in value for _, value in formatted_pairs
    )

    if not use_multiline:
        inner = ", ".join(f"{key}: {value}" for key, value in formatted_pairs)
        return "{ " + inner + " }"

    lines = ["{"]
    for key, value in formatted_pairs:
        if "\n" in value:
            value_lines = value.splitlines()
            lines.append(f"{base_indent}{indent_unit}{key}: {value_lines[0]}")
            for mid in value_lines[1:-1]:
                lines.append(mid)
            lines.append(f"{value_lines[-1]},")
        else:
            lines.append(f"{base_indent}{indent_unit}{key}: {value},")
    lines.append(f"{base_indent}}}")
    return "\n".join(lines)


def parse_literal_pairs(meta_text: str) -> Optional[list[tuple[str, str]]]:
    inner = meta_text.strip()[1:-1]
    entries: list[tuple[str, str]] = []
    index = 0
    depth = 0
    in_string: Optional[str] = None
    escape = False
    key_start: Optional[int] = None
    current_key: Optional[str] = None
    value_start: Optional[int] = None

    def flush_value(end_index: int) -> None:
        nonlocal key_start, current_key, value_start
        if current_key is None or value_start is None:
            return
        value = inner[value_start:end_index].strip()
        entries.append((current_key, value))
        key_start = None
        current_key = None
        value_start = None

    while index < len(inner):
        ch = inner[index]
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
            in_string = ch
            index += 1
            continue

        if ch in "{[(":
            depth += 1
        elif ch in "]})":
            depth = max(depth - 1, 0)

        if depth == 0:
            if current_key is None:
                if ch.isspace() or ch == ",":
                    index += 1
                    continue
                if key_start is None:
                    key_start = index
                if ch == ":":
                    key = inner[key_start:index].strip()
                    if not key:
                        return None
                    current_key = key
                    value_start = index + 1
            else:
                if ch == ",":
                    flush_value(index)
        index += 1

    if current_key is not None and value_start is not None:
        flush_value(len(inner))
    if key_start is not None and current_key is None:
        return None
    return entries


def format_array(
    value_text: str, base_indent: str, indent_unit: str, *, value_formatter
) -> Optional[str]:
    stripped = value_text.strip()
    if not (stripped.startswith("[") and stripped.endswith("]")):
        return None
    elements = parse_array_elements(stripped)
    if elements is None:
        return None
    formatted_elements = [
        value_formatter(element, base_indent + indent_unit, indent_unit)
        for element in elements
    ]
    use_multiline = len(formatted_elements) > 1 or any(
        "\n" in value for value in formatted_elements
    )
    if not use_multiline:
        inner = ", ".join(formatted_elements)
        return "[" + inner + "]"

    lines = ["["]
    for value in formatted_elements:
        if "\n" in value:
            value_lines = value.splitlines()
            lines.append(f"{base_indent}{indent_unit}{value_lines[0]}")
            for mid in value_lines[1:-1]:
                lines.append(mid)
            lines.append(f"{value_lines[-1]},")
        else:
            lines.append(f"{base_indent}{indent_unit}{value},")
    lines.append(f"{base_indent}]")
    return "\n".join(lines)


def parse_metadata_pairs(meta_text: str) -> Optional[list[tuple[str, str]]]:
    inner = meta_text.strip()[1:-1]
    entries: list[tuple[str, str]] = []
    index = 0
    depth = 0
    in_string: Optional[str] = None
    escape = False
    key: Optional[str] = None
    value_start: Optional[int] = None

    def flush_value(end_index: int) -> None:
        nonlocal key, value_start
        if key is None or value_start is None:
            return
        value = inner[value_start:end_index].strip()
        entries.append((key, value))
        key = None
        value_start = None

    while index < len(inner):
        ch = inner[index]
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
            in_string = ch
            index += 1
            continue

        if ch in "{[(":
            depth += 1
        elif ch in "]})":
            depth = max(depth - 1, 0)

        if key is None and depth == 0:
            if ch.isspace() or ch == ",":
                index += 1
                continue
            if ch in ("\"", "'"):
                start = index
                quote = ch
                index += 1
                while index < len(inner):
                    next_ch = inner[index]
                    if next_ch == "\\":
                        index += 2
                        continue
                    if next_ch == quote:
                        index += 1
                        break
                    index += 1
                key = inner[start:index]
                while index < len(inner) and inner[index].isspace():
                    index += 1
                if index >= len(inner) or inner[index] != ":":
                    return None
                value_start = index + 1
                index += 1
                continue
            if ch.isalpha() or ch == "_":
                start = index
                index += 1
                while index < len(inner):
                    next_ch = inner[index]
                    if not (next_ch.isalnum() or next_ch == "_"):
                        break
                    index += 1
                key = inner[start:index]
                while index < len(inner) and inner[index].isspace():
                    index += 1
                if index >= len(inner) or inner[index] != ":":
                    return None
                value_start = index + 1
                index += 1
                continue
        elif key is not None and depth == 0:
            if ch == ",":
                flush_value(index)
                index += 1
                continue

        index += 1

    if key is not None and value_start is not None:
        flush_value(len(inner))

    if not entries and inner.strip():
        return None
    return entries


def parse_array_elements(value_text: str) -> Optional[list[str]]:
    inner = value_text.strip()[1:-1]
    elements: list[str] = []
    index = 0
    depth = 0
    in_string: Optional[str] = None
    escape = False
    elem_start = 0

    def flush_element(end_index: int) -> None:
        value = inner[elem_start:end_index].strip()
        if value:
            elements.append(value)

    while index < len(inner):
        ch = inner[index]
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
            in_string = ch
            index += 1
            continue

        if ch in "{[(":
            depth += 1
        elif ch in "]})":
            depth = max(depth - 1, 0)

        if depth == 0 and ch == ",":
            flush_element(index)
            index += 1
            elem_start = index
            continue

        index += 1

    flush_element(len(inner))
    return elements


def _format_const_literals(text: str) -> str:
    raw_lines = text.splitlines(keepends=True)
    lines = [line[:-1] if line.endswith("\n") else line for line in raw_lines]
    line_starts = _line_start_offsets(raw_lines)
    replacements: list[tuple[int, int, str]] = []

    for line_index, line in enumerate(lines):
        stripped = line.lstrip()
        if not stripped.startswith("const "):
            continue
        eq_index = line.find("=")
        if eq_index == -1:
            continue
        expr_start_in_line = _first_non_space(line, eq_index + 1)
        if expr_start_in_line is None:
            continue
        open_char = line[expr_start_in_line]
        if open_char not in "{[":
            continue
        close_char = "}" if open_char == "{" else "]"
        start_offset = line_starts[line_index] + expr_start_in_line
        end_offset = _capture_balanced(text, start_offset, open_char, close_char)
        if end_offset is None:
            continue
        expr_text = text[start_offset : end_offset + 1]
        base_indent = line[: len(line) - len(stripped)]
        formatted = format_value_literal(expr_text, base_indent, INDENT_UNIT)
        if formatted == expr_text:
            continue
        replacements.append((start_offset, end_offset + 1, formatted))

    if not replacements:
        return text
    new_text = text
    for start, end, replacement in sorted(replacements, key=lambda item: item[0], reverse=True):
        new_text = new_text[:start] + replacement + new_text[end:]
    return new_text


def _collapse_blank_lines_top_level(text: str) -> str:
    lines = text.splitlines(keepends=True)
    if not lines:
        return text
    output: list[str] = []
    blank_streak = 0
    depth = 0
    in_block_comment = False
    in_string: Optional[str] = None
    escape = False
    for line in lines:
        stripped = line.strip()
        is_blank = stripped == ""
        if depth == 0 and not in_block_comment and is_blank:
            blank_streak += 1
            if blank_streak > 1:
                depth, in_block_comment, in_string, escape = _scan_depth(
                    line, depth, in_block_comment, in_string, escape
                )
                continue
        else:
            blank_streak = 0
        output.append(line)
        depth, in_block_comment, in_string, escape = _scan_depth(
            line, depth, in_block_comment, in_string, escape
        )
    return "".join(output)


DECL_BLOCK_HEAD_RE = re.compile(r"^\s*(struct|enum|interface|class|C)\s+[A-Za-z_][A-Za-z0-9_]*\b")
FUNC_LINE_RE = re.compile(r"^(async\s+)?f\s+[A-Za-z_][A-Za-z0-9_]*")
FIELD_LINE_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*\s*:")
CONST_LINE_RE = re.compile(r"^const\s+[A-Za-z_][A-Za-z0-9_]*\s*:")


def _normalize_spacing_and_indent(text: str) -> str:
    lines = text.splitlines(keepends=True)
    if not lines:
        return text

    output: list[str] = []
    block_depth = 0

    for line in lines:
        newline = "\n" if line.endswith("\n") else ""
        raw = line[:-1] if line.endswith("\n") else line
        stripped = raw.lstrip()

        is_block_head = bool(DECL_BLOCK_HEAD_RE.match(stripped) and "{" in stripped)
        brace_delta = _brace_delta(raw)

        if block_depth > 0 and block_depth == 1:
            if stripped.startswith("}"):
                indent = INDENT_UNIT * (block_depth - 1)
            else:
                indent = INDENT_UNIT * block_depth
            normalized = _normalize_decl_body_line(stripped, indent)
            output.append(normalized + newline)
        else:
            normalized = raw
            if block_depth == 0 and FUNC_LINE_RE.match(stripped):
                normalized = _normalize_function_line(stripped)
            output.append(normalized + newline)

        if block_depth > 0 or is_block_head:
            block_depth += brace_delta
            if block_depth <= 0:
                block_depth = 0

    return "".join(output)


def _normalize_decl_body_line(stripped: str, indent: str) -> str:
    if stripped == "":
        return ""
    if stripped.startswith(("//", "/*")):
        return indent + stripped
    if FUNC_LINE_RE.match(stripped):
        code, comment = _split_inline_comment(stripped)
        normalized = _normalize_function_line(code)
        return _join_comment(indent + normalized, comment)
    if CONST_LINE_RE.match(stripped):
        code, comment = _split_inline_comment(stripped)
        normalized = _normalize_const_line(code)
        return _join_comment(indent + normalized, comment)
    if FIELD_LINE_RE.match(stripped):
        code, comment = _split_inline_comment(stripped)
        normalized = _normalize_field_line(code)
        return _join_comment(indent + normalized, comment)
    return indent + stripped


def _normalize_function_line(code: str) -> str:
    match = re.match(r"^(async\s+)?f\s+([A-Za-z_][A-Za-z0-9_]*)", code)
    if not match:
        return code.strip()
    prefix = "async f " if match.group(1) else "f "
    name = match.group(2)
    rest = code[match.end() :].lstrip()
    normalized = prefix + name + rest
    normalized = _normalize_operator_spacing(normalized)
    return normalized.strip()


def _normalize_const_line(code: str) -> str:
    match = re.match(r"^const\s+([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(.+)$", code)
    if not match:
        return code.strip()
    name = match.group(1)
    tail = match.group(2)
    type_part, value_part = _split_first_equal(tail)
    type_text = type_part.strip()
    if value_part is None:
        return f"const {name}: {type_text}".strip()
    return f"const {name}: {type_text} = {value_part.strip()}".strip()


def _normalize_field_line(code: str) -> str:
    match = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(.+)$", code)
    if not match:
        return code.strip()
    name = match.group(1)
    tail = match.group(2)
    type_part, value_part = _split_first_equal(tail)
    type_text = type_part.strip()
    if value_part is None:
        return f"{name}: {type_text}".strip()
    return f"{name}: {type_text} = {value_part.strip()}".strip()


def _normalize_operator_spacing(code: str) -> str:
    return _normalize_operator(_normalize_operator(code, "->"), "=")


def _normalize_operator(text: str, op: str) -> str:
    output: list[str] = []
    index = 0
    in_string: Optional[str] = None
    escape = False
    in_block = False

    while index < len(text):
        ch = text[index]
        next_two = text[index : index + 2]
        if in_block:
            if next_two == "*/":
                in_block = False
                output.append(next_two)
                index += 2
                continue
            output.append(ch)
            index += 1
            continue
        if in_string:
            output.append(ch)
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == in_string:
                in_string = None
            index += 1
            continue
        if next_two == "//":
            output.append(text[index:])
            break
        if next_two == "/*":
            in_block = True
            output.append(next_two)
            index += 2
            continue
        if ch in ("\"", "'"):
            in_string = ch
            output.append(ch)
            index += 1
            continue

        if op == "->" and next_two == "->":
            while output and output[-1].endswith(" "):
                output[-1] = output[-1].rstrip(" ")
                if output[-1]:
                    break
                output.pop()
            output.append(" -> ")
            index += 2
            while index < len(text) and text[index].isspace():
                index += 1
            continue

        if op == "=" and ch == "=":
            prev = text[index - 1] if index > 0 else ""
            nxt = text[index + 1] if index + 1 < len(text) else ""
            if prev in "=<>!" or nxt == "=":
                output.append(ch)
                index += 1
                continue
            while output and output[-1].endswith(" "):
                output[-1] = output[-1].rstrip(" ")
                if output[-1]:
                    break
                output.pop()
            output.append(" = ")
            index += 1
            while index < len(text) and text[index].isspace():
                index += 1
            continue

        output.append(ch)
        index += 1

    return "".join(output)


def _split_inline_comment(line: str) -> tuple[str, str]:
    index = 0
    in_string: Optional[str] = None
    escape = False
    while index < len(line):
        ch = line[index]
        next_two = line[index : index + 2]
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
            return line[:index].rstrip(), line[index:]
        if ch in ("\"", "'"):
            in_string = ch
        index += 1
    return line.rstrip(), ""


def _split_first_equal(text: str) -> tuple[str, Optional[str]]:
    index = 0
    in_string: Optional[str] = None
    escape = False
    while index < len(text):
        ch = text[index]
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
            in_string = ch
            index += 1
            continue
        if ch == "=":
            return text[:index], text[index + 1 :]
        index += 1
    return text, None


def _join_comment(code: str, comment: str) -> str:
    if not comment:
        return code
    return f"{code} {comment.lstrip()}"


def _brace_delta(line: str) -> int:
    depth = 0
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
        if ch in ("\"", "'", "`"):
            in_string = ch
            index += 1
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
        index += 1
    return depth


def _scan_depth(
    line: str,
    depth: int,
    in_block_comment: bool,
    in_string: Optional[str],
    escape: bool,
) -> tuple[int, bool, Optional[str], bool]:
    index = 0
    in_line_comment = False
    while index < len(line):
        ch = line[index]
        next_two = line[index : index + 2]
        if in_line_comment:
            break
        if in_block_comment:
            if next_two == "*/":
                in_block_comment = False
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
            in_line_comment = True
            break
        if next_two == "/*":
            in_block_comment = True
            index += 2
            continue
        if ch in ("\"", "'", "`"):
            in_string = ch
            index += 1
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth = max(depth - 1, 0)
        index += 1
    return depth, in_block_comment, in_string, escape


def _first_non_space(line: str, start: int) -> Optional[int]:
    for index in range(start, len(line)):
        if not line[index].isspace():
            return index
    return None


def _capture_balanced(
    text: str, start_index: int, open_char: str, close_char: str
) -> Optional[int]:
    depth = 0
    in_string: Optional[str] = None
    escape = False
    in_line_comment = False
    in_block_comment = False
    index = start_index
    while index < len(text):
        ch = text[index]
        next_two = text[index : index + 2]
        if in_line_comment:
            if ch == "\n":
                in_line_comment = False
            index += 1
            continue
        if in_block_comment:
            if next_two == "*/":
                in_block_comment = False
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
            in_line_comment = True
            index += 2
            continue
        if next_two == "/*":
            in_block_comment = True
            index += 2
            continue
        if ch in ("\"", "'", "`"):
            in_string = ch
            index += 1
            continue
        if ch == open_char:
            depth += 1
        elif ch == close_char:
            depth -= 1
            if depth == 0:
                return index
        index += 1
    return None


def _order_pairs(pairs: Iterable[tuple[str, str]]) -> list[tuple[str, str]]:
    rank = {key: index for index, key in enumerate(CANONICAL_META_KEY_ORDER)}
    result = []
    for index, (key, value) in enumerate(pairs):
        key_rank = rank.get(key, len(CANONICAL_META_KEY_ORDER))
        sort_key = (key_rank, key if key_rank == len(CANONICAL_META_KEY_ORDER) else "", index)
        result.append((sort_key, (key, value)))
    result.sort(key=lambda item: item[0])
    return [value for _, value in result]


def _line_start_offsets(raw_lines: list[str]) -> list[int]:
    starts: list[int] = []
    offset = 0
    for line in raw_lines:
        starts.append(offset)
        offset += len(line)
    return starts


def _meta_end_position(
    meta_text: str, start_line: int, start_col: int
) -> tuple[int, int]:
    parts = meta_text.splitlines()
    if len(parts) == 1:
        return start_line, start_col + len(parts[0]) - 1
    end_line = start_line + len(parts) - 1
    end_col = len(parts[-1])
    return end_line, end_col
