# 0020: Rename adapt to setup

**Status:** Accepted

## Context

Decision 0014 originally named the domain generation command "setup". It was later renamed to "adapt" (decisions 0015, 0019). In practice, "adapt" confuses new users — it's not self-descriptive and adds a mandatory step that interrupts the init→all flow.

## Decision

1. Rename `adapt` → `setup` in all user-facing strings, functions, tests, documentation, and raw output filenames.
2. The `all` command auto-runs `setup` when domain files are stubs, collapsing the new user flow to `init` → edit profile → `all`.
3. `--force` on `all` does NOT force-regenerate domain files (setup is $5-10, a separate concern).
4. Only `all` gets auto-setup; `syllabus`/`content` keep existing preflight error behavior.

## Consequences

- New users don't need to know `setup` exists as a separate command.
- Existing users see no regression — `all` skips setup when domain files exist.
- The word "adapt" no longer appears in any user-facing output or code (only in historical decision docs).
