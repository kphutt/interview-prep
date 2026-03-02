# Plan: Profiles, Intake, and Dynamic Pipeline — DONE

**Last updated: Feb 17, 2026**

Cross-references: [brainstorm.md](brainstorm.md) | [decisions](../../decisions/) | [ROADMAP](../../../ROADMAP.md)

---

## Status overview

| Phase | Description | Status |
|-------|-------------|--------|
| 0 | Lock down current behavior (tests) | Done |
| 1 | Dynamic episode counts | Done |
| 2 | Template unification + syllabus adaptation | Done |
| 3 | Profile directory + config | Done |
| 4 | Domain-agnostic prompts | Done |
| 5 | `adapt` command + `domain/` rename | Done |

Side quests:
- Smoke test: dry-run mode, test prompts, input/output display (done)
- Model-agnostic API calls (done)

---

## Phase 0 — Lock down current behavior [DONE]

Added ~15 regression tests that assert hardcoded 12+3 behavior before refactoring. These became the guard rails for Phase 1.

**Tests added:**

| Class | Tests | What they assert |
|-------|-------|-----------------|
| `TestRenderTemplate` | `test_substitutes_all_placeholders`, `test_leaves_unknown_placeholders` | All 5 PREP_* and AS_OF_DATE placeholders replaced; unknowns pass through |
| `TestCmdStatusOutput` | `test_lists_all_episodes`, `test_lists_gem_slots`, `test_shows_missing_marker` | Status output contains ep 01-15, gem-1 through gem-8, missing episodes marked |
| `TestWriteManifestFormat` | `test_agenda_total_format`, `test_content_total_format`, `test_all_present_message` | Manifest shows "X/15" format and "all 15 episodes present" |
| `TestPackageGemScaffold` | `test_scaffold_copied_to_gem0`, `test_final_merge_copied_to_gem0` | scaffold.md and final_merge.md copied to gem-0-* |
| Additions to existing | `test_header_says_8_runs`, `test_total_distinct_slots_is_8`, `test_core_maps_to_exactly_6_slots` | Syllabus header, gem slot coverage |

---

## Phase 1 — Dynamic episode counts [DONE]

Env vars `PREP_CORE_EPISODES` (default 12) and `PREP_FRONTIER_EPISODES` (default 3) control episode counts. All derived state recomputed dynamically.

**What was built (9 items across 8 TDD steps):**

1. **Config constants** — `_CORE_COUNT`, `_FRONTIER_COUNT` from env vars; `CORE_EPS`, `FRONTIER_EPS`, `ALL_EPS` derived
2. **`build_syllabus_runs(core, frontier, batch_size=4)`** — generates the SCAFFOLD → CORE_BATCH → FRONTIER_DIGEST → FINAL_MERGE sequence dynamically. Default output matches original 8-run list exactly
3. **`frontier_map()`** — maps letters to episode numbers (e.g., `{"A": 13, "B": 14, "C": 15}`). Updated `parse_agendas()` and `cmd_syllabus()` to use it
4. **Dynamic `gem_slot(ep)`** — `ceil(core/2)` core slots + optional frontier slot + misc slot. Takes explicit params with defaults
5. **`_total_gem_slots()`** — drives `cmd_package()`, `cmd_status()`, and CLI `--gem-slot` choices
6. **Dynamic `cmd_syllabus` header** — prints `f"{len(SYLLABUS_RUNS)} runs"` instead of hardcoded "8 runs"
7. **Dynamic `write_manifest()`** — uses `len(ALL_EPS)` instead of hardcoded 15
8. **Updated Phase 0 tests** — replaced hardcoded "15" assertions with `len(prep.ALL_EPS)`
9. **`_reconfigure(core, frontier)`** — atomically resets all module-level derived state (used by tests)

**Verification:** 170 tests, all pass. Smoke test passes with `PREP_CORE_EPISODES=1 PREP_FRONTIER_EPISODES=0`.

**Decision recorded:** [decision 0010](../../decisions/0010-dynamic-episode-counts-implementation.md)

---

## Phase 2 — Template unification + syllabus adaptation [DONE]

**Goal:** Unify all prompts on `.replace()` substitution (decision #11) and make `prompts/syllabus.md` work with dynamic episode counts so the prompt doesn't hardcode "Episodes 1-12" and "Frontier Digests 13-15".

**Resolved open questions:**
- Q5 (dynamic episode count) — resolved by Phase 1
- Q11 (gem slot math) — resolved by Phase 1

### Steps

#### 2.1: Switch syllabus.md from `.format()` to `.replace()`

`syllabus_prompt()` (`prep.py:238-245`) currently uses `t.format(...)`. Switch to chained `.replace()` calls to match `content.md` and `distill.md`. Placeholder syntax stays as `{NAMED}` — only the substitution engine changes.

**Why now:** Phase 4 injects domain content that may contain `{braces}` (code examples, JSON). `.format()` would choke on these. Switching to `.replace()` in Phase 2 prevents this entirely. (Decision #11.)

**What changes:**
- `prep.py:238-245` — `syllabus_prompt()` switches from `.format(**kwargs)` to `.replace("{KEY}", value)` chains
- `render_template()` (`prep.py:268-276`) already uses `.replace()` — no change needed
- Existing tests for `syllabus_prompt()` continue to pass (output unchanged)

**Tests:**
- `test_syllabus_prompt_with_braces_in_content` — injecting `{curly braces}` into a field doesn't raise
- `test_syllabus_prompt_output_unchanged` — with default inputs, output is byte-identical to pre-change

#### 2.2: Add count placeholders to syllabus.md

Add these placeholders to `prompts/syllabus.md`:

| Placeholder | Example value | Replaces |
|-------------|---------------|----------|
| `{TOTAL_CORE}` | `12` | Hardcoded "12" in mode descriptions |
| `{TOTAL_FRONTIER}` | `3` | Hardcoded "3" |
| `{CORE_RANGE}` | `1-12` | "Episodes 1-12" |
| `{FRONTIER_RANGE}` | `13-15` | "Frontier Digests 13-15" |
| `{LISTENING_ORDER}` | interleaved string | Line 74 |
| `{FRONTIER_MAP}` | `Digest A = Episode 13, ...` | Lines 48-51 |

**Affected lines in `prompts/syllabus.md`:**
- Line 23: "Episodes 1-12" → "Episodes 1-{TOTAL_CORE}"
- Line 37: "specified CORE_EPISODES range (1-4 OR 5-8 OR 9-12)" → dynamic
- Lines 48-51: "Digest A = Episode 13" → `{FRONTIER_MAP}`
- Line 74: listening order → `{LISTENING_ORDER}`

**Watch out:** Lines 117-238 (training data) contain literal text. `.replace()` only replaces exact placeholder matches, so unlike `.format()` there's no risk of stray `{` breaking things.

#### 2.3: Update syllabus_prompt() to pass count values

Add the new placeholders to the `.replace()` chain in `syllabus_prompt()`. Values come from module-level state (`_CORE_COUNT`, `CORE_EPS`, `FRONTIER_EPS`).

**Tests:**
- `test_syllabus_prompt_contains_dynamic_ranges` — with `_reconfigure(8, 2)`, prompt contains "1-8" not "1-12"
- `test_syllabus_prompt_default_matches_current` — with 12+3, output unchanged from current
- `test_listening_order_format` — correct interleaving string
- `test_no_stray_placeholders` — no unreplaced `{TOTAL_*}` or `{CORE_*}` in output

#### 2.4: Leave training data alone

Lines 117-238 (domain-specific episode seeds) stay as-is. Addressed by Phase 4. Count placeholders don't affect this section.

**Not in scope:** `content.md` and `distill.md` have no count-specific references — they operate on a single episode and already use `.replace()`.

---

## Phase 3 — Profile directory + config [DONE]

**Goal:** Multiple prep profiles coexist. Each profile has its own config, inputs, and outputs. The existing env-var workflow still works when no `--profile` is specified.

**Resolved open questions:**
- Q2 (profile.md format) — Markdown with YAML frontmatter (decision #12)
- Q3 (how prep.py reads profiles) — set module-level vars from profile config, same vars existing code already reads
- Q6 (phasing) — this IS the minimum viable change
- YAML parsing dependency — hand-parse, no pyyaml (decision #12). Frontmatter is simple `key: value` lines; zero-dep philosophy maintained.

### Directory structure

```
profiles/
  security-infra/              # migrated from current outputs/ (decision #13)
    profile.md                 # structured config
    inputs/                    # JD, notes, context docs
      job-description.md
      notes.md
      context/
    domain/                   # generated by `setup` command (decision #15)
    outputs/                   # generated content
      syllabus/
      episodes/
      gem/
      notebooklm/
      raw/
```

### profile.md format

```markdown
---
role: "Staff Security Engineer"
company: "Google"
domain: "Security & Infrastructure"
audience: "Senior Software Engineers"
core_episodes: 12
frontier_episodes: 3
model: "gpt-5.2-pro"
effort: "xhigh"
---

## Interview schedule
- 2026-03-01: System Design (Security architecture, threat modeling)
- 2026-03-01: Coding (Security-flavored scripting)
- 2026-03-01: Behavioral (Leadership, cross-team influence)

## Notes
Any extra context for the meta-prompt...
```

### Steps

#### 3.1: `load_profile(name)` with validation

Reads `profiles/{name}/profile.md`, parses YAML frontmatter, sets module-level config vars.

**Parsing rules (decision #12 — no pyyaml):**
- Hand-parse `---` delimited frontmatter
- Case-insensitive key matching (`Role:` and `role:` both work)
- Values with or without quotes (`role: "Staff SWE"` and `role: Staff SWE`)
- Flexible whitespace

**Validation:**
- Required fields: `role`, `company`, `domain`. Error if missing.
- Known fields: `role`, `company`, `domain`, `audience`, `core_episodes`, `frontier_episodes`, `model`, `effort`. Warn on unrecognized keys: `WARNING: unknown field 'roll' in profile.md — did you mean 'role'?`
- Type checks: `core_episodes` and `frontier_episodes` must be positive integers.

**Config priority (highest wins), with warnings:**
1. CLI flags (`--model`, `--effort`)
2. Profile config (`profile.md` frontmatter)
3. Environment variables (`OPENAI_MODEL`, `PREP_ROLE`, etc.)
4. Defaults in code

When a higher-priority source overrides a lower one, print: `Using model=gpt-5.2-pro from profile (overrides OPENAI_MODEL=gpt-4.1-mini from environment)`.

**Error behavior:**
- Missing profile directory: `ERROR: profile 'my-prep' not found at profiles/my-prep/`
- Missing profile.md: `ERROR: profiles/my-prep/profile.md not found. Run 'python prep.py init my-prep' first.`
- Missing required field: `ERROR: profile.md missing required field 'role'.`
- Invalid type: `ERROR: core_episodes must be a positive integer, got 'twelve'.`

**Tests:**
- `test_load_profile_sets_vars` — loading a profile overrides ROLE, COMPANY, etc.
- `test_load_profile_falls_back_to_env` — missing fields use env vars
- `test_load_profile_not_found` — clear error message with path
- `test_load_profile_case_insensitive_keys` — `Role:` and `role:` both work
- `test_load_profile_unquoted_values` — values without quotes parse correctly
- `test_load_profile_warns_unknown_keys` — unrecognized key prints warning
- `test_load_profile_validates_required_fields` — missing `role` raises error
- `test_load_profile_validates_episode_counts` — non-integer episode count raises error
- `test_config_priority_warning` — override prints warning message

#### 3.2: `--profile` CLI flag + `set_profile()` mechanism

Add `--profile {name}` to argparse (`prep.py:690-699`). When set, call `set_profile(name)` before any command.

**`set_profile(name)` function:**
1. Call `load_profile(name)` to read config and set PREP_* vars
2. Reassign all directory constants atomically (same pattern as `_reconfigure()` at `prep.py:108`):
   - `SYLLABUS_DIR` → `profiles/{name}/outputs/syllabus/`
   - `EPISODES_DIR` → `profiles/{name}/outputs/episodes/`
   - `GEM_DIR` → `profiles/{name}/outputs/gem/`
   - `NLM_DIR` → `profiles/{name}/outputs/notebooklm/`
   - `RAW_DIR` → `profiles/{name}/outputs/raw/`
   - `IN_AGENDAS` → `profiles/{name}/inputs/`
   - `IN_EPISODES` → `profiles/{name}/inputs/`
3. Call `_reconfigure(core, frontier)` if profile overrides episode counts

**Call order in `main()`:**
```
parse args → set_profile() (if --profile) → ensure_dirs() → dispatch command
```

**Tests:**
- `test_cli_accepts_profile_flag` — parses without error
- `test_set_profile_redirects_all_dirs` — every directory constant points to profile path
- `test_set_profile_calls_reconfigure` — episode count overrides trigger _reconfigure
- `test_no_profile_uses_default_dirs` — existing behavior unchanged

#### 3.3: Output directory redirection for all commands

With `set_profile()` redirecting directory constants, verify every command works with profile-specific paths. These functions use module-level constants and should work without code changes IF `set_profile()` runs first, but each needs verification and a test:

| Function | Line | What to verify | Test |
|----------|------|----------------|------|
| `cmd_add` | 536 | Writes to redirected SYLLABUS_DIR, EPISODES_DIR, NLM_DIR; appends to correct gem file (line 562 append mode targets right profile) | `test_add_writes_to_profile_dirs` |
| `recover_agendas_from_raw` | 333 | Reads from redirected RAW_DIR | `test_recover_uses_profile_raw_dir` |
| `write_manifest` | 597 | Writes manifest to redirected OUTPUTS dir | `test_manifest_written_to_profile_dir` |
| `find_agenda` | 321 | Searches redirected IN_AGENDAS then SYLLABUS_DIR | `test_find_agenda_searches_profile_dirs` |
| `find_content` | 327 | Searches redirected IN_EPISODES then EPISODES_DIR | `test_find_content_searches_profile_dirs` |
| `ensure_dirs` | 313 | Creates all redirected directories | `test_ensure_dirs_creates_profile_structure` |
| `cmd_syllabus` | — | Writes to redirected SYLLABUS_DIR and RAW_DIR | `test_syllabus_outputs_to_profile` |
| `cmd_content` | — | Reads from redirected dirs, writes to EPISODES_DIR | `test_content_outputs_to_profile` |
| `cmd_package` | — | Reads from redirected dirs, writes to GEM_DIR and NLM_DIR | `test_package_outputs_to_profile` |

**Cross-profile safety:** `cmd_add` (line 562) opens gem files in append mode. With `set_profile()`, the path is `profiles/{name}/outputs/gem/gem-N-...`. Verify no scenario where `--profile A` appends to profile B's file. Add test: `test_add_no_cross_profile_contamination`.

#### 3.4: `cmd_init(name)` — create profile with guidance

Creates `profiles/{name}/` directory structure and a template `profile.md`.

```bash
python prep.py init my-prep
```

**Output after creation:**
```
Created profile 'my-prep' at profiles/my-prep/

Next steps:
  1. Fill out your profile:
     Option A: Use the intake interview
       - Copy prompts/intake.md into any AI chat (Claude, ChatGPT, Gemini)
       - Answer the interview questions
       - Save the output to profiles/my-prep/profile.md

     Option B: Edit the template directly
       - Open profiles/my-prep/profile.md
       - Fill in role, company, domain, and other fields

  2. Add your job description (optional):
       cp your-jd.md profiles/my-prep/inputs/job-description.md

  3. Check your profile:
       python prep.py status --profile my-prep
```

**Tests:**
- `test_init_creates_structure` — directories and profile.md created
- `test_init_refuses_existing` — won't overwrite existing profile
- `test_init_template_has_all_fields` — template contains all expected YAML keys
- `test_init_prints_next_steps` — output contains "Next steps"

#### 3.5: `cmd_status` with profiles and next-action guidance

**Without `--profile`:** List all profiles with one-line summary.
```
Profiles:
  security-infra    Staff Security Engineer @ Google    content complete
  my-prep           Senior SWE @ Meta                   syllabus generated
  (no profile)      using env vars / outputs/            content complete

Next: python prep.py status --profile my-prep
```

**With `--profile my-prep`:** Show full pipeline status and next action.
```
Profile: my-prep (Senior SWE @ Meta)

  Config:        12 core + 3 frontier episodes, model=gpt-5.2-pro

  Pipeline:
    [x] Profile created          profiles/my-prep/profile.md
    [ ] Domain generated          profiles/my-prep/domain/ (0/4 files)
    [ ] Syllabus generated       profiles/my-prep/outputs/syllabus/ (0/15 agendas)
    [ ] Content generated        profiles/my-prep/outputs/episodes/ (0/15 episodes)
    [ ] Packaged                 profiles/my-prep/outputs/gem/ (0/8 gem files)

  Next: python prep.py setup --profile my-prep
```

**Tests:**
- `test_status_lists_profiles` — lists available profiles
- `test_status_shows_pipeline_stage` — correct stage for partial completion
- `test_status_prints_next_command` — next command shown
- `test_status_no_profile_shows_legacy` — legacy output dir shown when no profiles exist

#### 3.6: Cost estimates before API calls

Before any API-calling command, print estimated cost and call count. Proceed after confirmation (skip with `--yes`).

```
$ python prep.py syllabus --profile my-prep
  Estimated: 8 API calls, ~$5
  Proceed? [Y/n]
```

```
$ python prep.py content --profile my-prep
  Estimated: 15 API calls, ~$25
  Proceed? [Y/n]
```

Estimates are rough (based on model and call count, not token-precise). Sufficient to prevent accidental $25 runs.

**Tests:**
- `test_cost_estimate_shown_before_api` — estimate printed
- `test_cost_estimate_skipped_with_yes` — `--yes` bypasses prompt
- `test_cost_estimate_scales_with_episodes` — estimate changes with episode count

#### 3.7: Per-episode content regeneration

Add `--episode N` flag to `content` command:

```bash
python prep.py content --episode 3 --profile my-prep
```

Regenerates only episode 3's content. Other episodes untouched. This works because each content episode is an independent API call.

**Not in this phase:** Per-episode syllabus regeneration. The syllabus uses a batch sequence (scaffold → core batches → frontier → merge) where episodes are generated in groups of 4. Regenerating one episode means re-running its batch, which affects sibling episodes. Deferred to backlog (decision #17).

**Tests:**
- `test_content_episode_flag_generates_one` — only specified episode generated
- `test_content_episode_flag_skips_others` — other episodes not regenerated
- `test_content_episode_flag_validates_range` — invalid episode number raises error

#### 3.8: Migrate S&I content (decision #13)

Move current `outputs/` to `profiles/security-infra/outputs/` using `git mv` for clean history. Create `profiles/security-infra/profile.md` from current env vars as a reference example.

**Tests:**
- `test_security_infra_profile_exists` — reference profile is valid
- `test_legacy_outputs_removed` — no content in top-level `outputs/`

### Config priority (highest wins)

1. CLI flags (`--model`, `--effort`)
2. Profile config (`profile.md` frontmatter)
3. Environment variables (`OPENAI_MODEL`, `PREP_ROLE`, etc.)
4. Defaults in code

---

## Phase 4 — Domain-agnostic prompts [DONE]

**Goal:** Extract domain-specific content from prompts into injectable sections so new domains don't require editing prompt files.

**Resolved open questions:**
- Q7 (7-section structure) — keep as-is, it generalizes. "Common Trap" and "Staff Pivot" are well-understood shorthand
- Q8 (persona renaming) — keep structure, let meta-prompt generate name and description
- Q9 (coverage map) — meta-prompt generates domain-equivalent categories
- Q12 (Nitty Gritty subsections) — meta-prompt generates domain-appropriate layout

### Prompt architecture (from brainstorm)

Every prompt has three layers:
1. **Generic skeleton** — section format, quality self-checks, length guidance (KEEP)
2. **Domain-specific flesh** — training data, examples, lenses, frameworks (INJECT)
3. **Count-specific references** — episode numbers, batch sizes (Phase 2 handles this)

### Steps

#### 4.1: Define domain section file format

Create `profiles/{name}/domain/` directory (decision #15 — not `domain/`, to signal these are generated intermediates, not user inputs) with files that contain injectable content.

**Files:**

| File | Injects into | Content |
|------|-------------|---------|
| `seeds.md` | `syllabus.md` lines 117-238 | Episode seed training data |
| `coverage.md` | `syllabus.md` line 69 | Coverage framework (replaces CISSP map) |
| `lenses.md` | `content.md`, `distill.md` | Domain lens, RRK lens, audience, subsection names, stakeholders |
| `gem-sections.md` | `gem.md` | Bookshelf, example questions, persona descriptions |

Each file starts with a generated-file header:
```markdown
<!-- Generated by: python prep.py setup --profile {name} -->
<!-- To regenerate: python prep.py setup --profile {name} --force -->
```

#### 4.2: Add injection markers to prompt templates

Replace domain-specific sections with markers. All markers use `.replace()` (decision #11), so injected content with `{braces}` is safe.

| Prompt | Marker | Replaces |
|--------|--------|----------|
| `syllabus.md` | `{DOMAIN_SEEDS}` | Lines 117-238 (training data) |
| `syllabus.md` | `{COVERAGE_FRAMEWORK}` | Line 69 (CISSP map) |
| `syllabus.md` | `{RRK_RULES}` | Lines 93-97 |
| `syllabus.md` | `{FRONTIER_RULES}` | Lines 102-105 |
| `content.md` | `{DOMAIN_LENS}` | Lines 11-13 |
| `content.md` | `{NITTY_GRITTY_LAYOUT}` | Lines 88-93 |
| `content.md` | `{DOMAIN_REQUIREMENTS}` | Lines 97-101 |
| `content.md` | `{DOMAIN_STAKEHOLDERS}` | Line 126 |
| `distill.md` | `{DOMAIN_LENS}` | Shares with content.md |
| `distill.md` | `{DISTILL_REQUIREMENTS}` | Lines 43-44 |
| `gem.md` | `{GEM_PERSONAS}` | Persona names/descriptions |
| `gem.md` | `{GEM_EXAMPLES}` | Example questions, pushback |
| `gem.md` | `{GEM_BOOKSHELF}` | Lines 182-199 |
| `gem.md` | `{GEM_CODING}` | Light Coding framing |

**Injection function:** Create `inject_domain(text, profile_name)` that reads domain files and substitutes markers. Separate from `render_template()` — render handles 5 simple env vars; injection handles multi-line file content.

**Fallback:** When no domain files exist (legacy mode or profile without `setup` run), use hardcoded S&I content as default. This keeps the tool working during the transition.

**Tests:**
- `test_inject_reads_domain_files` — content from domain/ appears in rendered prompt
- `test_inject_without_domain_uses_defaults` — S&I content used when domain files missing
- `test_no_domain_leakage` — with custom domain files, no S&I terms in output
- `test_braces_in_domain_content` — injected `{json: "example"}` doesn't break substitution

#### 4.3: Extract current S&I content into domain files

Move current hardcoded content from prompts into `profiles/security-infra/domain/` files. The prompts become templates; S&I becomes one instance.

**Tests:**
- `test_si_domain_files_created` — all 4 files exist for security-infra
- `test_prompts_are_templates` — no S&I-specific terms in prompt files (only markers)

#### 4.4: Validate smart NotebookLM prompt (decision #18)

Before eliminating per-episode frames, validate that the smart prompt produces sufficient format variety.

**Validation step:**
1. Write the smart NotebookLM prompt (one prompt that infers format from content)
2. Test with 5 existing S&I episodes (episodes 1, 5, 8, 12, 15 — spread across types)
3. Compare format variety: does the smart prompt produce at least 3 distinct formats across 5 episodes?
4. If yes: proceed — `cmd_package` no longer needs `notebooklm-frames.md`
5. If no: keep frames but make them domain-injectable. Add `frames.md` to domain files. Meta-prompt (Phase 5) generates per-episode frames.

**Tests (if validation passes):**
- `test_package_no_frames_needed` — packaging works without notebooklm-frames.md

**Tests (if validation fails):**
- `test_domain_frames_injected` — frames from domain/ used in packaging

#### 4.5: `render` command with domain injection

Specify `render` behavior incrementally:
- **Phase 3 state:** `render --profile` substitutes PREP_* vars from profile config
- **Phase 4 state:** `render --profile` also injects domain files (if they exist)
- **If domain files don't exist:** render substitutes vars only, prints warning: `Note: domain/ files not found. Run 'python prep.py setup --profile my-prep' for full rendering.`

**Tests:**
- `test_render_profile_substitutes_vars` — PREP_* replaced from profile
- `test_render_profile_injects_domain` — domain content injected
- `test_render_profile_warns_no_domain` — warning when domain files missing
- `test_render_no_profile_unchanged` — existing behavior without --profile

### Injection points by prompt (reference)

| Prompt | What gets injected | Source |
|--------|-------------------|--------|
| `syllabus.md` | Training data (~120 lines), coverage framework, RRK rules, frontier rules | `profiles/{name}/domain/seeds.md`, `profiles/{name}/domain/coverage.md` |
| `content.md` | Domain lens, RRK lens, audience, Nitty Gritty subsection names, requirements, stakeholders, portability examples | `profiles/{name}/domain/lenses.md` |
| `distill.md` | Same as content.md (shares injection points) | Same source |
| `gem.md` | Persona names/descriptions, Bookshelf, example questions, Light Coding framing | `profiles/{name}/domain/gem-sections.md` |
| `notebooklm.md` | Host 2 translation lens (minor) | Inline in profile.md |
| `notebooklm-frames.md` | Eliminated if decision #1 validates; otherwise domain-injectable | N/A or `profiles/{name}/domain/frames.md` |

---

## Phase 5 — Intake + meta-prompt [DONE — 5.2-5.3 superseded by `setup` command]

**Goal:** An AI-guided interview produces a complete profile, and focused meta-prompt calls generate domain-specific domain sections.

**Resolved open questions:**
- Q13 (one meta-prompt or several) — originally three focused calls (Phase 5.2), superseded by single-call `setup` command
- Q10 (quality validation) — syllabus-first review with checklist (Phase 5.4)

### The intake prompt (`prompts/intake.md`)

A showcase prompt (decision #7) that interviews the user and produces `profile.md`. Designed to be pasted into any AI chat.

**Questions it asks:**
1. What role are you preparing for? (title, level, company)
2. What domain? (security, ML, data eng, frontend, etc.)
3. What's your timeline? (interview dates, focus areas per interview)
4. What's your background? (current role, years, strengths, gaps)
5. Any specific topics or concerns? (what keeps you up at night)
6. Do you have a JD? (paste it in)

**Output format:** A complete `profile.md` with YAML frontmatter + structured sections. The user copies this file into `profiles/{name}/profile.md`.

### The meta-prompt (split into 3 focused calls)

Takes a completed profile and generates the domain-specific sections that slot into prompt templates.

**Input:** `profile.md` + optional context docs
**Output:** The files in `profiles/{name}/domain/`:
- `seeds.md` — episode seed training data
- `coverage.md` — coverage framework categories
- `lenses.md` — domain/RRK lenses, subsection names, stakeholders
- `gem-sections.md` — Bookshelf, example questions, persona descriptions

### Steps

#### 5.1: Write `prompts/intake.md`

The interview prompt. Must be a showcase piece — conversational, thorough, and produces clean structured output. The prompt must specify the exact output format precisely enough that Claude, GPT, and Gemini all produce parseable `profile.md`. Include a literal example of the expected format so models have a concrete target.

`load_profile()` (Phase 3.1) handles formatting variations as a safety net — case-insensitive keys, optional quoting, flexible whitespace.

**Tests:**
- `test_intake_prompt_renders` — no template errors
- Manual testing: paste into Claude/GPT/Gemini, verify all three produce parseable profile.md

#### 5.2: ~~Split meta-prompt into focused API calls~~ — superseded by `setup` command

**Superseded:** The three-call approach (seeds+coverage, lenses, gem-sections) was replaced by a single-call `setup` command using `prompts/setup.md`. Implemented in commit 32cd0eb.

#### 5.3: ~~`cmd_adapt(name)` command~~ — superseded by `setup` command

**Superseded:** Implemented as `cmd_setup(name)` instead — a single API call that generates all four domain files at once. See `prompts/setup.md`.

#### 5.4: End-to-end workflow [DONE — see `docs/design/workflow.md`]

Every command the user runs, in order:

```bash
# Step 1: Create profile skeleton (free, instant)
python prep.py init my-prep
# → Creates profiles/my-prep/ directory structure + template profile.md
# → Prints next steps (see Phase 3.4)

# Step 2: Fill profile (free, 5-15 minutes)
# Option A: AI-guided interview
#   Copy prompts/intake.md into any AI chat (Claude, ChatGPT, Gemini)
#   Answer interview questions
#   Save output to profiles/my-prep/profile.md
# Option B: Edit template directly
#   Open profiles/my-prep/profile.md, fill in fields
# Optional: add JD and context docs
#   cp your-jd.md profiles/my-prep/inputs/job-description.md

# Step 3: Check profile is valid (free, instant)
python prep.py status --profile my-prep
# → Shows profile config, confirms required fields present
# → Prints: "Next: python prep.py setup --profile my-prep"

# Step 4: Generate domain-specific domain sections (~$5-10, 1 API call)
python prep.py setup --profile my-prep
# → Creates domain/seeds.md, coverage.md, lenses.md, gem-sections.md
# → Prints: "Next: python prep.py syllabus --profile my-prep"

# Step 5: Generate syllabus — REVIEW BEFORE PROCEEDING (~$5, 8 API calls)
python prep.py syllabus --profile my-prep
# → 15 agenda files in profiles/my-prep/outputs/syllabus/
# → Prints review checklist (see below)
```

**Syllabus review checklist** (printed after `cmd_syllabus` completes):
```
Syllabus generated. Review before running content generation (~$25):

  [ ] Episode count matches expectations (15 episodes)
  [ ] Topics cover JD requirements (cross-reference with domain/coverage.md)
  [ ] No duplicate topics across episodes
  [ ] No obvious domain gaps
  [ ] Frontier digests cover emerging/advanced topics
  [ ] Mental models are distinct (not variations of the same idea)

Satisfied? Run: python prep.py content --profile my-prep
To regenerate: python prep.py syllabus --profile my-prep --force
```

```bash
# Step 6: Generate full content (~$25, 15 API calls)
python prep.py content --profile my-prep
# If episode 3 is bad: python prep.py content --episode 3 --profile my-prep

# Step 7: Package for Gem and NotebookLM (free, instant)
python prep.py package --profile my-prep

# Step 8: Set up Gem (manual, once)
python prep.py render prompts/gem.md --profile my-prep | pbcopy
# → Create Gem in Gemini, paste as system instructions
# → Upload gem-0 through gem-8 as knowledge files

# Step 9: Set up NotebookLM (manual, per episode)
# → Create notebook per episode, upload content file
# → Paste prompts/notebooklm.md into podcast instructions
# → Generate podcast
```

**Total estimated cost:** ~$35-40 for a full run. Budget 2-3 syllabus iterations (~$10-15 extra) for a new domain.

---

## Phase dependencies

```
Phase 0 ──► Phase 1 ──► Phase 2
                           │
                           ▼
                        Phase 3 ──► Phase 4 ──► Phase 5
```

- **2 before 3:** Prompts must use `.replace()` and handle dynamic counts before profiles add more variability
- **3 before 4:** Profile directory structure and `set_profile()` mechanism must exist before domain files can live in profiles
- **4 before 5:** Injection markers and domain file format must be defined before the meta-prompt can target them
- **2 and 3 are independent in code** but 3 depends on 2 conceptually — syllabus prompt needs to be count-agnostic before profiles set different counts

**Phase 2 / Phase 4 tension (resolved):** The original plan noted that Phase 2's `.format()` placeholders would conflict with Phase 4's domain injection if injected content contained `{braces}`. Decision #11 resolves this: Phase 2.1 switches syllabus.md to `.replace()`, so all prompts use the same brace-safe substitution pattern by the time Phase 4 adds injection markers.

---

## Resolved questions

All open questions from previous versions are now decided or deferred:

| Question | Resolution |
|----------|------------|
| Q1: Profile migration | Decision #13: `git mv` existing outputs to `profiles/security-infra/`. Phase 3.8. |
| Q14: S&I as profile? | Decision #13: yes, as reference example. |
| Q15: Cost awareness | Integrated into Phase 3.6 — print estimates before API calls. |
| YAML parsing dependency | Decision #12: hand-parse, no pyyaml. Frontmatter is simple `key: value` lines. |
| `.format()` vs `.replace()` | Decision #11: all prompts use `.replace()`. Phase 2.1 migrates syllabus.md. |
| Q13: One meta-prompt or several? | Three focused calls (Phase 5.2): seeds+coverage, lenses, gem-sections. |
| Prompt versioning | Deferred to backlog (decision #16): re-generation cost ($5-30) doesn't justify tracking complexity. |
| Per-episode syllabus regen | Deferred to backlog (decision #17): batch sequence makes single-episode regen complex. Content `--episode N` supported in Phase 3.7. |

---

## Deferred to backlog

These items were considered and explicitly deferred:

- **Prompt versioning** — tracking which prompt version generated a profile's outputs. Re-generation is cheap enough ($5-30) that "just regenerate" is acceptable.
- **Per-episode syllabus regeneration** — batch sequence (scaffold → core batches → frontier → merge) makes regenerating a single syllabus episode complex. Content per-episode regeneration is supported (Phase 3.7).
- **`prep.py intake --profile` command** — running the intake interview via API instead of pasting into external AI. Decision #9 (manual path always works) reduces urgency.

