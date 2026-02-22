# Smart NotebookLM prompt requires validation

## Status
Accepted

## Context
Decision 0001 assumes a single smart prompt produces sufficient format variety without per-episode frames.

## Decision
Must validate with 3-5 existing episodes before eliminating frames. If validation fails, keep frames but make them domain-injectable.

## Consequences
Validation gate before fully removing frames. Risk of reverting to per-episode frames if variety is insufficient.
