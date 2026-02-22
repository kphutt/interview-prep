# Rename adapted/ back to domain/

## Status
Accepted (supersedes 0015)

## Context
"Adapted" was confusing — sounds like a past-tense verb, not a noun. The directory holds domain-specific content chunks (seeds, coverage framework, lenses, gem sections) that get injected into prompt templates.

## Decision
Rename back to `domain/`. Reads naturally under `profiles/{name}/domain/`.

## Consequences
Simpler, more intuitive name. Supersedes decision 0015.
