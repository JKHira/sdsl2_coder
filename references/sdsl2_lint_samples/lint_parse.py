from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from .models import AnnotationBlock, MetaEntry


@dataclass(frozen=True)
class StatementGroup:
    annotations: list[AnnotationBlock]
    has_decl: bool
    had_gap: bool


def parse_annotations(lines: list[str]) -> tuple[list[AnnotationBlock], list[str]]:
    annotations: list[AnnotationBlock] = []
    line_kinds = ["blank" for _ in lines]
    in_block_comment = False

    index = 0
    while index < len(lines):
        line = lines[index]
        stripped = line.lstrip()

        if in_block_comment:
            line_kinds[index] = "comment"
            if "*/" in stripped:
                in_block_comment = False
            index += 1
            continue

        if stripped == "":
            line_kinds[index] = "blank"
            index += 1
            continue

        if stripped.startswith("/*"):
            line_kinds[index] = "comment"
            if "*/" not in stripped:
                in_block_comment = True
            index += 1
            continue

        if stripped.startswith("//"):
            line_kinds[index] = "comment"
            index += 1
            continue

        if stripped.startswith("@"):
            kind, kind_end = parse_annotation_kind(stripped)
            start_col = len(line) - len(stripped) + 1
            meta_text, meta_start_line, meta_start_col, end_line = capture_metadata(
                lines, index, len(line) - len(stripped) + kind_end
            )
            meta_entries = (
                parse_metadata_entries(meta_text, meta_start_line, meta_start_col)
                if meta_text
                else []
            )
            annotations.append(
                AnnotationBlock(
                    kind=kind,
                    start_line=index + 1,
                    start_col=start_col,
                    end_line=end_line + 1,
                    meta_text=meta_text,
                    meta_start_line=meta_start_line,
                    meta_start_col=meta_start_col,
                    meta_entries=meta_entries,
                )
            )
            for mark_index in range(index, end_line + 1):
                line_kinds[mark_index] = "annotation"
            index = end_line + 1
            continue

        line_kinds[index] = "statement"
        index += 1

    return annotations, line_kinds


def parse_annotation_kind(stripped: str) -> tuple[str, int]:
    match = re.match(r"@([A-Za-z0-9_.]+)", stripped)
    if not match:
        return "", 1
    return match.group(1), match.end()


def capture_metadata(
    lines: list[str], start_index: int, search_start: int
) -> tuple[Optional[str], Optional[int], Optional[int], int]:
    line = lines[start_index]
    brace_index = line.find("{", search_start)
    if brace_index == -1:
        return None, None, None, start_index

    started = False
    depth = 0
    in_string: Optional[str] = None
    escape = False
    end_line = start_index
    end_col = brace_index

    for line_index in range(start_index, len(lines)):
        line_text = lines[line_index]
        col_index = brace_index if line_index == start_index else 0
        while col_index < len(line_text):
            ch = line_text[col_index]
            if in_string:
                if escape:
                    escape = False
                elif ch == "\\":
                    escape = True
                elif ch == in_string:
                    in_string = None
                col_index += 1
                continue

            if ch in ("\"", "'"):
                in_string = ch
                col_index += 1
                continue

            if ch == "{":
                depth += 1
                started = True
            elif ch == "}":
                depth -= 1
                if started and depth == 0:
                    end_line = line_index
                    end_col = col_index
                    text = extract_meta_text(lines, start_index, brace_index, end_line, end_col)
                    return text, start_index + 1, brace_index + 1, end_line
            col_index += 1

    text = extract_meta_text(lines, start_index, brace_index, end_line, len(lines[end_line]) - 1)
    return text, start_index + 1, brace_index + 1, end_line


def extract_meta_text(
    lines: list[str], start_line: int, start_col: int, end_line: int, end_col: int
) -> str:
    if start_line == end_line:
        return lines[start_line][start_col : end_col + 1]
    chunks = [lines[start_line][start_col:]]
    for index in range(start_line + 1, end_line):
        chunks.append(lines[index])
    chunks.append(lines[end_line][: end_col + 1])
    return "\n".join(chunks)


def parse_metadata_entries(
    meta_text: str, base_line: Optional[int], base_col: Optional[int]
) -> list[MetaEntry]:
    if base_line is None or base_col is None:
        return []
    text = meta_text
    if not (text.startswith("{") and text.endswith("}")):
        return []
    inner = text[1:-1]

    entries: list[MetaEntry] = []
    line = base_line
    col = base_col + 1
    index = 0
    depth = 0
    in_string: Optional[str] = None
    escape = False
    current_key = ""
    key_line = 0
    key_col = 0
    capturing_key = False
    capturing_value = False
    value_start = 0
    value_line = 0
    value_col = 0

    def flush_value(end_index: int) -> None:
        nonlocal current_key, capturing_key, capturing_value, value_start
        nonlocal value_line, value_col
        if not current_key:
            capturing_key = False
            capturing_value = False
            return
        value = inner[value_start:end_index].strip()
        entries.append(
            MetaEntry(
                key=current_key,
                value_text=value,
                key_line=key_line,
                key_col=key_col,
            )
        )
        current_key = ""
        capturing_key = False
        capturing_value = False

    while index < len(inner):
        ch = inner[index]
        if ch == "\n":
            line += 1
            col = 1
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
            col += 1
            continue

        if ch in ("\"", "'"):
            in_string = ch
            index += 1
            col += 1
            continue

        if ch in "[{(":
            depth += 1
        elif ch in "]})":
            depth = max(depth - 1, 0)

        if depth == 0 and not capturing_value:
            if ch.isspace() or ch == ",":
                index += 1
                col += 1
                continue
            if ch.isalpha() or ch == "_":
                capturing_key = True
                current_key = ch
                key_line = line
                key_col = col
                index += 1
                col += 1
                while index < len(inner):
                    next_ch = inner[index]
                    if not (next_ch.isalnum() or next_ch in "_"):
                        break
                    current_key += next_ch
                    index += 1
                    col += 1
                continue
            if ch == ":" and capturing_key:
                capturing_value = True
                value_start = index + 1
                value_line = line
                value_col = col + 1
                index += 1
                col += 1
                continue
        elif depth == 0 and capturing_value:
            if ch == ",":
                flush_value(index)
                index += 1
                col += 1
                continue

        if capturing_key and ch == ":":
            capturing_value = True
            value_start = index + 1
            value_line = line
            value_col = col + 1

        index += 1
        col += 1

    if capturing_value:
        flush_value(len(inner))

    return entries


def group_annotations(
    annotations: list[AnnotationBlock], line_kinds: list[str], total_lines: int
) -> list[StatementGroup]:
    groups: list[StatementGroup] = []
    if not annotations:
        return groups

    annotations_sorted = sorted(annotations, key=lambda ann: ann.start_line)
    current_group: list[AnnotationBlock] = []

    def has_gap(prev_end: int, next_start: int) -> bool:
        for line_no in range(prev_end + 1, min(next_start, total_lines + 1)):
            if line_kinds[line_no - 1] in {"blank", "comment"}:
                return True
        return False

    for ann in annotations_sorted:
        if not current_group:
            current_group.append(ann)
            continue
        prev = current_group[-1]
        if has_gap(prev.end_line, ann.start_line):
            groups.append(StatementGroup(current_group, has_decl=False, had_gap=False))
            current_group = [ann]
        else:
            current_group.append(ann)

    if current_group:
        groups.append(StatementGroup(current_group, has_decl=False, had_gap=False))

    grouped: list[StatementGroup] = []

    for group in groups:
        last_line = group.annotations[-1].end_line
        next_line, next_kind = find_next_non_trivia_line(line_kinds, last_line + 1)
        if next_line is None:
            grouped.append(group)
            continue
        if next_kind != "statement":
            grouped.append(group)
            continue
        gap = has_gap(last_line, next_line)
        grouped.append(StatementGroup(group.annotations, has_decl=True, had_gap=gap))
    return grouped


def find_next_non_trivia_line(
    line_kinds: list[str], start_line: int
) -> tuple[Optional[int], Optional[str]]:
    for index in range(start_line - 1, len(line_kinds)):
        kind = line_kinds[index]
        if kind not in {"blank", "comment"}:
            return index + 1, kind
    return None, None


def find_first_statement_line(lines: list[str]) -> Optional[int]:
    in_block_comment = False
    for index, line in enumerate(lines, start=1):
        stripped = line.lstrip()
        if in_block_comment:
            if "*/" in stripped:
                in_block_comment = False
            continue
        if stripped == "":
            continue
        if stripped.startswith("/*"):
            if "*/" not in stripped:
                in_block_comment = True
            continue
        if stripped.startswith("//"):
            continue
        return index
    return None


def get_file_profile(annotations: list[AnnotationBlock]) -> Optional[str]:
    for ann in annotations:
        if ann.kind != "File":
            continue
        return get_meta_value(ann, "profile")
    return None


def get_file_id_prefix(annotations: list[AnnotationBlock]) -> Optional[str]:
    for ann in annotations:
        if ann.kind != "File":
            continue
        return get_meta_value(ann, "id_prefix")
    return None


def get_meta_value(ann: AnnotationBlock, key: str) -> Optional[str]:
    for entry in ann.meta_entries:
        if entry.key == key:
            return strip_quotes(entry.value_text)
    return None


def metadata_line_numbers(annotations: list[AnnotationBlock]) -> set[int]:
    lines: set[int] = set()
    for ann in annotations:
        if not ann.meta_text or ann.meta_start_line is None:
            continue
        count = len(ann.meta_text.splitlines())
        for line_no in range(ann.meta_start_line, ann.meta_start_line + count):
            lines.add(line_no)
    return lines


def strip_quotes(value: str) -> str:
    stripped = value.strip()
    if stripped.startswith("\"") and stripped.endswith("\"") and len(stripped) >= 2:
        return stripped[1:-1]
    return stripped


import re
