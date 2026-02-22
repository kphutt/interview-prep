# Per-episode syllabus regeneration deferred

## Status
Accepted

## Context
The batch sequence (scaffold -> core batches -> frontier -> merge) generates episodes in groups of 4. Regenerating one episode means re-running its batch, which affects sibling episodes.

## Decision
Defer single-episode syllabus regeneration. Content `--episode N` is supported (each content episode is an independent API call), but syllabus is batch-only.

## Consequences
Revisit if users frequently need single-episode syllabus fixes.
