from __future__ import annotations

import re

from .config import Config
from .lint_constants import CONTRACT_TOKEN_FINDER, SSOT_TOKEN_FINDER
from .models import AnnotationBlock, Diagnostic


def rule_token_placement(
    annotations: list[AnnotationBlock],
    path: str,
    config: Config,
    profile: str | None,
) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    for ann in annotations:
        if not ann.meta_entries:
            continue
        for entry in ann.meta_entries:
            contract_tokens = list(CONTRACT_TOKEN_FINDER.finditer(entry.value_text))
            ssot_tokens = list(SSOT_TOKEN_FINDER.finditer(entry.value_text))
            if contract_tokens:
                allowed = entry.key in config.contract_token_allowed_fields
                if ann.kind == "Dep" and entry.key == "to":
                    allowed = True
                if not allowed:
                    diagnostics.append(
                        Diagnostic(
                            path=path,
                            line=entry.key_line,
                            col=entry.key_col,
                            severity="error",
                            code="SDSL2E4002",
                            message="CONTRACT_TOKEN_PLACEMENT_VIOLATION: token outside allowed fields. Example: contract:[\"CONTRACT.X\"]",
                        )
                    )
            if ssot_tokens and entry.key not in config.ssot_token_allowed_fields:
                diagnostics.append(
                    Diagnostic(
                        path=path,
                        line=entry.key_line,
                        col=entry.key_col,
                        severity="error",
                        code="SDSL2E4003",
                        message="SSOT_TOKEN_PLACEMENT_VIOLATION: token outside allowed fields. Example: ssot:[\"SSOT.X\"]",
                    )
                )
            if entry.key == "refs" and (contract_tokens or ssot_tokens):
                diagnostics.append(
                    Diagnostic(
                        path=path,
                        line=entry.key_line,
                        col=entry.key_col,
                        severity="error",
                        code="SDSL2E4004",
                        message="REFS_MUST_BE_INTERNAL_REFS_ONLY: tokens forbidden in refs. Example: refs:[@Kind.REL_ID]",
                    )
                )
            if entry.key == "bind" and (contract_tokens or ssot_tokens):
                diagnostics.append(
                    Diagnostic(
                        path=path,
                        line=entry.key_line,
                        col=entry.key_col,
                        severity="error",
                        code="SDSL2E4005",
                        message="BIND_MUST_NOT_CONTAIN_TOKENS: tokens forbidden in bind. Example: bind:@Kind.REL_ID",
                    )
                )
            if re.search(r"@[^\s]*?(CONTRACT\.|SSOT\.)", entry.value_text):
                diagnostics.append(
                    Diagnostic(
                        path=path,
                        line=entry.key_line,
                        col=entry.key_col,
                        severity="error",
                        code="SDSL2E4001",
                        message="TOKEN_IN_REF_IDTOKEN_FORBIDDEN: tokens inside ref id. Example: @Kind.REL_ID",
                    )
                )
    return diagnostics
