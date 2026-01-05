```typescript
// P2: Feature Integration SDSL - TOPOLOGY / FLOW
// L2-L3 Feature Pipeline + Model Pipeline Zero-Copy Integration
// Component Behavior, State Machines, Data Flow, and Runtime Operations
// Source: 30_PHASE_2_FEATURE_INTEGRATION.md, Plugin_Architecture_Standards_Manual.md §12
// IMPORTANT: Must Obay Stable ID Rules: Stable_ID_Base_Rules.md
// ═══════════════════════════════════════════════════════════════
// @DocMeta.P2_T_SEC1_OVERVIEW: §1 Overview
// ═══════════════════════════════════════════════════════════════
// P2: L2-L3 Feature Pipeline + Model Pipeline Integration
// Zero-Copy Protocol for high-performance data transfer

// ═══════════════════════════════════════════════════════════════
// @DocMeta.P2_T_SEC2_1_PERMISSION_RULES_OPERATIONS_PERMISSION_HOLDER: §2.1 Permission Rules (Operations → Permission/Holder)
// ═══════════════════════════════════════════════════════════════
// | Operation        | Permission | Holder                      |
// | Buffer allocate  | WRITE      | Publisher (FeatureRunner)   |
// | Buffer write     | WRITE      | Publisher (FeatureRunner)   |
// | Buffer publish   | WRITE      | Publisher (FeatureRunner)   |
// | Buffer read/claim| READ       | Consumer (ModelInference)   |
// | Buffer release   | READ       | Consumer (ModelInference)   |

// ═══════════════════════════════════════════════════════════════
// @DocMeta.P2_T_SEC3_L2_L3_PULL_PATTERN_FLOW: §3 L2-L3 Pull Pattern - Flow
// ═══════════════════════════════════════════════════════════════
// @Rule.P2_T_PPF_PATTERN_PULL: @Structure.P2_T_FVTF_FEATURE_CLIENT_CLASS, @Structure.P2_T_FVTF_FEATURE_RUNNER_CLASS;
// Flow: ModelInference -> FeatureRequest -> FeatureRunner -> FeatureResponse -> ModelInference

// ═══════════════════════════════════════════════════════════════
// @DocMeta.P2_T_SEC4_2_BACKPRESSURE_BEHAVIOR_CLASSES: §4.2 Backpressure - Behavior Classes
// ═══════════════════════════════════════════════════════════════
// @Rule.P2_T_BPBC_CONFLATION: SSOT.MarketData, SSOT.InstrumentID;
// @Structure.P2_T_BPBC_CONFLATION_BUFFER_CLASS: Conflation buffer behavior class
C ConflationBuffer(cfg:ConflationConfig) {
  _buffers: d[s,any], _conflation_count: d[s,i], _total: i
  f put(sym:s, data:any) -> b {
    sym in _buffers ? (
      _conflation_count[sym]++ -> _total++ ->
      log.CRITICAL("Conflation",sym) ->
      _buffers[sym]=data -> ret F
    ) : (_buffers[sym]=data -> ret T)
  }
  f get(sym:s) -> any? { ret _buffers.pop(sym) }
  f get_all() -> d[s,any] { ret _buffers.clear_copy() }
  f stats() -> d { ret {buffered:len(_buffers),total:_total,per_sym:_conflation_count} }
}

// @Structure.P2_T_BP_BACKPRESSURE_MANAGER_CLASS: Backpressure manager alerting and counters
C BackpressureManager(cfg:BackpressureManagerConfig) {
// @Rule.P2_T_ALERT: CONTRACT.RiskControl, CONTRACT.LogSeverity;
// @Rule.P2_T_CHANNEL: CONTRACT.SafetyRedis;
  _safety_redis: Redis?, _drop_count: i, _conflation_count: i
  f start() -> v { _safety_redis = Redis.connect(cfg.safety_redis_host,cfg.safety_redis_port) }
  f record_drop(msg_type:s, priority:MessagePriority, reason:s, details:d?, component_id:s="unknown") -> v {
    _drop_count++ ->
    payload = {event:"BACKPRESSURE_DROP",level:"CRITICAL",msg_type,priority,reason,drop_count:_drop_count,details,ts:now_ns()} ->
    log.CRITICAL("Backpressure DROP",payload) ->
    _safety_redis?.publish(cfg.alert_channel,json(payload))
  }
  f record_conflation(sym:s, count:i) -> v {
    _conflation_count++ ->
    payload = {event:"BACKPRESSURE_CONFLATION",level:"CRITICAL",sym,count,total:_conflation_count,ts:now_ns()} ->
    log.CRITICAL("Conflation",payload) ->
    _safety_redis?.publish(cfg.alert_channel,json(payload))
  }
}

// ═══════════════════════════════════════════════════════════════
// @DocMeta.P2_T_SEC4_2_4_BACKPRESSURE_STATS_PERSISTENCE_FLOW: §4.2.4 Backpressure Stats Persistence - Flow
// ═══════════════════════════════════════════════════════════════
// @Function.P2_T_BPSP_PERSIST_STATS: Persist backpressure stats to Redis with TTL
f _persist_stats(component_id:s, main_redis:Redis, drop_count:i, conflation_count:i, last_drop_ts:i, last_conflation_ts:i, queue_high_watermark:i) -> v {
  stats_key = f"bp:stats:{component_id}" ->
  pipe = main_redis.pipeline() ->
  pipe.hset(stats_key, {total_drops:drop_count, total_conflations:conflation_count, last_drop_ts:last_drop_ts, last_conflation_ts:last_conflation_ts, queue_high_watermark:queue_high_watermark}) ->
  pipe.expire(stats_key, 60) ->
  pipe.execute()
}

// ═══════════════════════════════════════════════════════════════
// @DocMeta.P2_T_SEC3_4_ZERO_COPY_BUFFER_BEHAVIOR_IMPLEMENTATION: §3.4 Zero-Copy Buffer - Behavior Implementation
// ═══════════════════════════════════════════════════════════════
// @Structure.P2_T_ZCBB_ZERO_COPY_BUFFER_CLASS: Zero-copy buffer wrapper and IPC conversion
C ZeroCopyBuffer {
// @Rule.P2_T_ZCBB_VALIDATE_BUFFER: CONTRACT.ALLOWED_DTYPES, CONTRACT.MemoryLayout;
  data: pa.Array, dtype: s, shape: (i..)
  f from_numpy(arr:np.ndarray) -> ZeroCopyBuffer {
    arr.dtype not in ALLOWED_DTYPES ? raise DataTypeError :
    !arr.flags.C_CONTIGUOUS ? raise BufferLayoutError :
    arr.dtype.byteorder==">" ? raise BufferLayoutError("must be LE") :
    ret ZeroCopyBuffer(pa.array(arr.flatten()),str(arr.dtype),arr.shape)
  }
  f to_numpy() -> np.ndarray { ret data.to_numpy().reshape(shape) }
  f to_ipc() -> bytes { ret pa.ipc.serialize(data) }
  f from_ipc(ipc:bytes,shape:(i..),dtype:s) -> ZeroCopyBuffer {
// @Rule.P2_T_ZCBB_VALIDATE_NUMPY_DESERIALIZE: CONTRACT.ALLOWED_DTYPES, CONTRACT.BufferShape;
    dtype not in ALLOWED_DTYPES ? raise DataTypeError(f"Invalid dtype: {dtype}") :
    reader = pa.ipc.open_stream(ipc) ->
    batch = reader.read_next_batch() ->
    arrow_array = batch.column(0) ->
    ret ZeroCopyBuffer(arrow_array, dtype, shape)
  }
  f to_shm_ref(mgr:ZeroCopyBufferManager) -> s {
    // Write to SharedMemory and return reference
    ipc_bytes = to_ipc() ->
    desc = mgr.allocate(len(ipc_bytes), dtype, shape) ->
    desc = mgr.write(desc, ipc_bytes) ->
    mgr.publish(desc, "") ->
    ret desc.path  // shm://<uuid>.ipc
  }
}

// ═══════════════════════════════════════════════════════════════
// @DocMeta.P2_T_SEC3_5_BUFFER_LIFECYCLE_STATE_MACHINE_GAP_04: §3.5 Buffer Lifecycle State Machine (GAP-04)
// ═══════════════════════════════════════════════════════════════
// State Transition Diagram:
// ALLOCATED -> WRITTEN -> PUBLISHED -> CLAIMED -> RELEASED
//     |          |           |           |          |
//     └──────────┴───────────┴───────────┴──────► EXPIRED (TTL/Janitor)

// ═══════════════════════════════════════════════════════════════
// @DocMeta.P2_T_SEC3_5_3_1_BUFFER_REGISTRY_BEHAVIOR_REDIS_BACKED: §3.5.3.1 BufferRegistry - Behavior (Redis-backed)
// ═══════════════════════════════════════════════════════════════
// @Structure.P2_T_BRBR_ZC_BUFFER_REGISTRY_CLASS: Redis-backed buffer registry behavior
C BufferRegistry(redis:Redis) {
  f register(desc:BufferDescriptor) -> v {
    key = f"buffer:{desc.buffer_id}" ->
    redis.hset(key, desc.to_dict()) -> redis.expire(key, desc.expires_at_ns)
  }
  f get(buffer_ref:s) -> BufferDescriptor? {
    buffer_id = buffer_ref.replace("shm://","").replace(".ipc","") ->
    data = redis.hgetall(f"buffer:{buffer_id}") ->
    ret data ? BufferDescriptor.from_dict(data) : None
  }
  f incr_refcount(buffer_ref:s) -> i { ret redis.hincrby(key,"refcount",1) }
  f decr_refcount(buffer_ref:s) -> i { ret redis.hincrby(key,"refcount",-1) }
  f update_state(buffer_ref:s, state:BufferState) -> v { redis.hset(key,"state",state.value) }
}

// ═══════════════════════════════════════════════════════════════
// @DocMeta.P2_T_SEC3_5_3_2_BUFFER_JANITOR_CLEANUP_BEHAVIOR_SAFETY_NET_FOR_CRASH_TIMEOUT: §3.5.3.2 BufferJanitor - Cleanup Behavior (Safety net for crash/timeout)
// ═══════════════════════════════════════════════════════════════
// @Rule.P2_T_BJCB_JANITOR: @Structure.P2_T_BJCB_ZC_BUFFER_JANITOR_CLASS, @Structure.P2_T_BRBR_ZC_BUFFER_REGISTRY_CLASS;
// @Structure.P2_T_BJCB_ZC_BUFFER_JANITOR_CLASS: Cleanup janitor for expired buffers
C BufferJanitor(registry:BufferRegistry, manager:ZeroCopyBufferManager, scan_interval_sec:i=10) {
  _running: b, _task: Task?, _pid_namespace_shared: b = T
  f start() -> v { _running = T -> _task = create_task(_cleanup_loop()) }
  f stop() -> v { _running = F -> _task?.cancel() }
  f _cleanup_loop() -> v {
    while _running:
      _cleanup_expired() -> sleep(scan_interval_sec)
  }
  f _cleanup_expired() -> v {
    expired_buffers = registry.scan_expired() ->
    for desc in expired_buffers:
      !_is_publisher_alive(desc) | desc.is_expired() ?
        (manager._unlink(desc.path) -> registry.update_state(desc.path, EXPIRED) ->
         log.WARN("Janitor cleaned expired buffer", buffer_id=desc.buffer_id))
  }
  f _is_publisher_alive(desc:BufferDescriptor) -> b {
// @Rule.P2_T_BJCB_PID_NS: SSOT.PID, CONTRACT.Heartbeat;
    _pid_namespace_shared ? is_pid_alive(desc.publisher_pid) :
    redis.exists(f"buffer:heartbeat:{desc.buffer_id}")
  }
}

// Helper function for PID validation
// @Function.P2_T_BJCB_ZC_IS_PID_ALIVE: PID liveness check helper for janitor safety
f is_pid_alive(pid:i) -> b {
  // os.kill(pid, 0) - signal 0 checks if process exists
  try: os.kill(pid, 0) -> ret T
  except OSError: ret F
}

// ═══════════════════════════════════════════════════════════════
// @DocMeta.P2_T_SEC3_5_4_ZERO_COPY_BUFFER_MANAGER_LIFECYCLE_MANAGEMENT: §3.5.4 ZeroCopyBufferManager - Lifecycle Management
// ═══════════════════════════════════════════════════════════════
// @Structure.P2_T_ZCBM_ZERO_COPY_BUFFER_MANAGER_CLASS: Buffer manager lifecycle and state transitions
C ZeroCopyBufferManager(registry:BufferRegistry, ttl_sec:i=30) {
  f allocate(size:i, dtype:s, shape:(i..)) -> BufferDescriptor {
// @Rule.P2_T_ZCBM_LIMIT: CONTRACT.BUFFER_SIZE_LIMIT_BYTES, CONTRACT.LogSeverity;
    size > BUFFER_SIZE_LIMIT_BYTES ? (log.CRITICAL("size>1MB") -> raise) :
    desc = BufferDescriptor(dtype=dtype,shape=shape,size_bytes=size) ->
    desc.path = f"shm://{desc.buffer_id}.ipc" ->
    touch(SHM_BASE_DIR/f"{desc.buffer_id}.ipc", mode=0o600) ->
    async_write(zeros(size)) -> ret desc
  }
  f write(desc:BufferDescriptor, data:bytes) -> BufferDescriptor {
    // State: ALLOCATED -> WRITTEN
    desc.state != ALLOCATED ? raise :
    async_write(data) -> fsync() ->
    desc.crc32 = hex(crc32(data)) -> desc.state = WRITTEN -> ret desc
  }
  f publish(desc:BufferDescriptor, schema_id:s) -> BufferDescriptor {
    // State: WRITTEN -> PUBLISHED
    desc.state != WRITTEN ? raise :
    desc.state = PUBLISHED -> desc.schema_id = schema_id ->
    desc.expires_at_ns = now_ns() + ttl_sec*1e9 ->
    registry.register(desc) -> ret desc
  }
  f claim(buffer_ref:s) -> (bytes, BufferDescriptor) {
    // State: PUBLISHED -> CLAIMED (first claim)
// @Rule.P2_T_ZCBM_CRC: CONTRACT.CRC32, CONTRACT.BufferError;
    desc = registry.get(buffer_ref) ->
    desc.is_expired() ? raise BufferError("expired") :
    data = async_read(file) ->
    crc32(data) != desc.crc32 ? raise BufferError("CRC mismatch") :
    registry.incr_refcount(buffer_ref) ->
    desc.state == PUBLISHED ? (desc.state=CLAIMED -> registry.update_state) :
    ret (data, desc)
  }
  f release(buffer_ref:s) -> v {
    // refcount-- -> if 0: unlink file
    new_ref = registry.decr_refcount(buffer_ref) ->
    new_ref <= 0 ? (_unlink(buffer_ref) -> registry.update_state(RELEASED))
  }
  f _unlink(buffer_ref:s) -> v { unlink(file, missing_ok=T) }
}

// ═══════════════════════════════════════════════════════════════
// @DocMeta.P2_T_SEC3_5_7_CONSUMER_RELEASE_RESPONSIBILITY_FLOW_PATTERN: §3.5.7 Consumer Release Responsibility - Flow Pattern
// ═══════════════════════════════════════════════════════════════
// @Rule.P2_T_CRRF_RELEASE: @Structure.P2_T_ZCBM_ZERO_COPY_BUFFER_MANAGER_CLASS, @Structure.P2_T_CRRF_ZERO_COPY_CONSUMER_CLASS;
// @Rule.SI_CRRF_PATTERN_CONTEXT_MANAGER: @Structure.P2_T_CRRF_ZERO_COPY_CONSUMER_CLASS;
// @Rule.P2_T_CRRF_JANITOR_FALLBACK: @Structure.P2_T_BJCB_ZC_BUFFER_JANITOR_CLASS;
// @Structure.P2_T_CRRF_ZERO_COPY_CONSUMER_CLASS: Consumer context manager and release responsibility
C ZeroCopyConsumer(manager:ZeroCopyBufferManager) {
  // Context Manager: fetch() -> auto-release on exit
  f fetch(buffer_ref:s) -> async_ctx(bytes,BufferDescriptor) {
    data,desc = manager.claim(buffer_ref) ->
    yield (data,desc) ->
    finally: manager.release(buffer_ref)
  }
  // Raw API (manual release required)
  f fetch_raw(buffer_ref:s) -> (bytes,BufferDescriptor) { ret manager.claim(buffer_ref) }
  f release(buffer_ref:s) -> v { manager.release(buffer_ref) }
}

// Flow: Producer->publish-> Consumer->release-> [RELEASED]
// Abnormal: Producer->publish-> [Consumer crash] -> Janitor(TTL)-> [EXPIRED]

// ═══════════════════════════════════════════════════════════════
// @DocMeta.P2_T_SEC3_5_8_MLX_RUST_INTEGRATION_DATA_FLOW: §3.5.8 MLX/Rust Integration - Data Flow
// ═══════════════════════════════════════════════════════════════
// Python (MLX): mx.eval() -> np.asarray() -> C-contiguous float32/64 -> ZeroCopyBuffer
// Rust (PyO3): PyBuffer<f64> borrow -> registry refcount -> prevent GC
// @Function.P2_T_MRDF_MLX_TO_ZERO_COPY: Convert MLX array to zero-copy buffer descriptor
f mlx_to_zero_copy(mlx_arr:mx.array, mgr:ZeroCopyBufferManager) -> BufferDescriptor {
  mx.eval(mlx_arr) -> np_arr = np.asarray(mlx_arr) ->
  !np_arr.flags.C_CONTIGUOUS ? np_arr = np.ascontiguousarray(np_arr) :
  np_arr.dtype not in (f32,f64) ? np_arr = np_arr.astype(f64) :
  buf = ZeroCopyBuffer.from_numpy(np_arr) ->
  desc = mgr.allocate(len(buf.to_ipc()),str(np_arr.dtype),np_arr.shape) ->
  ret mgr.write(desc, buf.to_ipc())
}

// ═══════════════════════════════════════════════════════════════
// @DocMeta.P2_T_SEC4_FEATURE_VECTOR_TRANSFER_FLOW_BEHAVIOR: §4 Feature Vector Transfer - Flow & Behavior
// ═══════════════════════════════════════════════════════════════
// @Rule.P2_T_FVTF_TIMESTAMP: SSOT.UTC_Timestamp;
// Usage: datetime.now(timezone.utc) or equivalent
// @Function.P2_T_FVTF_UTC_NOW: Timezone-aware UTC now for feature transfer timestamps
f utc_now() -> ts { ret datetime.now(timezone.utc) }

// Topic naming helpers
// @Function.P2_T_FVTF_FEATURE_REQUEST_TOPIC: Feature request topic naming helper
f feature_request_topic(model_id:s) -> s { ret f"feature:req:{model_id}" }
// @Function.P2_T_FVTF_FEATURE_RESPONSE_TOPIC: Feature response topic naming helper
f feature_response_topic(trace_id:s) -> s { ret f"feature:resp:{trace_id}" }

// Helper: compute feature_schema_id (SHA-256 of BNS definition)
// @Function.P2_T_FVTF_COMPUTE_FEATURE_SCHEMA_ID: Compute feature schema id from BNS definition
f compute_feature_schema_id(bns_dict:d) -> s {
  // SHA-256 hash of serialized BNS definition for schema validation
  ret sha256(json.dumps(bns_dict, sort_keys=T)).hexdigest()
}

// @Structure.P2_T_FVTF_FEATURE_CLIENT_CLASS: Feature request/response client abstraction
C FeatureClient(redis:Redis, local_runner:FeatureRunner?) {
  // Abstracts Redis Req/Rep or same-process optimization
  f get_feature_vector(model_id:s, bns_id:s, timeout_ms:i=3000) -> FeatureResponse {
    local_runner ? ret local_runner.compute(bns_id) :
    // Redis Req/Rep
    trace_id = uuid4() ->
    req = FeatureRequest(trace_id, bns_id, model_id, now_ns()) ->
    redis.rpush(feature_request_topic(model_id), json(req)) ->
    result = redis.blpop(feature_response_topic(trace_id), timeout=timeout_ms/1000) ->
    !result ? ret FeatureResponse(trace_id, "TIMEOUT", error_code="TIMEOUT") :
    ret FeatureResponse.from_json(result[1])
  }
}
// @Structure.P2_T_FVTF_FEATURE_RUNNER_CLASS: Feature computation runner and transfer builder
C FeatureRunner {
  f get_feature_vector(bns_id:s) -> FeatureVectorTransfer {
    bns = bns_manager.get_bns(bns_id) ->
    results = _compute_features(bns) ->
    ordered = [results[node_id] for node_id in bns.feature_vector.order] ->
    feature_array = np.column_stack(ordered).astype(bns.feature_vector.dtype) ->
    schema_id = compute_feature_schema_id(bns.to_dict()) ->
    ret FeatureVectorTransfer(bns_id,schema_id,utc_now(),ZeroCopyBuffer.from_numpy(feature_array),bns.feature_vector.order)
  }
  f compute(bns_id:s) -> FeatureResponse {
    // Public API: convert internal Transfer -> FeatureResponse
// @Rule.P2_T_FVTF_RP_TIMING: CONTRACT.ComputeTime;
// @Rule.P2_T_FVTF_RP_TRACE: CONTRACT.TraceID;
// @Rule.P2_T_FVTF_RP_ERROR_COMPUTE: CONTRACT.FeatureResponse, CONTRACT.ErrorStatus;
    start_ns = time.perf_counter_ns() ->
    try:
      transfer = get_feature_vector(bns_id) ->
      shm_ref = transfer.buffer.to_shm_ref() ->
      compute_time_ms = (time.perf_counter_ns() - start_ns) / 1_000_000 ->
      ret FeatureResponse(trace_id:"",status:"OK",content_type:"arrow",buffer_ref:shm_ref,schema_id:transfer.feature_schema_id,feature_count:len(transfer.order),compute_time_ms:compute_time_ms)
    except Exception as e:
      ret FeatureResponse(trace_id:"",status:"ERROR",error_code:"COMPUTE_FAILED",error_message:str(e))
  }
}

// @Structure.P2_T_FVTF_FEATURE_FETCHER_CLASS: ModelInference-side feature fetcher and validation
// @DocMeta.P2_T_FVTF_SEC4_2_MODEL_INFERENCE_FEATURE_FETCHER_BEHAVIOR: §4.2 ModelInference Feature Fetcher - Behavior
C FeatureFetcher(redis:Redis, model_id:s, local_runner:FeatureRunner?) {
  _client: FeatureClient
  f fetch(bns_id:s, expected_schema_id:s) -> np.ndarray {
// @Rule.P2_T_FVTF_FF_TIMEOUT: CONTRACT.Timeout;
    resp = _client.get_feature_vector(model_id,bns_id,timeout_ms=3000) ->
    resp.status != "OK" ? (
      resp.status == "TIMEOUT" ? raise FeatureTimeoutError :
      raise FeatureFetchError(resp.error_code)
    ) :
    resp.schema_id != expected_schema_id ? raise FeatureSchemaMismatch :
    ret _read_buffer(resp.buffer_ref)
  }
  f _read_buffer(buffer_ref:s, desc:BufferDescriptor?) -> np.ndarray {
// Zero-Copy: pa.memory_map + ipc.open_stream
// @Rule.P2_T_FVTF_RB_PATH: CONTRACT.SHMPath;
// @Rule.P2_T_FVTF_RB_RESHAPE: @Structure.P2_T_BRBR_ZC_BUFFER_REGISTRY_CLASS, CONTRACT.BufferShape;
    buffer_id = buffer_ref.replace("shm://","").replace(".ipc","") ->
    file_path = Path("/dev/shm/system5_zero_copy") / f"{buffer_id}.ipc" ->
    source = pa.memory_map(str(file_path),"r") ->
    batch = pa.ipc.open_stream(source).read_next_batch() ->
    arr = batch.column(0).to_numpy(zero_copy_only=F) ->
    // Reshape using descriptor shape if available (from BufferRegistry)
    desc & desc.shape ? ret arr.reshape(tuple(desc.shape)) : ret arr
  }
}

// @Structure.P2_T_FVTF_FEATURE_RUNNER_REQ_REP_HANDLER_CLASS: Redis req/rep handler for feature runner
// @DocMeta.P2_T_FVTF_SEC4_3_FEATURE_RUNNER_REQ_REP_HANDLER_FLOW: §4.3 FeatureRunner Req/Rep Handler - Flow
C FeatureRunnerReqRepHandler(runner:FeatureRunner, redis:Redis, model_id:s) {
  f run() -> v {
    req_topic = feature_request_topic(model_id) ->
    loop: result = redis.blpop(req_topic,timeout=5) ->
          result ? _handle_request(result[1])
  }
  f _handle_request(raw:bytes) -> v {
    start_ns = time.perf_counter_ns() ->
    trace_id = "" ->
    try:
      envelope = json.loads(raw) -> req = FeatureRequest(envelope.payload) ->
      trace_id = req.trace_id ->
      transfer = runner.get_feature_vector(req.bns_id) ->
      buffer_ref = transfer.buffer.to_shm_ref() ->
      compute_time_ms = (time.perf_counter_ns() - start_ns) / 1_000_000 ->
// @Rule.P2_T_FVTF_ENVELOPE: CONTRACT.MessageEnvelope, CONTRACT.Payload;
// @Rule.P2_T_FVTF_META: CONTRACT.ComputeTime, CONTRACT.Latency;
      resp_envelope = MessageEnvelope(
        trace_id=trace_id, source:"feature_runner",
        content_type:ARROW, payload:None,  // ❗ CRITICAL: no binary in payload
        meta:{buffer_ref,schema_id:transfer.feature_schema_id,feature_count:len(transfer.order),compute_time_ms}
      ) ->
      redis.rpush(feature_response_topic(trace_id), resp_envelope.serialize())
    except Exception as e:
// @Rule.P2_T_FVTF_ERROR_HANDLERS: CONTRACT.FeatureResponse, CONTRACT.ErrorStatus;
      error_resp = FeatureResponse(trace_id,status:"ERROR",error_code:"COMPUTE_FAILED",error_message:str(e)) ->
      error_envelope = MessageEnvelope(trace_id,source:"feature_runner",content_type:JSON,payload:error_resp.to_dict()) ->
      trace_id ? redis.rpush(feature_response_topic(trace_id), error_envelope.serialize()) :
      log.ERROR("Feature request failed", error=str(e))
  }
}

// ═══════════════════════════════════════════════════════════════
// @DocMeta.P2_T_SEC5_FEATURE_STALE_DETECTION_BEHAVIOR_OD_FT_1: §5 Feature Stale Detection - Behavior (OD-FT-1)
// ═══════════════════════════════════════════════════════════════
// Design: Alpha Decay - information degrades over time
// Phase1: HARD_REJECT (stale->no trade), Phase2: LOGGING, Phase3: DYNAMIC
// @Rule.P2_T_FSDB_PHASE_TRANSITION: CONTRACT.StaleRate, CONTRACT.PhaseTransition;
// @Function.P2_T_FSDB_IS_FEATURE_STALE: Feature staleness predicate
f is_feature_stale(feature_ts:i, now_ts:i) -> b {
// @Rule.P2_T_FSDB_TIMESTAMPS: SSOT.LocalClock, SSOT.Timestamp;
  age_ms = (now_ts - feature_ts) / 1_000_000 ->
  ret age_ms > STALE_THRESHOLD_MS
}
// @Function.P2_T_FSDB_COMPUTE_DECAY_FACTOR: Compute volatility-based decay factor
f compute_decay_factor(age_ms:f, volatility:f) -> f {
  // Phase3: Higher volatility -> faster decay
  half_life_ms = 50 / max(volatility, 0.1) ->
  ret exp(-0.693 * age_ms / half_life_ms)
}

// @Structure.P2_T_FSDB_FEATURE_STALE_DETECTOR_CLASS: Feature staleness detection and policy modes
C FeatureStaleDetector(mode:StaleMode=HARD_REJECT) {
  _stale_count: i, _total_count: i
  f check(feature_ts:i, now_ts:i, volatility:f=0.0) -> b {
    // ret T = proceed, F = reject trade
    _total_count++ ->
    age_ms = (now_ts - feature_ts) / 1_000_000 ->  // Define age_ms for all branches
    !is_feature_stale(feature_ts,now_ts) ? ret T :
    _stale_count++ ->
    mode == HARD_REJECT ? (log.WARN("stale-rejected",age_ms=age_ms,threshold=STALE_THRESHOLD_MS) -> ret F) :
    mode == LOGGING ? (log.INFO("stale-logged",age_ms=age_ms) -> ret T) :
    // DYNAMIC: use age_ms with volatility-based decay
    decay = compute_decay_factor(age_ms,volatility) ->
    decay < 0.5 ? (log.WARN("stale-dynamic-rejected",age_ms=age_ms,decay=decay,volatility=volatility) -> ret F) : ret T
  }
  f stale_rate() -> f { ret _total_count > 0 ? _stale_count/_total_count : 0.0 }
}

// ═══════════════════════════════════════════════════════════════
// @DocMeta.P2_T_SEC6_BACKPRESSURE_POLICY_BEHAVIOR_OD_BP_1: §6 Backpressure Policy - Behavior (OD-BP-1)
// ═══════════════════════════════════════════════════════════════
// @Structure.P2_T_BPPB_BACKPRESSURE_POLICY_CLASS: Queue-based backpressure policy and dropping behavior
C BackpressurePolicy(max_queue_size:i=1000) {
  _queue: deque(maxlen=max_queue_size), _dropped_count: i
  f enqueue(msg:bytes) -> b {
    len(msg) > MAX_MESSAGE_SIZE ? (log.ERROR("msg>1MB rejected") -> ret F) :
    fill_ratio = len(_queue) / max_queue_size ->
    fill_ratio > CRITICAL_THRESHOLD ? log.CRITICAL("queue critical") :
    fill_ratio > WARNING_THRESHOLD ? log.WARN("queue warning") :
// @Rule.P2_T_BPPB_DROP_OLDEST: CONTRACT.QueueBehavior, CONTRACT.DroppedCount;
    len(_queue) >= max_queue_size ? (
      _queue.popleft() ->  // DROP oldest
      _dropped_count++ ->
      log.ERROR("dropped oldest message", dropped_count=_dropped_count)
    ) :
    _queue.append(msg) -> ret T
  }
  f dequeue() -> bytes? { ret _queue.popleft() if _queue else None }
  f stats() -> d { ret {queue_size:len(_queue),max:max_queue_size,fill:len(_queue)/max_queue_size,dropped:_dropped_count} }
}

// ═══════════════════════════════════════════════════════════════
// @DocMeta.P2_T_SEC7_5_L2_HEARTBEAT_BEHAVIOR_P2_HB_1: §7.5 L2 Heartbeat - Behavior (P2-HB-1)
// ═══════════════════════════════════════════════════════════════
// @Rule.P2_T_HBB_DETECTION: CONTRACT.ProtectiveStop, CONTRACT.KillSwitch;
//
// @Structure.P2_T_HBB_NAUTILUS_HEARTBEAT_CLASS: L2 heartbeat emitter to Safety Redis
C NautilusHeartbeat(safety_redis:Redis) {
  _running: b, _task: Task?, _last_data_received_ns: i
  f start() -> v { _running = T -> _task = create_task(_heartbeat_loop()) }
  f stop() -> v { _running = F -> _task?.cancel() }
  f on_data_received() -> v { _last_data_received_ns = time.time_ns() }
  f _heartbeat_loop() -> v {
    while _running:
      try:
        ts_ns = _last_data_received_ns or time.time_ns() ->
        safety_redis.set(HEARTBEAT_KEY, str(ts_ns), ex=HEARTBEAT_TTL_SEC) ->
        sleep(HEARTBEAT_INTERVAL_MS / 1000)  // 500ms = 0.5s
      except RedisError as e:
// @Rule.P2_T_HBB_CRITICAL: CONTRACT.SafetyRedis, CONTRACT.LogSeverity;
        log.CRITICAL("Failed to send heartbeat to Safety Redis", error=str(e))
  }
}

// @Structure.P2_T_HBB_NAUTILUS_DRIVER_CLASS: Nautilus driver heartbeat integration hooks
C NautilusDriver(safety_redis:Redis, ..) {
  _heartbeat: NautilusHeartbeat
  f start() -> v { _heartbeat.start() -> /* existing */ }
  f stop() -> v { _heartbeat.stop() -> /* existing */ }
  f _on_quote_tick(tick:QuoteTick) -> v { _heartbeat.on_data_received() -> /* process */ }
  f _on_trade_tick(tick:TradeTick) -> v { _heartbeat.on_data_received() -> /* process */ }
}

// ═══════════════════════════════════════════════════════════════
// @DocMeta.P2_T_SEC8_PERFORMANCE_TARGETS: §8 Performance Targets
// ═══════════════════════════════════════════════════════════════
// | Metric                  | Target   | Measurement Method                    |
// | L2->L3 latency          | <100µs   | End-to-end feature fetch timing       |
// | Zero-copy efficiency    | 0 allocs | Memory profiling (tracemalloc/heapy)  |
// | Backpressure detection  | <1ms     | Queue check overhead measurement      |
//
// @Rule.P2_T_PERT_MEASURE_LATENCY: CONTRACT.PerformanceMetric, CONTRACT.ComputeTime;
// @Rule.P2_T_PERT_MEASURE_ALLOC: CONTRACT.MemoryMetric, CONTRACT.AllocationMetric;
// @Rule.P2_T_PERT_MEASURE_BP: CONTRACT.QueueMetric, CONTRACT.BackpressureMetric;

// ═══════════════════════════════════════════════════════════════
// @DocMeta.P2_T_SEC9_IMPLEMENTATION_TASKS: §9 Implementation Tasks
// ═══════════════════════════════════════════════════════════════
// @Task.P2_T_IMPT_ZC_1: ZeroCopyBuffer class -> shared/zero_copy/protocol.py
// @Task.P2_T_IMPT_ZC_2: Arrow IPC serialization -> shared/zero_copy/protocol.py
// @Task.P2_T_IMPT_ZC_3: Buffer validation (dtype,endian,contiguous)
// @Task.P2_T_IMPT_FT_1: FeatureVectorTransfer dataclass
// @Task.P2_T_IMPT_FT_2: FeatureRunner.get_feature_vector()
// @Task.P2_T_IMPT_FT_3: FeatureFetcher class
// @Task.P2_T_IMPT_FT_4: Schema validation integration
// @Task.P2_T_IMPT_BP_1: BackpressurePolicy class
// @Task.P2_T_IMPT_BP_2: Integration with FeatureRunner
// @Task.P2_T_IMPT_HB_1: NautilusHeartbeat class
// @Task.P2_T_IMPT_HB_2: NautilusDriver integration
// @Task.P2_T_IMPT_HB_3: Unit tests -> tests/unit/test_nautilus_heartbeat.py
// @Task.P2_T_IMPT_TEST: Unit tests

// File Structure:
// myplugins/shared/zero_copy/{__init__.py,protocol.py,lifecycle.py,manager.py,consumer.py,retry_config.py,fallback.py,exceptions.py}
// myplugins/shared/backpressure/{__init__.py,policy.py,conflation.py,manager.py}
// myplugins/feature_pipeline/online/{__init__.py,feature_transfer.py,runner.py,stale_detection.py}
// myplugins/model_pipeline/inference/{__init__.py,feature_fetcher.py,actor.py}
// myplugins/data/nautilus/{__init__.py,heartbeat.py,driver.py}
// myplugins/shared/messaging/{__init__.py,envelope.py,feature_transport.py}

// ═══════════════════════════════════════════════════════════════
// @DocMeta.P2_T_SEC10_SUCCESS_CRITERIA: §10 Success Criteria
// ═══════════════════════════════════════════════════════════════
// [ ] ZeroCopyBuffer Arrow IPC operational
// [ ] dtype/endianness/contiguous validation functional
// [ ] FeatureVectorTransfer Pull pattern operational
// [ ] feature_schema_id validation pass/reject accurate
// [ ] Backpressure 5%/10%/full logging correct
// [ ] L2->L3 latency <100µs
// [ ] All unit tests passing (tests/unit/test_zero_copy/)
```
