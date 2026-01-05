```typescript
// P2: Feature Integration SDSL - CONTRACT / IO
// L2-L3 Feature Pipeline + Model Pipeline Zero-Copy Integration
// Data Contracts, Types, Constants, and Interface Formats
// IMPORTANT: Must Obay Stable ID Rules: Stable_ID_Base_Rules.md

// ═══════════════════════════════════════════════════════════════
// @DocMeta.P2_C_SEC1_1_ERROR_CLASSES: §1.1 Error Classes
// ═══════════════════════════════════════════════════════════════
// @Class.P2_C_EC_BUFFER_LAYOUT_ERROR: Buffer layout error exception
C BufferLayoutError extends Exception { msg: s }
// @Class.P2_C_EC_DATA_TYPE_ERROR: Data type error exception
C DataTypeError extends Exception { msg: s }
// @Class.P2_C_EC_BUFFER_ERROR: Shared buffer error exception
C BufferError extends Exception { msg: s }
// @Class.P2_C_EC_FEATURE_FETCH_ERROR: Feature fetch base exception
C FeatureFetchError extends Exception { msg: s }
// @Class.P2_C_EC_FEATURE_TIMEOUT_ERROR: Feature fetch timeout exception
C FeatureTimeoutError extends FeatureFetchError { }
// @Class.P2_C_EC_FEATURE_SCHEMA_MISMATCH: Feature schema mismatch exception
C FeatureSchemaMismatch extends FeatureFetchError { expected: s, actual: s }

// ═══════════════════════════════════════════════════════════════
// @DocMeta.P2_C_SEC2_PERMISSION_MODEL_P2_02: §2 Permission Model (P2-02)
// ═══════════════════════════════════════════════════════════════
// @Rule.P2_C_PERM_ACL: CONTRACT.BufferPermission, @Structure.P2_C_PM_BUFFER_ACCESS_POLICY, CONTRACT.BufferState;
// @Structure.P2_C_PERM_BUFFER_PERMISSION_ENUM: Buffer permission enum (READ/WRITE)
enum BufferPermission { READ="read", WRITE="write" }

// @Structure.P2_C_PERM_BUFFER_ACCESS_POLICY: Buffer access policy schema (write/read allowed states)
struct BufferAccessPolicy {
  write_allowed: ("allocated","written"),
  read_allowed: ("published","claimed")
}

// ═══════════════════════════════════════════════════════════════
// @DocMeta.P2_C_SEC3_L2_L3_PULL_PATTERN_CONSTANTS_FORMAT_RULES: §3 L2-L3 Pull Pattern - Constants & Format Rules
// ═══════════════════════════════════════════════════════════════
// @Rule.P2_C_PPCF_TOPIC_PULL: @Const.P2_C_PPCF_PULL_PATTERN_CONST;
// @Rule.P2_C_PPCF_TRANSPORT_PULL_PATTERN: @Const.P2_C_PPCF_PULL_PATTERN_CONST;
// @Rule.P2_C_PPCF_TIMEOUT_PULL: @Const.P2_C_PPCF_PULL_PATTERN_CONST, @Const.P2_C_EC_FEATURE_TIMEOUT_ERROR;
// @Rule.P2_C_PPCF_DTYPE_FEATURE_FLOAT: SSOT.DType, @Const.P2_C_ZCB_ALLOWED_DTYPES_CONST;
// @Rule.P2_C_PPCF_DAG_NOTE: SSOT.ComputationGraph;
//                 Workers load computation graph via bns_id from BNS Manager
// @Const.P2_C_PPCF_PULL_PATTERN_CONST: Pull pattern topics/timeouts constants
const FEATURE_REQ_TOPIC = "feature:req:{model_id}"
const FEATURE_RESP_TOPIC = "feature:resp:{trace_id}"
const FEATURE_TIMEOUT_MS = 3000
// -- end: P2_PPCF_PULL_PATTERN_CONST --

// ═══════════════════════════════════════════════════════════════
// @DocMeta.P2_C_SEC3_3_PROTOCOL_EXCEPTION_TRANSPORT_FORMAT_RULES: §3.3 Protocol Exception - Transport Format Rules
// ═══════════════════════════════════════════════════════════════
// @Rule.P2_C_PETF_HOT_PATH: CONTRACT.SharedMem, CONTRACT.ArrowIPC;
// @Rule.P2_C_PETF_OTHER: CONTRACT.MessageEnvelope;

// ═══════════════════════════════════════════════════════════════
// @DocMeta.P2_C_SEC3_4_ZERO_COPY_BUFFER_TYPE_DEFINITIONS: §3.4 Zero-Copy Buffer - Type Definitions
// ═══════════════════════════════════════════════════════════════
// @Const.P2_C_ZCB_ALLOWED_DTYPES_CONST: Allowed dtypes for zero-copy buffers
const ALLOWED_DTYPES = ["float32","float64"]
// -- end: P2_ZCB_ALLOWED_DTYPES_CONST --



// @Rule.P2_C_ZCB_VALIDATE: @Const.P2_C_ZCB_ALLOWED_DTYPES_CONST, CONTRACT.BufferDescriptor;

// ═══════════════════════════════════════════════════════════════
// @DocMeta.P2_C_SEC3_5_BUFFER_LIFECYCLE_TYPES_CONSTANTS: §3.5 Buffer Lifecycle - Types & Constants
// ═══════════════════════════════════════════════════════════════
// State definitions (state machine transitions are in TOPOLOGY)
// @Structure.P2_C_BLTC_BUFFER_STATE_ENUM: Buffer lifecycle state enum (ALLOCATED..EXPIRED)
enum BufferState { ALLOCATED, WRITTEN, PUBLISHED, CLAIMED, RELEASED, EXPIRED }


// @Const.P2_C_BLTC_DEFAULT_BUFFER_TTL_SECONDS_CONST: Default buffer TTL (seconds)
const DEFAULT_BUFFER_TTL_SECONDS = 30
// -- end: P2_BLTC_DEFAULT_BUFFER_TTL_SECONDS_CONST --


// @Structure.P2_C_BLTC_BUFFER_DESCRIPTOR: Buffer descriptor schema (ref/meta/ttl/crc/schema_id)
struct BufferDescriptor {
  buffer_id: U, state: BufferState = ALLOCATED,
  path: s = "",  // shm://<uuid>.ipc
  size_bytes: i = 0, crc32: s = "", dtype: s = "float64",
  shape: (i..) = (), created_at_ns: i, expires_at_ns: i = 0,
  publisher_pid: i, refcount: i = 0, schema_id: s = ""
  // @Rule.P2_C_BLTC_PID_NS: @Structure.P2_C_BL_BUFFER_DESCRIPTOR;
  // @Rule.P2_C_BLTC_ALT: CONTRACT.Heartbeat, @Structure.P2_C_BL_BUFFER_DESCRIPTOR;
  // @Rule.P2_C_BLTC_ENV_PID: CONTRACT.PIDValidation;
  f is_expired() -> b { ret expires_at_ns>0 & now_ns()>expires_at_ns }
  f to_envelope_meta() -> d { ret {buffer_ref:path,buffer_size:size_bytes,crc32,dtype,shape,created_at_ns,expires_at_ns,schema_id} }
}

// Envelope Metadata Requirements (§3.5.3)
// buffer_ref: s (shm://<uuid>.ipc), buffer_size: i, crc32: s (8-hex),
// dtype: s, shape: [i], created_at_ns: i, expires_at_ns: i, schema_id: s
// @Const.P2_C_BLTC_SHM_BASE_DIR_CONST: Shared memory base directory constant
const SHM_BASE_DIR = "/dev/shm/system5_zero_copy"
// -- end: P2_BLTC_SHM_BASE_DIR_CONST --


// ═══════════════════════════════════════════════════════════════
// @DocMeta.P2_C_SEC3_5_5_ZERO_COPY_RETRY_CONFIG_P2_01: §3.5.5 Zero-Copy Retry Config (P2-01)
// ═══════════════════════════════════════════════════════════════
// @Structure.P2_C_ZCRC_RETRY_CONFIG: Zero-copy retry configuration schema (attempts/backoff/fallback)
struct ZeroCopyRetryConfig {
  max_attempts: i = 3,        // max 3 (up to 4 allowed)
  initial_delay_ms: f = 2.5,  // 2-3ms
  backoff_multiplier: f = 2.0,// exponential
  max_delay_ms: f = 30.0,     // max 30ms
  max_total_wait_ms: f = 50.0,// total ≤50ms
  // @Rule.P2_C_ZCRC_FALLBACK: @Structure.P2_C_ZC_RETRY_CONFIG, @Structure.P2_C_ZC_RECOVER_STRATEGY_ENUM;
  fallback_on_exhaust: s = "degraded",
  alert_on_fallback: b = T,
  safety_redis_notify: b = T,
  trigger_degraded_transition: b = T
}

// ═══════════════════════════════════════════════════════════════
// @DocMeta.P2_C_SEC3_5_6_FALLBACK_STRATEGY_OD_ZC_2_TYPES: §3.5.6 Fallback Strategy (OD-ZC-2) - Types
// ═══════════════════════════════════════════════════════════════
// @OD.P2_C_FBS_ZC_2: Fallback Strategy defaults and configurability matrix
// @Structure.P2_C_FBS_ZC_RECOVER_STRATEGY_ENUM: Zero-copy recovery strategy enum
enum RecoverStrategy { FALLBACK_COPY, DROP, RETRY, DEGRADED }
// Strategy mapping (behavior logic in TOPOLOGY):
// mmap/open fail: COPY fallback (configurable)
// CRC mismatch: DROP + CRITICAL (not configurable)
// TTL expired: DROP + WARNING (configurable)
// Buffer not found: DROP + ERROR (not configurable)
// Retry exhaust: DEGRADED + CRITICAL (P2-09 default)

// @Structure.P2_C_FBS_ZC_CONFIG: Zero-copy fallback configuration schema
struct ZeroCopyConfig {
  fallback_on_open_failure: b = T,
  fallback_on_crc_mismatch: b = F,  // NOT recommended
  fallback_on_expiration: b = F,
  max_retries: i = 1,
  default_strategy: RecoverStrategy = FALLBACK_COPY
}

// ═══════════════════════════════════════════════════════════════
// @DocMeta.P2_C_SEC4_ZERO_COPY_PROTOCOL_P2_06_FORMAT_TYPE_RULES: §4 Zero-Copy Protocol (P2-06) - Format & Type Rules
// ═══════════════════════════════════════════════════════════════
// @Rule.P2_C_ZCP_FORMAT: CONTRACT.ArrowIPC;
// @Rule.P2_C_ZCP_DTYPE_DEFAULT: @Const.P2_C_ZCP_PROTOCOL_CONST, CONTRACT.DataType;
// @Rule.P2_C_ZCP_DTYPE_POLICY:　@Const.P2_C_ZCP_PROTOCOL_CONST, CONTRACT.DataTypePolicy;
// @Rule.P2_C_ZCP_COMPRESSION: CONTRACT.CompressionPolicy;
// @Rule.P2_C_ZCP_MEM_LIMIT: @Const.P2_C_ZCP_PROTOCOL_CONST, SSOT.BP_MAX_MESSAGE_SIZE_BYTES;
// @Rule.P2_C_ZCP_CRC32: CONTRACT.BufferDescriptor, @Structure.P2_C_BL_BUFFER_DESCRIPTOR;
// @Rule.P2_C_ZCP_OVERFLOW_ACTION: @Const.P2_C_ZCP_PROTOCOL_CONST, CONTRACT.OverflowPolicy;
// @Const.P2_C_ZCP_PROTOCOL_CONST: Zero-copy protocol constants (mem limit + dtype policy)
const SHARED_MEMORY_LIMIT_BYTES = 1000000  // 1MB (exactly 1,000,000)
const ZERO_COPY_DTYPE_DEFAULT = "float64"
const ZERO_COPY_DTYPE_ALLOWED = ["float32","float64"]
// -- end: P2_ZCP_PROTOCOL_CONST --


// ═══════════════════════════════════════════════════════════════
// @DocMeta.P2_C_SEC4_2_BACKPRESSURE_POLICY_TYPES_THRESHOLDS_P2_03_04_08_09: §4.2 Backpressure Policy - Types & Thresholds (P2-03/04/08/09)
// ═══════════════════════════════════════════════════════════════
// @Rule.P2_C_BPYT_WARN: SSOT.BPYT_WARN_THRESHOLD_PERCENT, @Structure.P2_C_BPYT_MANAGER_CONFIG;
// @Rule.P2_C_BPYT_CRIT: SSOT.BPYT_CRITICAL_THRESHOLD_PERCENT, @Structure.P2_C_BP_MANAGER_CONFIG;
// @Rule.P2_C_BPYT_SAFETY: @Structure.P2_C_BPYT_MESSAGE_PRIORITY_ENUM, CONTRACT.SafetyPolicy;
// @Structure.P2_C_BPYT_MESSAGE_PRIORITY_ENUM: Message priority enum (CRITICAL/HIGH/MEDIUM/LOW)
enum MessagePriority { CRITICAL=1, HIGH=2, MEDIUM=3, LOW=4 }

// Semantic Load Shedding Priority Definitions (P2-09)
// CRITICAL (Kill/Alert): NEVER DROP -> Safety Redis
// HIGH (Order/Position): DROP last resort -> CRITICAL alert
// MEDIUM-A (FeatureVec): NO DROP -> DEGRADED transition
// MEDIUM-B (MarketData): Conflation (latest only, P2-08)
// LOW (Metrics/Debug): DROP first
// @Structure.P2_C_BPYT_CONFLATION_CONFIG: Conflation configuration schema
struct ConflationConfig { buffer_per_symbol: i = 1 }

// @Structure.P2_C_BPYT_MANAGER_CONFIG: Backpressure manager config schema (redis + keys + ttl)
struct BackpressureManagerConfig {
  // B-1: Main Redis (:6379) for bp:stats persistence (SSOT: /SSOT_Kernel/ssot_definitions.ts §2.2)
  main_redis_host: s = "localhost",
  main_redis_port: i = 6379,
  // Safety Redis (:6380) for alerts only
  safety_redis_host: s = "localhost",
  safety_redis_port: i = 6380,
  alert_channel: s = "alert:backpressure",
  metrics_output: s = "stdout_json",
  metrics_redis_enabled: b = T,
  bp_stats_key_prefix: s = "bp:stats",      // B-1: SSOT key pattern
  bp_stats_ttl_sec: i = 60,                  // B-1: SSOT TTL
  bp_queue_usage_prefix: s = "bp:queue:usage",  // B-2: Queue usage key
  bp_queue_usage_ttl_sec: i = 10,            // B-2: SSOT TTL
  bp_conflation_prefix: s = "bp:conflation:count"  // B-3: Conflation count key
}

// @DocMeta.P2_C_SEC4_2_5_BACKPRESSURE_MANAGER_CLASS_B_1_B_2_B_3: §4.2.5 BackpressureManager Class (B-1, B-2, B-3)
// @SSOTRef.P2_C_BPYT_LOCATION: SSOT.BackpressureManager;
// @Rule.P2_C_BPYT_MAIN_REDIS: @Structure.P2_C_BPYT_MANAGER_CONFIG, SSOT.RedisDefinitions;
// @Rule.P2_C_BPYT_SAFETY_REDIS: @Structure.P2_C_BPYT_MANAGER_CONFIG, SSOT.RedisDefinitions;
// @Class.P2_C_BPYT_BACKPRESSURE_MANAGER_CLASS: Backpressure manager class (persist + alert)
C BackpressureManager(config: BackpressureManagerConfig, main_redis: Redis, safety_redis: Redis) {
  _total_drops: i = 0, _total_conflations: i = 0, _last_persist_ns: i = 0

  // B-1: Record drop and persist stats to Main Redis
  f record_drop(component_id: s, reason: s) -> v {
    _total_drops++ -> _persist_stats(component_id) ->
    log.warning(f"DROP: {reason}") -> _check_thresholds(component_id)
  }

  // B-3: Record conflation and persist to Main Redis
  f record_conflation(component_id: s, symbol: s) -> v {
    _total_conflations++ -> _persist_stats(component_id) ->
    // B-3: Update bp:conflation:count:{symbol}
    main_redis.incr(f"{config.bp_conflation_prefix}:{symbol}") ->
    main_redis.expire(f"{config.bp_conflation_prefix}:{symbol}", config.bp_stats_ttl_sec) ->
    _check_thresholds(component_id)
  }

  // B-2: Update queue usage to Main Redis
  f update_queue_usage(queue_id: s, current_size: i, max_size: i) -> v {
    usage_pct = (current_size * 100) / max_size if max_size > 0 else 0 ->
    main_redis.setex(
      f"{config.bp_queue_usage_prefix}:{queue_id}",
      config.bp_queue_usage_ttl_sec,
      str(usage_pct)
    )
  }

  // B-1: Persist stats to Main Redis Hash (bp:stats:{component_id})
  f _persist_stats(component_id: s) -> v {
    key = f"{config.bp_stats_key_prefix}:{component_id}" ->
    main_redis.hset(key, mapping={
      "total_drops": str(_total_drops),
      "total_conflations": str(_total_conflations),
      "last_updated_ns": str(now_ns())
    }) -> main_redis.expire(key, config.bp_stats_ttl_sec)
  }

  f _check_thresholds(component_id: s) -> v {
    // Threshold check logic - emit alert via Safety Redis if exceeded
// @Rule.P2_C_BPYT_CHECK_THRESHOLDS_ANY_DROP: SSOT.BackpressurePolicy, @Structure.P2_C_BPYT_MANAGER_CONFIG;
    safety_redis.publish(config.alert_channel, json({
      "component_id": component_id,
      "total_drops": _total_drops,
      "total_conflations": _total_conflations,
      "level": "CRITICAL",
      "timestamp_ns": now_ns()
    }))
  }
}

// ═══════════════════════════════════════════════════════════════
// @DocMeta.P2_C_SEC4_2_4_BACKPRESSURE_STATS_PERSISTENCE_KEY_FORMAT: §4.2.4 Backpressure Stats Persistence - Key Format
// ═══════════════════════════════════════════════════════════════
// @Rule.P2_C_BPS_PERSIST: SSOT.BP_STATS_KEY, @Structure.P2_C_BP_MANAGER_CONFIG;
//
// @Rule.P2_C_BPS_UPDATE: @Structure.P2_C_BP_BACKPRESSURE_MANAGER_CLASS, CONTRACT.RedisHash;

// ═══════════════════════════════════════════════════════════════
// @DocMeta.P2_C_SEC4_2_5_DECIDED_ITEMS_P2_03_04_07_POLICY_CONSTANTS: §4.2.5 Decided Items (P2-03/04/07) - Policy Constants
// ═══════════════════════════════════════════════════════════════
// @OD.P2_C_POC_2: ANY drop/conflation = CRITICAL (not WARNING)
// @OD.P2_C_POC_3: Phase1 metrics output = stdout JSON only (no Prometheus)
// @OD.P2_C_POC_4: Conflation buffer = symbols × 1 (fixed)
// @Rule.P2_C_POC_BATCH: CONTRACT.BatchingPolicy, @Task.P2_C_07;


// ═══════════════════════════════════════════════════════════════
// @DocMeta.P2_C_SEC4_3_FEATURE_VECTOR_TRANSFER_DATA_TYPES: §4 Feature Vector Transfer - Data Types
// ═══════════════════════════════════════════════════════════════
// @Structure.P2_C_FVTD_FEATURE_VECTOR_TRANSFER: Feature vector transfer schema (bns_id/schema_id/buffer/order)
struct FeatureVectorTransfer {
  bns_id: s, feature_schema_id: s,  // SHA-256 hash
  timestamp: ts, buffer: ZeroCopyBuffer,
  order: [s]  // Feature ordering (CRITICAL for model alignment)
  f validate_against_model(expected_hash:s) -> b { ret feature_schema_id == expected_hash }
}

// @Rule.P2_C_FVTD_TIMESTAMP_UTC: SSOT.TimeDefinitions, CONTRACT.Timestamp;
// Usage: datetime.now(timezone.utc) or equivalent

// Feature Transport DTOs (06_SHARED §12.4/12.5)
// @Structure.P2_C_FVTD_FEATURE_REQUEST: Feature request DTO (trace_id/bns_id/model_id/timestamp_ns)
struct FeatureRequest {
  trace_id: s, bns_id: s, model_id: s, timestamp_ns: i
}

// @Structure.P2_C_FVTD_FEATURE_RESPONSE: Feature response DTO (status/content_type/buffer_ref/schema_id/error)
struct FeatureResponse {
  trace_id: s, status: s,  // "OK" | "ERROR" | "TIMEOUT"
  content_type: s = "arrow",
  buffer_ref: s = "",      // shm://<uuid>.ipc
  schema_id: s = "",       // feature_schema_id
  feature_count: i = 0,
  compute_time_ms: f = 0.0,
  error_code: s? = None,
  error_message: s? = None
}

// @Rule.P2_C_FVTD_TRANSPORT_PROTOCOL: CONTRACT.TransportProtocol, @Structure.P2_C_FV_FEATURE_REQUEST;
// @Rule.P2_C_FVTD_TOPIC_FVT: @Const.P2_C_PPCF_PULL_PATTERN_CONST, @Structure.P2_C_FV_FEATURE_REQUEST;

// @Rule.P2_C_FVTD_ENVELOPE: CONTRACT.MessageEnvelope, @Structure.P2_C_FVTD_FEATURE_RESPONSE;
// @Rule.P2_C_FVTD_META: @Structure.P2_C_FVTD_FEATURE_RESPONSE, @Structure.P2_C_BL_BUFFER_DESCRIPTOR;

// ═══════════════════════════════════════════════════════════════
// @DocMeta.P2_C_SEC5_FEATURE_STALE_DETECTION_OD_FT_1_TYPES_THRESHOLDS: §5 Feature Stale Detection (OD-FT-1) - Types & Thresholds
// ═══════════════════════════════════════════════════════════════
// @Rule.P2_C_FSD_TIMESTAMP_STALE: @Const.P2_C_FSD_STALE_THRESHOLD_MS_CONST, CONTRACT.ArrivalTimestamp;
// @Rule.P2_C_FSD_THRESHOLD: @Const.P2_C_FSD_STALE_THRESHOLD_MS_CONST, SSOT.InfraRTT;
// @Rule.P2_C_FSD_ENV_STALE_THRESHOLD: @Const.P2_C_FSD_STALE_THRESHOLD_MS_CONST;
// @Const.P2_C_FSD_STALE_THRESHOLD_MS_CONST: Feature stale threshold constant (ms, env override)
const STALE_THRESHOLD_MS = int(os.getenv("FEATURE_STALE_THRESHOLD_MS", "100"))
// -- end: P2_FSD_STALE_THRESHOLD_MS_CONST --


// @Structure.P2_C_FSD_STALE_MODE_ENUM: Stale handling mode enum (HARD_REJECT/LOGGING/DYNAMIC)
enum StaleMode { HARD_REJECT, LOGGING, DYNAMIC }

// ═══════════════════════════════════════════════════════════════
// @DocMeta.P2_C_SEC6_BACKPRESSURE_POLICY_OD_BP_1_DEPRECATED_CONSTANTS: §6 Backpressure Policy (OD-BP-1) - Deprecated Constants
// ═══════════════════════════════════════════════════════════════
// Phase1: Silent DROP + counter + error channel (hot path阻害しない)
// Phase2: Phase1 + 1%サンプリングログ (1週間運用安定後)
// Phase3: Autonomous フロー制御自動調整 (Phase2でデータ蓄積後)

// DEPRECATED RULE: R_MAX_MESSAGE_SIZE_1MB (Category D deletion candidate)
// DO NOT USE for new design or implementation.
// Reason: Message size cap duplicates /SSOT_Kernel/ssot_definitions.ts §2.2 BP_MAX_MESSAGE_SIZE_BYTES; rely on the SSOT constant instead.
// If necessary, refer to the latest SSOT documents (Plugin_Architecture_Standards_Manual / /SSOT_Kernel/ssot_definitions.ts).

// DEPRECATED RULE: R_WARNING_THRESHOLD_5 (Category D deletion candidate)
// DO NOT USE for new design or implementation.
// Reason: Warning threshold duplicates /SSOT_Kernel/ssot_definitions.ts §2.2 BP_WARN_THRESHOLD_PERCENT; use the SSOT definition.
// If necessary, refer to the latest SSOT documents (Plugin_Architecture_Standards_Manual / /SSOT_Kernel/ssot_definitions.ts).

// DEPRECATED RULE: R_CRITICAL_THRESHOLD_10 (Category D deletion candidate)
// DO NOT USE for new design or implementation.
// Reason: Critical threshold duplicates /SSOT_Kernel/ssot_definitions.ts §2.2 BP_CRITICAL_THRESHOLD_PERCENT; use the SSOT definition.
// If necessary, refer to the latest SSOT documents (Plugin_Architecture_Standards_Manual / /SSOT_Kernel/ssot_definitions.ts).

// ═══════════════════════════════════════════════════════════════
// @DocMeta.P2_C_SEC7_5_L2_HEARTBEAT_KEY_FORMAT_CONSTANTS_P2_HB_1: §7.5 L2 Heartbeat - Key Format & Constants (P2-HB-1)
// ═══════════════════════════════════════════════════════════════
// @Rule.P2_C_HBKF_KEY: @Const.P2_C_HBKF_L2_HEARTBEAT_CONST, SSOT.SafetyHeartbeat;
// @Rule.P2_C_HBKF_TTL: @Const.P2_C_HBKF_L2_HEARTBEAT_CONST, SSOT.SafetySettings;
// @Rule.P2_C_HBKF_INTERVAL: @Const.P2_C_HBKF_L2_HEARTBEAT_CONST, SSOT.SafetySettings;
// @Const.P2_C_HBKF_L2_HEARTBEAT_CONST: L2 heartbeat key/ttl/interval constants
const HEARTBEAT_KEY = "safety:heartbeat:market_data_adapter"
const HEARTBEAT_TTL_SEC = 6
const HEARTBEAT_INTERVAL_MS = 500
// -- end: P2_HBKF_L2_HEARTBEAT_CONST --


// ═══════════════════════════════════════════════════════════════
// Topic/Key Naming Conventions (Helper Formats)
// ═══════════════════════════════════════════════════════════════
// Feature Request Topic: feature:req:{model_id}
// Feature Response Topic: feature:resp:{trace_id}
// Buffer Registry Key: buffer:{buffer_id}
// Backpressure Stats Key: bp:stats:{component_id}
// Heartbeat Key: safety:heartbeat:{component_name}
// Buffer Heartbeat Key: buffer:heartbeat:{buffer_id}
```
