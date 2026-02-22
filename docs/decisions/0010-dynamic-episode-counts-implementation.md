# Dynamic episode counts implementation

## Status
Accepted

## Context
Decision 0005 established that episode counts should be dynamic. This records the implementation approach.

## Decision
`PREP_CORE_EPISODES` (default 12) and `PREP_FRONTIER_EPISODES` (default 3) env vars control counts. All derived state (`CORE_EPS`, `FRONTIER_EPS`, `ALL_EPS`, `SYLLABUS_RUNS`, gem slots, manifest) is regenerated from these. `_reconfigure(core, frontier)` atomically resets all derived state. Batch size stays at 4, gem pairing at 2.

## Consequences
With no env vars set, output is identical to previous hardcoded behavior. All new functions take explicit parameters with defaults.
