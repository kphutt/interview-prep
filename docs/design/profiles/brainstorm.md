# Brainstorm: Profiles, Intake, and Dynamic Pipeline

**Status: Brainstorm — not a plan yet. Captured Feb 14, 2026.**

---

## Vision

Transform the tool from a hardcoded 15-episode Security & Infrastructure pipeline into a general-purpose technical deep-dive content generator that adapts to any goal, domain, and timeline.

Two audiences, no compromise on either:
- **Tool** — someone clones it and is generating content for their own prep in minutes
- **Showcase** — friends (and employers) who look at the repo see craft in the prompts, output quality, and architecture

## Architecture: Intake is external, prep.py is the batch generator

```
Phase 1: INTAKE (no API calls, no cost)
  Option A: paste prompts/intake.md into any AI → it interviews you →
            produces a structured profile.md
  Option B: manually fill out profiles/{name}/profile.md from template

Phase 2: GENERATE (API calls via prep.py)
  prep.py all --profile {name} → reads profile → generates everything
```

Key principle: **be cheap early, expensive late.** No API cost until the user has provided their inputs and is ready to generate.

## Inputs (all optional, more = better calibration)

| Input | Purpose | Where it lives |
|-------|---------|---------------|
| Target (JD / exam syllabus / topic) | What they're preparing for | `profiles/{name}/inputs/job-description.md` |
| Notes (recruiter, personal) | Context not in the JD | `profiles/{name}/inputs/notes.md` |
| Interview schedule + focus areas | Determines scope, depth, episode count | In `profile.md` |
| Extra context (facts, concepts, articles) | Domain knowledge that seeds the syllabus | `profiles/{name}/inputs/context/` |

Additional inputs (resume, interviewer info) are tracked in the [backlog](../backlog.md).

## Use cases

| Use case | Target | Timeline | Depth |
|----------|--------|----------|-------|
| Specific job | JD + company + scheduled interviews | Days to weeks | Focused on gaps, interviewer-aware |
| General job search | Role type + company tier | Weeks to months | Broader coverage |

Additional use cases (certification, learning) are tracked in the [backlog](../backlog.md).

## Profile directory structure

```
profiles/
  security-infra/
    profile.md              # structured intake output (from AI or manual)
    outputs/
      syllabus/
      episodes/
      gem/
      notebooklm/
  staff-sre-meta/
    profile.md
    outputs/
      ...
```

Settled decisions: [decisions.md](decisions.md)

## Existing code that needs to change

### `prep.py`

- **`prep.py:57-58`** — `CORE_EPS`, `FRONTIER_EPS` hardcoded to 12+3 — **[DONE — Phase 1]**
- **`prep.py:66-75`** — `SYLLABUS_RUNS` hardcodes 8-call sequence — **[DONE — Phase 1]**
- **`prep.py:61-64`** — `gem_slot()` assumes 12+3 structure — **[DONE — Phase 1]**
- **`prep.py:227, 329`** — Frontier digest mapping `{"A":13,"B":14,"C":15}` hardcoded twice — **[DONE — Phase 1]**
- **`prep.py:430-444`** — Gem packaging iterates `range(1, 9)` — always 8 slots — **[DONE — Phase 1]**
- **`prep.py:516-583`** — `write_manifest()` hardcodes "X/15" and "all 15 episodes present" — **[DONE — Phase 1]**
- **All env var references** — need to read from profile config, fall back to env vars
- **Output directory paths** — need to be profile-aware

### `prompts/syllabus.md`

- **Lines 117-238** — 120 lines of Security & Infrastructure training data (episode seeds, mental models). For a new domain, this entire section would be different. Currently THE source of truth for calibrating output quality.
- **Throughout** — references "Episodes 1-12" and "Frontier Digests 13-15"
- **Line 69** — CISSP coverage map — certification-specific, not domain-agnostic
- **Lines 93-97** — RRK integration rules reference "security-only thinking" — domain-specific
- **Lines 102-105** — Frontier digest rules reference "Identity & Infrastructure" — domain-specific

### `prompts/content.md`

- **Line 10** — "Audience: Senior SWEs" hardcoded, not via env var. Same concept as the PREP_AUDIENCE that's going away.
- **Lines 11-13** — Domain lens ("identity/infrastructure mechanisms") and RRK lens ("incident response/on-call reality, operational excellence/SRE thinking") — S&I-specific. These are the biggest injection points — they control what depth looks like.
- **Lines 88-93** — Canonical 6 Nitty Gritty subsections ("Protocol / Wire Details", "Data Plane / State / Caching", "Threats & Failure Modes", "Operations / SLOs / Rollout") — infrastructure-oriented subsection names.
- **Lines 97-101** — Requirements include "protocol/crypto details (headers/claims/handshakes/certs/curves)" — Security-specific.
- **Line 103** — Portability rule mentions "{COMPANY}-specific terms (e.g., GFE, Borg, ALTS)" — Google-specific examples.
- **Line 126** — Stakeholders hardcoded as "Security, Product, SRE, Legal/Compliance".

### `prompts/distill.md`

- **Lines 43-44** — Requirements include "protocol/crypto details" — Security-specific.
- **Line 71** — Example uses "use mTLS" — domain-specific.
- **Line 80** — Quality self-check says "Common Trap calls out 'security-only thinking' failure" — domain-specific.
- Shares the 7-section format with content.md — same injection points apply.

### `prompts/gem.md`

- **Lines 31-33** — Example questions use "signing algorithm for OIDC provider's JWKs" and "JWKS endpoint returning stale keys" — domain-specific examples.
- **Line 60** — Pushback example: "you're conflating Issuer with Verifier" — domain-specific.
- **Line 77** — "Light Coding" section says "Security-flavored scripting" with Security examples — domain-specific.
- **Line 116** — Example uses "mTLS for service-to-service" — domain-specific.
- **Lines 134-144** — Status Report format examples use "Crypto" topics and Security concepts — domain-specific.
- **Lines 182-199** — Bookshelf — entirely domain-specific. Already has a comment saying "replace with your domain's reference framework."
- The generic structure (personas, modes, concept tracking, session management) is entirely domain-agnostic. The persona CONCEPT (two lenses on the same material) generalizes; the persona NAMES and DESCRIPTIONS don't.

### `prompts/notebooklm.md`

- **Line 27** — Host 2 description mentions "latency, caching, state, rollout safety, blast radius, on-call cost" — mildly infra-oriented but actually fairly generic engineering concerns.
- Already has a comment (line 7): "Adapt Host 2's translation lens to your domain."
- **This is the best-parameterized prompt.** Mostly domain-agnostic already.

### `prompts/notebooklm-frames.md`

- **All 15 frames (lines 16-89)** — format, central argument, stakes are all S&I-specific. Entirely useless for a new domain.
- Decision #1 (smart NotebookLM prompt) may eliminate this file entirely.

## Prompt architecture

Every prompt has three layers:

1. **Generic structural skeleton** — section format, quality self-checks, micro-prefix cues, length guidance, pacing rules. This is the craft and it generalizes.
2. **Domain-specific flesh** — training data, examples, lenses, frameworks, persona framing. This is what the meta-prompt generates.
3. **Count-specific references** — episode numbers, batch sizes, frontier ranges. This is what dynamic pipeline solves.

The injection points are well-defined. The meta-prompt doesn't need to generate entire prompts — it generates domain-specific SECTIONS that slot into the existing skeleton. This preserves the craft in the skeleton while adapting the domain content.

| Prompt | Generic skeleton (keeps) | Domain-specific injection points | Count-specific refs |
|--------|------------------------|--------------------------------|-------------------|
| `syllabus.md` | 7-component agenda format, mode system, quality self-check | Training data (lines 117-238), RRK integration rules (93-97), frontier rules (102-105), coverage framework (69) | Episode ranges in modes (37-51), frontier numbering (48-51) |
| `content.md` | 7-section structure, micro-prefix cues, length guidance, quality self-check framework | Domain lens (11-12), RRK lens (12-13), audience (10), Nitty Gritty subsection names (88-93), requirements (97-101), stakeholders (126), portability examples (103) | None |
| `distill.md` | 7-section format, distillation rules framework, quality self-check | Requirements (43-44), examples (71), self-check details (80) | None |
| `gem.md` | Persona structure, modes (Interview/Rapid Fire/Explore), concept tracking, session management, Status Report format | Persona names & descriptions (19-26), Bookshelf (182-199), example questions (31-33, 60), Light Coding framing (77), format examples (134-144) | None |
| `notebooklm.md` | All of it — host dynamics, tone, narrative structure, pacing | Host 2 translation lens (27) — minor | None |
| `notebooklm-frames.md` | Frame format (format / central argument / stakes) | All 15 frames | Episode count |

## Meta-prompt workflow

The meta-prompt system takes profile inputs and generates the domain-specific sections that slot into prompt injection points. Two sub-problems:

### A) Domain content generation (the hard part)

Requires synthesizing domain expertise from profile inputs:

| Output | Consumes | Injects into | Notes |
|--------|----------|-------------|-------|
| Episode seeds (~120 lines of training data) | JD, domain, timeline, context docs | `syllabus.md` training data section | This is THE critical output — it determines whether the agendas are any good |
| Domain lens + second persona framing | Domain, role level | `content.md` lines 10-14, `distill.md` | Controls what "depth" means for this domain |
| Nitty Gritty subsection guidance | Domain | `content.md` canonical 6 layout | e.g., "Pipeline Architecture" instead of "Protocol / Wire Details" |
| Coverage map framework | Domain | `syllabus.md` (replaces CISSP) | What's the domain's equivalent of CISSP domains? |
| Reference framework (Bookshelf) | Domain, JD | `gem.md` Bookshelf section | The retrieval framework the Gem uses during coaching |
| Gem example questions + persona examples | Domain | `gem.md` scattered examples | Teaches the Gem what domain-specific pushback looks like |

### B) Structural adaptation (simpler — mostly text substitution)

| Output | Source | Notes |
|--------|--------|-------|
| Stakeholder list | Profile (what teams are relevant) | Replaces "Security, Product, SRE, Legal/Compliance" |
| Persona name | Profile or meta-prompt | Replaces "RRK" if not generic enough |
| Light Coding description | Domain | Replaces "Security-flavored scripting" |

**Open question:** Is this one meta-prompt or several? Could intake produce episode seeds directly (it already interviews the user about their domain), with a separate meta-prompt for the Bookshelf and examples? Or is it cleaner as one big generation step?

## Post-generation workflow

What happens AFTER `prep.py all` completes. Currently undocumented even for the current S&I domain. A friend needs to know how to actually use the outputs.

This is a separate concern from profiles — it should be documented regardless. Profiles inherits the workflow.

**NotebookLM setup (per episode):**
1. Create a notebook in NotebookLM
2. Upload the episode content file as a source
3. Paste the episode frame + generic prompt into podcast generation instructions
4. Generate podcast
5. Repeat 15 times

Decision #1 (smart NotebookLM prompt) simplifies this: upload + paste one generic prompt + generate. No per-episode frame needed.

**Gem setup (once):**
1. `python prep.py render prompts/gem.md | pbcopy`
2. Create a Gem in Gemini → paste prompt as system instructions
3. Upload gem-0 through gem-8 as knowledge files
4. Optionally upload resume, gaps brief

**Gap loop (ongoing):**
1. Practice with Gem → it reveals weak areas
2. Find a paper/article → `python prep.py add paper.pdf --gem-slot 8`
3. Re-upload updated gem file

**Recommended new-domain workflow:**
1. Set env vars
2. Adapt prompts (manually today, meta-prompt eventually)
3. Run `python prep.py syllabus` FIRST — generate only agendas
4. Review agendas before committing to content generation ($25+)
5. If agendas look wrong, tweak training data and regenerate
6. When satisfied, run `python prep.py content` then `python prep.py package`

This syllabus-first review pattern is already supported (`prep.py syllabus` exists) but isn't documented as the recommended approach for new domains. It matters because it catches bad training data before the expensive step.

## What a friend could do TODAY

Even without profiles implemented, a friend could adapt the tool manually. This serves two purposes: it makes the tool usable right now, AND it serves as a spec for what profiles automates.

**Manual adaptation steps (no code changes needed):**
1. Set env vars: `PREP_ROLE`, `PREP_COMPANY`, `PREP_DOMAIN`
2. In `prompts/syllabus.md`, replace lines 117-238 (training data) with 12 episode seeds for their domain — each with Title, Focus, Mental Model, Common Trap, Nitty Gritty, Staff Pivot
3. In `prompts/syllabus.md`, replace "CISSP" (line 69) with their domain's coverage framework
4. In `prompts/content.md`, replace domain lens (line 12) and RRK lens (line 13) with domain-appropriate descriptions
5. In `prompts/content.md`, update canonical Nitty Gritty subsections (lines 88-93) for their domain
6. In `prompts/content.md`, update requirements (lines 97-101) and stakeholders (line 126)
7. Same changes in `prompts/distill.md` (lines 43-44, 71, 80)
8. Run `python prep.py syllabus` — review agendas
9. Run `python prep.py content` — then `python prep.py package`
10. In `prompts/gem.md`, rewrite Bookshelf (lines 182-199) and example questions
11. Write 15 NotebookLM frames OR rely on decision #1's smart prompt
12. Set up NotebookLM and Gem (see post-gen workflow above)

This is achievable — 30-60 minutes of prompt editing plus $25-30 in API costs. The meta-prompt workflow automates steps 2-7 and 10-11.

## Open questions for next session

1. **Profile migration** — how to move existing `outputs/` content into `profiles/security-infra/` without losing git history?
2. **`profile.md` format** — what fields, what structure? YAML? Markdown with frontmatter? Plain text sections?
3. **How `prep.py` reads profiles** — does it set env vars from profile config (existing code unchanged)? Or refactor to read from profile directly?
4. **The intake prompt** — first pass at `prompts/intake.md`. What questions does it ask? What format does it output?
5. **Dynamic episode count** — how does the pipeline adapt? Variable batch sizes? Different syllabus prompt modes?
6. **Phasing** — what's the minimum viable change that gets profiles working without breaking what exists?
7. **Does the 7-section structure generalize?** — The sections (Hook, Mental Model, Common Trap, Nitty Gritty, Staff Pivot, Scenario Challenge) are conceptually generic. "Common Trap" assumes Google/Meta leveling (L4 = junior). "Staff Pivot" assumes Staff-level target. These are labels, not structure — likely fine to keep as-is since they're well-understood shorthand, even if the role is "Senior" not "Staff." But worth deciding: does the meta-prompt ever need to generate different section names?
8. **Should the second persona be renamed per domain?** — "RRK" (Reliability / Risk / Knobs) is meaningful for infrastructure. For ML Systems it might be "Evaluation / Drift / Scale." For Frontend, "Performance / Accessibility / Complexity." The persona CONCEPT (two complementary lenses on the same material) is one of the best ideas in the tool. The question is whether "RRK" is generic enough or if the name should be profile-driven. Leaning toward: keep the structure, let meta-prompt generate name and description.
9. **What replaces the CISSP coverage map?** — The scaffold/merge modes output a table mapping episodes to CISSP domains. This is the quality guarantee that the syllabus covers the domain comprehensively. For a new domain, the meta-prompt needs to generate equivalent coverage categories. For Data Engineering, maybe: Storage, Compute, Orchestration, Quality, Governance. The categories ARE the domain expertise.
10. **How to validate output quality for new domains?** — S&I content was manually reviewed by a domain expert. For a new domain, the friend might not have the calibrated eye. Options: (a) syllabus-first review (generate agendas, read them, iterate), (b) pipeline self-assessment ("does this agenda cover the JD requirements?"), (c) just trust the meta-prompt + model. Leaning toward (a) — it's cheap, already supported, and puts the human in the loop at the right moment.
11. **Gem slot math for non-15 counts** — `gem_slot()` pairs episodes (1-2 → slot 1, etc.) assuming 12 core + 3 frontier = 8 slots. Odd core episode counts don't pair evenly. Does the last slot get a single episode? Does the bucketing algorithm change? This needs a formula, not hardcoded ranges.
12. **How does `content.md` adapt its Nitty Gritty subsection layout?** — The "canonical 6" includes "Protocol / Wire Details" and "Threats & Failure Modes" — S&I-oriented. For Data Engineering, these might be "Pipeline Architecture" and "Data Quality / Schema Evolution." Should the meta-prompt generate a domain-appropriate canonical layout, or should the content prompt just say "use 4-6 domain-relevant subsections" and let the model decide?
13. **Is the meta-prompt one step or two?** — Could intake produce episode seeds directly (it already interviews the user about their domain), with a separate meta-prompt for Bookshelf, examples, and prompt sections? Or is it cleaner as one big generation: profile → all domain-specific sections?
14. **Migration path: does S&I become a profile?** — The existing content could become `profiles/security-infra/` as a concrete example of what a complete profile looks like. Or it stays in `outputs/` as a showcase and profiles are always new. If it becomes a profile, the friend has an example to follow. Open question #1 is related but vague — make it concrete.
15. **Cost awareness and iteration budget** — S&I cost ~$50 to generate ($25 agendas + $25 content). A new domain via meta-prompt adds ~$5-10. If the first run doesn't produce good agendas, the friend needs to iterate (tweak training data → regenerate syllabus). Each iteration is ~$5. Should the tool surface cost estimates? Should the brainstorm recommend a "budget" (e.g., "expect 2-3 iterations, ~$40-60 total")?

## Commands (projected)

```bash
python prep.py init {name}              # create profile from template
python prep.py init {name} --run        # create + immediately generate
python prep.py status                   # show all profiles and state
python prep.py all --profile {name}     # generate everything for a profile
python prep.py render prompts/gem.md --profile {name}  # render with profile vars
```

