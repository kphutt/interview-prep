# Rename generate-prompts command to setup

## Status
Accepted

## Context
The `generate-prompts` command generates domain injection fragments (seeds.md, coverage.md, lenses.md, gem-sections.md), not prompts. The name was misleading.

## Decision
Rename to `setup`. Implemented as a single API call using `prompts/setup.md`.

## Consequences
Clearer command name. One API call instead of three meta-prompt calls from Phase 5.2.
