```typescript
// P1: Orchestration Core SDSL - TOPOLOGY / FLOW
// @DocMeta.P1_T_SYSTEM_SPEC: System5 Orchestrator - Runtime Behavior & State Machine Flows
// IMPORTANT: Must Obay Stable ID Rules: Stable_ID_Base_Rules.md

// ═══════════════════════════════════════════════════════════════
// @DocMeta.P1_T_SEC1_SYSTEM_ARCHITECTURE_OVERVIEW: §1 . SYSTEM ARCHITECTURE OVERVIEW
// ═══════════════════════════════════════════════════════════════

// @Rule.P1_T_ARCH_SYSTEM_ARCHITECTURE: SSOT.SystemArchitecture;
// Layer 7: Observation (Collector, Metrics, Alerting)
// Layer 6: Execution (OrderManager, PositionManager, RiskGate)
// Layer 5: Strategy (StrategyExecutor, SignalGenerator)
// Layer 4: Models (ModelRegistry, InferenceEngine)
// Layer 3: Features (FeaturePipeline, DataTransformers)
// Layer 2: Data (DataClient, MarketDataAdapter)
// Layer 1: Infrastructure (Redis, EventBus, StateStore)

// @Rule.P1_T_ARCH_RESPONSIBILITIES: SSOT.OrchestratorResponsibilities;
// 1. Lifecycle Management (phases)
// 2. Component Coordination
// 3. State Machine Control
// 4. Health Aggregation
// 5. Recovery Orchestration

// ═══════════════════════════════════════════════════════════════
// @DocMeta.P1_T_SEC2_STATE_MACHINE_BEHAVIOR: §2 . STATE MACHINE BEHAVIOR
// ═══════════════════════════════════════════════════════════════

// @Rule.P1_T_SMB_SYSTEM_STATE: @Function.P1_T_SSMB_IS_TRADING_ALLOWED, CONTRACT.SystemState;
// @ContractRef.P1_T_SMB_REF_TRADING_CHECK: CONTRACT.SystemState, CONTRACT.SystemPhase, CONTRACT.DegradationLevel;
// @Function.P1_T_SMB_IS_TRADING_ALLOWED: Trading allowed predicate for SystemState
f is_trading_allowed(state: SystemState) -> b {
  state.phase == SystemPhase.TRADING &
  state.trading_safe == "off" &
  state.degradation_level in [DegradationLevel.FULL, DegradationLevel.PARTIAL]
  ? ret true : ret false
}

// ═══════════════════════════════════════════════════════════════
// @DocMeta.P1_T_SEC3_CIRCUIT_BREAKER_EVENT_DISPATCHER_FLOW: §3 . CIRCUIT BREAKER & EVENT DISPATCHER FLOW
// ═══════════════════════════════════════════════════════════════

// @Rule.P1_T_CBED_EVENT_DISPATCHER: @Structure.P1_T_CB_RELIABLE_EVENT_DISPATCHER_CLASS;
// Listener callbacks MUST run asynchronously outside the lock, and failure listeners MUST be isolated.
// @ContractRef.P1_T_CBED_REF_EVENT_DISPATCHER: CONTRACT.CircuitBreakerConfig, CONTRACT.ListenerState, CONTRACT.CircuitState;
// @Structure.P1_T_CBED__RELIABLE_EVENT_DISPATCHER_CLASS: Reliable event dispatcher with circuit breaker
C ReliableEventDispatcher {
  config: CircuitBreakerConfig,
  _listeners: d[s, AsyncCallback],
  _listener_states: d[s, ListenerState],
  _queue: AsyncQueue,
  _running: b = false

  f register(listener_id: s, callback: AsyncCallback) -> v {
    _listeners[listener_id] = callback ->
    _listener_states[listener_id] = ListenerState{}
  }

  f unregister(listener_id: s) -> v {
    _listeners.pop(listener_id) -> _listener_states.pop(listener_id)
  }

// @Rule.P1_T_CBED_DISPATCHED_EVENT: @Structure.P1_T_CB_RELIABLE_EVENT_DISPATCHER_CLASS;
  f dispatch(old_state: SystemState, new_state: SystemState) -> v {
    _queue.put((old_state, new_state))  // Non-blocking enqueue
  }

// @Rule.P1_T_CBED_SHOULD_CALL: @Structure.P1_T_CB_RELIABLE_EVENT_DISPATCHER_CLASS, CONTRACT.CircuitState;
  f _should_call(listener_id: s) -> b {
    state = _listener_states[listener_id] ->
    state.circuit_state == CircuitState.CLOSED ? ret true :
    state.circuit_state == CircuitState.OPEN ? (
      elapsed = now() - state.last_failure_time ->
      elapsed >= config.cooldown_seconds ? (state.circuit_state = CircuitState.HALF_OPEN -> ret true) : ret false
    ) : ret true  // HALF_OPEN allows test call
  }

// @Rule.P1_T_CBED_RECORD_ERROR: @Structure.P1_T_CB_RELIABLE_EVENT_DISPATCHER_CLASS, CONTRACT.CircuitBreakerConfig;
  f _record_error(listener_id: s, error: s) -> v {
    state = _listener_states[listener_id] ->
    state.consecutive_errors += 1 -> state.total_errors += 1 ->
    state.last_failure_time = now() ->
    state.consecutive_errors >= config.error_threshold ? (state.circuit_state = CircuitState.OPEN) : continue
  }
}

// ═══════════════════════════════════════════════════════════════
// @DocMeta.P1_T_SEC4_SYSTEM_STATE_MACHINE: §4 . SYSTEM STATE MACHINE
// ═══════════════════════════════════════════════════════════════

// @Rule.P1_T_SSM_CLASS_EVENT_DISPATCHER: @Structure.P1_T_SSM_SYSTEM_STATE_MACHINE_CLASS, @Structure.P1_T_CB_RELIABLE_EVENT_DISPATCHER_CLASS;
// @ContractRef.P1_T_SSM_REF_CORE: CONTRACT.SystemState, CONTRACT.SystemPhase, CONTRACT.DegradationLevel, CONTRACT.ALLOWED_TRANSITIONS;
// @Structure.P1_T_SSM_SYSTEM_STATE_MACHINE_CLASS: System state machine core
C SystemStateMachine {
  _state: SystemState,
  _dispatcher: ReliableEventDispatcher,
  _lock: AsyncLock,
  _health_aggregator: HealthAggregator

  f __init__(initial_state: SystemState, dispatcher: ReliableEventDispatcher?) -> v {
    _state = initial_state -> _dispatcher = dispatcher ?? ReliableEventDispatcher{}
  }

// @Rule.P1_T_SSM_SSMC_TRANSITION: @Structure.P1_T_SSM_SYSTEM_STATE_MACHINE_CLASS, CONTRACT.SystemPhase, CONTRACT.ALLOWED_TRANSITIONS;
  f transition(to_phase: SystemPhase, reason: s, operator_id: s?) -> b {
    async_with _lock {
      current = _state.phase ->
      to_phase not in ALLOWED_TRANSITIONS[current] ? ret false ->
      old_state = _state ->
      _state = SystemState{
        phase: to_phase,
        degradation_level: _compute_degradation(to_phase),
        entered_at_ns: utc_now_ns(),    // int64 ns UTC (SSOT naming)
        reason: reason,
        previous_phase: current
      }
    } ->
    _dispatcher.dispatch(old_state, _state) ->  // Outside lock
    ret true
  }

// @Rule.P1_T_SSM_SSMC_COMPUTE_DEGRADATION: @Structure.P1_T_SSM_SYSTEM_STATE_MACHINE_CLASS, CONTRACT.DegradationLevel, CONTRACT.SystemPhase;
// @ContractRef.P1_T_REF_DEGRADATION: CONTRACT.DEGRADATION_RULES;
  f _compute_degradation(phase: SystemPhase) -> DegradationLevel {
    phase in [SystemPhase.EMERGENCY, SystemPhase.STOPPING, SystemPhase.STOPPED]
      ? ret DegradationLevel.DISABLED :
    phase == SystemPhase.SAFE_MODE ? ret DegradationLevel.MINIMAL :
    ret _compute_from_component_health()
  }

// @Rule.P1_T_SSM_COMPUTE_FROM_HEALTH: @Structure.P1_T_SSM_SYSTEM_STATE_MACHINE_CLASS, CONTRACT.DEGRADATION_RULES;
  f _compute_from_component_health() -> DegradationLevel {
    health_map = _health_aggregator.get_all_health() ->
    // CRITICAL check (priority order)
    for (component_id, level) in DEGRADATION_RULES.critical {
      health_map[component_id]?.status == "CRITICAL" ? ret level : continue
    } ->
    // WARNING count
    warning_count = sum(1 for h in health_map.values() if h.status == "WARNING") ->
    warning_count >= 4 ? ret DegradationLevel.MINIMAL :
    warning_count >= 2 ? ret DegradationLevel.PARTIAL :
    ret DegradationLevel.FULL
  }
}

// ═══════════════════════════════════════════════════════════════
// @DocMeta.P1_T_SEC5_GUARDED_TRADING_MANAGER: §5 . GUARDED TRADING MANAGER
// ═══════════════════════════════════════════════════════════════

// @Rule.P1_T_GTM_MANAGER_CLASS_RECOVERY: @Structure.P1_T_GT_GUARDED_TRADING_MANAGER_CLASS, CONTRACT.RECOVERY_STAGES;
// @ContractRef.P1_T_GTM_REF_RECOVERY: CONTRACT.RecoveryStage, CONTRACT.RecoveryStageConfig, CONTRACT.GuardedTradingState, CONTRACT.RECOVERY_STAGES;
// @Structure.P1_T_GTM_GUARDED_TRADING_MANAGER_CLASS: Guarded trading 4-stage recovery manager
C GuardedTradingManager {
  _state: GuardedTradingState?

  f start_guarded_trading() -> GuardedTradingState {
    _state = GuardedTradingState{
      current_stage: RecoveryStage.STAGE_1, capacity_percent: 25,
      stage_entered_at: utc_now(), validation_status: {}
    } -> ret _state
  }

  f advance_stage(operator_id: s?) -> b {
    !_state ? ret false ->
    current_config = _get_stage_config(_state.current_stage) ->
    next_stage = _get_next_stage(_state.current_stage) ->
    next_stage == null ? ret true ->  // Stage 4 complete → TRADING
    !_all_validations_passed() ? ret false ->
    !current_config.auto_advance & !operator_id ? (_state.pending_approval = true -> ret false) ->
    // Advance stage
    next_config = _get_stage_config(next_stage) ->
    _state.current_stage = next_stage ->
    _state.capacity_percent = next_config.capacity_percent ->
    _state.stage_entered_at = utc_now() ->
    _state.validation_status = {} ->
    _state.pending_approval = false ->
    ret false  // Not yet complete
  }

  f get_capacity_limit() -> f { !_state ? ret 0.0 : ret _state.capacity_percent / 100.0 }
}

// ═══════════════════════════════════════════════════════════════
// @DocMeta.P1_T_SEC6_SAFE_MODE_ENFORCER: §6 . SAFE MODE ENFORCER
// ═══════════════════════════════════════════════════════════════

// @Rule.P1_T_SME_MODE_STRUCTURE_CONTRACT: @Structure.P1_T_SM_SAFE_MODE_ENFORCER_CLASS, CONTRACT.TRADING_SAFE_CONSTRAINTS;
// @ContractRef.P1_T_SME_REF_SAFE_MODE: CONTRACT.TradingSafeMode, CONTRACT.TradingSafeModeConstraints, CONTRACT.TRADING_SAFE_CONSTRAINTS;
// @Structure.P1_T_SME_SAFE_MODE_ENFORCER_CLASS: Safe mode order/config constraint enforcer
C SafeModeEnforcer {
  _config_safe: b = false,
  _trading_safe: TradingSafeMode = TradingSafeMode.OFF

  f set_config_safe(enabled: b, operator_id: s) -> v { _config_safe = enabled }
  f set_trading_safe(mode: TradingSafeMode, operator_id: s) -> v { _trading_safe = mode }
  f can_modify_config() -> b { ret !_config_safe }

  f validate_order(order: OrderRequest) -> OrderValidationResult {
    constraints = TRADING_SAFE_CONSTRAINTS[_trading_safe] ->
    order.is_new_position & !constraints.new_position_allowed ?
      ret OrderValidationResult{valid: false, reason: "New positions blocked"} ->
    order.is_new_position ? (
      max_size = order.normal_limit * (constraints.position_limit_percent / 100) ->
      order.size > max_size ? ret OrderValidationResult{valid: false, reason: "Position size exceeds limit"} : continue
    ) : continue ->
    order.order_type not in constraints.order_types_allowed ?
      ret OrderValidationResult{valid: false, reason: "Order type not allowed"} ->
    ret OrderValidationResult{valid: true}
  }
}

// ═══════════════════════════════════════════════════════════════
// @DocMeta.P1_T_SEC7_HEALTH_AGGREGATION_FLOW: §7 . HEALTH AGGREGATION FLOW
// ═══════════════════════════════════════════════════════════════

// @Rule.P1_T_HAF_FUNCTION: @Function.P1_T_HA_COMPUTE_SYSTEM_STATUS;
// 1 instance of UNHEALTHY means all system is UNHEALTHY
// @ContractRef.P1_T_HAF_REF_HEALTH: CONTRACT.HealthCheckResponse, CONTRACT.AggregatedHealthResponse;
// @Function.P1_T_HAF_COMPUTE_SYSTEM_STATUS: Aggregate component health into system status
f compute_system_status(components: d[s, HealthCheckResponse]) -> s {
  statuses = [c.status for c in components.values()] ->
  any(s == "CRITICAL" for s in statuses) ? ret "CRITICAL" :
  all(s == "HEALTHY" for s in statuses) ? ret "HEALTHY" :
  ret "DEGRADED"
}
// @Structure.P1_T_HAF_HEALTH_AGGREGATOR_CLASS: Health aggregation store and response builder
C HealthAggregator {
  _health_store: d[s, HealthCheckResponse]

  f get_all_health() -> d[s, HealthCheckResponse] { ret _health_store }
  f update_health(response: HealthCheckResponse) -> v { _health_store[response.component_id] = response }

  f aggregate() -> AggregatedHealthResponse {
    system_status = compute_system_status(_health_store) ->
    ret AggregatedHealthResponse{
      system_status: system_status,
      timestamp_ns: now_ns(),
      components: _health_store,
      degradation_level: _compute_degradation_from_health(),
      active_alerts: _collect_alerts(),
      summary: f"System {system_status}: {len(_health_store)} components"
    }
  }
}

// ═══════════════════════════════════════════════════════════════
// @DocMeta.P1_T_SEC8_BASELINE_ACTOR_FLOW: §8 . BASELINE ACTOR FLOW
// ═══════════════════════════════════════════════════════════════

// @Rule.P1_T_BAF_STRUCTURE: @Structure.P1_T_BA_BASELINE_ACTOR_CLASS;
// @ContractRef.P1_T_BAF_REF_BASELINE: CONTRACT.BaselineActorConfig, CONTRACT.DiagnosticsReport;
// @Structure.P1_T_BAF_BASELINE_ACTOR_CLASS: Baseline actor abstract diagnostics interface
C BaselineActor(ABC) {
  f collect_diagnostics() -> DiagnosticsReport   // Abstract
  f report_health() -> HealthReport              // Abstract
  f log_market_state() -> v                      // Abstract (no orders)
}

// @Structure.P1_T_BAF_SIMPLE_BASELINE_ACTOR_CLASS: Simple baseline actor implementation
C SimpleBaselineActor(BaselineActor) {
  config: BaselineActorConfig,
  _running: b = false

  f start() -> v { _running = true }
  f stop() -> v { _running = false }

  f collect_diagnostics() -> DiagnosticsReport {
    ret DiagnosticsReport{
      timestamp: utc_now(), system_phase: "L3_DISABLED", degradation_level: "DISABLED",
      component_status: _check_components(), memory_usage_mb: _get_memory_usage(),
      cpu_percent: _get_cpu_percent(), redis_latency_ms: _measure_redis_latency(),
      exchange_connectivity: _check_exchange(), last_market_update_age_sec: _get_market_data_age()
    }
  }
}

// ═══════════════════════════════════════════════════════════════
// @DocMeta.P1_T_SEC9_ORCHESTRATOR_CLASS: §9 . ORCHESTRATOR CLASS
// ═══════════════════════════════════════════════════════════════

// @Rule.P1_T_ORC_INTERFACE: @Interface.P1_T_ORC_ORCHESTRATOR_IF;
// @Rule.P1_T_ORC_CONTRACT: CONTRACT.KillSwitchState;
// @ContractRef.P1_T_ORC_REF_ORCHESTRATOR_DEPS: CONTRACT.SystemState, CONTRACT.KillSwitchState;
// @Interface.P1_T_ORC_ORCHESTRATOR_IF: Orchestrator boundary interface (start/stop/state/recovery)
C Orchestrator(ABC) {
  f start() -> b                                           // INITIALIZING → TRADING
  f stop(reason: s, timeout_per_phase: i = 10) -> b       // Graceful shutdown

// 🚨 The Kill Switch MUST be executed by the Safety Plane; the Orchestrator MUST only monitor.
  f on_kill_switch_state_changed(new_state: KillSwitchState) -> v

  f get_state() -> SystemState
  f trigger_recovery(recovery_type: s) -> b               // REC-1 or REC-2
}

// ═══════════════════════════════════════════════════════════════
// @DocMeta.P1_T_SEC10_STATE_API_FLOW: §10 . STATE API FLOW
// ═══════════════════════════════════════════════════════════════

// @ContractRef.P1_T_SAPT_REF_SYSTEM_STATE_API: CONTRACT.STATE_REDIS_KEY, CONTRACT.STATE_TTL_SECONDS, CONTRACT.SystemState;
// @Function.P1_T_SAPI_PUBLISH_STATE: Publish SystemState to Redis with TTL
f publish_state(redis: Redis, state: SystemState) -> v {
  redis.set(STATE_REDIS_KEY, state.to_json(), ex: STATE_TTL_SECONDS)
}

// ═══════════════════════════════════════════════════════════════
// @DocMeta.P1_T_SEC11_STARTUP_SHUTDOWN_SEQUENCE: §11 . STARTUP / SHUTDOWN SEQUENCE
// ═══════════════════════════════════════════════════════════════

// @Rule.P1_T_SUSD_STARTUP_FLOW: CONTRACT.STARTUP_PHASES;
// @ContractRef.P1_T_SUSD_REF_STARTUP_PHASES: CONTRACT.STARTUP_PHASES;
// Phase 1: Safety infrastructure (safety_redis, safety_monitor)
// Phase 2: Application infrastructure (app_redis, postgres)
// Phase 3: Orchestrator (self-registration)
// Phase 4: Feature pipeline
// Phase 5: Model manager
// Phase 6: Strategy engine
// Phase 7: Ops dashboard

// @Rule.P1_T_SUSD_SHUTDOWN_FLOW: CONTRACT.SHUTDOWN_TIMEOUT_PER_PHASE_SEC;
// @ContractRef.P1_SUSD_T_REF_SHUTDOWN_PHASES: CONTRACT.SHUTDOWN_TIMEOUT_PER_PHASE_SEC;
// Each phase has 10-second timeout
// Components in each phase are stopped concurrently
// Wait for all components in phase N before proceeding to phase N-1

// ═══════════════════════════════════════════════════════════════
// @DocMeta.P1_T_SEC12_IMPLEMENTATION_TASKS: §12 . IMPLEMENTATION TASKS
// ═══════════════════════════════════════════════════════════════

// @DocMeta.P1_T_IMPT_TASKCAT_SSM: State Machine
// @Task.P1_T_SSM_1: SystemPhase, DegradationLevel, TransitionPriority enums → states.py
// @Task.P1_T_SSM_2: SystemState dataclass → states.py
// @Task.P1_T_SSM_3: ALLOWED_TRANSITIONS map → state_machine.py
// @Task.P1_T_SSM_4: SystemStateMachine class → state_machine.py

// @DocMeta.P1_T_IMPT_TASKCAT_ED: Event Dispatcher (GAP-06)
// @Task.P1_T_ED_1: CircuitBreakerConfig, ListenerState → event_dispatcher.py
// @Task.P1_T_ED_2: ReliableEventDispatcher class → event_dispatcher.py
// @Task.P1_T_ED_3: Listener registration/unregistration → event_dispatcher.py

// @DocMeta.P1_T_IMPT_TASKCAT_ORC: Orchestrator Core
// @Task.P1_T_ORC_1: Orchestrator interface → orchestrator.py
// @Task.P1_T_ORC_2: Component registry → registry.py
// @Task.P1_T_ORC_3: Startup sequence (7-phase) → startup.py
// @Task.P1_T_ORC_4: Shutdown sequence (reverse) → shutdown.py

// @DocMeta.P1_T_IMPT_TASKCAT_GT: Recovery & Safe Mode
// @Task.P1_T_GT_1: RecoveryStage enum, RecoveryStageConfig → recovery.py
// @Task.P1_T_GT_2: RECOVERY_STAGES (4 stages) → recovery.py
// @Task.P1_T_GT_3: GuardedTradingManager → recovery.py
// @Task.P1_T_SF_1: TradingSafeMode enum → safe_mode.py
// @Task.P1_T_SF_2: TradingSafeModeConstraints → safe_mode.py
// @Task.P1_T_SF_3: SafeModeEnforcer → safe_mode.py

// @DocMeta.P1_T_IMPTTASKCAT_BA: Baseline Actor
// @Task.P1_T_BA_1: BaselineActorConfig → baseline_actor.py
// @Task.P1_T_BA_2: BaselineActor ABC → baseline_actor.py
// @Task.P1_T_BA_3: DiagnosticsReport → baseline_actor.py
// @Task.P1_T_BA_4: SimpleBaselineActor → baseline_actor.py

// @DocMeta.P1_T_IMPTTASKCAT_EV: Events & Integration
// @Task.P1_T_EV_1: EventType, OrchestratorEvent → events.py
// @Task.P1_T_EV_2: Event publisher → publisher.py
// @Task.P1_T_INT_1: Kill Switch integration → kill_switch_handler.py
// @Task.P1_T_INT_2: Health aggregation → health_aggregator.py

// @DocMeta.P1_T_IMPTTASKCAT_TEST: Testing
// @Task.P1_T_TEST_1: State machine transitions → tests/unit/test_state_machine.py
// @Task.P1_T_TEST_2: Event dispatcher circuit breaker → tests/unit/test_event_dispatcher.py
// @Task.P1_T_TEST_3: Recovery stages → tests/unit/test_recovery.py
// @Task.P1_T_TEST_4: Safe mode enforcement → tests/unit/test_safe_mode.py
// @Task.P1_T_TEST_5: Baseline actor diagnostics → tests/unit/test_baseline_actor.py
// @Task.P1_T_TEST_6: Integration tests → tests/integration/test_orchestrator.py

// ═══════════════════════════════════════════════════════════════
// @DocMeta.P1_T_SEC13_FILE_STRUCTURE: §13 . FILE STRUCTURE
// ═══════════════════════════════════════════════════════════════

// myplugins/orchestrator/
// ├── __init__.py
// ├── states.py              # SystemPhase, SystemState, DegradationLevel
// ├── state_machine.py       # SystemStateMachine, ALLOWED_TRANSITIONS
// ├── event_dispatcher.py    # ReliableEventDispatcher, CircuitBreaker
// ├── orchestrator.py        # Orchestrator interface and implementation
// ├── registry.py            # Component registry
// ├── startup.py             # Startup sequence (7-phase)
// ├── shutdown.py            # Shutdown sequence (reverse order)
// ├── recovery.py            # GuardedTradingManager, RecoveryStage
// ├── safe_mode.py           # SafeModeEnforcer, TradingSafeMode
// ├── baseline_actor.py      # BaselineActor, SimpleBaselineActor
// ├── events.py              # Event types and dataclasses
// ├── publisher.py           # Event publisher
// ├── kill_switch_handler.py # Kill Switch integration
// └── health_aggregator.py   # Health aggregation

// ═══════════════════════════════════════════════════════════════
// @DocMeta.P1_T_SEC14_SUCCESS_CRITERIA: §14 . SUCCESS CRITERIA
// ═══════════════════════════════════════════════════════════════

// @Criteria.P1_T_S001: All state machine transitions execute correctly.
// @Criteria.P1_T_S002: The startup sequence respects dependency order.
// @Criteria.P1_T_S003: The shutdown sequence stops components in reverse order.
// @Criteria.P1_T_S004: State transitions triggered by the Kill Switch work correctly.
// @Criteria.P1_T_S005: Health aggregation covers all components.
// @Criteria.P1_T_S006: Events are delivered via the MessageBus.
// @Criteria.P1_T_S007: All tests pass.
```
