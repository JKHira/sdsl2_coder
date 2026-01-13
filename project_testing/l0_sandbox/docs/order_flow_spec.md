# Order Flow Spec

## Decisions
EDGE_INTENT_01: EXTERNAL_CLIENT -> ORDER_API (call) CONTRACT.SubmitOrder
EDGE_INTENT_02: ORDER_API -> INVENTORY_SERVICE (call) CONTRACT.ReserveInventory
EDGE_INTENT_03: ORDER_API -> PAYMENT_FULFILLMENT (call) CONTRACT.PayAndCreateFulfillment

## Notes
Single-step sync flow for L1/L2 trial.
