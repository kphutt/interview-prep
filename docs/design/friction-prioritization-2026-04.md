# Friction prioritization — 2026-04

Grounded in `docs/design/friction-audit-reconciliation-2026-04.md`. Every citation below comes from that file.

Mission frame: "Friends can clone the repo, follow the README, and produce a working Gem and NotebookLM set without hitting a dead end."

## Category A: Overstated-done items

### A1: `status --profile` doesn't check API key

- Friction: The `status --profile` branch returns at `prep.py:1141` before `_show_pipeline_status` runs, so the `API key: set/NOT SET` line at `prep.py:1061` is skipped. Plain `status` shows it; the profile path doesn't.
- Mission impact: A friend verifying their setup with `status --profile X` gets a clean-looking pipeline checklist with no hint that their key is missing or typo'd — they only discover it when the first API command fails.
- Effort: S
- Touches: `prep.py:1107-1141` (add key status line to the profile branch), optionally `prep.py:1032` (refactor `_show_pipeline_status` to share logic).
- Recommendation: **complete the fix**. Revising the ROADMAP claim is also S, but the fix itself is trivial and mission-aligned; revising alone leaves a real gap for a named user path.

### A2: `main()` discards `cmd_content`'s return value

- Friction: `cmd_content` at `prep.py:818` returns `fail == 0`, but `main()` at `prep.py:1492` ignores the result. Shell exit is 0 even when episodes failed, despite ROADMAP listing "Partial failure exit codes ✅" as done.
- Mission impact: A friend scripting `all --yes` followed by downstream steps (or a CI smoketest) sees exit 0, proceeds to `package`, and ships a Gem with gaps.
- Effort: S
- Touches: `prep.py:1492` (propagate via `sys.exit(1)` on False; same treatment for `cmd_all` at `prep.py:1487`).
- Recommendation: **complete the fix**. Revising ROADMAP would cost roughly the same; propagating the exit code is one-line and matches what ROADMAP already asserts.

## Category B: Still-valid friction

### B1: Step 3 Low — no guidance on what makes a good `domain` value

- Friction: Init template body at `prep.py:1279-1294` just says `"Add any extra context here."` with no sizing or quality guidance for `domain:`.
- Mission impact: A friend who writes `domain: Engineering` (too broad) or `domain: OAuth token binding for mobile apps` (too narrow) silently gets a suboptimal syllabus — they spend $30+ on content before noticing, and the failure mode is "output looks fine but misses" rather than a hard error.
- Effort: S
- Touches: `prep.py:1279-1294`.

### B2: Step 7 Medium — no incremental cost tracking

- Friction: `cmd_content` at `prep.py:776-818` tracks `gen/skip/warn/fail` counters but no per-episode cost. Upfront estimate at `prep.py:1179` is the only cost signal.
- Mission impact: Content generation is the single most expensive phase of the flow (~$30 at default settings per the audit). A friend whose run fails at episode 12/15 has no idea whether they spent $5 or $25, which makes them cautious about retries and creates a cost-anxiety barrier to completing the flow.
- Effort: M
- Touches: `prep.py:776-818` (per-episode token usage already logged at `prep.py:488`, needs aggregation + post-run summary).

### B3: Step 5 Low — `--yes` flag unknown to first-time users

- Friction: `_confirm_cost` prompt at `prep.py:1186` says `"Proceed? [Y/n] "` without mentioning the `--yes` flag.
- Mission impact: A friend running the pipeline the first time hits a prompt mid-flow with no hint that automation is available. Low-stakes but directly on the happy path; trivial to fix.
- Effort: S
- Touches: `prep.py:1179-1189`.

## Category C: Changed friction

### C1: Step 4 High — setup parse failure guidance

- Friction: Reconciliation confirmed the error messaging shape has changed (per-marker warnings at `prep.py:930-946` and per-call raw saves at `prep.py:989, 1002, 1018`), but the underlying gap — no actionable guidance when the LLM returns malformed output — persists.
- Mission impact: `setup` is the first API call a friend makes. A bad parse here strands them at the start of the flow with warnings but no fix path. Despite the reduced severity label, its *position* in the flow keeps it mission-critical.
- Effort: M
- Touches: `prep.py:930-946` (enrich warnings with expected marker list and pointer to the specific raw file).

Step 1 Medium (env var validation) partially overlaps with A1 — A1 is the cheaper half-fix. Step 1 Low (fish/Windows) and Step 5 Medium (agenda parse warnings) do not warrant dedicated action this cycle; their reduced severity reflects real improvements.

## Category D: New findings

| # | Finding | Classification |
|---|---------|----------------|
| D1 | `main()` discards `cmd_content` return value (`prep.py:1492`) | Covered by A2 — not double-counted |
| D2 | `status --profile` skips API key line (`prep.py:1107-1141`) | Covered by A1 — not double-counted |
| D3 | `_preflight_check` doesn't check API key (`prep.py:223-245`) | **Actionable friction** |
| D4 | `cmd_all` doesn't print syllabus review checklist (`prep.py:1386`, `prep.py:1488-1491`) | Observation (design tension: `all` is end-to-end, inserting a checklist mid-flow doesn't gate anything) |
| D5 | `cmd_init` doesn't validate profile name beyond existence (`prep.py:1264-1269`) | **ROADMAP correction** — reconciliation couldn't locate the claimed validation; audit/verify ROADMAP claim rather than add code |
| D6 | `_write_domain_file` writes partial files that defeat `_is_stub` (`prep.py:930-946`, `prep.py:209-214`) | Observation (edge case off the happy path; only triggers on malformed LLM output) |

### Recommended actionable from D

**D3: Check API key in `_preflight_check`.** Friction: preflight validates domain and prompt files but not the key, so a friend with a typo'd key sits through cost confirmation and prompt-loading before failing at `get_client`. Mission impact: fails fast before any work is done, reinforces A1 with a hard check on API command paths. Effort: S. Touches: `prep.py:223-245`.

## Cross-category observation

**Opinion — if forced to pick three for this cycle:** A1, A2, and B1. Rationale: all three are S-effort, all three sit on the named happy path a cloning friend follows, and together they close the gap between what ROADMAP claims is done and what code actually does (A1, A2) plus the one silent-quality-failure entry point that can't be caught downstream (B1 — a bad `domain:` value degrades every subsequent artifact). The larger items (B2 cost tracking, C1 setup parse guidance) are higher-ceiling but M-effort and less clearly blocking; they belong in a second cycle.
