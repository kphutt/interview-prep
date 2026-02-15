# Decisions: Profiles

1. **Smart NotebookLM prompt** — one prompt tells NotebookLM to pick the episode format (postmortem/debate/war story/etc.) from the content. No per-episode frames needed. Removes human from the loop.

2. **Bookshelf is optional** — the Gem works without it. Power users add it later when deep in prep. If `bookshelf.md` exists in profile, inject it into rendered Gem prompt. If not, skip it.

3. **Personas are optional** — the two-persona structure (Domain Expert + RRK) ships as a solid default. Users customize if they want.

4. **PREP_AUDIENCE probably goes away** — resume captures who the candidate is, PREP_ROLE captures the target. The gap between them IS the calibration. "Audience" was ambiguous (candidate? interviewer? podcast listener?).

5. **Episode count is dynamic** — determined by timeline + scope, not hardcoded. Interview tomorrow → 3 episodes. Month out → 12+. Currently hardcoded to 15 (12 core + 3 frontier) throughout prep.py and syllabus.md.

6. **Interview dates include focus areas** — not just dates but what each interview covers (domain, system design, coding, behavioral). Shapes episode focus.

7. **The intake prompt is craft** — `prompts/intake.md` is a showcase piece like the Gem and NotebookLM prompts. First pass created here, refined by user in AI chats.

8. **Both intake paths produce the same artifact** — whether AI-interviewed or manually filled, `profile.md` has the same format. prep.py consumes it the same way.

9. **Every API step can be done manually instead** — the user can copy the prompts, run them in their own AI chat, and paste results back. For a small prep (3 episodes), someone might never call the API at all — just use the prompts with their own AI and let the non-API parts (packaging, rendering) handle the rest. The tool should never force an API call when the user has another way to get the same artifact.
