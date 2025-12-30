# Traceable SDSL v2.0 Grammar and Canonical Style Manual

## Out of Scope & Goals (v2.0)

SDSL v2.0 is a declarative metadata language for deterministic extraction of declarations and annotations. It is not a program analysis framework.

**Explicitly Out of Scope:**

* **Implementation-language semantics/typechecking** (TypeScript/Rust parsing, type inference, module resolution).
* **Full block-body parsing** (no inference engine capabilities).
* **“Tag everything” authoring:** L1 anchors target only CI-relevant units.
* **Ambiguity-resolution mechanisms** (omitted Kind precedence, path-based inference, automatic resolution).
* **Repository profiles:** The Stable-ID scheme (scope/vocabularies) MUST be expressed as a Repo Profile.

**Goals:**

* Deterministic grammar and canonical style (No-Variance).
* Topology/Graph defined by declaration, not inference.
* **Authority Separation:** Contract profile defines contract truth; Topology profile defines graph facts.
* **ContractRef Uniqueness:** External contracts MUST be expressed only as "CONTRACT.*" string tokens.

**Non-Goals:**

* Runtime semantics of pseudo-code.
* Moving authority by re-homing declarations across profiles.

## Rewrite Rules: Topology Graph Facts Generation & Safety (Normative)

R1. No Inference / No Synthesis (Generation Prohibited)
 • The converter (including any LLM-based rewrite) MUST NOT generate @Node, @Edge, @Flow, or @Terminal from any non-declarative content, including:
 • prose,
 • pseudo-code,
 • arrow notation (e.g., ->, ==>),
 • naming conventions, or
 • implementation text inside blocks or comments.
 • If a Graph Fact is not present in an allowed explicit source, it MUST be treated as missing and MUST NOT be inferred or synthesized.

R2. Allowed Explicit Sources for Graph Facts (Closed Set)

Graph Facts (@Node, @Edge, @Flow, @Terminal) MAY be created only from the following explicit sources (closed set):

 1. A connection table/list explicitly enumerating endpoints (e.g., producer/consumer pairs).
 2. Existing machine-readable connection metadata (structured lists, prior explicit metadata fields).
 3. An explicit, structured inventory/list of nodes/edges/terminals provided as authoritative input for rewrite.

Any other source is FORBIDDEN for Graph Fact generation.

R3. Output Admissibility: Empty Graph Facts Are Valid
 • If no allowed explicit source exists for Topology Graph Facts, the converter MUST produce no @Node/@Edge/@Flow/@Terminal statements (i.e., Graph Facts are empty).
 • Missing "topology" information MUST be left as missing and recorded only as diagnostics (e.g., MIG_*) and/or TODO markers, and MUST NOT be fabricated. Missing info of "Contract" should be "= None" instead of " = TODO".

R4. Contract Binding for Topology Connections
 • If a topology connection unit is created (@Edge or an edge object inside @Flow.edges), it MUST include contract_refs:[...] and the tokens MUST comply with the token placement/type rules in Section 9.3.
 • If contract_refs is not present in an allowed explicit source for that connection, the converter MUST NOT create the connection unit.

R5. Duplicate Representation: Prose vs Declared Graph Facts
 • If the same relationship appears both in prose/pseudo-code and in declarative Graph Facts, the converter MUST treat only the declarative Graph Facts as semantic.
 • Prose/pseudo-code representations of relationships MUST be ignored for graph construction and MUST NOT be used to add or modify Graph Facts.

R6. Duplicate Graph Facts (Same Target)

Choose exactly one policy and apply it consistently:
 • Option A (Strict): Duplicate Graph Fact declarations for the same target MUST be treated as an error.
 • Option B (Migration): Duplicate Graph Fact declarations for the same target MUST be reported as diagnostics (e.g., MIG_*) and resolved by rewrite guidance, but MUST NOT change semantics by implicit merging.

(Repository policy MUST select Option A or Option B.)

R7. SSOT References for Rewrite Authority
 • Token placement, external token typing, and forbidden placements MUST follow Section 9.3 (the only SSOT for the reference model).
 • The Topology two-layer model and the rule “Graph Facts only” MUST follow Section 9.4 (the only SSOT for the two-layer model).
 • This rewrite instruction MUST NOT redefine the reference model or two-layer semantics beyond deferring to the SSOT sections above

---

## 0. Normative Design Principles

* **Determinism:** Identical input yields identical parse and meaning.
* **No-Variance:** Equivalent meaning has one canonical form only.
* **Zero Inference:** Only declared facts are semantic; prose/pseudo-code are non-semantic.
* **Token Placement Closure:** "CONTRACT.*" and "SSOT.*" tokens are valid only in fields enumerated in **Section 9.3**.

---

## 2. Parse Surface and Profiles

### 2.1 Parse Surface (Deterministic)

CI parses only:

1. **Fenced code blocks** with enabled language tag (`sdsl` or `ts`/`typescript`).
2. **Whole-file mode** for configured paths.

#### 2.1.1 Multiple Parsed Regions (Normative)

CI **MUST** concatenate all parsed regions in source order to form a single logical SDSL document. The first Statement of the first parsed region is the document start.

#### 2.1.2 embedded_ts Surface (Normative)

When parsing `ts`/`typescript` regions, CI **MUST** extract SDSL Statements as follows:

* A line starting with `@` (first non-whitespace) starts an Annotation.
* A contiguous group of Annotation lines forms an annotation group.
* The next non-blank, non-comment line is a Declaration head *only* if it matches `DeclarationHead` (Section 5.1). Strict matching: lines with any leading modifier (e.g., export, default, declare, abstract) are **NOT** Declaration heads.
* If a Declaration head follows, the group + head (plus Block) form one **AnnotatedDecl**.
* If no Declaration head follows, the group is one **AnnotationOnly**.
* CI **MUST NOT** parse or typecheck TypeScript.

### 2.2 File Header (Mandatory)

A **Parsed SDSL Document** corresponds to a physical source file.

* Each document **MUST** begin with exactly one `@File { ... }` statement.
* `@File` **MUST** appear as the first non-comment, non-blank statement.
* Extra `@File` statements **MUST** be rejected (`DUPLICATE_FILE_HEADER`).
* If missing, CI **MUST** report `MANDATORY_HEADER_MISSING`.
* Mixing profiles (contract + topology) in one file is **not supported**.

```sdsl
@File { profile:"contract", id_prefix:"P0_C_KSDC" }

```

---

## 3. Lexical Conventions

* **Whitespace:** Space/tab only. Not semantically meaningful for grammar. CI/lint **MUST** preserve trivia (newlines/comments) for formatting enforcement.
* **Comments:** `//` and `/* ... */`. Ignored by parser. (Legacy migration: see Appendix M).
* **Identifiers:** `[A-Za-z_][A-Za-z0-9_]*` (Case sensitive).
* **Literals (Canonical):**
* Boolean: `T`, `F`
* Null: `None`
* String: `"..."` (double quotes only)
* Number: `123`, `1.23`

---

## 4. Core Data Model

**[UNIFIED] Topology as Specialized Kinds**
Topology primitives (`@Node`, `@Edge`, `@Flow`, `@Terminal`) are **Annotations with reserved Kinds**. The AST is a stream of unified Statements:

1. **AnnotatedDecl:** Annotations attached to one Declaration.
2. **AnnotationOnly:** Annotations not attached to a Declaration.

Contract dependency graph facts **MUST** use `@Dep` (not `@Edge`) when `@File.profile:"contract"`.



---

## 5. Grammar (Normative)

### 5.1 Document

```sdsl
Document        := (Statement | Comment | BlankLine)*
Statement       := AnnotatedDecl | AnnotationOnly
AnnotatedDecl   := AnnotationLine+ DeclarationUnit
AnnotationOnly  := AnnotationLine+
AnnotationLine  := Annotation Newline
Annotation      := '@' Kind WS MetadataObject
DeclarationUnit := EnumHead Block
                | StructHead Block
                | InterfaceHead Block
                | ConstHead
                | ClassHead Block
                | FunctionHead Block
                | TypeHead
EnumHead        := 'enum' Ident
StructHead      := 'struct' Ident
InterfaceHead   := 'interface' Ident
ConstHead       := 'const' Ident (':' Type)? '=' Expr
ClassHead       := ('C' | 'class') Ident Params?
FunctionHead    := ('f' | 'async' WS 'f') Ident Params '->' Type
TypeHead        := 'type' Ident '=' TypeExpr

```

CI **MUST** normalize line endings to `\n`.

**Statement Boundary Rules (Normative):**

* **AnnotatedDecl:** Annotation group + immediately following Declaration head.
* **AnnotationOnly:** Annotation group with no following Declaration head.
* A blank line or comment between group and Declaration head prevents AnnotatedDecl formation.

**Normative Constraints:**

* Declaration-bearing anchors (`@Structure`, `@Interface`, `@Type`, etc.) **MUST** appear in an AnnotatedDecl.
* Graph fact kinds (`@Node`, `@Edge`, `@Flow`, `@Terminal`) **MUST** be AnnotationOnly.
* `@Node` **MUST NOT** depend on declaration adjacency (MAY include `bind` target).
* Detached annotations (e.g., `@Rule`) **MUST** specify explicit `bind` targets.

### 5.2 Metadata Object

```sdsl
MetadataObject := '{' (Pair (',' Pair)*)? ','? '}'
Pair           := Key ':' Value
Value          := String | Number | Bool | Null | Ident | Ref | Array | MetadataObject
Ref            := '@' Kind ('.' | '::') IdToken
IdToken        := RelId | CanonId | String

```

* **Ref:** Explicitly encodes relative (`.`) vs absolute (`::`).
* **Canonical IDs:** MAY appear only in Refs as `@Kind::CANON_ID`; **MUST NOT** be authored as id values.

### 5.3 Declarations & Balanced-Brace Capture (Normative)

Declarations (`enum`, `struct`, etc.) are parsed structurally. Pseudo-code inside blocks is **not** interpreted.

**Capture Algorithm:**
CI **MUST** capture block bodies (`{...}`) and expressions (`= ...`) as raw text using a minimal state machine:

1. **Normal:** Increment/decrement brace depth. Ignore braces in strings/comments.
2. **Strings:** `'...'`, `"..."`, ``...``. Backslash escapes one char.
3. **Template Literals:** ``...``. `${` enters TEMPLATE_EXPR state.
4. **TEMPLATE_EXPR:** Process as Normal. First `}` returning depth to 0 resumes Template Literal.
5. **Comments:** `//`, `/*...*/`. Braces ignored.
6. **Termination:** Shortest match (first `}` returning depth to 0).
7. For ConstDecl expressions, capture from `=` forward using the same rules. If the expression spans multiple
   lines, CI MUST continue until reaching a line break where depth is 0 and the state is NORMAL.

---

## 6. Binding Rules

### 6.1 Inline Binding (Canonical)

**[MANDATORY] Single-Statement Binding:**
Adjacency/implicit binding is **NOT** permitted. Declaration-bearing annotations **MUST** be part of an **AnnotatedDecl**.
*Lint:* A blank line/comment between Annotation and Declaration is an error.

### 6.2 Explicit Binding

Used when ambiguity exists or for AnnotationOnly. Provide a `bind` object:
`bind: { kind:"struct", name:"..." }` (or array).
If `bind` is present, adjacency rules do not apply.

---

## 7. Canonical Style (Lint) — “No-Variance” Rules

Authors **MUST** follow these rules to eliminate notation variance.

### 7.1 Formatting & Literals (MUST)

* **Key Order:** `id`, `bind`, `title`, `desc`, `refs`, `contract`, `ssot`, `severity`.
* **Trailing Commas:** **REQUIRED** for multi-line objects/arrays.
* **Vertical Expansion:** Objects with >2 keys **MUST** use one pair per line.
* **Literals:** `T`/`F` (Bool), `None` (Null), `"..."` (String). Forbidden: `true`, `false`, `null`, single-quotes.

### 7.3 Collections & Types (MUST)

* **Allowed:** `T[]`, `d[K,V]`, `set[T]`, `(T1,T2)`, `(i..)`.
* **Forbidden:** `[T]`, `List[T]`, `Dict[K,V]`, `any`.
* **Exception:** `d` (untyped) **MAY** be used only if documented as intentionally dynamic.

### 7.3.1 Type Alias (Contract-only) (MUST)

* Type alias declarations are allowed only in `profile:"contract"`.
* Form: `type Name = "a"|"b"|...` (string literal union only).
* Type aliases **MUST** be anchored with `@Type` as an AnnotatedDecl.
* Non-string unions or other type expressions in `type` are forbidden (lint error).

#### Additional Type-Form Constraints (Normative)

1 Tuple type forms:
- The only valid tuple type syntax is the parenthesized form: (T1,T2,...) (e.g., (s,s), (s,i,ts)).
- Generic tuple notation is forbidden: tuple[T], tuple[s], tuple[...].

2 Dynamic/dictionary type forms:
- Parameterized angle-bracket forms are forbidden: d<T>, d<PhaseHealth>, Map<T>, Dict<T>, etc.
- Use only d (intentionally dynamic) or d[K,V] (typed map) as defined in this section.

Rationale (CI): These constraints eliminate notation variance and prevent parse/lint failures that would block downstream Contract↔Topology consistency checks.

### 7.4 Object Construction (MUST)

* **Preferred:** `TypeName{field:value}`.
* **Restricted:** `{key:value}` (untyped) only when intentionally dynamic.
* **Forbidden:** `{a,b,c}` shorthand.
* Do not mix typed and untyped construction for the same conceptual object within a single file.

### 7.5 Struct Field Layout (MUST)

* One field per line.
* Order: **required → optional → defaulted**.
* Field grammar MUST be one of:
  * name: Type
  * name: Type?
  * name: Type = <literal>
* Defaults **MUST** be deterministic literals only (no runtime expressions).

### 7.6 Canonical Declaration Ordering (SHOULD)

For stable diffs, authors SHOULD maintain the following order:

1. @DocMeta section anchor (if present)
2. Binding annotations
3. Declaration (enum / struct / interface / const / C / f / type)
4. Supporting annotations (e.g., detached @Rule, @Criteria) when needed

### 7.7 to 7.8 Annotation Form & Keys (MUST)

* **Native Form:** `@Structure { ... }` only. Legacy comment tags are forbidden (except in Migration, see Appendix M).
* **Common Keys:** `id` (RelId: UPPER_SNAKE_CASE), `bind`, `title`, `desc`, `refs`, `contract` (see 9.3), `ssot` (see 9.3).
* **Topology Keys:** `from`, `to`, `direction`, `channel`, `contract_refs` (see 9.3), `terminal_to`.

### 7.9 Canonical Reference Tokens (MUST)

1. **Internal Ref:** `@Kind.REL_ID` or `@Kind::CANON_ID`.
2. **External Token:** `"CONTRACT.*"` or `"SSOT.*"`.
3. **Local Binding:** `bind:{...}`.

* Escaped Internal Ref (@Kind."escaped") MUST be used only when RelId/CanonId is not possible; lint SHOULD treat it as non-canonical.
* Do not encode linkage twice (e.g., in `refs` and prose).
* **Constraints:** Normative placement defined in **Section 9.3**.

### 7.10 Canonical Direction (MUST)

Topology edge direction **MUST** be one of: `"pub"`, `"sub"`, `"req"`, `"rep"`, `"rw"`, `"call"` (if enabled).

### 7.11 Canonical Contract Binding (MUST)

Topology **connection units** (`@Edge` or `@Flow.edges`) **MUST** bind contracts using exactly one field: `contract_refs`.

* `contract_refs` **MUST** appear on `@Edge` and edge objects.
* `@Flow.contract_refs` **MUST NOT** appear.
* `contract:[...]` **MUST NOT** be used on connection units.

---

## 8. Topology Grammar Layer (Declarative)

Topology checks are driven by explicit declarations. Semantics defined in **Section 9.4**.

* **Nodes:** Exist only if declared by `@Node`. `@Node` is always **AnnotationOnly**.
* **Edges:** Exist only if declared by `@Edge` or `@Flow { edges:[...] }`.
* **Terminals:** Node is terminal only if:
* `@Terminal { ... }` targets it, or
* Edge declares `terminal_to:T`, or
* Node declares `terminal:T`.

CI must not infer terminalness from names (e.g., STOPPED).
CI **must not** infer graph facts from pseudo-code or prose.

---

## 9. Domain Authority Model (Normative)

SDSL v2 shares declaration syntax across profiles, but authority is profile-bound. Authority **MUST NOT** move across profiles.

### 9.1 Contract Authority (profile:"contract")

* This document is authoritative for contract definitions (schema/type/API/interface/const) and dependency facts (`@Dep`).
* Declarations in this profile define contract truth.
* Graph fact kinds (`@Node`, `@Edge`, `@Flow`, `@Terminal`) **MUST NOT** appear.
* Topology facts are not derived from contract files.

### 9.2 Topology Authority (profile:"topology")

* This document is authoritative for graph facts only: `@Node`, `@Edge`, `@Flow`, `@Terminal`.
* Declarations are descriptive anchors only and **MUST NOT** define contract truth or dependencies.
* Contract dependency facts (`@Dep`) **MUST NOT** appear.
* Contract binding exists only on connection units via `contract_refs`.

### 9.3 Contract Reference Model (Normative SSOT)

This section is the SSOT for token placement closure, field-type constraints, forbidden patterns, and resolution scope.

**Glossary (Normative)**

* **Internal Ref:** `@Kind.REL_ID` or `@Kind::CANON_ID`. Resolves against SDSL declarations.
* **External Token:** Registry symbol as string.
* **ContractRef:** `"CONTRACT.*"`
* **SSOTRef:** `"SSOT.*"`

* **Type Separation:** Internal Refs and External Tokens are different types and **MUST NOT** be mixed. A value matching `"CONTRACT.*"` or `"SSOT.*"` **MUST** be treated as an External Token and **MUST NOT** appear inside a Ref.

**Resolution Scope**

* ContractRef/SSOTRef resolution is independent of SDSL internal resolution.
* CI **MUST NOT** infer the meaning or existence of `"CONTRACT.*"` or `"SSOT.*"` tokens.

**Single Form for External Tokens**

* ContractRef **MUST** be expressed only as a `"CONTRACT.*"` string token.
* SSOTRef **MUST** be expressed only as a `"SSOT.*"` string token.
* Internal Refs **MUST NOT** be used as ContractRef or SSOTRef.

**Token Placement SSOT (Closed Set)**

| Token type          | Allowed fields (closed set) | Notes |
| ------------------- | --------------------------- | ----- |
| **ContractRef**<br> |

<br>`"CONTRACT.*"` | `contract:[...]`<br>

<br>`contract_refs:[...]`<br>

<br>`@Dep.to` | `@Dep.to` is external dependency target only.<br>

<br>`@Flow.contract_refs` is forbidden. |
| **SSOTRef**<br>

<br>`"SSOT.*"` | `ssot:[...]` |  |

Any placement of `"CONTRACT.*"` or `"SSOT.*"` outside the table above is an error.

**Field Type Constraints**

* `refs:[...]` **MUST** contain Internal Refs only.
* `bind` **MUST** contain Internal Refs or bind-target objects only.
* `contract:[...]` and `contract_refs:[...]` **MUST** contain ContractRef tokens only.
* `ssot:[...]` **MUST** contain SSOTRef tokens only.
* `contract_refs:[...]` is permitted only on topology connection units (Section 7.11).

**Forbidden Patterns**

* In a topology connection unit (`@Edge` / `@Flow` edges), `contract_refs` is the only binding field. `contract:[...]` **MUST NOT** appear.
* `refs` is forbidden on topology connection units.
* `contract_refs` and `contract` **MUST NOT** contain Internal Refs or non-token strings.
* Contract binding **MUST NOT** be expressed via alias fields (e.g., `contract_alias`) or inferred from descriptive fields.

**Forbidden Locations**

* Placement of `"CONTRACT.*"` or `"SSOT.*"` in `refs` or `bind` is an error.

**Token Placement Examples (Non-normative)**

Allowed:

contract_refs:["CONTRACT.X"]
ssot:["SSOT.X"]

Forbidden:

refs:["CONTRACT.X"]
contract:["SSOT.X"]

**@Dep.to Target Form (Normative)**

* `@Dep.to` **MAY** be either an Internal Ref OR a `"CONTRACT.*"` token.
* Within a single @Dep statement, to MUST use exactly one of the two forms above; mixing forms is forbidden.
* to MUST NOT be an array, union, or any form that encodes multiple targets or multiple reference types.

**Non-normative Examples (Dep.to)**

Allowed:

@Dep { id:"A_USES_EXT", from:@Structure.A, to:"CONTRACT.KillLevel", kind:"field_type" }
@Dep { id:"A_USES_LOCAL", from:@Structure.A, to:@Structure.B, kind:"field_type" }

Forbidden (mixed target form):

@Dep { id:"BAD_MIX", from:@Structure.A, to:["CONTRACT.KillLevel", @Structure.B] }

### 9.4 Topology Two-Layer Model

* **Graph Facts layer:** `@Node`, `@Edge`, `@Flow`, `@Terminal` define topology. CI **MUST** extract Graph Facts only from topology-profile documents.
* **Behavior layer:** Declarations/prose **MUST NOT** create or modify graph facts.
* Behavior text **MUST NOT** imply contract binding; only `contract_refs` binds contracts.
* Arrow notations (e.g., `->`) are cosmetic and **MUST NOT** be interpreted as graph facts.

### 9.5 Minimal Required KINDS (Informational)

*Note: `@SSOTRef` is excluded from v2.0 core (see Appendix M).*

**Contract Profile:**

* `@File`, `@DocMeta`
* `@Structure`, `@Interface`, `@Function`, `@Const`, `@Type`
* `@Dep` (from: Ref; to: Ref or ContractRef)

**Topology Profile:**

* `@Node` (id, kind, terminal?, bind?)
* `@Edge` (id, from, to, direction, contract_refs)
* `@Flow` (edges:[EdgeInline...])
* `@Terminal` (node, reason?)

---

## 10. Canonical Examples

### 10.1 Contract

```sdsl
@File { profile:"contract", id_prefix:"P0_C_KSDC" }
@Structure { id:"KILL_LEVEL" } enum KillLevel { ... }

```

### 10.2 Topology (Low False Positives)

```sdsl
@File { profile:"topology", id_prefix:"P0_T_SFTOPO" }
@Node { id:"EXECUTOR", kind:"component" }
@Edge {
  from:@Node.CONTROLLER, to:@Node.EXECUTOR, direction:"req",
  contract_refs:["CONTRACT.SignedControlCommand"]
}

```

---

## 11. Elegant, Concise Authoring Pattern (Recommended)

* **Single header annotation:** One primary annotation (`@Structure`/`@Function`) directly above declaration.
* **Cross-cutting constraints:** Use `@Rule` with explicit `bind`.
* **Topology:** Declare graph primitives separately from pseudo-code.

---

## 12. Canonical Checklist (Authoring Gate)

* Booleans are `T`/`F`, null is `None`, strings are `"..."`.
* Collections use `T[]`, `d[K,V]`.
* Every meaningful declaration has exactly one primary v2 annotation with `id`.
* No legacy tag lines are relied upon.
* Refs use `@Kind.REL_ID` or `@Kind::CANON_ID`.
* Topology edges exist only via `@Edge` / `@Flow.edges`.
* Every edge has `contract_refs:[...]`.

---

## Appendix: Repo Profile: System5 (Optional Normative)

*Normative only for repositories that declare adoption.*

### 1. Edges Are Explicitly Split by Domain

SDSL **MUST NOT** overload a single "Edge" concept.

#### A. Topology Domain (Runtime Wiring)

* **MUST** use: `@Node`, `@Edge`, `@Flow`, `@Terminal`.
* `@Edge` **MUST** declare: `from`, `to`, `direction` (closed set: `pub`,`sub`,`req`,`rep`,`rw`,`call`), `contract_refs`.

#### B. Contract Domain (Dependency)

* **MUST NOT** use `@Edge`.
* **MUST** use dependency KINDS: `@Dep`, `@Uses`, or `@TypeDep`.

### 2. Stable ID Namespacing via File-Level Prefix

#### 2.1 @File.id_prefix

* Each parsed file **MUST** define `@File.id_prefix`.

#### 2.2 Canonical ID Forms

* **Relative IDs:** UPPER_SNAKE_CASE. **MUST** be unique within the file.
* **Canonical IDs:** Computed by CI as `<id_prefix> + "_" + <relative_id>`. CI **MUST NOT** rewrite files.

#### 2.3 Reference Rules

* CI **MUST** resolve relative refs against `id_prefix` and absolute refs as canonical.
* The `.` vs `::` token is the only signal; CI **MUST NOT** infer.

### 3. Binding Is Unambiguous

* **Inline:** AnnotatedDecl (`Annotation+ Declaration`) is the single syntactic unit.
* **Detached:** `@Rule` **MUST** provide explicit `bind`. If absent, CI **MUST** report `BINDING_REQUIRED`.

### 4. Lint Requirements (Non-Negotiable)

* `@File` **MUST** appear once per file.
* `id_prefix` **MUST** be non-empty.
* **Edge Completeness:** `from`, `to`, `direction`, `contract_refs` required.
* CI **MUST NOT** modify source files.

---

## Canonical Authoring Model (Normative constraints)

*Supplements the Repo Profile. Strict adherence reduces CI noise.*

### 1. L1 Anchor Density

* **A. Section Anchors:** Each major section **MUST** have one `@DocMeta`.
* **B. Declaration Anchors:** Each externally meaningful declaration **MUST** have exactly one primary annotation (`@Structure`, `@Interface`, `@Function`, `@Node`).
* **C. Rule Anchors:** Only rules intended for CI verification **MUST** be written as `@Rule`.

### 2. Explicit Non-Targets (MUST)

* Private helpers, logs, and incidental pseudo-code **SHOULD NOT** receive stable IDs (L1-exempt).

### 3. SSOT Authority (MUST)

* The only semantic SSOT linkage is the metadata token list: `ssot:["SSOT.X"]`.
* `@SSOTRef` **MUST NOT** be used (Legacy only).

---
