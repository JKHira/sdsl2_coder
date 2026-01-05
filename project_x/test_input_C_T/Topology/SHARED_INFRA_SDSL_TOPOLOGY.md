```typescript
// ===============================================
// SHARED_INFRASTRUCTURE TOPOLOGY / FLOW IDL v2.28
// Components, Flows, State Machines, Runtime Behavior
// ===============================================
// @DocMeta.SI_T_SOURCE: SHARED_INFRA_IDL.md (refactored)
// @DocMeta.SI_T_CATEGORY: Runtime Behavior, State Transitions, Flows, Processes

// ===============================================
// @DocMeta.SI_T_SEC1_RUNTIME_GUIDELINES_FLOWS: §1 Runtime Guidelines & Flows
// ===============================================

// @DocMeta.SI_T_RTGF_SEC1_2_ASYNC_SYNC_GUIDELINES_COM_03: §1.2 Async/Sync Guidelines (COM-03)
// @Rule.SI_T_RTGF_BOUNDARY: CONTRACT.IO_BOUNDARY;
// @Rule.SI_T_RTGF_IO_TYPES: CONTRACT.IO_TYPES;
// @Rule.SI_T_RTGF_ASYNC_AWAIT: CONTRACT.ASYNC_AWAIT;
// @Rule.SI_T_RTGF_SYNC_TO_ASYNC: CONTRACT.SYNC_RUNNER;
// @Rule.SI_T_RTGF_BLOCKING_IO: CONTRACT.BLOCKING_IO;

// @Structure.SI_T_ASG_ASYNC_SYNC_GUIDELINES: Async/Sync guidelines schema
struct AsyncSyncGuidelines { rule_1_async_await_required:s, rule_2_sync_to_async:s, rule_3_no_blocking_io:s }

// @DocMeta.SI_T_RTGF_SEC1_4_3_RESTART_RECONCILIATION_FLOW: §1.4.3 Restart Reconciliation Flow
// @Rule.SI_T_RTGF_GHOST_ORDER: SSOT.GHOST_ORDER_RECOVERY;
// @Rule.SI_T_RTGF_UNCONFIRMED_ORDER: SSOT.UNCONFIRMED_ORDER_RECOVERY;
// @Rule.SI_T_RTGF_RECONCILE_FLOW: CONTRACT.RECONCILIATION_FLOW;

// @DocMeta.SI_T_RTGF_SEC1_4_3_1_ORDER_SIGNAL_GENERATION_FLOW_CONVERSION_RESPONSIBILITY: §1.4.3.1 OrderSignal Generation Flow (Conversion Responsibility)
// @SSOTRef.SI_T_RTGF_SSOT_LOC_SIGNAL_GENERATOR: SSOT.SignalGenerator;
C OrderSignalGenerator(precision:InstrumentPrecision) {
  f generate_signal(instrument_id:s,side:s,size_float:f,price_float:f?)->OrderSignal {
    size_decimal=float64_to_decimal(size_float) -> price_decimal=price_float?float64_to_decimal(price_float):None ->
    size_quantized=quantize_size(size_decimal,precision.lot_size) ->
    price_quantized=price_decimal?quantize_price(price_decimal,precision.tick_size):None ->
    ret OrderSignal(instrument_id,side,size_quantized,price_quantized)
  }
}

// ===============================================
// @DocMeta.SI_T_SEC3_ERROR_HANDLING_FLOWS: §3 Error Handling Flows
// ===============================================

// @DocMeta.SI_T_SEC3_0_1_DECISION_FLOW: §3.0.1 Decision Flow
// @Rule.SI_T_EHF_SYSTEM_STATUS_FLOW: SSOT.SYSTEM_STATUS_FLOW, CONTRACT.ErrorLevel;

// @DocMeta.SI_T_SEC3_0_2_SCENARIO_MAPPING_KEY_EXAMPLES: §3.0.2 Scenario Mapping (Key Examples)
// @Scenario.SI_T_EHF_KILL_SWITCH_ACTIVATED: CRITICAL (system auto-stop)
// @Scenario.SI_T_EHF_SAFETY_REDIS_DOWN: CRITICAL (safety plane stopped, unrecoverable)
// @Scenario.SI_T_EHF_MAIN_REDIS_DOWN: ERROR (degraded mode OK)
// @Scenario.SI_T_EHF_HEARTBEAT_MISSING_PRE_DMS: WARNING (auto-recovery possible)
// @Scenario.SI_T_EHF_HEARTBEAT_DMS_TRIGGERED: CRITICAL (system auto-stop)
// @Scenario.SI_T_EHF_CPU_MEM_THRESHOLD: WARNING (continues, kill switch not fired)
// @Scenario.SI_T_EHF_BACKPRESSURE_DROP: CRITICAL (data loss)
// @Scenario.SI_T_EHF_BACKPRESSURE_RISE_NO_DROP: WARNING (auto-recovery)
// @Scenario.SI_T_EHF_ORDER_SUBMIT_FAIL_RETRY: ERROR (partial fail, system OK)
// @Scenario.SI_T_EHF_RECONCILIATION_MISMATCH: CRITICAL (position divergence, manual needed)
// @Scenario.SI_T_EHF_FEATURE_CALC_TIMEOUT: ERROR (single loop affected)
// @Scenario.SI_T_EHF_EXTERNAL_API_RATE_LIMIT: WARNING (auto-backoff recovery)

// @DocMeta.SI_T_SEC3_0_3_ALERT_MANAGER_INTEGRATION_FLOW: §3.0.3 AlertManager Integration Flow
// @Rule.SI_T_EHF_ALERT_FILTER: CONTRACT.AlertFilter, CONTRACT.ErrorLevel;
f should_alert(level:ErrorLevel)->b { ret level in [CRITICAL,ERROR] }
f get_alert_urgency(level:ErrorLevel)->s { level==CRITICAL?"high": level==ERROR?"low": "none" }

// ===============================================
// @DocMeta.SI_T_SEC4_SECURITY_MIDDLEWARE_FLOWS: §4 Security Middleware Flows
// ===============================================

// @DocMeta.SI_T_SEC4_3_5_SIGNATURE_MIDDLEWARE_FLOW: §4.3.5 Signature Middleware Flow
C SignatureVerificationMiddleware(app:FastAPI,rbac:RBACPolicy?,exempt:frozenset?=SIGNATURE_EXEMPT_PATHS) {
  f dispatch(req:Request,call_next)->Response {
    _should_skip(req)?call_next(req):
    (headers=HttpSignatureHeaders.from_headers(req.headers) -> body=req.body() ->
    (valid,err)=_verifier.verify(headers,req.method,req.url.path,body) ->
    !valid?raise HTTPException(401,err):
    (rbac&req.url.path not in RBAC_EXEMPT?
      (!rbac.can_access(headers.operator_id,req.url.path)?raise HTTPException(403,"Denied"):v)):v ->
    req.state.operator_id=headers.operator_id -> call_next(req))
  }
  f _should_skip(req:Request)->b {
// @Rule.SI_T_SMF_SKIP_GET_EXEMPT: CONTRACT.SIGNATURE_EXEMPT_PATHS;
// @Rule.SI_T_SMF_SKIP_OPTIONS: CONTRACT.SIGNATURE_EXEMPT_METHODS;
    (req.method=="GET" & req.url.path in _exempt_paths) ? ret T :
    req.method=="OPTIONS" ? ret T : ret F
  }
}

// @DocMeta.SI_T_SEC4_3_6_MIDDLEWARE_APPLICATION_ORDER_FAST_API_INTEGRATION: §4.3.6 Middleware Application Order & FastAPI Integration
// @Rule.SI_T_SMF_APP_ORDER: CONTRACT.MIDDLEWARE_ORDER;
// @SSOTRef.SI_T_SMF_SSOT_LOC_OP_API: SSOT.OperationsAPI;
// @Pattern.SI_T_SMF_CREATE_APP: FastAPI() → RBACPolicy.load_from_config() → app.add_middleware(SignatureVerificationMiddleware,rbac=rbac) → include_router(...)
// @Pattern.SI_T_SMF_ROUTERS: /api/v1/safety, /api/v1/control, /api/v1/monitoring (P4 Operations API)

// @DocMeta.SI_T_SEC4_3_7_ENDPOINT_OPERATOR_ID_USAGE: §4.3.7 Endpoint operator_id Usage
// @Rule.SI_T_SMF_OPERATOR_ACCESS: CONTRACT.OperatorState;
// @Example.SI_T_SMF_ENDPOINT: @router.post("/command") → operator_id=request.state.operator_id → audit log

// ===============================================
// @DocMeta.SI_T_SEC7_REDIS_STATE_STORE_FLOWS: §7 Redis State Store Flows
// ===============================================

// Main Redis Singleton Pattern
// @SSOTRef.SI_T_RSFF_SSOT_LOC_MAIN_REDIS: SSOT.MainRedis;
f init_main_redis(config:MainRedisConfig)->v { _main_redis_pool=create_pool(config) }
f get_main_redis()->Redis { !_main_redis_pool?raise RuntimeError("Not initialized"):Redis(connection_pool=_main_redis_pool) }
async f check_main_redis_health()->b { try{get_main_redis().ping()->ret T}except{ret F} }
async f check_safety_redis_health(pool:ConnectionPool)->b { try{Redis(pool).ping()->ret T}except{ret F} }

f create_safety_redis_pools(cfg:SafetyRedisPoolConfig)->(ConnectionPool,ConnectionPool) {
  common={host,port,db,socket_connect_timeout,socket_timeout,retry_on_timeout=F} ->
  kill_pool=ConnectionPool(max_connections=cfg.kill_switch_max_connections,**common) ->
  general_pool=ConnectionPool(max_connections=cfg.general_max_connections,**common) ->
  ret (kill_pool,general_pool)
}

// @DocMeta.SI_T_SEC7_3_7_4_BUFFER_JANITOR_FLOW_GAP_04: §7.3 -7.4 Buffer Janitor Flow (GAP-04)
// @SSOTRef.SI_T_RSFF_SSOT_LOC_JANITOR: SSOT.BufferJanitor, SSOT.ShmCleanup;
// @Rule.SI_T_RSFF_STARTUP_CLEAN: @SSOTRef.SI_T_RSFF_SSOT_LOC_JANITOR, CONTRACT.STARTUP_SEQUENCE;
// @Rule.SI_T_RSFF_JANITOR_INTERVAL: SSOT.JANITOR_INTERVAL;
// @Rule.SI_T_RSFF_ORPHAN_ALERT: CONTRACT.ErrorLevel, SSOT.ORPHAN_ALERT;
// @Rule.SI_T_RSFF_PID_CHECK: SSOT.PID_CHECK;

f clean_start_shm()->v { SHM_BASE_DIR.exists()?(shutil.rmtree(SHM_BASE_DIR)):v -> SHM_BASE_DIR.mkdir(parents=T,exist_ok=T) }

C BufferJanitor(registry:BufferRegistry,safety_redis:Redis,scan_interval_seconds:f=1.0) {
  f start()->v { _task=create_task(_run_loop()) }
  f stop()->v { _shutdown.set() -> _task&&wait(_task) }
  f _run_loop()->v { while !_shutdown.is_set() { try{_scan_and_cleanup()}except{log.error} -> wait_for(_shutdown.wait(),timeout=scan_interval) } }
  f _scan_and_cleanup()->v { expired=registry.find_expired(now_ns()) -> [_cleanup_buffer(b,"expired") for b in expired] -> orphaned=registry.find_orphaned(_get_live_pids()) -> [_cleanup_buffer(b,"orphaned") for b in orphaned] -> (expired|orphaned)?_report_cleanup(len(expired),len(orphaned)):v }
  f _cleanup_buffer(buf:d,reason:s)->v { file_path=SHM_BASE_DIR/"{buf['buffer_id']}.ipc" -> file_path.unlink(missing_ok=T) -> registry.delete(buf["path"]) }
  f _get_live_pids()->set[i] { ret {int(e.name) for e in Path("/proc").iterdir() if e.name.isdigit()} }
}

// @DocMeta.SI_T_SEC7_5_1_HEALTH_AGGREGATOR_FLOW_HEARTBEAT_HEALTH_CONVERTER: §7.5.1 HealthAggregator Flow (Heartbeat → Health Converter)
// @SSOTRef.SI_T_RSFF_SSOT_LOC_HEALTH_AGGREGATOR: SSOT.HealthAggregator, SSOT.HealthStatus, SSOT.ComponentHealth;
C HealthAggregator(safety_redis:Redis, main_redis:Redis, component_ids:[s]) {
  DEGRADED_THRESHOLD_SEC:f=3.0, CRITICAL_THRESHOLD_SEC:f=6.0, CHECK_INTERVAL_SEC:f=1.0, _running:b=F
  async f run()->v { _running=T -> while _running { for cid in component_ids { _check_and_update(cid) } -> sleep(CHECK_INTERVAL_SEC) } }
  async f _check_and_update(component_id:s)->v {
    // 1. Read safety:heartbeat:{id} -> 2. Evaluate Liveness -> 3. Write system:component:{id}
// @Rule.SI_T_RSFF_STOPPED: SSOT.R_INFRA_HEALTH_STATUS_ENUM;
    now_ns=time_ns() -> hb=safety_redis.get(safety_heartbeat_key(component_id)) ->
    hb==None?(status=STOPPED,msg="No heartbeat (process not running)"):
    ((now_ns-int(hb))/1e9<DEGRADED_THRESHOLD_SEC?(status=HEALTHY,msg=None):
    (now_ns-int(hb))/1e9<CRITICAL_THRESHOLD_SEC?(status=DEGRADED,msg=f"Delayed: {age}s"):(status=CRITICAL,msg=f"Timeout: {age}s")) ->
    main_redis.hset(system_component_key(component_id), ComponentHealth(...).asdict())
  }
  f stop()->v { _running=F }
}

// @DocMeta.SI_T_SEC18_5_2_ORCHESTRATOR_L2_HEALTH_MONITOR_FLOW: §18.5.2 Orchestrator L2 Health Monitor Flow
// @Rule.SI_T_RSFF_CRITICAL_ACTION: SSOT.R_INFRA_HEALTH_STATUS_ENUM, CONTRACT.KILL_SWITCH_ACTION;
// @Rule.SI_T_RSFF_TARGET: CONTRACT.REDIS_KEY_TARGET;
async f monitor_l2_health(main_redis:Redis, kill_switch:KillSwitch)->v {
  while T { health_data=main_redis.hgetall("system:component:market_data_adapter") ->
    (health_data & health_data["status"]=="critical") ? (log.critical("L2 CRITICAL") -> kill_switch.activate_l1("L2 failure")) : v ->
    sleep(1.0) }
}

// ===============================================
// @DocMeta.SI_T_SEC8_IMPLEMENTATION_TASKS_CORE: §8 Implementation Tasks (Core)
// ===============================================

// @Task.SI_T_ME_1: MessageEnvelope dataclass -> shared/messaging/envelope.py
// @Task.SI_T_ME_2: JSON/msgpack serialization -> shared/messaging/envelope.py [SI-ME-1]
// @Task.SI_T_ER_1: ErrorCategory, ErrorLevel enums -> shared/errors/categories.py
// @Task.SI_T_ER_2: StructuredError dataclass -> shared/errors/structured.py [SI-ER-1]
// @Task.SI_T_ER_3: ErrorHandler class -> shared/errors/handler.py [SI-ER-2]
// @Task.SI_T_CPL_1: BaseCommand, BaseAck -> shared/control/commands.py
// @Task.SI_T_CPL_2: HMAC signature validation -> shared/control/commands.py [SI-CP-1]
// @Task.SI_T_CPL_3: CommandExecutor -> shared/control/executor.py [SI-CP-1]
// @Task.SI_T_LG_1: Logging configuration -> shared/logging/config.py
// @Task.SI_T_RS_1: RedisStateStore generic -> shared/state/redis_store.py
// @Task.SI_T_WAL_1: WALEntry dataclass -> shared/wal/entry.py
// @Task.SI_T_WAL_2: NonBlockingWAL writer -> shared/wal/writer.py [SI-WAL-1]
// @Task.SI_T_WAL_3: Async Redis backup sync -> shared/wal/sync.py [SI-WAL-2]
// @Task.SI_T_TEST: Unit tests -> tests/unit/test_shared/ [SI-*]

// ===============================================
// @DocMeta.SI_T_SEC9_FILE_STRUCTURE: §9 File Structure
// ===============================================

// @Structure.SI_T_FS_ROOT: myplugins/shared/
// @Structure.SI_T_FS_MESSAGING: messaging/{__init__,envelope}.py -> MessageEnvelope
// @Structure.SI_T_FS_ERRORS: errors/{__init__,categories,structured,handler}.py -> ErrorCategory,ErrorLevel,StructuredError,ErrorHandler
// @Structure.SI_T_FS_CONTROL: control/{__init__,commands,executor}.py -> BaseCommand,BaseAck,CommandExecutor
// @Structure.SI_T_FS_LOGGING: logging/{__init__,config}.py -> configure_logging
// @Structure.SI_T_FS_STATE: state/{__init__,redis_store}.py -> RedisStateStore
// @Structure.SI_T_FS_ZERO_COPY: zero_copy/ -> From P2
// @Structure.SI_T_FS_BACKPRESSURE: backpressure/ -> From P2
// @Structure.SI_T_FS_KILL_SWITCH: kill_switch/ -> From P0
// @Structure.SI_T_FS_RBAC: rbac/ -> From P0
// @Structure.SI_T_FS_CHECKPOINT: checkpoint/ -> From P0
// @Structure.SI_T_FS_HEARTBEAT: heartbeat/ -> From P0
// @Structure.SI_T_FS_WAL: wal/{__init__,entry,writer,sync}.py -> WALEntry,NonBlockingWAL,Async backup
// @Structure.SI_T_FS_HASHING: hashing.py -> From P3

// ===============================================
// @DocMeta.SI_T_SEC15_SAFETY_PLANE_COMMAND_TRANSPORT_FLOW: §15 Safety Plane Command Transport Flow
// ===============================================

// @Rule.SI_T_SPCT_KILL_ROUTE: CONTRACT.SAFETY_PLANE_ROUTE;
// @Rule.SI_T_SPCT_KILL_FLOW: CONTRACT.SAFETY_PLANE_FLOW;

// @DocMeta.SI_T_SEC15_3_SAFETY_PLANE_SERVER_FLOW: §15.3 SafetyPlaneServer Flow
C SafetyPlaneServer {
  redis:Redis, secret:s, kill_switch:KillSwitch, rbac:RBACPolicy, _shutdown:Event
// @Rule.SI_T_SPCT_SERVER_FLOW: CONTRACT.SAFETY_PLANE_RPC_FLOW;
// @Rule.SI_T_SPCT_ERVER_ALIDATION: CONTRACT.SAFETY_PLANE_VALIDATION;
  async f run()->v
  async f _handle_message(data:bytes)->v
  async f _execute_command(cmd:SignedCommand)->d
  async f _verify_kill_completion(level:s)->KillVerificationResult
  async f _update_kill_verification_state(level:s,verification:d)->v  // Write to REDIS_KEYS.SAFETY_KILLSWITCH_VERIFICATION, alert on INCOMPLETE/FAILED
  async f _send_ack(command_id:s,status:s,error_code:s?,error_message:s?,result:d?)->v
  async f shutdown()->v
}

// @Rule.SI_T_SPCT_VERIFICATION_KEY: SSOT.REDIS_KEYS;
// @Rule.SI_T_SPCT_ALERT_ON_FAIL: CONTRACT.ErrorLevel, SSOT.ALERT_CRITERIA;

// @DocMeta.SI_T_SEC15_7_SAFETY_PLANE_INDEPENDENT_EXCHANGE_CLIENT_FLOW: §15.7 Safety Plane Independent ExchangeClient Flow
// @Rule.SI_T_SPCT_RESPONSIBILITY: CONTRACT.SAFETY_PLANE_RESPONSIBILITY;
// @Rule.SI_T_SPCT_INDEPENDENCE: CONTRACT.SYSTEM_INDEPENDENCE;
C SafetyExchangeClient {
  config:SafetyExchangeConfig, _exchange:Exchange?, _blocked:b
  async f initialize()->v
  async f cancel_all_orders()->i       // Returns cancelled count
  async f disconnect()->v               // Physical sever
  async f block_new_orders()->v
  async f get_open_orders()->[Order]   // Verification
  async f get_positions()->[Position]  // Verification
  @property f is_blocked()->b
}

// @DocMeta.SI_T_SEC15_8_SINGLETON_LOCK_PATTERN: §15.8 Singleton Lock Pattern
async f acquire_singleton_lock(redis:Redis)->b
async f refresh_singleton_lock(redis:Redis)->v
async f release_singleton_lock(redis:Redis)->v

// ===============================================
// @DocMeta.SI_T_SEC16_IMPLEMENTATION_TASKS_UPDATED: §16 Implementation Tasks (Updated)
// ===============================================

// @DocRef.SI_T_IMTU_TASKS_CANONICAL: See @DocMeta.SI_T_SEC23_IMPLEMENTATION_TASKS for the canonical task list.
// @Note.SI_T_IMTU_TASKS_UPDATED_POLICY: This section MUST contain only deltas (renames/moves/scope changes). Do NOT re-define existing @Task IDs.

// ── Deltas (examples) ─────────────────────────────────────────────

// Feature Transport tasks: path consolidation / location normalization
// @Task.SI_T_IMTU_T_1_UPDATE_LOCATION: Update the canonical location for FeatureRequest/Response -> shared/messaging/feature_transport.py (Ref: @Task.SI_T_FT_1).
// @Task.SI_T_IMTU_FT_2_UPDATE_LOCATION: Update the canonical location for FeatureClient (Redis Req/Rep) -> shared/messaging/feature_transport.py (Ref: @Task.SI_T_FT_2).

// Exchange / Order tasks: file split or merge changes
// @Task.SI_T_IMTU_ORD_1_UPDATE_LOCATION: Update canonical location for OrderRequest/Response -> shared/types/order.py (Ref: @Task.SI_T_OR_1).
// @Task.SI_T_IMTU_ORD_2_UPDATE_LOCATION: Update canonical location for OrderSide/TimeInForce/OrderType enums -> shared/types/order.py (Ref: @Task.SI_T_OR_2).
// @Task.SI_T_IMTU_EX_1_UPDATE_LOCATION: Update canonical location for ExchangeClient abstract interface -> shared/exchange/interface.py (Ref: @Task.SI_T_EX_1).
// @Task.SI_T_IMTU_EX_2_UPDATE_LOCATION: Update canonical location for Position/OpenOrder dataclass -> shared/exchange/interface.py (Ref: @Task.SI_T_EX_2).
// @Task.SI_T_IMTU_EX_3_UPDATE_DEP: MockExchangeClient remains -> shared/exchange/mock.py (Ref: @Task.SI_T_EX_3).

// Safety Plane tasks: linkage adjustments
// @Task.SI_T_IMTU_SP_1_UPDATE_LOCATION: SignedCommand/CommandAck dataclass -> shared/safety/commands.py (Ref: @Task.SI_T_SP_1).
// @Task.SI_T_IMTU_SP_2_UPDATE_LOCATION: SafetyPlaneServer main loop -> safety_plane/main.py (Ref: @Task.SI_T_SP_2).

// ===============================================
// @DocMeta.SI_T_SEC17_SUCCESS_CRITERIA: §17 Success Criteria
// ===============================================

// @Criteria.SI_T_SUCT_ME: CONTRACT.MessageEnvelope, SSOT.SERIALIZATION;
// @Criteria.SI_T_SUCT_ER: CONTRACT.ErrorHandler;
// @Criteria.SI_T_SUCT_CP: CONTRACT.CommandExecutor, CONTRACT.TIMEOUT;
// @Criteria.SI_T_SUCT_SIG: CONTRACT.SignatureVerification;
// @Criteria.SI_T_SUCT_RS: CONTRACT.RedisStateStore;
// @Criteria.SI_T_SUCT_FT: CONTRACT.FeatureClient, SSOT.REDIS_REQ_REP;
// @Criteria.SI_T_SUCT_ORD: CONTRACT.OrderRequest, SSOT.DECIMAL_SAFETY;
// @Criteria.SI_T_SUCT_EX: CONTRACT.ExchangeClient;
// @Criteria.SI_T_SUCT_SP: CONTRACT.SafetyPlaneServer, SSOT.REDIS_PUB_SUB;
// @Criteria.SI_T_SUCT_TEST: CONTRACT.TEST_SUITE;

// ===============================================
// @DocMeta.SI_T_SEC19_TOPIC_CATALOG_ROUTING: §19 Topic Catalog & Routing
// ===============================================

// @SSOTRef.SI_T_TCR_SSOT_LOC_TOPICS: SSOT.TOPICS;
// @Structure.SI_T_TCR_EMBS_PUBSUB_TOPIC: Pub/Sub topic catalog entry schema
struct PubSubTopic { topic:s, direction:s, description:s, ref_section:s }

// @Structure.SI_T_TCR_EMBS_TOPICS_CATALOG_CONSTS: Topic catalog constants
const TOPICS = {
  "safety:cmd": PubSubTopic("safety:cmd","Operator→SafetyPlane","Safety command send","§15.3"),
  "safety:ack": PubSubTopic("safety:ack","SafetyPlane→Operator","Safety execution response","§15.3"),
  "alert:{level}": PubSubTopic("alert:{level}","Components→Observer","Alert distribution","P4§3"),
  "state:changed": PubSubTopic("state:changed","Orchestrator→All","State change notification","P1§5"),
  "master:reload": PubSubTopic("master:reload","Admin→BNSLoader","BNS reload trigger","P3§5.3"),
  "position:correction": PubSubTopic("position:correction","Reconciler→System","Position correction notification","P4§4.3")
}

// @DocMeta.SI_T_SEC18_9_USAGE_EXAMPLE_REDIS_KEYS_COMPONENT_ID: §18.9 Usage Example (REDIS_KEYS + ComponentId)
// @Example.SI_T_TCR_CORRECT: heartbeat_key = REDIS_KEYS.safety_heartbeat_key(ComponentId.FEATURE_PIPELINE)
// @Example.SI_T_TCR_WRONG: heartbeat_key = REDIS_KEYS.safety_heartbeat_key("feature_pipeline")  // String hardcoding FORBIDDEN
// @Example.SI_T_TCR_TTL: ttl = REDIS_KEYS.SAFETY_HEARTBEAT_TTL_SEC  // → 6
// @Example.SI_T_TCR_TOPIC: topic = REDIS_KEYS.TOPIC_SAFETY_CMD  // → "safety:cmd"

// @DocMeta.SI_T_SEC19_2_STREAM_ROUTER_FLOW: §19.2 StreamRouter Flow
// @Rule.SI_T_TCR_DATA_FLOW: SSOT.StreamRouter;
// @Rule.SI_T_TCR_INIT_FLOW: CONTRACT.ROUTING_INIT_FLOW;
// @Example.SI_T_TCR_USAGE: router=StreamRouter() → router.load_bns_config("bns_config.yaml") → router.register_runner("btc_features", btc_runner.on_stream_data) → adapter=NautilusDataAdapter(stream_router=router,...)

C StreamRouter {
  _routes:d[s,RouteEntry], _runners:d[s,Callable]
  f load_bns_config(config_path:s)->v
  f register_runner(node_id:s,callback:Callable[[StreamData],Awaitable[v]])->v
  async f route(stream_data:StreamData)->v
  f get_instruments_for_node(node_id:s)->[s]
}

// @DocMeta.SI_T_SEC19_3_NAUTILUS_DATA_ADAPTER_FLOW: §19.3 NautilusDataAdapter Flow
// @SSOTRef.SI_T_TCR_SSOT_LOC_NAUTILUS_DATA_DAPTER: SSOT.NautilusDataAdapter;
// @Rule.SI_T_TCR_ENUM_ISOLATION: CONTRACT.ENUM_ISOLATION;
// @Rule.SI_T_TCR_CONVERSION: CONTRACT.DATA_CONVERSION, @Structure.SI_T_TCR_EMBS_PUBSUB_TOPIC;
// @Rule.SI_T_TCR_STREAM_TYPES: CONTRACT.STREAM_SUBSCRIPTION;
C NautilusDataAdapter(Actor) {
  _router:StreamRouter, _instruments:[s], _sequence:d[s,i], subscribe_trades:b=T, subscribe_quotes:b=T, subscribe_bars:b=F
  f on_start()->v  // Subscribe to configured stream types for each instrument
  f on_trade_tick(tick:TradeTick)->v
  f on_quote_tick(tick:QuoteTick)->v
  f _convert_trade(tick:TradeTick)->StreamData
  f _convert_quote(tick:QuoteTick)->StreamData
  f _next_sequence(instrument_id:s)->i
}

// @DocMeta.SI_T_SEC19_3_1_NAUTILUS_EXCHANGE_ADAPTER_FLOW: §19.3.1 NautilusExchangeAdapter Flow
// @SSOTRef.SI_T_TCR_SSOT_LOC_NAUTILUS_EXCHANGE_ADAPTER: SSOT.NautilusExchangeAdapter;
// @Rule.SI_T_TCR_TRADING_PERMISSION: SSOT.TRADING_ALLOWED_STATES;
// @Rule.SI_T_TCR_ENUM_CONVERSION: CONTRACT.ORDER_ENUM_CONVERSION;
// @Rule.SI_T_TCR_DECIMAL_SAFETY: SSOT.DECIMAL_SAFETY;
// @Rule.SI_T_TCR_LOCAL_RISK_GATE: CONTRACT.RISK_GATE, SSOT.REDIS_KEYS;
// @Rule.SI_T_TCR_EXEC_ENGINE_GUARD: CONTRACT.EXEC_ENGINE_GUARD;
// @Rule.SI_T_TCR_NO_EXEC_ENGINE_IN_INIT: CONTRACT.INIT_CONSTRAINTS;
// @Rule.SI_T_TCR_CLORDID_MATCH: CONTRACT.CLORDID_MAPPING;
// @Rule.SI_T_TCR_FIELD_MAPPING: CONTRACT.FIELD_MAPPING;
const TRADING_ALLOWED_STATES = {"RUNNING"}

C NautilusExchangeAdapter(ExchangeClient,Actor) {
  _trader_id:s, _exec_engine:ExecutionEngine?, _order_cache:d[s,Order], _safety_redis_url:s, _trading_allowed:b, _current_system_state:s, _state_subscriber_task:Task?
  f on_start()->v
  async f _subscribe_system_state()->v
  async f submit_order(request:OrderRequest)->OrderResponse
  async f cancel_order(clordid:s,instrument_id:s)->CancelResponse
  async f cancel_all_orders(instrument_id:s?)->i
  f _convert_to_nautilus_order(request:OrderRequest)->Order
}

// ===============================================
// @DocMeta.SI_T_SEC20_SYSTEM_BOOTSTRAP_ENTRY_POINT: §20 System Bootstrap & Entry Point
// ===============================================

// @SSOTRef.SI_T_SBEP_SSOT_LOC_BOOTSTRAP: SSOT.SystemBootstrap;
// @SSOTRef.SI_T_SBEP_SSOT_LOC_SHUTDOWN: SSOT.SafetyBootstrap;
// @SSOTRef.SI_T_SBEP_SSOT_LOC_REGISTRY: SSOT.PidRegistry;
// @SSOTRef.SI_T_SBEP_SSOT_LOC_STATE_MACHINE: SSOT.ConfigLoader, SSOT.RuntimeConfig;

// @Rule.SI_T_SBEP_BOOTSTRAP: CONTRACT.STARTUP_ORDER;
// @Rule.SI_T_SBEP_SHUTDOWN: CONTRACT.SHUTDOWN_ORDER;
// @Rule.SI_T_SBEP_CRASH_RECOVERY: CONTRACT.CRASH_RECOVERY_FLOW;
// @Rule.SI_T_SBEP_QUEUE_PURGE: CONTRACT.QUEUE_PURGE;
// @Rule.SI_T_SBEP_SHM_CLEANUP: CONTRACT.SHM_CLEANUP;
// @Rule.SI_T_SBEP_DEV_MODE: CONTRACT.DEV_MODE;
// @Rule.SI_T_SBEP_CRITICAL_SEPARATION: CONTRACT.PROCESS_ISOLATION;
// @Rule.SI_T_SBEP_NAUTILUS_INDEPENDENT: CONTRACT.EVENT_LOOP_ISOLATION;
// @Rule.SI_T_SBEP_SAFETY_PLANE_LIFECYCLE: CONTRACT.SAFETY_PLANE_LIFECYCLE;

// @Structure.SI_T_SBEP_ORC_PROCESS_ENTRYPOINTS_CONSTS: Process entrypoint catalog constants
const PROCESS_ENTRYPOINTS = {
  "safety_main.py": "Safety Plane (Watchdog + KillSwitch)",
  "system_main.py": "Orchestrator only",
  "feature_main.py": "Feature Pipeline",
  "model_main.py": "Model Pipeline",
  "strategy_main.py": "Strategy Pipeline",
  "nautilus_main.py": "NautilusTrader TradingNode",
  "local_runner.py": "Development single-process mode (NOT production)"
}

const STARTUP_ORDER = ["safety_main.py","system_main.py","nautilus_main.py","others"]
const SHUTDOWN_ORDER = ["others","system_main.py","safety_main.py"]
const SHUTDOWN_ORDER_COMPONENTS = ["operations","strategy","model","feature","orchestrator"]

// @Structure.SI_T_SBEP_ORC_BOOTSTRAP_COMPONENTS: Orchestrator bootstrap components schema
struct BootstrapComponents { config:RuntimeConfig, redis_main:RedisPool, redis_safety:RedisPool, force_safe_mode:b, registry:ComponentRegistry, state_machine:SystemStateMachine, orchestrator:Orchestrator }

f bootstrap()->BootstrapComponents {
  // 1. ConfigLoader.load()
  // 2. Safety Redis connect (FATAL if fail)
  // 3. crash_recovery check: _check_crash_recovery(redis_safety)
  // 4. Main Redis connect (DEGRADED or exit if require_main_redis)
  // 5. purge_stale_queues(redis_main, redis_safety, "orchestrator")
  // 6. clean_start_shm()
  // 7. Safety Plane existence check
  // 8. Orchestrator init
  // 9. Shutdown hook registration: signal.signal(SIGTERM, graceful_shutdown)
}

f _check_crash_recovery(redis_safety:RedisPool)->s? {
// @Rule.SI_T_SBEP_KILLSWITCH_CHECK: SSOT.REDIS_KEYS, CONTRACT.KILL_SWITCH_STATES;
// @Rule.SI_T_SBEP_STATE_CHECK: SSOT.REDIS_KEYS, CONTRACT.SYSTEM_STATES;
// @Rule.SI_T_SBEP_NORMAL: CONTRACT.STARTUP_LOGIC;
// @Rule.SI_T_SBEP_ERROR_SAFE: CONTRACT.ERROR_RECOVERY;
}

f purge_stale_queues(redis_main:RedisPool,redis_safety:RedisPool,component_id:s)->v {
// @Rule.SI_T_SBEP_PATTERN: SSOT.REDIS_KEYS;
// @Rule.SI_T_SBEP_ACTION: CONTRACT.REDIS_CLEANUP_PATTERN;
// @Rule.SI_T_SBEP_GHOST_PREVENTION: CONTRACT.GHOST_PREVENTION;
// @Rule.SI_T_SBEP_SAFETY_REDIS_SKIP: CONTRACT.PURGE_EXCLUSIONS;
}

f graceful_shutdown(components:BootstrapComponents)->v {
// @Rule.SI_T_SBEP_SHUTDOWN_ORDER: CONTRACT.SHUTDOWN_ORDER_COMPONENTS;
// @Rule.SI_T_SBEP_TIMEOUT: CONTRACT.SHUTDOWN_TIMEOUT;
// @Rule.SI_T_SBEP_EXCLUSION: CONTRACT.SHUTDOWN_EXCLUSIONS;
}

f main()->v { components=bootstrap() -> signal_handlers(SIGTERM,SIGINT->graceful_shutdown) -> orchestrator.run() }

// @DocMeta.SI_T_SBEP_SEC20_2_1_DI_WIRING_ORCHESTRATOR_RUN_PHASE: §20.2.1 DI Wiring concretization (initialize according to each phase inside Orchestrator.run())
// @Rule.SI_T_SBEP_PHASE_INITIALIZING: CONTRACT.DI_INITIALIZING_PHASE;
// @Rule.SI_T_SBEP_PHASE_SYNCING: CONTRACT.DI_SYNCING_PHASE;
// @Rule.SI_T_SBEP_PHASE_WARMUP: CONTRACT.DI_WURMUP_PHASE;
// @Rule.SI_T_SBEP_PHASE_READY: CONTRACT.DI_READY_PHASE;
// @Rule.SI_T_SBEP_CIRCULAR_REF: CONTRACT.DI_CIRCULAR_RESOLUTION;

// @DocMeta.SI_T_SBEP_SEC20_4_NAUTILUS_DRIVER_FLOW_EVENT_LOOP_ISOLATION: §20.4 NautilusDriver Flow (Event Loop Isolation)
// @Rule.SI_T_SBEP_ISOLATION: CONTRACT.EVENT_LOOP_ISOLATION;
// @Rule.SI_T_SBEP_COMMUNICATION: SSOT.REDIS_PUB_SUB;
// @Example.SI_T_SBEP_USAGE_NAUTILUS_DRIVER: driver=NautilusDriver(config) → driver.start() (runs in a separate thread) → ... → driver.stop() (graceful shutdown)
C NautilusDriver {
  _config:TradingNodeConfig, _node:TradingNode?, _thread:Thread?, _running:b
  f start()->v { _running?warning:threading.Thread(target=_run_node,daemon=T).start() }
  f _run_node()->v { TradingNode(config=_config).run() }
  f stop(timeout:f=10.0)->v { _running=F -> _node.stop() -> _thread.join(timeout) }
  @property is_running:b { _running & _thread.is_alive() }
  f add_actor(actor)->v { _node.trader.add_actor(actor) }
}

// @DocMeta.SI_T_SBEP_SEC20_SAFETY_MAIN_PY_INDEPENDENT_PROCESS: §20 safety_main.py (Independent Process)
// @Rule.SI_T_SBEP_NAUTILUS_SEPARATION: CONTRACT.PROCESS_ISOLATION;
// @Rule.SI_T_SBEP_STARTUP_ORDER_SAFETY_MAIN: CONTRACT.STARTUP_ORDER;
// @Rule.SI_T_SBEP_SHUTDOWN_ORDER_SAFETY_MAIN: CONTRACT.SHUTDOWN_ORDER;
// @Rule.SI_T_SBEP_REASON: CONTRACT.FAULT_TOLERANCE;
// @Rule.SI_T_SBEP_ISOLATION_REASON: CONTRACT.STABILITY_ISOLATION;
// @Rule.SI_T_SBEP_NAUTILUS_INDEPENDENT_SAFETY_MAIN: CONTRACT.EVENT_LOOP_ISOLATION;
// @Structure.SI_T_SBEP_SP_SAFETY_COMPONENTS: Safety plane bootstrap components schema
struct SafetyComponents { config:RuntimeConfig, redis_safety:RedisPool, kill_switch:KillSwitchController, watchdog:DeadManSwitch, cmd_listener:SafetyCommandListener }

f bootstrap_safety()->SafetyComponents {   // 1. ConfigLoader.load()   // 2. Safety Redis connect (FATAL if fail)   // 3. KillSwitchController init   // 4. DeadManSwitch init   // 5. SafetyCommandListener init   // 6. Watchdog heartbeat registration }

f run_safety_plane(components:SafetyComponents)->v {
// @Rule.SI_T_SBEP_PARALLEL: CONTRACT.PARALLEL_EXECUTION;
// @Rule.SI_T_SBEP_WAIT: CONTRACT.TASK_ORCHESTRATION;
}

f _heartbeat_loop(redis:RedisPool,config:RuntimeConfig)->v {
// @Rule.SI_T_SBEP_KEY: SSOT.REDIS_KEYS;
// @Rule.SI_T_SBEP_TTL: SSOT.SAFETY_HEARTBEAT_TTL_SEC;
}

f shutdown_safety(components:SafetyComponents)->v { watchdog.stop() -> cmd_listener.stop() -> redis_safety.close() }

// @DocMeta.SI_T_SBEP_SEC20_NAUTILUS_MAIN_PY_FLOW: §20 nautilus_main.py Flow
// @Rule.SI_T_SBEP_CRITICAL_PID: CONTRACT.L2_EMERGENCY_KILL;
// @Rule.SI_T_SBEP_ZOMBIE_PREVENTION: CONTRACT.ZOMBIE_PREVENTION;
// @Rule.SI_T_SBEP_SIGNAL_WAIT: CONTRACT.SIGNAL_HANDLING;
const SAFETY_PID_KEY:s = "safety:pid:nautilus"

f register_pid(safety_redis:Redis)->v { safety_redis.set(SAFETY_PID_KEY,str(os.getpid())) }
f unregister_pid(safety_redis:Redis)->v { safety_redis.delete(SAFETY_PID_KEY) }
f main()->v { config=ConfigLoader.load() -> register_pid(safety_redis) -> driver=NautilusDriver(config) -> driver.add_actor(adapter) -> driver.start() -> signal.signal(SIGTERM,shutdown_handler) -> signal.pause() }

// @DocMeta.SI_T_SEC20_3_CONFIG_LOADER_FLOW: §20.3 ConfigLoader Flow
C ConfigLoader {
  _instance:RuntimeConfig?=None
  @classmethod f load(env_file:s?=None)->RuntimeConfig { _instance?_instance:RuntimeConfig() }
  @classmethod f reload()->RuntimeConfig { _instance=None -> load() }
}

// ===============================================
// @DocMeta.SI_T_SEC21_CROSS_PLATFORM_PROCESS_UTILITIES: §21 Cross-Platform Process Utilities
// ===============================================
// @SSOTRef.SI_T_CPPU_SSOT_LOC_PROCESS_UTILS: SSOT.ProcessUtils;

// @Rule.SI_T_CPPU_PORTABILITY: CONTRACT.CROSS_PLATFORM_SUPPORT;
// @Example.SI_T_CPPU_BUFFER_JANITOR: BufferJanitor._is_publisher_alive(desc) → is_pid_alive(desc.publisher_pid)
f is_pid_alive(pid:i)->b {
// @Rule.SI_T_CPPU_PID_ISPATCH: CONTRACT.PLATFORM_DISPATCH;
  sys.platform=="linux"?_is_pid_alive_linux(pid):
  sys.platform=="darwin"?_is_pid_alive_unix(pid):
  sys.platform=="win32"?_is_pid_alive_windows(pid):_is_pid_alive_unix(pid)
}

f _is_pid_alive_linux(pid:i)->b { ret os.path.exists(f"/proc/{pid}") }
f _is_pid_alive_unix(pid:i)->b { try{os.kill(pid,0)->ret T}except ProcessLookupError{ret F}except PermissionError{ret T} }
f _is_pid_alive_windows(pid:i)->b { handle=ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION,F,pid) -> handle?(CloseHandle(handle)->ret T):ret F }
f get_current_pid()->i { ret os.getpid() }
f get_process_start_time(pid:i)->i? {
// @Rule.SI_T_CPPU_LINUX: SSOT.LINUX_PID_STAT;
// @Rule.SI_T_CPPU_MACOS_WIN: SSOT.PSUTIL_CREATE_TIME;
}

// ===============================================
// @DocMeta.SI_T_SEC22_MODEL_PATH_RESOLUTION_FLOW: §22 Model Path Resolution Flow
// ===============================================
// @SSOTRef.SI_T_MPRF_SSOT_LOC_MODEL_PATH_RESOLVER: SSOT.ModelPathResolver;

C ModelPathResolver {
  _model_dir:Path
  f __init__(model_dir:s?=None) { _model_dir = model_dir | os.getenv(MODEL_DIR_ENV) | DEFAULT_MODEL_DIR }
  f resolve(model_id:s,format:ModelFormat="onnx")->Path {
// @Rule.SI_T_MPRF_CHECK: CONTRACT.FILE_EXISTENCE_CHECK;
// @Rule.SI_T_MPRF_FALLBACK: CONTRACT.MODEL_FORMAT_FALLBACK;
  }
  f resolve_config(model_id:s)->Path { ret _model_dir/model_id/"config.json" }
  f resolve_manifest(model_id:s)->Path { ret _model_dir/model_id/"manifest.yaml" }
  f list_models()->[s] { ret [d.name for d in _model_dir.iterdir() if d.is_dir() & !d.name.startswith(".")] }
}

// @Example.SI_T_MPRF_MODEL_INFERENCE_ACTOR: resolver=ModelPathResolver() → model_path=resolver.resolve(model_id,"onnx") → config_path=resolver.resolve_config(model_id)

// ===============================================
// @DocMeta.SI_T_SEC23_IMPLEMENTATION_TASKS: §23 Implementation Tasks
// ===============================================
//
// @Task.SI_T_IMPT_NA_1: NautilusDataAdapter (feature_pipeline/online/adapters/nautilus_adapter.py)
// @Task.SI_T_IMPT_NA_2: NautilusExchangeAdapter (shared/exchange/adapters/nautilus_adapter.py)
//
// @Task.SI_T_IMPT_BT_1: system_main.py
// @Task.SI_T_IMPT_BT_2: ConfigLoader (shared/config/loader.py)
//
// @Task.SI_T_IMPT_XP_1: process.py (shared/utils/process.py)
// @Task.SI_T_IMPT_XP_2: BufferJanitor fix (shared/zerocopy/janitor.py)
//
// @Task.SI_T_IMPT_MP_1: ModelPathResolver (model_pipeline/loader.py)
// @Task.SI_T_IMPT_MP_2: ModelInferenceActor integration (model_pipeline/inference/actor.py) (Ref: @Task.SI_T_MP_1)
//
// @Task.SI_T_IMPT_RK_1: RedisKeyCatalog dataclass (shared/messaging/redis_keys.py)
// @Task.SI_T_IMPT_RK_2: Migrate existing hardcoded keys (all files using Redis keys) (Ref: @Task.SI_T_RK_1)
// @Task.SI_T_IMPT_RK_3: Add CI check for hardcoded keys (CI pipeline) (Ref: @Task.SI_T_RK_1)
//
// @Task.SI_T_IMPT_HA_1: HealthAggregator (shared/health/aggregator.py)
```
