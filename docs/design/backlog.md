# Design backlog

## Meta-prompt workflow

Promoted to [profiles brainstorm](profiles/brainstorm.md#meta-prompt-workflow).

## Gap tracking and feedback loop

The Gem interview coach reveals gaps during practice — topics where answers are weak or the syllabus didn't go deep enough. The existing workflow (done manually): identify gaps, generate targeted study content (like `gaps-brief.md`), feed it back into the bot via `prep.py add` so the coach has that knowledge too. This is a loop: generate, study, practice, identify gaps, generate more. The `add` command already handles distill-and-package; the missing pieces are structured gap identification from coaching sessions and a way to generate study content targeting specific weak areas.

## Expanded use cases

Certification prep (mapped to exam domains like CISSP, AWS SA) and curiosity-driven learning (topic interest, no deadline). The architecture should handle these eventually, but profiles ships with job interview support first.

## Resume as input

Use the candidate's resume for baseline assessment and gap identification. Lets the pipeline focus on gaps rather than familiar ground. Stored at `profiles/{name}/inputs/resume.pdf`. Deferred for now.

## Interviewer-aware tailoring

Incorporate interviewer info (LinkedIn profiles, published articles) to tailor content toward likely questions. Advanced feature, stored in `profiles/{name}/inputs/interviewers/`.

## Local intake model

Run the intake interview locally instead of pasting into an external AI. Deferred — marginal benefit when paste-into-any-AI works.

## ~~Model-agnostic API calls~~ ✅

Done. `_MODEL_CAPS` now carries per-model allowed effort levels, `_clamp_effort()` adjusts invalid efforts to the nearest valid level, and `call_llm()` has a `BadRequestError` safety net that strips unsupported params on 400s. Cost table updated with `gpt-5.2-pro` and `gpt-4o-mini`.

## Globals refactor / PrepConfig class

Mutable globals modified by `set_profile()` and `_reconfigure()` create implicit coupling. Tests save/restore these globals in setUp/tearDown. Refactor to a `PrepConfig` class passed explicitly to functions. Unblocks clean file splitting if codebase grows. Separate design initiative.

## Defensive validation hardening

Several edge cases pass silently when they should error or warn:

- **Empty profile field validation:** `role:` with no value passes YAML parsing but causes blank prompts
- **cmd_content silent skip:** missing agendas cause silent episode skips; should suggest running `syllabus` first
- **Profile name validation:** no check for spaces or special chars in profile names
- **`add` command input format:** code only reads UTF-8 text; binary files (e.g., PDF) will fail silently or crash
