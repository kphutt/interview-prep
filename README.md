# Interview Prep Pipeline

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue?logo=python&logoColor=white)](https://www.python.org)
[![License: MIT](https://img.shields.io/badge/license-MIT-yellow.svg)](LICENSE)

## The Problem

Staff-level interview prep demands domain-specific depth that generic resources don't cover. Books and courses teach general patterns; they aren't structured around your specific role, company, and domain, and they don't guarantee coverage across topics. This pipeline generates a complete, personalized study syllabus and turns each episode into content you can study, listen to, or practice with.

## Overview

You describe your target role and domain; the pipeline generates Staff-level technical content tailored to your interviews. Ships with a complete Security & Infrastructure reference profile.

## What You Get

The pipeline produces three outputs from your domain description:

1. **Deep-dive study documents** — one episode per topic covering your domain end-to-end, each with Title, Hook, Mental Model, Common Trap (common wrong answers), Nitty Gritty (protocol/wire details), Staff Pivot, and Scenario Challenge sections
2. **NotebookLM podcasts** — each episode becomes a podcast you can listen to during commutes
3. **Gemini Gem coaching bot** — an interview coach with rapid-fire, mock interview, and explore modes

```
  init            setup / syllabus       content           package
┌───────┐     ┌──────────────┐     ┌────────────┐     ┌──────────┐
│profile│────>│   agendas    │────>│  episodes   │────>│ gem.md + │
│created│     │  generated   │     │  generated  │     │ notebook │
└───────┘     └──────────────┘     └────────────┘     └──────────┘
```

Each stage is idempotent and resumable — commands skip files that already exist unless you pass `--force`.

## Design Principles

- **Idempotent** — rerun safely; existing files are skipped. Prep runs iteratively over weeks — regenerating would destroy your annotations.
- **Marker-based injection** — domain content uses `<!-- MARKER -->` delimiters, injected into prompts via `{MARKER}` placeholders. This prevents prompt corruption when user content contains braces.
- **Every episode has traps and pivots** — prompts require Common Trap sections (wrong answers that sound right) and Staff Pivot sections (where the conversation shifts from "correct answer" to "architectural judgment").
- **Raw responses preserved** — every API response is saved to `outputs/raw/` for auditability.
- **Domain-portable** — one template, any specialty. Swap the domain files and the pipeline generates equivalent depth for a different field.

## Quick Start

### Browse the reference profile (free, no API key)

A complete Security & Infrastructure profile ships with the repo:

```bash
pip install -r requirements.txt

cp .env.example .env
# Edit .env: add your OPENAI_API_KEY

# Load config
set -a && source .env && set +a

# Create a profile for your domain
python prep.py init my-domain

# Generate everything (`all` auto-runs setup if domain files haven't been generated):
python prep.py all --profile my-domain
```

### Run the smoketest (pennies, ~1 min)

```bash
pip3 install -r requirements.txt
export OPENAI_API_KEY=sk-...    # get one at platform.openai.com
python3 prep.py all --profile smoketest --yes    # add --force to re-run
```

### Build your own profile

```bash
python3 prep.py init my-domain
# Edit profiles/my-domain/profile.md — set your role, company, and domain
python3 prep.py all --profile my-domain    # auto-runs setup, then syllabus + content + package
```

Outputs land in `profiles/my-domain/outputs/`. See [Using the Outputs](#using-the-outputs) for NotebookLM and Gem setup.

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `python: command not found` | Use `python3` — macOS doesn't ship a `python` alias |
| `ModuleNotFoundError: openai` | `pip3 install -r requirements.txt` |
| `ERROR: OPENAI_API_KEY not set` | Edit `.env`, then `source .env` (bash/zsh). PowerShell: `$env:OPENAI_API_KEY="sk-..."`. Fish: `set -gx OPENAI_API_KEY sk-...` |
| `ERROR: domain/seeds.md is empty` | Run `prep.py setup --profile <name>` or see [Manual Alternative](#manual-alternative) |
| `ERROR: --profile required` | Add `--profile <name>` to the command |
| API auth / rate / model error | Check your API key and model access tier; try `model: gpt-4o-mini` in profile.md |
| Cost seems high | The pipeline shows an estimate before each run. Test with `gpt-4o-mini` first |

## Iterating

Common Day 2 workflows:

**Regenerate one episode's content:**
```bash
python3 prep.py content --profile my-domain --episode 5
```

**Force regenerate everything** (without `--force`, existing files are skipped):
```bash
python3 prep.py all --profile my-domain --force
```

**Edit an agenda manually**, then regenerate its content:
```bash
# Edit profiles/my-domain/outputs/syllabus/episode-05-agenda.md
python3 prep.py content --profile my-domain --episode 5
```

**Add external material** (distill a document into an episode and append to the Gem):
```bash
python3 prep.py add paper.md --profile my-domain
```
Note: input must be UTF-8 text (not binary PDF).

**Change episode counts:** edit `core_episodes` / `frontier_episodes` in your profile.md and re-run.

## Profiles

Every interview domain lives in its own profile under `profiles/<name>/`. A profile contains:

```
profiles/my-domain/
  profile.md           <- Config: role, company, domain, model, episode counts
  domain/              <- Domain-specific content injected into shared prompts
    seeds.md             Episode seed data (12 episodes)
    coverage.md          Coverage framework (e.g., CISSP, DAMA-DMBOK)
    lenses.md            Domain lens, Nitty Gritty layout, requirements, stakeholders
    gem-sections.md      Gem coaching bot: bookshelf, examples, format
  inputs/              <- Pre-existing files (pipeline skips what exists)
    agendas/
    episodes/
    misc/
  outputs/             <- Generated content
    syllabus/            Episode agendas
    episodes/            Full content documents
    gem/                 Merged episode pairs for Gem knowledge files
    notebooklm/          Individual episode files for NotebookLM
    raw/                 Raw API responses (backup)
```

The reference profile `profiles/security-infra/` ships with complete domain files and generated content.

## Commands

All API commands (`all`, `syllabus`, `content`, `add`, `setup`) require `--profile`.

| Command | What it does |
|---------|-------------|
| `prep.py init <name>` | Create new profile skeleton with domain/ stubs |
| `prep.py setup --profile P` | Generate domain files (3 API calls, ~$5-10) |
| `prep.py all --profile P` | Full pipeline: auto-runs setup if needed, then syllabus -> content -> package |
| `prep.py syllabus --profile P` | Generate agendas only (8 API calls) |
| `prep.py content --profile P` | Generate content for existing agendas |
| `prep.py content --profile P --episode 5` | Generate content for one episode |
| `prep.py add doc.pdf --profile P` | Distill doc -> content -> package |
| `prep.py package --profile P` | Repackage outputs into Gem + NotebookLM |
| `prep.py render prompts/gem.md --profile P` | Substitute vars and print to stdout |
| `prep.py status` | List all profiles |
| `prep.py status --profile P` | Show pipeline progress for a profile |

Common flags: `--force` (regenerate existing), `--yes` (skip cost confirmation).

## Setting Up a New Domain

### 1. Create a profile

```bash
python prep.py init data-eng
```

This creates `profiles/data-eng/` with a template `profile.md` and 4 stub files in `domain/`.

### 2. Generate domain content

**Option A: Automated** (~$5-10, 3 API calls)
```bash
# Edit profiles/data-eng/profile.md first (fill in role, company, domain)
python prep.py setup --profile data-eng --yes
```

**Option B: Manual** ($0)
Paste `prompts/intake.md` into any AI chat (ChatGPT, Claude, Gemini). The intake prompt interviews you about your role, domain, and sub-areas, then generates all 5 files (`profile.md` + 4 domain files) ready to copy-paste.

### 3. Fill in your profile

Save the generated files:
- `profiles/data-eng/profile.md`
- `profiles/data-eng/domain/seeds.md`
- `profiles/data-eng/domain/coverage.md`
- `profiles/data-eng/domain/lenses.md`
- `profiles/data-eng/domain/gem-sections.md`

### 4. Generate content

```bash
# Test run with a cheap model first
python prep.py syllabus --profile data-eng --yes

# Review agendas in profiles/data-eng/outputs/syllabus/
# If satisfied, generate full content:
python prep.py all --profile data-eng --yes
```

### Domain file format

Domain files use `<!-- MARKER_NAME -->` HTML comment delimiters to define sections. Each marker corresponds to a placeholder in the shared prompt templates. See `profiles/security-infra/domain/` for a complete example.

| File | Markers | Injected into |
|------|---------|--------------|
| `seeds.md` | `DOMAIN_SEEDS` | syllabus.md |
| `coverage.md` | `COVERAGE_FRAMEWORK` | syllabus.md |
| `lenses.md` | `DOMAIN_LENS`, `NITTY_GRITTY_LAYOUT`, `DOMAIN_REQUIREMENTS`, `DISTILL_REQUIREMENTS`, `STAKEHOLDERS` | content.md, distill.md |
| `gem-sections.md` | `GEM_BOOKSHELF`, `GEM_EXAMPLES`, `GEM_CODING`, `GEM_FORMAT_EXAMPLES` | gem.md |

## Using the Outputs

### Output directories

| Directory | Contents |
|-----------|----------|
| `profiles/<name>/outputs/syllabus/` | Episode agendas — one per episode, plus `scaffold.md` and `final_merge.md` |
| `profiles/<name>/outputs/episodes/` | Full content documents — the canonical study material |
| `profiles/<name>/outputs/notebooklm/` | Same episode files, copied for easy NotebookLM upload |
| `profiles/<name>/outputs/gem/` | Episodes merged in pairs (ep 1-2 → gem-1.md, ep 3-4 → gem-2.md, etc.) to fit Gem token limits |
| `profiles/<name>/outputs/raw/` | Raw API responses — backup for debugging. If something goes wrong, these preserve the original LLM output |

### NotebookLM Podcasts

Each episode content document becomes a podcast source. For each episode:

1. Create a new NotebookLM notebook
2. Upload the episode content file from `profiles/<name>/outputs/episodes/` as a source
3. Copy the prompt from `prompts/notebooklm.md` and use it as the generation instruction
4. Generate the podcast

The prompt infers the narrative format (postmortem, debate, war story, etc.) from the episode content — no per-episode frames needed.

### Gemini Gem Coaching Bot

The Gem acts as an interview coach with two personas, three modes, and a concept tracking system:
1. Render the Gem prompt: `python3 prep.py render prompts/gem.md --profile <name>`
2. Create a Gemini Gem, paste the rendered prompt as system instructions
3. Upload the gem files from `outputs/gem/` as knowledge files
4. Start a session: "rapid fire", "interview", or "explore"

## Manual Alternative

If you'd rather not use the API for domain setup, you can generate your domain files for free using any AI chat:

1. Run `python3 prep.py init my-domain` and edit `profiles/my-domain/profile.md`
2. Paste `prompts/intake.md` into ChatGPT, Claude, or Gemini
3. The intake is an interactive conversation — the AI will ask about your role, domain, and sub-areas, then generate all the files you need
4. Copy each output into the matching file under `profiles/my-domain/domain/`
5. Run `python3 prep.py status --profile my-domain` to confirm markers are detected
6. Continue with `python3 prep.py all --profile my-domain`

Tip: test with `gpt-4o-mini` first to validate your domain content, then regenerate with a stronger model.

## Environment Variables

| Variable | Default | Notes |
|----------|---------|-------|
| `OPENAI_API_KEY` | (required) | Get from platform.openai.com |
| `OPENAI_MODEL` | gpt-5.2-pro | Overridden by profile config |
| `OPENAI_EFFORT` | xhigh | Reasoning effort: xhigh, high, medium, low |
| `OPENAI_MAX_TOKENS` | 16000 | Max output tokens |
| `AS_OF_DATE` | Feb 2026 | For frontier digests |
| `PREP_ROLE` | Staff Engineer | Overridden by profile config |
| `PREP_COMPANY` | a top tech company | Overridden by profile config |
| `PREP_DOMAIN` | Security & Infrastructure | Overridden by profile config |
| `PREP_AUDIENCE` | Senior Software Engineers | Overridden by profile config |

When using `--profile`, values in `profile.md` take precedence over env vars.

## Cost Estimates

The pipeline shows a cost estimate before each run and asks for confirmation. Use `--yes` to skip the confirmation prompt. Cost depends on model, episode count, and reasoning effort.

Tests cover prompt assembly, template structure, domain file injection, preflight validation, profile management, setup command, file helpers, skip/resume logic, packaging, manifest generation, and edge cases.

## Prompts

The `prompts/` directory includes:

| Prompt | Purpose |
|--------|---------|
| `syllabus.md` | Syllabus generation (8 chunked runs: scaffold, core batches, frontiers, merge) |
| `content.md` | Episode content generation (dense Staff-level technical documents) |
| `distill.md` | Document distillation (whitepaper/blog -> episode agenda) |
| `gem.md` | Gemini Gem coaching bot system prompt |
| `notebooklm.md` | NotebookLM podcast generation prompt |
| `notebooklm-frames.md` | Per-episode podcast frames |
| `intake.md` | Domain intake interview (generates domain files, $0 cost) |
| `meta-seeds.md` | Seeds + coverage generation (used by `setup` command) |
| `meta-lenses.md` | Domain lenses generation (used by `setup` command) |
| `meta-gem.md` | Gem sections generation (used by `setup` command) |

All prompts use `{PLACEHOLDER}` syntax. Role/company/domain vars are replaced first, then domain content, then user content. This ordering prevents double-replacement when user content contains `{braces}`.

## API Details

Uses the OpenAI **Responses API** (not Chat Completions) with:
- `reasoning.effort: "xhigh"` — extended thinking
- `text.verbosity: "high"` — detailed output
- `background: true` — no timeout risk, polls until done

Calls with high reasoning effort can take several minutes each.

## Tests

```bash
python3 -m unittest test_prep -v
```

Tests cover prompt assembly, template structure, domain file injection, preflight validation, profile management, file helpers, skip/resume logic, packaging, manifest generation, and edge cases.

## Design Docs

Design documents live in `docs/design/`. Convention:
- `{initiative}/brainstorm.md` — Required exploration scratchpad (open questions, analysis, edge cases)
- `{initiative}/backlog.md` — Optional phased plan for larger work
- `docs/decisions/NNNN-short-title.md` — Settled choices (one per file, append-only, centralized)
