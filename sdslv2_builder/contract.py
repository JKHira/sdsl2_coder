from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Iterable

from .errors import Diagnostic, BuilderError, json_pointer
from .jcs import dumps as jcs_dumps
from .refs import ContractRef, InternalRef, SSOTRef, RELID_RE


@dataclass(frozen=True)
class DocMeta:
    rel_id: str
    title: str | None
    desc: str | None
    refs: list[InternalRef]
    ssot: list[SSOTRef]


@dataclass(frozen=True)
class Decl:
    kind: str
    rel_id: str
    decl: str
    bind: InternalRef | None
    title: str | None
    desc: str | None
    refs: list[InternalRef]
    contract: list[ContractRef]
    ssot: list[SSOTRef]


@dataclass(frozen=True)
class Dep:
    dep_id: str
    bind: InternalRef
    from_ref: InternalRef
    to_ref: InternalRef | ContractRef
    ssot: list[SSOTRef]


@dataclass(frozen=True)
class Rule:
    rel_id: str
    bind: InternalRef
    refs: list[InternalRef]
    contract: list[ContractRef]
    ssot: list[SSOTRef]


@dataclass(frozen=True)
class ContractModel:
    id_prefix: str
    doc_meta: DocMeta | None
    decls: list[Decl]
    deps: list[Dep]
    rules: list[Rule]


def _require_relid(value: str, path: str) -> None:
    if not RELID_RE.match(value):
        raise BuilderError(
            Diagnostic(
                code="E_ID_FORMAT_INVALID",
                message="id must be RELID",
                expected="UPPER_SNAKE_CASE",
                got=value,
                path=path,
            )
        )


def _require_internal_ref(
    value: InternalRef | None,
    path: str,
    required: bool = False,
) -> InternalRef | None:
    if value is None:
        if required:
            raise BuilderError(
                Diagnostic(
                    code="E_BIND_TARGET_NOT_FOUND",
                    message="bind is required",
                    expected="@Kind.RELID",
                    got="missing",
                    path=path,
                )
            )
        return None
    if not isinstance(value, InternalRef):
        raise BuilderError(
            Diagnostic(
                code="E_BIND_TARGET_NOT_FOUND",
                message="bind must be InternalRef",
                expected="@Kind.RELID",
                got=str(value),
                path=path,
            )
        )
    return value


def _require_internal_refs(values: Iterable[InternalRef] | None, path_segments: tuple[str, ...]) -> list[InternalRef]:
    if values is None:
        return []
    items = list(values)
    for idx, item in enumerate(items):
        if not isinstance(item, InternalRef):
            raise BuilderError(
                Diagnostic(
                    code="E_BIND_TARGET_NOT_FOUND",
                    message="refs must be InternalRef list",
                    expected="@Kind.RELID",
                    got=str(item),
                    path=json_pointer(*path_segments, str(idx)),
                )
            )
    return items


def _require_contract_refs(values: Iterable[ContractRef] | None, path_segments: tuple[str, ...]) -> list[ContractRef]:
    if values is None:
        return []
    items = list(values)
    for idx, item in enumerate(items):
        if not isinstance(item, ContractRef):
            raise BuilderError(
                Diagnostic(
                    code="E_CONTRACT_REFS_INVALID",
                    message="contract must be ContractRef list",
                    expected="CONTRACT.*",
                    got=str(item),
                    path=json_pointer(*path_segments, str(idx)),
                )
            )
    return items


def _require_ssot_refs(values: Iterable[SSOTRef] | None, path_segments: tuple[str, ...]) -> list[SSOTRef]:
    if values is None:
        return []
    items = list(values)
    for idx, item in enumerate(items):
        if not isinstance(item, SSOTRef):
            raise BuilderError(
                Diagnostic(
                    code="E_TOKEN_PLACEMENT_VIOLATION",
                    message="ssot must be SSOTRef list",
                    expected="SSOT.*",
                    got=str(item),
                    path=json_pointer(*path_segments, str(idx)),
                )
            )
    return items


class ContractBuilder:
    def __init__(self) -> None:
        self._id_prefix: str | None = None
        self._doc_meta: DocMeta | None = None
        self._decls: list[Decl] = []
        self._deps: list[Dep] = []
        self._rules: list[Rule] = []

    def file(self, id_prefix: str) -> "ContractBuilder":
        _require_relid(id_prefix, json_pointer("file", "id_prefix"))
        self._id_prefix = id_prefix
        return self

    def doc_meta(
        self,
        rel_id: str,
        title: str | None = None,
        desc: str | None = None,
        refs: Iterable[InternalRef] | None = None,
        ssot: Iterable[SSOTRef] | None = None,
    ) -> "ContractBuilder":
        _require_relid(rel_id, json_pointer("doc_meta", "id"))
        self._doc_meta = DocMeta(
            rel_id=rel_id,
            title=title,
            desc=desc,
            refs=_require_internal_refs(refs, ("doc_meta", "refs")),
            ssot=_require_ssot_refs(ssot, ("doc_meta", "ssot")),
        )
        return self

    def structure(
        self,
        rel_id: str,
        decl: str,
        title: str | None = None,
        desc: str | None = None,
        refs: Iterable[InternalRef] | None = None,
        contract: Iterable[ContractRef] | None = None,
        ssot: Iterable[SSOTRef] | None = None,
        bind: InternalRef | None = None,
    ) -> "ContractBuilder":
        self._add_decl(
            "Structure",
            rel_id,
            decl,
            title=title,
            desc=desc,
            refs=refs,
            contract=contract,
            ssot=ssot,
            bind=bind,
        )
        return self

    def interface(
        self,
        rel_id: str,
        decl: str,
        title: str | None = None,
        desc: str | None = None,
        refs: Iterable[InternalRef] | None = None,
        contract: Iterable[ContractRef] | None = None,
        ssot: Iterable[SSOTRef] | None = None,
        bind: InternalRef | None = None,
    ) -> "ContractBuilder":
        self._add_decl(
            "Interface",
            rel_id,
            decl,
            title=title,
            desc=desc,
            refs=refs,
            contract=contract,
            ssot=ssot,
            bind=bind,
        )
        return self

    def function(
        self,
        rel_id: str,
        decl: str,
        title: str | None = None,
        desc: str | None = None,
        refs: Iterable[InternalRef] | None = None,
        contract: Iterable[ContractRef] | None = None,
        ssot: Iterable[SSOTRef] | None = None,
        bind: InternalRef | None = None,
    ) -> "ContractBuilder":
        self._add_decl(
            "Function",
            rel_id,
            decl,
            title=title,
            desc=desc,
            refs=refs,
            contract=contract,
            ssot=ssot,
            bind=bind,
        )
        return self

    def const(
        self,
        rel_id: str,
        decl: str,
        title: str | None = None,
        desc: str | None = None,
        refs: Iterable[InternalRef] | None = None,
        contract: Iterable[ContractRef] | None = None,
        ssot: Iterable[SSOTRef] | None = None,
        bind: InternalRef | None = None,
    ) -> "ContractBuilder":
        self._add_decl(
            "Const",
            rel_id,
            decl,
            title=title,
            desc=desc,
            refs=refs,
            contract=contract,
            ssot=ssot,
            bind=bind,
        )
        return self

    def type_alias(
        self,
        rel_id: str,
        decl: str,
        title: str | None = None,
        desc: str | None = None,
        refs: Iterable[InternalRef] | None = None,
        contract: Iterable[ContractRef] | None = None,
        ssot: Iterable[SSOTRef] | None = None,
        bind: InternalRef | None = None,
    ) -> "ContractBuilder":
        self._add_decl(
            "Type",
            rel_id,
            decl,
            title=title,
            desc=desc,
            refs=refs,
            contract=contract,
            ssot=ssot,
            bind=bind,
        )
        return self

    def dep(
        self,
        from_ref: InternalRef,
        to: InternalRef | ContractRef,
        ssot: Iterable[SSOTRef] | None = None,
    ) -> "ContractBuilder":
        from_ref = _require_internal_ref(from_ref, json_pointer("dep", "from"), required=True)
        if not isinstance(to, (InternalRef, ContractRef)):
            raise BuilderError(
                Diagnostic(
                    code="E_TOKEN_PLACEMENT_VIOLATION",
                    message="dep to must be InternalRef or ContractRef",
                    expected="@Kind.RELID or CONTRACT.*",
                    got=str(to),
                    path=json_pointer("dep", "to"),
                )
            )
        to_norm = to.to_string()
        payload = jcs_dumps({"from": from_ref.to_string(), "to": to_norm}).encode("utf-8")
        dep_id = f"DEP_{from_ref.rel_id}_{hashlib.sha256(payload).hexdigest()[:12].upper()}"
        self._deps.append(
            Dep(
                dep_id=dep_id,
                bind=from_ref,
                from_ref=from_ref,
                to_ref=to,
                ssot=_require_ssot_refs(ssot, ("dep", "ssot")),
            )
        )
        return self

    def rule(
        self,
        rel_id: str,
        bind: InternalRef,
        refs: Iterable[InternalRef] | None = None,
        contract: Iterable[ContractRef] | None = None,
        ssot: Iterable[SSOTRef] | None = None,
    ) -> "ContractBuilder":
        _require_relid(rel_id, json_pointer("rule", "id"))
        if bind is None:
            raise BuilderError(
                Diagnostic(
                    code="E_RULE_BIND_REQUIRED",
                    message="bind is required",
                    expected="@Kind.RELID",
                    got="missing",
                    path=json_pointer("rule", "bind"),
                )
            )
        bind_ref = _require_internal_ref(bind, json_pointer("rule", "bind"), required=True)
        self._rules.append(
            Rule(
                rel_id=rel_id,
                bind=bind_ref,
                refs=_require_internal_refs(refs, ("rule", "refs")),
                contract=_require_contract_refs(contract, ("rule", "contract")),
                ssot=_require_ssot_refs(ssot, ("rule", "ssot")),
            )
        )
        return self

    def _add_decl(
        self,
        kind: str,
        rel_id: str,
        decl: str,
        title: str | None,
        desc: str | None,
        refs: Iterable[InternalRef] | None,
        contract: Iterable[ContractRef] | None,
        ssot: Iterable[SSOTRef] | None,
        bind: InternalRef | None,
    ) -> None:
        _require_relid(rel_id, json_pointer(kind.lower(), "id"))
        bind_ref = _require_internal_ref(bind, json_pointer(kind.lower(), "bind"), required=False)
        self._decls.append(
            Decl(
                kind=kind,
                rel_id=rel_id,
                decl=decl,
                bind=bind_ref,
                title=title,
                desc=desc,
                refs=_require_internal_refs(refs, (kind.lower(), "refs")),
                contract=_require_contract_refs(contract, (kind.lower(), "contract")),
                ssot=_require_ssot_refs(ssot, (kind.lower(), "ssot")),
            )
        )

    def build(self) -> ContractModel:
        if not self._id_prefix:
            raise BuilderError(
                Diagnostic(
                    code="E_PROFILE_INVALID",
                    message="file(id_prefix) must be set",
                    expected="file(id_prefix)",
                    got="missing",
                    path=json_pointer("file"),
                )
            )
        model = ContractModel(
            id_prefix=self._id_prefix,
            doc_meta=self._doc_meta,
            decls=list(self._decls),
            deps=list(self._deps),
            rules=list(self._rules),
        )
        from .closed_set_contract_v0_1 import validate_contract_model_v0_1

        validate_contract_model_v0_1(model)
        return model
