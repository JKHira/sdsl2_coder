export const SSOT_DEFINITIONS = {
  "meta": {
    "version": "0.1.0",
    "created": "2025-01-01",
    "last_updated": "2025-01-01",
    "status": "authoritative"
  },
  "kernel": {
    "token_rules": {
      "ssot_ref_pattern": "^SSOT\\.[A-Za-z0-9_.-]+$",
      "contract_ref_pattern": "^CONTRACT\\.[A-Za-z0-9_.-]+$",
      "internal_ref_pattern": "^@(?P<kind>[A-Za-z_][A-Za-z0-9_]*)\\.(?P<id>[A-Z][A-Z0-9_]{2,63})$"
    },
    "registry_schema": {
      "schema_version": "1.0",
      "required_fields": ["schema_version", "source_rev", "input_hash", "generator_id", "entries"],
      "entry_fields": ["token", "target"],
      "target_format": "<path>#/<json_pointer>",
      "unresolved_marker": "UNRESOLVED#/"
    },
    "distribution_boundary": {
      "definitions_path": "OUTPUT/ssot/ssot_definitions.json",
      "registry_map_path": "OUTPUT/ssot/ssot_registry_map.json",
      "registry_path": "OUTPUT/ssot/ssot_registry.json"
    },
    "required_artifacts": {
      "ssot_registry": {
        "path": "OUTPUT/ssot/ssot_registry.json",
        "schema_version": "1.0",
        "schema_ref": "ssot_kernel_builder/ssot_definitions.ts#kernel.registry_schema"
      },
      "decisions_edges": {
        "path": "decisions/edges.yaml",
        "schema_version": "1.0",
        "schema_ref": "sdsl2_manuals/ope_addendum/SDSL2_Decisions_Spec.md"
      },
      "decisions_contracts": {
        "path": "decisions/contracts.yaml",
        "schema_version": "1.0",
        "schema_ref": "sdsl2_manuals/ope_addendum/SDSL2_Decisions_Spec.md"
      },
      "evidence_map": {
        "path": "decisions/evidence.yaml",
        "schema_version": "1.0",
        "schema_ref": "sdsl2_manuals/ope_addendum/SDSL2_Decision_Evidence_Spec.md"
      },
      "topology_ledger": {
        "path": "drafts/ledger/topology_ledger.yaml",
        "schema_version": "topology-ledger-v0.1",
        "schema_ref": "coder_planning/ledger_format/topology_ledger_v0_1.md"
      }
    },
    "determinism": {
      "input_hash_spec": "sdsl2_manuals/ope_addendum/SDSL2_InputHash_Spec.md",
      "serialization_spec": "sdsl2_manuals/ope_addendum/SDSL2_ContextPack_BundleDoc_Spec.md"
    }
  },
  "tokens": {
    "SSOT.ACCEPTANCE_CRITERIA": {
      "kind": "ref",
      "summary": "Referenced by SDSL inputs"
    },
    "SSOT.ALERT_ACTIONS": {
      "kind": "table",
      "summary": "Allowed alert actions",
      "value": ["LOG_ONLY", "DASHBOARD", "SLACK", "PAGER", "NONE"]
    },
    "SSOT.ALERT_CRITERIA": {
      "kind": "rule",
      "summary": "Alert escalation criteria",
      "value": {
        "notify_min_level": "ERROR",
        "page_min_level": "CRITICAL"
      }
    },
    "SSOT.API_GATEWAY_FLOW": {
      "kind": "ref",
      "summary": "Referenced by SDSL inputs"
    },
    "SSOT.APPROVAL_POLICY": {
      "kind": "ref",
      "summary": "Referenced by SDSL inputs"
    },
    "SSOT.ATOMICITY_CONSTRAINTS": {
      "kind": "ref",
      "summary": "Referenced by SDSL inputs"
    },
    "SSOT.AUDIT_RETENTION_POLICY": {
      "kind": "alias",
      "summary": "Alias of SSOT.AuditRetentionPolicy",
      "alias_of": "SSOT.AuditRetentionPolicy"
    },
    "SSOT.AUDIT_STORAGE_STRATEGY": {
      "kind": "rule",
      "summary": "Audit storage strategy (dual write)",
      "value": {
        "mode": "dual_write",
        "primary": "postgres",
        "secondary": "redis_stream",
        "stream_key": "safety:audit:log"
      }
    },
    "SSOT.AUTHORITY_CALCULATION": {
      "kind": "ref",
      "summary": "Referenced by SDSL inputs"
    },
    "SSOT.AUTHORIZATION_CACHE_TTL_SECONDS": {
      "kind": "rule",
      "summary": "Authorization cache TTL in seconds",
      "value": 30
    },
    "SSOT.AlertManager": {
      "kind": "rule",
      "summary": "Alert manager defaults",
      "value": {
        "channel": "safety:alert",
        "history_key": "safety:alert:history",
        "active_key": "safety:alerts:active",
        "history_max_len": 1000,
        "dedup_window_sec": 60
      }
    },
    "SSOT.AlertManagerPolicy": {
      "kind": "rule",
      "summary": "Alert routing policy defaults",
      "value": {
        "notify_min_level": "ERROR",
        "routes": {
          "INFO": ["LOG_ONLY"],
          "WARN": ["DASHBOARD"],
          "ERROR": ["SLACK", "DASHBOARD"],
          "CRITICAL": ["PAGER", "SLACK", "DASHBOARD"]
        }
      }
    },
    "SSOT.ArchitectureResolution": {
      "kind": "ref",
      "summary": "Referenced by SDSL inputs"
    },
    "SSOT.AsyncExecution": {
      "kind": "ref",
      "summary": "Referenced by SDSL inputs"
    },
    "SSOT.AtomicBuffering": {
      "kind": "ref",
      "summary": "Referenced by SDSL inputs"
    },
    "SSOT.Atomicity": {
      "kind": "ref",
      "summary": "Referenced by SDSL inputs"
    },
    "SSOT.AuditRetentionPolicy": {
      "kind": "rule",
      "summary": "Audit retention defaults",
      "value": {
        "retention_days": 180,
        "archive_after_days": 90,
        "redis_retention_days": 7,
        "stream_maxlen": 100000,
        "stream_key": "safety:audit:log"
      }
    },
    "SSOT.AuditTypes": {
      "kind": "table",
      "summary": "Audit event types and default levels",
      "value": {
        "types": [
          "kill_switch_activated",
          "kill_switch_reset",
          "state_transition",
          "component_register",
          "component_deregister",
          "health_check",
          "buffer_allocate",
          "buffer_release",
          "config_change",
          "manual_intervention",
          "recovery_start",
          "recovery_complete"
        ],
        "default_levels": {
          "kill_switch_activated": "CRITICAL",
          "kill_switch_reset": "CRITICAL",
          "state_transition": "INFO",
          "component_register": "INFO",
          "component_deregister": "WARNING",
          "health_check": "DEBUG",
          "buffer_allocate": "DEBUG",
          "buffer_release": "DEBUG",
          "config_change": "WARNING",
          "manual_intervention": "CRITICAL",
          "recovery_start": "WARNING",
          "recovery_complete": "INFO"
        }
      }
    },
    "SSOT.BACKPRESSURE_THRESHOLD": {
      "kind": "rule",
      "summary": "Backpressure alert thresholds (percent)",
      "value": {
        "warn_percent": 70,
        "critical_percent": 90
      }
    },
    "SSOT.BNS_Dtypes": {
      "kind": "ref",
      "summary": "Referenced by SDSL inputs"
    },
    "SSOT.BNS_Formats": {
      "kind": "ref",
      "summary": "Referenced by SDSL inputs"
    },
    "SSOT.BNS_Validation_Spec": {
      "kind": "ref",
      "summary": "Referenced by SDSL inputs"
    },
    "SSOT.BPYT_CRITICAL_THRESHOLD_PERCENT": {
      "kind": "rule",
      "summary": "Backpressure critical threshold (percent)",
      "value": 90
    },
    "SSOT.BPYT_WARN_THRESHOLD_PERCENT": {
      "kind": "rule",
      "summary": "Backpressure warning threshold (percent)",
      "value": 70
    },
    "SSOT.BP_MAX_MESSAGE_SIZE_BYTES": {
      "kind": "rule",
      "summary": "Maximum message size in bytes",
      "value": 1000000
    },
    "SSOT.BP_STATS_KEY": {
      "kind": "rule",
      "summary": "Backpressure stats key pattern",
      "value": {
        "pattern": "bp:stats:{component_id}",
        "ttl_sec": 60
      }
    },
    "SSOT.BackpressureManager": {
      "kind": "rule",
      "summary": "Backpressure manager defaults",
      "value": {
        "alert_channel": "alert:backpressure",
        "metrics_output": "stdout_json",
        "metrics_redis_enabled": true,
        "bp_stats_key_prefix": "bp:stats",
        "bp_stats_ttl_sec": 60,
        "bp_queue_usage_prefix": "bp:queue:usage",
        "bp_queue_usage_ttl_sec": 10,
        "bp_conflation_prefix": "bp:conflation:count"
      }
    },
    "SSOT.BackpressurePolicy": {
      "kind": "rule",
      "summary": "Backpressure drop/conflation policy",
      "value": {
        "priority_policy": {
          "CRITICAL": "NO_DROP",
          "HIGH": "DROP_LAST_RESORT",
          "MEDIUM": "CONFLATE",
          "LOW": "DROP_FIRST"
        },
        "warn_threshold_percent": 70,
        "critical_threshold_percent": 90
      }
    },
    "SSOT.BufferJanitor": {
      "kind": "ref",
      "summary": "Referenced by SDSL inputs"
    },
    "SSOT.BufferRegistry": {
      "kind": "ref",
      "summary": "Referenced by SDSL inputs"
    },
    "SSOT.CACHE_POLICY": {
      "kind": "ref",
      "summary": "Referenced by SDSL inputs"
    },
    "SSOT.CALCULATION_LOGIC": {
      "kind": "ref",
      "summary": "Referenced by SDSL inputs"
    },
    "SSOT.CATCHUP_STRATEGY": {
      "kind": "rule",
      "summary": "Catchup triggers and reasons for reconciliation",
      "value": {
        "reasons": ["startup_catchup", "periodic", "syncing_complete", "killswitch_reset"],
        "startup_condition": "system_state in phases_after_syncing",
        "periodic_trigger": "config.periodic_interval_sec",
        "syncing_complete_trigger": "state transition SYNCING->WARMUP when enabled",
        "killswitch_reset_trigger": "state transition SAFE_MODE/EMERGENCY->RECOVERY_READY when enabled",
        "state_source": "REDIS_KEYS.SYSTEM_STATE"
      }
    },
    "SSOT.CLIENT_VERIFICATION_POLICY": {
      "kind": "ref",
      "summary": "Referenced by SDSL inputs"
    },
    "SSOT.COMMAND_SIGNER": {
      "kind": "rule",
      "summary": "Control-plane command signer defaults",
      "value": {
        "algorithm": "HMAC-SHA256",
        "payload": "json.dumps(signable, sort_keys=True, default=str).encode('utf-8')",
        "exclude_fields": ["signature"]
      }
    },
    "SSOT.CONFIRMATION_CODE_REQUIREMENT": {
      "kind": "ref",
      "summary": "Referenced by SDSL inputs"
    },
    "SSOT.CONFLATION_LOGIC": {
      "kind": "rule",
      "summary": "Event conflation allowlist",
      "value": {
        "conflate_events": ["market_tick", "position_update"]
      }
    },
    "SSOT.CONTROL_PLANE_GATE": {
      "kind": "rule",
      "summary": "Control plane gate: signature + RBAC + audit",
      "value": {
        "steps": ["signature_validation", "rbac_check", "audit_log"],
        "on_signature_failure": "reject",
        "on_permission_failure": "reject"
      }
    },
    "SSOT.CONTROL_PLANE_TIMEOUT": {
      "kind": "rule",
      "summary": "Control plane timeout defaults",
      "value": {
        "timeout_sec": 30,
        "extended_timeout_commands": ["STOP", "SHUTDOWN", "KILL_L2"]
      }
    },
    "SSOT.CQRS_PATTERN": {
      "kind": "ref",
      "summary": "Referenced by SDSL inputs"
    },
    "SSOT.CRASH_RECOVERY_SAFETY": {
      "kind": "rule",
      "summary": "Crash recovery safety guarantees"
    },
    "SSOT.CheckpointPolicy": {
      "kind": "ref",
      "summary": "Referenced by SDSL inputs"
    },
    "SSOT.ClOrdID": {
      "kind": "rule",
      "summary": "ClOrdID format and idempotency key",
      "value": {
        "format": "{prefix}-{env}-{instrument}-{startup_seed_ns}-{counter:05d}",
        "example": "ORD-PROD-BTC-1702123456789012345-00001",
        "idempotency_key": "cmd:executed:{clordid}",
        "ttl_seconds": 86400
      }
    },
    "SSOT.CommandExecutor": {
      "kind": "ref",
      "summary": "Referenced by SDSL inputs"
    },
    "SSOT.CommandTimeout": {
      "kind": "rule",
      "summary": "Command execution timeout default",
      "value": {
        "timeout_sec": 30
      }
    },
    "SSOT.CommandTypes": {
      "kind": "ref",
      "summary": "Referenced by SDSL inputs"
    },
    "SSOT.CommunicationChannel": {
      "kind": "ref",
      "summary": "Referenced by SDSL inputs"
    },
    "SSOT.ComponentHealth": {
      "kind": "rule",
      "summary": "Component health record schema",
      "value": {
        "fields": {
          "component_id": "s",
          "status": "HealthStatus",
          "last_heartbeat_ns": "i",
          "last_check_ns": "i",
          "message": "s?"
        }
      }
    },
    "SSOT.ComponentID": {
      "kind": "ref",
      "summary": "Referenced by SDSL inputs"
    },
    "SSOT.ComputationGraph": {
      "kind": "ref",
      "summary": "Referenced by SDSL inputs"
    },
    "SSOT.ConcurrencyControl": {
      "kind": "rule",
      "summary": "Lock acquisition order (deadlock-safe)",
      "value": {
        "lock_order": [
          "kill_switch",
          "state_machine",
          "component_registry",
          "buffer_manager"
        ]
      }
    },
    "SSOT.ConfigLoader": {
      "kind": "ref",
      "summary": "Referenced by SDSL inputs"
    },
    "SSOT.ContainerManagement": {
      "kind": "ref",
      "summary": "Referenced by SDSL inputs"
    },
    "SSOT.ContinuityPrinciple": {
      "kind": "ref",
      "summary": "Referenced by SDSL inputs"
    },
    "SSOT.ControlCommands": {
      "kind": "rule",
      "summary": "Control plane command types",
      "value": {
        "types": ["KILL_L0", "KILL_L1", "KILL_L2", "RESUME"]
      }
    },
    "SSOT.DASHBOARD_PRIORITIES": {
      "kind": "table",
      "summary": "Dashboard priority buckets",
      "value": ["P0", "P1", "P2", "P3"]
    },
    "SSOT.DB_PARTITIONING_POLICY": {
      "kind": "ref",
      "summary": "Referenced by SDSL inputs"
    },
    "SSOT.DECIMAL_SAFETY": {
      "kind": "ref",
      "summary": "Referenced by SDSL inputs"
    },
    "SSOT.DELIVERY_GUARANTEE": {
      "kind": "rule",
      "summary": "Events that must not be dropped",
      "value": {
        "no_drop_events": ["alert", "order_update", "system_status"]
      }
    },
    "SSOT.DType": {
      "kind": "ref",
      "summary": "Referenced by SDSL inputs"
    },
    "SSOT.DataExchangeFormat": {
      "kind": "ref",
      "summary": "Referenced by SDSL inputs"
    },
    "SSOT.DecimalUtils": {
      "kind": "ref",
      "summary": "Referenced by SDSL inputs"
    },
    "SSOT.DecimalValidators": {
      "kind": "ref",
      "summary": "Referenced by SDSL inputs"
    },
    "SSOT.DegradationLevel": {
      "kind": "ref",
      "summary": "Referenced by SDSL inputs"
    },
    "SSOT.DurabilityPolicy": {
      "kind": "rule",
      "summary": "WAL durability defaults",
      "value": {
        "execution_fsync_policy": "EVERY_WRITE",
        "feature_fsync_policy": "BATCH",
        "fsync_batch_size": 100,
        "fsync_batch_interval_ms": 100,
        "max_file_size_mb": 100,
        "max_file_age_hours": 1,
        "retain_rotated_files": 10,
        "checksum_algorithm": "crc32",
        "verify_on_read": true,
        "corrupt_entry_policy": "skip_and_warn"
      }
    },
    "SSOT.DurabilityStrategy": {
      "kind": "rule",
      "summary": "WAL storage strategy defaults",
      "value": {
        "storage": "mmap",
        "writer_mode": "async_queue",
        "non_blocking": true
      }
    },
    "SSOT.ENTRYPOINT_TABLE": {
      "kind": "ref",
      "summary": "Referenced by SDSL inputs"
    },
    "SSOT.ENVIRONMENT_BASELINE": {
      "kind": "ref",
      "summary": "Referenced by SDSL inputs"
    },
    "SSOT.ERROR_CODES": {
      "kind": "table",
      "summary": "Error code registry (minimal)",
      "value": {
        "codes": [
          "E_1001",
          "E_1002",
          "E_1003",
          "E_1004",
          "E_1005",
          "E_1006",
          "E_1007",
          "E_2001",
          "E_2002",
          "E_2003",
          "E_2004",
          "E_2005",
          "E_2006",
          "E_2007",
          "E_3001",
          "E_3002",
          "E_3003",
          "E_3004",
          "E_3005",
          "E_3006",
          "E_3007",
          "E_3008",
          "E_4001",
          "E_4002",
          "E_4003",
          "E_4004",
          "E_4005",
          "E_4006",
          "E_5001",
          "E_5002",
          "E_5003",
          "E_5004",
          "E_5005",
          "E_5006",
          "E_5007",
          "E_5008",
          "E_9001",
          "E_9002"
        ]
      }
    },
    "SSOT.ERROR_CODE_1001": {
      "kind": "rule",
      "summary": "Kill switch triggered",
      "value": {
        "code": "E_1001",
        "domain": "safety",
        "name": "KILL_SWITCH_TRIGGERED",
        "http": 503,
        "severity": "CRITICAL",
        "message_template": "Kill switch triggered: {reason} (Level: {level})"
      }
    },
    "SSOT.ERROR_CODE_1002": {
      "kind": "rule",
      "summary": "Heartbeat timeout",
      "value": {
        "code": "E_1002",
        "domain": "safety",
        "name": "HEARTBEAT_TIMEOUT",
        "http": 503,
        "severity": "CRITICAL",
        "message_template": "Heartbeat timeout: {component_id} (Last seen: {age_ms}ms ago)"
      }
    },
    "SSOT.ERROR_CODE_1003": {
      "kind": "rule",
      "summary": "Invalid signature",
      "value": {
        "code": "E_1003",
        "domain": "safety",
        "name": "INVALID_SIGNATURE",
        "http": 401,
        "severity": "ERROR",
        "message_template": "Command signature verification failed: {command_id}"
      }
    },
    "SSOT.ERROR_CODE_1004": {
      "kind": "rule",
      "summary": "RBAC denied",
      "value": {
        "code": "E_1004",
        "domain": "safety",
        "name": "RBAC_DENIED",
        "http": 403,
        "severity": "ERROR",
        "message_template": "Permission denied: Operator {operator_id} lacks {permission}"
      }
    },
    "SSOT.ERROR_CODE_1005": {
      "kind": "rule",
      "summary": "Safety Redis failure",
      "value": {
        "code": "E_1005",
        "domain": "safety",
        "name": "SAFETY_REDIS_FAILURE",
        "http": 500,
        "severity": "CRITICAL",
        "message_template": "Safety Redis connection failed: {error}"
      }
    },
    "SSOT.ERROR_CODE_1006": {
      "kind": "rule",
      "summary": "WAL write failure",
      "value": {
        "code": "E_1006",
        "domain": "safety",
        "name": "WAL_WRITE_FAILURE",
        "http": 500,
        "severity": "CRITICAL",
        "message_template": "WAL write failed: {error} (Path: {path})"
      }
    },
    "SSOT.ERROR_CODE_1007": {
      "kind": "rule",
      "summary": "Checkpoint validation failed",
      "value": {
        "code": "E_1007",
        "domain": "safety",
        "name": "CHECKPOINT_VALIDATION_FAILED",
        "http": 400,
        "severity": "ERROR",
        "message_template": "Checkpoint validation failed: CRC mismatch"
      }
    },
    "SSOT.ERROR_CODE_2001": {
      "kind": "rule",
      "summary": "Invalid state transition",
      "value": {
        "code": "E_2001",
        "domain": "orchestration",
        "name": "INVALID_STATE_TRANSITION",
        "http": 409,
        "severity": "ERROR",
        "message_template": "Invalid state transition: {current} -> {target}"
      }
    },
    "SSOT.ERROR_CODE_2002": {
      "kind": "rule",
      "summary": "Component not ready",
      "value": {
        "code": "E_2002",
        "domain": "orchestration",
        "name": "COMPONENT_NOT_READY",
        "http": 503,
        "severity": "WARN",
        "message_template": "Component not ready: {component_id} is {status}"
      }
    },
    "SSOT.ERROR_CODE_2003": {
      "kind": "rule",
      "summary": "Recovery timeout",
      "value": {
        "code": "E_2003",
        "domain": "orchestration",
        "name": "RECOVERY_TIMEOUT",
        "http": 408,
        "severity": "ERROR",
        "message_template": "Recovery timeout: Stage {stage} exceeded {timeout}s"
      }
    },
    "SSOT.ERROR_CODE_2004": {
      "kind": "rule",
      "summary": "Config validation failed",
      "value": {
        "code": "E_2004",
        "domain": "orchestration",
        "name": "CONFIG_VALIDATION_FAILED",
        "http": 400,
        "severity": "ERROR",
        "message_template": "Config validation failed: {reason}"
      }
    },
    "SSOT.ERROR_CODE_2005": {
      "kind": "rule",
      "summary": "Guarded trading active",
      "value": {
        "code": "E_2005",
        "domain": "orchestration",
        "name": "GUARDED_TRADING_ACTIVE",
        "http": 503,
        "severity": "WARN",
        "message_template": "Guarded Trading active: {stage}% capacity"
      }
    },
    "SSOT.ERROR_CODE_2006": {
      "kind": "rule",
      "summary": "Event routing failed",
      "value": {
        "code": "E_2006",
        "domain": "orchestration",
        "name": "EVENT_ROUTING_FAILED",
        "http": 500,
        "severity": "ERROR",
        "message_template": "Event routing failed: {topic} (Reason: {reason})"
      }
    },
    "SSOT.ERROR_CODE_2007": {
      "kind": "rule",
      "summary": "Safety plane unresponsive",
      "value": {
        "code": "E_2007",
        "domain": "orchestration",
        "name": "SAFETY_PLANE_UNRESPONSIVE",
        "http": 500,
        "severity": "CRITICAL",
        "message_template": "Safety Plane unresponsive: Watchdog stale for {age_sec}s"
      }
    },
    "SSOT.ERROR_CODE_3001": {
      "kind": "rule",
      "summary": "Schema validation failed",
      "value": {
        "code": "E_3001",
        "domain": "featureData",
        "name": "SCHEMA_VALIDATION_FAILED",
        "http": 400,
        "severity": "ERROR",
        "message_template": "Schema validation failed: {schema_id} mismatch"
      }
    },
    "SSOT.ERROR_CODE_3002": {
      "kind": "rule",
      "summary": "Backpressure critical",
      "value": {
        "code": "E_3002",
        "domain": "featureData",
        "name": "BACKPRESSURE_CRITICAL",
        "http": 500,
        "severity": "CRITICAL",
        "message_template": "Backpressure critical: Queue usage {usage}% > {threshold}%"
      }
    },
    "SSOT.ERROR_CODE_3003": {
      "kind": "rule",
      "summary": "Stale feature detected",
      "value": {
        "code": "E_3003",
        "domain": "featureData",
        "name": "STALE_FEATURE_DETECTED",
        "http": 422,
        "severity": "WARN",
        "message_template": "Stale feature detected: Age {age_ms}ms > {threshold_ms}ms"
      }
    },
    "SSOT.ERROR_CODE_3004": {
      "kind": "rule",
      "summary": "Zero-copy buffer error",
      "value": {
        "code": "E_3004",
        "domain": "featureData",
        "name": "ZERO_COPY_BUFFER_ERROR",
        "http": 500,
        "severity": "CRITICAL",
        "message_template": "Zero-Copy buffer error: {reason}"
      }
    },
    "SSOT.ERROR_CODE_3005": {
      "kind": "rule",
      "summary": "Data quality check failed",
      "value": {
        "code": "E_3005",
        "domain": "featureData",
        "name": "DATA_QUALITY_CHECK_FAILED",
        "http": 422,
        "severity": "ERROR",
        "message_template": "Data quality check failed: {reason} (NaN/Inf)"
      }
    },
    "SSOT.ERROR_CODE_3006": {
      "kind": "rule",
      "summary": "Conflation overflow",
      "value": {
        "code": "E_3006",
        "domain": "featureData",
        "name": "CONFLATION_OVERFLOW",
        "http": 500,
        "severity": "CRITICAL",
        "message_template": "Conflation overflow: Symbol {symbol} ({count} conflations)"
      }
    },
    "SSOT.ERROR_CODE_3007": {
      "kind": "rule",
      "summary": "Orphan buffer detected",
      "value": {
        "code": "E_3007",
        "domain": "featureData",
        "name": "ORPHAN_BUFFER_DETECTED",
        "http": 503,
        "severity": "WARN",
        "message_template": "Orphan buffer detected: {buffer_ref} (PID {pid} dead)"
      }
    },
    "SSOT.ERROR_CODE_3008": {
      "kind": "rule",
      "summary": "Schema hash mismatch",
      "value": {
        "code": "E_3008",
        "domain": "featureData",
        "name": "SCHEMA_HASH_MISMATCH",
        "http": 422,
        "severity": "ERROR",
        "message_template": "Schema hash mismatch: received {received}, expected {expected}"
      }
    },
    "SSOT.ERROR_CODE_4001": {
      "kind": "rule",
      "summary": "Confidence too low",
      "value": {
        "code": "E_4001",
        "domain": "modelStrategy",
        "name": "CONFIDENCE_TOO_LOW",
        "http": 422,
        "severity": "WARN",
        "message_template": "Confidence too low: {confidence} < {threshold}"
      }
    },
    "SSOT.ERROR_CODE_4002": {
      "kind": "rule",
      "summary": "Circuit breaker triggered",
      "value": {
        "code": "E_4002",
        "domain": "modelStrategy",
        "name": "CIRCUIT_BREAKER_TRIGGERED",
        "http": 500,
        "severity": "CRITICAL",
        "message_template": "Circuit breaker triggered: {strategy_id}"
      }
    },
    "SSOT.ERROR_CODE_4003": {
      "kind": "rule",
      "summary": "Order validation failed",
      "value": {
        "code": "E_4003",
        "domain": "modelStrategy",
        "name": "ORDER_VALIDATION_FAILED",
        "http": 400,
        "severity": "ERROR",
        "message_template": "Order validation failed: {reason}"
      }
    },
    "SSOT.ERROR_CODE_4004": {
      "kind": "rule",
      "summary": "Feature schema mismatch",
      "value": {
        "code": "E_4004",
        "domain": "modelStrategy",
        "name": "FEATURE_SCHEMA_MISMATCH",
        "http": 422,
        "severity": "ERROR",
        "message_template": "Feature schema mismatch: Expected {expected}, got {actual}"
      }
    },
    "SSOT.ERROR_CODE_4005": {
      "kind": "rule",
      "summary": "Strategy paused",
      "value": {
        "code": "E_4005",
        "domain": "modelStrategy",
        "name": "STRATEGY_PAUSED",
        "http": 503,
        "severity": "WARN",
        "message_template": "Strategy paused: {strategy_id} (Reason: {reason})"
      }
    },
    "SSOT.ERROR_CODE_4006": {
      "kind": "rule",
      "summary": "Order submission failed",
      "value": {
        "code": "E_4006",
        "domain": "modelStrategy",
        "name": "ORDER_SUBMISSION_FAILED",
        "http": 500,
        "severity": "ERROR",
        "message_template": "Order submission failed: {cloid} (Exchange: {error})"
      }
    },
    "SSOT.ERROR_CODE_5001": {
      "kind": "rule",
      "summary": "Authentication failed",
      "value": {
        "code": "E_5001",
        "domain": "operationsApi",
        "name": "AUTHENTICATION_FAILED",
        "http": 401,
        "severity": "ERROR",
        "message_template": "Authentication failed: Invalid API key"
      }
    },
    "SSOT.ERROR_CODE_5002": {
      "kind": "rule",
      "summary": "Insufficient permissions",
      "value": {
        "code": "E_5002",
        "domain": "operationsApi",
        "name": "INSUFFICIENT_PERMISSIONS",
        "http": 403,
        "severity": "ERROR",
        "message_template": "Insufficient permissions: {operator_id} for {action}"
      }
    },
    "SSOT.ERROR_CODE_5003": {
      "kind": "rule",
      "summary": "Command timeout",
      "value": {
        "code": "E_5003",
        "domain": "operationsApi",
        "name": "COMMAND_TIMEOUT",
        "http": 408,
        "severity": "ERROR",
        "message_template": "Command timeout: {command_id} after {timeout_sec}s"
      }
    },
    "SSOT.ERROR_CODE_5004": {
      "kind": "rule",
      "summary": "Rate limit exceeded",
      "value": {
        "code": "E_5004",
        "domain": "operationsApi",
        "name": "RATE_LIMIT_EXCEEDED",
        "http": 429,
        "severity": "WARN",
        "message_template": "Rate limit exceeded: {endpoint} ({requests}/min)"
      }
    },
    "SSOT.ERROR_CODE_5005": {
      "kind": "rule",
      "summary": "Audit log write failed",
      "value": {
        "code": "E_5005",
        "domain": "operationsApi",
        "name": "AUDIT_LOG_WRITE_FAILED",
        "http": 500,
        "severity": "ERROR",
        "message_template": "Audit log write failed: {error}"
      }
    },
    "SSOT.ERROR_CODE_5006": {
      "kind": "rule",
      "summary": "Parameter rollback expired",
      "value": {
        "code": "E_5006",
        "domain": "operationsApi",
        "name": "PARAMETER_ROLLBACK_EXPIRED",
        "http": 400,
        "severity": "WARN",
        "message_template": "Parameter rollback expired: {command_id}"
      }
    },
    "SSOT.ERROR_CODE_5007": {
      "kind": "rule",
      "summary": "SSE connection lost",
      "value": {
        "code": "E_5007",
        "domain": "operationsApi",
        "name": "SSE_CONNECTION_LOST",
        "http": 503,
        "severity": "ERROR",
        "message_template": "SSE connection lost: {client_id}"
      }
    },
    "SSOT.ERROR_CODE_5008": {
      "kind": "rule",
      "summary": "mTLS validation failed",
      "value": {
        "code": "E_5008",
        "domain": "operationsApi",
        "name": "MTLS_VALIDATION_FAILED",
        "http": 500,
        "severity": "CRITICAL",
        "message_template": "Client certificate validation failed: {cn}"
      }
    },
    "SSOT.ERROR_CODE_9001": {
      "kind": "rule",
      "summary": "Schema mismatch invariant violated",
      "value": {
        "code": "E_9001",
        "domain": "invariant",
        "name": "SCHEMA_MISMATCH",
        "http": 500,
        "severity": "CRITICAL",
        "message_template": "Schema mismatch invariant violated"
      }
    },
    "SSOT.ERROR_CODE_9002": {
      "kind": "rule",
      "summary": "Invariant violation",
      "value": {
        "code": "E_9002",
        "domain": "invariant",
        "name": "INVARIANT_VIOLATION",
        "http": 500,
        "severity": "CRITICAL",
        "message_template": "Invariant violation"
      }
    },
    "SSOT.ERROR_DOMAIN_RANGES": {
      "kind": "table",
      "summary": "Error domain ranges",
      "value": {
        "safety": { "min": 1000, "max": 1999 },
        "orchestration": { "min": 2000, "max": 2999 },
        "featureData": { "min": 3000, "max": 3999 },
        "modelStrategy": { "min": 4000, "max": 4999 },
        "operationsApi": { "min": 5000, "max": 5999 },
        "invariant": { "min": 9000, "max": 9999 }
      }
    },
    "SSOT.ERROR_RATE_THRESHOLD": {
      "kind": "rule",
      "summary": "Error rate alert thresholds (percent)",
      "value": {
        "warn_percent": 1,
        "critical_percent": 5,
        "window_sec": 60
      }
    },
    "SSOT.EVENT_PRIORITY_MATRIX": {
      "kind": "ref",
      "summary": "Referenced by SDSL inputs"
    },
    "SSOT.EXCHANGE_API_SPEC": {
      "kind": "ref",
      "summary": "Referenced by SDSL inputs"
    },
    "SSOT.EXPIRATION_CALCULATION": {
      "kind": "ref",
      "summary": "Referenced by SDSL inputs"
    },
    "SSOT.EncodingPolicy": {
      "kind": "ref",
      "summary": "Referenced by SDSL inputs"
    },
    "SSOT.ErrorCategories": {
      "kind": "table",
      "summary": "Error category and level vocabularies",
      "value": {
        "categories": [
          "VALIDATION",
          "CONNECTION",
          "RATE_LIMIT",
          "BACKPRESSURE",
          "RECONCILIATION",
          "COMPUTATION",
          "CRITICAL_PANIC"
        ],
        "levels": ["INFO", "WARN", "ERROR", "CRITICAL"]
      }
    },
    "SSOT.ErrorHandler": {
      "kind": "ref",
      "summary": "Referenced by SDSL inputs"
    },
    "SSOT.ErrorHandling": {
      "kind": "rule",
      "summary": "Default error handling severity mapping",
      "value": {
        "levels": ["INFO", "WARN", "ERROR", "CRITICAL"],
        "category_defaults": {
          "VALIDATION": "ERROR",
          "CONNECTION": "ERROR",
          "RATE_LIMIT": "WARN",
          "BACKPRESSURE": "CRITICAL",
          "RECONCILIATION": "CRITICAL",
          "COMPUTATION": "ERROR",
          "CRITICAL_PANIC": "CRITICAL"
        }
      }
    },
    "SSOT.EscalationLogic": {
      "kind": "rule",
      "summary": "Escalation logic defaults",
      "value": {
        "missing_key_as_zero": true,
        "recovery_resets_escalation": true
      }
    },
    "SSOT.EscalationPolicy": {
      "kind": "ref",
      "summary": "Referenced by SDSL inputs"
    },
    "SSOT.EscalationThresholds": {
      "kind": "rule",
      "summary": "Escalation timing thresholds (sec)",
      "value": {
        "l0_after_seconds": 5,
        "l1_after_seconds": 15,
        "l2_after_seconds": 30
      }
    },
    "SSOT.ExchangeInterface": {
      "kind": "ref",
      "summary": "Referenced by SDSL inputs"
    },
    "SSOT.FAULT_INJECTION_POLICY": {
      "kind": "ref",
      "summary": "Referenced by SDSL inputs"
    },
    "SSOT.FULL_SAFE_MODE_POLICY": {
      "kind": "ref",
      "summary": "Referenced by SDSL inputs"
    },
    "SSOT.FailureModePolicy": {
      "kind": "ref",
      "summary": "Referenced by SDSL inputs"
    },
    "SSOT.FeatureTransport": {
      "kind": "ref",
      "summary": "Referenced by SDSL inputs"
    },
    "SSOT.FileStructure": {
      "kind": "ref",
      "summary": "Referenced by SDSL inputs"
    },
    "SSOT.FormatRules": {
      "kind": "ref",
      "summary": "Referenced by SDSL inputs"
    },
    "SSOT.GHOST_KILL_POLICY": {
      "kind": "ref",
      "summary": "Referenced by SDSL inputs"
    },
    "SSOT.GHOST_ORDER_RECOVERY": {
      "kind": "ref",
      "summary": "Referenced by SDSL inputs"
    },
    "SSOT.GHOST_ORDER_SAFETY": {
      "kind": "rule",
      "summary": "Ghost order safety guarantees"
    },
    "SSOT.GRACE_PERIOD_SECONDS": {
      "kind": "ref",
      "summary": "Referenced by SDSL inputs"
    },
    "SSOT.GapDetection": {
      "kind": "ref",
      "summary": "Referenced by SDSL inputs"
    },
    "SSOT.Governance": {
      "kind": "ref",
      "summary": "Referenced by SDSL inputs"
    },
    "SSOT.HEALTH_STATUS_VALUES": {
      "kind": "table",
      "summary": "Health status enum values",
      "value": ["HEALTHY", "WARNING", "DEGRADED", "CRITICAL", "STOPPED"]
    },
    "SSOT.HEARTBEAT_THRESHOLD": {
      "kind": "rule",
      "summary": "Heartbeat timeout threshold",
      "value": {
        "timeout_ms": 5000
      }
    },
    "SSOT.HMAC_SIGNATURE": {
      "kind": "rule",
      "summary": "HMAC signature defaults",
      "value": {
        "algorithm": "HMAC-SHA256",
        "max_age_sec": 300,
        "headers": {
          "signature": "X-Signature",
          "timestamp": "X-Signature-Ts",
          "nonce": "X-Nonce",
          "operator_id": "X-Operator-Id",
          "content_type": "application/json"
        },
        "payload_formats": [
          "{method}:{path}:{body_hash}:{ts}:{nonce}:{operator_id}",
          "{command_id}:{action}:{params_json_sorted}:{issued_by}:{ts}"
        ]
      }
    },
    "SSOT.HealthAggregator": {
      "kind": "rule",
      "summary": "Health aggregation rule",
      "value": {
        "healthy_if": "ALL_HEALTHY",
        "critical_if": "ANY_CRITICAL",
        "degraded_if": "ANY_WARNING_OR_DEGRADED"
      }
    },
    "SSOT.HealthStatus": {
      "kind": "alias",
      "summary": "Alias of SSOT.HEALTH_STATUS_VALUES",
      "alias_of": "SSOT.HEALTH_STATUS_VALUES"
    },
    "SSOT.HealthStatusEnum": {
      "kind": "alias",
      "summary": "Alias of SSOT.HEALTH_STATUS_VALUES",
      "alias_of": "SSOT.HEALTH_STATUS_VALUES"
    },
    "SSOT.HealthTypes": {
      "kind": "table",
      "summary": "Health-related schema names",
      "value": ["HealthCheckResponse", "HealthCheckConfig", "ComponentHealth"]
    },
    "SSOT.HeartbeatInterval": {
      "kind": "rule",
      "summary": "Heartbeat interval defaults",
      "value": {
        "default_ms": 500,
        "min_ms": 100,
        "max_ms": 10000
      }
    },
    "SSOT.HttpSignature": {
      "kind": "ref",
      "summary": "Referenced by SDSL inputs"
    },
    "SSOT.IDEMPOTENCY_POLICY": {
      "kind": "ref",
      "summary": "Referenced by SDSL inputs"
    },
    "SSOT.INSTRUMENT_ID_FORMAT": {
      "kind": "ref",
      "summary": "Referenced by SDSL inputs"
    },
    "SSOT.INTEGRITY_CRITERIA": {
      "kind": "ref",
      "summary": "Referenced by SDSL inputs"
    },
    "SSOT.Idempotency": {
      "kind": "rule",
      "summary": "Idempotency defaults",
      "value": {
        "store_key_pattern": "cmd:executed:{command_id}",
        "ttl_seconds": 86400,
        "on_duplicate": "RESEND_ACK",
        "max_replays": 3
      }
    },
    "SSOT.IdempotencyKeys": {
      "kind": "rule",
      "summary": "Idempotency key patterns",
      "value": {
        "command_id": "cmd:executed:{command_id}",
        "clordid": "cmd:executed:{clordid}",
        "ttl_seconds": 86400
      }
    },
    "SSOT.ImmutabilityPolicy": {
      "kind": "ref",
      "summary": "Referenced by SDSL inputs"
    },
    "SSOT.ImplementationBacklog": {
      "kind": "ref",
      "summary": "Referenced by SDSL inputs"
    },
    "SSOT.InfraRTT": {
      "kind": "ref",
      "summary": "Referenced by SDSL inputs"
    },
    "SSOT.InfrastructureIsolation": {
      "kind": "ref",
      "summary": "Referenced by SDSL inputs"
    },
    "SSOT.InitialConfig": {
      "kind": "ref",
      "summary": "Referenced by SDSL inputs"
    },
    "SSOT.InstrumentID": {
      "kind": "ref",
      "summary": "Referenced by SDSL inputs"
    },
    "SSOT.IntentTypes": {
      "kind": "ref",
      "summary": "Referenced by SDSL inputs"
    },
    "SSOT.JANITOR_INTERVAL": {
      "kind": "ref",
      "summary": "Referenced by SDSL inputs"
    },
    "SSOT.JUDGE_LOGIC": {
      "kind": "ref",
      "summary": "Referenced by SDSL inputs"
    },
    "SSOT.JsonUtils": {
      "kind": "ref",
      "summary": "Referenced by SDSL inputs"
    },
    "SSOT.KEY_ROTATION_PROCEDURE": {
      "kind": "ref",
      "summary": "Referenced by SDSL inputs"
    },
    "SSOT.KILL_SWITCH_CONSTRAINTS": {
      "kind": "ref",
      "summary": "Referenced by SDSL inputs"
    },
    "SSOT.KISS": {
      "kind": "ref",
      "summary": "Referenced by SDSL inputs"
    },
    "SSOT.KernelDefinitions": {
      "kind": "rule",
      "summary": "Kernel distribution boundary paths",
      "value": {
        "definitions_path": "OUTPUT/ssot/ssot_definitions.json",
        "registry_map_path": "OUTPUT/ssot/ssot_registry_map.json",
        "registry_path": "OUTPUT/ssot/ssot_registry.json"
      }
    },
    "SSOT.LATENCY_CRITERIA": {
      "kind": "rule",
      "summary": "Latency budget criteria (20ms loop)",
      "value": {
        "logic_max_ms": 1.0,
        "risk_route_max_ms": 2.0,
        "sync_io_max_ms": 0.0,
        "jitter_buffer_ms": 10.0,
        "reserve_ms": 7.0,
        "loop_period_ms": 20.0
      }
    },
    "SSOT.LATENCY_THRESHOLD": {
      "kind": "rule",
      "summary": "Latency alert thresholds (ms)",
      "value": {
        "warn_ms": 10,
        "critical_ms": 50
      }
    },
    "SSOT.LINUX_PID_STAT": {
      "kind": "ref",
      "summary": "Referenced by SDSL inputs"
    },
    "SSOT.LOG_FORMAT_JSON": {
      "kind": "rule",
      "summary": "JSON log format (line-delimited)",
      "value": {
        "format": "json",
        "line_delimited": true,
        "encoding": "utf-8"
      }
    },
    "SSOT.LOST_ORDER_POLICY": {
      "kind": "ref",
      "summary": "Referenced by SDSL inputs"
    },
    "SSOT.LayerHierarchy": {
      "kind": "ref",
      "summary": "Referenced by SDSL inputs"
    },
    "SSOT.LocalClock": {
      "kind": "ref",
      "summary": "Referenced by SDSL inputs"
    },
    "SSOT.Locks": {
      "kind": "ref",
      "summary": "Referenced by SDSL inputs"
    },
    "SSOT.LoggingConfig": {
      "kind": "rule",
      "summary": "Structured logging defaults",
      "value": {
        "levels": ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        "default_level": "INFO",
        "json_output": true,
        "timestamp_format": "iso",
        "output": "stdout"
      }
    },
    "SSOT.MASTER_RELOAD_MECHANISM": {
      "kind": "ref",
      "summary": "Referenced by SDSL inputs"
    },
    "SSOT.MEMORY_THRESHOLD": {
      "kind": "rule",
      "summary": "Memory alert thresholds (percent)",
      "value": {
        "warn_percent": 80,
        "critical_percent": 95
      }
    },
    "SSOT.MINIMAL_DEF": {
      "kind": "ref",
      "summary": "Referenced by SDSL inputs"
    },
    "SSOT.MTLS_CONFIG": {
      "kind": "ref",
      "summary": "Referenced by SDSL inputs"
    },
    "SSOT.MainRedis": {
      "kind": "rule",
      "summary": "Main Redis connection defaults",
      "value": {
        "port": 6379,
        "db": 0,
        "required_prefix": "system:",
        "retry_on_timeout": true
      }
    },
    "SSOT.MarketData": {
      "kind": "ref",
      "summary": "Referenced by SDSL inputs"
    },
    "SSOT.MessageEnvelope": {
      "kind": "ref",
      "summary": "Referenced by SDSL inputs"
    },
    "SSOT.MockExchange": {
      "kind": "ref",
      "summary": "Referenced by SDSL inputs"
    },
    "SSOT.ModelPathResolver": {
      "kind": "ref",
      "summary": "Referenced by SDSL inputs"
    },
    "SSOT.MonitoringFrequency": {
      "kind": "rule",
      "summary": "Monitoring frequency defaults",
      "value": {
        "default_interval_ms": 1000,
        "min_interval_ms": 100,
        "max_interval_ms": 60000
      }
    },
    "SSOT.NautilusDataAdapter": {
      "kind": "ref",
      "summary": "Referenced by SDSL inputs"
    },
    "SSOT.NautilusExchangeAdapter": {
      "kind": "ref",
      "summary": "Referenced by SDSL inputs"
    },
    "SSOT.ORDER_VALIDATION_FLOW": {
      "kind": "ref",
      "summary": "Referenced by SDSL inputs"
    },
    "SSOT.ORPHAN_ALERT": {
      "kind": "rule",
      "summary": "Orphaned resource alert policy",
      "value": {
        "level": "WARNING",
        "action": "DASHBOARD",
        "topic": "alert:buffer_janitor"
      }
    },
    "SSOT.OVERWRITE_FIELDS": {
      "kind": "ref",
      "summary": "Referenced by SDSL inputs"
    },
    "SSOT.Observability": {
      "kind": "rule",
      "summary": "Observability pillars",
      "value": {
        "pillars": ["logging", "metrics", "tracing", "alerting", "audit"]
      }
    },
    "SSOT.OperationsAPI": {
      "kind": "ref",
      "summary": "Referenced by SDSL inputs"
    },
    "SSOT.OrchestratorResponsibilities": {
      "kind": "ref",
      "summary": "Referenced by SDSL inputs"
    },
    "SSOT.OrderTypes": {
      "kind": "ref",
      "summary": "Referenced by SDSL inputs"
    },
    "SSOT.PARTITION_SCHEMA": {
      "kind": "ref",
      "summary": "Referenced by SDSL inputs"
    },
    "SSOT.PHASE1_AUTH_METHOD": {
      "kind": "ref",
      "summary": "Referenced by SDSL inputs"
    },
    "SSOT.PHASE_MATURITY_POLICY": {
      "kind": "ref",
      "summary": "Referenced by SDSL inputs"
    },
    "SSOT.PID": {
      "kind": "ref",
      "summary": "Referenced by SDSL inputs"
    },
    "SSOT.PID_CHECK": {
      "kind": "ref",
      "summary": "Referenced by SDSL inputs"
    },
    "SSOT.PROCESS_ISOLATION_RULES": {
      "kind": "ref",
      "summary": "Referenced by SDSL inputs"
    },
    "SSOT.PSUTIL_CREATE_TIME": {
      "kind": "ref",
      "summary": "Referenced by SDSL inputs"
    },
    "SSOT.PayloadEncryption": {
      "kind": "ref",
      "summary": "Referenced by SDSL inputs"
    },
    "SSOT.PerformanceOptimization": {
      "kind": "rule",
      "summary": "Performance optimization defaults",
      "value": {
        "non_blocking_queue": true,
        "prefer_async": true,
        "batching_allowed": true
      }
    },
    "SSOT.PerformancePolicy": {
      "kind": "rule",
      "summary": "Performance policy defaults",
      "value": {
        "fsync_policy": "BATCH"
      }
    },
    "SSOT.PermissionMatrix": {
      "kind": "table",
      "summary": "RBAC permission matrix (permission -> roles)",
      "value": {
        "AUDIT_LOG_READ": ["OPERATOR", "ADMIN"],
        "CHANGE_PARAMETERS": ["OPERATOR", "ADMIN"],
        "EXECUTE_TRADES": ["TRADER", "OPERATOR", "ADMIN"],
        "KILL_SWITCH_L0": ["TRADER", "OPERATOR", "ADMIN"],
        "KILL_SWITCH_L1_L2": ["OPERATOR", "ADMIN"],
        "RESET_KILL_SWITCH": ["ADMIN"],
        "VIEW_POSITIONS": ["OBSERVER", "TRADER", "OPERATOR", "ADMIN"],
        "VIEW_STATUS": ["OBSERVER", "TRADER", "OPERATOR", "ADMIN"]
      }
    },
    "SSOT.PidRegistry": {
      "kind": "ref",
      "summary": "Referenced by SDSL inputs"
    },
    "SSOT.PlaneSeparation": {
      "kind": "ref",
      "summary": "Referenced by SDSL inputs"
    },
    "SSOT.PluginManual": {
      "kind": "rule",
      "summary": "Plugin manual authority roots",
      "value": {
        "authoritative_root": "myplugins/",
        "scope": "plugin-specific rules/config adjacent to code",
        "non_authoritative_roots": ["OUTPUT/", "drafts/"]
      }
    },
    "SSOT.ProcessIndependence": {
      "kind": "rule",
      "summary": "Process independence requirements",
      "value": {
        "isolation_level": "process",
        "independent_components": ["nautilus"],
        "no_subprocess_spawn": true
      }
    },
    "SSOT.ProcessManagement": {
      "kind": "rule",
      "summary": "Process management defaults",
      "value": {
        "pid_key_prefix": "safety:pid:{component}",
        "pid_check_path": "/proc/{pid}",
        "kill_signal": "SIGKILL",
        "graceful_stop_timeout_sec": 5,
        "container_kill_timeout_sec": 5
      }
    },
    "SSOT.ProcessUtils": {
      "kind": "rule",
      "summary": "Process utility expectations",
      "value": {
        "pid_exists_check": "/proc/{pid}",
        "psutil_fallback": true
      }
    },
    "SSOT.RBAC": {
      "kind": "alias",
      "summary": "Alias of SSOT.RBAC_POLICY",
      "alias_of": "SSOT.RBAC_POLICY"
    },
    "SSOT.RBACMapping": {
      "kind": "mapping",
      "summary": "Component to role mapping defaults",
      "value": {
        "default_role": "OBSERVER",
        "component_overrides": {}
      }
    },
    "SSOT.RBACPolicy": {
      "kind": "alias",
      "summary": "Alias of SSOT.RBAC_POLICY",
      "alias_of": "SSOT.RBAC_POLICY"
    },
    "SSOT.RBAC_MATRIX": {
      "kind": "table",
      "summary": "RBAC permission matrix",
      "value": {
        "AUDIT_LOG_READ": ["OPERATOR", "ADMIN"],
        "CHANGE_PARAMETERS": ["OPERATOR", "ADMIN"],
        "EXECUTE_TRADES": ["TRADER", "OPERATOR", "ADMIN"],
        "KILL_SWITCH_L0": ["TRADER", "OPERATOR", "ADMIN"],
        "KILL_SWITCH_L1_L2": ["OPERATOR", "ADMIN"],
        "RESET_KILL_SWITCH": ["ADMIN"],
        "VIEW_POSITIONS": ["OBSERVER", "TRADER", "OPERATOR", "ADMIN"],
        "VIEW_STATUS": ["OBSERVER", "TRADER", "OPERATOR", "ADMIN"]
      }
    },
    "SSOT.RBAC_POLICY": {
      "kind": "rule",
      "summary": "RBAC policy and role hierarchy",
      "value": {
        "roles": ["OBSERVER", "TRADER", "OPERATOR", "ADMIN"],
        "role_hierarchy": ["OBSERVER", "TRADER", "OPERATOR", "ADMIN"],
        "permissions": {
          "AUDIT_LOG_READ": ["OPERATOR", "ADMIN"],
          "CHANGE_PARAMETERS": ["OPERATOR", "ADMIN"],
          "EXECUTE_TRADES": ["TRADER", "OPERATOR", "ADMIN"],
          "KILL_SWITCH_L0": ["TRADER", "OPERATOR", "ADMIN"],
          "KILL_SWITCH_L1_L2": ["OPERATOR", "ADMIN"],
          "RESET_KILL_SWITCH": ["ADMIN"],
          "VIEW_POSITIONS": ["OBSERVER", "TRADER", "OPERATOR", "ADMIN"],
          "VIEW_STATUS": ["OBSERVER", "TRADER", "OPERATOR", "ADMIN"]
        },
        "default_role": "OBSERVER",
        "policy_version": "1.0"
      }
    },
    "SSOT.RECON_ACTIVE_PHASES": {
      "kind": "ref",
      "summary": "Referenced by SDSL inputs"
    },
    "SSOT.RECON_TRIGGER_EVENTS": {
      "kind": "ref",
      "summary": "Referenced by SDSL inputs"
    },
    "SSOT.REDIS_DATA_USAGE": {
      "kind": "rule",
      "summary": "Redis usage boundaries (SoT vs cache)",
      "value": {
        "source_of_truth": "WAL_OR_DB",
        "cache_role": "VIEW_ONLY",
        "write_path": "SOT_FIRST",
        "read_path": "CACHE_THEN_SOT",
        "consistency": "EVENTUAL"
      }
    },
    "SSOT.REDIS_KEYS": {
      "kind": "alias",
      "summary": "Alias of SSOT.RedisKeyCatalog",
      "alias_of": "SSOT.RedisKeyCatalog"
    },
    "SSOT.REDIS_PUB_SUB": {
      "kind": "rule",
      "summary": "Redis pub/sub channel conventions",
      "value": {
        "separator": ".",
        "allow_colon": false
      }
    },
    "SSOT.REDIS_PUB_SUB_TOPICS": {
      "kind": "table",
      "summary": "Canonical pub/sub topics",
      "value": {
        "control": [
          "system.control.{component_id}",
          "system.control.broadcast"
        ],
        "alert": [
          "alert:backpressure"
        ]
      }
    },
    "SSOT.REDIS_REQ_REP": {
      "kind": "rule",
      "summary": "Redis request/response channel pattern",
      "value": {
        "pattern": "rpc.{service}.{method}"
      }
    },
    "SSOT.REDIS_UPDATE_STRATEGY": {
      "kind": "rule",
      "summary": "Redis update strategy for view/cache",
      "value": {
        "pattern": "VIEW_UPDATE_AFTER_SOT",
        "cache_miss": "FALLBACK_TO_SOT",
        "invalidations": "TTL_OR_EXPLICIT",
        "retry_policy": "RETRY_OR_REBUILD"
      }
    },
    "SSOT.RETENTION_DEFAULTS": {
      "kind": "rule",
      "summary": "Audit retention defaults",
      "value": {
        "audit_retention_days": 180,
        "audit_archive_days": 90,
        "audit_redis_retention_days": 7,
        "audit_stream_maxlen": 100000,
        "audit_stream_key": "safety:audit:log"
      }
    },
    "SSOT.RETRY_POLICY": {
      "kind": "rule",
      "summary": "Retry defaults",
      "value": {
        "max_retries": 3,
        "interval_sec": 1.0,
        "backoff": "fixed",
        "jitter_sec": 0.0
      }
    },
    "SSOT.ROLLBACK_WINDOW": {
      "kind": "ref",
      "summary": "Referenced by SDSL inputs"
    },
    "SSOT.ROUND_HALF_UP": {
      "kind": "ref",
      "summary": "Referenced by SDSL inputs"
    },
    "SSOT.RPC_TIMEOUT_SPEC": {
      "kind": "rule",
      "summary": "RPC timeout defaults",
      "value": {
        "default_sec": 30.0,
        "min_sec": 1.0,
        "max_sec": 120.0
      }
    },
    "SSOT.RULE_STATE_SYSTEM_STATE_CANONICAL": {
      "kind": "ref",
      "summary": "Referenced by SDSL inputs"
    },
    "SSOT.R_INFRA_HEALTH_STATUS_ENUM": {
      "kind": "alias",
      "summary": "Alias of SSOT.HEALTH_STATUS_VALUES",
      "alias_of": "SSOT.HEALTH_STATUS_VALUES"
    },
    "SSOT.RecoveryPolicy": {
      "kind": "ref",
      "summary": "Referenced by SDSL inputs"
    },
    "SSOT.RecoveryTimeObjective": {
      "kind": "ref",
      "summary": "Referenced by SDSL inputs"
    },
    "SSOT.RedisBestPractices": {
      "kind": "rule",
      "summary": "Redis operational safety defaults",
      "value": {
        "require_prefix": true,
        "ttl_required_for_ephemeral": true,
        "avoid_keys_command": true,
        "pipeline_batching": true
      }
    },
    "SSOT.RedisDefinitions": {
      "kind": "rule",
      "summary": "Redis store configuration and durability rules",
      "value": {
        "stores": {
          "main": {
            "port": 6379,
            "db": 0,
            "required_prefix": "system:",
            "retry_on_timeout": true
          },
          "safety": {
            "port": 6380,
            "db": 0,
            "required_prefix": "safety:",
            "retry_on_timeout": false
          }
        },
        "durability": {
          "main": {
            "mode": "AOF",
            "appendfsync": "everysec"
          },
          "safety": {
            "mode": "AOF",
            "appendfsync": "always"
          }
        }
      }
    },
    "SSOT.RedisDurability": {
      "kind": "alias",
      "summary": "Alias of SSOT.RedisDefinitions",
      "alias_of": "SSOT.RedisDefinitions"
    },
    "SSOT.RedisKeyCatalog": {
      "kind": "table",
      "summary": "Redis key patterns (authoritative)",
      "value": {
        "safety": {
          "heartbeat": "safety:heartbeat:{component_id}",
          "killswitch_state": "safety:killswitch:state",
          "killswitch_verification": "safety:killswitch:verification",
          "watchdog_state": "safety:watchdog:state",
          "alerts_active": "safety:alerts:active",
          "audit_log": "safety:audit:log"
        },
        "main": {
          "system_state": "system:state",
          "orch_components": "orch:components:{component_id}",
          "orch_state_history": "orch:state:history",
          "feature_req": "feature:req:{model_id}",
          "feature_resp": "feature:resp:{trace_id}",
          "feature_cache": "feature:cache:{bns_id}:{ts}",
          "buffer_registry": "buffer:registry:{buffer_id}",
          "statestore_intents_processed": "statestore:intents:processed:{id}",
          "statestore_orders": "statestore:orders:{cloid}",
          "statestore_orders_index": "statestore:orders:index",
          "statestore_positions": "statestore:positions:{instrument}",
          "statestore_positions_index": "statestore:positions:index",
          "statestore_meta_last_sequence": "statestore:meta:last_sequence",
          "cmd_executed": "cmd:executed:{command_id}",
          "bp_stats": "bp:stats:{component_id}",
          "bp_queue_usage": "bp:queue:usage:{queue_id}",
          "bp_conflation_count": "bp:conflation:count:{symbol}",
          "guarded_stage": "guarded:stage",
          "guarded_reason": "guarded:reason",
          "guarded_transition_ts_ns": "guarded:transition:ts_ns"
        }
      }
    },
    "SSOT.RedisStore": {
      "kind": "alias",
      "summary": "Alias of SSOT.RedisDefinitions",
      "alias_of": "SSOT.RedisDefinitions"
    },
    "SSOT.RemovalPolicy": {
      "kind": "ref",
      "summary": "Referenced by SDSL inputs"
    },
    "SSOT.ReplayPrevention": {
      "kind": "ref",
      "summary": "Referenced by SDSL inputs"
    },
    "SSOT.RoleHierarchy": {
      "kind": "table",
      "summary": "RBAC role hierarchy order",
      "value": ["OBSERVER", "TRADER", "OPERATOR", "ADMIN"]
    },
    "SSOT.RuntimeConfig": {
      "kind": "rule",
      "summary": "Runtime config authority and defaults",
      "value": {
        "location": "myplugins/shared/config/runtime.py",
        "sections": ["RetryConfig", "TimeoutConfig", "CircuitBreakerConfig", "WALFsyncConfig"],
        "timeout_defaults_sec": {
          "internal_api": 3.0,
          "control_plane": 30.0,
          "external_http": 5.0
        }
      }
    },
    "SSOT.SAFETY_HEARTBEAT_TTL_SEC": {
      "kind": "rule",
      "summary": "Safety heartbeat TTL in seconds (SSOT.SharedConstants)",
      "value": 6
    },
    "SSOT.SAFETY_PLANE": {
      "kind": "ref",
      "summary": "Referenced by SDSL inputs"
    },
    "SSOT.SCORE_RANGE_VALIDATION": {
      "kind": "ref",
      "summary": "Referenced by SDSL inputs"
    },
    "SSOT.SERIALIZATION": {
      "kind": "ref",
      "summary": "Referenced by SDSL inputs"
    },
    "SSOT.SHA256": {
      "kind": "rule",
      "summary": "SHA-256 hex digest constraints",
      "value": {
        "hex_length": 64,
        "hex_pattern": "^[0-9a-f]{64}$",
        "lowercase_only": true
      }
    },
    "SSOT.SHARED_CONSTANTS": {
      "kind": "alias",
      "summary": "Alias of SSOT.SharedConstants",
      "alias_of": "SSOT.SharedConstants"
    },
    "SSOT.SOURCE_OF_TRUTH": {
      "kind": "ref",
      "summary": "Referenced by SDSL inputs"
    },
    "SSOT.SSE_THROTTLING_POLICY": {
      "kind": "rule",
      "summary": "SSE throttle defaults",
      "value": {
        "max_msg_per_sec": 10,
        "conflate_events": ["market_tick", "position_update"],
        "no_drop_events": ["alert", "order_update", "system_status"]
      }
    },
    "SSOT.STARTUP_ORDER": {
      "kind": "ref",
      "summary": "Referenced by SDSL inputs"
    },
    "SSOT.STORAGE_CONFIG": {
      "kind": "rule",
      "summary": "Audit storage configuration",
      "value": {
        "primary": "postgres",
        "secondary": "redis_stream",
        "stream_key": "safety:audit:log",
        "stream_maxlen": 100000
      }
    },
    "SSOT.STORAGE_TIERING": {
      "kind": "rule",
      "summary": "Audit storage tiering",
      "value": {
        "hot": "postgres",
        "archive": "postgres_partition",
        "stream": "redis_stream",
        "archive_after_days": 90
      }
    },
    "SSOT.SYNCING_PHASE_RECON": {
      "kind": "ref",
      "summary": "Referenced by SDSL inputs"
    },
    "SSOT.SYSTEM_PHASES": {
      "kind": "ref",
      "summary": "Referenced by SDSL inputs"
    },
    "SSOT.SYSTEM_STATE_DERIVATION": {
      "kind": "ref",
      "summary": "Referenced by SDSL inputs"
    },
    "SSOT.SYSTEM_STATE_SCHEMA": {
      "kind": "ref",
      "summary": "Referenced by SDSL inputs"
    },
    "SSOT.SYSTEM_STATUS_FLOW": {
      "kind": "ref",
      "summary": "Referenced by SDSL inputs"
    },
    "SSOT.SafetyBootstrap": {
      "kind": "ref",
      "summary": "Referenced by SDSL inputs"
    },
    "SSOT.SafetyCommands": {
      "kind": "rule",
      "summary": "Safety plane command types and topics",
      "value": {
        "types": ["KILL_L0", "KILL_L1", "KILL_L2", "RESET", "STATUS", "MAINTENANCE"],
        "wire_values": ["L0", "L1", "L2", "RESET", "STATUS", "MAINTENANCE"],
        "topics": {
          "cmd": "safety:cmd",
          "ack": "safety:ack"
        }
      }
    },
    "SSOT.SafetyCriticalPolicy": {
      "kind": "ref",
      "summary": "Referenced by SDSL inputs"
    },
    "SSOT.SafetyExchangeClient": {
      "kind": "ref",
      "summary": "Referenced by SDSL inputs"
    },
    "SSOT.SafetyHeartbeat": {
      "kind": "rule",
      "summary": "Safety heartbeat key format",
      "value": {
        "key_pattern": "safety:heartbeat:{component_id}"
      }
    },
    "SSOT.SafetyPriorityOrder": {
      "kind": "ref",
      "summary": "Referenced by SDSL inputs"
    },
    "SSOT.SafetyRedisKeys": {
      "kind": "table",
      "summary": "Safety Redis key patterns",
      "value": {
        "heartbeat": "safety:heartbeat:{component_id}",
        "killswitch_state": "safety:killswitch:state",
        "killswitch_verification": "safety:killswitch:verification",
        "watchdog_state": "safety:watchdog:state",
        "alerts_active": "safety:alerts:active",
        "audit_log": "safety:audit:log"
      }
    },
    "SSOT.SafetySettings": {
      "kind": "rule",
      "summary": "Safety heartbeat timing defaults",
      "value": {
        "heartbeat_ttl_sec": 6,
        "heartbeat_interval_ms": 500
      }
    },
    "SSOT.SchemaIdStrict": {
      "kind": "rule",
      "summary": "Strict schema_id format (sha256:<64hex>)",
      "value": {
        "pattern": "^sha256:[0-9a-f]{64}$",
        "prefix": "sha256:"
      }
    },
    "SSOT.SecurityPolicy": {
      "kind": "ref",
      "summary": "Referenced by SDSL inputs"
    },
    "SSOT.SecurityValidation": {
      "kind": "rule",
      "summary": "Security validation defaults",
      "value": {
        "require_signature": true,
        "nonce_prefix": "nonce:used:",
        "nonce_ttl_sec": 300,
        "reject_replay": true
      }
    },
    "SSOT.SemVer": {
      "kind": "ref",
      "summary": "Referenced by SDSL inputs"
    },
    "SSOT.SerializationFormat": {
      "kind": "rule",
      "summary": "Serialization defaults",
      "value": {
        "format": "json",
        "sort_keys": true,
        "default_str": true,
        "encoding": "utf-8"
      }
    },
    "SSOT.SerializationMsgPack": {
      "kind": "ref",
      "summary": "Referenced by SDSL inputs"
    },
    "SSOT.ServiceLevelAgreement": {
      "kind": "ref",
      "summary": "Referenced by SDSL inputs"
    },
    "SSOT.SharedConstants": {
      "kind": "rule",
      "summary": "Shared infra constants (TTLs + system state schema)",
      "value": {
        "ttls_sec": {
          "safety_heartbeat": 6,
          "safety_killswitch_verification": 3600,
          "safety_audit_log": 604800,
          "feature_resp": 10,
          "system_state": 5,
          "bp_stats": 60
        },
        "system_state_schema": {
          "required_fields": [
            "phase",
            "entered_at_ns",
            "degradation_level",
            "trading_safe",
            "config_safe",
            "reason",
            "maintenance_mode",
            "maintenance_reason"
          ],
          "optional_fields": ["previous_phase", "operator_id"],
          "local_only_fields": ["component_health"]
        },
        "health_status_values": ["HEALTHY", "WARNING", "DEGRADED", "CRITICAL", "STOPPED"]
      }
    },
    "SSOT.SharedInfra": {
      "kind": "ref",
      "summary": "Referenced by SDSL inputs"
    },
    "SSOT.ShmCleanup": {
      "kind": "ref",
      "summary": "Referenced by SDSL inputs"
    },
    "SSOT.SignalGenerator": {
      "kind": "ref",
      "summary": "Referenced by SDSL inputs"
    },
    "SSOT.SignalTypes": {
      "kind": "ref",
      "summary": "Referenced by SDSL inputs"
    },
    "SSOT.SignatureConfig": {
      "kind": "rule",
      "summary": "Signature algorithm defaults",
      "value": {
        "algorithm": "HMAC-SHA256",
        "key_env_var": "SAFETY_SIGNING_KEY",
        "nonce_ttl_seconds": 300
      }
    },
    "SSOT.SignatureMiddleware": {
      "kind": "rule",
      "summary": "Signature/RBAC exempt paths",
      "value": {
        "signature_exempt_paths": [
          "/api/events/stream",
          "/api/v1/status",
          "/health",
          "/healthz",
          "/metrics",
          "/ready"
        ],
        "rbac_exempt_paths": ["/api/v1/status", "/health", "/healthz", "/metrics", "/ready"]
      }
    },
    "SSOT.SignatureStability": {
      "kind": "ref",
      "summary": "Referenced by SDSL inputs"
    },
    "SSOT.SigningLogic": {
      "kind": "ref",
      "summary": "Referenced by SDSL inputs"
    },
    "SSOT.StateManagement": {
      "kind": "rule",
      "summary": "State management defaults for restore/recovery",
      "value": {
        "checkpoint_restore": {
          "missing_checkpoint": "cold_start",
          "missing_strategy_state": "skip_and_warn",
          "restore_error": "log_and_continue"
        },
        "heartbeat_recovery": {
          "reset_miss_count_on_healthy": true
        },
        "init_state": {
          "allow_null_before_start": true
        }
      }
    },
    "SSOT.StoragePolicy": {
      "kind": "rule",
      "summary": "Storage mode defaults",
      "value": {
        "modes": ["single", "dual"],
        "default_mode": "dual"
      }
    },
    "SSOT.StreamRouter": {
      "kind": "rule",
      "summary": "StreamRouter interface expectations",
      "value": {
        "required_methods": [
          "load_bns_config",
          "register_runner",
          "route",
          "get_instruments_for_node"
        ],
        "init_flow": ["load_bns_config", "register_runner"]
      }
    },
    "SSOT.StructuredError": {
      "kind": "ref",
      "summary": "Referenced by SDSL inputs"
    },
    "SSOT.SystemArchitecture": {
      "kind": "rule",
      "summary": "System architecture layer model",
      "value": {
        "layers": [
          {
            "level": 7,
            "name": "Observation",
            "components": ["Collector", "Metrics", "Alerting"]
          },
          {
            "level": 6,
            "name": "Execution",
            "components": ["OrderManager", "PositionManager", "RiskGate"]
          },
          {
            "level": 5,
            "name": "Strategy",
            "components": ["StrategyExecutor", "SignalGenerator"]
          },
          {
            "level": 4,
            "name": "Models",
            "components": ["ModelRegistry", "InferenceEngine"]
          },
          {
            "level": 3,
            "name": "Features",
            "components": ["FeaturePipeline", "DataTransformers"]
          },
          {
            "level": 2,
            "name": "Data",
            "components": ["DataClient", "MarketDataAdapter"]
          },
          {
            "level": 1,
            "name": "Infrastructure",
            "components": ["Redis", "EventBus", "StateStore"]
          }
        ]
      }
    },
    "SSOT.SystemBootstrap": {
      "kind": "ref",
      "summary": "Referenced by SDSL inputs"
    },
    "SSOT.SystemStateKeys": {
      "kind": "ref",
      "summary": "Referenced by SDSL inputs"
    },
    "SSOT.TIMEOUT_HANDLER": {
      "kind": "rule",
      "summary": "Timeout handling defaults",
      "value": {
        "on_timeout": "FAIL",
        "error_code": "TIMEOUT",
        "retryable": false
      }
    },
    "SSOT.TIMESTAMP_NS_FORMAT": {
      "kind": "rule",
      "summary": "Timestamp field naming for UTC nanoseconds",
      "value": {
        "event_time_suffix": "_ts_ns",
        "lifecycle_time_suffix": "_at_ns",
        "generic_name": "timestamp_ns"
      }
    },
    "SSOT.TIMESTAMP_STANDARD": {
      "kind": "rule",
      "summary": "Canonical timestamp standard",
      "value": {
        "type": "int64",
        "unit": "ns",
        "timezone": "UTC"
      }
    },
    "SSOT.TLS_VERSION_REQUIREMENT": {
      "kind": "ref",
      "summary": "Referenced by SDSL inputs"
    },
    "SSOT.TOGGLE_DEFAULT_BEHAVIOR": {
      "kind": "ref",
      "summary": "Referenced by SDSL inputs"
    },
    "SSOT.TOPICS": {
      "kind": "rule",
      "summary": "Topic naming conventions",
      "value": {
        "standard_separator": ".",
        "alert_separator": ":",
        "standard_format": "{domain}.{category}.{id}",
        "alert_format": "alert:{type}",
        "validation_regex": {
          "data": "^data\\.[a-z_]+\\.[A-Z0-9]+-[A-Z]+-[A-Z]+\\.[A-Z]+$",
          "features": "^features\\.[a-z][a-z0-9_]*$",
          "predictions": "^predictions\\.[a-z][a-z0-9_]*$",
          "control": "^system\\.control\\.[a-z][a-z0-9_]*$",
          "error": "^system\\.error\\.[a-z][a-z0-9_]*$",
          "strategy": "^strategy\\.[a-z0-9_]+\\.[a-z]+$",
          "execution": "^execution\\.[a-z0-9_]+\\.[a-z]+$",
          "alert": "^alert:[a-z_]+$"
        },
        "categories": {
          "system": "^system\\.[a-z]+\\.[a-z_]+$",
          "data": "^data\\.[a-z_]+\\..+$",
          "features": "^features\\.[a-z][a-z0-9_]*$",
          "predictions": "^predictions\\.[a-z][a-z0-9_]*$",
          "strategy": "^strategy\\.[a-z0-9_]+\\.[a-z]+$",
          "execution": "^execution\\.[a-z0-9_]+\\.[a-z]+$",
          "alert": "^alert:[a-z_]+$"
        }
      }
    },
    "SSOT.TRADING_ALLOWED_STATES": {
      "kind": "ref",
      "summary": "Referenced by SDSL inputs"
    },
    "SSOT.TRADING_SAFE_MODE_CONSTRAINTS": {
      "kind": "ref",
      "summary": "Referenced by SDSL inputs"
    },
    "SSOT.TimeDefinitions": {
      "kind": "rule",
      "summary": "Canonical time definitions",
      "value": {
        "timezone": "UTC",
        "timestamp_type": "int64",
        "timestamp_unit": "ns",
        "string_format": "RFC3339",
        "field_suffixes": {
          "event_time": "_ts_ns",
          "lifecycle_time": "_at_ns",
          "generic": "timestamp_ns"
        },
        "allowed_precisions": ["ns", "us", "ms", "s"]
      }
    },
    "SSOT.TimeFormat": {
      "kind": "rule",
      "summary": "Canonical time string format",
      "value": {
        "format": "RFC3339",
        "timezone": "UTC"
      }
    },
    "SSOT.TimePrecision": {
      "kind": "rule",
      "summary": "Allowed time precision units",
      "value": {
        "units": ["ns", "us", "ms", "s"]
      }
    },
    "SSOT.TimeUtils": {
      "kind": "rule",
      "summary": "Time normalization utilities",
      "value": {
        "parse_format": "RFC3339",
        "normalize_to": "UTC",
        "to_ns": true,
        "from_ns": true,
        "reject_naive": true
      }
    },
    "SSOT.Timestamp": {
      "kind": "rule",
      "summary": "Timestamp scalar constraints",
      "value": {
        "type": "int64",
        "unit": "ns",
        "timezone": "UTC",
        "epoch": "Unix"
      }
    },
    "SSOT.TracePropagation": {
      "kind": "ref",
      "summary": "Referenced by SDSL inputs"
    },
    "SSOT.TypeError": {
      "kind": "ref",
      "summary": "Referenced by SDSL inputs"
    },
    "SSOT.UNCONFIRMED_ORDER_RECOVERY": {
      "kind": "ref",
      "summary": "Referenced by SDSL inputs"
    },
    "SSOT.UPDATE_INTERVALS": {
      "kind": "rule",
      "summary": "Dashboard update intervals",
      "value": {
        "critical_sec": 1,
        "realtime": "sse",
        "important_sec": 5,
        "info_sec": 10
      }
    },
    "SSOT.UTC_Timestamp": {
      "kind": "alias",
      "summary": "Alias of SSOT.Timestamp",
      "alias_of": "SSOT.Timestamp"
    },
    "SSOT.UUIDFormat": {
      "kind": "rule",
      "summary": "UUID v4 canonical format",
      "value": {
        "version": "v4",
        "pattern": "^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
        "lowercase_only": true
      }
    },
    "SSOT.ValidationErrors": {
      "kind": "ref",
      "summary": "Referenced by SDSL inputs"
    },
    "SSOT.WALDurabilityConfig": {
      "kind": "rule",
      "summary": "WAL durability configuration defaults",
      "value": {
        "execution_fsync_policy": "EVERY_WRITE",
        "feature_fsync_policy": "BATCH",
        "fsync_batch_size": 100,
        "fsync_batch_interval_ms": 100,
        "max_file_size_mb": 100,
        "max_file_age_hours": 1,
        "retain_rotated_files": 10,
        "checksum_algorithm": "crc32",
        "verify_on_read": true,
        "corrupt_entry_policy": "skip_and_warn",
        "fsync_policy_values": ["EVERY_WRITE", "BATCH", "OS_DEFAULT"]
      }
    },
    "SSOT.WAL_RETENTION_POLICY": {
      "kind": "rule",
      "summary": "WAL retention defaults",
      "value": {
        "max_file_size_mb": 100,
        "max_file_age_hours": 1,
        "retain_rotated_files": 10
      }
    },
    "SSOT.WAL_SSOT": {
      "kind": "rule",
      "summary": "WAL is the source of truth"
    },
    "SSOT.WatchdogConfig": {
      "kind": "rule",
      "summary": "Watchdog configuration defaults",
      "value": {
        "safety_redis_host": "localhost",
        "safety_redis_port": 6380,
        "heartbeat_interval_ms": 500,
        "heartbeat_timeout_ms": 5000,
        "l2_heartbeat_timeout_ms": 10000,
        "failsafe_enabled": true
      }
    },
    "SSOT.WatchdogLogic": {
      "kind": "rule",
      "summary": "Watchdog escalation levels",
      "value": {
        "levels": ["L0_SOFT_STOP", "L1_HARD_STOP", "L2_EMERGENCY"],
        "default_actions": ["BLOCK_NEW_ORDERS", "CLOSE_ALL_POSITIONS", "FULL_STOP"]
      }
    },
    "SSOT.WatchdogThreshold": {
      "kind": "rule",
      "summary": "Watchdog threshold defaults",
      "value": {
        "heartbeat_timeout_ms": 5000,
        "l2_heartbeat_timeout_ms": 10000
      }
    },
    "SSOT.WatchdogTimeout": {
      "kind": "rule",
      "summary": "Watchdog state TTL",
      "value": {
        "ttl_sec": 5
      }
    },
    "SSOT.WatchdogTriggerConfig": {
      "kind": "rule",
      "summary": "Watchdog trigger defaults",
      "value": {
        "heartbeat_miss_threshold": 3,
        "heartbeat_interval_ms": 500,
        "memory_critical_percent": 95.0,
        "cpu_critical_percent": 98.0,
        "error_rate_threshold": 10.0,
        "error_rate_window_sec": 60
      }
    },
    "SSOT.get_main_redis": {
      "kind": "ref",
      "summary": "Referenced by SDSL inputs"
    }
  },
  "enums": {
    "SSE_AUTH_MODE": [
      "NONE",
      "QUERY_TOKEN",
      "API_KEY",
      "SESSION",
      "MTLS"
    ]
  }
} as const;

export const SSOT_META = SSOT_DEFINITIONS.meta;

export type SsotToken = keyof typeof SSOT_DEFINITIONS["tokens"];
export type SseAuthMode = (typeof SSOT_DEFINITIONS)["enums"]["SSE_AUTH_MODE"][number];
