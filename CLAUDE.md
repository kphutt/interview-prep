# CLAUDE.md

## Project overview

Interview prep content pipeline. Generates a technical deep-dive syllabus (configurable episode count, default 12 core + 3 frontier) using OpenAI's Responses API, then packages output for NotebookLM and Gemini.

## Key files

- `prep.py` — Main pipeline script (single file)
- `test_prep.py` — Unit tests
- `requirements.txt` — Python dependencies (openai>=2.0.0)
- `profiles/security-infra/` — Reference profile with generated content
- `prompts/syllabus.md` — Syllabus generation prompt (uses `.replace()`)
- `prompts/content.md` — Content generation prompt (uses `.replace()`)
- `prompts/distill.md` — Document distillation prompt (uses `.replace()`)
- `prompts/setup.md` — Automated domain setup prompt (generates adapted files via API)
- `prompts/intake.md` — Domain intake interview (generates adapted files, $0 cost)
- `prompts/gem.md` — Gemini Gem system prompt (manual use, not processed by pipeline)
- `prompts/notebooklm.md` — NotebookLM podcast prompt (manual use, not processed by pipeline)
- `prompts/notebooklm-frames.md` — Per-episode frames that seed each NotebookLM podcast run
- `.env.example` — Config template matching actual env var names (values quoted for shell sourcing)

## Architecture

Pipeline flow: `syllabus` -> `content` -> `package` (gem + notebooklm). Episode count is set by `core_episodes` + `frontier_episodes` in profile.md (default 12+3). Syllabus run count scales with episode count.

Multi-profile support: `--profile <name>` redirects all I/O to `profiles/<name>/`. API commands (`all`, `syllabus`, `content`, `add`) require `--profile`; non-API commands (`status`, `render`, `package`) work without it.

Role is parameterized via env vars (`PREP_ROLE`, `PREP_COMPANY`, `PREP_DOMAIN`, `PREP_AUDIENCE`) or profile config — no hardcoded role/company in code or prompts.

All prompt templates use `.replace()` — because user content (agendas, raw docs) may contain `{braces}`. Role vars are replaced BEFORE user content injection to avoid double-replacement.

System instructions (`_syllabus_instructions()`, `_content_instructions()`, `_distill_instructions()`) are functions (not constants) so they reflect profile-loaded config.

## Commands

```bash
python3 prep.py init <profile-name>        # Create new profile skeleton
python3 prep.py setup  --profile P        # Generate adapted/ files via API
python3 prep.py all    --profile P        # Full pipeline
python3 prep.py syllabus --profile P      # Generate agendas only
python3 prep.py content --profile P [--episode N]  # Generate content
python3 prep.py add <file> --profile P [--gem-slot N]  # Distill doc -> content -> package
python3 prep.py package [--profile P]      # Repackage outputs
python3 prep.py render <file> [--profile P] # Substitute env vars, print to stdout
python3 prep.py status  [--profile P]      # Show what exists (pipeline view with --profile)
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
