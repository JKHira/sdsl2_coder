from __future__ import annotations

from dataclasses import dataclass

from .contract import ContractModel, Decl, Dep, DocMeta, Rule
from .refs import ContractRef, InternalRef, SSOTRef


DECL_KIND_ORDER = {
    "Structure": 1,
    "Interface": 2,
    "Function": 3,
    "Const": 4,
    "Type": 5,
}


def _quote(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _format_internal_refs(items: list[InternalRef]) -> str:
    inner = ",".join(ref.to_string() for ref in items)
    return f"[{inner}]"


def _format_tokens(items: list[ContractRef] | list[SSOTRef]) -> str:
    inner = ",".join(_quote(ref.to_string()) for ref in items)
    return f"[{inner}]"


def _format_annotation(kind: str, pairs: list[tuple[str, str]]) -> list[str]:
    if len(pairs) <= 2:
        inner = ", ".join(f"{k}:{v}" for k, v in pairs)
        return [f"@{kind} {{ {inner} }}"]
    lines = [f"@{kind} {{"]
    for key, value in pairs:
        lines.append(f"  {key}:{value},")
    lines.append("}")
    return lines


def _format_doc_meta(item: DocMeta) -> list[str]:
    pairs: list[tuple[str, str]] = [("id", _quote(item.rel_id))]
    if item.title is not None:
        pairs.append(("title", _quote(item.title)))
    if item.desc is not None:
        pairs.append(("desc", _quote(item.desc)))
    if item.refs:
        pairs.append(("refs", _format_internal_refs(item.refs)))
    if item.ssot:
        pairs.append(("ssot", _format_tokens(item.ssot)))
    return _format_annotation("DocMeta", pairs)


def _format_decl(item: Decl) -> list[str]:
    pairs: list[tuple[str, str]] = [("id", _quote(item.rel_id))]
    if item.bind is not None:
        pairs.append(("bind", item.bind.to_string()))
    if item.title is not None:
        pairs.append(("title", _quote(item.title)))
    if item.desc is not None:
        pairs.append(("desc", _quote(item.desc)))
    if item.refs:
        pairs.append(("refs", _format_internal_refs(item.refs)))
    if item.contract:
        pairs.append(("contract", _format_tokens(item.contract)))
    if item.ssot:
        pairs.append(("ssot", _format_tokens(item.ssot)))

    lines = _format_annotation(item.kind, pairs)
    decl_lines = [line.rstrip() for line in item.decl.rstrip().splitlines()]
    lines.extend(decl_lines)
    return lines


def _format_dep(item: Dep) -> list[str]:
    pairs: list[tuple[str, str]] = [
        ("id", _quote(item.dep_id)),
        ("bind", item.bind.to_string()),
        ("from", item.from_ref.to_string()),
        ("to", _quote(item.to_ref.to_string()) if not isinstance(item.to_ref, InternalRef) else item.to_ref.to_string()),
    ]
    if item.ssot:
        pairs.append(("ssot", _format_tokens(item.ssot)))
    return _format_annotation("Dep", pairs)


def _format_rule(item: Rule) -> list[str]:
    pairs: list[tuple[str, str]] = [
        ("id", _quote(item.rel_id)),
        ("bind", item.bind.to_string()),
    ]
    if item.refs:
        pairs.append(("refs", _format_internal_refs(item.refs)))
    if item.contract:
        pairs.append(("contract", _format_tokens(item.contract)))
    if item.ssot:
        pairs.append(("ssot", _format_tokens(item.ssot)))
    return _format_annotation("Rule", pairs)


def write_contract(model: ContractModel) -> str:
    if not isinstance(model, ContractModel):
        raise TypeError("MODEL_TYPE_INVALID")

    lines: list[str] = []
    lines.append(f'@File {{ profile:"contract", id_prefix:{_quote(model.id_prefix)} }}')

    if model.doc_meta:
        lines.extend(_format_doc_meta(model.doc_meta))

    decls = sorted(model.decls, key=lambda d: (DECL_KIND_ORDER.get(d.kind, 99), d.rel_id))
    deps = sorted(model.deps, key=lambda d: d.dep_id)
    rules = sorted(model.rules, key=lambda r: r.rel_id)

    for item in decls:
        lines.extend(_format_decl(item))
    for item in deps:
        lines.extend(_format_dep(item))
    for item in rules:
        lines.extend(_format_rule(item))

    text = "\n".join(lines).rstrip() + "\n"
    return text
