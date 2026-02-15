# CLAUDE.md

## Project overview

Interview prep content pipeline. Generates a 15-episode technical deep-dive syllabus using OpenAI's Responses API, then packages output for NotebookLM and Gemini.

## Key files

- `prep.py` — Main pipeline script (single file, ~600 lines)
- `test_prep.py` — 128 unit tests
- `requirements.txt` — Python dependencies (openai>=2.0.0)
- `prompts/syllabus.md` — Syllabus generation prompt (uses `.format()`)
- `prompts/content.md` — Content generation prompt (uses `.replace()`)
- `prompts/distill.md` — Document distillation prompt (uses `.replace()`)
- `.env.example` — Config template matching actual env var names (values quoted for shell sourcing)

## Architecture

Pipeline flow: `syllabus` (8 runs) -> `content` (15 episodes) -> `package` (gem + notebooklm)

Role is parameterized via env vars (`PREP_ROLE`, `PREP_COMPANY`, `PREP_DOMAIN`, `PREP_AUDIENCE`) — no hardcoded role/company in code or prompts.

Prompt templates use two substitution patterns:
- `syllabus.md` uses Python `.format()` — all placeholders are `{NAMED}`
- `content.md` and `distill.md` use `.replace()` — because user content (agendas, raw docs) may contain `{braces}`
- Role vars are replaced BEFORE user content injection to avoid double-replacement

## Commands

```bash
python prep.py all                        # Full pipeline
python prep.py syllabus                   # Generate agendas only
python prep.py content                    # Generate content for existing agendas
python prep.py add <file> --gem-slot N    # Distill doc -> content -> package
python prep.py package                    # Repackage outputs
python prep.py status                     # Show what exists
```

## Testing

```bash
python -m unittest test_prep -v
```

Tests use `unittest` with `MagicMock` for the OpenAI client. Many tests redirect dirs to `tempfile.mkdtemp()` and restore in tearDown. No real API calls in tests.

## Style

- Single-file script, no classes (functions + module-level config)
- Python 3.9+ required
- `os.environ.get()` for all config, no python-dotenv dependency
- Generated content in `outputs/` is committed (it cost ~$50 to generate)
- `.env` is gitignored; `.env.example` is committed
