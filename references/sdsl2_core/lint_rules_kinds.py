from __future__ import annotations

import re

from .config import Config
from .lint_parse import StatementGroup, get_meta_value
from .models import AnnotationBlock, Diagnostic


def rule_kinds_allowlist(
    annotations: list[AnnotationBlock],
    path: str,
    config: Config,
    profile: str | None,
) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    if not profile or profile not in config.kinds_allowlist_by_profile:
        return diagnostics
    allowlist = config.kinds_allowlist_by_profile.get(profile, set())
    for ann in annotations:
        if ann.kind in {"File"}:
            continue
        if ann.kind not in allowlist:
            diagnostics.append(
                Diagnostic(
                    path=path,
                    line=ann.start_line,
                    col=ann.start_col,
                    severity="error",
                    code="SDSL2E2001",
                    message=f"KIND_NOT_ALLOWED_IN_PROFILE: {ann.kind} not allowed in {profile}. Example: check @File.profile allowlist",
                )
            )
    return diagnostics


def rule_statement_forms(
    groups: list[StatementGroup], path: str, config: Config
) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    for group in groups:
        kinds = {ann.kind for ann in group.annotations}
        if config.annotated_decl_required.intersection(kinds):
            if not group.has_decl:
                ann = group.annotations[0]
                diagnostics.append(
                    Diagnostic(
                        path=path,
                        line=ann.start_line,
                        col=ann.start_col,
                        severity="error",
                        code="SDSL2E2002",
                        message="DECL_ANCHOR_MUST_BE_ANNOTATED_DECL: declaration required. Example: @Structure { id:\"X\" } struct X {}",
                    )
                )
            if group.had_gap:
                ann = group.annotations[0]
                diagnostics.append(
                    Diagnostic(
                        path=path,
                        line=ann.start_line,
                        col=ann.start_col,
                        severity="error",
                        code="SDSL2E2004",
                        message="ANNOTATION_GROUP_SEPARATED_FROM_DECL: blank/comment between annotation and declaration. Example: annotation must be directly followed by decl",
                    )
                )
        if config.annotation_only_required.intersection(kinds) and group.has_decl:
            ann = group.annotations[0]
            diagnostics.append(
                Diagnostic(
                    path=path,
                    line=ann.start_line,
                    col=ann.start_col,
                    severity="error",
                    code="SDSL2E2003",
                    message="GRAPH_FACT_KIND_MUST_BE_ANNOTATION_ONLY: declaration forbidden. Example: @Node { id:\"N\" }",
                )
            )
        if config.annotation_only_and_bind_required.intersection(kinds) and group.has_decl:
            ann = group.annotations[0]
            diagnostics.append(
                Diagnostic(
                    path=path,
                    line=ann.start_line,
                    col=ann.start_col,
                    severity="error",
                    code="SDSL2E2003",
                    message="GRAPH_FACT_KIND_MUST_BE_ANNOTATION_ONLY: declaration forbidden. Example: @Node { id:\"N\" }",
                )
            )
    return diagnostics


def rule_rule_bind(groups: list[StatementGroup], path: str) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    for group in groups:
        for ann in group.annotations:
            if ann.kind != "Rule":
                continue
            bind_value = get_meta_value(ann, "bind")
            if not bind_value:
                diagnostics.append(
                    Diagnostic(
                        path=path,
                        line=ann.start_line,
                        col=ann.start_col,
                        severity="error",
                        code="SDSL2E2005",
                        message="RULE_BIND_REQUIRED: @Rule must include bind. Example: @Rule { id:\"R\", bind:{ kind:\"struct\", name:\"X\" } }",
                    )
                )
                continue
            if "@" in bind_value:
                continue
            if not (re.search(r"\bkind\s*:", bind_value) and re.search(r"\bname\s*:", bind_value)):
                diagnostics.append(
                    Diagnostic(
                        path=path,
                        line=ann.start_line,
                        col=ann.start_col,
                        severity="error",
                        code="SDSL2E2006",
                        message="BIND_TARGET_INVALID: bind requires kind/name or internal ref. Example: bind:{ kind:\"struct\", name:\"X\" } or bind:@Kind.REL_ID",
                    )
                )
    return diagnostics


def rule_id_rules(
    annotations: list[AnnotationBlock],
    path: str,
    config: Config,
    id_prefix: str | None,
) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    seen: set[tuple[str, str]] = set()
    prefix = f"{id_prefix}_" if id_prefix else None

    for ann in annotations:
        if ann.kind in {"File", "DocMeta"}:
            continue
        id_value = get_meta_value(ann, "id")
        if not id_value:
            diagnostics.append(
                Diagnostic(
                    path=path,
                    line=ann.start_line,
                    col=ann.start_col,
                    severity="error",
                    code="SDSL2E3001",
                    message="ID_MISSING: metadata id is required. Example: { id:\"FOO\" }",
                )
            )
            continue
        if config.rel_id_regex.pattern and not config.rel_id_regex.match(id_value):
            diagnostics.append(
                Diagnostic(
                    path=path,
                    line=ann.start_line,
                    col=ann.start_col,
                    severity="error",
                    code="SDSL2E3002",
                    message="ID_NOT_RELID: id must be UPPER_SNAKE_CASE. Example: id:\"FOO_BAR\"",
                )
            )
        if prefix and id_value.startswith(prefix):
            diagnostics.append(
                Diagnostic(
                    path=path,
                    line=ann.start_line,
                    col=ann.start_col,
                    severity="error",
                    code="SDSL2E3004",
                    message="CANON_ID_AUTHORED_AS_ID: id appears to be canonical. Example: id:\"FOO\" not \"PREFIX_FOO\"",
                )
            )
        key = (ann.kind, id_value)
        if key in seen:
            diagnostics.append(
                Diagnostic(
                    path=path,
                    line=ann.start_line,
                    col=ann.start_col,
                    severity="error",
                    code="SDSL2E3003",
                    message="ID_DUPLICATE_WITHIN_FILE: duplicate (kind,id)",
                )
            )
        else:
            seen.add(key)

    return diagnostics
