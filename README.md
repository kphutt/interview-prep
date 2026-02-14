# Interview Prep Pipeline

One command generates a 15-episode technical deep-dive syllabus with content, packaged for NotebookLM and Gemini.

Built with prompt engineering + OpenAI's Responses API. The prompts are the crown jewels — they define episode structure, depth targets, and quality self-checks that consistently produce Staff-level technical content.

## Quick Start

```bash
pip install openai

# Copy and edit your config
cp .env.example .env
# Edit .env: set OPENAI_API_KEY and your target role

# Source your config
source .env && export $(grep -v '^#' .env | xargs)

# Run everything
python prep.py all
```

## Configure Your Target Role

Edit `.env` to set your interview target:

```bash
PREP_ROLE="Principal SRE"
PREP_COMPANY="Meta"
PREP_DOMAIN="Reliability & Infrastructure"
PREP_AUDIENCE="Senior Software Engineers"
```

These flow into the system instructions and prompt templates. The pipeline generates content tailored to your role, company, and domain.

## Commands

| Command | What it does |
|---------|-------------|
| `prep.py all` | Full pipeline: syllabus -> content -> package |
| `prep.py syllabus` | Generate agendas only (8 API calls) |
| `prep.py content` | Generate content for existing agendas |
| `prep.py add paper.pdf --gem-slot 3` | Distill doc -> content -> package |
| `prep.py package` | Repackage into Gem + NotebookLM |
| `prep.py status` | Show what exists |

## Output

```
outputs/
  notebooklm/   <- Upload to NotebookLM (individual episode files)
  gem/           <- Upload to Gemini (8 merged files)
    gem-1.md       episodes 1-2
    gem-2.md       episodes 3-4
    gem-3.md       episodes 5-6
    gem-4.md       episodes 7-8
    gem-5.md       episodes 9-10
    gem-6.md       episodes 11-12
    gem-7.md       frontiers 13-15
    gem-8.md       misc
```

## Existing Files

Drop into `inputs/` with these names — pipeline skips what exists:
- `inputs/agendas/episode-01-agenda.md`
- `inputs/episodes/episode-01-content.md`

## Environment

| Variable | Default | Notes |
|----------|---------|-------|
| OPENAI_API_KEY | (required) | Get from platform.openai.com |
| OPENAI_MODEL | gpt-5.2-pro | Uses Responses API |
| OPENAI_EFFORT | xhigh | Reasoning effort: xhigh, high, medium, low |
| OPENAI_MAX_TOKENS | 16000 | Max output tokens |
| AS_OF_DATE | Feb 2026 | For frontier digests |
| PREP_ROLE | Staff Engineer | Your target role |
| PREP_COMPANY | a top tech company | Target company |
| PREP_DOMAIN | Security & Infrastructure | Interview domain |
| PREP_AUDIENCE | Senior Software Engineers | Content audience |

## Tests

```bash
python -m pytest test_prep.py
# or
python -m unittest test_prep -v
```

128 tests covering prompt assembly, template structure, file helpers, skip/resume logic, packaging, manifest generation, and edge cases.

## API Details

Uses the OpenAI **Responses API** (not Chat Completions) with:
- `reasoning.effort: "xhigh"` — extended thinking
- `text.verbosity: "high"` — detailed output
- `background: true` — no timeout risk, polls until done

Each call may take 1-5 minutes with Pro + xhigh effort.
Full pipeline (~20 calls) takes roughly 30-60 minutes.
Cost: ~$25-30 for full generation with gpt-5.2-pro.

To reduce cost:
```bash
export OPENAI_MODEL='gpt-5.2'
export OPENAI_EFFORT='high'
```
