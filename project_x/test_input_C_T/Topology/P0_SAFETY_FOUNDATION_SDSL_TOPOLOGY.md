```typescript
// ============================================================================
// @DocMeta.P0_T_SEC0_CORE_PRINCIPLES_ARCHITECTURE: §0 . CORE PRINCIPLES & ARCHITECTURE
// ============================================================================
// P0_SAFETY_FOUNDATION_SDSL_TOPOLOGY
// Topology / Flow SDSL - Safety Foundation System
// IMPORTANT: Must Obay Stable ID Rules: Stable_ID_Base_Rules.md
// @Rule.P0_T_CPA_PRIORITY_PRINCIPLE: SSOT.SafetyPriorityOrder;
// @Rule.P0_T_CPA_ARCHITECTURE_CHANGE: SSOT.CommunicationChannel;
// @Rule.P0_T_CPA_PLANE_SEPARATION: SSOT.PlaneSeparation;
// @Rule.P0_T_CPA_SAFETY_REDIS_AOF: SSOT.RedisDurability;
// @Rule.P0_T_CPA_ASYNC: SSOT.AsyncExecution;
// @Rule.P0_T_CPA_NOW_NS: SSOT.TimePrecision;

// ============================================================================
// @DocMeta.P0_T_SEC1_KILL_SWITCH_FLOW_IMPLEMENTATION: §1 . KILL SWITCH FLOW & IMPLEMENTATION
// ============================================================================

// @Rule.P0_T_KSFI_WATCHDOG_FALLBACK: SSOT.EscalationThresholds, @Structure.P0_T_SFTOPO_DEAD_MAN_SWITCH_CLASS, @Interface.P0_T_SFTOPO_KILL_SWITCH_CONTROLLER;
// @Rule.P0_T_KSFI_CONTROLLER_CONTRACT: CONTRACT.KillSwitchController;
// @Rule.P0_T_KSFI_SFTOPO_THREAD_SAFE: SSOT.ConcurrencyControl;
// @Rule.P0_T_KSFI_SFTOPO_COMMAND_TIMEOUT_SEC: SSOT.CommandTimeout;
// @Rule.P0_T_KSFI_SFTOPO_VALIDATION_SIG_RBAC: SSOT.SecurityValidation;

// @Interface.P0_T_SFTOPO_KILL_SWITCH_CONTROLLER: Kill switch controller interface (validate/execute/reset/state)
interface KillSwitchController {
// @Ref.P4_KSFI_ATOMIC_CONTROLLER: @Rule.P4_ATOMIC;
// @Ref.SI_KSFI_TIMEOUT_CONTROLLER: @Rule.SI_TIMEOUT;
// @Ref.P0_T_KSFI_ASYNC_CONTROLLER: @Rule.P0_T_ASYNC;
// @Ref.P0_T_KSFI_THREAD_SAFE_CONTROLLER: @Rule.P0_T_THREAD_SAFE;

// @Ref.SI_VALIDATION: @Rule.SI_VALIDATION, @Structure.P0_T_CPL_COMMAND_SIGNER_CLASS, @Function.P0_T_PERMISSION;
  async f validate_command(cmd: KillSwitchCommand) -> b

// @Rule.P0_T_KSFI_SFTOPO_KSC_EXECUTE_LOCK: SSOT.ConcurrencyControl;
// @Rule.P0_T_KSFI_SFTOPO_KSC_EXECUTE_IDEMPOTENT: SSOT.Idempotency;
// @Rule.P0_T_KSFI_SFTOPO_KSC_EXECUTE_ATOMIC: SSOT.Atomicity;
  async f execute(cmd: KillSwitchCommand) -> KillSwitchAck
  // Execute kill switch command
  // Thread-safe: MUST acquire lock before state modification
  // Idempotent: Check command_id in executed_commands set before execution
  // Atomic: Use transaction or rollback on partial failure

// @Rule.P0_T_KSFI_SFTOPO_KSC_GET_STATE_NONBLOCKING: SSOT.ConcurrencyControl;
  f get_state() -> KillSwitchState
  // Get current kill switch state (sync, non-blocking)
  // Thread-safe: Returns immutable snapshot of current state

// @Rule.P0_T_KSFI_SFTOPO_KSC_RESET_ADMIN_ONLY: SSOT.RBAC_MATRIX;
  async f reset(operator_id: s, reason: s) -> b
  // Reset kill switch (requires ADMIN role)
// @Ref.P4_T_KSFI_RBAC: SSOT.RBAC_MATRIX;
  // Thread-safe: MUST acquire lock before state modification
}

// @Rule.P0_T_KSFI_SAFETY_EXCHANGE_CLIENT_RULES: SSOT.ProcessIndependence, @Structure.P0_T_SFTOPO_SAFETY_EXCHANGE_CLIENT_CLASS;

// @Rule.P0_T_KSFI_ARCHITECTURE_INDEPENDENCE: SSOT.ProcessIndependence, @Structure.P0_T_SFTOPO_SAFETY_EXCHANGE_CLIENT_CLASS, @Structure.P0_T_SFTOPO_KILL_SEQUENCE_EXECUTOR_CLASS;

// @Structure.P0_T_KSFI_SFTOPO_SAFETY_EXCHANGE_CLIENT_CLASS: Safety Plane owned independent exchange client (ccxt wrapper)
C SafetyExchangeClient(api_key: s, secret: s, exchange_id: s = "binance") {
// @Ref.SI_INDEPENDENCE_CLIENT: @Rule.SI_INDEPENDENCE;
  _ccxt_client: ccxt.Exchange

  f __init__() {
    _ccxt_client = ccxt.create(exchange_id, {apiKey: api_key, secret: secret})
  }

  async f cancel_all_orders() -> d {
// @Ref.P0_T_DIRECT_CALL: @Rule.P0_T_DIRECT_CALL;
    await _ccxt_client.cancel_all_orders()
  }

  async f disconnect() -> v {
    await _ccxt_client.close()
  }

  async f block_new_orders() -> v {
// Local flag to reject new order attempts from this client
    _blocked = T
  }
}

// @SSOTRef.P0_T_KSFI_SFTOPO_REDIS_KEYS_AUTHORITY: SSOT.RedisKeyCatalog, @Structure.SI_RKC_REDIS_KEY_CATALOG_CLASS;
// @Loc.P0_T_KSFI_SFTOPO_LOC_SAFETY_PID_KEYS: Uses safety:pid:* for PID lookup in Physical Sever path
// @Loc.P0_T_KSFI_SFTOPO_LOC_SAFETY_AUDIT_STREAM: Writes audit events to safety:audit:log stream during kill operations
// @Loc.P0_T_KSFI_SFTOPO_LOC_SAFETY_KILLSWITCH_STATE: Writes killswitch state to safety:killswitch:state during EMERGENCY transition
// @Structure.P0_T_KSFI_SFTOPO_KILL_SEQUENCE_EXECUTOR_CLASS: Kill sequence executor (MassCancel -> PhysicalSever -> Emergency -> Notify)
C KillSequenceExecutor(safety_exchange: SafetyExchangeClient, safety_redis: RedisClient, notifier, config: KillSequenceConfig) {
// @Ref.P0_T_KSFI_DEPENDENCY_KSE: @Rule.P0_T_DEPENDENCY;
// @Ref.SI_KSFI_ORDER_KSE: @Rule.SI_ORDER;
// @Ref.P0_T_KSFI_PRIORITY_KSE: @Rule.P0_T_PRIORITY;
// @Ref.P0_T_KSFI_ASYNC_KSE: All methods are async (@Rule.P0_T_ASYNC);

  async f execute(level: KillLevel, reason: s) -> d {
    await _mass_cancel() timeout(1500ms) | {status:"timeout", proceed:T} ->
    await _physical_sever() ->
    await _transition_to_emergency() ->
    await _notify_with_retry(level, reason)
  }

  async f _mass_cancel() -> d { await safety_exchange.cancel_all_orders() }

  async f _physical_sever() -> d {
// @Ref.SI_KSFI_CRITICAL_SERVER: @Rule.SI_CRITICAL;
    results = {nautilus_kill: None, safety_disconnect: None}
    pid_key = "safety:pid:nautilus"
    pid_str = await safety_redis.get(pid_key)

// @Ref.P0_T_KSFI_PID_NOT_REGISTERED: @Rule.P0_T_PID_NOT_REGISTERED;
    !pid_str? {
      log.warning("Nautilus PID not registered - cannot execute physical sever", key=pid_key)
      results["nautilus_kill"] = {status: "skipped", reason: "pid_not_registered"}
    } : {
      pid = int(pid_str)
// @Ref.P0_T_KSFI_AUDIT: @Rule.P0_T_AUDIT;
      await safety_redis.xadd("safety:audit:log", {
        action: "PHYSICAL_SEVER_NAUTILUS",
        target_pid: pid,
        reason: "KillSequence Physical Sever step",
        timestamp_ns: int(time.time() * 1e9)
      })

// @Rule.P2_KSFI_PID_NS: SSOT.ProcessManagement;
      try {
        os.path.exists(f"/proc/{pid}")? {
          os.kill(pid, signal.SIGKILL)
          log.critical("Nautilus killed by SIGKILL", pid=pid)
          results["nautilus_kill"] = {status: "killed", pid: pid}
        } : {
          cmd = env.get("KILL_CONTAINER_CMD_NAUTILUS")
          cmd? {
            subprocess.run(cmd.split(), timeout=5)
            results["nautilus_kill"] = {status: "container_stopped"}
          } : {
            log.error("KILL_CONTAINER_CMD_NAUTILUS not set")
            results["nautilus_kill"] = {status: "container_cmd_not_configured"}
          }
        }
      } catch ProcessLookupError {
        log.warning("Nautilus process already dead")
        results["nautilus_kill"] = {status: "already_dead"}
      } catch PermissionError as e {
        log.error("Permission denied to kill Nautilus", error=str(e))
        results["nautilus_kill"] = {status: "failed", reason: "permission_denied"}
      } catch Exception as e {
        log.error("Failed to kill Nautilus", error=str(e))
        results["nautilus_kill"] = {status: "failed", reason: str(e)}
      }
    }

// @Ref.P0_T_KSFI_SAFETY_DISCONNECT: @Rule.P0_T_SAFETY_DISCONNECT;
    try {
      await safety_exchange.disconnect()
      await safety_exchange.block_new_orders()
      results["safety_disconnect"] = {status: "success"}
    } catch e {
      log.warning("Safety exchange disconnect failed", error=str(e))
      results["safety_disconnect"] = {status: "failed", reason: str(e)}
    }

    ret {status: "success", details: results}
  }

  async f _transition_to_emergency() -> d {
// @Ref.P3_KSFI_STATE: @Rule.P3_STATE;
    await safety_redis.hset("safety:killswitch:state", "mode", "EMERGENCY")
  }

  async f _notify_with_retry(level: KillLevel, reason: s) -> d {
// @Ref.P0_T_KSFI_NOTIFICATION_PAYLOAD: @Rule.P0_T_NOTIFICATION_PAYLOAD;
    retry(3, 1000ms) {
      await notifier.send_critical_alert(
        title=f"Kill Switch Activated: {level.value}",  // e.g., "Kill Switch Activated: hard_stop"
        message=reason                                   // Original trigger reason
      )
    }
  }
}

// @Rule.P0_T_KSFI_PID_REGISTRATION: SSOT.ProcessManagement;
// @Function.P0_T_KSFI_SFTOPO_REGISTER_COMPONENT_PID: Register component PID into Safety Redis (safety:pid:{component})
f register_component_pid(safety_redis, component: s) -> v {
  pid = os.getpid()
  safety_redis.set("safety:pid:{component}", str(pid))
}

// @Function.P0_T_KSFI_SFTOPO_UNREGISTER_COMPONENT_PID: Unregister component PID from Safety Redis (safety:pid:{component})
f unregister_component_pid(safety_redis, component: s) -> v {
  safety_redis.delete("safety:pid:{component}")
}

// @Rule.P0_T_KSFI_ENV_CONTAINER_CMD: SSOT.ContainerManagement;

// @Rule.P0_T_KSFI_SFTOPO_DMS_GRACEFUL_STOP: SSOT.ProcessManagement;
// @Rule.P0_T_KSFI_SFTOPO_DMS_LOOP_STOP_FLAG: SSOT.ProcessManagement;
// @Rule.P0_T_KSFI_SFTOPO_DMS_KEY_MISSING_AS_ZERO: SSOT.EscalationLogic;
// @Rule.P0_T_KSFI_SFTOPO_DMS_RECOVERY_RESETS_ESCALATION: SSOT.EscalationLogic;
// @Rule.P0_T_KSFI_SFTOPO_DMS_INTERVAL_MS_500: SSOT.HeartbeatInterval;
// @Rule.P0_T_KSFI_SFTOPO_DMS_SAFETY_REDIS_FAILSAFE: @OD.P0_T_17;
// @Rule.P0_T_KSFI_SFTOPO_DMS_CONTAINER_CMD_REQUIRED: SSOT.ContainerManagement;
// @Rule.P0_T_KSFI_SFTOPO_DMS_CONTAINER_CMD_TIMEOUT_SEC_5: SSOT.ContainerManagement;
// @Rule.P0_T_KSFI_SFTOPO_DMS_FAILSAFE_CONTINUE: SSOT.ProcessManagement;
// @Structure.P0_T_KSFI_SFTOPO_DEAD_MAN_SWITCH_CLASS: DeadManSwitch watchdog (L0/L1/L2 escalation) + failsafe loops
C DeadManSwitch(config: DeadManSwitchConfig, kill_executor: KillSequenceExecutor, escalation_config: WatchdogEscalationConfig = WatchdogEscalationConfig()) {
// @Ref.SI_T_INDEPENDENCE: Runs in Safety Plane, isolated from Orchestrator (@Rule.SI_T_INDEPENDENCE);
// @Ref.P0_T_ESCALATION: @Rule.P0_T_ESCALATION;
// @Ref.P0_T_CONFIG_DERIVED: @Rule.P0_T_CONFIG_DERIVED;
  _escalation_thresholds_ms: [i] = [
    escalation_config.l0_after_seconds * 1000,
    escalation_config.l1_after_seconds * 1000,
    escalation_config.l2_after_seconds * 1000
  ]
  const KILLABLE_COMPONENTS: ["orchestrator", "nautilus"]

  _safety_redis: redis.Redis? = None
  _running: b = F
// @Ref.
  _current_escalation: i = -1

  async f start() -> v {
    _safety_redis = redis.Redis(host=config.safety_redis_host, port=config.safety_redis_port)
    _running = T
    asyncio.create_task(_watchdog_loop())
    config.l2_failsafe_enabled? asyncio.create_task(_l2_failsafe_loop())
  }

  async f stop() -> v {
// @Ref.P0_T_GRACEFUL: @Rule.P0_T_GRACEFUL;
    _running = F
    _safety_redis? await _safety_redis.close()
  }

  async f _watchdog_loop() -> v {
// @Ref.P3
// @Ref.P0_T_STOP: @Rule.P0_T_STOP;
    while _running {
      try {
        last_hb = await safety_redis.get(heartbeat_key)
        now_ns = time.time() * 1e9

// @Ref.P0_T_KEY_MISSING: @Rule.P0_T_KEY_MISSING;
        last_ts = last_hb? int(last_hb) : 0
        age_ms = (now_ns - last_ts) / 1e6

        for (lvl, thresh) in enumerate(_escalation_thresholds_ms) {
          age_ms > thresh & lvl > _current_escalation? {
            await _trigger_kill(lvl)
            _current_escalation = lvl
            break
          }
        }

// @Ref.P0_T_RECOVERY: @Rule.P0_T_RECOVERY;
        age_ms < _escalation_thresholds_ms[0]? _current_escalation = -1
// @Ref.P0_T_INTERVAL: @Rule.P0_T_INTERVAL;
        await asyncio.sleep(config.heartbeat_interval_ms / 1000)
      } catch redis.RedisError {
// @Ref.P0_T_REDIS_FAIL: @Rule.P0_T_REDIS_FAIL, @OD.P0_T_17;
        await _enter_maintenance_mode()
        await asyncio.sleep(1.0)
      }
    }
  }

// @Rule.P0_T_SFTOPO_DMS_TRIGGER_KILL_ASYNC: SSOT.AsyncExecution;
  async f _trigger_kill(escalation_level: i) -> v {
    levels = [SOFT_STOP, HARD_STOP, EMERGENCY]
    level_names = ["L0 (SOFT_STOP)", "L1 (HARD_STOP)", "L2 (EMERGENCY)"]
    await kill_executor.execute(levels[escalation_level], f"DeadManSwitch timeout - {level_names[escalation_level]}")
    safety_redis.set(watchdog_state_key, "TRIGGERED")
  }

  f _enter_maintenance_mode() -> v {
// @Ref.P0_T_17: @OD.P0_T_17;
    // Block all trading, require manual intervention
    log.critical("Safety Redis unavailable - entering SAFE_MODE (maintenance)")
    kill_executor.execute(SOFT_STOP, "Safety Redis unavailable - SAFE_MODE (maintenance)")
  }

  f _physical_kill_all_components() -> v {
// @Ref.SI_CRITICAL: Kill ALL components on L2 (@Rule.SI_CRITICAL);
// @Ref.P0_T_L2_EXCLUDE: @Rule.P0_T_L2_EXCLUDE;
    killed_pids = []
    failed_components = []
    for comp in KILLABLE_COMPONENTS {
      pid = safety_redis.get("safety:pid:{comp}")
      !pid? -> { log.warn("PID not registered", comp); failed_components.append(comp); continue }
// @Ref.P0_T_AUDIT: Log BEFORE kill execution (@Rule.P0_T_AUDIT);
      _audit_kill_action(pid, f"DeadManSwitch timeout - L2 EMERGENCY ({comp})") ->
      _is_same_pid_namespace()? { _kill_by_signal(pid); killed_pids.append((comp, pid)) } :
                                { _kill_container(comp); killed_pids.append((comp, "container")) }
    }
    log.critical("Physical kill completed", killed=killed_pids, failed=failed_components)
  }

  f _is_same_pid_namespace() -> b {
// @Ref.P0_T_HOST_PID: @Rule.P0_T_HOST_PID;
// @Ref.P0_T_DEPLOYMENT_REQUIREMENT: @Rule.P0_T_DEPLOYMENT_REQUIREMENT;
    os.path.exists("/proc/{os.getpid()}")
  }

  f _kill_by_signal(pid: i) -> v {
    os.kill(pid, signal.SIGKILL)
  }

  f _kill_container(comp: s) -> v {
// @Ref.P0_T_ENV: @Rule.P0_T_ENV;
// @Ref.P0_T_CONTAINER_STOP_SPEC: @Rule.P0_T_CONTAINER_STOP_SPEC;

// @Ref.P0_T_FAILSAFE: @Rule.P0_T_FAILSAFE;
    env_key = f"KILL_CONTAINER_CMD_{comp.upper()}"
    cmd = env.get(env_key)
    cmd? {
      result = subprocess.run(cmd.split(), capture_output=T, timeout=5)
      log.critical("Container stop executed", component=comp, cmd=cmd, returncode=result.returncode)
    } : {
      log.critical("Container stop command not configured - FAILSAFE INCOMPLETE",
                   env_key=env_key, component=comp,
                   msg="Set env var for containerized deployments")
    }
  }

  f _audit_kill_action(pid: i, reason: s) -> v {
    safety_redis.xadd("safety:audit:log", {action:"PHYSICAL_KILL", pid, reason, ts:now_ns})
  }

  f _l2_failsafe_loop() -> v {
// @Ref.P0_T_L2_BACKUP_MONITORING: @Rule.P0_T_L2_BACKUP_MONITORING;
// @Ref.P0_T_ONCE: @Rule.P0_T_ONCE;
    l2_triggered: b = F

    loop {
      try {
        l2_hb = safety_redis.get(l2_heartbeat_key)
        now_ns = time.time() * 1e9

        l2_hb == None & !l2_triggered? {
          // L2 Heartbeat key missing -> L2 likely dead
          log.critical("L2 failsafe: No heartbeat key found - market_data_adapter likely dead")
          kill_executor.execute(HARD_STOP, "L2 failsafe: market_data_adapter heartbeat missing")
          l2_triggered = T
        } : l2_hb? {
          last_ts = int(l2_hb)
          age_ms = (now_ns - last_ts) / 1e6

          age_ms > config.l2_heartbeat_timeout_ms & !l2_triggered? {
            log.critical("L2 failsafe: Heartbeat timeout", age_ms=age_ms, timeout_ms=config.l2_heartbeat_timeout_ms)
            kill_executor.execute(HARD_STOP, f"L2 failsafe: market_data_adapter heartbeat timeout ({age_ms:.0f}ms)")
            l2_triggered = T
          } : age_ms < config.l2_heartbeat_timeout_ms? {
// @Ref.P0_T_RECOVERY: Reset flag on recovery (@Rule.P0_T_RECOVERY);
            l2_triggered = F
          }
        }

        sleep(1.0)  // 1s monitoring interval
      } catch redis.RedisError {
        log.error("L2 failsafe: Safety Redis error")
        sleep(1.0)
      }
    }
  }
}

// @Structure.P0_T_SFTOPO_SAFETY_HEARTBEAT_EMITTER_CLASS: Emit orchestrator heartbeat into Safety Redis with TTL
C SafetyHeartbeatEmitter(host: s = "localhost", port: i = 6380, heartbeat_key: s = "safety:heartbeat:orchestrator", interval_ms: i = 500) {
// @SSOTRef.P0_T_HEARTBEAT_TTL: SSOT.SHARED_CONSTANTS;
  const HEARTBEAT_TTL_SECONDS: i = 6
  _redis: redis.Redis? = None
  _running: b = F

  async f start() -> v {
    _redis = redis.Redis(host=host, port=port, decode_responses=T)
    _running = T
    asyncio.create_task(_emit_loop())
  }

  async f _emit_loop() -> v {
    while _running {
      try {
        now_ns = int(time.time() * 1_000_000_000)
        await _redis.setex(heartbeat_key, HEARTBEAT_TTL_SECONDS, str(now_ns))
      } catch redis.RedisError as e {
        log.error("Failed to emit heartbeat", error=str(e))
      }
      await asyncio.sleep(interval_ms / 1000)
    }
  }

  async f stop() -> v {
    _running = F
    _redis? await _redis.close()
  }
}

// ============================================================================
// @DocMeta.P0_T_SEC1_1_DECIDED_ITEMS_OD: §1.1 DECIDED ITEMS (OD-*)
// ============================================================================

// @OD.P0_T_KS_1: Watchdog Reset -> Manual ADMIN Reset ONLY | No auto-recovery (safety-first principle) | reset() requires ADMIN role | Signed command required
// @OD.P0_T_KS_2: L2 Kill Switch Exclusions -> Observation continues | CONTINUE: Logging, Metrics, Health endpoints, L7 Observation | STOP: Trading, Feature, Model, Order execution
// @OD.P0_T_RBAC_1: Auth Method -> API Key + HMAC | Command signature (§14) unified | Future: JWT/IdP extension possible
// @OD.P0_T_SF_1: Safety Redis Down -> Immediate Maintenance Mode (Fail-Stop) | @OD.P0_T_17: Decision: No auto-failover | Safety Redis unavailable -> immediate maintenance mode | Block new orders, require manual intervention | Principle: Safety Redis "breaks -> stop" is correct
// @OD.P0_T_SF_2: Mass Cancel Retry -> No Retry | 2s timeout -> proceed immediately to Physical Sever | Safety-first: eliminate retry delay risk

// ============================================================================
// @DocMeta.P0_T_SEC2_RBAC_FLOW_IMPLEMENTATION: §2 . RBAC FLOW & IMPLEMENTATION
// ============================================================================

// @Function.P0_T_PERMISSION: Permission checking (async for store access)
async f has_permission(operator_id: s, permission: Permission) -> b {
  operator = await store.get_operator(operator_id)
  !operator? -> ret F
  ret permission in ROLE_PERMISSIONS[operator.role]
}

// @Decorator.P0_T_RBAC: Permission enforcement decorator
decorator require_permission(permission: Permission) {
// @Ref.P0_T_GATE_VALIDATION: @Rule.P0_T_GATE_VALIDATION;
// @Ref.P0_T_GATE_AUDIT: @Rule.P0_T_GATE_AUDIT;
  @wraps(func)
  async f wrapper(command, ..) {
// @Ref.P0_T_ASYNC: has_permission is async, must await (@Rule.P0_T_ASYNC);
    !await has_permission(command.operator_id, permission)?
      -> raise PermissionDeniedError(f"Missing {permission}")
    ret await func(command, ..)
  }
}

// @Flow.P0_T_BOOTSTRAP: Admin initialization on startup
async f bootstrap() -> v:
  await redis.connect()
  -> await ensure_bootstrap_admin()

// @Ref.P0_T_ASYNC: Store methods are async (@Rule.P0_T_ASYNC);
async f ensure_bootstrap_admin() -> b:
  existing_admins = await store.list_operators_by_role(ADMIN)
  existing_admins? -> ret F  // Admin exists, skip

  admin_id = env.get("INITIAL_ADMIN_ID")
  admin_key = env.get("INITIAL_ADMIN_KEY")

  !admin_id & !admin_key? -> warn("No bootstrap admin env vars") -> ret F
  admin_id ^ admin_key? -> raise ValueError("Both ID and KEY required")

  await store.register_operator(
    Operator(operator_id=admin_id, role=ADMIN, created_at=now()),
    api_key=admin_key
  )
  ret T

// ============================================================================
// @DocMeta.P0_T_SEC3_CHECKPOINT_FLOW_IMPLEMENTATION: §3 . CHECKPOINT FLOW & IMPLEMENTATION
// ============================================================================

// @Interface.P0_T_CKP_STATEFUL_STRATEGY_IF: Stateful strategy interface for checkpoint restore
interface StatefulStrategy {
  f get_state() -> d[s, any]  // Pickle-able dict
  f set_state(state: d[s, any]) -> v
  f is_warmed_up() -> b
  strategy_id: s
}

// @Function.P0_T_CKP_SERIALIZE_STRATEGY_STATE: Serialize strategy state to base64 ASCII string for checkpoint storage
f serialize_strategy_state(state: d) -> s {
// @Rule.P0_T_ENCODING: SSOT.SerializationFormat;
  base64.b64encode(pickle.dumps(state)).decode("ascii")
}

// @Function.P0_T_CKP_DESERIALIZE_STRATEGY_STATE: Deserialize base64 ASCII string back to strategy state dict
f deserialize_strategy_state(encoded: s) -> d {
// @Rule.P0_T_DECODING: SSOT.SerializationFormat;
  pickle.loads(base64.b64decode(encoded.encode("ascii")))
}

// @Structure.P0_T_CKP_STRATEGY_PIPELINE_CLASS: Strategy pipeline with checkpoint restore/collect
C StrategyPipeline {
  _strategies: d[s, StatefulStrategy]

  f __init__(strategies: [StatefulStrategy]) {
    _strategies = { s.strategy_id: s for s in strategies }
  }

// @Rule.P0_T_CKP_RESTORE_COLD_START: SSOT.StateManagement;
// @Rule.P0_T_EXCEPTION_HANDLING: SSOT.ErrorHandling;
  async f restore_from_checkpoint(checkpoint: SystemCheckpoint) -> v {
// @Rule.P0_T_EMPTY_CHECK: SSOT.ErrorHandling;
    !checkpoint.strategy_states? {
      log.warning(
        "checkpoint_no_strategy_states",
        msg="No strategy states in checkpoint, strategies will cold start"
      )
      ret
    }

    restored_count = 0
    for (strategy_id, encoded) in checkpoint.strategy_states.items() {
      strategy = _strategies.get(strategy_id)

// @Rule.P0_T_UNKNOWN_STRATEGY: SSOT.ErrorHandling;
      !strategy? {
        log.warning(
          "checkpoint_unknown_strategy",
          strategy_id=strategy_id,
          msg="Strategy in checkpoint not found in pipeline"
        )
        continue
      }

// @Rule.P0_T_TRY_CATCH: SSOT.ErrorHandling;
      try {
        state = deserialize_strategy_state(encoded)
        strategy.set_state(state)
        restored_count += 1
        log.info(
          "strategy_state_restored",
          strategy_id=strategy_id,
          is_warmed_up=strategy.is_warmed_up()
        )
      } catch (e: Exception) {
// @Rule.P0_T_ERROR_RECOVERY: SSOT.ErrorHandling;
        log.error(
          "strategy_state_restore_failed",
          strategy_id=strategy_id,
          error=str(e)
        )
      }
    }

// @Rule.P0_T_SUMMARY_LOG: SSOT.Observability;
    log.info(
      "strategy_pipeline_restored",
      total_strategies=len(_strategies),
      restored_count=restored_count
    )
  }

  f collect_states_for_checkpoint() -> d[s, s] {
    { sid: serialize_strategy_state(s.get_state()) for sid, s in _strategies.items() }
  }
}

// @Rule.P0_T_CKP_WARMUP_SUMMARY_LOG: SSOT.Observability;
// @Rule.P0_T_CKP_WARMUP_OBSERVABILITY: SSOT.Observability;
// @Function.P0_T_CKP_CHECK_STRATEGY_WARMUP: Check strategy warmup and return pending strategy_ids
f check_strategy_warmup(pipeline: StrategyPipeline) -> [s] {
  not_warmed_up = []
  for (sid, strategy) in pipeline._strategies.items() {
    !strategy.is_warmed_up()? {
      not_warmed_up.append(sid)
// @Rule.P0_T_WARNING_LOG: SSOT.Observability;
      log.warning(
        "strategy_not_warmed_up",
        strategy_id=sid,
        msg="Strategy needs warmup data before generating signals"
      )
    }
  }

// @Ref.P0_T_CKP_REF_SUMMARY_LOG: @Rule.P0_T_CKP_WARMUP_SUMMARY_LOG;
  not_warmed_up.length > 0? {
    log.warning(
      "strategies_pending_warmup",
      count=not_warmed_up.length,
      strategy_ids=not_warmed_up,
      msg="System should remain in GUARDED mode until all strategies are warmed up"
    )
  }

  ret not_warmed_up
}

// ============================================================================
// @DocMeta.P0_T_SEC4_HEARTBEAT_FLOW_IMPLEMENTATION: §4 . HEARTBEAT FLOW & IMPLEMENTATION
// ============================================================================

// @Note.P0_T_HBFI_REF: SafetyHeartbeatEmitter defined in §1 (L492-519)
// @Structure.P0_T_HBFI_HEARTBEAT_READER_CLASS: Read heartbeat ts/ttl from Safety Redis
C HeartbeatReader {
  redis: RedisClient

  f get(component_id: s) -> i?
    -> redis.GET("safety:heartbeat:{component_id}")

  f ttl(component_id: s) -> i
    -> redis.TTL("safety:heartbeat:{component_id}")
}

// @Structure.P0_T_HBFI_TIMEOUT_DETECTOR_CLASS: Timeout detector based on heartbeat reader and threshold
C TimeoutDetector {
  reader: HeartbeatReader
  threshold: f = 5.0

  f check(component_id: s) -> HeartbeatStatus
    -> ts = reader.get(component_id)
    -> ts ? (now() - ts > 5e9 ? CRITICAL : HEALTHY) : CRITICAL

  f scan_all(component_ids: [s]) -> d[s, HeartbeatStatus]
}

// @Rule.P0_T_HBFI_DEADMAN_SWITCH: @Structure.P0_T_SFTOPO_DEAD_MAN_SWITCH_CLASS;
// @Interface.P0_T_HBFI_WATCHDOG: Abstract watchdog for kill switch triggering
interface Watchdog {
  f trigger(component_id: s, reason: s) -> v
// @Rule.P0_T_HBFI_ESCALATION: @Structure.P0_T_SFTOPO_KILL_SEQUENCE_EXECUTOR_CLASS;
}

// @Structure.P0_T_HBFI_WATCHDOG_BRIDGE_CLASS: Bridge timeout detector to watchdog trigger
C WatchdogBridge {
  detector: TimeoutDetector
  watchdog: Watchdog
// @Rule.P3_T_STATE: SSOT.StateManagement;
  _miss_counts: d[s, i] = {}

  f monitor(component_id: s) -> v {
    status = detector.check(component_id)

// @Rule.P0_T_HBFI_MISS_COUNT: SSOT.Observability;
    status == CRITICAL? {
      _miss_counts[component_id] = _miss_counts.get(component_id, 0) + 1
      miss_count = _miss_counts[component_id]

// @Rule.P0_T_HBFI_THRESHOLD: SSOT.WatchdogTriggerConfig;

      miss_count >= config.heartbeat_miss_threshold? {
        watchdog.trigger(component_id, f"heartbeat_timeout (miss_count={miss_count})")
        log.warning("Watchdog triggered", component_id, miss_count)
      } : {
        log.warning("Heartbeat miss detected", component_id, miss_count, threshold=config.heartbeat_miss_threshold)
      }
    } : {
// @Rule.P0_T_HBFI_RECOVERY: SSOT.StateManagement;
      _miss_counts[component_id] = 0
    }
  }
}

// ============================================================================
// @DocMeta.P0_T_SEC5_WAL_FLOW_IMPLEMENTATION: §5 . WAL FLOW & IMPLEMENTATION
// ============================================================================

// @Rule.P0_T_WAL_ARCHITECTURE: SSOT.DurabilityStrategy;

// @Rule.P0_T_WAL_SSOT_HIERARCHY: SSOT.Governance;

// @Function.P0_T_WAL_SERIALIZE_ENTRY: Serialize WALEntry to msgpack bytes payload
f serialize_wal_entry(entry: WALEntry) -> bytes {
// @Rule.P0_T_WAL_FORMAT: SSOT.SerializationFormat;
  data = {
    "entry_id": str(entry.entry_id),       // UUID -> string
    "entry_type": entry.entry_type.value,  // Enum -> string value
    "ts": entry.ts,
    "component_id": entry.component_id,
    "payload": entry.payload,              // Already MsgPack bytes
    "checksum": entry.checksum,
    "sequence_id": entry.sequence_id
  }
  msgpack.packb(data, use_bin_type=T)
}

// @Function.P0_T_WAL_DESERIALIZE_ENTRY: Deserialize msgpack bytes back to WALEntry
f deserialize_wal_entry(data: bytes) -> WALEntry {
  parsed = msgpack.unpackb(data, raw=F)
  WALEntry(
    entry_id=UUID(parsed["entry_id"]),
    entry_type=WALEntryType(parsed["entry_type"]),
    ts=parsed["ts"],
    component_id=parsed["component_id"],
    payload=parsed["payload"],
    checksum=parsed["checksum"],
    sequence_id=parsed.get("sequence_id")
  )
}

// @Function.P0_T_WAL_RESOLVE_PATH: Resolve WAL path using component_id and PID to prevent conflicts
f resolve_wal_path(base_dir: Path, component_id: s, base_name: s = "execution") -> Path {
// @Rule.P0_T_MULTIPROCESS: SSOT.ProcessManagement;
  base_dir / f"{base_name}_{component_id}_{os.getpid()}.wal"
}

// @Structure.P0_T_WAL_NON_BLOCKING_WAL_CLASS: Non-blocking WAL writer with mmap + writer thread
C NonBlockingWAL {
// @Rule.P0_T_WAL_CRITICAL_FIX: SSOT.ProcessManagement;
// system_main.py and nautilus_main.py writing to same WAL causes file lock conflicts
// Solution: Include component_id and PID in WAL filename
  wal_path: Path
  component_id: s
  max_size_mb: i = 100
  sync_interval_ms: i = 100
  _queue: Queue[WALEntry]
// @Rule.P3_INIT: SSOT.StateManagement;
  _mmap: mmap? = None
  _writer_thread: Thread? = None
  _shutdown: Event

  f __init__(wal_path: Path, component_id: s, max_size_mb: i = 100, sync_interval_ms: i = 100) {
// @Rule.SI_CRITICAL: SSOT.ProcessManagement;
    self.wal_path = resolve_wal_path(wal_path.parent, component_id, wal_path.stem)
    self.component_id = component_id
    self.max_size_mb = max_size_mb
    self.sync_interval_ms = sync_interval_ms
    self._queue = Queue()
    self._shutdown = Event()
  }

  f start() -> v {
    _init_mmap()
    _writer_thread = Thread(target=_writer_loop, daemon=T, name=f"wal-writer-{component_id}")
    _writer_thread.start()
  }

  f _init_mmap() -> v {
// @Rule.P0_T_WAL_MMAP: SSOT.DurabilityStrategy;

    fd = open(wal_path, "r+b") | open(wal_path, "w+b")
    fd.truncate(max_size_mb * 1024 * 1024)
    _mmap = mmap.mmap(fd.fileno(), 0, access=mmap.ACCESS_WRITE)
  }

  f write(entry: WALEntry) -> v {
// @Rule.P3_DESIGN: SSOT.PerformanceOptimization;
    _queue.put_nowait(entry)
  }

  f _writer_loop() -> v {
// @Rule.P0_T_WAL_FATAL_ERRORS: SSOT.ErrorHandling;
    FATAL_ERRORS = (IOError, OSError, PermissionError, FileNotFoundError)
    loop {
      try {
        entry = _queue.get(timeout=sync_interval_ms/1000)
        try { _write_entry_to_mmap(entry) }
        catch e in FATAL_ERRORS -> os._exit(1) // hard crash
      } catch Empty {
// @Rule.P0_T_WAL_NON_BLOCKING: SSOT.PerformanceOptimization;
        pass
      }
      _shutdown.is_set()? -> break
    }
  }

  f stop() -> v {
    _shutdown.set() -> _writer_thread.join(5.0)
  }
}

// @Structure.P0_T_WAL_ASYNC_REDIS_BACKUP_THREAD_CLASS: Background WAL-to-Redis backup thread
C AsyncRedisBackupThread {
// @Rule.P3_DESIGN: Background sync from local WAL to Redis;
  wal_reader: WALReader
  redis: RedisClient
  sync_interval_ms: i = 1000
  _backup_thread: Thread
  _shutdown: Event
  _last_synced_seq: i = 0

  f start() -> v {
    _backup_thread = Thread(_backup_loop) -> _backup_thread.start()
  }

  f _backup_loop() -> v {
    loop {
      entries = wal_reader.read_since(_last_synced_seq)
      for entry in entries {
        redis.xadd("wal:backup:{component_id}", entry.to_dict())
        _last_synced_seq = entry.sequence_id
      }
      _shutdown.is_set()? -> break
      sleep(sync_interval_ms / 1000)
    }
  }

  f stop() -> v {
    _shutdown.set() -> _backup_thread.join(5.0)
  }

  f get_sync_lag() -> i {
    wal_reader.get_latest_seq() - _last_synced_seq
  }
}
// @Function.P0_T_WAL_GET_FSYNC_POLICY_FOR_ENTRY: Determine fsync policy per entry type and durability config
f get_fsync_policy_for_entry(entry_type: WALEntryType, config: WALDurabilityConfig) -> FsyncPolicy {
// @Rule.P0_T_WAL_SAFETY_FIRST: SSOT.DurabilityStrategy;
  entry_type in [STATE_CHANGE, POSITION_UPDATE, ORDER_EVENT, CHECKPOINT]?
    -> ret config.execution_fsync_policy
  // Feature/Metric events can use BATCH for performance
  ret config.feature_fsync_policy
}

// @Function.P0_T_WAL_COMPUTE_CHECKSUM: Compute checksum string for WALEntry payload
f compute_checksum(entry: WALEntry) -> s {
  data = entry.entry_type.value.encode() + entry.ts.to_bytes(8, 'big') + entry.component_id.encode() + entry.payload
  f"{zlib.crc32(data):08x}"
}

// @Function.P0_T_WAL_VERIFY_CHECKSUM: Verify checksum for WALEntry against computed value
f verify_checksum(entry: WALEntry) -> b {
  compute_checksum(entry) == entry.checksum
}

// @Structure.P0_T_WAL_ROTATION_MANAGER_CLASS: WAL rotation and retention cleanup manager
C WALRotationManager {
  wal_dir: Path
  config: WALDurabilityConfig

  f rotate(current_file: Path) -> Path {
    rotated = current_file.with_suffix(f".{int(time.time())}.wal")
    current_file.rename(rotated) -> _cleanup_old_files() -> current_file
  }

  f _cleanup_old_files() -> v {
    sorted_files = sorted(wal_dir.glob("*.*.wal"), key=lambda p: p.stat().st_mtime, reverse=T)
    for f in sorted_files[config.retain_rotated_files:] { f.unlink() }
  }
}

// @Rule.P0_T_WAL_READ: SSOT.DurabilityStrategy;
// @Function.P0_T_WAL_READ_RAW_ENTRIES: Read raw length-prefixed WAL entry bytes from mmap file
f read_raw_entries(wal_path: Path) -> Generator[bytes] {
// @Rule.P0_T_ITERATOR: SSOT.PerformanceOptimization;
// Implementation reads mmap'd file, yields length-prefixed entries
  with open(wal_path, "rb") as f {
    mm = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
    while mm.tell() < mm.size() {
      length = struct.unpack("<I", mm.read(4))[0]
      yield mm.read(length)
    }
  }
}

// @Rule.P0_T_RECOVERY_POLICY: SSOT.WALDurabilityConfig;

// @Function.P0_T_WAL_RECOVER_WITH_INTEGRITY_CHECK: Recover WAL entries with gap/corruption handling and metrics
f recover_with_integrity_check(wal_path: Path, config: WALDurabilityConfig, checkpoint_config: CheckpointConfig? = None) -> ([WALEntry], WALRecoveryMetrics) {
// @Rule.P0_T_WAL_RECOVERY_METRICS_OBSERVABILITY: SSOT.Observability;
// @Rule.P0_T_WAL_MAX_REPLAY: SSOT.WALDurabilityConfig;
  max_replay_ns = checkpoint_config? checkpoint_config.max_wal_replay_sec * 1e9 : None
  cutoff_ts = max_replay_ns? int(time.time() * 1e9) - max_replay_ns : 0
  entries = []
  last_seq = -1
  metrics = WALRecoveryMetrics()
  start_time = time.time()

  for raw in read_raw_entries(wal_path) {
    metrics.total_entries += 1
    entry = deserialize_wal_entry(raw)

// @Rule.P0_T_WAL_SEQUENCE_GAP: SSOT.ErrorHandling;
    entry.sequence_id? & entry.sequence_id <= last_seq? {
      metrics.sequence_gaps += 1
      log.error("WAL sequence gap detected", last_seq, entry.sequence_id)
      raise WALSequenceGapError(f"Gap: {last_seq} -> {entry.sequence_id}")
    }
    entry.sequence_id? -> last_seq = entry.sequence_id

// @Rule.P0_T_WAL_HECKSUM: SSOT.SecurityValidation;
    config.verify_on_read & !verify_checksum(entry)? {
      metrics.corruption_errors += 1
      log.error("WAL checksum failure", entry_id=entry.entry_id)
      config.corrupt_entry_policy == "halt"?
        raise WALCorruptionError(f"Checksum fail: {entry.entry_id}")
        : { metrics.skipped_entries += 1; continue }
    }

    entries.append(entry)
    metrics.valid_entries += 1
    metrics.last_valid_sequence = entry.sequence_id | last_seq
  }

  metrics.recovery_duration_ms = (time.time() - start_time) * 1000

// @Rule.P0_T_WAL_RECOVERY_SUMMARY_OBSERVABILITY: SSOT.Observability;
  log.info("WAL recovery completed",
    total=metrics.total_entries,
    valid=metrics.valid_entries,
    skipped=metrics.skipped_entries,
    corrupted=metrics.corruption_errors,
    gaps=metrics.sequence_gaps,
    duration_ms=metrics.recovery_duration_ms
  )

  (entries, metrics)
}

// ============================================================================
// @DocMeta.P0_T_SEC6_CONTROL_PLANE_FLOW_IMPLEMENTATION: §6 . CONTROL PLANE FLOW & IMPLEMENTATION
// ============================================================================

// @Structure.P0_CPLFI_COMMAND_SIGNER_CLASS: HMAC signer/verifier for control plane commands
C CommandSigner(secret_key: bytes) {
  f sign(command: any) -> s {
// @Rule.P0_T_CPLFI_DICT_EXTRACTION: SSOT.SecurityValidation;
    cmd_dict = asdict(command) if hasattr(command, '__dataclass_fields__') else command
    signable = {k: v for k, v in cmd_dict.items() if k != "signature"}
// @Rule.P0_T_CPLFI_JSON_SERIALIZATION: SSOT.SerializationFormat;
    payload = json.dumps(signable, sort_keys=T, default=str).encode("utf-8")
    ret hmac.new(secret_key, payload, sha256).hexdigest()
  }

  f verify(command: any, signature: s) -> b {
    ret hmac.compare_digest(sign(command), signature)
  }
}

// @Structure.P0_T_CPLFI_NONCE_STORE_CLASS: Nonce store for replay prevention (Redis-backed)
C NonceStore(redis: RedisClient) {
// @Rule.P0_T_CPLFI_REPLAY_PREVENTION: SSOT.SecurityValidation;
  const NONCE_PREFIX: s = "nonce:used:"
 // @Rule.P0_T_CPLFI_NONCE_TTL_SYNC: SSOT.SignatureConfig;
  const NONCE_TTL_SEC: i = 300

  f is_nonce_valid(nonce: s, timestamp_ns: i) -> SignatureVerificationResult {
    // Check nonce expiry (5 minute window)
    now_ns = time.time() * 1e9
    age_sec = (now_ns - timestamp_ns) / 1e9
    age_sec > NONCE_TTL_SEC? -> ret EXPIRED_NONCE

    // Check nonce reuse (replay attack)
    nonce_key = f"{NONCE_PREFIX}{nonce}"
    redis.exists(nonce_key)? -> ret REPLAY_DETECTED

    // Mark nonce as used
    redis.setex(nonce_key, NONCE_TTL_SEC, "1")
    ret VALID
  }
}

// @Structure.P0_T_CPLFI_SIGNATURE_VALIDATOR_CLASS: Validate signature + optional nonce policy
C SignatureValidator(signer: CommandSigner, nonce_store: NonceStore?) {
// @Rule.P0_T_CPLFI_SIGNATURE_VALIDATOR_ASYNC: SSOT.AsyncExecution;
  async f validate(command: any) -> SignatureVerificationResult {
    // Step 1: Check signature presence
    !command.signature? -> raise InvalidSignatureError("Missing signature")

    // Step 2: Verify HMAC signature
    !signer.verify(command, command.signature)? {
      log.critical("Signature verification failed", command_id=command.command_id)
      ret INVALID_SIGNATURE
    }

    // Step 3: Validate nonce (replay prevention) - if nonce_store configured
    nonce_store? {
      nonce_result = nonce_store.is_nonce_valid(command.nonce, command.timestamp_ns)
      nonce_result != VALID? {
        log.critical("Nonce validation failed", command_id=command.command_id, result=nonce_result)
        ret nonce_result
      }
    }

    ret VALID
  }
}

// @Structure.P0_T_CPLFI_CONTROL_PLANE_GATE_CLASS: Gate for signature + RBAC enforcement with audit
C ControlPlaneGate(sig_validator: SignatureValidator, audit_logger: AuditLogger) {
  f require_permission(permission: Permission) -> decorator {
    @wraps(func)
    async f wrapper(command, ..) {
      // Step 1: Signature validation with audit logging on failure
      sig_result = sig_validator.validate(command)
      sig_result != VALID? {
// @Rule.P0_T_CPLFI_AUDIT_ON_FAILURE: SSOT.Observability;
        audit_logger.log_failed(
          func.__name__,
          getattr(command, "operator_id", "unknown"),
          f"Signature validation failed: {sig_result}",
          getattr(command, "command_id", "")
        )
        sig_result == INVALID_SIGNATURE? -> raise InvalidSignatureError("Invalid signature")
        sig_result == EXPIRED_NONCE? -> raise InvalidSignatureError("Nonce expired")
        sig_result == REPLAY_DETECTED? -> raise InvalidSignatureError("Replay attack detected")
      }

      // Step 2: RBAC permission check
      !has_permission(command.operator_id, permission)? {
        audit_logger.log_failed(func.__name__, command.operator_id, "Permission denied", command.command_id)
        raise PermissionDeniedError(f"Missing {permission}")
      }

      // Step 3: Execute and audit
// @Rule.P0_T_CPLFI_GATE_HANDLER_ASYNC: SSOT.AsyncExecution;
      try {
        result = await func(command, ..)
        await audit_logger.log_success(func.__name__, command.operator_id, command.command_id)
        ret result
      } catch e {
        await audit_logger.log_failed(func.__name__, command.operator_id, str(e), command.command_id)
        raise
      }
    }
    ret wrapper
  }
}

// @Function.P0_T_CPLFI_WITH_TIMEOUT: Awaitable wrapper with timeout and CommandTimeoutError
f with_timeout(coro: Awaitable[T], timeout_sec: f = 30, command_id: s = "") -> T {
  try {
    ret asyncio.wait_for(coro, timeout=timeout_sec)
  } catch TimeoutError {
    raise CommandTimeoutError(f"Command {command_id} timed out after {timeout_sec}s")
  }
}

// @Function.P0_T_CPLFI_TIMEOUT_HANDLER: Decorator factory applying with_timeout to async command handlers
f timeout_handler(timeout_sec: f = 30) -> decorator {
  @wraps(func)
  async f wrapper(command, ..) {
    ret with_timeout(func(command, ..), timeout_sec, command.command_id)
  }
  ret wrapper
}

// @Structure.P0_T_CPLFI_AUDIT_LOGGER_CLASS: Async audit logger for control plane actions
C AuditLogger(backend: AuditBackend) {
// @Rule.P0_T_CPLFI_AUDIT_LOGGER_ASYNC: SSOT.AsyncExecution;
  async f log_success(action: s, operator_id: s, command_id: s = "", details: d? = None, ip: s? = None) -> v {
    record = AuditRecord(
      record_id=uuid4(),
      timestamp=utcnow(),
      action=action,
      operator_id=operator_id,
      command_id=command_id,
      outcome=SUCCESS,
      details=details | {},
      ip_address=ip
    )
    await backend.write(record)
// @Rule.P0_T_CPLFI_AUDIT_LOGGER_OBSERVABILITY: SSOT.Observability;
    log.info("Control plane command succeeded", action=action, operator=operator_id, command_id=command_id)
  }

  async f log_failed(action: s, operator_id: s, reason: s, command_id: s = "", ip: s? = None) -> v {
    record = AuditRecord(
      record_id=uuid4(),
      timestamp=utcnow(),
      action=action,
      operator_id=operator_id,
      command_id=command_id,
      outcome=FAILED,
      reason=reason,
      ip_address=ip
    )
    await backend.write(record)
    log.warning("Control plane command failed", action=action, operator=operator_id, reason=reason)
  }
}

// @Structure.P0_T_CPLFI_KILL_SWITCH_HANDLER_CLASS: Control plane handler for kill switch commands
C KillSwitchHandler(gate: ControlPlaneGate, executor: KillSequenceExecutor) {
  @timeout_handler(30)
  async f handle(command: KillSwitchCommand) -> KillSwitchAck {
    permission = _level_to_permission(command.level)

    @gate.require_permission(permission)
    async f _execute(cmd) {
// @Ref.P0_T_CPLFI_REF_ASYNC: @Rule.P0_T_ASYNC;
      result = await executor.execute(cmd.level, cmd.reason)
      ret KillSwitchAck(
        command_id=cmd.command_id,
        level_executed=cmd.level,
        details=result
      )
    }

    ret await _execute(command)
  }

  f _level_to_permission(level: KillLevel) -> Permission {
 // @Rule.P0_T_CPLFI_PERMISSION_MAPPING: SSOT.RBACMapping;
    ret {
      SOFT_STOP: KILL_SWITCH_L0,
      HARD_STOP: KILL_SWITCH_L1,
      EMERGENCY: KILL_SWITCH_L2
    }[level]
  }
}

// ============================================================================
// @DocMeta.P0_T_SEC7_IMPLEMENTATION_TASKS: §7 . IMPLEMENTATION TASKS
// ============================================================================

// Kill Switch Tasks:
// @Task.P0_T_KS_1: KillSwitchCommand/Ack -> shared/kill_switch/commands.py
// @Task.P0_T_KS_2: KillSwitchController -> shared/kill_switch/controller.py
// @Task.P0_T_KS_3: Redis state store -> shared/kill_switch/state_store.py
// @Task.P0_T_KS_4: HMAC signature -> shared/kill_switch/auth.py
// @Task.P0_T_KS_5: Watchdog fallback -> shared/kill_switch/watchdog.py
// @Task.P0_T_KS_6: Unit tests -> tests/unit/test_kill_switch/

// RBAC Tasks:
// @Task.P0_T_RBAC_1: Role/Permission enums -> shared/rbac/models.py
// @Task.P0_T_RBAC_2: Permission matrix -> shared/rbac/permissions.py
// @Task.P0_T_RBAC_3: @require_permission -> shared/rbac/decorators.py
// @Task.P0_T_RBAC_4: Operator store -> shared/rbac/store.py
// @Task.P0_T_RBAC_5: Unit tests -> tests/shared/rbac/
// @Task.P0_T_RBAC_6: ensure_bootstrap_admin() -> shared/rbac/bootstrap.py
// @Task.P0_T_RBAC_7: bootstrap() integration -> shared/system_main.py
// @Task.P0_T_RBAC_8: Bootstrap Admin tests -> tests/unit/test_rbac/test_bootstrap.py

// Checkpoint Tasks:
// @Task.P0_T_CKP_1: SystemCheckpoint -> shared/checkpoint/models.py
// @Task.P0_T_CKP_2: Checkpoint writer -> shared/checkpoint/writer.py
// @Task.P0_T_CKP_3: Checkpoint reader -> shared/checkpoint/reader.py
// @Task.P0_T_CKP_4: Scheduled trigger -> shared/checkpoint/scheduler.py
// @Task.P0_T_CKP_5: Unit tests -> tests/checkpoint/
// @Task.P0_T_CKP_6: StatefulStrategy -> shared/strategy/state_interface.py
// @Task.P0_T_CKP_7: StrategyPipeline -> shared/strategy/pipeline.py
// @Task.P0_T_CKP_8: Warmup guard -> shared/strategy/guards.py
// @Task.P0_T_CKP_9: Strategy integration -> shared/checkpoint/writer.py

// Heartbeat Tasks:
// @Task.P0_T_HB_1: HeartbeatMessage -> shared/heartbeat/messages.py
// @Task.P0_T_HB_2: Heartbeat emitter -> shared/heartbeat/emitter.py
// @Task.P0_T_HB_3: Heartbeat reader -> shared/heartbeat/reader.py
// @Task.P0_T_HB_4: Timeout detector -> shared/heartbeat/detector.py
// @Task.P0_T_HB_5: Watchdog integration -> shared/heartbeat/watchdog_bridge.py
// @Task.P0_T_HB_6: Unit tests -> tests/shared/heartbeat/

// WAL Tasks:
// @Task.P0_T_WAL_1: WALEntry -> shared/wal/entry.py
// @Task.P0_T_WAL_2: NonBlockingWAL -> shared/wal/writer.py
// @Task.P0_T_WAL_3: Async Redis backup -> shared/wal/sync.py
// @Task.P0_T_WAL_4: Recovery -> shared/wal/recovery.py
// @Task.P0_T_WAL_5: Unit tests -> tests/shared/wal/
// @Task.P0_T_WAL_6: Durability config -> shared/wal/config.py
// @Task.P0_T_WAL_7: Rotation manager -> shared/wal/rotation.py

// Control Plane Tasks:
// @Task.P0_T_CPL_1: CommandSigner -> shared/control_plane/signature.py
// @Task.P0_T_CPL_2: SignatureValidator -> shared/control_plane/signature.py
// @Task.P0_T_CPL_3: ControlPlaneGate -> shared/control_plane/rbac_gate.py
// @Task.P0_T_CPL_4: timeout utilities -> shared/control_plane/timeout.py
// @Task.P0_T_CPL_5: AuditLogger -> shared/control_plane/audit.py
// @Task.P0_T_CPL_6: PostgreSQL backend -> shared/control_plane/backends/postgres.py
// @Task.P0_T_CPL_7: Unit tests -> tests/unit/control_plane/

// ============================================================================
// @DocMeta.P0_T_SEC8_FILE_STRUCTURE: §8 . FILE STRUCTURE
// ============================================================================

// myplugins/shared/
// +-- kill_switch/{commands,controller,state_store,auth,watchdog,dead_man_switch}.py
// +-- rbac/{models,permissions,decorators,store,bootstrap}.py
// +-- checkpoint/{models,writer,reader,scheduler}.py
// +-- heartbeat/{messages,emitter,reader,detector,watchdog_bridge,hub}.py
// +-- wal/{entry,writer,sync,recovery}.py
// +-- control_plane/{signature,rbac_gate,timeout,audit,backends/}.py
// +-- strategy/{state_interface,pipeline,guards}.py

// ============================================================================
// @DocMeta.P0_T_SEC9_SUCCESS_CRITERIA: §9 . SUCCESS CRITERIA
// ============================================================================

// [ ] Kill Switch L0/L1/L2 works
// [ ] RBAC permission checks work
// [ ] Bootstrap admin registration works (ensure_bootstrap_admin)
// [ ] Checkpoint save/restore works
// [ ] Strategy state serialize/deserialize works
// [ ] Heartbeat timeout triggers Watchdog (staged escalation 5s/15s/30s)
// [ ] DeadManSwitch uses WatchdogEscalationConfig
// [ ] All tests pass
// [ ] PASM §14 CQRS pattern compliance
// [ ] WAL non-blocking persistence
// [ ] WAL startup recovery works (max_wal_replay_sec enforced)
// [ ] Control Plane: All commands pass HMAC signature verification
// [ ] Control Plane: All commands pass RBAC permission checks
// [ ] Control Plane: All commands respect 30s timeout
// [ ] Control Plane: All commands logged to audit trail
// [ ] Safety Redis TTL=6s per SSOT SHARED_CONSTANTS §2.1
```
