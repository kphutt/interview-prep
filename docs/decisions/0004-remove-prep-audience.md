# PREP_AUDIENCE probably goes away

## Status
Accepted

## Context
"Audience" was ambiguous — candidate? interviewer? podcast listener? Resume captures who the candidate is, PREP_ROLE captures the target.

## Decision
The gap between resume and role IS the calibration. PREP_AUDIENCE is not needed as a separate concept.

## Consequences
One fewer env var to configure. Calibration is implicit from resume + role.
