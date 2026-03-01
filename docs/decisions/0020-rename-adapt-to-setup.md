# 0020: Rename adapt to setup

**Status:** Accepted

## Context

Decision 0014 originally named the domain generation command "setup". It was later renamed to "adapt" (decisions 0015, 0019). In practice, "adapt" confuses new users — it's not self-descriptive and adds a mandatory step that interrupts the init→all flow.

## Decision

1. Rename `adapt` → `setup` in all user-facing strings, functions, tests, and documentation.
2. The `all` command auto-runs `setup` when domain files are stubs, collapsing the new user flow to `init` → edit profile → `all`.
3. Raw output filenames (`adapt-1-seeds.md`, `adapt-2-lenses.md`, `adapt-3-gem.md`) are preserved for backwards compatibility with existing profiles.
4. `--force` on `all` does NOT force-regenerate domain files (setup is $5-10, a separate concern).
5. Only `all` gets auto-setup; `syllabus`/`content` keep existing preflight error behavior.

## Consequences

- New users don't need to know `setup` exists as a separate command.
- Existing users see no regression — `all` skips setup when domain files exist.
- The word "adapt" no longer appears in any user-facing output (only in raw filenames and historical decision docs).
