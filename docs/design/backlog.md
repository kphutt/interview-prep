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

## Model-agnostic API calls

`call_llm()` passes `reasoning={"effort": ...}` and `text={"verbosity": "high"}` unconditionally, but these are model-specific: `o4-mini` and `o3` reject `verbosity: "high"`, `gpt-4.1-mini` rejects `reasoning.effort` entirely, and `gpt-5.2-pro` doesn't support `effort: "low"`. The fix: detect model capabilities (or catch 400s and retry without unsupported params), so the pipeline works with cheaper models for smoke tests and iteration. Discovered during API smoke testing of dynamic episode counts.
