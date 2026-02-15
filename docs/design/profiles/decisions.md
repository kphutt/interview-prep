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

10. **Dynamic episode counts implemented** — `PREP_CORE_EPISODES` (default 12) and `PREP_FRONTIER_EPISODES` (default 3) env vars control episode counts. All derived state (`CORE_EPS`, `FRONTIER_EPS`, `ALL_EPS`, `SYLLABUS_RUNS`, gem slots, manifest) is regenerated from these counts. Batch size stays at 4 (`ceil(core/4)` batches). Gem pairing stays at 2 (`ceil(core/2)` core slots + optional frontier slot + misc slot). `_reconfigure(core, frontier)` atomically resets all derived state. All new functions take explicit parameters with defaults (`frontier_map()`, `gem_slot()`, `_total_gem_slots()`, `build_syllabus_runs()`). With no env vars set, output is identical to the previous hardcoded behavior.

11. **All prompts use `.replace()` substitution** — `syllabus_prompt()` switches from `.format(**kwargs)` to chained `.replace()` calls, matching `content_prompt()` and `distill_prompt()`. Placeholder syntax stays `{NAMED}`. This prevents `{braces}` in Phase 4's injected domain content from breaking substitution and aligns all prompts on one pattern.

12. **Hand-parse YAML frontmatter, no pyyaml** — profile.md frontmatter is simple `key: value` lines. Hand-parsing with case-insensitive key matching and optional quoting keeps the zero-dependency philosophy. If frontmatter complexity grows later, reconsider.

13. **S&I content migrates to `profiles/security-infra/`** — existing `outputs/` moves to `profiles/security-infra/outputs/` via `git mv`. Provides a reference example of a complete profile. Resolves Q1 (migration path) and Q14 (does S&I become a profile).

14. **`generate-prompts` command renamed to `adapt`** — the command generates domain injection fragments (seeds.md, coverage.md, lenses.md, gem-sections.md), not prompts. `adapt` describes what it does: adapt prompts to a domain.

15. **`domain/` directory renamed to `adapted/`** — `profiles/{name}/adapted/` signals "machine-generated intermediates from the adapt command," not "user-created domain inputs." Matches the `adapt` command name.

16. **Prompt versioning deferred** — re-generation cost ($5-30) is low enough that "just regenerate" is acceptable. Hash tracking adds complexity for minimal benefit at this stage. Revisit if prompt iteration becomes frequent.

17. **Per-episode syllabus regeneration deferred** — the batch sequence (scaffold → core batches → frontier → merge) generates episodes in groups of 4. Regenerating one episode means re-running its batch, which affects sibling episodes. Content `--episode N` is supported (each content episode is an independent API call). Revisit if users frequently need single-episode syllabus fixes.

18. **Smart NotebookLM prompt requires validation** — decision #1 assumes a single smart prompt produces sufficient format variety (postmortem, debate, war story, etc.) without per-episode frames. Must validate with 3-5 existing episodes before Phase 4.4 eliminates frames. If validation fails, keep frames but make them domain-injectable.
