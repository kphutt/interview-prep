# Interview Prep Pipeline

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue?logo=python&logoColor=white)](https://www.python.org)
[![License: MIT](https://img.shields.io/badge/license-MIT-yellow.svg)](LICENSE)
[![Tests: 291 passed](https://img.shields.io/badge/tests-291_passed-brightgreen)]()

A prompt-engineering pipeline that generates technical deep-dive content using OpenAI's Responses API, packaged for NotebookLM podcasts and a Gemini coaching bot. Works for any interview domain via profiles.

The prompts are the crown jewels — they define episode structure, depth targets, and quality self-checks that consistently produce Staff-level technical content. The repo ships with 15 episodes of Security & Infrastructure content as a reference profile.

## Quick Start

```bash
pip install -r requirements.txt

cp .env.example .env
# Edit .env: add your OPENAI_API_KEY

# Load config
set -a && source .env && set +a

# Create a profile for your domain
python prep.py init my-domain

# Generate adapted content (see "Adapting to a New Domain" below)
# Then generate everything:
python prep.py all --profile my-domain
```

## Profiles

Every interview domain lives in its own profile under `profiles/<name>/`. A profile contains:

```
profiles/my-domain/
  profile.md           <- Config: role, company, domain, model, episode counts
  adapted/             <- Domain-specific content injected into shared prompts
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

The reference profile `profiles/security-infra/` ships with complete adapted files and generated content.

## Commands

All API commands (`all`, `syllabus`, `content`, `add`) require `--profile`.

| Command | What it does |
|---------|-------------|
| `prep.py init <name>` | Create new profile skeleton with adapted/ stubs |
| `prep.py all --profile P` | Full pipeline: syllabus -> content -> package |
| `prep.py syllabus --profile P` | Generate agendas only (8 API calls) |
| `prep.py content --profile P` | Generate content for existing agendas |
| `prep.py content --profile P --episode 5` | Generate content for one episode |
| `prep.py add doc.pdf --profile P` | Distill doc -> content -> package |
| `prep.py package --profile P` | Repackage outputs into Gem + NotebookLM |
| `prep.py render prompts/gem.md --profile P` | Substitute vars and print to stdout |
| `prep.py status` | List all profiles |
| `prep.py status --profile P` | Show pipeline progress for a profile |

Common flags: `--force` (regenerate existing), `--yes` (skip cost confirmation).

## Adapting to a New Domain

### 1. Create a profile

```bash
python prep.py init data-eng
```

This creates `profiles/data-eng/` with a template `profile.md` and 4 stub files in `adapted/`.

### 2. Generate adapted content

Paste `prompts/intake.md` into any AI chat (ChatGPT, Claude, Gemini). The intake prompt interviews you about your role, domain, and sub-areas, then generates all 5 files (`profile.md` + 4 adapted files) ready to copy-paste into your profile directory.

Cost: $0 — the intake runs in an external conversation, not through the pipeline.

### 3. Fill in your profile

Save the generated files:
- `profiles/data-eng/profile.md`
- `profiles/data-eng/adapted/seeds.md`
- `profiles/data-eng/adapted/coverage.md`
- `profiles/data-eng/adapted/lenses.md`
- `profiles/data-eng/adapted/gem-sections.md`

### 4. Generate content

```bash
# Test run with a cheap model first
python prep.py syllabus --profile data-eng --yes

# Review agendas in profiles/data-eng/outputs/syllabus/
# If satisfied, generate full content:
python prep.py all --profile data-eng --yes
```

### Adapted file format

Adapted files use `<!-- MARKER_NAME -->` HTML comment delimiters to define sections. Each marker corresponds to a placeholder in the shared prompt templates. See `profiles/security-infra/adapted/` for a complete example.

| File | Markers | Injected into |
|------|---------|--------------|
| `seeds.md` | `DOMAIN_SEEDS` | syllabus.md |
| `coverage.md` | `COVERAGE_FRAMEWORK` | syllabus.md |
| `lenses.md` | `DOMAIN_LENS`, `NITTY_GRITTY_LAYOUT`, `DOMAIN_REQUIREMENTS`, `DISTILL_REQUIREMENTS`, `STAKEHOLDERS` | content.md, distill.md |
| `gem-sections.md` | `GEM_BOOKSHELF`, `GEM_EXAMPLES`, `GEM_CODING`, `GEM_FORMAT_EXAMPLES` | gem.md |

## Using the Outputs

### NotebookLM Podcasts

Each episode content document becomes a podcast source. For each episode:
1. Create a new NotebookLM notebook
2. Upload the episode content file from `outputs/episodes/`
3. Paste the episode frame from `prompts/notebooklm-frames.md` + the system prompt from `prompts/notebooklm.md`
4. Generate the podcast

### Gemini Gem Coaching Bot

The Gem acts as an interview coach with two personas, three modes, and a concept tracking system:
1. Render the Gem prompt: `python prep.py render prompts/gem.md --profile <name>`
2. Create a Gemini Gem, paste the rendered prompt as system instructions
3. Upload the gem files from `outputs/gem/` as knowledge files
4. Start a session: "rapid fire", "interview", or "explore"

## Cost Estimates

The pipeline shows a cost estimate before making API calls. Use `--yes` to skip confirmation.

| Model | Full pipeline (~20 calls) | Syllabus only (~8 calls) |
|-------|--------------------------|-------------------------|
| gpt-5.2-pro (xhigh) | ~$25-30 | ~$10-15 |
| gpt-5.2 (high) | ~$5-10 | ~$2-5 |
| gpt-4o-mini | ~$0.30 | ~$0.15 |

Tip: test with `gpt-4o-mini` first to validate your adapted content, then regenerate with a stronger model.

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

## Tests

```bash
python -m unittest test_prep -v
```

291 tests covering prompt assembly, template structure, adapted file injection, preflight validation, profile management, file helpers, skip/resume logic, packaging, manifest generation, and edge cases.

## Platform Prompts

The `prompts/` directory includes:

| Prompt | Purpose |
|--------|---------|
| `syllabus.md` | Syllabus generation (8 chunked runs: scaffold, core batches, frontiers, merge) |
| `content.md` | Episode content generation (dense Staff-level technical documents) |
| `distill.md` | Document distillation (whitepaper/blog -> episode agenda) |
| `gem.md` | Gemini Gem coaching bot system prompt |
| `notebooklm.md` | NotebookLM podcast generation prompt |
| `notebooklm-frames.md` | Per-episode podcast frames |
| `intake.md` | Domain intake interview (generates adapted files, $0 cost) |

All prompts use `{PLACEHOLDER}` syntax. Role/company/domain vars are replaced first, then adapted domain content, then user content. This ordering prevents double-replacement when user content contains `{braces}`.

## API Details

Uses the OpenAI **Responses API** (not Chat Completions) with:
- `reasoning.effort: "xhigh"` — extended thinking
- `text.verbosity: "high"` — detailed output
- `background: true` — no timeout risk, polls until done

Each call may take 1-5 minutes with Pro + xhigh effort.

## Design Docs

Design documents live in `docs/design/`. Convention:
- `backlog.md` — Ideas not yet tied to an initiative
- `{initiative}/brainstorm.md` — Exploration, specs, open questions
- `{initiative}/decisions.md` — Settled choices (append-only)
