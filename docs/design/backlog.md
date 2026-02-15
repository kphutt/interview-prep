# Design backlog

## Meta-prompt workflow

Every prompt in the pipeline was originally created by first writing a meta-prompt (a prompt that generates the actual prompt), then iterating on the output. This is the process that made the prompts good. For new domains/profiles, the pipeline should formalize this: meta-prompts that take profile inputs and generate domain-specific prompts (e.g., the training data section of syllabus.md, the episode content prompt calibrated to a new domain). The meta-prompts themselves are showcase artifacts.

## Gap tracking and feedback loop

The Gem interview coach reveals gaps during practice — topics where answers are weak or the syllabus didn't go deep enough. The existing workflow (done manually): identify gaps, generate targeted study content (like `gaps-brief.md`), feed it back into the bot via `prep.py add` so the coach has that knowledge too. This is a loop: generate, study, practice, identify gaps, generate more. The `add` command already handles distill-and-package; the missing pieces are structured gap identification from coaching sessions and a way to generate study content targeting specific weak areas.
