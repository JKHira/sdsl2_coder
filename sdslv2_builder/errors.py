from __future__ import annotations

from dataclasses import dataclass


def _escape_json_pointer_segment(segment: str) -> str:
    return segment.replace("~", "~0").replace("/", "~1")


def json_pointer(*segments: str) -> str:
    if not segments:
        return ""
    return "/" + "/".join(_escape_json_pointer_segment(s) for s in segments)


@dataclass(frozen=True)
class Diagnostic:
    code: str
    message: str
    expected: str
    got: str
    path: str

    def to_dict(self) -> dict[str, str]:
        return {
            "code": self.code,
            "message": self.message,
            "expected": self.expected,
            "got": self.got,
            "path": self.path,
        }


class BuilderError(Exception):
    def __init__(self, diagnostic: Diagnostic) -> None:
        super().__init__(f"{diagnostic.code}: {diagnostic.message}")
        self.diagnostic = diagnostic
