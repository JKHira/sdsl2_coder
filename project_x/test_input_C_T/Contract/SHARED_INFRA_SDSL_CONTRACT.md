```typescript
// ===============================================
// SHARED_INFRASTRUCTURE CONTRACT / IO SDSL v2.28
// Data Contracts, Types, Formats, Interfaces
// ===============================================
// IMPORTANT: Must Obay Stable ID Rules: Stable_ID_Base_Rules.md

// ===============================================
// @DocMeta.SI_C_SEC1_CONFIGURATION_DATA_TYPES: §1 Configuration & Data Types
// ===============================================

// @DocMeta.SI_C_SEC1_1_CENTRALIZED_CONFIGURATION_SSOT: §1.1 Centralized Configuration SSOT
// @SSOTRef.SI_C_CDT_RUNTIME_CONFIG_SSOT_RUNTIME_PY: SSOT.RuntimeConfig;
// @Rule.SI_C_CDT_NO_HARDCODING: SSOT.RuntimeConfig, @Const.SI_C_CDT_CONFIG_SSOT_LOCATION_CONST;

// @Const.SI_C_CDT_CONFIG_SSOT_LOCATION_CONST: Runtime config SSOT location constant (runtime.py)
const CONFIG_SSOT_LOCATION = "myplugins/shared/config/runtime.py"
// -- end: SI_CDT_CONFIG_SSOT_LOCATION_CONST --


// @Structure.SI_C_CDT_RUNTIME_CONFIG_SSOT_STRUCT: Runtime config SSOT schema (runtime.py reference)
struct RuntimeConfigSSoT {
  RetryConfig,        // Retry/backoff settings
  TimeoutConfig,      // Timeout settings
  CircuitBreakerConfig, // Circuit breaker settings
  WALFsyncConfig      // WAL fsync policy (P0-16 Hybrid)
}

// @DocMeta.SI_C_SEC1_2_1_TIMEOUT_CONFIG_SSOT_RUNTIME_PY: §1.2.1 Timeout Config (SSOT: runtime.py)
// @Const.SI_C_CDT_TIMEOUT_DEFAULTS_CONST: Timeout default constants (runtime.py SSOT)
const TIMEOUT_DEFAULTS = { internal_api:3.0, control_plane:30.0, external_http:5.0 }
// --- end: SI_CDT_TIMEOUT_DEFAULTS_CONST ---

// @DocMeta.SI_C_SEC1_3_TIMEZONE_AWARE_DATETIME: §1.3 Timezone-Aware Datetime
// @SSOTRef.SI_C_CDT_TIME_UTILS_TIME_PY: SSOT.TimeUtils;
// @Rule.SI_C_CDT_TIMEZONE: @Function.SI_C_CDT_UTC_NOW;
// @Rule.SI_C_CDT_PROHIBITION: @Function.SI_C_CDT_UTC_NOW;
// @Function.SI_C_CDT_UTC_NOW: timezone-aware utc_now() (naive datetime forbidden)
f utc_now() -> ts { ret datetime.now(timezone.utc) }

// @DocMeta.SI_C_SEC1_3_1_LATENCY_BUDGET_20MS_LOOP: §1.3.1 Latency Budget (20ms Loop)
// @Structure.SI_C_CDT_LATENCY_BUDGET_CONFIG: Hot-loop latency budget configuration schema
struct LatencyBudgetConfig { logic_max_ms:f=1.0, risk_route_max_ms:f=2.0, sync_io_max_ms:f=0.0, jitter_buffer_ms:f=10.0, reserve_ms:f=7.0, loop_period_ms:f=20.0 }
// @Rule.SI_C_CDT_SYNC_IO: @Structure.SI_C_CDT_LATENCY_BUDGET_CONFIG;

// @DocMeta.SI_C_SEC1_4_CL_ORD_ID_MANAGEMENT: §1.4 ClOrdID Management
// @SSOTRef.SI_C_CDT_CLORDID_CLORDID_PY: SSOT.ClOrdID;
// @Rule.SI_C_CDT_CLORDID_GEN: CONTRACT.OrderManager, SSOT.ClOrdID;
// @Rule.SI_C_CDT_CLORDID_FORMAT: SSOT.ClOrdID;
// @Rule.SI_C_CDT_CLORDID_FORMAT_DETAIL: SSOT.ClOrdID, @Structure.SI_C_CDT_CLORDID_GENERATOR;
// @Rule.SI_C_CDT_SIGNAL_VS_CLORDID: SSOT.ClOrdID, @Structure.SI_C_CDT_ORDER_REQUEST_ID_LINK;
// @Example.SI_C_CDT_FORMAT_EXAMPLE: ORD-PROD-BTC-1702123456789012345-00001
// @Structure.SI_C_CDT_CLORDID_GENERATOR: ClOrdId generator config/state schema
struct ClOrdIdGenerator { prefix:s, env:s, startup_seed_ns:i, _counter:i=0 }


// @Structure.SI_C_CDT_ORDER_REQUEST_ID_LINK: Minimal order request id link (clordid + optional signal_id)
struct OrderRequestIdLink { clordid:s, signal_id:s? }

// @Class.SI_C_CDT_CLORDID_GENERATOR_CLASS: ClOrdId generator implementation contract (generate semantics)
C ClOrdIdGenerator { f generate(inst:s)->s { _counter++ -> ret "{prefix}-{env}-{inst}-{startup_seed_ns}-{ _counter:05d}" } }
// @Rule.SI_C_CDT_COLLISION_AVOID: SSOT.ClOrdID, @Class.SI_C_CDT_CLORDID_GENERATOR_CLASS;

// @DocMeta.SI_C_SEC1_4_4_IDEMPOTENCY_CHECK_AUXILIARY: §1.4.4 Idempotency Check (Auxiliary)
// @Rule.SI_C_CDT_IDEMPOTENCY_KEY: @Const.SI_C_CDT_CLORDID_IDEMPOTENCY_REDIS_KEYS, SSOT.ClOrdID;
// @Const.SI_C_CDT_CLORDID_IDEMPOTENCY_REDIS_KEYS: ClOrdId idempotency redis key constants
const CLORDID_EXECUTED_KEY:s = "cmd:executed:{clordid}"
const CLORDID_EXECUTED_TTL:i = 86400  // 24h
// --- end: SI_CDT_CLORDID_IDEMPOTENCY_REDIS_KEYS ---

// ===============================================
// @DocMeta.SI_C_SEC2_MESSAGE_ENVELOPE_TYPES: §2 MessageEnvelope Types
// ===============================================

// @SSOTRef.SI_C_MET_ENVELOPE_PY: SSOT.MessageEnvelope;
// @Structure.SI_C_MET_CONTENT_TYPE_ENUM: Message envelope content type enum
enum ContentType { NUMPY="numpy", ARROW="arrow", JSON="json", MSGPACK="msgpack" }


// @Function.SI_C_MET_NOW_NS: UTC nanoseconds helper (int64)
f _now_ns()->i { ret int(time.time()*1_000_000_000) }  // UTC nanoseconds helper

// @Structure.SI_C_MET_MESSAGE_ENVELOPE: Canonical MessageEnvelope schema
struct MessageEnvelope { trace_id:U, sequence_id:i=0, source:s, server_ts_ns:i, origin_ts_ns:i, schema_id:s, version:s="1.0.0", content_type:ContentType=JSON, payload:any, meta:d }

// @Rule.SI_C_MET_TIMESTAMP: @Structure.SI_C_MET_MESSAGE_ENVELOPE;
// @Rule.SI_C_MET_ZERO_COPY: @Structure.SI_C_MET_MESSAGE_ENVELOPE, @Structure.SI_C_MET_CONTENT_TYPE_ENUM;
// @Rule.SI_C_MET_SEQ_ID: @Structure.SI_C_MET_MESSAGE_ENVELOPE;
// @Rule.SI_C_MET_SEQ_GEN: CONTRACT.Publisher, @Structure.SI_C_MET_MESSAGE_ENVELOPE;
// @Rule.SI_C_MET_SEQ_GAP: CONTRACT.Subscriber, @Structure.SI_C_MET_MESSAGE_ENVELOPE;

// @Function.SI_C_MET_SERIALIZE: Serialize MessageEnvelope with content-type rules
f serialize()->bytes { content_type in [JSON,MSGPACK]?include payload:payload=None }

// @Function.SI_C_MET_DESERIALIZE: Deserialize MessageEnvelope with content-type rules
@classmethod f deserialize(data:bytes,content_type:ContentType)->MessageEnvelope
// @DocMeta.SI_C_SEC2_3_TRACE_ID_CONVENTION_OD_CC_2: §2.3 Trace ID Convention (OD-CC-2)
// @Rule.SI_C_MET_TRACE_FORMAT: @Structure.SI_C_MET_MESSAGE_ENVELOPE;
// @Rule.SI_C_MET_TRACE_GEN: @Structure.SI_C_MET_MESSAGE_ENVELOPE;
// @Rule.SI_C_MET_TRACE_PROPAGATION: @Structure.SI_C_MET_MESSAGE_ENVELOPE;
// @Rule.SI_C_MET_OTEL_FUTURE: @Structure.SI_C_MET_MESSAGE_ENVELOPE;

// @DocMeta.SI_C_SEC2_4_BINARY_PAYLOAD_TRANSPORT_META_BUFFER_REF_CONVENTION: §2.4 Binary Payload Transport (meta.buffer_ref Convention)
// @Rule.SI_C_MET_META_KEYS: @Structure.SI_C_MET_MESSAGE_ENVELOPE;
// @Rule.SI_C_MET_SCHEMA_KEY: @Structure.SI_C_MET_MESSAGE_ENVELOPE;
// @Rule.SI_C_MET_VIOLATION_RISK: @Structure.SI_C_MET_MESSAGE_ENVELOPE, @Structure.SI_C_MET_CONTENT_TYPE_ENUM;

// @DocMeta.SI_C_SEC2_5_JSON_CUSTOM_SERIALIZER: §2.5 JSON Custom Serializer
// @SSOTRef.SI_C_MET_JSON_UTILS_JSON_UTILS_PY: SSOT.JsonUtils;
// @Function.SI_C_MET_JSON_CUSTOM_DEFAULT: JSON custom default serializer
f custom_default(obj:any)->any { obj is UUID?str(obj): obj is datetime?obj.isoformat(): obj is Decimal?str(obj): obj is Enum?obj.value: raise TypeError }

// @Function.SI_C_MET_JSON_DUMPS: JSON dumps wrapper (custom_default)
f dumps(obj:any)->s { ret json.dumps(obj,default=custom_default) }

// @Function.SI_C_MET_JSON_LOADS: JSON loads wrapper
f loads(s:s|bytes)->any { ret json.loads(s) }  // passthrough wrapper for consistency

// ===============================================
// @DocMeta.SI_C_SEC3_ERROR_HANDLING_TYPES: §3 Error Handling Types
// ===============================================

// @DocMeta.SI_C_SEC3_0_LOG_LEVEL_DEFINITION_SSOT: §3.0 Log Level Definition (SSOT)
// @Rule.SI_C_ERHT_CRITICAL_DEF: @Structure.SI_C_ERHT_ERROR_LEVEL_ENUM;
// @Rule.SI_C_ERHT_ERROR_DEF: @Structure.SI_C_ERHT_ERROR_LEVEL_ENUM;
// @Rule.SI_C_ERHT_WARNING_DEF: @Structure.SI_C_ERHT_ERROR_LEVEL_ENUM;
// @Rule.SI_C_ERHT_INFO_DEF: @Structure.SI_C_ERHT_ERROR_LEVEL_ENUM;
// @Rule.SI_C_ERHT_DEBUG_DEF: @Structure.SI_C_ERHT_ERROR_LEVEL_ENUM;

// @DocMeta.SI_C_SEC3_1_ERROR_CATEGORIES_LEVELS: §3.1 Error Categories & Levels
// @SSOTRef.SI_C_ERHT_ERROR_CATEGORIES_CATEGORIES_PY: SSOT.ErrorCategories;
// @Rule.SI_C_ERHT_DISTINCTION: @Structure.SI_C_ERHT_ERROR_CATEGORY_ENUM, @Structure.SI_C_ERHT_ERROR_LEVEL_ENUM;
// @Structure.SI_C_ERHT_ERROR_CATEGORY_ENUM: ErrorCategory enum (domain axis)
enum ErrorCategory { VALIDATION,CONNECTION,RATE_LIMIT,BACKPRESSURE,RECONCILIATION,COMPUTATION,CRITICAL_PANIC }

// @Structure.SI_C_ERHT_ERROR_LEVEL_ENUM: ErrorLevel enum (severity axis)
enum ErrorLevel { INFO,WARN,ERROR,CRITICAL }

// @DocMeta.SI_C_SEC3_1_1_CATEGORY_DEFAULT_LEVEL_MAPPING: §3.1.1 Category Default Level Mapping
// @Rule.SI_C_ERHT_BACKPRESSURE_CRITICAL_RATIONALE: @Structure.SI_C_ERHT_ERROR_CATEGORY_ENUM, @Structure.SI_C_ERHT_ERROR_LEVEL_ENUM;
// @Const.SI_C_ERHT_CATEGORY_DEFAULT_LEVEL_MAP: Default level mapping by category
const CATEGORY_DEFAULT_LEVEL = {
  VALIDATION:ERROR, CONNECTION:ERROR, RATE_LIMIT:WARN,
  BACKPRESSURE:CRITICAL,
  RECONCILIATION:CRITICAL, COMPUTATION:ERROR, CRITICAL_PANIC:CRITICAL
}

// @Rule.SI_C_ERHT_BACKPRESSURE_LEVEL: @Structure.SI_C_ERHT_ERROR_CATEGORY_ENUM, @Structure.SI_C_ERHT_ERROR_LEVEL_ENUM;
// @Rule.SI_C_ERHT_ALERT: @Structure.SI_C_ERHT_ERROR_LEVEL_ENUM, CONTRACT.AlertManager;

// @SSOTRef.SI_C_ERHT_STRUCTURED_ERROR_STRUCTURED_PY: SSOT.StructuredError;
// @Structure.SI_C_ERHT_STRUCTURED_ERROR: Structured error schema
struct StructuredError { error_id:U, category:ErrorCategory, level:ErrorLevel, message:s, details:d, source:s, timestamp:ts, trace_id:s?, recoverable:b=T }

// @Class.SI_C_ERHT_STRUCTURED_ERROR_CLASS: StructuredError helper/serialization contract (to_dict)
C StructuredError { f to_dict()->d { ret {error_id:str,category:val,level:val,message,details,source,timestamp:iso,trace_id,recoverable} } }

// @SSOTRef.SI_C_ERHT_ERROR_HANDLER_HANDLER_PY: SSOT.ErrorHandler;
// @Class.SI_C_ERHT_ERROR_HANDLER_CLASS: ErrorHandler component contract (handler.py)
C ErrorHandler(alert_mgr:AlertManager?) {
  _handlers:d[ErrorCategory,list[Callable]], _level_handlers:d[ErrorLevel,list[Callable]]
  f set_alert_manager(alert_mgr:AlertManager)->v { _alert_mgr=alert_mgr }  // DI or lazy init
  f register_category_handler(category:ErrorCategory,handler:Callable)->v
  f register_level_handler(level:ErrorLevel,handler:Callable)->v
  f handle(err:StructuredError)->v { log(err.level,err.message) -> (err.level in [CRITICAL,ERROR] & _alert_mgr) ? _alert_mgr.send_alert(err) : v -> call_handlers(err) }
}

// @DocMeta.SI_C_SEC3_4_ALERT_MANAGER_TYPES: §3.4 AlertManager Types
// @SSOTRef.SI_C_ERHT_ALERT_MANAGER_ALERT_MANAGER_PY: SSOT.AlertManager;
// @Const.SI_C_ERHT_ALERT_REDIS_CONSTS: AlertManager Redis channel/key constants
const ALERT_CHANNEL="safety:alert", ALERT_HISTORY_KEY="safety:alert:history", ALERT_HISTORY_MAX_LEN=1000
// @Const.SI_C_ERHT_ALERT_ACTIVE_KEY_CONSTS:
const SAFETY_ALERTS_ACTIVE_KEY="safety:alerts:active"  // B-4: Set for active alerts

// @Rule.SI_C_ERHT_DEDUP: @Class.SI_C_ERHT_ALERT_MANAGER_CLASS;
// @Structure.SI_C_ERHT_ALERT_EVENT: Alert event payload schema
struct Alert { level:s, category:s, message:s, error_id:s, source:s, details:d, timestamp_ns:i }

// @Class.SI_C_ERHT_ALERT_MANAGER_CLASS: AlertManager component contract (alert_manager.py)
C AlertManager(safety_redis:Redis, dedup_window_sec:i=60) {
  _recent_alerts:d[s,f]
  f send_alert(level:s,category:s,message:s,error_id:s,source:s,details:d?)->b {
    now=time() -> (error_id in _recent_alerts & now-_recent_alerts[error_id]<dedup_window_sec) ? (log("Dup")->ret F) :
    // B-5: timestamp_ns を明示的に設定
    (_recent_alerts[error_id]=now -> Alert(level=level,category=category,message=message,error_id=error_id,source=source,details=details,timestamp_ns=int(time()*1_000_000_000)) -> _send_async(alert) -> ret T)
  }
  f _send_async(alert:Alert)->v {
    // B-4: CRITICAL の場合は safety:alerts:active に SADD
    alert.level=="CRITICAL" ? redis.sadd(SAFETY_ALERTS_ACTIVE_KEY,alert.error_id) : v ->
    redis.publish(ALERT_CHANNEL,json(alert)) -> redis.lpush(ALERT_HISTORY_KEY,json(alert)) -> redis.ltrim(0,MAX_LEN-1)
  }
  async f get_recent_alerts(count:i=100)->list[Alert] {
    // @DocRef.SI_C_ERHT_ALERT_HISTORY_DASHBOARD_DISPLAY: Dashboard display - retrieve recent alerts from Redis List
    raw_list=redis.lrange(ALERT_HISTORY_KEY,0,count-1) -> ret [Alert(**json.loads(r)) for r in raw_list if valid_json(r)]
  }
  f clear_active_alert(error_id:s)->v { redis.srem(SAFETY_ALERTS_ACTIVE_KEY,error_id) }  // For alert resolution
}

// ===============================================
// @DocMeta.SI_C_SEC4_SECURITY_TYPES: §4 Security Types
// ===============================================

// @DocMeta.SI_C_SEC4_1_TRANSPORT_SECURITY_OD_ME_1: §4.1 Transport Security (OD-ME-1)
// @Rule.SI_C_SCT_TRANSPORT: CONTRACT.TransportSecurity;
// @Rule.SI_C_SCT_AUTH: CONTRACT.TransportSecurity;
// @Rule.SI_C_SCT_INTEGRITY: CONTRACT.TransportSecurity, SSOT.PluginManual;
// @Rule.SI_C_SCT_PAYLOAD_ENCRYPT: @Structure.SI_C_SCT_TOPIC_SENSITIVITY_ENUM;
// @Rule.SI_C_SCT_TLS_SUFFICIENT: CONTRACT.TransportSecurity;

// @DocMeta.SI_C_SEC4_2_TOPIC_LEVEL_PAYLOAD_ENCRYPTION: §4.2 Topic-Level Payload Encryption
// @SSOTRef.SI_C_SCT_PAYLOAD_ENCRYPTION_PAYLOAD_ENCRYPTION_PY: SSOT.PayloadEncryption;

// @Structure.SI_C_SCT_TOPIC_SENSITIVITY_ENUM: Topic sensitivity enum
enum TopicSensitivity { PUBLIC,INTERNAL,SENSITIVE,CRITICAL }

// @Rule.SI_C_SCT_ENCRYPT: @Structure.SI_C_SCT_TOPIC_SENSITIVITY_ENUM, @Structure.SI_C_SCT_ENCRYPTION_CONFIG;
// @Const.SI_C_SCT_SENSITIVE_TOPICS_MAP: Topic sensitivity overrides map
const SENSITIVE_TOPICS = { "order.submit":SENSITIVE, "position.update":SENSITIVE, "credentials.rotate":CRITICAL, "api_key.issue":CRITICAL }

// @Structure.SI_C_SCT_ENCRYPTION_CONFIG: Payload encryption configuration schema
struct EncryptionConfig { enabled:b=F, algorithm:s="AES-256-GCM", key_rotation_days:i=90 }

// @Function.SI_C_SCT_SHOULD_ENCRYPT_PAYLOAD: Decide topic-level payload encryption based on sensitivity + config
f should_encrypt_payload(topic:s,cfg:EncryptionConfig)->b { !cfg.enabled?F: SENSITIVE_TOPICS.get(topic,PUBLIC) in [SENSITIVE,CRITICAL] }

// @DocMeta.SI_C_SEC4_3_HMAC_HTTP_SIGNATURE_TYPES: §4.3 HMAC HTTP Signature Types
// @SSOTRef.SI_C_SCT_HTTP_SIGNATURE_HTTP_SIGNATURE_PY: SSOT.HttpSignature;
// @Rule.SI_C_SCT_HTTP_SIG_EXPIRE: @Class.SI_C_SCT_HTTP_SIGNATURE_VERIFIER_CLASS;
// @Rule.SI_C_SCT_HTTP_SIG_PAYLOAD: @Class.SI_C_SCT_HTTP_SIGNATURE_VERIFIER_CLASS;

// @DocMeta.SI_C_SEC4_3_1_HTTP_HEADER_SPECIFICATION: §4.3.1 HTTP Header Specification
// @Rule.SI_C_SCT_HEADER_X_SIGNATURE: SSOT.PluginManual;
// @Rule.SI_C_SCT_HEADER_X_SIGNATURE_TS: @Structure.SI_C_SCT_HTTP_SIGNATURE_HEADERS;
// @Rule.SI_C_SCT_HEADER_X_NONCE: @Structure.SI_C_SCT_HTTP_SIGNATURE_HEADERS;
// @Rule.SI_C_SCT_HEADER_X_OPERATOR_ID: @Structure.SI_C_SCT_HTTP_SIGNATURE_HEADERS;
// @Rule.SI_C_SCT_HEADER_CONTENT_TYPE: @Structure.SI_C_SCT_HTTP_SIGNATURE_HEADERS;

// @Structure.SI_C_SCT_HTTP_SIGNATURE_HEADERS: HTTP signature headers schema
struct HttpSignatureHeaders { signature:s, timestamp_ns:i, nonce:s, operator_id:s }
// f to_headers()->d[s,s] { ret {"X-Signature":signature, "X-Signature-Ts":str(timestamp_ns), "X-Nonce":nonce, "X-Operator-Id":operator_id, "Content-Type":"application/json"} }
// @classmethod f from_headers(headers:d)->HttpSignatureHeaders { ret cls(signature=headers["X-Signature"], ...) }

// @Class.SI_C_SCT_HTTP_SIGNATURE_VERIFIER_CLASS: HMAC HTTP signature create/verify contract
C HttpSignatureVerifier(secret:s) {
  MAX_AGE_NS:i=5*60*1e9,_used_nonces:set[s]
  f create_signature(method:s,path:s,body:bytes,operator_id:s,nonce:s?)->HttpSignatureHeaders {
    ts=now_ns() -> nonce=nonce|uuid4()[:8] -> body_hash=sha256(body).hex() ->
    payload="{method}:{path}:{body_hash}:{ts}:{nonce}:{operator_id}" ->
    sig=hmac_sha256(secret,payload).hex() -> ret HttpSignatureHeaders(sig,ts,nonce,operator_id)
  }
  f verify_signature(h:HttpSignatureHeaders,method:s,path:s,body:bytes)->(b,s?) {
    (abs(now_ns()-h.timestamp_ns)>MAX_AGE_NS) ? ret(F,"Signature expired") :
    (h.nonce in _used_nonces) ? ret(F,"Nonce reused") :
    (_used_nonces.add(h.nonce) -> (len>10000?_used_nonces.clear():v) ->
    expected=hmac_sha256(secret,build_payload(...)).hex() ->
    !compare_digest(h.signature,expected) ? ret(F,"Invalid signature") : ret(T,None))
  }
}

// @DocMeta.SI_C_SEC4_3_5_SIGNATURE_MIDDLEWARE_CONFIG: §4.3.5 Signature Middleware Config
// @SSOTRef.SI_C_SCT_SIGNATURE_MIDDLEWARE_MIDDLEWARE_PY: SSOT.SignatureMiddleware;
// @Const.SI_C_SCT_SIGNATURE_MIDDLEWARE_EXEMPT_PATHS_CONSTS: Signature/RBAC exempt paths constants
const SIGNATURE_EXEMPT_PATHS={"/health","/healthz","/ready","/metrics","/api/v1/status","/api/events/stream"}
// @Const.SI_C_SCT_RBAC_EXEMPT_PATHS_CONSTS: RBAC exempt paths constants
const RBAC_EXEMPT_PATHS={"/health","/healthz","/ready","/metrics","/api/v1/status"}
// @Rule.SI_C_SCT_SSE_EXEMPT: @Const.SI_C_SCT_SIGNATURE_MIDDLEWARE_EXEMPT_PATHS_CONSTS;

// ===============================================
// @DocMeta.SI_C_SEC5_CONTROL_PLANE_CQRS_TYPES: §5 Control Plane CQRS Types
// ===============================================

// @SSOTRef.SI_C_CPLCT_CONTROL_COMMANDS_COMMANDS_PY: SSOT.ControlCommands;
// @Rule.SI_C_CPLCT_CQRS_TIMEOUT: @Structure.SI_C_CPLCT_CQRS_FLOW_CONFIG;
// @Rule.SI_C_CPLCT_IDEMPOTENCY: SSOT.PluginManual, @Const.SI_C_CPLCT_COMMAND_TIMEOUT_CONSTS;
// @Rule.SI_C_CPLCT_SINGLE_TIMEOUT: SSOT.RuntimeConfig, @Const.SI_C_CPLCT_COMMAND_TIMEOUT_CONSTS;
// @Const.SI_C_CPLCT_COMMAND_TIMEOUT_CONSTS: Control plane CQRS timeout/idempotency constants
const COMMAND_TIMEOUT=30, IDEMPOTENCY_TTL=86400, EXTENDED_TIMEOUT_COMMANDS={"STOP","SHUTDOWN","KILL_L2"}

// @Structure.SI_C_CPLCT_CQRS_FLOW_CONFIG: CQRS flow configuration schema
struct CQRSFlowConfig { command_timeout_s:f=30.0, shutdown_timeout_s:f=90.0, ack_retry_count:i=0, on_timeout:s="LOG_AND_FAIL", max_total_attempts:i=1 }

// @Structure.SI_C_CPLCT_BASE_COMMAND: Base command schema (control plane)
struct BaseCommand { command_id:U, trace_id:s, action:s, params:d, issued_by:s, ts:i, signature:s }

// @Class.SI_C_CPLCT_BASE_COMMAND_CLASS: Base command validation/signature semantics contract
C BaseCommand {
  f validate_signature(secret:s)->b {
    // @Rule.SI_C_CPLCT_CQRS_SIG_PAYLOAD: {command_id}:{action}:{params_json_sorted}:{issued_by}:{ts};
    payload=f"{command_id}:{action}:{json.dumps(params,sort_keys=T)}:{issued_by}:{ts}" ->
    expected=hmac.new(secret.encode(),payload.encode(),hashlib.sha256).hexdigest() ->
    ret hmac.compare_digest(signature,expected)
  }
}

// @Structure.SI_C_CPLCT_BASE_ACK: Base ack schema (control plane)
struct BaseAck { ack_id:U, command_id:U, status:s="OK", error_code:s="", message:s="", ts:i }

// @Rule.SI_C_CPLCT_COMMAND_TYPES: @Structure.SI_C_CPLCT_BASE_COMMAND, @Structure.SI_C_SPC_SIGNED_COMMAND;

// @SSOTRef.SI_C_CPLCT_COMMAND_EXECUTOR_EXECUTOR_PY: SSOT.CommandExecutor;
// @Class.SI_C_CPLCT_COMMAND_EXECUTOR_CLASS: Control-plane command executor (signature + idempotency)
C CommandExecutor[C,A](secret:s,redis:Redis) {
  _idempotency_prefix:s="cmd:executed:"
  f _is_executed(cid:s)->b { ret redis.exists("{ _idempotency_prefix}{cid}")>0 }
  f _mark_executed(cid:s)->v { redis.setex("{ _idempotency_prefix}{cid}",IDEMPOTENCY_TTL,"1") }
  f execute(cmd:C,handler:Callable[[C],Awaitable[A]])->A {
    !cmd.validate_signature(secret) ? ret BaseAck(command_id=cmd.command_id,status="FAIL",error_code="AUTH_FAILED") :
    _is_executed(cmd.command_id) ? ret BaseAck(...,error_code="DUPLICATE") :
    try { ack=wait_for(handler(cmd),timeout=COMMAND_TIMEOUT) -> _mark_executed(cmd.command_id) -> ret ack }
    except TimeoutError { ret BaseAck(...,status="FAIL",error_code="TIMEOUT") }
  }
}

// @DocMeta.SI_C_SEC5_1_HMAC_SIGNATURE_CONTRACT: §5.1 HMAC Signature Contract
// @Rule.SI_C_CPLCT_ALGORITHM: @Class.SI_C_CPLCT_BASE_COMMAND_CLASS;
// @Rule.SI_C_CPLCT_PAYLOAD: @Class.SI_C_CPLCT_BASE_COMMAND_CLASS;
// @Rule.SI_C_CPLCT_TIMING: @Class.SI_C_CPLCT_BASE_COMMAND_CLASS;
// @Rule.SI_C_CPLCT_EXPIRY: @Class.SI_C_CPLCT_BASE_COMMAND_CLASS;

// Signature payload format: "{command_id}:{command_type}:{ts_ns}:{issuer_id}:{nonce}:{params_json_sorted}"
// @Rule.SI_C_CPLCT_PARAMS_JSON: @Class.SI_C_CPLCT_BASE_COMMAND_CLASS;

// ===============================================
// @DocMeta.SI_C_SEC6_LOGGING_CONFIG: §6 Logging Config
// ===============================================

// @SSOTRef.SI_C_LOGC_CONFIG_PY: SSOT.LoggingConfig;
// @Rule.SI_C_LOGC_LOG_OUTPUT: @Function.SI_C_LOGC_CONFIGURE_LOGGING;
// @Function.SI_C_LOGC_CONFIGURE_LOGGING: Configure structured logging (json_output default)
f configure_logging(level:s="INFO",json_output:b=T)->v {
  processors=[filter_by_level,add_logger_name,add_log_level,...,TimeStamper(fmt="iso")] ->
  json_output?processors.append(JSONRenderer()):processors.append(ConsoleRenderer()) ->
  structlog.configure(...) -> logging.basicConfig(stream=stdout,level=level)
}

// ===============================================
// @DocMeta.SI_C_SEC7_REDIS_STATE_STORE_TYPES: §7 Redis State Store Types
// ===============================================
// @Rule.SI_C_RSST_SAFETY_REDIS: @Structure.SI_C_RSST_SAFETY_REDIS_CONFIG;
// @Rule.SI_C_RSST_MAIN_REDIS: @Structure.SI_C_RSST_MAIN_REDIS_CONFIG;
// @Rule.SI_C_RSST_SAFETY_FAILURE: @Structure.SI_C_RSST_SAFETY_REDIS_CONFIG;
// @Rule.SI_C_RSST_MAIN_FAILURE: @Structure.SI_C_RSST_MAIN_REDIS_CONFIG;

// @DocMeta.SI_C_SEC7_1_REDIS_CONFIG_OD_SR_1_OD_SR_2: §7.1 Redis Config (OD-SR-1, OD-SR-2)
// @Rule.SI_C_RSST_RETRY_MAIN: @Structure.SI_C_RSST_MAIN_REDIS_CONFIG;
// @Rule.SI_C_RSST_RETRY_SAFETY: @Structure.SI_C_RSST_SAFETY_REDIS_CONFIG;
// @Rule.SI_C_RSST_MAX_CONN_INCREASE: @Structure.SI_C_RSST_SAFETY_REDIS_CONFIG;

// @Structure.SI_C_RSST_MAIN_REDIS_CONFIG: Main Redis connection config schema
struct MainRedisConfig { host:s="localhost", port:i=6379, db:i=0, connection_timeout_sec:f=5.0, socket_timeout_sec:f=3.0, max_connections:i=10 }

// @Structure.SI_C_RSST_SAFETY_REDIS_CONFIG: Safety Redis connection config schema
struct SafetyRedisConfig { host:s="localhost", port:i=6380, db:i=0, connection_timeout_sec:f=2.0, socket_timeout_sec:f=1.0, max_connections:i=20 }

// @Structure.SI_C_RSST_SAFETY_REDIS_POOL_CONFIG: Safety Redis pool separation config schema
struct SafetyRedisPoolConfig { kill_switch_max_connections:i=5, general_max_connections:i=15, host:s, port:i, db:i, connection_timeout_sec:f, socket_timeout_sec:f }
// @Rule.SI_C_RSST_POOL_SEPARATION: @Structure.SI_C_RSST_SAFETY_REDIS_POOL_CONFIG;

// @SSOTRef.SI_C_RSST_REDIS_STORE_PY: SSOT.RedisStore;
// @Class.SI_C_RSST_REDIS_STATE_STORE_CLASS: Generic Redis-backed state store contract (get/set/delete/exists)
C RedisStateStore[T](redis:Redis,prefix:s,ttl_seconds:i?) {
  f _key(id:s)->s { ret "{prefix}:{id}" }
  f get(id:s,factory:type[T])->T? { data=redis.get(_key(id)) -> data?factory(**json.loads(data)):None }
  f set(id:s,item:T)->v { data=json.dumps(asdict(item)) -> ttl?redis.setex(_key(id),ttl,data):redis.set(_key(id),data) }
  f delete(id:s)->v { redis.delete(_key(id)) }
  f exists(id:s)->b { ret redis.exists(_key(id))>0 }
  async f list_keys()->[s] { keys=redis.keys("{prefix}:*") -> ret [k.decode().replace("{prefix}:","") for k in keys] }
}

// @DocMeta.SI_C_SEC7_3_7_4_BUFFER_REGISTRY_TYPES_GAP_04: §7.3 -7.4 Buffer Registry Types (GAP-04)
// @SSOTRef.SI_C_RSST_BUFFER_REGISTRY_REGISTRY_PY: SSOT.BufferRegistry;
// @Const.SI_C_RSST_BUFFER_REGISTRY_CONSTS: Buffer registry component contract
const BUFFER_REGISTRY_PREFIX="buffer_registry", SHM_BASE_DIR="/dev/shm/system5_zero_copy"

// @Class.SI_C_RSST_BUFFER_REGISTRY_CLASS: Zero-copy buffer registry contract (register/get/refcount/cleanup queries)
C BufferRegistry(redis:Redis) {
  f _key(buffer_ref:s)->s { buffer_id=buffer_ref.replace("shm://","").replace(".ipc","") -> ret "{BUFFER_REGISTRY_PREFIX}:{buffer_id}" }
  f register(desc:BufferDescriptor)->v { redis.set(_key(desc.path),json(desc_dict)) }
  f get(buffer_ref:s)->BufferDescriptor? { data=redis.get(_key(buffer_ref)) -> data?BufferDescriptor(**json.loads(data)):None }
  f update_state(buffer_ref:s,state:BufferState)->v { data=redis.get(_key) -> parsed=json.loads(data) -> parsed["state"]=state.value -> redis.set(_key,json(parsed)) }
  f increment_refcount(buffer_ref:s)->i { data=redis.get(_key)->parsed["refcount"]++ ->redis.set(_key,json(parsed))->ret parsed["refcount"] }
  f decrement_refcount(buffer_ref:s)->i { data=redis.get(_key)->parsed["refcount"]=max(0,parsed["refcount"]-1)->redis.set(_key,json(parsed))->ret parsed["refcount"] }
  f delete(buffer_ref:s)->v { redis.delete(_key(buffer_ref)) }
  async f list_all()->list[d] { keys=redis.keys("{BUFFER_REGISTRY_PREFIX}:*") -> ret [json.loads(redis.get(k)) for k in keys if redis.get(k)] }
  f find_expired(current_time_ns:i)->list[d] { ret [b for b in list_all() if b["expires_at_ns"]>0&b["expires_at_ns"]<current_time_ns] }
  f find_orphaned(live_pids:set[i])->list[d] { ret [b for b in list_all() if b["publisher_pid"] not in live_pids] }
}

// @DocMeta.SI_C_SEC7_4_1_BUFFER_JANITOR_TYPES_B_6: §7.4.1 BufferJanitor Types (B-6)
// @SSOTRef.SI_C_RSST_BUFFER_JANITOR_JANITOR_PY: SSOT.BufferJanitor;
// @Rule.SI_C_RSST_CLEANUP: @Class.SI_C_RSST_BUFFER_JANITOR;
// @Const.SI_C_RSST_ALERT_BUFFER_JANITOR_TOPIC_CONST: Buffer janitor alert topic constant
const ALERT_BUFFER_JANITOR_TOPIC = "alert:buffer_janitor"

// @Structure.SI_C_RSST_BUFFER_CLEANUP_EVENT: Buffer cleanup event payload schema
struct BufferCleanupEvent { event_type:s, buffer_id:s, reason:s, timestamp_ns:i, details:d? }

// @Class.SI_C_RSST_BUFFER_JANITOR: Buffer janitor component contrac
C BufferJanitor(registry:BufferRegistry, safety_redis:Redis, cleanup_interval_sec:i=60) {
  f run_cleanup()->BufferCleanupReport {
    expired=registry.find_expired(now_ns()) -> orphaned=registry.find_orphaned(get_live_pids()) ->
    cleaned=[] -> for b in (expired+orphaned) {
      reason="expired" if b in expired else "orphaned" ->
      _cleanup_buffer(b) -> cleaned.append(b) ->
      // B-6: Publish cleanup event to alert:buffer_janitor
      event=BufferCleanupEvent(event_type="buffer_cleaned",buffer_id=b["buffer_id"],reason=reason,timestamp_ns=now_ns(),details=b) ->
      safety_redis.publish(ALERT_BUFFER_JANITOR_TOPIC,json(event))
    } -> ret BufferCleanupReport(expired_count=len(expired),orphaned_count=len(orphaned),cleaned_ids=[b["buffer_id"] for b in cleaned])
  }
  f _cleanup_buffer(b:d)->v { shm_path=SHM_BASE_DIR+"/"+b["buffer_id"]+".ipc" -> os.path.exists(shm_path)?os.unlink(shm_path):v -> registry.delete(b["buffer_id"]) }
}

// @Structure.SI_C_RSST_BUFFER_CLEANUP_REPORT: Buffer cleanup report schema
struct BufferCleanupReport { expired_count:i, orphaned_count:i, cleaned_ids:[s] }

// @DocMeta.SI_C_SEC7_5_AUDIT_LOG_TYPES_COM_13_14: §7.5 Audit Log Types (COM-13~14)
// @SSOTRef.SI_C_RSST_AUDIT_TYPES_AUDIT_PY: SSOT.AuditTypes;
// @Rule.SI_C_RSST_DUAL_WRITE: CONTRACT.AuditLogger;
// @Rule.SI_C_RSST_DIRECT_WRITE_FORBIDDEN: CONTRACT.AuditLogger, @Structure.SI_C_RSST_REDIS_AUDIT_ENTRY;
// @Structure.SI_C_RSST_REDIS_AUDIT_ENTRY: Redis audit stream entry schema
struct RedisAuditEntry { timestamp_ns:i, trace_id:s, event_type:s, actor_id:s, action:s, result:s, target_id:s?, old_value:d?, new_value:d?, error_code:s?, duration_ms:i?, metadata:d? }
// @Const.SI_C_RSST_AUDIT_LOG_LEVELS_MAP: Audit event type to default alert level map
const AUDIT_LOG_LEVELS = {
  kill_switch_activated:CRITICAL, kill_switch_reset:CRITICAL,
  state_transition:INFO, component_register:INFO, component_deregister:WARNING,
  health_check:DEBUG, buffer_allocate:DEBUG, buffer_release:DEBUG,
  config_change:WARNING, manual_intervention:CRITICAL,
  recovery_start:WARNING, recovery_complete:INFO
}

// @DocMeta.SI_C_SEC7_6_LOCKS_IDEMPOTENCY_TYPES: §7.6 Locks & Idempotency Types
// @SSOTRef.SI_C_RSST_LOCKS_LOCKS_PY: SSOT.Locks;
// @SSOTRef.SI_C_RSST_IDEMPOTENCY_IDEMPOTENCY_PY: SSOT.Idempotency;
// @Rule.SI_C_RSST_LOCK_ORDER: @Const.SI_C_RSST_LOCK_DEFINITIONS_MAP;
// @Structure.SI_C_RSST_LOCK_DEFINITION: Lock definition schema
struct LockDefinition { name:s, scope:s, reentrant:b, timeout_ms:i, acquisition_order:i }
// @Const.SI_C_RSST_LOCK_DEFINITIONS_MAP: Lock definitions registry (deadlock-safe order)
const LOCK_DEFINITIONS = {
  kill_switch:LockDefinition("kill_switch","global",F,100,0),
  state_machine:LockDefinition("state_machine","global",F,1000,1),
  component_registry:LockDefinition("component_registry","global",F,500,2),
  buffer_manager:LockDefinition("buffer_manager","resource",T,100,3)
}
// @Structure.SI_C_RSST_IDEMPOTENCY_CONFIG: Idempotency configuration schema
struct IdempotencyConfig { store_key_pattern:s="cmd:executed:{command_id}", ttl_seconds:i=86400, on_duplicate:s="RESEND_ACK", max_replays:i=3 }

// @DocMeta.SI_C_SEC7_7_HEALTH_CHECK_TRACING_TYPES: §7.7 HealthCheck & Tracing Types
// @SSOTRef.SI_C_RSST_HEALTH_TYPES_TYPES_PY: SSOT.HealthTypes;
// @SSOTRef.SI_C_RSST_TRACE_PROPAGATION_PROPAGATION_PY: SSOT.TracePropagation;
// @Structure.SI_C_RSST_HEALTH_CHECK_RESPONSE: Health check response schema
struct HealthCheckResponse { component_id:s, status:s, timestamp_ns:i, response_time_ms:f, message:s?, metrics:d?, dependencies:d[s,s]? }

// @Rule.SI_C_STATUS_ENUM: @Structure.SI_C_RSST_HEALTH_CHECK_RESPONSE;
// @Structure.SI_C_RSST_HEALTH_CHECK_CONFIG: Health check config schema
struct HealthCheckConfig { interval_ms:i=5000, timeout_ms:i=3000, consecutive_failures_for_unhealthy:i=3 }

// @Structure.SI_C_RSST_TRACE_PROPAGATION: Trace propagation configuration schema
struct TracePropagation { http_header:s="X-Trace-ID", redis_field:s="trace_id", message_envelope_field:s="trace_id", format:s="UUID_V4" }
// @Rule.SI_C_RSST_TRACE_PROPAGATION: @Structure.SI_C_RSST_TRACE_PROPAGATION, @Structure.SI_C_MET_MESSAGE_ENVELOPE;

// ===============================================
// @DocMeta.SI_C_SEC10_DEPENDENCIES: §10 Dependencies
// ===============================================
// @Const.SI_C_DEPENDENCIES_MAP: Python dependency version constraints
const DEPENDENCIES = {
  redis: ">=4.5",      // State store, pub/sub
  pydantic: ">=2.0",   // Validation
  structlog: ">=23.0", // Structured logging
  msgpack: ">=1.0",    // Binary serialization
  pyarrow: ">=14.0"    // Zero-copy (Arrow IPC)
}

// ===============================================
// @DocMeta.SI_C_SEC11_WAL_FSYNC_HYBRID_POLICY_P0_16: §11 WAL fsync Hybrid Policy (P0-16)
// ===============================================

// @Rule.SI_C_WAL_FSYNC_POLICY: @Const.SI_C_WAL_WAL_FSYNC_POLICY_CONST;
// @Const.SI_C_WAL_WAL_FSYNC_POLICY_CONST: WAL fsync policy map (domain -> ALWAYS/BATCH)
const WAL_FSYNC_POLICY = { execution:"ALWAYS", risk:"ALWAYS", feature:"BATCH", metric:"BATCH", default:"ALWAYS" }

// ===============================================
// @DocMeta.SI_C_SEC12_L2_L3_FEATURE_PULL_TRANSPORT_TYPES: §12 L2-L3 Feature Pull Transport Types
// ===============================================

// @SSOTRef.SI_C_FPTT_FEATURE_TRANSPORT_PY: SSOT.FeatureTransport;
// @Rule.SI_C_FPTT_TRANSPORT: CONTRACT.FeaturePullTransport;
// @Rule.SI_C_FPTT_DIRECT_CALL: CONTRACT.FeaturePullTransport;
// @Structure.SI_C_FPTT_FEATURE_REQUEST: Feature request schema (req/rep)
struct FeatureRequest { trace_id:s, model_id:s, bns_id:s, request_ts_ns:i, content_type:s="arrow", buffer_ref:s?, schema_id:s?, timeout_ms:i=3000, priority:i=0 }
// @Structure.SI_C_FPTT_FEATURE_RESPONSE: Feature response schema (req/rep)
struct FeatureResponse { trace_id:s, status:s="OK", response_ts_ns:i, content_type:s="arrow", buffer_ref:s?, schema_id:s?, feature_count:i=0, error_code:s?, error_message:s?, compute_time_ms:f? }

// @Function.SI_C_FPTT_FEATURE_REQUEST_TOPIC: Feature request Redis list key generator (model_id scoped)
f feature_request_topic(model_id:s)->s { ret "feature:req:{model_id}" }
// @Function.SI_C_FPTT_FEATURE_RESPONSE_TOPIC: Feature response Redis list key generator (trace_id scoped)
f feature_response_topic(trace_id:s)->s { ret "feature:resp:{trace_id}" }
// @Rule.SI_C_FPTT_REDIS_KEYS_WRAPPER: @Class.SI_C_RKC_REDIS_KEY_CATALOG_CLASS, @Const.SI_C_RKC_REDIS_KEYS_SINGLETON_CONST;

// @Class.SI_C_FPTT_FEATURE_CLIENT_CLASS: Feature pull client contract (local runner or Redis req/rep)
C FeatureClient(redis:Redis,local_runner:FeatureRunner?) {
  f get_feature_vector(model_id:s,bns_id:s,timeout_ms:i=3000)->FeatureResponse {
    local_runner?local_runner.compute(bns_id):_request_via_redis(model_id,bns_id,timeout_ms)
  }
  f _request_via_redis(model_id:s,bns_id:s,timeout_ms:i)->FeatureResponse {
    req=FeatureRequest(model_id=model_id,bns_id=bns_id,timeout_ms=timeout_ms) ->
    envelope=MessageEnvelope(trace_id=req.trace_id,payload=asdict(req)) ->
    redis.rpush(feature_request_topic(model_id),json(envelope)) ->
    result=redis.blpop(feature_response_topic(req.trace_id),timeout=timeout_ms/1000) ->
    result?FeatureResponse(**json.loads(result[1])):FeatureResponse(trace_id=req.trace_id,status="TIMEOUT",error_code="CLIENT_TIMEOUT")
  }
}

// ===============================================
// @DocMeta.SI_C_SEC13_ORDER_TYPES: §13 Order Types
// ===============================================

// @SSOTRef.SI_C_ODT_ORDER_PY: SSOT.OrderTypes;
// @Rule.SI_C_ODT_NO_FLOAT: @Structure.SI_C_ODT_ORDER_SIDE_ENUM, @Structure.SI_C_ODT_TIME_IN_FORCE_ENUM, @Structure.SI_C_ODT_ORDER_TYPE_ENUM;
// @Rule.SI_C_ODT_ENUM_BOUNDARY: @Structure.SI_C_ODT_ORDER_SIDE_ENUM, @Structure.SI_C_ODT_TIME_IN_FORCE_ENUM, @Structure.SI_C_ODT_ORDER_TYPE_ENUM;
// @Structure.SI_C_ODT_ORDER_SIDE_ENUM: Order side enum (BUY/SELL)
enum OrderSide { BUY="BUY", SELL="SELL" }
// @Structure.SI_C_ODT_TIME_IN_FORCE_ENUM: Time-in-force enum (GTC/IOC/FOK)
enum TimeInForce { GTC="GTC", IOC="IOC", FOK="FOK" }
// @Structure.SI_C_ODT_ORDER_TYPE_ENUM: Order type enum (LIMIT/MARKET)
enum OrderType { LIMIT="LIMIT", MARKET="MARKET" }
// @Structure.SI_C_ODT_ORDER_STATUS_ENUM: Order status enum (lifecycle)
enum OrderStatus { PENDING,SUBMITTED,ACCEPTED,PARTIAL,FILLED,CANCELLED,REJECTED }

struct OrderRequest(BaseModel) {
  clordid:s, instrument_id:s, side:OrderSide, size:Decimal, order_type:OrderType=LIMIT, time_in_force:TimeInForce=GTC,
  price:Decimal?, reduce_only:b=F, post_only:b=F, strategy_id:s?, client_tags:list[s]=[], created_at_ns:i, trace_id:s?, signal_id:s?
// @Rule.SI_C_ODT_VALIDATION: @Structure.SI_C_ODT_ORDER_REQUEST_MODEL;

f order_request_validation(req: OrderRequest) -> b { ... }

f coerce_to_decimal(v:any)->Decimal? { v is None?None: v is Decimal?v: v is int|float?Decimal(str(v)): v is str?Decimal(v): raise ValueError }

f get_signature_payload()->s { ret "|".join(sorted_fields_alphabetically) }
}

// @Structure.SI_C_ODT_ORDER_RESPONSE_MODEL: OrderResponse schema (pydantic model)
struct OrderResponse(BaseModel) { clordid:s, exchange_order_id:s?, status:OrderStatus=PENDING, filled_size:Decimal="0", remaining_size:Decimal="0", avg_price:Decimal?, error_code:s?, error_message:s?, created_at_ns:i, updated_at_ns:i }

// @DocMeta.SI_C_SEC13_3_DECIMAL_UTILS: §13.3 Decimal Utils
// @SSOTRef.SI_C_ODT_DECIMAL_UTILS_DECIMAL_UTILS_PY: SSOT.DecimalUtils;
// @SSOTRef.SI_C_ODT_DECIMAL_VALIDATORS_DECIMAL_VALIDATORS_PY: SSOT.DecimalValidators;
// @Rule.SI_C_ODT_FLOAT_CONTAMINATION: @Structure.SI_C_ODT_INSTRUMENT_PRECISION;
// @Rule.SI_C_ODT_ROUNDING: @Function.SI_C_ODT_QUANTIZE_PRICE, @Function.SI_C_ODT_QUANTIZE_SIZE;
// @Rule.SI_C_ODT_YAML_FIELDS: @Structure.SI_C_ODT_INSTRUMENT_PRECISION;
// @Structure.SI_C_ODT_INSTRUMENT_PRECISION: InstrumentPrecision schema
struct InstrumentPrecision { tick_size:Decimal, lot_size:Decimal }
// @Rule.SI_C_POST_INIT_CHECK: @Structure.SI_C_ODT_INSTRUMENT_PRECISION;

// @DocMeta.SI_C_SEC13_3_1_SAFE_DECIMAL_TYPE_PYDANTIC_ANNOTATED: §13.3.1 SafeDecimal Type (Pydantic Annotated)
// @Rule.SI_C_ODT_SAFE_DECIMAL: @Function.SI_C_ODT_VALIDATE_DECIMAL_FROM_STRING;
// @Rule.SI_C_ODT_ACCEPTS: @Function.SI_C_ODT_VALIDATE_DECIMAL_FROM_STRING;
// @Rule.SI_C_ODT_REJECTS: @Function.SI_C_ODT_VALIDATE_DECIMAL_FROM_STRING;
// @Function.SI_C_ODT_QUANTIZE_PRICE: Quantize price to tick_size with ROUND_HALF_UP
f quantize_price(price:Decimal,tick_size:Decimal)->Decimal { ret (price/tick_size).quantize(1,rounding=ROUND_HALF_UP)*tick_size }
// @Function.SI_C_ODT_QUANTIZE_SIZE: Quantize size to lot_size with ROUND_DOWN
f quantize_size(size:Decimal,lot_size:Decimal)->Decimal { ret (size/lot_size).quantize(1,rounding=ROUND_DOWN)*lot_size }
// @Function.SI_C_ODT_FLOAT64_TO_DECIMAL: Convert float64 to Decimal with NaN/Inf rejection
f float64_to_decimal(v:f)->Decimal { isnan(v)|isinf(v)?raise ValueError("NaN/Inf"):Decimal(f"{v:.15g}") }
// @Rule.SI_C_ODT_CONVERSION_POINT: CONTRACT.StrategyPipeline;

// @Function.SI_C_ODT_VALIDATE_DECIMAL_FROM_STRING: Validator for SafeDecimal (reject float, accept str/int/Decimal)
f validate_decimal_from_string(v:any)->Decimal {
  v is Decimal?v: v is float?raise ValueError("Float not allowed"): v is int?Decimal(str(v)): v is str?Decimal(v): raise ValueError
}

// ===============================================
// @DocMeta.SI_C_SEC14_EXCHANGE_CLIENT_INTERFACE: §14 ExchangeClient Interface
// ===============================================

// @SSOTRef.SI_C_ECI_EXCHANGE_INTERFACE_INTERFACE_PY: SSOT.ExchangeInterface;
// @Rule.SI_C_ECI_ASYNC_ALL: @Interface.SI_C_ECI_EXCHANGE_CLIENT;
// @Rule.SI_C_ECI_KEY_NORMALIZE: @Interface.SI_C_ECI_EXCHANGE_CLIENT;
// @Structure.SI_C_ECI_POSITION: Position schema
struct Position { instrument_id:s, size:Decimal, avg_price:Decimal, unrealized_pnl:Decimal, realized_pnl:Decimal="0", liquidation_price:Decimal?, updated_at_ns:i }

// @Structure.SI_C_ECI_OPEN_ORDER: Open order schema
struct OpenOrder { clordid:s, exchange_order_id:s, instrument_id:s, side:s, order_type:s, price:Decimal?, original_size:Decimal, remaining_size:Decimal, filled_size:Decimal, status:s, time_in_force:s, created_at_ns:i }

// @Interface.SI_C_ECI_EXCHANGE_CLIENT: Exchange client interface contract
interface ExchangeClient {
// @Note.SI_C_ECI_CANCEL_ALL_ORDERS: cancelled count
  f cancel_all_orders(instrument_id:s?)->i
  f block_new_orders()->v
  f unblock_new_orders()->v
// @Note.SI_C_ECI_POSITIONS: size!=0
  f get_positions()->list[Position]
  f get_open_orders(instrument_id:s?)->list[OpenOrder]
  f submit_order(req:OrderRequest)->OrderResponse
  f cancel_order(clordid:s,exchange_order_id:s?)->b
  f ping()->b
  f get_server_time_ns()->i
  f set_execution_callback(cb:Callable[[ExecutionReport],Awaitable[v]])->v
// @Rule.SI_C_ECI_CALLBACK_FLOW: @Interface.SI_C_ECI_EXCHANGE_CLIENT, CONTRACT.NautilusActor;
  f set_order_status_callback(cb:Callable[[OrderStatusUpdate],Awaitable[v]])->v
// @Rule.SI_C_ECI_STATUS_EVENTS: @Interface.SI_C_ECI_EXCHANGE_CLIENT;
}

// @Class.SI_C_ECI_EXCHANGE_ERROR_CLASS: Base exchange error type
C ExchangeError(Exception) {}
// @Class.SI_C_ECI_RATE_LIMIT_ERROR_CLASS: Rate-limit error type
C RateLimitError(ExchangeError) {}
// @Class.SI_C_ECI_AUTH_ERROR_CLASS: Authentication error type
C AuthenticationError(ExchangeError) {}
// @Class.SI_C_ECI_ORDER_REJECTED_ERROR_CLASS: Order rejected error with error_code field
C OrderRejectedError(ExchangeError) { error_code:s }

// @DocMeta.SI_C_SEC14_3_MOCK_EXCHANGE_CLIENT_TYPES_TEST: §14.3 MockExchangeClient Types (Test)
// @SSOTRef.SI_C_ECI_MOCK_EXCHANGE_MOCK_PY: SSOT.MockExchange;

// @Structure.SI_C_ECI_FILL_MODE_ENUM: Mock fill mode enum
enum FillMode { IMMEDIATE,DELAYED,PARTIAL,NEVER,RANDOM }
// @Structure.SI_C_ECI_FILL_CONFIG: Mock fill config schema
struct FillConfig { mode:FillMode=IMMEDIATE, delay_ms:i=100, partial_fill_ratio:f=0.5, random_reject_rate:f=0.1, slippage_bps:i=0 }
// @Structure.SI_C_ECI_FILL_EVENT: Mock fill event schema
struct FillEvent { clordid:s, exchange_order_id:s, filled_size:Decimal, remaining_size:Decimal, fill_price:Decimal, timestamp_ns:i, is_final:b }

// @Class.SI_C_ECI_MOCK_EXCHANGE_CLIENT_CLASS: MockExchangeClient behavior contract (fill scheduling + callbacks)
C MockExchangeClient(ExchangeClient) {
  fill_config:FillConfig, latency_ms:i=0, _positions:d, _orders:d, _blocked:b=F, _fill_callback:Callable?, _pending_fills:d, _last_prices:d
  f submit_order(req:OrderRequest)->OrderResponse { latency_ms>0?sleep(latency_ms/1000):v -> _blocked?OrderResponse(status=REJECTED,error_code="BLOCKED"):(_schedule_fill(req,exchange_order_id)->OrderResponse(status=ACCEPTED)) }
  f _schedule_fill(req,eid)->v { mode=fill_config.mode -> (mode==RANDOM?_random_mode():mode)==NEVER?_orders[req.clordid]=OpenOrder(...):create_task(_execute_fill(req,eid,mode)) }
  f _execute_fill(req,eid,mode)->v { mode==DELAYED?sleep(delay_ms/1000):v -> fill_price=_calc_slippage(req) -> mode==PARTIAL?(filled=size*ratio,remaining=size-filled,is_final=F):(filled=size,remaining=0,is_final=T) -> _update_position(req.instrument_id,req.side,filled,fill_price) -> _fill_callback?_fill_callback(FillEvent(...)):v -> is_final?_orders.pop(clordid):_orders[clordid]=OpenOrder(remaining_size=remaining) }
  // Test Helpers
  f set_fill_callback(cb:Callable[[FillEvent],v])->v { _fill_callback=cb }
  f set_last_price(instrument_id:s,price:Decimal)->v { _last_prices[instrument_id]=price }
  f set_fill_config(config:FillConfig)->v { _fill_config=config }
  async f wait_all_fills(timeout:f=5.0)->v { _pending_fills?asyncio.wait(_pending_fills.values(),timeout=timeout):v }
  f reset()->v { [task.cancel() for task in _pending_fills.values()] -> _pending_fills.clear() -> _positions.clear() -> _orders.clear() -> _blocked=F -> _last_prices.clear() }
}

// ===============================================
// @DocMeta.SI_C_SEC15_SAFETY_PLANE_COMMAND_TYPES: §15 Safety Plane Command Types
// ===============================================

// @SSOTRef.SI_C_SPC_COMMANDS_PY: SSOT.SafetyCommands;
// @Rule.SI_C_SPC_TRANSPORT: @Const.SI_C_SPC_SAFETY_TOPIC_CONSTS;
// @Rule.SI_C_SPC_TOPIC: @Const.SI_C_SPC_SAFETY_TOPIC_CONSTS;
// @Rule.SI_C_SPC_SECURITY: @Structure.SI_C_SPC_SIGNED_COMMAND;
// @Rule.SI_C_SPC_RBAC: @Structure.SI_C_SPC_SIGNED_COMMAND, SSOT.RBACPolicy;

// @Const.SI_C_SPC_SAFETY_TOPIC_CONSTS: Safety plane Pub/Sub topic constants (cmd/ack)
const SAFETY_CMD_TOPIC:s = "safety:cmd"
const SAFETY_ACK_TOPIC:s = "safety:ack"
// --- end: SI_SPC_SAFETY_TOPIC_CONSTS ---

// @Structure.SI_C_SPC_SAFETY_COMMAND_TYPE_ENUM: Safety command type enum
enum SafetyCommandType {
  // @Rule.SI_C_SPC_PRIORITY: @Structure.SI_C_SPC_SAFETY_COMMAND_TYPE_ENUM;
  // @Rule.SI_C_SPC_ALIAS: @Structure.SI_C_SPC_SAFETY_COMMAND_TYPE_ENUM;
  KILL_L0="L0", KILL_L1="L1", KILL_L2="L2", RESET="RESET", STATUS="STATUS", MAINTENANCE="MAINTENANCE"
}

// @Structure.SI_C_SPC_SIGNED_COMMAND: Signed safety command schema
struct SignedCommand {
  // @Rule.SI_C_SPC_REQUIRED: @Structure.SI_C_SPC_SIGNED_COMMAND;
  // @Rule.SI_C_SPC_SAFETY_CMD_SIGNATURE: @Structure.SI_C_SPC_SIGNED_COMMAND;
  // @Rule.SI_C_SPC_EXPIRY: @Structure.SI_C_SPC_SIGNED_COMMAND;
  // @Rule.SI_C_SPC_NONCE: @Structure.SI_C_SPC_SIGNED_COMMAND;
  command_id:s, command_type:SafetyCommandType, ts_ns:i, issuer_id:s, nonce:s, signature:s, params:d, reason:s?
  f sign(secret:s)->v
  f verify(secret:s)->b
  f is_expired(max_age_ns:i=300_000_000_000)->b
  f _get_signature_payload()->s  // Fixed order: id:type:ts:issuer:nonce:params
}

// @Structure.SI_C_SPC_COMMAND_ACK: Safety command ack schema
struct CommandAck {
  // @Rule.SI_C_SPC_STATUS: @Structure.SI_C_SPC_COMMAND_ACK;
  // @Rule.SI_C_SPC_ERROR_CODES: @Structure.SI_C_SPC_COMMAND_ACK;
  ack_id:s, command_id:s, status:s, error_code:s?, error_message:s?, ts_ns:i, result:d?
}

// @Rule.SI_C_SPC_VERIFICATION: @Structure.SI_C_SPC_KILL_VERIFICATION_RESULT;
// @Rule.SI_C_SPC_COMPLETENESS: @Structure.SI_C_SPC_KILL_VERIFICATION_RESULT;
// @Rule.SI_C_SPC_RETRY: @Structure.SI_C_SPC_KILL_VERIFICATION_RESULT;
// @Structure.SI_C_SPC_KILL_VERIFICATION_RESULT: Kill verification result schema
struct KillVerificationResult { status:s, remaining_orders:i, remaining_positions:i, verified_at:s, retry_count:i, error:s? }

// @DocMeta.SI_C_SEC15_7_SAFETY_PLANE_EXCHANGE_CLIENT_CONFIG: §15.7 Safety Plane ExchangeClient Config
// @SSOTRef.SI_C_SPC_SAFETY_EXCHANGE_CLIENT_FILE: SSOT.SafetyExchangeClient;
// @Rule.SI_C_SPC_ISOLATION: @Structure.SI_C_SPC_SAFETY_EXCHANGE_CONFIG;
// @Rule.SI_C_SPC_PURPOSE: @Structure.SI_C_SPC_SAFETY_EXCHANGE_CONFIG;
// @Rule.SI_C_SPC_AVAILABILITY: @Structure.SI_C_SPC_SAFETY_EXCHANGE_CONFIG;
// @Structure.SI_C_SPC_SAFETY_EXCHANGE_CONFIG: Safety plane exchange config schema
struct SafetyExchangeConfig { exchange_id:s="binance", api_key:s, api_secret:s, testnet:b=T, timeout_ms:i=5000 }

// @Rule.SI_C_SPC_SAFETY_PLANE_SINGLETON: @Const.SI_C_SPC_SAFETY_PLANE_LOCK_CONSTS;
// @Rule.SI_C_SPC_LOCK: @Const.SI_C_SPC_SAFETY_PLANE_LOCK_CONSTS;
// @Const.SI_C_SPC_SAFETY_PLANE_LOCK_CONSTS: Safety plane singleton lock key/ttl constants
const SAFETY_PLANE_LOCK_KEY:s = "safety:plane:lock"
const SAFETY_PLANE_LOCK_TTL_SEC:i = 60
// --- end: SI_SPC_SAFETY_PLANE_LOCK_CONSTS ---


// ===============================================
// @DocMeta.SI_C_SEC18_REDIS_KEY_CATALOG_SSOT: §18 Redis Key Catalog (SSOT)
// ===============================================

// @Rule.SI_C_RKC_NAMING: @Const.SI_C_RKC_REDIS_KEYS_SAFETY_MAP;
// @Rule.SI_C_RKC_PROHIBITED: @Const.SI_C_RKC_REDIS_KEYS_SAFETY_MAP;
// @Rule.SI_C_RKC_REGISTRATION: @Const.SI_C_RKC_REDIS_KEYS_SAFETY_MAP;

// @DocMeta.SI_C_SEC18_2_SAFETY_PLANE_KEYS_SAFETY_REDIS_6380: §18.2 Safety Plane Keys (Safety Redis :6380)
// @SSOTRef.SI_C_RKC_SAFETY_REDIS_KEYS_PY: SSOT.SafetyRedisKeys;
// @Const.SI_C_RKC_REDIS_KEYS_SAFETY_MAP: Redis key catalog map for safety redis
const REDIS_KEYS_SAFETY = {
  // @Rule.SI_C_TTL: @Const.SI_C_RKC_REDIS_KEYS_SAFETY_MAP, SSOT.SharedConstants;
  SAFETY_HEARTBEAT: "safety:heartbeat:{component_id}",  // String, 6s TTL (SSOT)
  SAFETY_KILLSWITCH_STATE: "safety:killswitch:state",   // Hash, no TTL
  SAFETY_KILLSWITCH_VERIFICATION: "safety:killswitch:verification", // String, 3600s
  SAFETY_WATCHDOG_STATE: "safety:watchdog:state",       // String, no TTL
  SAFETY_ALERTS_ACTIVE: "safety:alerts:active",         // Set, no TTL
  SAFETY_AUDIT_LOG: "safety:audit:log",                 // Stream, 7d TTL
  SAFETY_PID_PREFIX: "safety:pid"                       // + :{component_id}
}

// @DocMeta.SI_C_SEC18_3_FEATURE_PIPELINE_KEYS_MAIN_REDIS_6379: §18.3 Feature Pipeline Keys (Main Redis :6379)
// @SSOTRef.SI_C_RKC_FEATURE_KEYS_FEATURE_TRANSPORT_PY: SSOT.FeatureTransport;
// @Const.SI_C_RKC_REDIS_KEYS_FEATURE_MAP: Redis key catalog map for feature pipeline
const REDIS_KEYS_FEATURE = {
  FEATURE_REQ: "feature:req:{model_id}",      // List, no TTL
  FEATURE_RESP: "feature:resp:{trace_id}",    // List, 10s TTL (SSOT: SHARED_CONSTANTS §2.2)
  BUFFER_REGISTRY: "buffer:registry:{buffer_id}" // Hash, no TTL
}

// @DocMeta.SI_C_SEC18_4_COMMAND_CONTROL_KEYS_MAIN_REDIS_6379: §18.4 Command/Control Keys (Main Redis :6379)
// @SSOTRef.SI_C_RKC_COMMAND_KEYS_IDEMPOTENCY_PY: SSOT.IdempotencyKeys;
// @Const.SI_C_RKC_REDIS_KEYS_COMMAND_MAP: Redis key catalog map for command/idempotency
const REDIS_KEYS_COMMAND = {
  CMD_EXECUTED: "cmd:executed:{command_id}",     // String, 24h TTL
  CLORDID_EXECUTED: "clordid:executed:{clordid}" // String, 24h TTL
}

// @DocMeta.SI_C_SEC18_5_SYSTEM_STATE_KEYS_MAIN_REDIS_6379: §18.5 System State Keys (Main Redis :6379)
// @SSOTRef.SI_C_RKC_SYSTEM_KEYS_REDIS_KEYS_PY: SSOT.SystemStateKeys;
// @Const.SI_C_RKC_REDIS_KEYS_SYSTEM_MAP: Redis key catalog map for system state
const REDIS_KEYS_SYSTEM = {
  SYSTEM_STATE: "system:state",                // Hash, 5s TTL (SSOT: SHARED_CONSTANTS §2.2)
  SYSTEM_CHECKPOINT_LATEST: "system:checkpoint:latest", // String, no TTL
  SYSTEM_COMPONENT: "system:component:{component_id}"  // Hash, no TTL
}

// @SSOTRef.SI_C_RKC_SHARED_CONSTANTS_SYSTEM_STATE_SCHEMA: SSOT.SharedConstants;
// @Rule.SI_C_RKC_SYSTEM_STATE_FIELDS: @SSOTRef.SI_C_RKC_SHARED_CONSTANTS_SYSTEM_STATE_SCHEMA;
// DEPRECATED: Below struct is superseded by SSOT canonical schema. Do not extend.
// struct SystemStateHash { phase:s, mode:s, maintenance_mode:b, maintenance_reason:s }
// ↑ Issues: "mode" ambiguous (禁止), maintenance_mode wrong type (b→s), missing 6 required fields

// @DocMeta.SI_C_SEC18_5_1_HEARTBEAT_VS_HEALTH_SEPARATION: §18.5.1 Heartbeat vs Health Separation
// @Rule.SI_C_RKC_LIVENESS: @Const.SI_C_RKC_REDIS_KEYS_SAFETY_MAP;
// @Rule.SI_C_RKC_READINESS: @Const.SI_C_RKC_REDIS_KEYS_SYSTEM_MAP;
// @Rule.SI_C_RKC_OWNERSHIP: @Const.SI_C_RKC_REDIS_KEYS_SAFETY_MAP, CONTRACT.HealthAggregator;
// @Rule.SI_C_RKC_PROHIBITION: @Const.SI_C_RKC_REDIS_KEYS_SYSTEM_MAP;

// HealthAggregator Types
// @SSOTRef.SI_C_RKC_HEALTH_AGGREGATOR_PY: SSOT.HealthAggregator;
// @Rule.SI_C_RKC_THRESHOLDS: @Structure.SI_C_RKC_COMPONENT_HEALTH_STRUCT;
// @Rule.SI_C_RKC_SSOT_ENUM: @Structure.SI_C_RKC_HEALTH_STATUS_ENUM, SSOT.SharedConstants;
// @Rule.SI_C_RKC_MAPPING: @Structure.SI_C_RKC_HEALTH_STATUS_ENUM;

// @Structure.SI_C_RKC_HEALTH_STATUS_ENUM: Infrastructure health status enum (UPPERCASE SSOT)
enum HealthStatus {
  HEALTHY="HEALTHY",
  WARNING="WARNING",
  DEGRADED="DEGRADED",
  CRITICAL="CRITICAL",
  STOPPED="STOPPED"
}

// @Structure.SI_C_RKC_COMPONENT_HEALTH_STRUCT: ComponentHealth schema (aggregated health state)
struct ComponentHealth { component_id:s, status:HealthStatus, last_heartbeat_ns:i, last_check_ns:i, message:s? }

// Backpressure Statistics
// @Const.SI_C_RKC_BP_STATS_CONSTS: Backpressure stats key prefix and TTL constants
const BP_STATS_PREFIX:s = "bp:stats"  // + :{component_id}
const BP_STATS_TTL_SEC:i = 60
// --- end: SI_RKC_BP_STATS_CONSTS ---


// @DocMeta.SI_C_SEC18_7_REDIS_KEY_CATALOG_CLASS_SSOT: §18.7 RedisKeyCatalog Class (SSOT)
// @SSOTRef.SI_C_RKC_REDIS_KEY_CATALOG_REDIS_KEYS_PY: SSOT.RedisKeyCatalog;
// @Rule.SI_C_RKC_REDIS_CATALOG_SINGLETON: @Class.SI_C_RKC_REDIS_KEY_CATALOG_CLASS, @Const.SI_C_RKC_REDIS_KEYS_SINGLETON_CONST;

// @Class.SI_C_RKC_REDIS_KEY_CATALOG_CLASS: RedisKeyCatalog canonical key builders/constants (SSOT)　dataclass(frozen=True)
C RedisKeyCatalog {
  // Safety Plane (Redis :6380)
  SAFETY_HEARTBEAT_PREFIX:s="safety:heartbeat"
  SAFETY_HEARTBEAT_TTL_SEC:i=6  // L0閾値(5s)+マージン(1s) - SSOT: SHARED_CONSTANTS §2.1
  SAFETY_KILLSWITCH_STATE:s="safety:killswitch:state"
  SAFETY_KILLSWITCH_VERIFICATION:s="safety:killswitch:verification"
  SAFETY_WATCHDOG_STATE:s="safety:watchdog:state"
  SAFETY_ALERTS_ACTIVE:s="safety:alerts:active"
  SAFETY_AUDIT_LOG:s="safety:audit:log"
  SAFETY_PID_PREFIX:s="safety:pid"
  // Feature Pipeline
  FEATURE_REQ_PREFIX:s="feature:req"
  FEATURE_RESP_PREFIX:s="feature:resp"
  FEATURE_RESP_TTL_SEC:i=10  // SSOT: SHARED_CONSTANTS §2.2
  BUFFER_REGISTRY_PREFIX:s="buffer_registry"
  // Backpressure Statistics
  BP_STATS_PREFIX:s="bp:stats"
  BP_STATS_TTL_SEC:i=60
  // Command / Idempotency
  CMD_EXECUTED_PREFIX:s="cmd:executed"
  CMD_EXECUTED_TTL_SEC:i=86400
  CLORDID_EXECUTED_PREFIX:s="clordid:executed"
  // System State
  SYSTEM_STATE:s="system:state"
  SYSTEM_CHECKPOINT_LATEST:s="system:checkpoint:latest"
  SYSTEM_COMPONENT_PREFIX:s="system:component"
  // Pub/Sub Topics
  TOPIC_SAFETY_CMD:s="safety:cmd"
  TOPIC_SAFETY_ACK:s="safety:ack"
  TOPIC_ALERT_PREFIX:s="alert"
  TOPIC_STATE_CHANGED:s="state:changed"
  TOPIC_MASTER_RELOAD:s="master:reload"
  TOPIC_POSITION_CORRECTION:s="position:correction"
  // Helper Methods (@staticmethod)

  @staticmethod f safety_heartbeat_key(component_id:s)->s { ret "safety:heartbeat:{component_id}" }
  @staticmethod f feature_request_topic(model_id:s)->s { ret "feature:req:{model_id}" }
  @staticmethod f feature_response_topic(trace_id:s)->s { ret "feature:resp:{trace_id}" }
  @staticmethod f cmd_executed_key(command_id:s)->s { ret "cmd:executed:{command_id}" }
  @staticmethod f system_component_key(component_id:s)->s { ret "system:component:{component_id}" }
  @staticmethod f alert_topic(source:s)->s { ret "alert:{source}" }
  @staticmethod f bp_stats_key(component_id:s)->s { ret "bp:stats:{component_id}" }
  @staticmethod f clordid_executed_key(clordid:s)->s { ret "clordid:executed:{clordid}" }
  @staticmethod f buffer_registry_key(buffer_id:s)->s { ret "buffer:registry:{buffer_id}" }
}

// @Const.SI_C_RKC_REDIS_KEYS_SINGLETON_CONST: RedisKeyCatalog singleton instance (module-level)
const REDIS_KEYS = RedisKeyCatalog()  // Singleton instance
// --- end: SI_RKC_REDIS_KEYS_SINGLETON_CONST ---


// ===============================================
// @DocMeta.SI_C_SEC19_COMPONENT_SIGNAL_TYPES: §19 Component & Signal Types
// ===============================================

// @DocMeta.SI_C_SEC19_8_COMPONENT_ID_ENUM: §19.8 ComponentId Enum
// @SSOTRef.SI_C_CST_COMPONENT_ID_FILE: SSOT.ComponentID;
// @Rule.SI_C_CST_CRITICAL: @Structure.SI_C_CST_COMPONENT_ID_ENUM;
// @Structure.SI_C_CST_COMPONENT_ID_ENUM: ComponentId enum (canonical component identifiers)
enum ComponentId {
  ORCHESTRATOR="orchestrator", SAFETY_PLANE="safety_plane", WATCHDOG="watchdog",
  FEATURE_PIPELINE="feature_pipeline", MODEL_PIPELINE="model_pipeline", STRATEGY_PIPELINE="strategy_pipeline", EXECUTION_PIPELINE="execution_pipeline",
  MARKET_DATA_ADAPTER="market_data_adapter", ORDER_GATEWAY="order_gateway", POSITION_MANAGER="position_manager",
  HEALTH_AGGREGATOR="health_aggregator", BUFFER_JANITOR="buffer_janitor", CHECKPOINT_MANAGER="checkpoint_manager"
}
// Type alias for compatibility (use ComponentId enum instead)
// @type.SI_C_CST_COMPONENT_ID_TYPE_ALIAS: Compatibility type alias (prefer ComponentId enum)
type ComponentIdType = s | ComponentId

// @DocMeta.SI_C_SEC19_10_PREDICTION_RESULT_ORDER_SIGNAL_SCHEMA: §19.10 PredictionResult & OrderSignal Schema
// @SSOTRef.SI_C_CST_SIGNAL_PY: SSOT.SignalTypes;
// @Rule.SI_C_CST_ZERO_COPY: @Structure.SI_C_CST_PREDICTION_RESULT;
// @Rule.SI_C_CST_PIPELINE_FLOW: @Structure.SI_C_CST_PREDICTION_RESULT;
// @Rule.SI_C_CST_FROM_DICT_ZEROCOPY: @Structure.SI_C_CST_PREDICTION_RESULT;
// @Rule.SI_C_CST_FROM_DICT_FALLBACK: @Structure.SI_C_CST_PREDICTION_RESULT;
// @Rule.SI_C_CST_SHM_LIFECYCLE: @Structure.SI_C_CST_PREDICTION_RESULT, @Class.SI_C_RSST_BUFFER_JANITOR;
// @Example.SI_C_CST_MODEL_OUTPUT: result=PredictionResult(model_id="btc_trend_v3",trace_id=fv.trace_id,prediction_value=float(raw),confidence=0.85,feature_vector_id=fv.vector_id)
// @Example.SI_C_CST_ENVELOPE: envelope=MessageEnvelope(source=ComponentId.MODEL_PIPELINE,destination=ComponentId.STRATEGY_PIPELINE,message_type="prediction_result",payload=result.to_serializable())

// @Structure.SI_C_CST_PREDICTION_RESULT: PredictionResult schema (zero-copy aware)
struct PredictionResult {
  model_id:s, trace_id:U, timestamp_ns:i,
  prediction_value:f|i|[f]|NDArray=0.0,
  confidence:f?, probabilities:d[s,f]?,
  schema_id:s="prediction_v1", feature_vector_id:U?, meta:d={},
  buffer_ref:s?  // SharedMemory buffer name
  f __post_init__() -> v  // NDArray→meta["shape","dtype"]
  f to_serializable() -> d  // Zero-Copy aware serialization
  f from_dict(data:d) -> PredictionResult  // Zero-Copy aware deserialization
}

// @Example.SI_C_CST_P4_STRATEGY_USAGE: on_prediction_result(envelope) → result=PredictionResult.from_dict(envelope.payload) → if result.prediction_value>THRESHOLD and (result.confidence or 0)>0.7 → OrderSignal(trace_id=result.trace_id,instrument_id="BTC/USDT.BINANCE",direction="LONG",strength=result.confidence,prediction_result_id=result.trace_id,model_id=result.model_id)
// @Structure.SI_C_CST_ORDER_SIGNAL: OrderSignal schema
struct OrderSignal {
  signal_id:U, trace_id:U, timestamp_ns:i,
  instrument_id:s="", direction:s="FLAT", strength:f=0.0, target_position_size:f?,
  prediction_result_id:U?, model_id:s?,
  max_position_size:f?, stop_loss_pct:f?, take_profit_pct:f?,
  meta:d={}
}

// @DocMeta.SI_C_SEC19_11_ORDER_INTENT_SCHEMA_META_SCHEMA_NAME_ORDER_INTENT_V1: §19.11 OrderIntent Schema (meta.schema_name = order_intent_v1)
// @SSOTRef.SI_C_CST_INTENT_TYPES_INTENT_PY: SSOT.IntentTypes;
// @Rule.SI_C_CST_SCHEMA_NAME: @Structure.SI_C_CST_ORDER_INTENT, SSOT.SchemaIdStrict;
// @Rule.SI_C_CST_RESPONSIBILITY: @Structure.SI_C_CST_ORDER_INTENT, @Structure.SI_C_CST_ORDER_SIGNAL, @Structure.SI_C_ODT_ORDER_REQUEST_MODEL;
// @Rule.SI_C_CST_CONVERSION_CHAIN: @Structure.SI_C_CST_ORDER_SIGNAL, @Structure.SI_C_CST_ORDER_INTENT, @Structure.SI_C_ODT_ORDER_REQUEST_MODEL;
// @Rule.SI_C_CST_IDEMPOTENCY_KEY: @Structure.SI_C_CST_ORDER_INTENT, CONTRACT.StateStore;
// @Rule.SI_C_CST_NO_CLORDID: @Structure.SI_C_CST_ORDER_INTENT, CONTRACT.OrderManager, SSOT.PluginManual;
// @Rule.SI_C_CST_NO_EXECUTION_DETAILS: @Structure.SI_C_CST_ORDER_INTENT;
// @Structure.SI_C_CST_ORDER_INTENT: OrderIntent schema (meta.schema_name=order_intent_v1)
struct OrderIntent {
  intent_id:U,              // Required: Idempotency primary key (UUID)
  trace_id:U,               // Required: Tracing (UUID)
  timestamp_ns:i,           // Required: UTC nanoseconds
  instrument_id:s,          // Required: e.g. "BTC/USDT.BINANCE"
  direction:s,              // Required: "LONG"|"SHORT"|"FLAT" (not "side" to avoid confusion)
  target_position_size:f,   // Required: Target position size (float, not Decimal for msgpack/cross-language compatibility)
  signal_id:U?,             // Optional but recommended: Reference to source OrderSignal
  constraints:d?,           // Optional: L6-interpreted constraints (e.g. max_slippage_pct, max_notional)
  meta:d={}                 // Optional: Extension field for future use
}

// @DocMeta.SI_C_SEC19_2_STREAM_DATA_TYPE: §19.2 StreamData Type
// @SSOTRef.SI_C_CST_STREAM_ROUTER_ROUTER_PY: SSOT.StreamRouter;
// @Structure.SI_C_CST_STREAM_DATA: StreamData schema
struct StreamData { stream_type:s, instrument_id:s, timestamp_ns:i, data:d, sequence_id:i }
// @Rule.SI_C_CST_STREAM_DATA_TRADES: @Structure.SI_C_CST_STREAM_DATA;
// @Rule.SI_C_CST_STREAM_DATA_QUOTES: @Structure.SI_C_CST_STREAM_DATA;
// @Rule.SI_C_CST_STREAM_DATA_BARS: @Structure.SI_C_CST_STREAM_DATA;
// @Structure.SI_C_CST_ROUTE_ENTRY: RouteEntry schema (routing node_ids + callback)
struct RouteEntry { node_ids:[s], callback:Callable? }

// ===============================================
// @DocMeta.SI_C_SEC20_CONFIG_TYPES: §20 Config Types
// ===============================================

// @DocMeta.SI_C_SEC20_3_CONFIG_LOADER_TYPES_PYDANTIC_SETTINGS: §20.3 ConfigLoader Types (Pydantic Settings)
// @Structure.SI_C_CFT_REDIS_SETTINGS: Redis settings schema (pydantic settings)
struct RedisSettings { model_config:SettingsConfigDict(env_prefix="REDIS_"), main_url:s="redis://localhost:6379/0", safety_url:s="redis://localhost:6380/0", max_connections:i=10 }

// @Structure.SI_C_CFT_SAFETY_SETTINGS: Safety settings schema (pydantic settings)
struct SafetySettings { model_config:SettingsConfigDict(env_prefix="SAFETY_"), heartbeat_interval_ms:i=500, heartbeat_ttl_s:i=40, watchdog_l0_threshold_s:i=5, watchdog_l1_threshold_s:i=15, watchdog_l2_threshold_s:i=30 }

// @Structure.SI_C_CFT_ORCHESTRATOR_SETTINGS: Orchestrator settings schema (pydantic settings)
struct OrchestratorSettings { model_config:SettingsConfigDict(env_prefix="ORCH_"), startup_timeout_ms:i=30000, state_ttl_s:i=5, health_check_interval_ms:i=5000 }

// @Structure.SI_C_CFT_RUNTIME_CONFIG: Runtime config schema (pydantic settings root)
struct RuntimeConfig {
  model_config:SettingsConfigDict(env_file=".env",env_file_encoding="utf-8",extra="ignore"),
  environment:s="development", debug:b=F,
  main_redis_url:s="redis://localhost:6379/0", safety_redis_url:s="redis://localhost:6380/0", require_main_redis:b=T,
  safety:SafetySettings, orchestrator:OrchestratorSettings
}

// ===============================================
// @DocMeta.SI_C_SEC22_MODEL_PATH_RESOLUTION_TYPES: §22 Model Path Resolution Types
// ===============================================

// @DocMeta.SI_C_SEC22_MPRT_MODEL_DIR: MODEL_DIR/{model_id}/weights.onnx # ONNX format, weights.pt # PyTorch format,weights.pkl # Pickle format ,weights.npz # NumPy format ,config.json # Model config ,manifest.yaml # Schema definition (P3 §6)

// @Const.SI_C_MPRT_MODEL_PATH_CONSTANTS: Model path resolution constants and formats
const MODEL_DIR_ENV:s = "MODEL_DIR"
// @Const.SI_C_MPRT_MODEL_DIRECTORY: Model path resolution constants and formats
const DEFAULT_MODEL_DIR:s = "myplugins/model_pipeline/models"
// @Type.SI_C_MPRT_MODEL_FORMAT: Model format
type ModelFormat = "onnx"|"pt"|"pkl"|"npz"
// @Const.SI_C_MPRT_MODEL_FILE_TYPES: Model path resolution constants and formats
const WEIGHT_FILE_PATTERNS = { "onnx":"weights.onnx", "pt":"weights.pt", "pkl":"weights.pkl", "npz":"weights.npz" }

```
