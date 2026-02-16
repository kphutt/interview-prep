# CLAUDE.md

## Project overview

Interview prep content pipeline. Generates a 15-episode technical deep-dive syllabus using OpenAI's Responses API, then packages output for NotebookLM and Gemini.

## Key files

- `prep.py` — Main pipeline script (single file, ~900 lines)
- `test_prep.py` — ~240 unit tests
- `requirements.txt` — Python dependencies (openai>=2.0.0)
- `profiles/security-infra/` — Reference profile with generated content
- `prompts/syllabus.md` — Syllabus generation prompt (uses `.replace()`)
- `prompts/content.md` — Content generation prompt (uses `.replace()`)
- `prompts/distill.md` — Document distillation prompt (uses `.replace()`)
- `prompts/gem.md` — Gemini Gem system prompt (manual use, not processed by pipeline)
- `prompts/notebooklm.md` — NotebookLM podcast prompt (manual use, not processed by pipeline)
- `prompts/notebooklm-frames.md` — Per-episode frames that seed each NotebookLM podcast run
- `.env.example` — Config template matching actual env var names (values quoted for shell sourcing)

## Architecture

Pipeline flow: `syllabus` (8 runs) -> `content` (15 episodes) -> `package` (gem + notebooklm)

Multi-profile support: `--profile <name>` redirects all I/O to `profiles/<name>/`. Without `--profile`, uses top-level `outputs/` and `inputs/` with env vars.

Role is parameterized via env vars (`PREP_ROLE`, `PREP_COMPANY`, `PREP_DOMAIN`, `PREP_AUDIENCE`) or profile config — no hardcoded role/company in code or prompts.

All prompt templates use `.replace()` — because user content (agendas, raw docs) may contain `{braces}`. Role vars are replaced BEFORE user content injection to avoid double-replacement.

System instructions (`_syllabus_instructions()`, `_content_instructions()`, `_distill_instructions()`) are functions (not constants) so they reflect profile-loaded config.

## Commands

```bash
python prep.py init <profile-name>        # Create new profile skeleton
python prep.py all    [--profile P]       # Full pipeline
python prep.py syllabus [--profile P]     # Generate agendas only
python prep.py content [--profile P] [--episode N]  # Generate content
python prep.py add <file> --gem-slot N    # Distill doc -> content -> package
python prep.py package [--profile P]      # Repackage outputs
python prep.py render <file> [--profile P] # Substitute env vars, print to stdout
python prep.py status  [--profile P]      # Show what exists (pipeline view with --profile)
```

Common flags: `--force` (regenerate), `--yes` (skip cost confirmation), `--profile` (use profile config/dirs).

## Testing

```bash
python -m unittest test_prep -v
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
