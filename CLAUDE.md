# CLAUDE.md

## Project overview

Interview prep content pipeline. Generates a technical deep-dive syllabus (configurable episode count, default 12 core + 3 frontier) using OpenAI's Responses API, then packages output for NotebookLM and Gemini.

## Key files

- `prep.py` — Main pipeline script (single file, ~1400 lines)
- `test_prep.py` — ~307 unit tests
- `requirements.txt` — Python dependencies (openai>=2.0.0)
- `profiles/security-infra/` — Reference profile with generated content
- `prompts/syllabus.md` — Syllabus generation prompt (uses `.replace()`)
- `prompts/content.md` — Content generation prompt (uses `.replace()`)
- `prompts/distill.md` — Document distillation prompt (uses `.replace()`)
- `prompts/intake.md` — Domain intake interview (generates domain files, $0 cost)
- `prompts/meta-seeds.md` — Meta-prompt for seeds + coverage (used by `adapt` command)
- `prompts/meta-lenses.md` — Meta-prompt for domain lenses (used by `adapt` command)
- `prompts/meta-gem.md` — Meta-prompt for gem sections (used by `adapt` command)
- `prompts/gem.md` — Gemini Gem system prompt (manual use, not processed by pipeline)
- `prompts/notebooklm.md` — NotebookLM podcast prompt (manual use, not processed by pipeline)
- `prompts/notebooklm-frames.md` — Per-episode frames that seed each NotebookLM podcast run
- `.env.example` — Config template matching actual env var names (values quoted for shell sourcing)

## Architecture

Pipeline flow: `syllabus` -> `content` -> `package` (gem + notebooklm). Episode count is set by `core_episodes` + `frontier_episodes` in profile.md (default 12+3). Syllabus run count scales with episode count.

Multi-profile support: `--profile <name>` redirects all I/O to `profiles/<name>/`. API commands (`all`, `syllabus`, `content`, `add`, `adapt`) require `--profile`; non-API commands (`status`, `render`, `package`) work without it.

Role is parameterized via env vars (`PREP_ROLE`, `PREP_COMPANY`, `PREP_DOMAIN`, `PREP_AUDIENCE`) or profile config — no hardcoded role/company in code or prompts.

All prompt templates use `.replace()` — because user content (agendas, raw docs) may contain `{braces}`. Role vars are replaced BEFORE user content injection to avoid double-replacement.

System instructions (`_syllabus_instructions()`, `_content_instructions()`, `_distill_instructions()`, `_adapt_instructions()`) are functions (not constants) so they reflect profile-loaded config.

Domain-specific content lives in `profiles/<name>/domain/` (4 files: seeds.md, coverage.md, lenses.md, gem-sections.md). These are injected into prompt templates via `{MARKER}` placeholders by `_inject_domain()`. Generated automatically by `adapt` command or manually via `prompts/intake.md`.

## Commands

```bash
python prep.py init <profile-name>        # Create new profile skeleton
python prep.py adapt --profile P          # Generate domain files (3 API calls, ~$5-10)
python prep.py all    --profile P        # Full pipeline
python prep.py syllabus --profile P      # Generate agendas only
python prep.py content --profile P [--episode N]  # Generate content
python prep.py add <file> --gem-slot N    # Distill doc -> content -> package
python prep.py package [--profile P]      # Repackage outputs
python prep.py render <file> [--profile P] # Substitute env vars, print to stdout
python prep.py status  [--profile P]      # Show what exists (pipeline view with --profile)
```

Common flags: `--force` (regenerate), `--yes` (skip cost confirmation), `--profile` (use profile config/dirs).

## Testing

```bash
python3 -m unittest test_prep -v
```

Tests use `unittest` with `MagicMock` for the OpenAI client. Many tests redirect dirs to `tempfile.mkdtemp()` and restore in tearDown. No real API calls in tests.

## Style

- Single-file script, no classes (functions + module-level config)
- Python 3.9+ required
- `os.environ.get()` for all config, no python-dotenv dependency
- Generated content in `profiles/security-infra/outputs/` is committed (it cost ~$50 to generate)
- `.env` is gitignored; `.env.example` is committed

## Design docs

Design documents live in `docs/design/`. Convention:

- `backlog.md` — Ideas not yet tied to an initiative (short paragraphs)
- `{initiative}/brainstorm.md` — Exploration, specs, open questions, code impact
- `{initiative}/decisions.md` — Settled choices (extracted from brainstorm, append-only)

Lifecycle: backlog item → initiative folder with brainstorm → decisions extracted as they're made.
