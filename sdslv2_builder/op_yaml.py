from __future__ import annotations

from pathlib import Path
from typing import Any
import re


def _parse_scalar(value: str) -> Any:
    value = value.strip()
    if value == "null":
        return None
    if value == "true":
        return True
    if value == "false":
        return False
    if value == "[]":
        return []
    if value == "{}":
        return {}
    if len(value) >= 2 and value[0] == value[-1] == '"':
        return value[1:-1].replace(r"\\", "\\").replace(r"\"", '"')
    if re.match(r"^-?\d+$", value):
        return int(value)
    if re.match(r"^-?\d+\.\d+$", value):
        return float(value)
    return value


def _count_indent(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def _parse_block(lines: list[str], start: int, indent: int) -> tuple[Any, int]:
    i = start
    block_type = None
    items: list[Any] = []
    mapping: dict[str, Any] = {}

    while i < len(lines):
        line = lines[i]
        if line.strip() == "":
            i += 1
            continue
        cur_indent = _count_indent(line)
        if cur_indent < indent:
            break
        if cur_indent > indent:
            raise ValueError(f"YAML_INDENT_ERROR:{i + 1}")
        content = line[cur_indent:]
        if content.startswith("-"):
            if block_type is None:
                block_type = "list"
            if block_type != "list":
                raise ValueError(f"YAML_MIXED_BLOCK:{i + 1}")
            rest = content[1:].lstrip()
            if rest == "":
                value, i = _parse_block(lines, i + 1, indent + 2)
            else:
                if ":" in rest:
                    key, tail = rest.split(":", 1)
                    key = key.strip()
                    tail = tail.lstrip()
                    if not key:
                        raise ValueError(f"YAML_MISSING_KEY:{i + 1}")
                    value = {}
                    if tail == "":
                        nested, i = _parse_block(lines, i + 1, indent + 2)
                        value[key] = nested
                    else:
                        value[key] = _parse_scalar(tail)
                        i += 1

                    probe = i
                    while probe < len(lines) and lines[probe].strip() == "":
                        probe += 1
                    if probe < len(lines):
                        probe_indent = _count_indent(lines[probe])
                        if probe_indent == indent + 2 and not lines[probe].lstrip().startswith("-"):
                            extra, i = _parse_block(lines, probe, indent + 2)
                            if not isinstance(extra, dict):
                                raise ValueError(f"YAML_LIST_ITEM_NOT_DICT:{probe + 1}")
                            value.update(extra)
                        elif probe_indent > indent and lines[probe].lstrip().startswith("-"):
                            raise ValueError(f"YAML_UNSUPPORTED_LIST_ITEM:{probe + 1}")
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
            raise ValueError(f"YAML_MIXED_BLOCK:{i + 1}")
        if ":" not in content:
            raise ValueError(f"YAML_MISSING_COLON:{i + 1}")
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


def load_yaml(path: Path) -> Any:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        import json

        return json.loads(text)
    lines = text.splitlines()
    data, _ = _parse_block(lines, 0, 0)
    return data


def _needs_quotes(value: str) -> bool:
    if value == "":
        return True
    if value.startswith("-") or value.startswith("?") or value.startswith(":"):
        return True
    if value.strip() != value:
        return True
    if any(ch in value for ch in [":", "#", "{", "}", "[", "]", ",", "\n", "\t"]):
        return True
    if value in {"null", "true", "false", "[]", "{}"}:
        return True
    if re.match(r"^-?\d+(\.\d+)?$", value):
        return True
    return False


def _dump_scalar(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        if _needs_quotes(value):
            escaped = value.replace("\\", "\\\\").replace('"', '\\"')
            return f'"{escaped}"'
        return value
    raise TypeError(f"Unsupported scalar: {type(value).__name__}")


def dump_yaml(data: Any, indent: int = 0) -> str:
    lines: list[str] = []

    def emit(value: Any, level: int) -> None:
        prefix = " " * level
        if isinstance(value, dict):
            for key, val in value.items():
                if isinstance(val, (dict, list)):
                    lines.append(f"{prefix}{key}:")
                    emit(val, level + 2)
                else:
                    lines.append(f"{prefix}{key}: {_dump_scalar(val)}")
            return
        if isinstance(value, list):
            if not value:
                lines.append(f"{prefix}[]")
                return
            for item in value:
                if isinstance(item, (dict, list)):
                    lines.append(f"{prefix}-")
                    emit(item, level + 2)
                else:
                    lines.append(f"{prefix}- {_dump_scalar(item)}")
            return
        lines.append(f"{prefix}{_dump_scalar(value)}")

    emit(data, indent)
    return "\n".join(lines) + "\n"
