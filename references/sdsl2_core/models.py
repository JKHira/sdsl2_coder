from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Diagnostic:
    path: str
    line: int
    col: int
    severity: str
    code: str
    message: str


@dataclass(frozen=True)
class MetaEntry:
    key: str
    value_text: str
    key_line: int
    key_col: int


@dataclass(frozen=True)
class AnnotationBlock:
    kind: str
    start_line: int
    start_col: int
    end_line: int
    meta_text: Optional[str]
    meta_start_line: Optional[int]
    meta_start_col: Optional[int]
    meta_entries: list[MetaEntry]
