```typescript
// P1: Orchestration Core SDSL - CONTRACT / IO
// @Rule.P1_C_SPEC: CONTRACT.System5Orchestrator;
// IMPORTANT: Must Obay Stable ID Rules: Stable_ID_Base_Rules.md

// ═══════════════════════════════════════════════════════════════
// @DocMeta.P1_C_SEC1_LIFECYCLE_STATES_ENUMS: §1 LIFECYCLE STATES & ENUMS
// ═══════════════════════════════════════════════════════════════

// @Structure.P1_C_LCSE_SYSTEM_PHASE: SystemPhase covers all 16 lifecycle states
enum SystemPhase {
// Startup states
  OFFLINE = "offline",                 // 未起動（初期状態）
  INITIALIZING = "initializing",       // コンポーネント初期化中
  SYNCING = "syncing",                 // 取引所状態同期中
  WARMUP = "warmup",                   // Feature計算ウォームアップ
  READY = "ready",                     // 起動完了、取引待機

// Normal operation
  TRADING = "trading",                 // 通常取引中

// Abnormal states (ABN flows)
  PAUSED = "paused",                   // 一時停止（手動 or 軽微異常）
  PROTECTIVE_STOP = "protective_stop", // ABN-1: 即時停止（重大異常）
  DEGRADED = "degraded",               // ABN-3: 縮退運転中

// Recovery states (REC flows)
  RECOVERY_READY = "recovery_ready",   // 復旧準備完了
  WARMUP_RECOVERY = "warmup_recovery", // 復旧時ウォームアップ
  GUARDED_TRADING = "guarded_trading", // 段階的復帰中（25%→50%→75%→100%）

// Safe mode (MAN flows)
  SAFE_MODE = "safe_mode",             // Kill Switch L0 / メンテナンスモード
  EMERGENCY = "emergency",             // Kill Switch L1/L2

// Shutdown states
  STOPPING = "stopping",               // シャットダウン進行中
  STOPPED = "stopped",                 // 完全停止（終端状態）
  INIT_FAILED = "init_failed"          // 初期化失敗（終端状態）
}

// @Structure.P1_C_LCSE_TRANSITION_PRIORITY: TransitionPriority defines processing order
// 安全 > 復旧 > 通常 の優先順位で遷移を処理
enum TransitionPriority {
  EMERGENCY = 0,   // Kill Switch L2 連動 (最高優先度)
  CRITICAL = 1,    // Kill Switch L0/L1, Emergency Stop
  HIGH = 2,        // Degradation, Safe Mode
  NORMAL = 3,      // Recovery, Mode switch
  LOW = 4          // Routine state updates
}

// @Rule.P1_C_STATE_LCSE_DEGRADATION_LEVEL: @Structure.P1_C_LCSE_DEGRADATION_LEVEL_ENUM;
// 📌 KillLevel との名前衝突を解消した新命名
// @Structure.P1_C_LCSE_DEGRADATION_LEVEL_ENUM: Degradation level enum (FULL/PARTIAL/MINIMAL/DISABLED)
enum DegradationLevel {
  FULL = "full",           // 100% フル稼働
  PARTIAL = "partial",     // 60-80% 縮退運転
  MINIMAL = "minimal",     // 20-40% 最小限
  DISABLED = "disabled"    // 0% 完全停止
}

// Backward compatibility aliases (deprecated)
// DEPRECATED RULE: D_DEG_ALIAS (Category D deletion candidate)
// DO NOT USE for new design or implementation.
// Reason: Legacy degradation aliases are superseded by the DegradationLevel enum and must not be referenced.
// If necessary, refer to the latest SSOT documents (Plugin_Architecture_Standards_Manual / /SSOT_Kernel/ssot_definitions.ts).

// ═══════════════════════════════════════════════════════════════
// @DocMeta.P1_C_SEC2_SYSTEM_STATE_DATACLASS: §2 SYSTEM STATE DATACLASS
// ═══════════════════════════════════════════════════════════════

// @Rule.P1_C_SSDC_STATE_STRUCTURE: @Structure.P1_C_SSDC_SYSTEM_STATE;
// @SSOTRef.P1_C_SSDC_REF: SSOT.SYSTEM_STATE_SCHEMA;
// @SSOTRef.P1_C_SSDC_RULE: SSOT.RULE_STATE_SYSTEM_STATE_CANONICAL;
// @Structure.P1_C_SSDC_SYSTEM_STATE: System state canonical snapshot schema
struct SystemState {
  // === Redis Hash fields (system:state) ===
  phase: SystemPhase,
  previous_phase: SystemPhase?,
  entered_at_ns: i,                // int64 ns UTC (SSOT naming convention)
  degradation_level: DegradationLevel,
  trading_safe: s = "off",         // TradingSafeMode: "off" | "partial" | "full"
  config_safe: b = false,          // Config changes blocked
  reason: s = "",                  // 直近の状態遷移理由
  operator_id: s?,                 // 遷移を起こした operator (自動遷移時は null)
  maintenance_mode: s = "off",     // "off" | "scheduled" | "safety_redis_down" (H-1 Gap Fix)
  maintenance_reason: s = "",

  // === Local in-memory view only (NOT written to Redis Hash) ===
  component_health: d[s, s]        // ローカル集計用、Redis には orch:components:{id} で別管理
}

// ═══════════════════════════════════════════════════════════════
// @DocMeta.P1_C_SEC3_STATE_MACHINE_TRANSITION_MAP: §3 STATE MACHINE TRANSITION MAP
// ═══════════════════════════════════════════════════════════════

// @Rule.P1_C_SMT_COMPLETE_TRANSITION_MAP: @Const.P1_C_SMT_ALLOWED_TRANSITIONS_MAP;
// @Const.P1_C_SMT_ALLOWED_TRANSITIONS_MAP: Allowed transitions map (SystemPhase -> next phases)
const ALLOWED_TRANSITIONS: d[SystemPhase, [SystemPhase]] = {
  // === Startup Flow ===
  SystemPhase.OFFLINE: [SystemPhase.INITIALIZING],
  SystemPhase.INITIALIZING: [SystemPhase.SYNCING, SystemPhase.INIT_FAILED, SystemPhase.STOPPING],
  SystemPhase.SYNCING: [SystemPhase.WARMUP, SystemPhase.INIT_FAILED, SystemPhase.STOPPING],
  SystemPhase.WARMUP: [SystemPhase.READY, SystemPhase.DEGRADED, SystemPhase.SAFE_MODE, SystemPhase.STOPPING],
  SystemPhase.READY: [SystemPhase.TRADING, SystemPhase.PAUSED, SystemPhase.STOPPING],

  // === Normal Operation ===
  SystemPhase.TRADING: [SystemPhase.PAUSED, SystemPhase.PROTECTIVE_STOP, SystemPhase.DEGRADED, SystemPhase.SAFE_MODE, SystemPhase.EMERGENCY, SystemPhase.STOPPING],

  // === Abnormal States ===
  SystemPhase.PAUSED: [SystemPhase.TRADING, SystemPhase.RECOVERY_READY, SystemPhase.PROTECTIVE_STOP, SystemPhase.SAFE_MODE, SystemPhase.STOPPING],
  SystemPhase.PROTECTIVE_STOP: [SystemPhase.RECOVERY_READY, SystemPhase.SAFE_MODE, SystemPhase.EMERGENCY, SystemPhase.STOPPING],
  SystemPhase.DEGRADED: [SystemPhase.TRADING, SystemPhase.RECOVERY_READY, SystemPhase.PROTECTIVE_STOP, SystemPhase.SAFE_MODE, SystemPhase.EMERGENCY, SystemPhase.STOPPING],

  // === Recovery Flow ===
  SystemPhase.RECOVERY_READY: [SystemPhase.WARMUP_RECOVERY, SystemPhase.STOPPING],
  SystemPhase.WARMUP_RECOVERY: [SystemPhase.GUARDED_TRADING, SystemPhase.PROTECTIVE_STOP, SystemPhase.STOPPING],
  SystemPhase.GUARDED_TRADING: [SystemPhase.TRADING, SystemPhase.PAUSED, SystemPhase.PROTECTIVE_STOP, SystemPhase.SAFE_MODE, SystemPhase.STOPPING],

  // === Safe Mode ===
  SystemPhase.SAFE_MODE: [SystemPhase.RECOVERY_READY, SystemPhase.EMERGENCY, SystemPhase.STOPPING],
  SystemPhase.EMERGENCY: [SystemPhase.RECOVERY_READY, SystemPhase.STOPPING],

  // === Shutdown (Terminal) ===
  SystemPhase.STOPPING: [SystemPhase.STOPPED],
  SystemPhase.STOPPED: [],      // Terminal
  SystemPhase.INIT_FAILED: []   // Terminal
}

// ═══════════════════════════════════════════════════════════════
// @DocMeta.P1_C_SEC4_CIRCUIT_BREAKER_TYPES: §4 CIRCUIT BREAKER TYPES
// ═══════════════════════════════════════════════════════════════
//　@Structure.P1_C_CBT_CIRCUIT_STATE_ENUM: Circuit breaker state enum (CLOSED/OPEN/HALF_OPEN)
enum CircuitState { CLOSED = "closed", OPEN = "open", HALF_OPEN = "half_open" }

// @Rule.P1_C_CBT_CIRCUIT_BREAKER_CONFIG: @Structure.P1_C_CBT_CIRCUIT_BREAKER_CONFIG;
// @Structure.P1_C_CBT_CIRCUIT_BREAKER_CONFIG: Circuit breaker configuration schema
struct CircuitBreakerConfig {
  error_threshold: i = 5,              // 連続エラー閾値
  cooldown_seconds: f = 30.0,          // OPEN状態の継続時間
  listener_timeout_seconds: f = 5.0    // リスナ実行タイムアウト
}
// @Structure.P1_C_CBT_LISTENER_STATE: Circuit breaker listener runtime state schema
struct ListenerState {
  consecutive_errors: i = 0,
  circuit_state: CircuitState = CircuitState.CLOSED,
  last_failure_time: f = 0.0,
  total_calls: i = 0,
  total_errors: i = 0
}

// ═══════════════════════════════════════════════════════════════
// @DocMeta.P1_C_SEC5_DEGRADATION_RULES_DATA: §5 DEGRADATION RULES DATA
// ═══════════════════════════════════════════════════════════════

// @Rule.P1_C_DEG_STRUCTURE: @Const.P1_C_DEG_DEGRADATION_RULES_TABLE;
// @Const.P1_C_DEG_DEGRADATION_RULES_TABLE: Degradation rules table (critical + thresholds)
const DEGRADATION_RULES = {
  critical: {
    // Must-Survive: CRITICAL → DISABLED (即時停止)
    "kill_switch": DegradationLevel.DISABLED,
    "orchestrator": DegradationLevel.DISABLED,
    "feature_pipeline": DegradationLevel.DISABLED,
    "model_pipeline": DegradationLevel.DISABLED,

// @DocMeta.P1_C_SEC4_7_1_LV1_MUST_SURVIVE_CRITICAL_DISABLED_KILL_L1: §4.7.1 Lv1 Must Survive: CRITICAL → DISABLED + Kill L1
    "market_data_adapter": DegradationLevel.DISABLED,
    "order_gateway": DegradationLevel.DISABLED,

// @DocMeta.P1_C_SEC4_7_1_LV2_SHOULD_SURVIVE_CLOSE_ONLY: §4.7.1 Lv2 Should Survive: Close Only モード
    "strategy_pipeline": DegradationLevel.MINIMAL,

    // L7 Operations: 監視のみなので CRITICAL でも稼働継続
    "health_aggregator": DegradationLevel.FULL
  },
  warning_thresholds: {
    2: DegradationLevel.PARTIAL,
    4: DegradationLevel.MINIMAL
  }
}

// ═══════════════════════════════════════════════════════════════
// @DocMeta.P1_C_SEC6_GUARDED_TRADING_TYPES: §6 GUARDED TRADING TYPES
// ═══════════════════════════════════════════════════════════════
// @Structure.P1_C_GTT_RECOVERY_STAGE_ENUM: Recovery stage enum (STAGE_1..4)
enum RecoveryStage { STAGE_1 = "stage_1", STAGE_2 = "stage_2", STAGE_3 = "stage_3", STAGE_4 = "stage_4" }

// @Rule.P1_C_GTT_RECOVERY_STAGE_CONFIG: @Structure.P1_C_GTT_RECOVERY_STAGE_CONFIG_SCHEMA;
// @Structure.P1_C_GTT_RECOVERY_STAGE_CONFIG_SCHEMA: Recovery stage configuration schema
struct RecoveryStageConfig {
  stage: RecoveryStage,
  capacity_percent: i,
  description: s,
  validation_criteria: [s],
  min_duration_seconds: i,
  auto_advance: b
}

// @Rule.P1_C_GTT_RECOVERY_STAGE_TYPES: @Const.P1_C_GTT_RECOVERY_STAGES_TABLE;
// @Const.P1_C_GTT_RECOVERY_STAGES_TABLE: Canonical recovery stages table (25/50/75/100)
const RECOVERY_STAGES: [RecoveryStageConfig] = [
  RecoveryStageConfig{stage: RecoveryStage.STAGE_1, capacity_percent: 25,
    description: "Position sync verification",
    validation_criteria: ["position_sync_complete", "balance_reconciled", "no_orphan_orders"],
    min_duration_seconds: 60, auto_advance: true},
  RecoveryStageConfig{stage: RecoveryStage.STAGE_2, capacity_percent: 50,
    description: "Small test orders",
    validation_criteria: ["test_order_success", "latency_within_threshold", "no_execution_errors"],
    min_duration_seconds: 120, auto_advance: true},
  RecoveryStageConfig{stage: RecoveryStage.STAGE_3, capacity_percent: 75,
    description: "Limited trading",
    validation_criteria: ["pnl_within_expected", "risk_metrics_normal", "no_anomalies_detected"],
    min_duration_seconds: 300, auto_advance: false},  // Operator confirmation required
  RecoveryStageConfig{stage: RecoveryStage.STAGE_4, capacity_percent: 100,
    description: "Awaiting operator approval",
    validation_criteria: ["all_systems_nominal", "operator_approval"],
    min_duration_seconds: 0, auto_advance: false}  // Final approval required
]

// @Structure.P1_C_GTT_GUARDED_TRADING_STATE: Guarded trading runtime state schema
struct GuardedTradingState {
  current_stage: RecoveryStage,
  capacity_percent: i,
  stage_entered_at: ts,
  validation_status: d[s, b],
  pending_approval: b = false
}

// ═══════════════════════════════════════════════════════════════
// @DocMeta.P1_C_SEC7_TWO_AXIS_SAFE_MODE_TYPES: §7 TWO-AXIS SAFE MODE TYPES
// ═══════════════════════════════════════════════════════════════

// @Structure.P1_C_TSM_TRADING_SAFE_MODE_ENUM: TradingSafeMode enum (OFF/PARTIAL/FULL)
enum TradingSafeMode { OFF = "off", PARTIAL = "partial", FULL = "full" }

// @Rule.P1_C_TSM_CONSTRAINTS_STRUCTURE: @Structure.P1_C_TSM_TRADING_SAFE_MODE_CONSTRAINTS;
// @Structure.P1_C_TSM_TRADING_SAFE_MODE_CONSTRAINTS: Trading safe mode constraints schema
struct TradingSafeModeConstraints {
  mode: TradingSafeMode,
  new_position_allowed: b,
  position_limit_percent: i,
  order_types_allowed: [s],
  close_position_allowed: b
}

// @Rule.P1_C_TSM_CONSTRAINTS_MODE: @Const.P1_C_TSM_CONSTRAINTS_MODE;
// @Const.P1_C_TSM_CONSTRAINTS_MODE: Trading safe mode constraints
const TRADING_SAFE_CONSTRAINTS: d[TradingSafeMode, TradingSafeModeConstraints] = {
  TradingSafeMode.OFF: TradingSafeModeConstraints{
    mode: TradingSafeMode.OFF, new_position_allowed: true,
    position_limit_percent: 100, order_types_allowed: ["LIMIT", "MARKET", "STOP", "STOP_LIMIT"],
    close_position_allowed: true},
  TradingSafeMode.PARTIAL: TradingSafeModeConstraints{
    mode: TradingSafeMode.PARTIAL, new_position_allowed: true,
    position_limit_percent: 50, order_types_allowed: ["LIMIT"],
    close_position_allowed: true},
  TradingSafeMode.FULL: TradingSafeModeConstraints{
    mode: TradingSafeMode.FULL, new_position_allowed: false,
    position_limit_percent: 0, order_types_allowed: ["LIMIT"],
    close_position_allowed: true}
}

// ═══════════════════════════════════════════════════════════════
// @DocMeta.P1_C_SEC8_GRACEFUL_DEGRADATION_TYPES: §8 GRACEFUL DEGRADATION TYPES
// ═══════════════════════════════════════════════════════════════

// @Rule.P1_C_GDT_PRIORITY_ENUM: @Structure.P1_C_GDT_COMPONENT_PRIORITY_ENUM;
// @Structure.P1_C_GDT_COMPONENT_PRIORITY_ENUM: Component priority enum (LV1/LV2/LV3)
enum ComponentPriority {
  LV1_MUST_SURVIVE = "lv1_must_survive",    // L2, L6, L7
  LV2_SHOULD_SURVIVE = "lv2_should_survive", // L5
  LV3_OPTIONAL = "lv3_optional"              // L3, L4
}

// @Rule.P1_C_GDT_L2_FAILURE_CONFIG: @Structure.P1_C_GDT_L2_FAILURE_CONFIG_SCHEMA;
// @Note.P1_C_GDT_L2_FAILURE_CONFIG: no_data_timeout_sec is L2-specific market data staleness detection, distinct from Watchdog L0 threshold (5s per SSOT §4.5). This shorter timeout (3s) triggers reconnect attempt before escalating to Kill Switch. kill_switch_delay_sec (5s) aligns with L0.
// @Structure.P1_C_GDT_L2_FAILURE_CONFIG_SCHEMA: L2 market data failure detection config schema
struct L2FailureConfig {
  ws_disconnect_trigger: b = true,
  no_data_timeout_sec: f = 3.0,         // L2 market data staleness (NOT Watchdog L0)
  reconnect_attempt_on_detect: i = 1,   // 誤検知防止: 即座に1回再接続
  kill_switch_delay_sec: f = 5.0        // Watchdog L0 threshold (SSOT §4.5) - 復帰しなければ L1 移行
}

// @Rule.P1_C_GDT_GRACEFUL_DEGRADATION_CONFIG: @Structure.P1_C_GDT_GRACEFUL_DEGRADATION_CONFIG;
// @Structure.P1_C_GDT_GRACEFUL_DEGRADATION_CONFIG: Graceful degradation config (Kill経路一本化)
struct GracefulDegradationConfig {
  // Lv 1: Must Survive (L2, L6, L7)
  lv1_action: s = "PROTECTIVE_STOP",
  lv1_blind_state_block_orders: b = true,
  lv1_kill_cmd: s = "KILL_L1",          // safety:cmd に送信

  // Lv 2: Should Survive (L5)
  lv2_action: s = "CLOSE_ONLY",
  lv2_reduce_only_flag: b = true,
  lv2_allowed_order_types: [s] = ["LIMIT", "MARKET"],

  // Lv 3: Optional (L3, L4)
  lv3_action: s = "DEGRADED",
  lv3_new_entry_blocked: b = true,
  lv3_close_position_allowed: b = true
}
// @Rule.P1_C_GDT_COMPONENT_PRIORITY_MAP: @Const.P1_C_GDT_COMPONENT_PRIORITY_MAP_TABLE;
// @Const.P1_C_GDT_COMPONENT_PRIORITY_MAP_TABLE: Component -> priority canonical mapping table
const COMPONENT_PRIORITY_MAP: d[s, ComponentPriority] = {
  "L2_Data": ComponentPriority.LV1_MUST_SURVIVE,
  "L6_Execution": ComponentPriority.LV1_MUST_SURVIVE,
  "L7_Risk": ComponentPriority.LV1_MUST_SURVIVE,
  "L5_Strategy": ComponentPriority.LV2_SHOULD_SURVIVE,
  "L3_Feature": ComponentPriority.LV3_OPTIONAL,
  "L4_Model": ComponentPriority.LV3_OPTIONAL
}

// @Rule.P1_C_GDT_MANUAL_RECOVERY_CONFIG: @Structure.P1_C_GDT_MANUAL_RECOVERY_CONFIG_SCHEMA;
// @Structure.P1_C_GDT_MANUAL_RECOVERY_CONFIG_SCHEMA: Manual recovery configuration schema
struct ManualRecoveryConfig {
  auto_escalation: b = false,
  require_signed_request: b = true,
  recovery_endpoint: s = "/api/system/recover",
  audit_action: s = "MANUAL_RECOVERY",
  required_audit_fields: [s] = ["operator_id", "trace_id"]
}

// ═══════════════════════════════════════════════════════════════
// @DocMeta.P1_C_SEC9_HEALTH_AGGREGATION_TYPES: §9 HEALTH AGGREGATION TYPES
// ═══════════════════════════════════════════════════════════════

// @Rule.P1_C_HAT_HEALTH_CHECK_RESPONSE_ENUM: @Structure.P1_C_HAT_HEALTH_CHECK_RESPONSE;
// @Ref.P1_C_HAT_SSOT_ENUM: SSOT.R_INFRA_HEALTH_STATUS_ENUM;
// @Structure.P1_C_HAT_HEALTH_CHECK_RESPONSE: Health check response schema (COM-20)
struct HealthCheckResponse {
  component_id: s,
  // @Rule.P1_C_HAT_SSOT_ENUM_VALUES: SSOT.HEALTH_STATUS_VALUES;
  status: HealthStatus,
  timestamp_ns: i,
  response_time_ms: f,
  message: s?,
  metrics: d?,
  dependencies: d[s, s]?
}

// @Rule.P1_C_HAT_AGGREGATED_HEALTH_RESPONSE: @Structure.P1_C_HAT_AGGREGATED_HEALTH_RESPONSE;
// @Structure.P1_C_HAT_AGGREGATED_HEALTH_RESPONSE: Aggregated health response schema
struct AggregatedHealthResponse {
  system_status: s,         // "HEALTHY" | "DEGRADED" | "CRITICAL"
  timestamp_ns: i,
  components: d[s, HealthCheckResponse],
  degradation_level: s,
  active_alerts: [s],
  summary: s
}

// ═══════════════════════════════════════════════════════════════
// @DocMeta.P1_C_SEC10_BASELINE_ACTOR_TYPES: §10 BASELINE ACTOR TYPES
// ═══════════════════════════════════════════════════════════════

// @Rule.P1_C_BAT_CONFIG: @Structure.P1_C_BAT_BASELINE_ACTOR_CONFIG;
// @Structure.P1_C_BAT_BASELINE_ACTOR_CONFIG: Baseline actor configuration schema
struct BaselineActorConfig {
  enabled: b = false,
  diagnostics_only: b = true,
  health_report_interval_sec: i = 10,
  log_level: s = "DEBUG"
}
// @Structure.P1_C_BAT_DIAGNOSTICS_REPORT: Diagnostics report payload schema emitted by baseline actor.
struct DiagnosticsReport {
  timestamp: ts,
  system_phase: s,
  degradation_level: s,
  component_status: d[s, s],
  memory_usage_mb: f,
  cpu_percent: f,
  redis_latency_ms: f,
  exchange_connectivity: b,
  last_market_update_age_sec: f
}

// ═══════════════════════════════════════════════════════════════
// @DocMeta.P1_C_SEC11_COMPONENT_DEPENDENCY_TYPES: §11 COMPONENT DEPENDENCY TYPES
// ═══════════════════════════════════════════════════════════════
// @Structure.P1_C_CODT_DEFINITION_ENUM: Component definition with dependency graph
enum ComponentType {
  SAFETY = "safety", ORCHESTRATOR = "orchestrator", FEATURE = "feature",
  MODEL = "model", STRATEGY = "strategy", EXECUTION = "execution", OPS = "ops"
}

// @Rule.P1_C_CODT_COMPONENTS_LIST: @Structure.P1_C_CODT_COMPONENT_DEFINITION;
// @Structure.P1_C_CODT_COMPONENT_DEFINITION: Component definition schema (deps + timeouts)
struct ComponentDefinition {
  component_id: s,
  component_type: ComponentType,
  phase: i,                          // 起動Phase (1-7)
  depends_on: [s] = [],              // 必須依存 (起動前に必要)
  soft_depends_on: [s] = [],         // オプション依存
  startup_timeout_ms: i = 30000,
  // @Ref.P1_C_CODT_GRACEFUL_SHUTDOWN: CONTRACT.GracefulShutdownPolicy;
  shutdown_timeout_ms: i = 10000,
  health_check_interval_ms: i = 5000
}

// @Rule.P1_C_CODT_STARTUP_PHASES: @Const.P1_C_CODT_STARTUP_PHASES_MAP;
// @Const.P1_C_CODT_STARTUP_PHASES_MAP: phase -> component_ids
const STARTUP_PHASES: d[i, [s]] = {
  1: ["safety_redis", "safety_monitor"],
  2: ["app_redis", "postgres"],
  3: ["orchestrator"],
  4: ["feature_pipeline"],
  5: ["model_manager"],
  6: ["strategy_engine"],
  7: ["ops_dashboard"]
}

// @Rule.P1_C_CODT_SHUTDOWN_ORDER: @Const.P1_C_CODT_SHUTDOWN_TIMEOUT_PER_PHASE_SEC;
// 各フェーズ 10秒タイムアウト (Ref: @Rule.P1_C_18)
// @Const.P1_C_CODT_SHUTDOWN_TIMEOUT_PER_PHASE_SEC: Timeout per shutdown phase (sec)
const SHUTDOWN_TIMEOUT_PER_PHASE_SEC = 10
// -- end: P1_CODT_SHUTDOWN_TIMEOUT_PER_PHASE_SEC --

// ═══════════════════════════════════════════════════════════════
// @DocMeta.P1_C_SEC12_EVENTS_MESSAGE_BUS_TYPES: §12 EVENTS & MESSAGE BUS TYPES
// ═══════════════════════════════════════════════════════════════
// @Structure.P1_C_EMBT_EVENT_TYPE_ENUM: EventType values for events/message bus
enum EventType {
  // Lifecycle events
  PHASE_CHANGED = "phase_changed",
  COMPONENT_STARTED = "component_started",
  COMPONENT_STOPPED = "component_stopped",
  COMPONENT_FAILED = "component_failed",

  // Health events
  HEALTH_UPDATE = "health_update",
  DEGRADATION_DETECTED = "degradation_detected",
  RECOVERY_STARTED = "recovery_started",
  RECOVERY_COMPLETED = "recovery_completed",

  // Kill switch events
  KILL_SWITCH_ACTIVATED = "kill_switch_activated",
  KILL_SWITCH_RESET = "kill_switch_reset"
}

// @Rule.P1_C_EMBT_ORCHESTRATOR_EVENT_STRUCTURE: CONTRACT.MessageEnvelope, @Structure.P1_C_EMBT_ORCHESTRATOR_EVENT;
// @Structure.P1_C_EMBT_ORCHESTRATOR_EVENT: Orchestrator event schema aligned with MessageEnvelope
struct OrchestratorEvent {
  event_type: EventType,
  trace_id: s,
  sequence_id: i = 0,
  source: s = "orchestrator",
  server_ts_ns: i,   // int64 ns - publication time
  origin_ts_ns: i,   // int64 ns - event generation time
  schema_id: s = "",
  version: s = "1.0.0",
  content_type: s = "json",
  payload: d,
  meta: d
}

// ═══════════════════════════════════════════════════════════════
// @DocMeta.P1_C_SEC13_STATE_API_TYPES: §13 STATE API TYPES
// ═══════════════════════════════════════════════════════════════

// @Rule.P1_C_SAPI_REDIS_KEYS: @Const.P1_C_SAPI_STATE_REDIS_CONSTANTS;
// @Const.P1_C_SAPI_STATE_REDIS_CONSTANTS: State publishing Redis key + TTL constants
const STATE_REDIS_KEY = "system:state"
const STATE_TTL_SECONDS = 5
// -- end: P1_SAPI_STATE_REDIS_CONSTANTS --


// @Rule.P1_C_SAPI_RECOVERY_PHASE_ENUM: @Structure.P1_C_SAPI_RECOVERY_PHASE_ENUM_DEF;
// @Structure.P1_C_SAPI_RECOVERY_PHASE_ENUM_DEF: Recovery phase enum definition
enum RecoveryPhase {
  INITIATED = "initiated",
  VALIDATING = "validating",
  RESTORING = "restoring",
  VERIFYING = "verifying",
  COMPLETED = "completed",
  FAILED = "failed"
}

// @Rule.P1_C_SAPI_GUARDED_TRADING_STAGES_STRUCTURE: @Structure.P1_C_SAPI_GUARDED_TRADING_CONTRACT;
// @Structure.P1_C_SAPI_GUARDED_TRADING_CONTRACT: Guarded trading per-stage contract schema
struct GuardedTradingContract {
  stage: i,                       // 1-4
  capacity_percent: i,            // 25, 50, 75, 100
  max_position_ratio: f,
  allowed_order_types: [s],
  require_operator_approval: b
}
// @Rule.P1_C_SAPI_GUARDED_TRADING_STAGES: @Const.P1_C_SAPI_GUARDED_TRADING_STAGES;
// @Const.P1_C_SAPI_GUARDED_TRADING_STAGES: Canonical per-stage guarded trading constraints table.
const GUARDED_TRADING_STAGES: d[i, GuardedTradingContract] = {
  1: GuardedTradingContract{stage: 1, capacity_percent: 25, max_position_ratio: 0.25, allowed_order_types: ["LIMIT"], require_operator_approval: false},
  2: GuardedTradingContract{stage: 2, capacity_percent: 50, max_position_ratio: 0.50, allowed_order_types: ["LIMIT"], require_operator_approval: false},
  3: GuardedTradingContract{stage: 3, capacity_percent: 75, max_position_ratio: 0.75, allowed_order_types: ["LIMIT", "MARKET"], require_operator_approval: true},
  4: GuardedTradingContract{stage: 4, capacity_percent: 100, max_position_ratio: 1.00, allowed_order_types: ["LIMIT", "MARKET", "STOP"], require_operator_approval: true}
}

// @Rule.P1_C_SAPI_BASELINE_ACTOR_CONTRACT: @Structure.P1_C_SAPI_BASELINE_ACTOR_CONTRACT_SCHEMA;
// @Structure.P1_C_SAPI_BASELINE_ACTOR_CONTRACT_SCHEMA: Baseline actor contract schema
struct BaselineActorContract {
  trigger_condition: s = "degradation_level == DISABLED",
  input_source: s = "feature_pipeline",
  output_action: s = "LOG_ONLY",  // "LOG_ONLY" | "FLAT_POSITION" | "HEDGE"
  diagnostics_interval_sec: i = 10
}

// ═══════════════════════════════════════════════════════════════
// @DocMeta.P1_C_SEC14_SNAPSHOT_RECOVERY_TYPES: §14 SNAPSHOT & RECOVERY TYPES
// ═══════════════════════════════════════════════════════════════

// @Rule.P1_C_SSRT_SNAPSHOT_CONFIG: @Structure.P1_C_SSRT_SNAPSHOT_CONFIG_SCHEMA;
// @Structure.P1_C_SSRT_SNAPSHOT_CONFIG_SCHEMA: Snapshot configuration schema
struct SnapshotConfig {
  redis_key_prefix: s = "snapshot:",
  disk_path: s = "./data/snapshots",
  restore_on_startup: b = false,   // Opt-in only
  cli_flag: s = "--restore-snapshot",
  keep_last_n: i = 5
}

// @Rule.P1_C_SSRT_SNSRT_REDIS_STATE_KEYS: CONTRACT.RedisStateKeys;

// ═══════════════════════════════════════════════════════════════
// @DocMeta.P1_C_SEC15_CREDENTIAL_MANAGEMENT_TYPES_H_3_GAP_FIX: §15 CREDENTIAL MANAGEMENT TYPES (H-3 Gap Fix)
// ═══════════════════════════════════════════════════════════════

// @Rule.P1_C_CRED_CREDENTIAL_SCOPE_ENUM: @Structure.P1_C_CRED_CREDENTIAL_SCOPE_ENUM_DEF;
// @Structure.P1_C_CRED_CREDENTIAL_SCOPE_ENUM_DEF: Credential scope enum definition
enum CredentialScope {
  INTERNAL_HMAC = "internal_hmac",
  EXCHANGE_API_KEY = "exchange_api_key",
  WEBHOOK_SECRET = "webhook_secret"
}

// @Rule.P1_C_CRED_KEY_VERSION_STRUCTURE: @Structure.P1_C_CRED_KEY_VERSION;
// @Structure.P1_C_CRED_KEY_VERSION: Key version schema (single credential version)
struct KeyVersion {
  version_id: s,
  secret_material: s,        // SecureString (encrypted or protected)
  valid_from: ts,
  expires_at: ts?
}

// @Rule.P1_C_CRED_ACTIVE_CREDENTIAL_SET_STRUCTURE: @Structure.P1_C_CRED_ACTIVE_CREDENTIAL_SET;
// @Structure.P1_C_CRED_ACTIVE_CREDENTIAL_SET: Active credential set schema (primary/secondary/revoked)
struct ActiveCredentialSet {
  primary_key: KeyVersion,
  secondary_keys: [KeyVersion],  // Grace Period中の旧鍵
  revoked_ids: [s]               // メモリキャッシュ破棄用
}

// @Rule.P1_C_CRED_CREDENTIAL_MANAGER_INTERFACE: @Interface.P1_C_CRED_CREDENTIAL_MANAGER;
// @Interface.P1_C_CRED_CREDENTIAL_MANAGER: CredentialManager interface (Orchestrator authority)
interface CredentialManager {
  // @Rule.P1_C_CRED_WAL_WRITE_ROTATION_EVENTS: CONTRACT.CredentialRotationPolicy;
  // @Rule.P1_C_CRED_ADMIN_ONLY: CONTRACT.AdminAuthRequired;
  f rotate_credential(
    scope: CredentialScope,
    new_secret_payload: s,       // SecureString
    grace_period_ms: i
  ) -> Result<KeyVersion, Error>

  // @Rule.P1_C_CRED_WAL_WRITE_EXPIRED_EVENTS: CONTRACT.CredentialRevocationPolicy;
  // @Rule.P1_C_CRED_IMMEDIATE_EFFECT: CONTRACT.ImmediateRevocationConsistency;
  f revoke_credential(
    scope: CredentialScope,
    version_id: s
  ) -> Result<d, Error>

  // @Rule.P1_C_CRED_INTERNAL_ONLY: CONTRACT.InternalAccessOnly;
  f get_active_credentials(scope: CredentialScope) -> Result<ActiveCredentialSet, Error>
}
```
