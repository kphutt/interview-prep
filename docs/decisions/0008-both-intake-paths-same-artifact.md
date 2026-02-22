# Both intake paths produce the same artifact

## Status
Accepted

## Context
Users can either run the AI intake interview or manually fill out their profile.

## Decision
Whether AI-interviewed or manually filled, `profile.md` has the same format. prep.py consumes it the same way.

## Consequences
No branching logic needed in the pipeline. One input format regardless of how it was created.
