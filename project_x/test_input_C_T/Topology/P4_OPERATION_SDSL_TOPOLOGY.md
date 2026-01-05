```typescript
// P4: Operations Code Plan - TOPOLOGY / FLOW IDL
// Component flows, state transitions, runtime behavior, routing
// SSOT: Manual Intervention, Dashboard, Health API, Reconciliation

// ─────────────────────────────────────────────────────────────────────
// @DocMeta.P4_T_SEC1_MAN_COMMANDS_FLOW_CQRS_PATTERN: §1 MAN Commands Flow (CQRS Pattern)
// ─────────────────────────────────────────────────────────────────────

// @Rule.P4_T_MAN_RBAC_MATRIX: SSOT.RBAC_MATRIX;
// @Rule.P4_T_MAN_APPROVAL_POLICY: SSOT.APPROVAL_POLICY;
// @Rule.P4_T_MAN_CQRS_HMAC: SSOT.CQRS_PATTERN, SSOT.HMAC_SIGNATURE;
// @Rule.P4_T_MAN_KILL_PATH: @Structure.P4_T_AGWR_RPC_REDIS_RPC_HANDLER, SSOT.SAFETY_PLANE;
// @Rule.P4_T_MAN_KILL_UI_PROHIBITIONS: SSOT.KILL_SWITCH_CONSTRAINTS;
// @Rule.P4_T_MAN_KILL_REQUIREMENTS: SSOT.RBAC, @Structure.P4_T_ADL_AUDIT_LOGGER, SSOT.HMAC_SIGNATURE;

// @Rule.P4_T_TOGGLE_PHASE: SSOT.SYSTEM_PHASES;

// ─────────────────────────────────────────────────────────────────────
// @DocMeta.P4_T_SEC2_ALERT_THRESHOLD_ACTIONS: §2 Alert Threshold Actions
// ─────────────────────────────────────────────────────────────────────

// Alert routing behavior (thresholds defined in CONTRACT)
// @Rule.P4_T_ALERT_BACKPRESSURE_ACTION: CONTRACT.SAFETY_REDIS;
// @Rule.P4_T_ALERT_ERROR_RATE_ACTION: CONTRACT.CIRCUIT_BREAKER;
// @Rule.P4_T_ALERT_LATENCY_P99_ACTION: CONTRACT.SYSTEM_STATE;
// @Rule.P4_T_ALERT_MEMORY_ACTION: SSOT.SYSTEM_PHASES, SSOT.ALERT_ACTIONS;
// @Rule.P4_T_ALERT_HEARTBEAT_ACTION: CONTRACT.WATCHDOG;

// ─────────────────────────────────────────────────────────────────────
// @DocMeta.P4_T_SEC3_HEALTH_API_COMPONENT: §3 Health API Component
// ─────────────────────────────────────────────────────────────────────

// @Structure.P4_T_HAPIC_HEALTH_ROUTER: Health API router for system/phase/component health endpoints
C HealthRouter(prefix="/api/health") {
// @Rule.P4_T_HAPIC_RBAC_OBSERVER_PLUS: SSOT.RBAC_POLICY;
// @Function.P4_T_HAPIC_GET_SYSTEM_HEALTH: Health API endpoint returning overall system health
  f get_system_health() -> SystemHealthResponse
// @Function.P4_T_HAPIC_GET_PHASE_HEALTH: Health API endpoint returning health for a specific phase (404 if invalid)
  f get_phase_health(phase:s) -> PhaseHealth { phase!in(VALID_PHASES)?HTTPException(404) }
// @Function.P4_T_HAPIC_GET_COMPONENTS_HEALTH: Health API endpoint returning per-component health summary
  f get_components_health() -> ComponentsHealthResponse
}

// ─────────────────────────────────────────────────────────────────────
// @DocMeta.P4_T_SEC4_DASHBOARD_SSE_FLOW: §4 Dashboard & SSE Flow
// ─────────────────────────────────────────────────────────────────────

// @Rule.P4_T_DSSE_DASH_PRIORITY: SSOT.DASHBOARD_PRIORITIES;
// @Rule.P4_T_DSSE_UPDATE_CRITICAL: SSOT.UPDATE_INTERVALS;
// @Rule.P4_T_DSSE_UPDATE_REALTIME: SSOT.UPDATE_INTERVALS;
// @Rule.P4_T_DSSE_UPDATE_IMPORTANT: SSOT.UPDATE_INTERVALS;
// @Rule.P4_T_DSSE_UPDATE_INFO: SSOT.UPDATE_INTERVALS;

// Dashboard Panel Config (P4_01_P4_02)
// | Priority | Panel            | DataSource    | Interval      | Status       |
// |----------|------------------|---------------|---------------|--------------|
// | 1        | SystemStatus     | HealthAPI     | 1s            | REQUIRED     |
// | 2        | KillSwitchPanel  | Orchestrator  | SSE(realtime) | REQUIRED     |
// | 3        | RiskMetrics      | Redis         | 1s            | REQUIRED     |
// | 4        | LatencyDashboard | Redis         | 5s            | Semi-req     |
// | 5        | ComponentHealth  | HealthAPI     | 5s            | Semi-req     |
// | 6        | PhaseStatus      | HealthAPI     | 5s            | -            |
// | 7        | PositionSummary  | Redis         | 1s            | -            |
// | 8        | PnLChart         | Redis         | 1s            | -            |
// | 9        | RecentAlerts     | AlertRouter   | SSE(realtime) | -            |
// | 10       | AuditLog         | PostgreSQL    | 10s           | -            |



// @Structure.P4_T_DSSE_EVENT_ROUTER: Events/SSE router for dashboard streaming
C EventRouter(prefix="/api/events") {
// @Rule.P4_T_DSSE_EV_RBAC_OBSERVER_PLUS: SSOT.RBAC_POLICY;
// @Function.P4_T_DSSE_EV_VALIDATE_SSE_AUTH: Validate SSE authorization according to SSE_AUTH_MODE
  f validate_sse_auth(request:Request) -> b {
    SSE_AUTH_MODE==NONE?ret T :
    SSE_AUTH_MODE==QUERY_TOKEN?(request.query_params.get("token")!=SSE_API_KEY?HTTPException(401)) :
    SSE_AUTH_MODE==API_KEY?(request.headers.get("X-API-Key")!=SSE_API_KEY?HTTPException(401)) :
    SSE_AUTH_MODE==SESSION?(!validate_session(request.cookies.get("session_id"))?HTTPException(401)) :
    SSE_AUTH_MODE==MTLS?(!request.scope.transport.peercert?HTTPException(401)) : ret T
  }
// @Function.P4_T_DSSE_EV_EVENT_STREAM: SSE event stream endpoint (generator-backed)
  f event_stream(request:Request) -> EventSourceResponse { generate()→yield{event,data} }
}

// ─────────────────────────────────────────────────────────────────────
// @DocMeta.P4_T_SEC5_RECONCILIATION_FLOW: §5 Reconciliation Flow
// ─────────────────────────────────────────────────────────────────────

// @Structure.P4_T_RCF_POSITION_RECONCILER: Reconcile internal vs exchange state and emit correction events (WAL-first)
C PositionReconciler(config:ReconciliationConfig,redis:Redis,exchange:ExchangeClient) {
// @Rule.P4_T_RCF_RECON_FLOW: @Function.P4_T_RCF_RECONCILE, @Function.P4_T_RCF_APPLY_CORRECTIONS, @Function.P4_T_RCF_CANCEL_GHOST_ORDERS;
// @Rule.P4_T_RCF_GHOST_CRASH_RECOVERY: @Function.P4_T_RCF_CANCEL_GHOST_ORDERS, SSOT.CRASH_RECOVERY_SAFETY;
// @Rule.P4_T_RCF_RECON_WAL_REDIS: CONTRACT.POSITION_CORRECTION_EVENT, SSOT.WAL_SSOT;
// @Function.P4_T_RCF_RECONCILE: Reconcile internal vs exchange state and emit correction events (WAL-first)
  f reconcile(trace_id:s) -> ReconciliationResult {
    exchange_state=_fetch_exchange_state_with_retry(trace_id) :
    exchange_state==null ? ret ReconciliationResult(F,0,0,skipped_reason="API failure") :
    internal_state=_fetch_internal_state() ->
    mismatches=_compare_states(exchange_state,internal_state) ->
    mismatches?_apply_corrections(mismatches,trace_id) ->
    ghost_cancelled=_cancel_ghost_orders(trace_id) ->
    ret ReconciliationResult(T,len(mismatches),len(mismatches),ghost_cancelled)
  }
// @Function.P4_T_RCF_CANCEL_GHOST_ORDERS: Cancel ghost orders on exchange immediately (ghost-order safety)
  f _cancel_ghost_orders(trace_id:s) -> i {
// @Rule.P4_T_RCF_GHOST_ORDER_CANCEL: @Function.P4_T_RCF_CANCEL_GHOST_ORDERS, SSOT.GHOST_ORDER_SAFETY;
    exchange_orders=exchange.get_open_orders() ->
    known_ids=order_manager.get_all_open_order_ids() ->
    ghosts=[o for o in exchange_orders if o.clordid!in known_ids & o.exchange_order_id!in known_ids] ->
    foreach(ghost in ghosts){ log.warning("ghost_order_detected") -> exchange.cancel_order(ghost) }
  }
// @Function.P4_T_RCF_APPLY_CORRECTIONS: Apply reconciliation corrections via WAL-first event path (no direct Redis write)
  f _apply_corrections(mismatches:d[],trace_id:s) {
// @Rule.P4_T_RCF_CORRECTION_EVENT_PATH: CONTRACT.POSITION_CORRECTION_EVENT, SSOT.WAL_SSOT;
// @Rule.P4_T_RCF_WAL_IS_SSOT_REDIS_IS_VIEW: SSOT.WAL_SSOT, CONTRACT.REDIS_VIEW;
    foreach(m in mismatches){
      log.warning("reconciliation_mismatch",instrument_id=m.instrument_id) ->
      correction=PositionCorrectionEvent(trace_id,instrument_id,RECONCILIATION,old_qty,new_qty,...) ->
      order_manager.apply_position_correction(correction)
      // OrderManager writes to WAL first, then updates Redis view
    }
  }
}

// @Structure.P4_T_RCF_RECONCILIATION_SCHEDULER: Schedule reconciliation on startup catchup, periodic, and state transitions
C ReconciliationScheduler(reconciler:PositionReconciler,redis:Redis,config:ReconciliationSchedulerConfig) {
// @Rule.P4_T_RCF_PUBSUB_CATCHUP: CONTRACT.SYSTEM_STATE, SSOT.CATCHUP_STRATEGY;
// @Function.P4_T_RCF_SCHED_START: Start reconciliation scheduler (startup catchup + periodic loop)
  f start() { _check_missed_events() -> _running=T -> _periodic_task=create_task(_periodic_loop()) }
// @Function.P4_T_RCF_RUN_RECONCILIATION: Execute one reconciliation run with reason tagging and metrics/audit hooks
  f _check_missed_events() {
// @Rule.P4_T_RCF_PUBSUB_FIX: SSOT.CATCHUP_STRATEGY, CONTRACT.SYSTEM_STATE;
    current_state=redis.get(REDIS_KEYS.SYSTEM_STATE) ->
    current_state in PHASES_AFTER_SYNCING ? _run_reconciliation("startup_catchup")
  }
// @Function.P4_T_RCF_SCHED_PERIODIC_LOOP: Periodic reconciliation loop runner (operational contract)
  f _periodic_loop() { while(_running){ sleep(config.periodic_interval_sec) -> _run_reconciliation("periodic") } }
// @Function.P4_T_RCF_SCHED_ON_SYNCING_COMPLETE: Trigger reconciliation when syncing completes (if enabled)
  f on_syncing_complete() { config.run_on_syncing_complete ? _run_reconciliation("syncing_complete") }
// @Function.P4_T_RCF_SCHED_ON_KILLSWITCH_RESET: Trigger reconciliation after killswitch reset (if enabled)
  f on_killswitch_reset() { config.run_on_killswitch_reset ? _run_reconciliation("killswitch_reset") }
}

// @Structure.P4_T_OPS_OPERATIONS_SERVICE: Operations service orchestrating reconciliation triggers from state changes
C OperationsService(reconciler:PositionReconciler,...) {
// @Rule.P4_T_RCF_EVENT_HANDLER: @Structure.P4_T_OPS_OPERATIONS_SERVICE, @Structure.P4_T_RCF_RECONCILIATION_SCHEDULER;
// @Rule.P4_T_RCF_RECOVERY_READY: CONTRACT.SYSTEM_PHASE, @Function.P4_T_OPS_ON_STATE_CHANGE;
// @Function.P4_T_RCF_OPS_ON_STATE_CHANGE: Handle system state transitions and trigger reconciliation scheduler
  f on_state_change(old:SystemState,new:SystemState) {
    old.phase==SYNCING & new.phase==WARMUP ? scheduler.on_syncing_complete() :
    old.phase in {SAFE_MODE,EMERGENCY} & new.phase==RECOVERY_READY ? scheduler.on_killswitch_reset()
  }
}

// ─────────────────────────────────────────────────────────────────────
// @DocMeta.P4_T_SEC6_AUDIT_LOGGER_COMPONENT: §6 Audit Logger Component
// ─────────────────────────────────────────────────────────────────────

// @Structure.P4_T_ADL_AUDIT_LOGGER: Audit logger with PG as SoT and Redis stream as best-effort sink
C AuditLogger(pg_pool:asyncpg.Pool,redis:Redis) {
// @Rule.P4_T_ADL_DUAL_WRITE: SSOT.AUDIT_STORAGE_STRATEGY;
// @Rule.P4_T_ADL_ATOMIC: SSOT.ATOMICITY_CONSTRAINTS;
// @Function.P4_T_ADL_LOG: Write audit log to PostgreSQL (must succeed) and Redis stream (best effort)
  f log(action:AuditAction,operator_id:s,details:d,ip_address:s?,success:b=T) -> AuditLogEntry {
    entry=AuditLogEntry(action,operator_id,details,ip_address,success) ->
    _write_postgres(entry) -> // Must succeed
    try{_write_redis_stream(entry)}catch{log.warning} -> // Best effort
    ret entry
  }
  f _write_postgres(entry:AuditLogEntry) { conn.execute(INSERT audit_log...) }
  f _write_redis_stream(entry:AuditLogEntry) {
// @Rule.P4_T_ADL_REDIS_TIMESTAMP: SSOT.TIMESTAMP_NS_FORMAT;
    stream_entry={entry_id:str,timestamp_ns:i,operator_id:s,action:s,details:json,ip_address:s,success:"1"|"0"} ->
    redis.xadd(AUDIT_STREAM_KEY,stream_entry,maxlen=AUDIT_STREAM_MAXLEN)
  }
}

// ─────────────────────────────────────────────────────────────────────
// @DocMeta.P4_T_SEC7_M_TLS_SECURITY_COMPONENTS: §7 mTLS Security Components
// ─────────────────────────────────────────────────────────────────────

// @Function.P4_T_MTLS_CREATE_SSL_CONTEXT: Create TLS server SSLContext with optional client verification (mTLS)
f create_ssl_context(config:MTLSConfig) -> ssl.SSLContext {
  ctx=ssl.SSLContext(PROTOCOL_TLS_SERVER) ->
  ctx.minimum_version=TLSv1_3 ->
  ctx.load_cert_chain(server_cert,server_key) ->
  config.verify_client ? (ctx.verify_mode=CERT_REQUIRED -> ctx.load_verify_locations(ca_cert)) ->
  ret ctx
}

// @Structure.P4_T_MTLS_CLIENT_CERT_MIDDLEWARE: Middleware enforcing client certificate CN allowlist and request.state propagation
C ClientCertMiddleware(app,allowed_cns:s[]?) {
// @Rule.P4_T_MTLS_CN_ALLOW: SSOT.MTLS_CONFIG;
// @Rule.P4_T_MTLS_STATE_CN: CONTRACT.REQUEST_STATE;
// @Function.P4_T_MTLS_DISPATCH: Enforce client cert presence and CN allowlist, set request.state.client_cn
  f dispatch(request:Request,call_next) {
    client_cert=request.scope.transport.peercert :
    !client_cert ? HTTPException(401,"Client certificate required") :
    cn=_extract_cn(client_cert) ->
    allowed_cns & cn!in allowed_cns ? HTTPException(403,"CN not allowed") :
    request.state.client_cn=cn -> call_next(request)
  }
  f _extract_cn(cert:d) -> s { for rdn in cert.subject: for attr in rdn: attr[0]=="commonName" ? ret attr[1] : ret "" }
}

// ─────────────────────────────────────────────────────────────────────
// @DocMeta.P4_T_SEC8_CONTROL_PLANE_INTEGRATION_P0_SEC9: §8 Control Plane Integration (P0 §9)
// ─────────────────────────────────────────────────────────────────────

// @Rule.P4_T_CPLI_APPLY: SSOT.CONTROL_PLANE_GATE;
// @Rule.P4_T_CPLI_COMPONENTS: SSOT.COMMAND_SIGNER, SSOT.CONTROL_PLANE_GATE, SSOT.TIMEOUT_HANDLER, @Structure.P4_T_ADL_AUDIT_LOGGER;
// @Structure.P4_T_CPLI_PARAMETER_CHANGE_HANDLER: Control-plane handler for parameter changes with RBAC gate and timeout
C ParameterChangeHandler(gate:ControlPlaneGate,config_store:ConfigStore) {
// @Rule.P4_T_CPLI_TIMEOUT: SSOT.CONTROL_PLANE_TIMEOUT;
// @Function.P4_T_CPLI_HANDLE_PARAMETER_CHANGE: Apply parameter change via control-plane gate with timeout
  @timeout_handler(CONTROL_PLANE_TIMEOUT_SEC)
  f handle(cmd:ParameterChangeCommand) -> ParameterChangeAck {
    @gate.require_permission(Permission.CHANGE_PARAMETERS)
    old_value=config_store.get(cmd.parameter_key) ->
    config_store.set(cmd.parameter_key,cmd.new_value,cmd.category) ->
    ret ParameterChangeAck(cmd.command_id,T,T)
  }
}

// ─────────────────────────────────────────────────────────────────────
// @DocMeta.P4_T_SEC9_API_GATEWAY_REDIS_RPC_FLOW: §9 API Gateway + Redis RPC Flow
// ─────────────────────────────────────────────────────────────────────

// @Rule.P4_T_AGWR_API_GATEWAY_FLOW: SSOT.API_GATEWAY_FLOW;
// @Rule.P4_T_AGWR_CMD_TOPIC: CONTRACT.SAFETY_TOPICS;

// @Structure.P4_T_AGWR_RPC_REDIS_RPC_HANDLER: Redis Pub/Sub RPC handler bridging HTTP requests and safety plane command/ack topics
C RedisRPCHandler(redis:Redis,cmd_topic:s,ack_topic:s) {
// @Rule.P4_T_AGWR_RPC_FLOW: @Function.P4_T_AGWR_RPC_CALL;
// @Rule.P4_T_AGWR_SUBSCRIBER_FLOW_TYPES: CONTRACT.SIGNED_COMMAND, CONTRACT.COMMAND_ACK;
  f start() { _running=T -> _subscriber_task=create_task(_ack_subscriber()) }
  f stop() { _running=F -> _subscriber_task?.cancel() -> for(f in _pending.values()){ f.cancel() } -> _pending.clear() }
// @Function.P4_T_AGWR_RPC_CALL: Publish signed command and wait for ack via pending-future map
  f call(request:SignedCommand) -> CommandAck {
    future=Future() -> _pending[request.command_id]=future ->
    redis.publish(cmd_topic,json(asdict(request))) ->
    try{ ret wait_for(future,timeout=30.0) }  // Use CONTROL_PLANE_TIMEOUT_SEC
    catch(TimeoutError){ ret CommandAck(command_id=request.command_id,status="FAIL",error_code="TIMEOUT") }
    finally{ _pending.pop(request.command_id) }
  }
// @Function.P4_T_AGWR_RPC_ACK_SUBSCRIBER: Subscribe safety:ack and resolve pending futures for RPC
  f _ack_subscriber() {
    pubsub=redis.pubsub() -> pubsub.subscribe(ack_topic) ->
    while(_running){
      msg=pubsub.get_message(timeout=1.0) ->
      msg & msg.type=="message" ? (
        data=json.loads(msg.data) ->
        future=_pending.get(data.command_id) ->
        future & !future.done() ? future.set_result(CommandAck(**data))
      )
    } -> pubsub.unsubscribe(ack_topic)
  }
}

// ─────────────────────────────────────────────────────────────────────
// @DocMeta.P4_T_SEC10_API_ENDPOINTS_ROUTING: §10 API Endpoints Routing
// ─────────────────────────────────────────────────────────────────────

// @Rule.P4_T_AER_API_RBAC: SSOT.RBAC_POLICY, CONTRACT.SAFETY_TOPICS, CONTRACT.MASTER_RELOAD_CHANNEL;

// @Structure.P4_T_AER_ADMIN_ROUTER: Admin API router for master-table reload and operational admin endpoints
C AdminRouter(prefix="/api/admin") {
// @Structure.P4_T_AER_MASTER_RELOAD_CHANNEL: Master-table reload pubsub channel constant ("master:reload")
  const MASTER_RELOAD_CHANNEL:s = "master:reload"
// @Ref.P4_T_AER_MASTER_RELOAD_MECHANISM: SSOT.MASTER_RELOAD_MECHANISM;
// @Function.P4_T_AER_ADMIN_RELOAD_MASTER_TABLE: Publish master-table reload event to MASTER_RELOAD_CHANNEL
  f reload_master_table(redis:Redis) -> d {
// @Rule.P4_T_AER_MASTER_RELOAD: CONTRACT.MASTER_RELOAD_CHANNEL;
    redis.publish(MASTER_RELOAD_CHANNEL,"reload") -> ret {status:"published",channel:MASTER_RELOAD_CHANNEL}
  }
}

// ─────────────────────────────────────────────────────────────────────
// @DocMeta.P4_T_SEC11_PROCESS_STARTUP_CONSTRAINTS: §11 Process Startup Constraints
// ─────────────────────────────────────────────────────────────────────
//
// @Rule.P4_T_PSC_SI_STARTUP_ORDER: SSOT.STARTUP_ORDER;
// @Rule.P4_T_PSC_SI_NAUTILUS_INDEPENDENT: SSOT.PROCESS_ISOLATION_RULES;
//
// @DocRef.P4_T_PSC_STARTUP_ORDER_REF: See @Rule.SI_STARTUP_ORDER in @DocMeta.SI_SEC20_SAFETY_MAIN_PY_INDEPENDENT_PROCESS (SHARED_INFRA).
// @DocRef.P4_T_PSC_SHUTDOWN_ORDER_REF: See @Rule.SI_SHUTDOWN_ORDER in @DocMeta.SI_SEC20_SAFETY_MAIN_PY_INDEPENDENT_PROCESS (SHARED_INFRA).
//
// @Ref.P4_T_PSC_ENTRYPOINT: SSOT.ENTRYPOINT_TABLE;

// ─────────────────────────────────────────────────────────────────────
// @DocMeta.P4_T_SEC12_ACCEPTANCE_TEST_RUNNER: §12 Acceptance Test Runner
// ─────────────────────────────────────────────────────────────────────

// @Loc.P4_T_ATR_TEST_E2E_LATENCY: myplugins/tests/acceptance/test_e2e_latency.py
// @Structure.P4_T_ATR_TEST_ACCEPTANCE_TEST_RUNNER: Acceptance test runner that executes tests and judges via log analysis
C AcceptanceTestRunner(config:AcceptanceTestConfig) {
// @Function.P4_T_ATR_RUN_AND_JUDGE: Run acceptance test command and judge pass/fail via log analysis
  f run_and_judge(test_command:s) -> b {
    result=subprocess.run(test_command) ->
    logs=_parse_json_logs(result.stdout) ->
    unexpected_errors=[log for log in logs if log.level in config.error_levels & !_is_expected_error(log)] ->
    ret len(unexpected_errors)==0
  }
  f _parse_json_logs(stdout:s) -> d[]
  f _is_expected_error(log:d) -> b { ret F } // Override in FaultInjectionTestRunner
// @Function.P4_T_ATR_CHECK_LATENCY_METRICS: Judge E2E latency p99 against acceptance threshold
  f check_latency_metrics(logs:d[]) -> b {
    latencies=[log.latency_e2e_us/1000 for log in logs if "latency_e2e_us" in log] ->
    !latencies ? ret T :
    p99=sorted(latencies)[int(len(latencies)*0.99)] ->
    ret p99<=config.e2e_latency_p99_ms
  }
}

// ─────────────────────────────────────────────────────────────────────
// @DocMeta.P4_T_SEC13_SUCCESS_CRITERIA: §13 Success Criteria
// ─────────────────────────────────────────────────────────────────────

// @Rule.P4_T_SUCCESS_CRITERIA: SSOT.ACCEPTANCE_CRITERIA;
// ─────────────────────────────────────────────────────────────────────
// @DocMeta.P4_T_SEC14_FILE_STRUCTURE: §14 File Structure
// ─────────────────────────────────────────────────────────────────────

// myplugins/operations/
// ├── manual/{parameters,strategies,modes,meta_strategy}.py  # MAN-2~5
// ├── handlers/{parameter,strategy,mode,meta}_handler.py     # Control Plane handlers
// ├── api/app.py + routes/{health,events,manual,admin}.py    # FastAPI
// ├── security/{mtls,middleware}.py                          # mTLS
// ├── audit/{models,schema.sql,logger}.py                    # Audit
// ├── reconciliation/{config,reconciler,scheduler}.py        # Reconciliation
// ├── dashboard/aggregator.py                                # Dashboard
// └── safe_mode.py                                           # Safe mode state machine
```
