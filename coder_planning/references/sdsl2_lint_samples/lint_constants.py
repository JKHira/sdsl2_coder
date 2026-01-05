from __future__ import annotations

import re

TYPE_FORBIDDEN_PATTERNS = [
    (re.compile(r"\bany\b"), "SDSL2E5001"),
    (re.compile(r"\btuple\s*\["), "SDSL2E5002"),
    (re.compile(r"\bd\s*<"), "SDSL2E5003"),
    (re.compile(r"\bList\s*\["), "SDSL2E5002"),
    (re.compile(r"\bDict\s*\["), "SDSL2E5002"),
    (re.compile(r"\bMap\s*\["), "SDSL2E5002"),
    (re.compile(r"^\s*\[[^\]]+\]"), "SDSL2E5002"),
    (re.compile(r"\bdatetime\b"), "SDSL2E5206"),
]

LITERAL_FORBIDDEN_PATTERNS = [
    (re.compile(r"\btrue\b"), "SDSL2E5101"),
    (re.compile(r"\bfalse\b"), "SDSL2E5101"),
    (re.compile(r"\bnull\b"), "SDSL2E5101"),
]

TODO_STRING_IN_CONST_PATTERN = re.compile(
    r'\bconst\s+[A-Za-z_][A-Za-z0-9_]*\s*:\s*s\?\s*=\s*(?P<todo>"(?i:todo)")'
)
OPTIONAL_MARKER_PATTERN = re.compile(r"\b[A-Za-z_][A-Za-z0-9_]*\?\s*:")
STRUCT_HEAD_PARAMS_PATTERN = re.compile(r"^\s*struct\s+[A-Za-z_][A-Za-z0-9_]*\s*\(")
NON_DETERMINISTIC_DEFAULT_PATTERN = re.compile(
    r"^\s*[A-Za-z_][A-Za-z0-9_]*\s*:\s*[^=]+?=\s*(uuid4|utcnow|field)\s*\("
)
BLOCK_HEAD_PATTERN = re.compile(
    r"^\s*(struct|enum|interface|class|C)\s+[A-Za-z_][A-Za-z0-9_]*\b"
)
CONST_TYPE_PATTERN = re.compile(
    r"^\s*const\s+[A-Za-z_][A-Za-z0-9_]*\s*:\s*(?P<type>[^=]+)"
)
FIELD_TYPE_PATTERN = re.compile(
    r"^\s*[A-Za-z_][A-Za-z0-9_]*\s*:\s*(?P<type>[^=]+)"
)
FUNC_HEAD_PATTERN = re.compile(r"^\s*(async\s+)?f\b")
SPREAD_LITERAL_PATTERN = re.compile(r"(\[\s*\.\.|,\s*\.\.)")
IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
FIELD_DECL_PATTERN = re.compile(
    r"^\s*(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*:\s*(?P<type>[^=]*?)(?:=\s*(?P<expr>.*))?$"
)
CONST_DECL_PATTERN = re.compile(
    r"^\s*const\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*:\s*(?P<type>[^=]*?)(?:=\s*(?P<expr>.*))?$"
)
TYPE_SPACED_IDENT_PATTERN = re.compile(
    r"[A-Za-z_][A-Za-z0-9_]*\s+[A-Za-z_][A-Za-z0-9_]*"
)
OPTIONAL_MARKER_SPACING_PATTERN = re.compile(r"\s+\?")
NUMERIC_TRAILING_ALPHA_PATTERN = re.compile(r"\b\d+(?:\.\d+)?[A-Za-z_]+\b")
NUMERIC_SPACED_DIGITS_PATTERN = re.compile(r"\d\s+\d")
NUMERIC_DOT_SPACING_PATTERN = re.compile(r"\d+\s+\.\d+|\d+\.\s+\d+")
TYPE_INVALID_CHAR_PATTERN = re.compile(r"[^A-Za-z0-9_\[\]\(\),\.?\s]")
INVALID_META_KEY_SPACING_PATTERN = re.compile(
    r"\b[A-Za-z_][A-Za-z0-9_]*\s+[A-Za-z_][A-Za-z0-9_]*\s*:"
)
INVALID_LITERAL_TOKEN_PATTERN = re.compile(
    r"\b[A-Za-z_][A-Za-z0-9_]*\s+[A-Za-z_][A-Za-z0-9_]*\b"
)
DECL_HEAD_PATTERN = re.compile(r"^\s*(struct|enum|interface|class|C)\s+(?P<rest>.+)$")
CONST_HEAD_PATTERN = re.compile(r"^\s*const\s+(?P<rest>.+)$")
TOKEN_LIKE_STRING_PATTERN = re.compile(r"^(?:[A-Z0-9_]+|[a-z0-9_]+)$")
LOWER_ONLY_IDENTIFIER_PATTERN = re.compile(r"^[a-z_][a-z0-9_]*$")

CONTRACT_TOKEN_FINDER = re.compile(r"CONTRACT\\.[A-Za-z0-9_.]+")
SSOT_TOKEN_FINDER = re.compile(r"SSOT\\.[A-Za-z0-9_.]+")
