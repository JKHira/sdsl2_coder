from __future__ import annotations

from dataclasses import dataclass

from .errors import BuilderError, Diagnostic, json_pointer
from .refs import ContractRef, InternalRef, SSOTRef


DECL_KINDS = {
    "Structure",
    "Interface",
    "Function",
    "Const",
    "Type",
}


def validate_contract_model_v0_1(model) -> None:
    from .contract import ContractModel, Decl, Dep, Rule  # local import to avoid circulars

    if not isinstance(model, ContractModel):
        raise BuilderError(
            Diagnostic(
                code="E_PROFILE_INVALID",
                message="contract model invalid",
                expected="ContractModel",
                got=type(model).__name__,
                path=json_pointer(),
            )
        )

    for idx, decl in enumerate(model.decls):
        if not isinstance(decl, Decl):
            raise BuilderError(
                Diagnostic(
                    code="E_PROFILE_KIND_FORBIDDEN",
                    message="decl entry invalid",
                    expected="Decl",
                    got=type(decl).__name__,
                    path=json_pointer("decls", str(idx)),
                )
            )
        if decl.kind not in DECL_KINDS:
            raise BuilderError(
                Diagnostic(
                    code="E_PROFILE_KIND_FORBIDDEN",
                    message="Kind not allowed in contract profile",
                    expected="Structure/Interface/Function/Const/Type",
                    got=decl.kind,
                    path=json_pointer("decls", str(idx), "kind"),
                )
            )

    for idx, dep in enumerate(model.deps):
        if not isinstance(dep, Dep):
            raise BuilderError(
                Diagnostic(
                    code="E_PROFILE_KIND_FORBIDDEN",
                    message="dep entry invalid",
                    expected="Dep",
                    got=type(dep).__name__,
                    path=json_pointer("deps", str(idx)),
                )
            )
        if dep.bind.to_string() != dep.from_ref.to_string():
            raise BuilderError(
                Diagnostic(
                    code="E_DEP_BIND_MUST_EQUAL_FROM",
                    message="dep bind must equal from",
                    expected=dep.from_ref.to_string(),
                    got=dep.bind.to_string(),
                    path=json_pointer("deps", str(idx), "bind"),
                )
            )
        if not isinstance(dep.to_ref, (InternalRef, ContractRef)):
            raise BuilderError(
                Diagnostic(
                    code="E_TOKEN_PLACEMENT_VIOLATION",
                    message="dep to must be InternalRef or ContractRef",
                    expected="@Kind.RELID or CONTRACT.*",
                    got=str(dep.to_ref),
                    path=json_pointer("deps", str(idx), "to"),
                )
            )

    for idx, rule in enumerate(model.rules):
        if not isinstance(rule, Rule):
            raise BuilderError(
                Diagnostic(
                    code="E_PROFILE_KIND_FORBIDDEN",
                    message="rule entry invalid",
                    expected="Rule",
                    got=type(rule).__name__,
                    path=json_pointer("rules", str(idx)),
                )
            )
        if not isinstance(rule.bind, InternalRef):
            raise BuilderError(
                Diagnostic(
                    code="E_RULE_BIND_INVALID",
                    message="rule bind must be InternalRef",
                    expected="@Kind.RELID",
                    got=str(rule.bind),
                    path=json_pointer("rules", str(idx), "bind"),
                )
            )
        for ref_idx, ref in enumerate(rule.refs):
            if not isinstance(ref, InternalRef):
                raise BuilderError(
                    Diagnostic(
                        code="E_RULE_REFS_INVALID",
                        message="rule refs must be InternalRef list",
                        expected="@Kind.RELID",
                        got=str(ref),
                        path=json_pointer("rules", str(idx), "refs", str(ref_idx)),
                    )
                )
        for ref_idx, ref in enumerate(rule.contract):
            if not isinstance(ref, ContractRef):
                raise BuilderError(
                    Diagnostic(
                        code="E_CONTRACT_REFS_INVALID",
                        message="rule contract must be ContractRef list",
                        expected="CONTRACT.*",
                        got=str(ref),
                        path=json_pointer("rules", str(idx), "contract", str(ref_idx)),
                    )
                )
        for ref_idx, ref in enumerate(rule.ssot):
            if not isinstance(ref, SSOTRef):
                raise BuilderError(
                    Diagnostic(
                        code="E_TOKEN_PLACEMENT_VIOLATION",
                        message="rule ssot must be SSOTRef list",
                        expected="SSOT.*",
                        got=str(ref),
                        path=json_pointer("rules", str(idx), "ssot", str(ref_idx)),
                    )
                )
