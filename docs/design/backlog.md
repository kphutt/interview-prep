# Design backlog

Prioritized by what helps new users get started and get value fastest.

## Tier 1 — Reduce first-run friction

### `prep.py validate` command

Add a `validate` subcommand that checks env vars, profile fields, and adapted file markers before any API calls. Catches misconfigurations early (blank fields, missing API key, malformed markers) instead of failing mid-pipeline. Highest-impact friction reduction from the [friction audit](friction-audit.md).

### Expanded use cases

Certification prep (mapped to exam domains like CISSP, AWS SA) and curiosity-driven learning (topic interest, no deadline). The architecture should handle these eventually, but profiles ships with job interview support first. Even lightweight prompt variants per use case would broaden who can use the tool without architectural changes.

### Local intake model

Run the intake interview locally (`prep.py intake --profile P`) instead of pasting into an external AI. Eliminates the biggest onboarding speed bump — the context switch to another tool mid-setup. The user already has an OpenAI key configured; use it.

### Offline local models

Support local LLMs (e.g. Ollama, llama.cpp) as an alternative to the OpenAI API. Removes the API key requirement and makes the tool free to run. Trade-off: output quality will likely be significantly worse — the prompts are tuned for frontier reasoning models, and local models may struggle with the structured multi-section format, domain depth, and long-context syllabus continuity. Worth testing but expectations should be low.

### NotebookLM batch setup documentation

The biggest time sink in the workflow is creating 15 individual NotebookLM notebooks (30-45 min of repetitive clicking). Document a streamlined workflow or provide a helper script that generates per-episode instructions with pre-extracted prompts from `notebooklm-frames.md`. Cannot fully automate (no NotebookLM API) but can reduce friction significantly.

### Smoketest `--force` in README

The README snippet `python3 prep.py all --profile smoketest --yes` silently skips because outputs already exist. Needs `--force` or a note. Tiny fix, outsized first-impression impact.

## Tier 2 — Improve output quality

### Resume as input

Use the candidate's resume for baseline assessment and gap identification. Lets the pipeline focus on gaps rather than familiar ground. Stored at `profiles/{name}/inputs/resume.pdf`.

### Gap tracking and feedback loop

The Gem interview coach reveals gaps during practice — topics where answers are weak or the syllabus didn't go deep enough. The existing workflow (done manually): identify gaps, generate targeted study content (like `gaps-brief.md`), feed it back into the bot via `prep.py add` so the coach has that knowledge too. This is a loop: generate, study, practice, identify gaps, generate more. The `add` command already handles distill-and-package; the missing pieces are structured gap identification from coaching sessions and a way to generate study content targeting specific weak areas.

## Tier 2.5 — Operational robustness

### Rate-limit aware retry

`call_llm` retries at 2/4/8s for all errors. OpenAI `RateLimitError` (429) can require minutes. Should read `Retry-After` header or use longer backoff for 429s.

### Partial failure exit codes

`cmd_content` returns `True` even when episodes fail. A 12/15 run looks identical to 15/15. Should surface the failure count and return a clear warning or non-zero exit.

## Tier 3 — Contributor/maintainer experience

### Globals refactor / PrepConfig class

Mutable globals modified by `set_profile()` and `_reconfigure()` create implicit coupling. Tests save/restore these globals in setUp/tearDown. Refactor to a `PrepConfig` class passed explicitly to functions. Unblocks clean file splitting if codebase grows. Separate design initiative.

### CONTRIBUTING.md

No guide for contributors. Should cover: running tests, the global-save/restore pattern, why `.replace()` not `.format()`, profile system architecture.

### Remove `prep-backup.py`

A 603-line pre-refactor copy is committed. `.gitignore` blocks new backups but this one is already tracked. Confusing to anyone who clones.

## Tier 4 — Speculative / advanced

### Interviewer-aware tailoring

Incorporate interviewer info (LinkedIn profiles, published articles) to tailor content toward likely questions. Advanced feature, stored in `profiles/{name}/inputs/interviewers/`.

## Done

### ~~Meta-prompt workflow~~

Promoted to [profiles brainstorm](profiles/brainstorm.md#meta-prompt-workflow).

### ~~Model-agnostic API calls~~ ✅

Done. `_MODEL_CAPS` now carries per-model allowed effort levels, `_clamp_effort()` adjusts invalid efforts to the nearest valid level, and `call_llm()` has a `BadRequestError` safety net that strips unsupported params on 400s. Cost table updated with `gpt-5.2-pro` and `gpt-4o-mini`.

### ~~Defensive validation hardening~~ ✅

Done. Four guards added: blank required profile fields error with specific message, `cmd_content` suggests running syllabus when all agendas missing, `cmd_init` validates profile names against `^[a-zA-Z0-9][a-zA-Z0-9_-]*$`, and `cmd_add` catches `UnicodeDecodeError` on binary files.

### ~~Friction and manual-step audit~~ ✅

Done. Audit document at [docs/design/friction-audit.md](friction-audit.md) catalogs 19 friction points across 10 pipeline steps (3 High, 7 Medium, 9 Low). E2E smoke test (`TestFullPipelineSmoke`) exercises init → setup → syllabus → content → package → status → render with mocked API calls. Findings added to backlog: `validate` command, NotebookLM batch setup docs.
