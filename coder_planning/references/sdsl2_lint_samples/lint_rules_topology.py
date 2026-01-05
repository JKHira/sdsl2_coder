from __future__ import annotations

from .config import Config
from .models import AnnotationBlock, Diagnostic


def rule_topology_connections(
    annotations: list[AnnotationBlock],
    path: str,
    config: Config,
    profile: str | None,
) -> list[Diagnostic]:
    if profile != "topology":
        return []
    diagnostics: list[Diagnostic] = []
    for ann in annotations:
        keys = {entry.key for entry in ann.meta_entries}
        if ann.kind == "Flow" and "contract_refs" in keys:
            diagnostics.append(
                Diagnostic(
                    path=path,
                    line=ann.start_line,
                    col=ann.start_col,
                    severity="error",
                    code="SDSL2E4102",
                    message="FLOW_CONTRACT_REFS_FORBIDDEN: contract_refs belongs on edges. Example: @Edge { contract_refs:[\"CONTRACT.X\"] }",
                )
            )
        if ann.kind != "Edge" and "contract_refs" in keys and ann.kind != "Flow":
            diagnostics.append(
                Diagnostic(
                    path=path,
                    line=ann.start_line,
                    col=ann.start_col,
                    severity="error",
                    code="SDSL2E4113",
                    message="CONTRACT_REFS_MISPLACED: contract_refs only on edges. Example: @Edge { contract_refs:[\"CONTRACT.X\"] }",
                )
            )
        if ann.kind == "Edge":
            missing = config.topology_edge_required_fields.difference(keys)
            if "contract_refs" in missing:
                diagnostics.append(
                    Diagnostic(
                        path=path,
                        line=ann.start_line,
                        col=ann.start_col,
                        severity="error",
                        code="SDSL2E4101",
                        message="TOPOLOGY_CONNECTION_MISSING_CONTRACT_REFS: contract_refs required. Example: @Edge { id:\"E\", from:@Node.A, to:@Node.B, direction:\"pub\", contract_refs:[\"CONTRACT.X\"] }",
                    )
                )
            if missing:
                diagnostics.append(
                    Diagnostic(
                        path=path,
                        line=ann.start_line,
                        col=ann.start_col,
                        severity="error",
                        code="SDSL2E4112",
                        message="TOPOLOGY_CONNECTION_SHAPE_INVALID: missing required fields. Example: id/from/to/direction/contract_refs",
                    )
                )
            if "contract" in keys:
                diagnostics.append(
                    Diagnostic(
                        path=path,
                        line=ann.start_line,
                        col=ann.start_col,
                        severity="error",
                        code="SDSL2E4103",
                        message="TOPOLOGY_CONNECTION_FORBIDS_CONTRACT_FIELD: use contract_refs. Example: contract_refs:[\"CONTRACT.X\"]",
                    )
                )
            if "refs" in keys:
                diagnostics.append(
                    Diagnostic(
                        path=path,
                        line=ann.start_line,
                        col=ann.start_col,
                        severity="error",
                        code="SDSL2E4104",
                        message="TOPOLOGY_CONNECTION_FORBIDS_REFS_FIELD: refs not allowed. Example: use contract_refs only",
                    )
                )
            direction = None
            for entry in ann.meta_entries:
                if entry.key == "direction":
                    direction = entry.value_text.strip().strip("\"")
                    break
            if direction and direction not in config.topology_edge_direction_vocab:
                diagnostics.append(
                    Diagnostic(
                        path=path,
                        line=ann.start_line,
                        col=ann.start_col,
                        severity="error",
                        code="SDSL2E4105",
                        message="TOPOLOGY_DIRECTION_INVALID: invalid direction value. Example: direction:\"pub\"",
                    )
                )
    return diagnostics
