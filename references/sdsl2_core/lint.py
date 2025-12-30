from __future__ import annotations

from .config import Config
from .lint_parse import (
    get_file_id_prefix,
    get_file_profile,
    group_annotations,
    parse_annotations,
)
from .lint_rules_decl import (
    rule_const_name_invalid,
    rule_decl_keyword_unknown,
    rule_decl_name_invalid,
    rule_enum_member_names,
    rule_field_name_and_type,
    rule_function_signatures,
    rule_invalid_numeric_literals,
    rule_metadata_key_invalid,
    rule_missing_default_values,
)
from .lint_rules_files import (
    rule_docmeta_presence,
    rule_file_header,
    rule_file_id_prefix,
    rule_file_profile,
)
from .lint_rules_kinds import (
    rule_id_rules,
    rule_kinds_allowlist,
    rule_rule_bind,
    rule_statement_forms,
)
from .lint_rules_literals import (
    rule_const_literal_identifier_tokens,
    rule_enum_string_value_wrapping,
    rule_enum_string_value_symbols,
    rule_enum_string_values,
    rule_invalid_literal_spacing,
    rule_literal_invalid_chars,
    rule_scalar_literal_wrapping,
    rule_string_literal_token_spacing,
    rule_unquoted_identifier_symbols,
)
from .lint_rules_tokens import rule_token_placement
from .lint_rules_topology import rule_topology_connections
from .lint_rules_types import (
    rule_ellipsis_in_type,
    rule_forbidden_patterns,
    rule_invalid_optional_marker,
    rule_non_deterministic_defaults,
    rule_struct_head_params,
    rule_todo_string_in_consts,
    rule_type_invalid_chars,
    rule_type_spacing,
)
from .models import Diagnostic


EDITOR_RULE_CODES = {
    "SDSL2E1001",
    "SDSL2E1002",
    "SDSL2E1003",
    "SDSL2E1004",
    "SDSL2E1005",
    "SDSL2E2001",
    "SDSL2E2002",
    "SDSL2E2003",
    "SDSL2E2004",
    "SDSL2E2005",
    "SDSL2E2006",
    "SDSL2E3001",
    "SDSL2E3002",
    "SDSL2E3003",
    "SDSL2E3004",
    "SDSL2W3101",
    "SDSL2E4001",
    "SDSL2E4002",
    "SDSL2E4003",
    "SDSL2E4004",
    "SDSL2E4005",
    "SDSL2E4101",
    "SDSL2E4102",
    "SDSL2E4103",
    "SDSL2E4104",
    "SDSL2E4105",
    "SDSL2E4112",
    "SDSL2E4113",
    "SDSL2E5001",
    "SDSL2E5002",
    "SDSL2E5003",
    "SDSL2E5101",
    "SDSL2E5202",
    "SDSL2E5203",
    "SDSL2E5204",
    "SDSL2E5205",
    "SDSL2E5206",
    "SDSL2E5207",
    "SDSL2E5208",
    "SDSL2E5209",
    "SDSL2E5210",
    "SDSL2E5211",
    "SDSL2E5212",
    "SDSL2E5213",
    "SDSL2E5214",
    "SDSL2E5215",
    "SDSL2E5216",
    "SDSL2E5217",
    "SDSL2E5218",
    "SDSL2E5219",
    "SDSL2E5220",
    "SDSL2E5221",
    "SDSL2E5222",
    "SDSL2E5223",
    "SDSL2E5224",
    "SDSL2E5225",
    "SDSL2E5226",
    "SDSL2E5227",
    "SDSL2E5228",
    "SDSL2E5229",
    "SDSL2E5230",
    "SDSL2E5231",
    "SDSL2E5232",
    "SDSL2E5233",
    "SDSL2E5234",
    "SDSL2W5201",
}


def lint_text(text: str, path: str, config: Config) -> list[Diagnostic]:
    lines = text.splitlines()
    annotations, line_kinds = parse_annotations(lines)
    groups = group_annotations(annotations, line_kinds, len(lines))

    diagnostics: list[Diagnostic] = []
    diagnostics.extend(rule_file_header(lines, annotations, path))
    file_profile = get_file_profile(annotations)
    id_prefix = get_file_id_prefix(annotations)
    diagnostics.extend(rule_file_profile(annotations, path, config, file_profile))
    diagnostics.extend(rule_file_id_prefix(annotations, path, config, id_prefix))
    diagnostics.extend(rule_docmeta_presence(annotations, path))
    diagnostics.extend(rule_kinds_allowlist(annotations, path, config, file_profile))
    diagnostics.extend(rule_statement_forms(groups, path, config))
    diagnostics.extend(rule_rule_bind(groups, path))
    diagnostics.extend(rule_id_rules(annotations, path, config, id_prefix))
    diagnostics.extend(rule_token_placement(annotations, path, config, file_profile))
    diagnostics.extend(rule_topology_connections(annotations, path, config, file_profile))
    diagnostics.extend(rule_forbidden_patterns(lines, path))
    diagnostics.extend(rule_invalid_optional_marker(lines, path))
    diagnostics.extend(rule_ellipsis_in_type(lines, path))
    diagnostics.extend(rule_struct_head_params(lines, path))
    diagnostics.extend(rule_non_deterministic_defaults(lines, path))
    diagnostics.extend(rule_todo_string_in_consts(lines, path, file_profile))
    diagnostics.extend(rule_enum_member_names(lines, path))
    diagnostics.extend(rule_field_name_and_type(lines, path))
    diagnostics.extend(rule_type_spacing(lines, path))
    diagnostics.extend(rule_missing_default_values(lines, path))
    diagnostics.extend(rule_invalid_numeric_literals(lines, path))
    diagnostics.extend(rule_function_signatures(lines, path))
    diagnostics.extend(rule_type_invalid_chars(lines, path))
    diagnostics.extend(rule_invalid_literal_spacing(lines, path))
    diagnostics.extend(rule_metadata_key_invalid(lines, path, annotations))
    diagnostics.extend(rule_decl_keyword_unknown(lines, path, annotations))
    diagnostics.extend(rule_enum_string_values(lines, path))
    diagnostics.extend(rule_enum_string_value_symbols(lines, path))
    diagnostics.extend(rule_decl_name_invalid(lines, path))
    diagnostics.extend(rule_const_name_invalid(lines, path))
    diagnostics.extend(rule_string_literal_token_spacing(lines, path))
    diagnostics.extend(rule_enum_string_value_wrapping(lines, path))
    diagnostics.extend(rule_literal_invalid_chars(lines, path))
    diagnostics.extend(rule_scalar_literal_wrapping(lines, path))
    diagnostics.extend(rule_unquoted_identifier_symbols(lines, path))
    diagnostics.extend(rule_const_literal_identifier_tokens(lines, path))

    return [diag for diag in diagnostics if diag.code in EDITOR_RULE_CODES]
