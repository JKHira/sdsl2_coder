```typescript
// P3: Schema Validation SDSL - TOPOLOGY / FLOW
// @DocMeta.P3_T_SPEC: BNS_Validation_Spec Part1-3
// @DocMeta.P3_T_SPLIT: Flows, state transitions, runtime behavior, implementation tasks

// ═══════════════════════════════════════════════════════════════
// @DocMeta.P3_T_SEC2_FEATURE_SCHEMA_ID_SYSTEM_PROCESSING_FLOW: §2 . FEATURE SCHEMA ID SYSTEM - PROCESSING FLOW
// ═══════════════════════════════════════════════════════════════
// @Function.P3_T_FSID_NORMALIZE_FLOATS: Deterministic float normalization for schema hashing
f normalize_floats(obj:any, prec:i=9) -> any {
// @Rule.P3_T_FSID_BNS_SEC5_1_N: SSOT.TypeError;
// @Rule.P3_T_FSID_BNS_SEC5_1_ROUNDING: SSOT.ROUND_HALF_UP;
  obj instanceof PROHIBITED_TYPES ? throw TypeError("Prohibited type") :
  obj:f ? (isnan(obj)|isinf(obj) ? throw TypeError("NaN/Inf") :
    Context(prec=prec, rounding=ROUND_HALF_UP).create_decimal(str(obj)) -> format("{:.{prec}g}")) :
  obj:d ? {k:normalize_floats(v,prec) for k,v in obj} :
  obj:list ? [normalize_floats(i,prec) for i in obj] :
  obj:(s|i|b|None) ? obj : throw TypeError("Unsupported type")
}

// @Function.P3_T_FSID_COMPUTE_FEATURE_SCHEMA_ID: Compute feature_schema_id from normalized HashInputSchema
f compute_feature_schema_id(bns:d) -> s {
// @Rule.P3_T_FSID_HASH_SORT_NORMALIZE_SHA256: @Function.P3_T_FSID_NORMALIZE_FLOATS, SSOT.SHA256;
  data = deepcopy(bns) -> sort(data.nodes, key=node_id) -> normalize_floats(data) ->
  json.dumps(data, sort_keys=T, sep=(',',':')) -> sha256(enc('utf-8')) ->
  ret "sha256:{hex}"
}
// @Function.P3_T_FSID_VALIDATE_HASH_INPUT: Validate HashInputSchema required keys and SemVer constraints
f validate_hash_input(bns:d) -> v {
// @Rule.P3_T_FSID_REQUIRED_KEYS: CONTRACT.HashInputSchema, SSOT.SemVer;
  missing(["bns_id","bns_version","bns_config","nodes"]) ? throw KeyError :
  !SEMVER_PATTERN.match(bns.bns_version) ? throw ValueError :
  missing(bns_config, ["format","dtype","order"]) ? throw KeyError :
// @Rule.P3_T_FSID_NODE_VALIDATION: @Function.P3_T_FSID_VALIDATE_HASH_INPUT;
  for i, node in enumerate(bns.nodes):
    missing(node, ["node_id","feature_def","feature_version","node_version","params"]) ?
      throw KeyError("Missing key in nodes[{i}]") :
// @Rule.P3_T_FSID_VERSION_SEMVER_SEPARATE: SSOT.SemVer;
    !SEMVER_PATTERN.match(node.feature_version) ?
      throw ValueError("Invalid feature_version '{node.feature_version}' in nodes[{i}]: must be SemVer") :
    !SEMVER_PATTERN.match(node.node_version) ?
      throw ValueError("Invalid node_version '{node.node_version}' in nodes[{i}]: must be SemVer")
}

// @Function.P3_T_FSID_COMPUTE_FEATURE_SCHEMA_ID_SAFE: Validate input then compute feature_schema_id
f compute_feature_schema_id_safe(bns:d) -> s {
  validate_hash_input(bns) -> ret compute_feature_schema_id(bns)
}

// ═══════════════════════════════════════════════════════════════
// @DocMeta.P3_T_SEC3_VERSION_RESOLVER_RESOLUTION_FLOW: §3 . VERSION RESOLVER - RESOLUTION FLOW
// ═══════════════════════════════════════════════════════════════

// @Function.P3_T_VRRF_PARSE_VERSIONED_REFERENCE: Parse `name@version` reference into structured form
f VersionedReference.parse(ref:s) -> VersionedReference {
  "@" in ref ? (parts=ref.split("@",1) -> {name:parts[0],version:parts[1]}) : {name:ref,version:None}
}
// @Structure.P3_T_RV_RESOLUTION_ERROR: Resolver error type for missing/invalid YAML references
C ResolutionError(Exception) {}

// @Structure.P3_T_VRRF_VERSION_RESOLVER: Resolve BNS/Node/Feature YAMLs into HashInputSchema-compatible dict
C VersionResolver(features_dir:Path, nodes_dir:Path, bns_dir:Path) {
// @Function.P3_T_VRRF_RESOLVE_BNS: Resolve BNS YAML to HashInputSchema-compatible dict by resolving node references
  f resolve_bns(bns_id:s) -> d {
// @Rule.P3_T_VRRF_OUTPUT: CONTRACT.HashInputSchema;
    bns_path = bns_dir / "{bns_id}.yaml" ->
    !exists(bns_path) ? throw ResolutionError("BNS '{bns_id}' not found") :
    bns_data = yaml.safe_load(bns_path) ->
    resolved_nodes = [] ->
// @Rule.P3_T_VRRF_NODE_REF: CONTRACT.NodeReference;
    for node_ref in bns_data.nodes:
      node_ref:s ? (node_id=node_ref, bns_params={}) :
        (node_id=node_ref.node_id, bns_params=node_ref.params|{}) ->
      resolved_nodes.append(_resolve_node(node_id, bns_params)) ->
    feature_vector = bns_data.feature_vector | {} ->
    ret {
      bns_id: bns_data.bns_id,
      bns_version: bns_data.version | "1.0.0",
      bns_config: {
        format: feature_vector.format | "numpy",
        dtype: feature_vector.dtype | "float64",
        order: feature_vector.order | []
      },
      nodes: resolved_nodes
    }
  }
// @Function.P3_T_VRRF_RESOLVE_NODE: Resolve Node YAML and merge defaults with BNS overrides to produce resolved node entry
  f _resolve_node(node_id:s, bns_params:d) -> d {
// @Rule.P3_T_VRRF_MERGE: @Function.P3_T_VRRF_RESOLVE_NODE;
    node_path = nodes_dir / "{node_id}.yaml" ->
    !exists(node_path) ? throw ResolutionError("Node '{node_id}' not found") :
    node_data = yaml.safe_load(node_path) ->
    feature_ref = VersionedReference.parse(node_data.feature_def | "") ->
    feature_version = feature_ref.version ? feature_ref.version : _get_feature_version(feature_ref.name) ->
    merged_params = {**node_data.params|{}, **bns_params} ->
    ret {
      node_id: node_id,
      feature_def: feature_ref.name,
      feature_version: feature_version,
      node_version: node_data.version | "1.0.0",
      params: merged_params
    }
  }
// @Function.P3_T_VRRF_GET_FEATURE_VERSION: Get Feature version from feature YAML (fallback version resolution)
  f _get_feature_version(feature_name:s) -> s {
    feature_path = features_dir / "{feature_name}.yaml" ->
    !exists(feature_path) ? throw ResolutionError("Feature '{feature_name}' not found") :
    yaml.safe_load(feature_path).version | "1.0.0"
  }
}

// ═══════════════════════════════════════════════════════════════
// @DocMeta.P3_T_SEC4_2_STARTUP_VALIDATION_FLOW: §4.2 STARTUP VALIDATION FLOW
// ═══════════════════════════════════════════════════════════════

// @Rule.P3_T_SUVF_STARTUP_VALIDATION: @Function.P3_T_SUVF_VALIDATE_MASTER_TABLE_STARTUP;
// @Flow.P3_T_SUVF_MT_STARTUP_VALIDATION_FLOW: Master table startup validation sequence (load->integrity->phase checks->report)
// @Function.P3_T_SUVF_VALIDATE_MASTER_TABLE_STARTUP: Execute sequential 4-step startup validation for MasterTable
f validate_master_table_startup(table:MasterTableSchema, resolver:VersionResolver) -> ValidationReport {
  // Step 1: Load model_master_table.yaml
  // Step 2: Verify config_hash (integrity)
  computed_hash = compute_config_hash(table) ->
  computed_hash != table.metadata.config_hash ? throw ConfigHashMismatch("Integrity check failed") :
  // Step 3: For each phase validate
  errors = [] ->
  for phase_name, phase_config in table.phases:
    // 3a: Check bns_id in allowed_bns
    // 3b: Check bns_version >= min_version
    for bns_entry in phase_config.allowed_bns:
      resolved_bns = resolver.resolve_bns(bns_entry.bns_id) ->
      !semver_gte(resolved_bns.bns_version, bns_entry.min_version) ?
        errors.append({phase:phase_name, error:"BNS version < min_version", bns_id:bns_entry.bns_id}) :
      // 3c: Compute feature_schema_id
      schema_id = compute_feature_schema_id_safe(resolved_bns) ->
      // 3d: Check feature_schema_id in allowed_feature_schema_ids
      schema_id not in phase_config.allowed_feature_schema_ids ?
        errors.append({phase:phase_name, error:"feature_schema_id not allowed", id:schema_id}) :
      // 3e: Check model_id in allowed_models
      // 3f: Check model_version >= min_version
      for model_entry in phase_config.allowed_models:
        model = load_model(model_entry.model_id) ->
        !semver_gte(model.version, model_entry.min_version) ?
          errors.append({phase:phase_name, error:"Model version < min_version", model_id:model_entry.model_id}) ->
  // Step 4: Report validation result
  ret {valid: len(errors)==0, errors: errors}
}

// ═══════════════════════════════════════════════════════════════
// @DocMeta.P3_T_SEC5_MASTER_TABLE_RELOAD_OD_MT_1_FLOW_STATE: §5 . MASTER TABLE RELOAD (OD-MT-1) - FLOW & STATE
// ═══════════════════════════════════════════════════════════════

// @Rule.P3_T_MTR_OD_MT_1: @Rule.P3_T_MTR_STAGE_CRITERIA;
// @Rule.P3_T_MTR_DESIGN: SSOT.KISS;
// @Rule.P3_T_MTR_PROGRESSION: @Rule.P3_T_MTR_STAGE_GATE;
//
// @Rule.P3_T_MTR_STAGE_CRITERIA: CONTRACT.ReloadStage;
// | Stage | Mode           | Behavior                          | Transition Criteria                          |
// | 1     | cold_restart   | Process restart reloads YAML      | Initial state (default)                      |
// | 2     | manual_api     | Admin API triggers manual reload  | GATE: cold_restart運用確立後 (ops verified)    |
// | 3     | observer_only  | File change detection, notify only| GATE: manual_api安定運用後 (stable ops proven) |
// | 4     | notify_only    | Detection + notify, manual approve| GATE: observer安定後 (observer reliability ok) |
// | 5     | apply          | Full auto (requires rollback)     | GATE: 十分な信頼性確保後 (sufficient trust)     |
//
// @Rule.P3_T_MTR_STAGE_GATE: CONTRACT.ReloadStage;
// @Rule.P3_T_MTR_STAGE_NO_AUTO: CONTRACT.ReloadStage;



// @Rule.P3_T_MTR_SWAP_ROLLBACK_ON_FAILURE: @Function.P3_T_MTR_ROLLBACK;
// @Structure.P3_T_MTR_ATOMIC_MASTER_TABLE_SWAP: Active/standby pointer-swap with canary + rollback
C AtomicMasterTableSwap() {
  active:MasterTable?, standby:MasterTable?
// @Function.P3_T_MTR_SWAP: Perform canary test then atomically pointer-swap active/standby MasterTable
  async f swap(new_table:MasterTable) -> b {
// @Rule.P3_T_MTR_SWAP_CANARY_BEFORE_SWAP: @Function.P3_T_MTR_CANARY_TEST;
    !await _canary_test(new_table) ? (log.err("Canary failed", new_hash=new_table.config_hash) -> ret F) :
    standby = active ->
    active = new_table -> // Atomic assignment in Python
    log.info("Swapped", new_hash=new_table.config_hash, prev_hash=standby?.config_hash) ->
    ret T
  }
// @Function.P3_T_MTR_ROLLBACK: Roll back to standby MasterTable via atomic pointer-swap
  async f rollback() -> b {
    standby == None ? (log.err("No standby for rollback") -> ret F) :
    active = standby -> standby = None ->
    log.info("Rollback", restored_hash=active.config_hash) -> ret T
  }
// @Function.P3_T_MTR_CANARY_TEST: Run minimum canary checks before activating new MasterTable
  async f _canary_test(table:MasterTable) -> b {
// @Rule.P3_T_MTR_CANARY_CHECKS: CONTRACT.MasterTableSchema;
    // Tests: Schema validation (Pydantic), Critical field presence, Hash integrity
    try:
      // 1. Schema validation (Pydantic)
      MasterTableSchema(**table.data) ->
      // 2. Critical field presence
      !table.data.metadata ? ret F :
      !table.data.phases ? ret F :
      // 3. Hash integrity (format check)
      !table.config_hash.startswith("sha256:") ? ret F :
      !table.data ? ret F :
      // Add more canary tests as needed (per original comment)
      ret T
    except Exception as e:
      log.exception("Canary test exception", error=str(e)) -> ret F
  }
}

// @Structure.P3_T_MTR_MASTER_TABLE_LOADER: Loads/validates MasterTable and manages reload via Redis pubsub (degraded-capable)
C MasterTableLoader(table_path:Path, redis:Redis?=None) {
// @Rule.P3_T_MTR_REDIS_SEC5_2_SSOT: SSOT.get_main_redis;
// @Rule.P3_T_MTR_REDIS_SEC5_2_ARG_REMOVED: SSOT.get_main_redis;
// @Rule.P3_T_MTR_REDIS_SEC5_2_DEGRADED: CONTRACT.DegradedMode;
  //
// @Rule.P3_T_MTR_REDIS_RESILIENCE_BEHAVIOR: CONTRACT.DegradedMode;
  // | Operation        | Redis Available  | Redis Unavailable (Degraded Mode)           |
  // | load()           | Normal operation | Normal operation (file-based, no Redis req) |
  // | start_subscriber | Subscribe to ch  | Log WARN, skip subscription, continue       |
  // | trigger_reload   | Publish event    | Log WARN, skip broadcast, continue          |
  // | table property   | Normal operation | Normal operation (local atomic swap only)   |
  // | rollback()       | Normal operation | Normal operation (local atomic swap only)   |
  //
// @Rule.P3_T_MTR_DEGRADED_PRINCIPLE: CONTRACT.DegradedMode;
  _atomic_swap:AtomicMasterTableSwap, _pubsub:PubSub?
// @Rule.P3_T_MTR_INIT_REDIS: SSOT.get_main_redis;
  redis:Redis

  f __init__(table_path:Path, redis:Redis?=None) {
    self.table_path = table_path ->
// @Rule.P3_T_MTR_REDIS_BACKWARD_COMPAT: SSOT.get_main_redis;
    self.redis = redis if redis is not None else get_main_redis() ->
    self._atomic_swap = AtomicMasterTableSwap()
  }
// @Function.P3_T_MTR_LOAD: Load and validate MasterTable YAML then activate via AtomicMasterTableSwap
  async f load() -> MasterTableSchema {
// @Rule.P3_T_MTR_LOAD_USES_ATOMIC_SWAP: @Structure.P3_T_MTR_ATOMIC_MASTER_TABLE_SWAP;
    data = yaml.safe_load(table_path) ->
    schema = MasterTableSchema(**data) -> // Pydantic validation
    new_table = MasterTable(
      config_hash=schema.metadata.config_hash,
      data=data,
      loaded_at=time_ns()
    ) ->
    !await _atomic_swap.swap(new_table) ? throw RuntimeError("Canary test failed") :
    log.info("Loaded via AtomicSwap", config_hash=schema.metadata.config_hash) ->
    r
// @Function.P3_T_MTR_START_SUBSCRIBER: Subscribe to reload channel and reload table on events (degraded-capable)
  async f start_subscriber(phase_name:s?=None) {
// @Rule.P3_T_MTR_DEGRADED_SKIPPING: CONTRACT.DegradedMode;
    try:
      _pubsub = redis.pubsub() -> await _pubsub.subscribe(RELOAD_CHANNEL) ->
      log.info("Subscribed to reload channel") ->
      async for msg in _pubsub.listen():
        msg.type == "message" ? (
          log.info("Reload triggered") ->
          await load() ->
// @Rule.P3_T_MTR_STEP6: @Function.P3_T_MTR_VALIDATE_PHASE_POST_RELOAD;
          phase_name != None ? await _validate_phase_post_reload(phase_name)
        )
    except RedisConnectionError as e:
      log.warn("Redis unavailable - running in degraded mode (no pub/sub)", error=str(e))
  }
// @Function.P3_T_MTR_VALIDATE_PHASE_POST_RELOAD: Validate phase exists after reload; raise on missing phase
  async f _validate_phase_post_reload(phase_name:s) {
// @Rule.P3_T_MTR_STEP6_SUBSCRIBER_PHASE_VALIDATION: @Function.P3_T_MTR_VALIDATE_PHASE_POST_RELOAD;
    phase_config = self.table.data.get("phases", {}).get(phase_name) ->
    !phase_config ?
      (log.err("Phase not found after reload - rollback recommended", phase=phase_name) ->
       throw PhaseValidationError("Phase '{phase_name}' missing after reload")) :
    log.info("Post-reload phase validation passed", phase=phase_name)
  }
// @Function.P3_T_MTR_TRIGGER_RELOAD: Publish reload event to Redis (warn and continue in degraded mode)
  async f trigger_reload() {
// @Rule.P3_T_MTR_DEGRADED_LOGGING: CONTRACT.DegradedMode;
    try:
      await redis.publish(RELOAD_CHANNEL, "reload") ->
      log.info("Reload broadcast sent")
    except RedisConnectionError as e:
      log.warn("Redis unavailable - reload broadcast skipped", error=str(e))
  }
// @Function.P3_T_MTR_TABLE_GETTER: Return active MasterTable from AtomicMasterTableSwap (raises if not loaded)
  @property f table() -> MasterTable {
// @Rule.P3_T_MTR_ACCESS_SEC5_2: @Structure.P3_T_MTR_ATOMIC_MASTER_TABLE_SWAP;
    // Access validated data via: loader.table.data (raw dict) or re-validate with MasterTableSchema
    _atomic_swap.active == None ? throw RuntimeError("Master Table not loaded") : _atomic_swap.active
  }
// @Function.P3_T_MTR_LOADER_ROLLBACK: Invoke AtomicMasterTableSwap rollback for the loader
  async f rollback() -> b { ret await _atomic_swap.rollback() }
}

// @DocMeta.P3_T_MTR_SEC5_3_RELOAD_MECHANISM_SEQUENCE_STAGE_2: §5.3 RELOAD MECHANISM SEQUENCE (Stage 2+)
// @Rule.P3_T_MTR_RELOAD_SEQUENCE: @Function.P3_T_MTR_ADMIN_RELOAD_HANDLER, @Function.P3_T_MTR_START_SUBSCRIBER;

// @Rule.P3_T_MTR_STEP6_VALIDATION_EXPLAINED: @Function.P3_T_MTR_VALIDATE_PHASE_POST_RELOAD;

// @Flow.P3_T_MTR_ADMIN_RELOAD_FLOW: Admin API reload sequence (validate->integrity->publish)
// @Function.P3_T_MTR_ADMIN_RELOAD_HANDLER: Admin reload handler implementation for master-table reload (validate->integrity->publish)
f admin_reload_handler(table_path:Path, redis:Redis) -> ReloadResult {
  // Step 1: Called by POST /admin/master-table/reload
  // Step 2: Validate new YAML with Pydantic
  data = yaml.safe_load(table_path) ->
  try:
    schema = MasterTableSchema(**data)
  except ValidationError as e:
    ret {success:F, error:"Schema validation failed", details:str(e)} ->
  // Step 3: Compute new config_hash and verify integrity
  new_hash = compute_config_hash(data) ->
// @Rule.P3_T_MTR_INTEGRITY: CONTRACT.MasterTableMetadata;
  data.metadata.config_hash != new_hash ?
    (log.err("config_hash mismatch - REJECT", stored=data.metadata.config_hash, computed=new_hash) ->
     ret {success:F, error:"config_hash mismatch", stored:data.metadata.config_hash, computed:new_hash}) :
  // Step 4: Publish reload event
  await redis.publish(RELOAD_CHANNEL, "reload") ->
  ret {success:T, config_hash:new_hash}
}

// ═══════════════════════════════════════════════════════════════
// @DocMeta.P3_T_SEC6_VALIDATION_ERROR_BEHAVIOR_P3_01_02_ERROR_FLOW: §6 . VALIDATION ERROR BEHAVIOR (P3-01/02) - ERROR FLOW
// ═══════════════════════════════════════════════════════════════

// @Rule.P3_T_VEB_ERROR_MATRIX_01_02: CONTRACT.ValidationMode;
// @Rule.P3_T_VEB_DESIGN: "Detect problems at startup, prioritize continuity at runtime";
//
// @Rule.P3_T_VEB_CONFLICT_RESOLUTION (§6.1 vs §8.2):
// - §6.1 originally specified: Runtime feature_schema_id mismatch = "WARN + SKIP"
// - §8.2 updated (2025-12-09): Runtime = "DEGRADED + WARN" with data SKIP
// - RESOLVED: §8.2 supersedes §6.1; unified behavior = DEGRADED state transition + WARN log + data SKIP
// - Rationale: State transition makes mismatch visible for monitoring while preserving continuity
//
// | Error                      | Startup | Runtime           | Action              |
// | feature_schema_id mismatch | CRASH   | DEGRADED+WARN+SKIP| State + Log + Skip  |
// | BNS version < min_version  | CRASH   | CRASH             | Fatal error         |
// | Model version < min_version| CRASH   | CRASH             | Fatal error         |
// | config_hash mismatch       | CRASH   | CRASH             | Fatal error         |
// | Using deprecated hash      | CRASH   | WARN              | Allow with warning  |
// | DB sync failure            | CRASH   | CRASH             | Fatal error         |

// @Function.P3_T_VEB_ERRF_VALIDATE_FEATURE_SCHEMA_ID: Validate received feature_schema_id against expected list with mode-dependent behavior (strict/inference)
f validate_feature_schema_id(recv:s, expected:list[s], mode:s="inference") -> ValidationResult {
// @Rule.P3_T_VEB_ERROR_MATRIX_01_02_MODE_APPLICATION: CONTRACT.ValidationMode;
  recv in expected ? ret {valid:T} :
  mode == "strict" ? // Startup mode
    (log.err("STRICT mismatch", received=recv, expected=expected) ->
     throw ValueError("SCHEMA.HASH.MISMATCH: {recv}")) :
  // Runtime (inference) mode: DEGRADED state transition + data SKIP + WARN
// @Rule.P3_T_VEB_RUNTIME: CONTRACT.DegradedMode;
  log.warn("Schema mismatch - DEGRADED + SKIP",
    received=recv, expected=expected, error_code="SCHEMA.HASH.MISMATCH") ->
  ret {
    valid: F,
    skip_reason: "schema_id_mismatch",
    error_code: "SCHEMA.HASH.MISMATCH",
// @Rule.P3_T_VEB_STATE_FEATURE_SCHEMA_ID_MISMATCH: Visible state transition for monitoring
    state_transition: "DEGRADED"
  }
}

// ═══════════════════════════════════════════════════════════════
// @DocMeta.P3_T_SEC7_AUTHORIZATION_CHECK_P3_03_07_AUTHORIZATION_FLOW: §7 . AUTHORIZATION CHECK (P3-03~07) - AUTHORIZATION FLOW
// ═══════════════════════════════════════════════════════════════

// @Rule.P3_T_AUTHC_OPERATION_REQUIRED: CONTRACT.AuthorizationResult;
// @Rule.P3_T_AUTHC_TIMING: @Function.P3_T_AUTHC_CHECK_AUTHORIZATION;
// @Structure.P3_T_AUTHC_AZ_SCHEMA_AUTHORIZER: Pre-inference authorization for feature_schema_id by phase with TTL cache
C SchemaAuthorizer(loader:MasterTableLoader) {
// @Rule.P3_T_AUTHC_AUTHORIZATION: CONTRACT.AuthorizationResult;
  _cache:d[s,tuple[AuthorizationResult,f]]
// @Rule.P3_T_AUTHC_ACCESS: @Structure.P3_T_MTR_ATOMIC_MASTER_TABLE_SWAP;
// @Function.P3_T_AUTHC_CHECK_AUTHORIZATION: Pre-inference authorization check for feature_schema_id by phase with TTL cache
  f check_authorization(feature_schema_id:s, phase:s) -> AuthorizationResult {
// @Rule.P3_T_AUTHC_PRE_INFERENCE: @Function.P3_T_AUTHC_CHECK_AUTHORIZATION;
    cache_key = "{phase}:{feature_schema_id}" ->
// @Rule.P3_T_AUTHC_CACHE_TTL: SSOT.AUTHORIZATION_CACHE_TTL_SECONDS;
    cache_key in _cache & (time() - _cache[cache_key][1] < AUTHORIZATION_CACHE_TTL_SECONDS) ?
      ret _cache[cache_key][0] :
// @Rule.P3_T_AUTHC_ACCESS_MASTER_TABLE: CONTRACT.MasterTableSchema;
    phase_config = loader.table.data["phases"].get(phase) ->
    !phase_config ?
      ret {authorized:F, reason:"Unknown phase: {phase}", error_code:"SCHEMA.PHASE.UNKNOWN"} :
    // Check allowed list
    feature_schema_id in phase_config["allowed_feature_schema_ids"] ?
      (result = {authorized:T} -> _cache[cache_key] = (result, time()) -> ret result) :
// @Rule.P3_T_AUTHC_DEPRECATED_CHECK: SSOT.GRACE_PERIOD_SECONDS;
    deprecated_entry = _find_deprecated(feature_schema_id) ->
    deprecated_entry ?
      (grace_ns = int((time() + GRACE_PERIOD_SECONDS) * 1e9) ->
       log.warn("Deprecated schema (grace active)",
         schema_id=feature_schema_id,
         deprecated_since=deprecated_entry["deprecated_since"],
         grace_expires_at=grace_ns) ->
       result = {authorized:T, deprecated:T, grace_expires_at:grace_ns} ->
       _cache[cache_key] = (result, time()) -> ret result) :
    // Not authorized
    log.err("Schema not authorized",
      schema_id=feature_schema_id, phase=phase, error_code="SCHEMA.HASH.MISMATCH") ->
    ret {authorized:F, reason:"Not in allowed list", error_code:"SCHEMA.HASH.MISMATCH"}
  }
// @Function.P3_T_AUTHC_FIND_DEPRECATED: Find schema_id entry in deprecated_schema_ids list
  f _find_deprecated(schema_id:s) -> DeprecatedSchemaEntry? {
// @Rule.P3_T_AUTHC_FIND_DEPRECATED_SCHEMA_IDS: CONTRACT.MasterTableSchema;
    for entry in loader.table.data.get("deprecated_schema_ids", []):
      entry["id"] == schema_id ? ret entry ->
    ret None
  }
// @Function.P3_T_AUTHC_INVALIDATE_CACHE: Clear authorization cache on Master Table reload
  f invalidate_cache() {
// @Rule.P3_T_AUTHC_INVALIDATE_CACHE: @Function.P3_T_AUTHC_INVALIDATE_CACHE;
    _cache.clear() -> log.info("Authorization cache invalidated")
  }
}

// ═══════════════════════════════════════════════════════════════
// @DocMeta.P3_T_SEC8_VALIDATION_MODES_P3_21_MODE_BEHAVIOR: §8 . VALIDATION MODES (P3-21) - MODE BEHAVIOR
// ═══════════════════════════════════════════════════════════════

// @Rule.P3_T_VALM_MODEL_DEFINITIONS: CONTRACT.ValidationMode;
// @Rule.P3_T_VALM_DESIGN: SSOT.ContinuityPrinciple;
// | Mode      | Context                    | Behavior                              |
// | strict    | CI/CD, Deploy, Startup     | CRASH on any mismatch                 |
// | inference | Production Runtime         | CRASH on critical, DEGRADED+WARN on deprec |
// | test      | Local Dev, Unit Tests      | WARN on most, allows no-DB operation  |

// @Rule.P3_T_VALM_SCOPE: CONTRACT.ValidationMode;
// | Check                      | strict | inference        | test |
// | feature_schema_id mismatch | CRASH  | DEGRADED+WARN+SKIP| WARN |
// | BNS version < min_version  | CRASH  | CRASH            | WARN |
// | Model version < min_version| CRASH  | CRASH            | WARN |
// | config_hash mismatch       | CRASH  | CRASH            | WARN |
// | DB sync failure            | CRASH  | CRASH            | WARN |
// | Using deprecated hash      | CRASH  | WARN             | SKIP |

// @Rule.P3_T_VALM_RUNTIME_DETAIL: CONTRACT.DegradedMode;
// 1. Transition to DEGRADED state (visible for monitoring)
// 2. Skip data (discard, don't process)
// 3. Log WARN
// 4. Continue processing (don't crash)

// ═══════════════════════════════════════════════════════════════
// @DocMeta.P3_T_SEC9_10_IMPLEMENTATION_TASKS_FILE_STRUCTURE: §9 -10. IMPLEMENTATION TASKS & FILE STRUCTURE
// ═══════════════════════════════════════════════════════════════

// @Rule.P3_T_ITFS_TASKS: CONTRACT.ImplementationTask;
// | Task ID  | Description                              | Depends On       | Output                                    |
// | P3-HS-1  | normalize_floats() function              | -                | shared/hashing.py                         |
// | P3-HS-2  | compute_feature_schema_id()              | P3-HS-1          | shared/hashing.py                         |
// | P3-HS-3  | validate_hash_input() (BNS §5.1)         | -                | shared/hashing.py                         |
// | P3-HS-4  | compute_feature_schema_id_safe() wrapper | P3-HS-2, P3-HS-3 | shared/hashing.py                         |
// | P3-HS-5  | Hash computation tests (incl prohibited) | P3-HS-4          | tests/unit/test_hashing.py                |
// | P3-RV-1  | VersionedReference class                 | -                | feature_pipeline/bns/resolver.py          |
// | P3-RV-2  | VersionResolver class                    | P3-RV-1          | feature_pipeline/bns/resolver.py          |
// | P3-RV-3  | Resolution error handling                | P3-RV-2          | feature_pipeline/bns/resolver.py          |
// | P3-MT-1  | Pydantic models for Master Table         | -                | model_pipeline/registry/master_table.py   |
// | P3-MT-2  | Master Table loader                      | P3-MT-1          | model_pipeline/registry/loader.py         |
// | P3-MT-3  | config_hash computation                  | P3-HS-2          | model_pipeline/registry/integrity.py      |
// | P3-VL-1  | Validation mode config                   | -                | model_pipeline/config/validation.py       |
// | P3-VL-2  | Startup validator                        | P3-MT-2, P3-RV-2 | model_pipeline/inference/validator.py     |
// | P3-VL-3  | Deprecation checker                      | P3-MT-1          | model_pipeline/registry/deprecation.py    |
// | P3-SC-1  | compute_feature_schema_id.py script      | P3-HS-2          | scripts/compute_feature_schema_id.py      |
// | P3-SC-2  | validate_master_table.py script          | P3-VL-2          | scripts/validate_master_table.py          |
// | P3-SC-3  | sync_master_table.py script              | P3-MT-2          | scripts/sync_master_table.py              |
// | P3-RL-1  | MasterTableLoader with pub/sub           | P3-MT-2          | model_pipeline/registry/loader.py         |
// | P3-RL-2  | Admin API reload endpoint                | P3-RL-1          | admin/api/master_table.py                 |
// | P3-TEST  | Unit tests                               | P3-*             | tests/unit/test_schema_validation/        |

// @Rule.P3_T_ITFS_FILES: SSOT.FileStructure;
// myplugins/shared/hashing.py <- normalize_floats, compute_feature_schema_id, validate_hash_input
// myplugins/feature_pipeline/bns/resolver.py <- VersionedReference, VersionResolver
// myplugins/model_pipeline/registry/master_table.py <- Pydantic models
// myplugins/model_pipeline/registry/loader.py <- MasterTableLoader, AtomicMasterTableSwap
// myplugins/model_pipeline/registry/integrity.py <- config_hash computation
// myplugins/model_pipeline/registry/deprecation.py <- Deprecation checker
// myplugins/model_pipeline/registry/authorization.py <- SchemaAuthorizer
// myplugins/model_pipeline/registry/atomic_swap.py <- AtomicMasterTableSwap
// myplugins/model_pipeline/config/validation.py <- Validation mode config
// myplugins/model_pipeline/inference/validator.py <- Startup validator
// scripts/compute_feature_schema_id.py
// scripts/validate_master_table.py
// scripts/sync_master_table.py
// admin/api/master_table.py <- Admin API reload endpoint

// ═══════════════════════════════════════════════════════════════
// @DocMeta.P3_T_SEC11_CI_INTEGRATION: §11 . CI INTEGRATION
// ═══════════════════════════════════════════════════════════════

// @Rule.P3_T_CII_GITHUB: CONTRACT.MasterTableMetadata;

// ═══════════════════════════════════════════════════════════════
// @DocMeta.P3_T_SEC12_SUCCESS_CRITERIA: §12 . SUCCESS CRITERIA
// ═══════════════════════════════════════════════════════════════

// @Rule.P3_T_SUCCESS_CRITERIA: CONTRACT.SuccessCriteria;
// - [ ] feature_schema_id deterministic (same input -> same output)
// - [ ] Version resolver Feature/Node/BNS correct resolution
// - [ ] MasterTableSchema Pydantic validation works
// - [ ] config_hash auto-compute & verify
// - [ ] Validation mode (strict/inference/test) switching correct
// - [ ] deprecated_schema_ids grace period (60s) functional
// - [ ] CI blocking validation active
// - [ ] Master Table reload via pub/sub notifies all components
// - [ ] BNS§5.1: Prohibited types (datetime/bytes) -> TypeError
// - [ ] BNS§5.1: Missing required keys -> KeyError
// - [ ] BNS§5.1: Invalid version format -> ValueError
// - [ ] OD-HS-1: NaN/Inf -> TypeError
// - [ ] All tests pass (P3-TEST complete)

// ═══════════════════════════════════════════════════════════════
// @DocMeta.P3_T_SEC13_IMPLEMENTATION_NOTES: §13 . IMPLEMENTATION NOTES
// ═══════════════════════════════════════════════════════════════

// @Rule.P3_T_IMP_NOTE_DEFERRED: SSOT.ImplementationBacklog;
// DEPRECATED RULE: R_DEFERRED_ITEMS (Category D deletion candidate)
// DO NOT USE for new design or implementation.
// Reason: This entry is an implementation backlog list, not a specification rule; manage these items in roadmap/backlog documents.
//If necessary, refer to the latest SSOT documents (Plugin_Architecture_Standards_Manual / SHARED_CONSTANTS).
```
