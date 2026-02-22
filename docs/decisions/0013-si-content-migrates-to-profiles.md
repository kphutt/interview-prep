# S&I content migrates to profiles/security-infra/

## Status
Accepted

## Context
Existing Security & Infrastructure outputs lived at the repo root in `outputs/`. The profile system needed a reference example.

## Decision
Move existing `outputs/` to `profiles/security-infra/outputs/` via `git mv`. Provides a complete profile example.

## Consequences
S&I becomes the reference profile. New users can see what a finished profile looks like.
