# SDSL v2 Addendum L1: Interface Shaping

Use with SDSLv2_Manual_Addendum_Core.md.

## L1 Rules (Normative)

- Required: @File.stage:"L1".
- Allowed: @Node, @Terminal, @Edge, @Flow.edges with contract_refs per Manual.
- Forbidden: @EdgeIntent.
- Placeholders in SDSL statements: forbidden.

## L1 Gate Defaults (Recommended)

- @EdgeIntent -> DIAG (upgrade to FAIL after migration window).
