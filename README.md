# Interview Prep Pipeline

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue?logo=python&logoColor=white)](https://www.python.org)
[![License: MIT](https://img.shields.io/badge/license-MIT-yellow.svg)](LICENSE)
[![Tests: passing](https://img.shields.io/badge/tests-passing-brightgreen)]()

Preparing for a Staff+ technical interview? This tool generates a personalized study syllabus for your domain, then turns each episode into a deep-dive document you can study from, listen to as a podcast (via NotebookLM), or practice with an AI coaching bot (via Gemini Gem).

You describe your target role and domain; the pipeline generates Staff-level technical content tailored to your interviews. Ships with a complete Security & Infrastructure reference profile.

The prompts are the crown jewels — they define episode structure, depth targets, and quality self-checks that consistently produce Staff-level technical content.

## What You Get

The pipeline produces three outputs from your domain description:

1. **Deep-dive study documents** — one episode per topic covering your domain end-to-end, each with Title, Hook, Mental Model, L4 Trap (common wrong answers), Nitty Gritty (protocol/wire details), Staff Pivot, and Scenario Challenge sections
2. **NotebookLM podcasts** — each episode becomes a podcast you can listen to during commutes
3. **Gemini Gem coaching bot** — an interview coach with rapid-fire, mock interview, and explore modes

**Sample episode titles** (from the Security & Infrastructure reference profile):

- Ep 1 — The Binding Problem: mTLS vs DPoP for Sender-Constrained OAuth Tokens
- Ep 2 — The Session Kill Switch: Event-Driven Revocation with CAEP/RISC
- Ep 3 — Mobile Identity: Defeating the Confused Deputy with Universal/App Links + PKCE
- Ep 5 — BeyondCorp: Building a Zero-Trust Proxy (Identity-Aware Access Without the VPN)
- Ep 8 — Supply Chain Security: SLSA Provenance + Deploy-Time Verification
- Ep 10 — Crypto Agility (Post-Quantum): Hybrid TLS + "Rotate the Math Without a Code Push"
- Ep 11 — Envelope Encryption: Rotate Access to Petabytes by Re-wrapping Keys, Not Data

**Sample content depth** (from Episode 1 — Hook section):

> Bearer JWTs are spendable "anywhere, immediately" once copied (logs, headers, JS); sender-constraint reduces replay, but only if enforcement happens at the right hop (edge vs app) without introducing a new single point of failure.
>
> mTLS binding is operationally "clean" for controlled server-to-server clients, but certificate issuance/rotation/revocation is a full product with pager load; adoption failures tend to be spiky and correlated (one bad renewal script can take out a partner cohort).
>
> DPoP fits public clients (mobile/SPAs) but shifts cost to the hot path: per-request signed proofs + replay caches + nonce retry logic; at 200k RPS the CPU and p99 budget impact is real, not theoretical.

Browse the full reference profile: `profiles/security-infra/outputs/episodes/`

## Prerequisites

- **Python 3.9+**
- **OpenAI API key** — get one at [platform.openai.com](https://platform.openai.com)
- Default model is `gpt-5.2-pro`; if you don't have access, set `model: gpt-4o-mini` in your profile.md
- Examples use bash/zsh; see [Troubleshooting](#troubleshooting) for Windows PowerShell and Fish

## Getting Started

```bash
# Install dependencies
pip3 install -r requirements.txt

# Configure API key
cp .env.example .env
# Edit .env: set OPENAI_API_KEY=sk-...

# Load config into your shell
set -a && source .env && set +a

# Create a profile for your domain
python3 prep.py init my-domain
# Edit profiles/my-domain/profile.md with your role, company, and domain

# Generate domain-adapted files (~$2 with gpt-5.2-pro)
python3 prep.py setup --profile my-domain

# Validate your profile is ready
python3 prep.py status --profile my-domain

# Generate everything (shows cost estimate before proceeding)
python3 prep.py all --profile my-domain
```

For a free alternative that skips the API for domain setup, see [Manual Alternative](#manual-alternative).

## Try It Before You Buy It

You don't have to spend anything to evaluate the pipeline. Start small and build confidence:

**$0 — Browse the reference profile:**
- Browse `profiles/security-infra/outputs/episodes/` to see output quality
- Run `python3 prep.py status --profile security-infra` to see what a complete profile looks like

**Pennies — Validate the pipeline end-to-end:**
- The `smoketest` profile ships with 2 episodes + gpt-4o-mini:
  ```bash
  python3 prep.py all --profile smoketest --yes
  ```

**Cheap — Test your domain with gpt-4o-mini:**
- Set `model: gpt-4o-mini` in your profile.md, then:
  ```bash
  python3 prep.py syllabus --profile my-domain --yes
  ```
- Review the generated agendas in `profiles/my-domain/outputs/syllabus/` before committing to full content generation

**Full pipeline:**
- Switch to `model: gpt-5.2-pro` in your profile.md, then:
  ```bash
  python3 prep.py all --profile my-domain
  ```
- The pipeline shows a cost estimate and asks for confirmation before making any API calls

## Profiles

Every interview domain lives in its own profile under `profiles/<name>/`. A profile contains:

```
profiles/my-domain/
  profile.md           <- Config: role, company, domain, model, episode counts
  adapted/             <- Domain-specific content injected into shared prompts
    seeds.md             Episode seed data
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

### Adapted file format

Adapted files use `<!-- MARKER_NAME -->` HTML comment delimiters to define sections. Each marker corresponds to a placeholder in the shared prompt templates. See `profiles/security-infra/adapted/` for a complete example.

| File | Markers | Injected into |
|------|---------|--------------|
| `seeds.md` | `DOMAIN_SEEDS` | syllabus.md |
| `coverage.md` | `COVERAGE_FRAMEWORK` | syllabus.md |
| `lenses.md` | `DOMAIN_LENS`, `NITTY_GRITTY_LAYOUT`, `DOMAIN_REQUIREMENTS`, `DISTILL_REQUIREMENTS`, `STAKEHOLDERS` | content.md, distill.md |
| `gem-sections.md` | `GEM_BOOKSHELF`, `GEM_EXAMPLES`, `GEM_CODING`, `GEM_FORMAT_EXAMPLES` | gem.md |

## Commands

All API commands (`all`, `syllabus`, `content`, `add`) require `--profile`.

| Command | What it does |
|---------|-------------|
| `prep.py init <name>` | Create new profile skeleton with adapted/ stubs |
| `prep.py setup --profile P` | Generate adapted/ files from profile.md via API |
| `prep.py all --profile P` | Full pipeline: syllabus -> content -> package |
| `prep.py syllabus --profile P` | Generate agendas only |
| `prep.py content --profile P` | Generate content for existing agendas |
| `prep.py content --profile P --episode 5` | Generate content for one episode |
| `prep.py add doc.md --profile P [--gem-slot N]` | Distill doc -> content -> package |
| `prep.py package [--profile P]` | Repackage outputs into Gem + NotebookLM |
| `prep.py render prompts/gem.md [--profile P]` | Substitute vars and print to stdout |
| `prep.py status` | List all profiles |
| `prep.py status --profile P` | Show pipeline progress for a profile |

Common flags: `--force` (regenerate existing), `--yes` (skip cost confirmation).

## Pipeline Stages

```
  init          setup / syllabus       content           package
┌───────┐     ┌──────────────┐     ┌────────────┐     ┌──────────┐
│profile│────>│   agendas    │────>│  episodes   │────>│ gem.md + │
│created│     │  generated   │     │  generated  │     │ notebook │
└───────┘     └──────────────┘     └────────────┘     └──────────┘
```

Each stage is **idempotent** — commands skip files that already exist unless you pass `--force`. The pipeline is **resumable**: if content generation stops halfway, re-running the command picks up where it left off.

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

## Cost Estimates

The pipeline shows a cost estimate before each run and asks for confirmation. Use `--yes` to skip the confirmation prompt. Cost depends on model, episode count, and reasoning effort.

Tip: test with `gpt-4o-mini` first to validate your adapted content, then regenerate with a stronger model.

## Manual Alternative

If you'd rather not use the API for domain setup, you can generate your adapted files for free using any AI chat:

1. Run `python3 prep.py init my-domain` and edit `profiles/my-domain/profile.md`
2. Paste `prompts/intake.md` into ChatGPT, Claude, or Gemini
3. The intake is an interactive conversation — the AI will ask about your role, domain, and sub-areas, then generate all the files you need
4. Copy each output into the matching file under `profiles/my-domain/adapted/`
5. Run `python3 prep.py status --profile my-domain` to confirm markers are detected
6. Continue with `python3 prep.py all --profile my-domain`

This replaces the `prep.py setup` step in [Getting Started](#getting-started) — everything else in the pipeline works the same.

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

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `python: command not found` | Use `python3` — macOS doesn't ship a `python` alias |
| `ModuleNotFoundError: openai` | `pip3 install -r requirements.txt` |
| `ERROR: OPENAI_API_KEY not set` | Edit `.env`, then `source .env` (bash/zsh). PowerShell: `$env:OPENAI_API_KEY="sk-..."`. Fish: `set -gx OPENAI_API_KEY sk-...` |
| `ERROR: adapted/seeds.md is empty` | Run `prep.py setup --profile <name>` or see [Manual Alternative](#manual-alternative) |
| `ERROR: --profile required` | Add `--profile <name>` to the command |
| API auth / rate / model error | Check your API key and model access tier; try `model: gpt-4o-mini` in profile.md |
| Cost seems high | The pipeline shows an estimate before each run. Test with `gpt-4o-mini` first |

## Tests

```bash
python3 -m unittest test_prep -v
```

Tests cover prompt assembly, template structure, adapted file injection, preflight validation, profile management, file helpers, skip/resume logic, packaging, manifest generation, and edge cases.

## Platform Prompts

The `prompts/` directory includes:

| Prompt | Purpose |
|--------|---------|
| `syllabus.md` | Syllabus generation (chunked runs: scaffold, core batches, frontiers, merge) |
| `content.md` | Episode content generation (dense Staff-level technical documents) |
| `distill.md` | Document distillation (whitepaper/blog -> episode agenda) |
| `gem.md` | Gemini Gem coaching bot system prompt |
| `notebooklm.md` | NotebookLM podcast generation prompt |
| `notebooklm-frames.md` | Per-episode podcast frames |
| `setup.md` | Automated domain setup (generates adapted files via API) |
| `intake.md` | Domain intake interview (generates adapted files, $0 cost) |

All prompts use `{PLACEHOLDER}` syntax. Role/company/domain vars are replaced first, then adapted domain content, then user content. This ordering prevents double-replacement when user content contains `{braces}`.

## API Details

Uses the OpenAI **Responses API** (not Chat Completions) with:
- `reasoning.effort: "xhigh"` — extended thinking
- `text.verbosity: "high"` — detailed output
- `background: true` — no timeout risk, polls until done

Calls with high reasoning effort can take several minutes each.

## Design Docs

Design documents live in `docs/design/`. Convention:
- `backlog.md` — Ideas not yet tied to an initiative
- `{initiative}/brainstorm.md` — Exploration, specs, open questions
- `{initiative}/decisions.md` — Settled choices (append-only)
