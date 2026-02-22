# All prompts use .replace() substitution

## Status
Accepted

## Context
`content_prompt()` and `distill_prompt()` used `.replace()` but `syllabus_prompt()` used `.format(**kwargs)`. Injected domain content contains `{braces}` that break `.format()`.

## Decision
All prompts use chained `.replace()` calls. Placeholder syntax stays `{NAMED}`.

## Consequences
Prevents `{braces}` in domain content from breaking substitution. All prompts use one consistent pattern.
