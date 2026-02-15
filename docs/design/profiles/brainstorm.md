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
| Resume | Baseline assessment, gap identification | `profiles/{name}/inputs/resume.pdf` |
| Target (JD / exam syllabus / topic) | What they're preparing for | `profiles/{name}/inputs/job-description.md` |
| Notes (recruiter, personal) | Context not in the JD | `profiles/{name}/inputs/notes.md` |
| Interview schedule + focus areas | Determines scope, depth, episode count | In `profile.md` |
| Interviewer info (LinkedIn, articles) | Tailor to likely questions | `profiles/{name}/inputs/interviewers/` |

## Use cases (the target is broader than "job interview")

| Use case | Target | Timeline | Depth |
|----------|--------|----------|-------|
| Specific job | JD + company + scheduled interviews | Days to weeks | Focused on gaps, interviewer-aware |
| General job search | Role type + company tier | Weeks to months | Broader coverage |
| Certification | Exam syllabus (CISSP, AWS SA, etc.) | Variable | Mapped to exam domains |
| Learning | Topic description ("distributed systems") | No deadline | Curiosity-driven |

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

- **`prep.py:57-58`** — `CORE_EPS`, `FRONTIER_EPS` hardcoded to 12+3
- **`prep.py:66-75`** — `SYLLABUS_RUNS` hardcodes 8-call sequence
- **`prep.py:61-64`** — `gem_slot()` assumes 12+3 structure
- **`prompts/syllabus.md:117-238`** — 120 lines of Security & Infrastructure training data (episode seeds, mental models). For a new domain, this entire section would be different. Currently THE source of truth for calibrating output quality.
- **`prompts/syllabus.md` throughout** — references "Episodes 1-12" and "Frontier Digests 13-15"
- **All env var references** — need to read from profile config, fall back to env vars
- **Output directory paths** — need to be profile-aware

## The training data problem

`prompts/syllabus.md` has a TRAINING DATA section with 12 detailed episode seeds (mental models, protocols, key details) that are entirely Security & Infrastructure. This is what makes the output consistently good — without it, the model generates more generic content.

For a new domain, this training data needs to be different. The user originally crafted this manually in AI chats before the pipeline existed, using the JD + recruiter notes + personal knowledge as input.

The intake prompt could generate this as part of its output — "given these inputs, here are the episode seed concepts" — but we haven't decided exactly how yet.

## Open questions for next session

1. **Profile migration** — how to move existing `outputs/` content into `profiles/security-infra/` without losing git history?
2. **`profile.md` format** — what fields, what structure? YAML? Markdown with frontmatter? Plain text sections?
3. **How `prep.py` reads profiles** — does it set env vars from profile config (existing code unchanged)? Or refactor to read from profile directly?
4. **The intake prompt** — first pass at `prompts/intake.md`. What questions does it ask? What format does it output?
5. **Dynamic episode count** — how does the pipeline adapt? Variable batch sizes? Different syllabus prompt modes?
6. **Phasing** — what's the minimum viable change that gets profiles working without breaking what exists?

## Commands (projected)

```bash
python prep.py init {name}              # create profile from template
python prep.py init {name} --run        # create + immediately generate
python prep.py status                   # show all profiles and state
python prep.py all --profile {name}     # generate everything for a profile
python prep.py render prompts/gem.md --profile {name}  # render with profile vars
```

## What NOT to change yet

- No embedded local model for intake — too complex, marginal benefit
- No renaming `NotebookLM - Prompts/` directory (already removed; content in `prompts/`)
- No CI/CD — not needed for a personal tool
- Resume handling — user said "forget about it for now" but it's noted as an input
