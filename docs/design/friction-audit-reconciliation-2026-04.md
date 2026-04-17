# Friction audit reconciliation — 2026-04

## Method

Files read:
- `docs/design/friction-audit.md` — the audit being reconciled
- `prep.py` (all 1501 lines) — pipeline entry, commands, parsing, preflight, cost prompts, status
- `prompts/syllabus.md`, `prompts/content.md` (first 50 lines) — to verify placeholder/marker shapes
- `README.md` — setup instructions, troubleshooting guidance
- `ROADMAP.md` — cross-reference for what's already claimed done

Not readable:
- `.env.example` — denied by permission settings. Not load-bearing for any audit point; audit's Step 1 friction about env-var *validation* is verifiable in `prep.py` (the env file's shape is not what the audit contests).

Steps 9 and 10 of the audit describe Gemini UI and NotebookLM UI behavior — no code in this repo exercises them, so they are marked UNVERIFIABLE FROM CODE rather than guessed.

## Point-by-point status

### Step 1: Clone + install + env setup

- **[Medium] Env vars not validated until the first API command runs. Silent pass-through in `init`, `status`, `package`**: CHANGED
  - Evidence: `prep.py:433-437` — `get_client()` is still the sole hard validation for `OPENAI_API_KEY`. `prep.py:1061` — `_show_pipeline_status()` prints `API key: set/NOT SET`, but `prep.py:1107-1141` — the `status --profile` branch returns early at line 1141 and never reaches `_show_pipeline_status`. `cmd_init` (`prep.py:1264`), `cmd_package` (`prep.py:820`), and the `render` branch (`prep.py:1456-1465`) never check the key. `_preflight_check` (`prep.py:223-245`) checks domain and prompt files but not the API key.
  - Severity still fits: n-a
  - Notes: Partial fix — `status` *without* `--profile` surfaces the key state; with `--profile` it does not. `init`, `package`, and `render` still silently pass through a bad key. ROADMAP's "Done — `prep.py validate` command ✅ — Folded into status: checks API key, profile fields, domain markers, prompt files" overstates coverage for the `--profile` path.

- **[Low] `source .env` requires `set -a`/`set +a` wrapper. No instructions for fish/Windows**: CHANGED
  - Evidence: `README.md:55` still uses `set -a && source .env && set +a`. `README.md:80` now includes PowerShell (`$env:OPENAI_API_KEY="sk-..."`) and Fish (`set -gx OPENAI_API_KEY sk-...`) alternatives in the Troubleshooting table.
  - Severity still fits: n-a
  - Notes: Fish/Windows guidance is now present but appears only in the Troubleshooting table, not in the Quick Start flow.

### Step 2: `init` — create profile

(No friction points counted toward the 19.)

### Step 3: Edit `profile.md`

- **[Medium] Profile fields not validated until `setup` or `syllabus` runs**: STILL VALID
  - Evidence: `prep.py:259-320` — `load_profile` validates blank required fields (line 291), missing required fields (line 301), and integer-field types (line 317), but is only called from `set_profile` (`prep.py:323`). `set_profile` runs when any `--profile`-accepting command executes (`prep.py:1437-1438`). No dedicated editor-time check; user must invoke a command.
  - Severity still fits: yes
  - Notes: `status --profile <name>` now serves as a cheap validator (it calls `set_profile` -> `load_profile`), but this is undocumented as a validate workflow.

- **[Low] No guidance on what makes a good `domain` value**: STILL VALID
  - Evidence: `prep.py:1279-1294` — init template body says `"Add any extra context here."` with no domain sizing guidance. ROADMAP Tier 1 "Better profile.md template and init output" confirms this is still open.
  - Severity still fits: yes

### Step 4: `setup` — generate domain files

- **[High] Setup parse failures are silent. Raw saved to `setup-raw.md`, generic "Could not parse response" error**: CHANGED
  - Evidence: `prep.py:989, 1002, 1018` — raw responses are saved per-call to `setup-1-seeds.md`, `setup-2-lenses.md`, `setup-3-gem.md` (not `setup-raw.md` as audit claims). `prep.py:930-946` — `_write_domain_file` prints per-file warnings: `WARNING: {filename} missing markers: ...` (line 935) and `WARNING: {filename} has no recognized markers, skipping` (line 937). No "Could not parse response" string exists anywhere in the code (grep confirms).
  - Severity still fits: lower
  - Notes: The described error messaging is outdated. Underlying friction (silent success-with-warnings and no actionable fix guidance) persists, but the exact shape differs — warnings are per-marker, not a single generic error. Guidance on *how* to fix bad output is still absent.

- **[Medium] Marker format fragility: `<!-- WORD -->` single word, one space padding**: STILL VALID
  - Evidence: `prep.py:172` — regex is `^<!--\s+(\w+)\s+-->$`. `\s+` accepts one-or-more whitespace (audit's "extra whitespace fails" is wrong — extra whitespace is tolerated). Missing spaces *do* fail (the `\s+` requires at least one). `\w+` disallows spaces, hyphens, and other non-word chars in the marker name, so multi-word markers silently fail to match.
  - Severity still fits: yes
  - Notes: Audit's "extra whitespace" claim is wrong, but missing-space and multi-word failures are real — the underlying friction (silent match failure) holds.

- **[Low] Manual alternative requires context switch to another tool**: UNVERIFIABLE FROM CODE
  - This is a UX judgement about switching between terminal and an external AI chat. Code can confirm the manual path exists (`prompts/intake.md` referenced at `README.md:243-254`) but not that the switch is disruptive.

### Step 5: `syllabus` — generate agendas

- **[Medium] Agenda parse failures produce warnings but no agendas; user may not know what to do**: CHANGED
  - Evidence: `prep.py:742-744` — now prints three lines: `WARNING: parse_agendas found 0 episodes...`, `Raw output saved to {path}`, `Check format: expected '## Episode N:' or '## Frontier Digest A/B/C:'`. The audit's description (single `WARNING: parse_agendas found 0 episodes`) is outdated — guidance is now more actionable.
  - Severity still fits: lower
  - Notes: Underlying friction (no agenda files, user must read raw and decide next step) still present; the warning quality has improved.

- **[Low] Cost confirmation prompt interrupts automation; `--yes` unknown to first-time users**: STILL VALID
  - Evidence: `prep.py:1179-1189` — `_confirm_cost` prompts `"Proceed? [Y/n] "` with no mention of the `--yes` flag in the prompt text itself.
  - Severity still fits: yes

### Step 6: Review agendas

- **[Low] Review checklist printed only to terminal; easy to miss if scrolled past**: STILL VALID
  - Evidence: `prep.py:761-774` — `_print_syllabus_review` writes to stdout only, no file saved. `prep.py:1488-1491` — called only after standalone `syllabus` command (when `ok` is true); `cmd_all` at `prep.py:1354-1397` does not invoke it.
  - Severity still fits: yes

- **[Low] No structured way to provide feedback; user must manually edit agenda files or re-run whole syllabus**: STILL VALID
  - Evidence: `prep.py:676-909` — no feedback/accept/reject command exists. Only `cmd_syllabus`, `cmd_content`, `cmd_package`, `cmd_add`, `cmd_setup`.
  - Severity still fits: yes

### Step 7: `content` — generate episodes

- **[Medium] No incremental cost tracking; failure at episode N/M leaves spend unclear**: STILL VALID
  - Evidence: `prep.py:776-818` — `cmd_content` tracks `gen`, `skip`, `warn`, `fail` counters only, no per-episode cost. `prep.py:1179` — `_confirm_cost` prints an estimate upfront but there is no post-run summary. ROADMAP Tier 1 "Post-run cost summary" confirms this is open.
  - Severity still fits: yes

- **[Low] Partial failures return True; "12 generated, 0 skipped" hides 3 failures**: FIXED
  - Evidence: `prep.py:812` — summary now includes failure count: `"=== CONTENT: {gen} generated, {skip} skipped, {fail} failed ==="`. `prep.py:816-817` — explicit `WARNING: {fail} episode(s) failed. Re-run to retry.`. `prep.py:818` — returns `fail == 0` (False on any failure).
  - Severity still fits: n-a
  - Notes: Partial fix — function now returns False on failures and summary surfaces them, but `main()` at `prep.py:1492` discards the return value, so the shell exit code is still 0 when some episodes fail. ROADMAP's "Partial failure exit codes ✅" overstates the wiring.

### Step 8: `package` — create gem + notebooklm files

(No friction points counted toward the 19.)

### Step 9: Set up Gem

- **[High] Manual upload of 8 files in Gemini UI; no batch drag-and-drop**: UNVERIFIABLE FROM CODE
  - Gemini UI behavior, external to this repo.

- **[Medium] Rendered prompt must be manually copied to clipboard**: UNVERIFIABLE FROM CODE
  - Gemini UI integration, external to this repo.

- **[Low] File naming not documented in render output**: UNVERIFIABLE FROM CODE
  - Could be partially verified (the render command doesn't emit file list), but the friction is about end-user documentation comprehension — a UX judgement.

### Step 10: Set up NotebookLM

- **[High] 15 manual notebook creations; 30-45 min of repetitive clicking**: UNVERIFIABLE FROM CODE
  - NotebookLM UI, external to this repo. ROADMAP Tier 1 "NotebookLM batch setup documentation" acknowledges this is still open.

- **[Medium] Episode-specific prompts must be manually extracted from `notebooklm-frames.md`**: UNVERIFIABLE FROM CODE
  - Partially inspectable (file exists per CLAUDE.md's key-files list), but the friction is about the user workflow of extraction, not code behavior.

- **[Low] NotebookLM has no API — cannot be automated**: UNVERIFIABLE FROM CODE
  - External product capability statement.

## Tallies

- STILL VALID: 7 (Step 3 Medium, Step 3 Low, Step 4 Medium, Step 5 Low, Step 6 Low x2, Step 7 Medium)
- FIXED: 1 (Step 7 Low)
- CHANGED: 4 (Step 1 Medium, Step 1 Low, Step 4 High, Step 5 Medium)
- UNVERIFIABLE FROM CODE: 7 (Step 4 Low, Step 9 x3, Step 10 x3)

Total: 19.

## New findings

- `main()` at `prep.py:1492` discards `cmd_content`'s return value — partial-failure exit code never reaches the shell despite ROADMAP listing "Partial failure exit codes ✅" as done.
- `status --profile` branch (`prep.py:1107-1141`) returns before `_show_pipeline_status` (`prep.py:1032`), so users with a profile never see the `API key: set/NOT SET` line — inconsistent coverage vs. plain `status`.
- `_preflight_check` (`prep.py:223-245`) checks domain files and prompt files but never the API key, so API commands with a valid profile reach `get_client` before failing on a missing key.
- `cmd_all` invokes `cmd_syllabus` (`prep.py:1386`) but does not print the syllabus review checklist — the review is only visible when `syllabus` is run standalone (`prep.py:1488-1491`). A user running `all` never sees the review prompt.
- `cmd_init` (`prep.py:1264-1269`) does not validate the profile name beyond checking for an existing directory — no character/length checks — so the ROADMAP claim of "profile name validation" under "Defensive validation hardening ✅" may refer to something else or be inaccurate.
- `_write_domain_file` (`prep.py:930-946`) writes whatever markers it found and skips missing ones with a warning, but the file *is* written even when partial — the next `_is_stub` check (`prep.py:209-214`) will treat a partially-written file as non-stub, so an incomplete setup run does not trigger re-setup via the `all` auto-run path.
