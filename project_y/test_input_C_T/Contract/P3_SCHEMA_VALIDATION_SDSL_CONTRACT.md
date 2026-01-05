```typescript
// P3: Schema Validation SDSL - CONTRACT / IO
// @Rule.P3_C_SPEC: SSOT.BNS_Validation_Spec;
// @Rule.P3_C_SPLIT: CONTRACT.DataContracts, SSOT.FormatRules;
// IMPORTANT: Must Obay Stable ID Rules: Stable_ID_Base_Rules.md

// ═══════════════════════════════════════════════════════════════
// @DocMeta.P3_C_SEC2_FEATURE_SCHEMA_ID_SYSTEM_TYPE_DEFINITIONS: §2 . FEATURE SCHEMA ID SYSTEM - TYPE DEFINITIONS
// ═══════════════════════════════════════════════════════════════

// @Rule.P3_C_FSIS_TYPE_PRPHIBITED : CONTRACT.PROHIBITED_TYPES, @Const.P3_C_FSIS_TYPE_RULE_CONSTS;
// @Rule.P3_C_FSIS_TYPE_ALLOWED : CONTRACT.ALLOWED_TYPES, @Const.P3_C_FSIS_TYPE_RULE_CONSTS;
// @Const.P3_C_FSIS_TYPE_RULE_CONSTS: Feature Schema ID System type rule constants (prohibited/precision/semver)
const PROHIBITED_TYPES = [datetime,date,time,bytes,bytearray]
const FLOAT_PRECISION = 9
const SEMVER_PATTERN = /^\d+\.\d+\.\d+/
// --- end: P3_FSIS_TYPE_RULE_CONSTS ---

// @Structure.P3_C_FSIS_HASH_INPUT_SCHEMA: Hash input schema for feature_schema_id derivation
struct HashInputSchema {
// @Rule.P3_C_FSIS_FMT_BNS_IDS:
  bns_id:s, bns_version:s,
  bns_config:{
// @Rule.P3_C_FSIS_BNS_SEC5_1_FORMAT: @Structure.P3_C_FSIS_HASH_INPUT_SCHEMA, SSOT.BNS_Formats;
    format:enum["numpy"|"polars"|"arrow"],
// @Rule.P3_C_FSIS_BNS_SEC5_1_DTYPE: @Structure.P3_C_FSIS_HASH_INPUT_SCHEMA, SSOT.BNS_Dtypes;
    dtype:enum["float32"|"float64"],
    order:list[s]
  },
  nodes:[{node_id:s, feature_def:s, feature_version:s, node_version:s, params:d}]
}

// ═══════════════════════════════════════════════════════════════
// @DocMeta.P3_C_SEC3_VERSION_RESOLVER_TYPE_DEFINITIONS: §3 . VERSION RESOLVER - TYPE DEFINITIONS
// ═══════════════════════════════════════════════════════════════

// @Rule.P3_C_VRTD_LAYER: SSOT.LayerHierarchy;
// @Structure.P3_C_VRTD_VERSIONED_REFERENCE: Versioned reference (name + optional version)
struct VersionedReference { name:s, version:s? }

// ═══════════════════════════════════════════════════════════════
// @DocMeta.P3_C_SEC4_MASTER_TABLE_TYPE_DEFINITIONS: §4 . MASTER TABLE - TYPE DEFINITIONS
// ═══════════════════════════════════════════════════════════════

// @Rule.P3_C_MTTD_BNS_SEC6: @Structure.P3_C_MTTD_MASTER_TABLE_SCHEMA;

// @Rule.P3_C_MTTD_PATTERN: @Const.P3_C_MTTD_PATTERN_CONSTS, CONTRACT.PATTERN_ID, CONTRACT.PATTERN_SEMVER, CONTRACT.PATTERN_HASH;
// @Const.P3_C_MTTD_PATTERN_CONSTS: Master table regex pattern constants (id/semver/hash)
const PATTERN_ID = /^[a-z][a-z0-9_]*$/        // bns_id, model_id (max_length=64)
const PATTERN_SEMVER = /^\d+\.\d+\.\d+/       // system_version, min_version
const PATTERN_HASH = /^sha256:[a-f0-9]{64}$/  // config_hash, deprecated id
// --- end: P3_MTTD_PATTERN_CONSTS ---


// @Structure.P3_C_MTTD_BNS_ENTRY: Master table entry for allowed BNS (id + min_version)
struct BNSEntry {
// @Rule.P3_C_MTTD_ID_PATTERN_BNS_ENTRY : pattern=PATTERN_ID, max_length=64
  bns_id:s,
// @Rule.P3_C_MTTD_BNS_ENTRY_SEMVER : pattern=PATTERN_SEMVER
  min_version:s
}

// @Structure.P3_C_MTTD_MODEL_ENTRY: Master table entry for allowed model (id + min_version)
struct ModelEntry {
// @Rule.P3_C_MTTD_ID_PATTERN_MODEL_ENTRY: pattern=PATTERN_ID, max_length=64
  model_id:s,
// @Rule.P3_C_MTTD: pattern=PATTERN_SEMVER
  min_version:s
}

// @Structure.P3_C_MTTD_PHASE_CONFIG: Master table phase config (role + allowlists + failure policy)
struct PhaseConfig {
  role:s, allowed_bns:list[BNSEntry]?, allowed_feature_schema_ids:list[s]?,
  allowed_models:list[ModelEntry]?,
  failure_policy:enum["HARD_HALT"|"DEGRADE"|"NO_SIGNAL"|"REJECT_ALL"|"FORCE_EXIT"|"STATIC_WEIGHTS"]
}

// @Structure.P3_C_MTTD_DEPRECATED_SCHEMA_ENTRY: Deprecated schema entry (id + deprecation/removal)
struct DeprecatedSchemaEntry {
// @Rule.P3_C_MTTD_ID_PATTERN_DEPRECATED_SCHEMA_ENTRY: CONTRACT.PATTERN_HASH, @Const.P3_C_MTTD_PATTERN_CONSTS;
  id:s,
  deprecated_since:s,
// @Rule.P3_C_MTTD_AUTO_REMOVEAL_DATE: SSOT.RemovalPolicy;
  removal_date:s?
}

// @Structure.P3_C_MTTD_METADATA: Master table metadata (system_version/config_hash/last_updated)
struct Metadata {
// @Rule.P3_C_MTTD_METADATA_SEMVER: CONTRACT.PATTERN_SEMVER, @Const.P3_C_MTTD_PATTERN_CONSTS;
  system_version:s,
  target_symbol:s,
// @Rule.P3_C_MTTD_METADATA_HASH: CONTRACT.PATTERN_HASH, @Const.P3_C_MTTD_PATTERN_CONSTS;
  config_hash:s,
  last_updated:ts
}

// @Structure.P3_C_MTTD_MASTER_TABLE_SCHEMA: Master table schema (metadata + phases + deprecated list)
struct MasterTableSchema { metadata:Metadata, phases:d[s,PhaseConfig], deprecated_schema_ids:list[DeprecatedSchemaEntry]? }

// ═══════════════════════════════════════════════════════════════
// @DocMeta.P3_C_SEC5_MASTER_TABLE_RELOAD_TYPE_DEFINITIONS: §5 . MASTER TABLE RELOAD - TYPE DEFINITIONS
// ═══════════════════════════════════════════════════════════════

// @Rule.P3_C_MTRT_22: SSOT.AtomicBuffering, @Structure.P3_C_MTR_MASTER_TABLE;
// @Structure.P3_C_MTRT_MASTER_TABLE: Loaded master table container (config_hash/data/loaded_at_ns)
struct MasterTable { config_hash:s, data:d, loaded_at:i } // loaded_at=nanoseconds

// @Const.P3_C_MTRT_RELOAD_CHANNEL_CONST: Master table reload channel constant
const RELOAD_CHANNEL = "master:reload"
// --- end: P3_MTRT_RELOAD_CHANNEL_CONST ---

//
// ═══════════════════════════════════════════════════════════════
// @DocMeta.P3_C_SEC6_VALIDATION_ERROR_BEHAVIOR_TYPE_DEFINITIONS: §6 . VALIDATION ERROR BEHAVIOR - TYPE DEFINITIONS
// ═══════════════════════════════════════════════════════════════

// @Rule.P3_C_VEB_ERROR_CODE: CONTRACT.ErrorCode, SSOT.ValidationErrors;
// @Structure.P3_C_VEB_VALIDATION_RESULT: Validation result (valid/skip_reason/error_code/state_transition)
struct ValidationResult { valid:b, skip_reason:s?, error_code:s?, state_transition:s? }

// ═══════════════════════════════════════════════════════════════
// @DocMeta.P3_C_SEC7_AUTHORIZATION_CHECK_TYPE_DEFINITIONS_CONSTANTS: §7 . AUTHORIZATION CHECK - TYPE DEFINITIONS & CONSTANTS
// ═══════════════════════════════════════════════════════════════

// @Rule.P3_C_ACTD_05: CONTRACT.AUTHORIZATION_CACHE_TTL_SECONDS, @Const.P3_C_ACTD_AUTHZ_CONSTS;
// @Rule.P3_C_ACTD_07: CONTRACT.GRACE_PERIOD_SECONDS, @Const.P3_C_ACTD_AUTHZ_CONSTS;
// @Ref.P3_C_ACTD_06: @Rule.P3_C_VEB_ERROR_CODE;
// @Note.P3_C_ACTD_CACHE_DISTINCTION: This is Authorization result cache, NOT Master Table cache (SSOT feature:cache TTL=60s)

// @Const.P3_C_ACTD_AUTHZ_CONSTS: Authorization check constants (cache_ttl/grace_period)
const AUTHORIZATION_CACHE_TTL_SECONDS = 30  // P3-05: Authorization result cache (NOT Master Table cache)
const GRACE_PERIOD_SECONDS = 60
// --- end: P3_ACTD_AUTHZ_CONSTS ---


// @Structure.P3_C_ACTD_AUTHORIZATION_RESULT: Authorization result (authorized/reason/error_code/deprecated/grace_expires_at)
struct AuthorizationResult { authorized:b, reason:s?, error_code:s?, deprecated:b=F, grace_expires_at:i? }

// @DocMeta.P3_C_SEC7_2_CONFIGURATION_SUMMARY: §7.2 CONFIGURATION SUMMARY (P3-03~07) — table follows
// | Setting         | Value                      | Rationale                               |
// |-----------------|----------------------------|------------------------------------------|
// | Hash Algorithm  | SHA-256                    | Industry standard, collision-resistant   |
// | Check Timing    | Pre-inference (@Task.P3_C_03)| Fail fast before computation             |
// | Cache TTL       | 30 seconds (@Task.P3_C_05)   | Balance freshness vs performance         |
// | Grace Period    | 60 seconds (@Task.P3_C_07)   | Allow rollback during deprecation        |
// | Error Code      | SCHEMA.HASH.MISMATCH(@Task.P3_C_06) | Consistent error identification    |
```
