# Onboarding Friction — Brainstorm

**Author**: Karsten Huttelmaier — co-authored with Claude

Vision: collapse `init` → edit → `setup` → `all` down to `init` → edit → `all`.

## Friction points identified

### 1. `adapt` was a confusing name (DONE — renamed to `setup`, decision 0020)

Users don't know what "adapt" means. "Setup" is self-descriptive.

### 2. `all` errored instead of auto-running setup (DONE — Phase 1)

New users hit a preflight error telling them to run a command they haven't heard of. Now `all` detects stub domain files and auto-runs `setup`.

### 3. Profile template doesn't explain what the body is for

The init template body says "Add any extra context here" — doesn't mention job descriptions or explain that the body directly feeds `setup` and significantly improves output quality.

### 4. README Quick Start is misleading

"Browse the reference profile (free, no API key)" is the first section but immediately shows commands that require an API key (`all --profile my-domain`). Users copy-paste and hit errors.

### 5. No progress during API calls

`call_llm` can take 30-90s per call with no output beyond the initial "-> MODEL: label..." line. Users think the pipeline is hung.

### 6. No cost summary after runs

There's a cost confirmation before runs but no summary after. Users can't compare estimate vs actual or budget for future runs.

## Edge case analysis (Phase 1: auto-setup)

- **`--force` behavior**: `cmd_all(force=True)` does NOT force-regenerate domain files. Setup is $5-10, a separate concern. Users who want to re-setup use `setup --force` directly.
- **`_DOMAIN` reload**: After auto-setup, `_DOMAIN` global must be reloaded via `_load_domain()`. This is the only global that depends on domain file content — all other globals come from `profile.md` config or env vars.
- **Partial failure**: If `cmd_setup` returns `False` (API failure), `cmd_all` stops before syllabus. If setup "succeeds" but some files are still stubs (partial write), the post-setup verify catches this.
- **Partial domain files**: `_needs_setup()` returns True if *any* file is a stub. The `cmd_setup` skip-existing logic handles the case where some files exist and others don't.
- **`--yes` passthrough**: The combined cost confirmation in `main()` covers setup+syllabus+content. No second prompt inside `cmd_all`.

## Hidden bottlenecks discovered

- README Quick Start has a broken happy path (first section requires API key despite "free" label)
- `docs/design/workflow.md` had stale "adapted/" references (from decision 0015→0019 rename cycle)
- `prompts/gem.md` referenced "adapted/" directory name
