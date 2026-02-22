# Every API step can be done manually

## Status
Accepted

## Context
Users may not want to use the API for every step, especially for small preps (3 episodes).

## Decision
The user can copy the prompts, run them in their own AI chat, and paste results back. The tool never forces an API call when the user has another way to get the same artifact. Non-API parts (packaging, rendering) handle the rest.

## Consequences
The tool is usable without an API key for small preps. Prompts must be self-contained and renderable.
