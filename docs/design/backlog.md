# Design backlog

## Meta-prompt workflow

Every prompt in the pipeline was originally created by first writing a meta-prompt (a prompt that generates the actual prompt), then iterating on the output. This is the process that made the prompts good. For new domains/profiles, the pipeline should formalize this: meta-prompts that take profile inputs and generate domain-specific prompts (e.g., the training data section of syllabus.md, the episode content prompt calibrated to a new domain). The meta-prompts themselves are showcase artifacts.

The most concrete need: `prompts/syllabus.md` has ~120 lines of domain-specific training data (episode seeds, mental models, protocols) that make the output consistently good. For a new profile, this entire section must be different. The intake prompt could produce episode seeds as part of its output, or a dedicated meta-prompt could generate the training data section given the profile inputs. Either way, this is the primary use case for the meta-prompt workflow.

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
