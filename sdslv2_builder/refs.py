from __future__ import annotations

import re
from dataclasses import dataclass

RELID_RE = re.compile(r"^[A-Z][A-Z0-9_]{2,63}$")
CONTRACT_TOKEN_RE = re.compile(r"^CONTRACT\.[A-Za-z0-9_.-]+$")
SSOT_TOKEN_RE = re.compile(r"^SSOT\.[A-Za-z0-9_.-]+$")
INTERNAL_REF_KINDS = {
    "File",
    "DocMeta",
    "Structure",
    "Interface",
    "Function",
    "Const",
    "Type",
    "Dep",
    "Rule",
    "Node",
    "Edge",
}
INTERNAL_REF_RE = re.compile(r"^@(?P<kind>[A-Za-z_][A-Za-z0-9_]*)\.(?P<id>[A-Z][A-Z0-9_]{2,63})$")


@dataclass(frozen=True)
class InternalRef:
    kind: str
    rel_id: str
    absolute: bool = False

    def to_string(self) -> str:
        return f"@{self.kind}.{self.rel_id}"


@dataclass(frozen=True)
class ContractRef:
    token: str

    def to_string(self) -> str:
        return self.token


@dataclass(frozen=True)
class SSOTRef:
    token: str

    def to_string(self) -> str:
        return self.token


def parse_internal_ref(value: str) -> InternalRef | None:
    m = INTERNAL_REF_RE.match(value.strip())
    if not m:
        return None
    kind = m.group("kind")
    if kind not in INTERNAL_REF_KINDS:
        return None
    return InternalRef(kind=kind, rel_id=m.group("id"), absolute=False)


def parse_contract_ref(value: str) -> ContractRef | None:
    if not CONTRACT_TOKEN_RE.match(value.strip()):
        return None
    return ContractRef(token=value.strip())


def parse_ssot_ref(value: str) -> SSOTRef | None:
    if not SSOT_TOKEN_RE.match(value.strip()):
        return None
    return SSOTRef(token=value.strip())
