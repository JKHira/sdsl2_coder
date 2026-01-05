```typescript
// P4: Operations Code Plan - CONTRACT / IO SDSL
// Data contracts, types, I/F definitions, config schemas
// SSOT: Manual Intervention, Dashboard, Health API, Reconciliation
// IMPORTANT: Must Obay Stable ID Rules: Stable_ID_Base_Rules.md

// ─────────────────────────────────────────────────────────────────────
// @DocMeta.P4_C_SEC1_ENUMS_DATA_CONTRACTS: §1 Enums (Data Contracts)
// ─────────────────────────────────────────────────────────────────────

// @Structure.P4_C_EDC_ENUM_PARAMETER_CATEGORY: Parameter category enum
enum ParameterCategory { RISK="risk",EXECUTION="execution",FEATURE="feature",MODEL="model" }

// ParameterCategory.RISK: max_position,max_drawdown | EXECUTION: slippage,timeout | FEATURE: warmup_period,cache_ttl | MODEL: confidence_threshold
// @Structure.P4_C_EDC_ENUM_OPERATION_MODE: Operation mode enum
enum OperationMode { LIVE="live",PAPER="paper",OBSERVATION="observation",MAINTENANCE="maintenance" }

// @Structure.P4_C_EDC_ENUM_AUDIT_ACTION: Audit action enum
enum AuditAction { KILL_SWITCH_ACTIVATED,KILL_SWITCH_RESET,PARAMETER_CHANGED,STRATEGY_TOGGLED,MODE_SWITCHED,META_STRATEGY_CHANGED,LOGIN,LOGOUT,POSITION_FLATTENED,AUTO_EXIT_TRIGGERED }

// @Structure.P4_C_EDC_ENUM_SSE_AUTH_MODE: SSE authentication mode enum
enum SSEAuthMode { NONE="none",QUERY_TOKEN="query_token",API_KEY="api_key",SESSION="session",MTLS="mtls" }

// @Structure.P4_C_EDC_ENUM_CONFIG_SAFE: ConfigSafe axis enum
enum ConfigSafe { OFF,ON }

// @Structure.P4_C_EDC_ENUM_TRADING_SAFE: TradingSafe axis enum
enum TradingSafe { OFF,PARTIAL,FULL }

// ─────────────────────────────────────────────────────────────────────
// @DocMeta.P4_C_SEC2_MAN_COMMANDS_DATA_STRUCTURES_CQRS_PATTERN: §2 MAN Commands - Data Structures (CQRS Pattern)
// ─────────────────────────────────────────────────────────────────────

// @Structure.P4_C_CQRS_MAN_PARAMETER_CHANGE_COMMAND: MAN parameter change command schema
struct ParameterChangeCommand { command_id:U,category:ParameterCategory=RISK,parameter_key:s,old_value:s,new_value:s,reason:s,operator_id:s,timestamp:ts,signature:s }

// @Structure.P4_C_CQRS_MAN_PARAMETER_CHANGE_ACK: MAN parameter change ack schema
struct ParameterChangeAck { ack_id:U,command_id:U,executed_at:ts,success:b,rollback_available:b,rollback_deadline:ts?,error_message:s="" }

// @Rule.P4_C_CQRS_ROLLBACK: SSOT.ROLLBACK_WINDOW, @Structure.P4_C_CQRS_MAN_PARAMETER_CHANGE_ACK;
// @Structure.P4_C_CQRS_MAN_STRATEGY_TOGGLE_COMMAND: MAN strategy toggle command schema
struct StrategyToggleCommand { command_id:U,strategy_id:s,enabled:b,cancel_open_orders:b=T,force_close_positions:b=F,reason:s,operator_id:s,timestamp:ts,signature:s }

// @Structure.P4_C_CQRS_MAN_STRATEGY_TOGGLE_ACK: MAN strategy toggle ack schema
struct StrategyToggleAck { ack_id:U,command_id:U,executed_at:ts,success:b,previous_state:b,current_state:b,active_positions_handled:b,positions_remaining:i=0 }

// @Rule.P4_C_CQRS_TOGGLE_DEFAULT: SSOT.TOGGLE_DEFAULT_BEHAVIOR, @Structure.P4_C_CQRS_MAN_STRATEGY_TOGGLE_COMMAND;
// @Structure.P4_C_CQRS_MAN_MANUAL_FLATTEN_COMMAND: MAN manual flatten command schema
struct ManualFlattenCommand { command_id:U,strategy_id:s,order_type:"market"|"limit"="limit",limit_offset_bps:i=5,operator_id:s,confirmation_code:s,timestamp:ts,signature:s }

// @Rule.P4_C_CQRS_FLATTEN: SSOT.CONFIRMATION_CODE_REQUIREMENT, @Structure.P4_C_CQRS_MAN_MANUAL_FLATTEN_COMMAND;
// @Structure.P4_C_CQRS_MAN_AUTO_EXIT_CONFIG: Auto-exit configuration schema
struct AutoExitConfig { algorithm:"vwap"|"twap"|"pov"="twap",duration_minutes:i=30,max_participation_rate:f=0.1,urgency:"passive"|"normal"|"aggressive"="normal" }

// @Rule.P4_C_CQRS_AUTO_EXIT: SSOT.PHASE_MATURITY_POLICY, @Structure.P4_C_CQRS_MAN_AUTO_EXIT_CONFIG;
// @Structure.P4_C_CQRS_MAN_MODE_SWITCH_COMMAND: Operation mode switch command schema
struct ModeSwitchCommand { command_id:U,target_mode:OperationMode=PAPER,reason:s,operator_id:s,timestamp:ts,signature:s,force:b=F }

// @Structure.P4_C_CQRS_MAN_MODE_SWITCH_ACK: Operation mode switch ack schema
struct ModeSwitchAck { ack_id:U,command_id:U,executed_at:ts,success:b,previous_mode:OperationMode,current_mode:OperationMode,positions_handled:i=0 }

// @Structure.P4_C_CQRS_MAN_META_STRATEGY_COMMAND: Meta-strategy command schema
struct MetaStrategyCommand { command_id:U,parameter_key:s,new_value:d,duration_minutes:i?,reason:s,operator_id:s,timestamp:ts,signature:s }

// @Structure.P4_C_CQRS_MAN_META_STRATEGY_ACK: Meta-strategy ack schema
struct MetaStrategyAck { ack_id:U,command_id:U,executed_at:ts,success:b,expires_at:ts? }

// ─────────────────────────────────────────────────────────────────────
// @DocMeta.P4_C_SEC3_ALERT_THRESHOLD_CONSTANTS: §3 Alert Threshold Constants
// ─────────────────────────────────────────────────────────────────────

// @Rule.P4_C_ALERT_BACKPRESSURE: SSOT.BACKPRESSURE_THRESHOLD, CONTRACT.ALERT_CONFIG;
// @Rule.P4_C_ALERT_ERROR_RATE: SSOT.ERROR_RATE_THRESHOLD, CONTRACT.ALERT_CONFIG;
// @Rule.P4_C_ALERT_LATENCY_P99: SSOT.LATENCY_THRESHOLD, CONTRACT.ALERT_CONFIG;
// @Rule.P4_C_ALERT_MEMORY: SSOT.MEMORY_THRESHOLD, CONTRACT.ALERT_CONFIG;
// @Rule.P4_C_ALERT_HEARTBEAT: SSOT.HEARTBEAT_THRESHOLD, CONTRACT.ALERT_CONFIG;

// ─────────────────────────────────────────────────────────────────────
// @DocMeta.P4_C_SEC4_HEALTH_API_DATA_STRUCTURES: §4 Health API - Data Structures
// ─────────────────────────────────────────────────────────────────────

// @Structure.P4_C_HADS_HEALTH_PHASE_HEALTH: Health API phase health schema
struct PhaseHealth { status:"HEALTHY"|"WARNING"|"DEGRADED"|"CRITICAL"|"STOPPED",score:f,last_updated:s }

// @Rule.P4_C_HADS_SCORE_RANGE: SSOT.SCORE_RANGE_VALIDATION, @Structure.P4_C_HADS_HEALTH_PHASE_HEALTH;
// @Structure.P4_C_HADS_HEALTH_COMPONENT_HEALTH: Health API component health schema
struct ComponentHealth { component_id:s,status:"HEALTHY"|"WARNING"|"DEGRADED"|"CRITICAL"|"STOPPED",last_heartbeat:s?,error_count:i=0,latency_p99_ms:f? }

// @Structure.P4_C_HADS_HEALTH_SYSTEM_HEALTH_RESPONSE: Health API system health response schema
struct SystemHealthResponse { system_health:d={status,score,validation_mode,feature_schema_id,phases:d<PhaseHealth>} }

// @Structure.P4_C_HADS_HEALTH_COMPONENTS_HEALTH_RESPONSE: Health API components health response schema
struct ComponentsHealthResponse { components:ComponentHealth[] }

// ─────────────────────────────────────────────────────────────────────
// @DocMeta.P4_C_SEC5_DASHBOARD_SSE_DATA_STRUCTURES: §5 Dashboard & SSE - Data Structures
// ─────────────────────────────────────────────────────────────────────

// @Structure.P4_C_DSDS_SSE_THROTTLE_CONFIG: SSE throttle configuration schema
struct SSEThrottleConfig { max_msg_per_sec:i=10,conflate_events:s[]=["market_tick","position_update"],no_drop_events:s[]=["alert","order_update","system_status"] }
// @Rule.P4_C_DSDS_SSE_THROTTLE: SSOT.SSE_THROTTLING_POLICY, @Structure.P4_C_DSDS_SSE_THROTTLE_CONFIG;
// @Rule.P4_C_DSDS_SSE_CONFLATE: SSOT.CONFLATION_LOGIC, @Structure.P4_C_DSDS_SSE_THROTTLE_CONFIG;
// @Rule.P4_C_DSDS_SSE_NO_DROP: SSOT.DELIVERY_GUARANTEE, @Structure.P4_C_DSDS_SSE_THROTTLE_CONFIG;
// @DocMeta.P4_C_SEC5_SSE_EVENT_PAYLOAD_SCHEMA_P4_12: SSE Event Payload Schema (P4-12)
// @Note.P4_C_DSDS_SSE_EVENT_COMMON_FIELDS: Common fields for SSE events: ts, trace_id
// @Structure.P4_C_DSDS_SSE_EVENT_MARKET_TICK: SSE event payload schema - market tick
struct SSEEventMarketTick { ts:ts,trace_id:s,instrument_id:s,bid:f,ask:f,last:f }

// @Structure.P4_C_DSDS_SSE_EVENT_ORDER_UPDATE: SSE event payload schema - order update
struct SSEEventOrderUpdate { ts:ts,trace_id:s,order_id:s,status:s,filled_qty:f,avg_price:f }

// @Structure.P4_C_DSDS_SSE_EVENT_POSITION_UPDATE: SSE event payload schema - position update
struct SSEEventPositionUpdate { ts:ts,trace_id:s,instrument_id:s,qty:f,pnl:f,margin:f }

// @Structure.P4_C_DSDS_SSE_EVENT_SYSTEM_STATUS: SSE event payload schema - system status
struct SSEEventSystemStatus { ts:ts,trace_id:s,status:"GREEN"|"YELLOW"|"RED",active_phase:s }

// @Structure.P4_C_DSDS_SSE_EVENT_ALERT: SSE event payload schema - alert
struct SSEEventAlert { ts:ts,trace_id:s,level:s,message:s,component:s }

// @Rule.P4_C_DSDS_SSE_EVENT_FREQ: SSOT.EVENT_PRIORITY_MATRIX, @Structure.P4_C_DSDS_SSE_THROTTLE_CONFIG;
// @Structure.P4_C_DSDS_SSE_AUTH_CONFIG: SSE auth configuration schema
struct SSEAuthConfig { auth_method:s="query_token",token_param_name:s="token",rotation_method:s="config_reload",dynamic_rotation:b=F }

// @Rule.P4_C_DSDS_SSE_AUTH_PHASE1: SSOT.PHASE1_AUTH_METHOD, @Structure.P4_C_DSDS_SSE_AUTH_CONFIG;
// @Rule.P4_C_DSDS_SSE_KEY_ROTATE: SSOT.KEY_ROTATION_PROCEDURE, @Structure.P4_C_DSDS_SSE_AUTH_CONFIG;

// ─────────────────────────────────────────────────────────────────────
// @DocMeta.P4_C_SEC5_1_TRADING_AUTHORITY_MATRIX_M_2_GAP_FIX: §5.1 Trading Authority Matrix (M-2 Gap Fix)
// ─────────────────────────────────────────────────────────────────────

// @Rule.P4_C_TAM_SSOT: SSOT.SYSTEM_STATE_DERIVATION, @Structure.P4_C_TAM_TRADING_AUTHORITY;
// @Rule.P4_C_TAM_AUTHORITY_FORMULA: SSOT.AUTHORITY_CALCULATION, @Structure.P4_C_TAM_TRADING_AUTHORITY;
// @Structure.P4_C_TAM_TRADING_AUTHORITY: Trading authority schema (derived/cached)
struct TradingAuthority {
  allow_new_entry: b,              // New position allowed
  allow_closing: b,                // Close position allowed
  max_size_ratio: f,               // 0.0 ~ 1.0 (ratio of Strategy max_position)
  allowed_order_types: [s],        // ["LIMIT", "MARKET", ...]
  reason: s                        // Restriction reason (e.g., "DEGRADED_MODE")
}

// @Rule.P4_C_TAM_VALIDATION: SSOT.ORDER_VALIDATION_FLOW, @Structure.P4_C_TAM_TRADING_AUTHORITY;
// @Rule.P4_C_TAM_REJECT_CODE: SSOT.ERROR_CODES, @Structure.P4_C_TAM_TRADING_AUTHORITY;
// @Rule.P4_C_TAM_CACHE: SSOT.CACHE_POLICY, @Structure.P4_C_TAM_TRADING_AUTHORITY;


// ─────────────────────────────────────────────────────────────────────
// @DocMeta.P4_C_SEC5_2_WAL_RECOVERY_INTERFACES_H_2_GAP_FIX: §5.2 WAL Recovery Interfaces (H-2 Gap Fix)
// ─────────────────────────────────────────────────────────────────────

// @Rule.P4_C_WRI_WAL_SSOT: SSOT.IDEMPOTENCY_POLICY, @Structure.P4_C_WRI_WAL_STATE;
// @Rule.P4_C_WRI_MEMORY_CACHE: SSOT.WAL_RETENTION_POLICY, @Structure.P4_C_WRI_WAL_STATE;
// @Rule.P4_C_WRI_REDIS_VIEW_ONLY: SSOT.REDIS_DATA_USAGE, @Structure.P4_C_WRI_WAL_STATE;
// @Structure.P4_C_WRI_WAL_STATE: WAL-derived state schema for recovery
struct WalState {
  active_orders: [d],              // Active order records from WAL
  current_position: d,             // Position state from WAL
  processed_clordids: set[s]       // Idempotency cache (24h)
}

// @Structure.P4_C_WRI_EXCHANGE_SNAPSHOT: Exchange snapshot schema for reconciliation
struct ExchangeSnapshot {
  open_orders: [d],                // Orders from exchange API
  position: d,                     // Position from exchange API
  timestamp_ns: i                  // Snapshot timestamp
}

// @Rule.P4_C_WRI_SYNCING_PHASE: SSOT.SYNCING_PHASE_RECON, @Structure.P4_C_WRI_EXCHANGE_SNAPSHOT;
// @Rule.P4_C_WRI_GHOST_KILL: SSOT.GHOST_KILL_POLICY, @Structure.P4_C_WRI_EXCHANGE_SNAPSHOT;
// @Rule.P4_C_WRI_LOST_ORDER: SSOT.LOST_ORDER_POLICY, @Structure.P4_C_WRI_WAL_STATE;
// @Rule.P4_C_WRI_POSITION_OVERWRITE: @Rule.P4_C_RECON_SOT, @Structure.P4_C_WRI_EXCHANGE_SNAPSHOT;

// ─────────────────────────────────────────────────────────────────────
// @DocMeta.P4_C_SEC6_RECONCILIATION_DATA_STRUCTURES: §6 Reconciliation - Data Structures
// ─────────────────────────────────────────────────────────────────────

// @Structure.P4_C_RDS_RECON_CONFIG: Reconciliation configuration schema
struct ReconciliationConfig {
  exchange_api_endpoint:s="/info",internal_state_source:s="redis",
  api_retry_count:i=3,api_retry_interval_sec:f=1.0,skip_on_all_failures:b=T,
  overwrite_fields:s[]=["position_qty","entry_price","locked_margin"],
  redis_update_command:s="HSET",full_object_replace:b=F
}
// @Rule.P4_C_RDS_RECON_EXCHANGE: SSOT.EXCHANGE_API_SPEC, @Structure.P4_C_RDS_RECON_CONFIG;
// @Rule.P4_C_RDS_RECON_NOTE: SSOT.CALCULATION_LOGIC, @Structure.P4_C_RDS_RECON_CONFIG;
// @Rule.P4_C_RDS_RECON_SOT: SSOT.SOURCE_OF_TRUTH, @Structure.P4_C_RDS_RECON_CONFIG;
// @Rule.P4_C_RDS_RECON_RETRY: SSOT.RETRY_POLICY, @Structure.P4_C_RDS_RECON_CONFIG;
// @Rule.P4_C_RDS_RECON_FIELDS: SSOT.OVERWRITE_FIELDS, @Structure.P4_C_RDS_RECON_CONFIG;
// @Rule.P4_C_RDS_RECON_UPDATE: SSOT.REDIS_UPDATE_STRATEGY, @Structure.P4_C_RDS_RECON_CONFIG;
// @Rule.P4_C_RDS_RECON_ID: SSOT.INSTRUMENT_ID_FORMAT, @Structure.P4_C_RDS_RECON_CONFIG;

// @Structure.P4_C_RDS_RECON_RESULT: Reconciliation run result schema
struct ReconciliationResult { success:b,mismatches_found:i,mismatches_corrected:i,ghost_orders_cancelled:i=0,skipped_reason:s? }
// PositionCorrectionEvent (referenced from OrderManager)

// @Structure.P4_C_RDS_RECON_POSITION_CORRECTION_EVENT: Position correction event schema
struct PositionCorrectionEvent { trace_id:s,instrument_id:s,correction_type:s="RECONCILIATION",old_qty:f,new_qty:f,old_entry_price:f?,new_entry_price:f,old_margin:f?,new_margin:f,reason:s,timestamp_ns:i }

// @Structure.P4_C_RDS_RECON_SCHEDULER_CONFIG: Reconciliation scheduler configuration schema
struct ReconciliationSchedulerConfig { periodic_interval_sec:i=60,run_on_syncing_complete:b=T,run_on_killswitch_reset:b=T,enabled:b=T }
// @Rule.P4_C_RDS_RECON_TRIGGER: SSOT.RECON_TRIGGER_EVENTS, @Structure.P4_C_RECON_SCHEDULER_CONFIG;
// @Rule.P4_C_RDS_RECON_PHASES_AFTER_SYNCING: SSOT.RECON_ACTIVE_PHASES, @Structure.P4_C_RECON_SCHEDULER_CONFIG;

// ─────────────────────────────────────────────────────────────────────
// @DocMeta.P4_C_SEC7_AUDIT_LOG_DATA_STRUCTURES_SCHEMA: §7 Audit Log - Data Structures & Schema
// ─────────────────────────────────────────────────────────────────────

// @Rule.P4_C_AUDIT_DECISION_05_LOG_FORMAT: SSOT.LOG_FORMAT_JSON, @Structure.P4_C_ALDS_AUDIT_LOG_ENTRY;
// @Rule.P4_C_AUDIT_DECISION_08_STORAGE: SSOT.STORAGE_TIERING, @Structure.P4_C_ALDS_AUDIT_LOG_ENTRY;
// @Rule.P4_C_AUDIT_ECISION_25_PARTITIONING: SSOT.DB_PARTITIONING_POLICY, @Structure.P4_C_ALDS_AUDIT_LOG_ENTRY;
// @Const.P4_C_ALDS_AUDIT_CONST: Audit retention/stream constants
const AUDIT_RETENTION_DAYS:i = 180   // PostgreSQL retention (env: AUDIT_RETENTION_DAYS)
const AUDIT_ARCHIVE_DAYS:i = 90      // Move to archive partition after 90d (env: AUDIT_ARCHIVE_DAYS)
const AUDIT_STREAM_MAXLEN:i = 100000 // Redis Stream XTRIM maxlen (~7d equivalent)
const AUDIT_STREAM_KEY:s = "safety:audit:log"
const AUDIT_REDIS_RETENTION_DAYS:i = 7
// --- end: P4_ALDS_AUDIT_CONST ---

// @Structure.P4_C_ALDS_AUDIT_LOG_ENTRY: Audit log entry schema
struct AuditLogEntry { entry_id:U=uuid4(),timestamp:ts=utc_now(),operator_id:s,action:AuditAction,details:d,ip_address:s?,success:b=T,archived_at:ts?,expires_at:ts,created_at:ts? }
// @Rule.P4_C_AUDIT_EXPIRES: SSOT.EXPIRATION_CALCULATION, @Structure.P4_C_ALDS_AUDIT_LOG_ENTRY;
// @Rule.P4_C_AUDIT_TIMESTAMP_TZ: SSOT.TIMESTAMP_STANDARD, @Structure.P4_C_ALDS_AUDIT_LOG_ENTRY;
// @Rule.P4_C_AUDIT_STORAGE: SSOT.STORAGE_CONFIG, @Structure.P4_C_ALDS_AUDIT_LOG_ENTRY;
// @Rule.P4_C_AUDIT_PARTITION: SSOT.PARTITION_SCHEMA, @Structure.P4_C_ALDS_AUDIT_LOG_ENTRY;
// @Rule.P4_C_AUDIT_RETENTION: SSOT.AUDIT_RETENTION_POLICY, @Structure.P4_C_ALDS_AUDIT_LOG_ENTRY;
// @Rule.P4_C_AUDIT_API: CONTRACT.AUDIT_LOGGER_INTERFACE, @Structure.P4_C_ALDS_AUDIT_LOG_ENTRY;

// @Note.P4_C_AUDIT_POSTGRES_SCHEMA_SUMMARY: PostgreSQL schema summary (audit_log): partitioning, indexes, cleanup job details are implementation guidance; authoritative rules are, @Rule.P4_C_AUDIT_PARTITION, @Rule.P4_C_AUDIT_RETENTION, @Rule.P4_C_AUDIT_STORAGE;
// @Rule.P4_C_AUDIT_RETENTION_DEFAULTS: SSOT.RETENTION_DEFAULTS, @Const.P4_C_ALDS_AUDIT_CONST;

// PostgreSQL Schema Summary (audit_log):
// CREATE TABLE audit_log (...) PARTITION BY RANGE(timestamp)
// Columns: entry_id UUID PK, timestamp TIMESTAMPTZ, operator_id VARCHAR(64), action VARCHAR(64), details JSONB, ip_address INET, success BOOLEAN, archived_at TIMESTAMPTZ?, expires_at TIMESTAMPTZ, created_at TIMESTAMPTZ
// Partitions: audit_log_current (last 90d→MAXVALUE), audit_log_archive (MINVALUE→last 90d)
// Indexes: idx_audit_timestamp(DESC), idx_audit_operator, idx_audit_action, idx_audit_expires
// Cleanup: DELETE FROM audit_log WHERE expires_at < NOW() (daily job)

// ─────────────────────────────────────────────────────────────────────
// @DocMeta.P4_C_SEC8_SAFE_MODE_AXES_STATE_DEFINITIONS: §8 Safe Mode Axes - State Definitions
// ─────────────────────────────────────────────────────────────────────

// @Rule.P4_C_SAFE_MODE_AXES: @Structure.P4_C_SMAS_ENUM_CONFIG_SAFE, @Structure.P4_C_SMAS_ENUM_TRADING_SAFE;
// @Rule.P4_C_SAFE_MODE_RADING_FULL: SSOT.FULL_SAFE_MODE_POLICY, @Structure.P4_C_SMAS_ENUM_TRADING_SAFE;
// @Ref.P4_C_SAFE_MODE_P1_CONSTRAINTS: SSOT.TRADING_SAFE_MODE_CONSTRAINTS;
// @Note.P4_C_SAFE_MODE_COMBO_TABLE: OFF+OFF=Normal | OFF+PARTIAL=NewPosBlocked | OFF+FULL=NewOrdersBlocked,CloseAllowed | ON+OFF=ConfigLocked | ON+PARTIAL=ConfigLocked+NewPosBlocked | ON+FULL=FullSafeMode

// ─────────────────────────────────────────────────────────────────────
// @DocMeta.P4_C_SEC9_M_TLS_SECURITY_CONFIG_STRUCTURE: §9 mTLS Security - Config Structure
// ─────────────────────────────────────────────────────────────────────

// @Structure.P4_C_TSCS_TLS_MTLS_CONFIG: mTLS security configuration schema
struct MTLSConfig { ca_cert:Path,server_cert:Path,server_key:Path,verify_client:b=T,min_tls_version:s="TLSv1.3" }
// @Rule.P4_C_TSCS_TLS_MIN_VERSION: SSOT.TLS_VERSION_REQUIREMENT, @Structure.P4_C_TSCS_TLS_MTLS_CONFIG;
// @Rule.P4_C_TSCS_TLS_VERIFY: SSOT.CLIENT_VERIFICATION_POLICY, @Structure.P4_C_TSCS_TLS_MTLS_CONFIG;

// ─────────────────────────────────────────────────────────────────────
// @DocMeta.P4_C_SEC10_REDIS_RPC_DATA_STRUCTURES: §10 Redis RPC - Data Structures
// ─────────────────────────────────────────────────────────────────────

// @Ref.P4_C_REDIS_RPC_PUBSUB: SSOT.REDIS_PUB_SUB_TOPICS;
// @Structure.P4_C_REDIS_RPC_REQUEST: Redis RPC request schema
struct RPCRequest { command_id:s=uuid4(),command_type:s,payload:d,timeout_sec:f=30.0 }
// @Structure.P4_C_REDIS_RPC_RESPONSE: Redis RPC response schema
struct RPCResponse { command_id:s,success:b=F,result:any?,error:s? }
// @Rule.P4_C_REDIS_RPC_TIMEOUT: SSOT.RPC_TIMEOUT_SPEC, @Structure.P4_C_REDIS_RPC_REQUEST;

// ─────────────────────────────────────────────────────────────────────
// @DocMeta.P4_C_SEC11_ACCEPTANCE_TEST_DATA_STRUCTURES: §11 Acceptance Test - Data Structures
// ─────────────────────────────────────────────────────────────────────

// @Rule.P4_C_ATDS_ENV_BASELINE: SSOT.ENVIRONMENT_BASELINE, @Structure.P4_C_ATDS_ATDS_ACCEPTANCE_TEST_CONFIG;
// @Note.P4_C_ATDS_METRICS_TABLE: E2E_Latency<50ms(p99)|Feature→OrderAPI, KillSwitch<2.0s|Cmd→CancelComplete, DataIntegrity=0/hour|Reconciliation_overwrites
// @Loc.P4_C_ATDS_CRITERIA_FILE: myplugins/tests/acceptance/criteria.py

// @Structure.P4_C_ATDS_ATDS_ACCEPTANCE_TEST_CONFIG: Acceptance test configuration schema
struct AcceptanceTestConfig { // @attr frozen=True
  e2e_latency_p99_ms:f=50.0,kill_switch_latency_sec:f=2.0,
  max_reconciliation_overwrites_per_hour:i=0,
  log_source:s="stdout",log_format:s="json",
  error_levels:tuple[s]=("ERROR","CRITICAL"),
  metrics_keys:tuple[s]=("latency_e2e_us","processing_time_ms","kill_switch_duration_ms")
}
// @Rule.P4_C_ATDS_LATENCY: SSOT.LATENCY_CRITERIA, @Structure.P4_C_ATDS_ATDS_ACCEPTANCE_TEST_CONFIG;
// @Rule.P4_C_ATDS_INTEGRITY: SSOT.INTEGRITY_CRITERIA, @Structure.P4_C_ATDS_ATDS_ACCEPTANCE_TEST_CONFIG;
// @Rule.P4_C_ATDS_JUDGE: SSOT.JUDGE_LOGIC, @Structure.P4_C_ATDS_ATDS_ACCEPTANCE_TEST_CONFIG;

// @Structure.P4_C_ATDS_ATDS_FAULT_INJECTION_TEST_CONFIG: Fault injection test configuration schema
struct FaultInjectionTestConfig { // @attr frozen=True
  expected_error_patterns:tuple[s]=(),unexpected_error_is_fail:b=T,expected_error_is_pass:b=T
}
// @Rule.P4_C_ATDS_FAULT_INJECT: SSOT.FAULT_INJECTION_POLICY, @Structure.P4_C_ATDS_ATDS_FAULT_INJECTION_TEST_CONFIG;
```
