# P4_T_OPERATION Edge Facts Notes

Edge 1:
- from: P4_T_OPS_OPERATIONS_SERVICE
- to: P4_T_RCF_RECONCILIATION_SCHEDULER
- direction: call
- contract_refs: CONTRACT.SYSTEM_PHASE
- evidence:
  - @Function.P4_T_RCF_OPS_ON_STATE_CHANGE calls scheduler.on_syncing_complete()/on_killswitch_reset()
  - @Rule.P4_T_RCF_RECOVERY_READY includes CONTRACT.SYSTEM_PHASE

Edge 2:
- from: P4_T_RCF_RECONCILIATION_SCHEDULER
- to: P4_T_RCF_POSITION_RECONCILER
- direction: call
- contract_refs: CONTRACT.SYSTEM_STATE
- evidence:
  - ReconciliationScheduler holds reconciler: PositionReconciler and runs reconciliation
  - @Rule.P4_T_RCF_PUBSUB_CATCHUP / @Rule.P4_T_RCF_PUBSUB_FIX include CONTRACT.SYSTEM_STATE

Edge 3:
- from: P4_T_AER_ADMIN_ROUTER
- to: P4_T_AER_MASTER_RELOAD_CHANNEL
- direction: pub
- contract_refs: CONTRACT.MASTER_RELOAD_CHANNEL
- evidence:
  - @Function.P4_T_AER_ADMIN_RELOAD_MASTER_TABLE uses redis.publish(MASTER_RELOAD_CHANNEL, "reload")
  - @Rule.P4_T_AER_MASTER_RELOAD includes CONTRACT.MASTER_RELOAD_CHANNEL
