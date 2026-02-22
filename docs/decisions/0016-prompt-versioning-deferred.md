# Prompt versioning deferred

## Status
Accepted

## Context
Could track prompt hashes to detect when prompts change and auto-regenerate stale outputs.

## Decision
Defer. Re-generation cost ($5-30) is low enough that "just regenerate" is acceptable. Hash tracking adds complexity for minimal benefit at this stage.

## Consequences
Revisit if prompt iteration becomes frequent. For now, manual `--force` regeneration is sufficient.
