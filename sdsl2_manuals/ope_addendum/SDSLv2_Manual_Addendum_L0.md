# SDSL v2 Addendum L0: Global Skeleton

Use with SDSLv2_Manual_Addendum_Core.md.

## L0 Rules (Normative)

- Required: @File.stage:"L0".
- Allowed: @Node, @EdgeIntent.
- Forbidden: @Edge, @Flow.edges.
- Forbidden: @Terminal (default; see Repository Policy).
- @Node MUST include id.
- Placeholders in SDSL statements: forbidden.

## L0 Gate Defaults (Recommended)

- @Edge or @Flow.edges -> FAIL.
- @Terminal -> FAIL (unless allowed by Repository Policy).
