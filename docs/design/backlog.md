# Design backlog

Prioritized by what helps new users get started and get value fastest.

## Tier 1 — Reduce first-run friction

### Expanded use cases

Certification prep (mapped to exam domains like CISSP, AWS SA) and curiosity-driven learning (topic interest, no deadline). The architecture should handle these eventually, but profiles ships with job interview support first. Even lightweight prompt variants per use case would broaden who can use the tool without architectural changes.

### Local intake model

Run the intake interview locally (`prep.py intake --profile P`) instead of pasting into an external AI. Eliminates the biggest onboarding speed bump — the context switch to another tool mid-setup. The user already has an OpenAI key configured; use it.

## Tier 2 — Improve output quality

### Resume as input

Use the candidate's resume for baseline assessment and gap identification. Lets the pipeline focus on gaps rather than familiar ground. Stored at `profiles/{name}/inputs/resume.pdf`.

### Gap tracking and feedback loop

The Gem interview coach reveals gaps during practice — topics where answers are weak or the syllabus didn't go deep enough. The existing workflow (done manually): identify gaps, generate targeted study content (like `gaps-brief.md`), feed it back into the bot via `prep.py add` so the coach has that knowledge too. This is a loop: generate, study, practice, identify gaps, generate more. The `add` command already handles distill-and-package; the missing pieces are structured gap identification from coaching sessions and a way to generate study content targeting specific weak areas.

## Tier 3 — Contributor/maintainer experience

### Globals refactor / PrepConfig class

Mutable globals modified by `set_profile()` and `_reconfigure()` create implicit coupling. Tests save/restore these globals in setUp/tearDown. Refactor to a `PrepConfig` class passed explicitly to functions. Unblocks clean file splitting if codebase grows. Separate design initiative.

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
