# SDSL2 SSOT File Layout and Parse Surface

Scope: Define SSOT root and parse surface for .sdsl2.
Non-scope: Grammar/semantics; manifest allowlist mode.

## Definitions
- SSOT root: Only directory for authoritative SDSL2 parsing.
- Parsed file: File selected under SSOT root.
- Whole-file mode: Parse full file; no fenced regions.
- Normalized relative path: Repo-relative, "/" separators, no leading "./".

## Rules
- SSOT root: sdsl2/.
- Parsed globs:
  - sdsl2/contract/**/*.sdsl2
  - sdsl2/topology/**/*.sdsl2
- Parsing is whole-file only; fenced-region parsing for sdsl2/ is disabled.
- CI MUST NOT follow symlinks under sdsl2/.
- @File.profile MUST match containing dir (contract|topology); mismatch FAIL.
- Parse order: lexical by normalized relative path.
- @File.id_prefix MUST be globally unique across all parsed files; duplicate FAIL.
- Parsed files MUST be UTF-8 with LF-normalized line endings.
- Manifest allowlist mode is inactive; if adopted it MUST replace glob mode (no mixed mode).
- Empty profile dirs allowed; CI emits DIAG when a profile has zero parsed files.
