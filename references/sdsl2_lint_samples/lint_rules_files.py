from __future__ import annotations

from typing import Optional

from .config import Config
from .lint_parse import find_first_statement_line
from .models import AnnotationBlock, Diagnostic


def rule_file_header(
    lines: list[str], annotations: list[AnnotationBlock], path: str
) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    file_annotations = [ann for ann in annotations if ann.kind == "File"]
    first_statement_line = find_first_statement_line(lines)
    if not file_annotations:
        target_line = first_statement_line or 1
        diagnostics.append(
            Diagnostic(
                path=path,
                line=target_line,
                col=1,
                severity="error",
                code="SDSL2E1001",
                message="MANDATORY_HEADER_MISSING: @File must be the first non-blank statement. Example: @File { profile:\"contract\", id_prefix:\"X\" }",
            )
        )
        return diagnostics

    first_file = file_annotations[0]
    if first_statement_line and first_statement_line != first_file.start_line:
        diagnostics.append(
            Diagnostic(
                path=path,
                line=first_file.start_line,
                col=first_file.start_col,
                severity="error",
                code="SDSL2E1002",
                message="FILE_HEADER_NOT_FIRST: @File must be the first non-blank statement. Example: @File { profile:\"contract\", id_prefix:\"X\" }",
            )
        )

    for duplicate in file_annotations[1:]:
        diagnostics.append(
            Diagnostic(
                path=path,
                line=duplicate.start_line,
                col=duplicate.start_col,
                severity="error",
                code="SDSL2E1003",
                message="DUPLICATE_FILE_HEADER: only one @File is allowed per document. Example: keep a single @File at top",
            )
        )
    return diagnostics


def rule_file_profile(
    annotations: list[AnnotationBlock], path: str, config: Config, profile: Optional[str]
) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    file_ann = next((ann for ann in annotations if ann.kind == "File"), None)
    if not file_ann:
        return diagnostics
    if not profile or profile not in config.allowed_profiles:
        diagnostics.append(
            Diagnostic(
                path=path,
                line=file_ann.start_line,
                col=file_ann.start_col,
                severity="error",
                code="SDSL2E1004",
                message="FILE_PROFILE_INVALID_OR_MISSING: @File.profile missing or invalid. Example: @File { profile:\"contract\" }",
            )
        )
    return diagnostics


def rule_file_id_prefix(
    annotations: list[AnnotationBlock],
    path: str,
    config: Config,
    id_prefix: Optional[str],
) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    if not config.stable_id_prefix_required:
        return diagnostics
    file_ann = next((ann for ann in annotations if ann.kind == "File"), None)
    if not file_ann:
        return diagnostics
    if not id_prefix:
        diagnostics.append(
            Diagnostic(
                path=path,
                line=file_ann.start_line,
                col=file_ann.start_col,
                severity="error",
                code="SDSL2E1005",
                message="FILE_ID_PREFIX_MISSING: @File.id_prefix required. Example: @File { id_prefix:\"X\" }",
            )
        )
    return diagnostics


def rule_docmeta_presence(annotations: list[AnnotationBlock], path: str) -> list[Diagnostic]:
    if any(ann.kind == "DocMeta" for ann in annotations):
        return []
    line = annotations[0].start_line if annotations else 1
    return [
        Diagnostic(
            path=path,
            line=line,
            col=1,
            severity="warning",
            code="SDSL2W3101",
            message="DOCMETA_MISSING_OR_TOO_SPARSE: Consider adding @DocMeta. Example: @DocMeta { id:\"SECTION\" }",
        )
    ]
