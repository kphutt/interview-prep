# Episode count is dynamic

## Status
Accepted

## Context
Episode count was hardcoded to 15 (12 core + 3 frontier). Different prep timelines need different amounts of content.

## Decision
Episode count is determined by timeline + scope, not hardcoded. Interview tomorrow = 3 episodes. Month out = 12+.

## Consequences
Pipeline must derive all state (batch sizes, gem slots, manifest) from episode counts dynamically.
