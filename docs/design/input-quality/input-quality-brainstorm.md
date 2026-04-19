# Input Quality — Brainstorm

**Author**: Karsten Huttelmaier — co-authored with Claude

Vision: close the input boundary of the pipeline — the surface where the tool trusts user input without evaluating whether that input has the raw material to produce good output.

## The observation

The pipeline is optimistic about its inputs and rigorous about its outputs. Generation prompts (`syllabus.md`, `content.md`, `distill.md`) have dense structural contracts — section counts, required prefixes, depth requirements, quality self-checks. `_preflight_check` at `prep.py:223-245` validates that domain files are non-stub and that prompt templates exist before API commands fire. But neither layer checks input *specificity* (does the user's `domain` give the pipeline enough to produce a domain-specific syllabus?) or environmental *prerequisites* (is the API key actually set?) before expensive LLM calls begin.

Two items from `friction-prioritization-2026-04.md` sit on this same failure mode: **B1** (init template body at `prep.py:1286-1301` has no domain sizing guidance — "Add any extra context here" is the whole Notes section) and **D3** (`_preflight_check` at `prep.py:223-245` doesn't verify `OPENAI_API_KEY`, so API commands with a valid profile reach `get_client` only after cost confirmation and prompt assembly).

## Three moves at the same boundary

### 1. Intake specificity gate — merged via PR #5

Inserted between "Questions to Ask Me" and "Output Files" in `prompts/intake.md`. Checks Q5 (sub-areas) and Q6 (depth definition) against concrete bars:
- **Q5 bar:** 4+ distinct concrete sub-areas, each specific enough that a technical reader could name 2-3 episodes it would cover without guessing. Counter-examples: "data stuff," "various areas," "engineering things."
- **Q6 bar:** each sub-area has at least one concrete technical anchor — protocol name, algorithm, tool, or mechanism. Counter-example: "batch pipelines: understand how they work."

If both clear → proceed to generate files. If either doesn't clear → output a diagnostic (name what falls short, give 2-3 domain-specific examples of good answers, ask for revision or explicit "proceed anyway") and stop. If the user opts into "proceed anyway" despite weak inputs → generate files prefixed with a warning banner.

Structure is binary (pass or stop), not round-counting; escalation is user-driven rather than AI-counted. Applies only to the intake path (the external-AI-chat flow per decision 0008). `prep.py setup` uses a different prompt (`meta-seeds.md`) and does not currently share this gate.

### 2. Passive guidance — B1 / onboarding Phase 2, open

`cmd_init` at `prep.py:1286-1301` writes a `profile.md` template whose Notes section reads "Add any extra context here." — no explanation of what the body is for, no mention that pasting a job description materially improves downstream output quality. A user who fills in the YAML fields but leaves the body blank misses the highest-leverage text in the entire profile.

Proposed change (onboarding Phase 2 scope): rename the Notes section to "Job Description & Context" with inline guidance that explains the body is fed directly into `setup` and significantly improves domain-specific output quality. Update `cmd_init`'s stdout message to tell users to paste the JD and why it matters. No validation — still free-form text — just shaping what goes in.

Helps users avoid the gate before they ever see it, by making the JD's role explicit at `init` time.

### 3. Preflight API key check — D3, open

`_preflight_check` at `prep.py:223-245` validates that domain files are non-stub and that `syllabus.md`, `content.md`, `distill.md` exist. It does not check `OPENAI_API_KEY`. A friend with a typo'd key runs `prep.py syllabus --profile X`, sits through cost confirmation, waits while prompts are loaded and injected, then fails at `get_client` when the API call finally fires.

Proposed change: add an `OPENAI_API_KEY` presence check to `_preflight_check` for API commands (everything except `status`, `render`, `package` — non-API commands don't need a key). Fail fast with the same remediation hint `_show_pipeline_status` already uses. Reinforces A1 (which surfaces the key state on `status --profile`) with a hard check on command paths where it actually blocks progress.

Catches a different failure mode (missing prerequisite, not missing specificity) at the same boundary as the other two moves.

## How the three stack

Passive guidance → gate → preflight is a coverage ladder:

- Passive guidance shapes inputs early, so many users never need the gate to fire.
- The gate catches users whose inputs slip past guidance.
- The preflight check catches an orthogonal failure mode (environment, not content) before anything expensive runs.

Each layer is independent enough to build and land on its own, but together they close the input boundary for the mission's named user (a friend who clones the repo and follows the README).

## Why one initiative, not three

All three target the same failure mode — pipeline spends time and money on inputs that can't produce good output — at the same boundary (intake + init + preflight, before generation starts). Treating them as one initiative keeps the reasoning consistent across moves, and makes it natural to sequence them. It also creates a home for the "optimistic inputs, rigorous outputs" frame, which may generalize beyond these three specific fixes.

## Status

- Gate: merged via PR #5.
- Passive guidance (B1): open.
- Preflight API key check (D3): open.

## Open questions

- **Is the merged gate's specificity bar the right shape?** The Q5 "4+ distinct concrete sub-areas" and Q6 "at least one technical anchor per sub-area" haven't been tested against real intake runs. Could be too strict (rejecting borderline-ok inputs) or too loose (letting marginal inputs through). Worth a regression pass against a `security-infra` intake replay as a known-good baseline.
- **How should the gate handle genuinely narrow domains?** A user with a tightly scoped domain (e.g., "OAuth token binding for mobile apps") may only have 2-3 sub-areas yet still produce a high-quality syllabus. The "4+" bar would reject them, which is wrong.
- **Does the gate text assume CLI context?** The intake runs in an external AI chat (per decision 0008). Any phrasing implying `prep.py`-specific context would violate 0008. Worth a careful re-read of the merged text for this.
- **Preflight key check scope — all `--profile` commands or just API commands?** Non-API commands (`status`, `render`, `package`) don't need a key; gating them would be overreach.
- **Keep Phase 2's original scope or extend?** Phase 2 covers template rename + `cmd_init` stdout update. Whether to bundle Phase 3 (README Quick Start restructure) into the same initiative is a separate call.

## Edge cases

- **Non-native English speakers.** The gate's diagnostic must *show* concrete examples of good answers, not just name the problem. A user whose answer reads vague because their English is imprecise needs to see specificity in action, not a rebuke.
- **Dry-run with placeholder answers.** A user testing the pipeline with obviously-placeholder answers ("foo," "bar," "test stuff") should be caught — the diagnostic is the right response, not silent generic generation.
- **Prototyping override.** A user who knowingly wants a generic syllabus for a test run needs the "proceed anyway" path. The warning banner should be visible but non-blocking — discourage, don't prevent.
- **Unsourced shell with valid key elsewhere.** A user whose shell hasn't loaded `.env` but whose key exists in their system keychain or parent-shell environment would get a false-positive failure from the D3 preflight check. The diagnostic should point at the README troubleshooting table's platform-specific setup (PowerShell, Fish, etc.) so users self-serve the fix.

## What's NOT in scope

- **JD content validation.** The init template body is free-form; we're improving guidance about what to paste, not constraining what's allowed.
- **Downstream prompt changes** to syllabus/content/distill. The gate sits at intake, not at generation.
- **Replacing the manual intake path.** Decision 0008 stands — the AI-chat intake and the `prep.py setup` path must continue to produce the same `profile.md` artifact.
- **A1 and A2.** Landed separately via PR #3. Their fixes are adjacent to this initiative but scoped to `ROADMAP`-accuracy and exit-code propagation, not input quality.
- **Automated test coverage of the gate.** The gate lives in prompt text evaluated by an external LLM; validation is manual (paste intake into a chat, run against good/bad answers, confirm behavior). No unit test surface.

## Cross-references

- `docs/design/friction-audit.md` — original audit.
- `docs/design/friction-audit-reconciliation-2026-04.md` — reconciled state; B1 and D3 grounding.
- `docs/design/friction-prioritization-2026-04.md` — the prioritization that named B1 and D3.
- `docs/design/onboarding/onboarding-backlog.md` Phase 2 — the passive-guidance work, potentially relocatable to this initiative.
- `docs/decisions/0007-intake-prompt-is-craft.md` — intake is a showcase prompt; gate quality matters.
- `docs/decisions/0008-both-intake-paths-same-artifact.md` — both intake paths must produce the same `profile.md`; the gate must not assume CLI context.
- `ROADMAP.md` Tier 1 entry "Better profile.md template and init output" — user-facing framing of B1.

## Parking lot

- The **"optimistic inputs, rigorous outputs"** framing may earn a decision record if the pattern recurs elsewhere in the codebase. Worth tracking future work against this observation before formalizing.
- The **placeholder-vs-domain-marker verifier** surfaced in an earlier applicability analysis (separate session) is another input-boundary fix targeting a different failure mode — prompt template expects a marker, domain file didn't supply it, and `_inject_domain` silently leaves the literal `{MARKER}` in the text sent to the API. Worth its own ticket.
