# Hand-parse YAML frontmatter, no pyyaml

## Status
Accepted

## Context
profile.md uses YAML frontmatter for config. Could add pyyaml as a dependency.

## Decision
Hand-parse with case-insensitive key matching and optional quoting. Keeps the zero-dependency philosophy.

## Consequences
If frontmatter complexity grows later, reconsider adding pyyaml. For now, simple `key: value` lines are sufficient.
