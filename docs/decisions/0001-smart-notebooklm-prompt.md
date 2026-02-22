# Smart NotebookLM prompt

## Status
Accepted

## Context
Per-episode frames required manual effort to assign formats (postmortem, debate, war story, etc.) to each episode.

## Decision
One prompt tells NotebookLM to pick the episode format from the content. No per-episode frames needed. Removes human from the loop.

## Consequences
Shipped in Phase 4.4. `notebooklm.md` now includes an Episode Format section with signal-to-format mapping. `notebooklm-frames.md` retained as reference but no longer required.
