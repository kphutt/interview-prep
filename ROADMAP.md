# Roadmap

Prioritized by what helps new users get started and get value fastest.

## Tier 1 — Reduce first-run friction

### Better profile.md template and init output

The `init` template body says "Add any extra context here" — doesn't mention job descriptions or explain that the body directly feeds `setup` and significantly improves output quality. Two changes: (1) rename the template section to "Job Description & Context" with a clear prompt to paste the JD, (2) update `cmd_init` output to explicitly tell users to paste the JD and why it matters.

### ~~`all` auto-runs setup~~ ✅

Implemented: `all` detects stub domain files and auto-runs `setup` before proceeding. See `docs/design/onboarding/` for future phases.

### `prep.py clean --profile P`

No way to reset generated outputs without `rm -rf profiles/P/outputs/`, which risks deleting domain files by accident. A `clean` command that only removes generated outputs (syllabus, episodes, gem, notebooklm, raw) would be safer.

### Progress during API calls

`call_llm` can take 30-90 seconds per call with no output. A simple elapsed timer or "waiting..." indicator would reassure users the pipeline isn't hung.

### Post-run cost summary

There's a cost confirmation before runs but no summary after. Printing "This run used ~N calls (~$X estimated)" at the end helps users budget, especially on first runs.

### `status` surfaces validate issues

`status --profile P` doesn't flag config issues (missing API key, stub domain files). If it did, users could catch problems before spending on API calls.

### Expanded use cases

Certification prep (mapped to exam domains like CISSP, AWS SA) and curiosity-driven learning (topic interest, no deadline). The architecture should handle these eventually, but profiles ships with job interview support first. Even lightweight prompt variants per use case would broaden who can use the tool without architectural changes.

### Local intake model

Run the intake interview locally (`prep.py intake --profile P`) instead of pasting into an external AI. Eliminates the biggest onboarding speed bump — the context switch to another tool mid-setup. The user already has an OpenAI key configured; use it.

### Offline local models

Support local LLMs (e.g. Ollama, llama.cpp) as an alternative to the OpenAI API. Removes the API key requirement and makes the tool free to run. Trade-off: output quality will likely be significantly worse — the prompts are tuned for frontier reasoning models, and local models may struggle with the structured multi-section format, domain depth, and long-context syllabus continuity. Worth testing but expectations should be low.

### NotebookLM batch setup documentation

The biggest time sink in the workflow is creating 15 individual NotebookLM notebooks (30-45 min of repetitive clicking). Document a streamlined workflow or provide a helper script that generates per-episode instructions with pre-extracted prompts from `notebooklm-frames.md`. Cannot fully automate (no NotebookLM API) but can reduce friction significantly.

## Tier 2 — Improve output quality

### Resume as input

Use the candidate's resume for baseline assessment and gap identification. Lets the pipeline focus on gaps rather than familiar ground. Stored at `profiles/{name}/inputs/resume.pdf`.

### Gap tracking and feedback loop

The Gem interview coach reveals gaps during practice — topics where answers are weak or the syllabus didn't go deep enough. The existing workflow (done manually): identify gaps, generate targeted study content (like `gaps-brief.md`), feed it back into the bot via `prep.py add` so the coach has that knowledge too. This is a loop: generate, study, practice, identify gaps, generate more. The `add` command already handles distill-and-package; the missing pieces are structured gap identification from coaching sessions and a way to generate study content targeting specific weak areas.

## Tier 2.5 — Operational robustness

### Rate-limit aware retry

`call_llm` retries at 2/4/8s for all errors. OpenAI `RateLimitError` (429) can require minutes. Should read `Retry-After` header or use longer backoff for 429s.

## Tier 3 — Contributor/maintainer experience

### Globals refactor / PrepConfig class

Mutable globals modified by `set_profile()` and `_reconfigure()` create implicit coupling. Tests save/restore these globals in setUp/tearDown. Refactor to a `PrepConfig` class passed explicitly to functions. Unblocks clean file splitting if codebase grows. Separate design initiative.

### CONTRIBUTING.md

No guide for contributors. Should cover: running tests, the global-save/restore pattern, why `.replace()` not `.format()`, profile system architecture.

## Tier 4 — Speculative / advanced

### Interviewer-aware tailoring

Incorporate interviewer info (LinkedIn profiles, published articles) to tailor content toward likely questions. Advanced feature, stored in `profiles/{name}/inputs/interviewers/`.

## Done

- ~~Meta-prompt workflow~~ — Promoted to [profiles brainstorm](docs/design/profiles/brainstorm.md#meta-prompt-workflow).
- ~~Model-agnostic API calls~~ ✅ — `_MODEL_CAPS`, `_clamp_effort()`, `BadRequestError` safety net.
- ~~Defensive validation hardening~~ ✅ — Blank field errors, missing syllabus hints, profile name validation, binary file guard.
- ~~Friction and manual-step audit~~ ✅ — [Audit doc](docs/design/friction-audit.md): 19 friction points, E2E smoke test.
- ~~`prep.py validate` command~~ ✅ — Folded into `status`: checks API key, profile fields, domain markers, prompt files.
- ~~Smoketest `--force` in README~~ ✅ — Auto-detects complete pipeline, suggests `--force`.
- ~~Partial failure exit codes~~ ✅ — `cmd_content` tracks and reports failures.
- ~~Remove `prep-backup.py`~~ ✅ — Already gitignored, not tracked.
- ~~Profile-only mode cleanup~~ ✅ — Smoke test uses `--profile` throughout.
