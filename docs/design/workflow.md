# End-to-End Workflow Reference

Current-state snapshot of the full journey from clone to podcast. Captures every step, mixing automated pipeline commands with manual platform actions.

For details on env vars, troubleshooting, adapted file markers, and API config, see the [README](../../README.md).

---

## Steps

### 1. Install + API key

| | |
|---|---|
| **Type** | Manual |
| **Cost** | $0 |
| **Prerequisites** | Python 3.9+, OpenAI account |
| **Produces** | Working environment with dependencies and credentials |

```bash
pip3 install -r requirements.txt
cp .env.example .env
# Edit .env: set OPENAI_API_KEY=sk-...
set -a && source .env && set +a
```

### 2. Create profile

| | |
|---|---|
| **Type** | CLI |
| **Cost** | $0 |
| **Command** | `python3 prep.py init <name>` |
| **Prerequisites** | Step 1 |
| **Produces** | `profiles/<name>/` with template `profile.md` and stub files in `adapted/` |

Creates the directory skeleton:

```
profiles/<name>/
  profile.md            <- Config template (role, company, domain, model, episode counts)
  adapted/
    seeds.md            <- Stub
    coverage.md         <- Stub
    lenses.md           <- Stub
    gem-sections.md     <- Stub
  inputs/
    agendas/
    episodes/
    misc/
  outputs/              <- Empty, populated by later steps
```

### 3. Configure profile

| | |
|---|---|
| **Type** | Manual |
| **Cost** | $0 |
| **Prerequisites** | Step 2 |
| **Produces** | A filled-in `profile.md` |

Edit `profiles/<name>/profile.md` to set:

```yaml
---
role: "Staff Engineer"
company: "a top tech company"
domain: "Your Domain"
audience: "Senior Software Engineers"
core_episodes: 12
frontier_episodes: 3
model: "gpt-5.2-pro"
effort: "xhigh"
as_of: "Feb 2026"
---
```

**Alternative (free):** Paste `prompts/intake.md` into any AI chat (ChatGPT, Claude, Gemini). The intake is an interactive conversation — the AI asks about your role and domain, then generates the profile config and all adapted files. Copy results into the appropriate files.

### 4. Generate adapted content

| | |
|---|---|
| **Type** | CLI |
| **Cost** | ~$2 (with gpt-5.2-pro) |
| **Command** | `python3 prep.py setup --profile <name>` |
| **Prerequisites** | Step 3 (filled-in `profile.md`) |
| **Produces** | 4 files in `profiles/<name>/adapted/` |

The setup command reads `profile.md` and generates domain-specific content:

| File | What it contains |
|------|-----------------|
| `seeds.md` | Episode seed data (topics, angles, pairings) |
| `coverage.md` | Coverage framework (e.g., CISSP domains, DAMA-DMBOK) |
| `lenses.md` | Domain lens, Nitty Gritty layout, requirements, stakeholders |
| `gem-sections.md` | Gem coaching bot: bookshelf, examples, coding challenges, format |

These adapted files get injected into the shared prompt templates via marker substitution. Each file uses `<!-- MARKER_NAME -->` HTML comment delimiters.

**Alternative (free):** If you used the intake interview in Step 3, you already have these files — skip this step.

### 5. Validate

| | |
|---|---|
| **Type** | CLI |
| **Cost** | $0 |
| **Command** | `python3 prep.py status --profile <name>` |
| **Prerequisites** | Steps 3–4 |
| **Produces** | Pipeline status report (no files) |

Confirms adapted files are loaded and markers are detected. Fix any issues before spending on API calls. Run `status` without `--profile` to list all profiles.

### 6. Generate syllabus

| | |
|---|---|
| **Type** | CLI |
| **Cost** | ~$5–10 (with gpt-5.2-pro) |
| **Command** | `python3 prep.py syllabus --profile <name>` |
| **Prerequisites** | Step 5 (validated profile) |
| **Produces** | Files in `profiles/<name>/outputs/syllabus/` and `outputs/raw/` |

The syllabus command makes multiple chunked API calls:

1. **Scaffold** — overall episode plan → `scaffold.md`
2. **Core batches + frontier digests** — interleaved: each batch of ~4 core agendas is followed by one frontier digest (e.g., core 1–4, frontier A, core 5–8, frontier B, core 9–12, frontier C) → `episode-NN-agenda.md`
3. **Final merge** — consolidation pass → `final_merge.md`

Raw API responses are saved to `outputs/raw/syllabus-NN-*.md`.

The number of API calls scales with episode count. The pipeline shows a cost estimate and asks for confirmation (skip with `--yes`).

**Review point:** Read the agendas in `outputs/syllabus/` before proceeding. You can edit agendas manually and regenerate individual episodes later. This is the cheapest place to course-correct.

### 7. Generate content

| | |
|---|---|
| **Type** | CLI |
| **Cost** | ~$15–30 (with gpt-5.2-pro, 15 episodes) |
| **Command** | `python3 prep.py content --profile <name>` |
| **Prerequisites** | Step 6 (agendas exist) |
| **Produces** | Files in `profiles/<name>/outputs/episodes/` and `outputs/raw/` |

One API call per episode. Each call takes the episode agenda and produces a dense Staff-level technical document with sections: Title, Hook, Mental Model, Common Trap, Nitty Gritty, Staff Pivot, Scenario Challenge.

Output: `episode-NN-content.md` in `outputs/episodes/`, raw responses in `outputs/raw/`.

Use `--episode N` to generate a single episode. Existing files are skipped unless `--force` is passed.

### 8. Package

| | |
|---|---|
| **Type** | CLI |
| **Cost** | $0 |
| **Command** | `python3 prep.py package --profile <name>` |
| **Prerequisites** | Step 7 (episode content exists) |
| **Produces** | Files in `outputs/gem/` and `outputs/notebooklm/` |

Packaging creates two output formats from the episode content:

**NotebookLM** (`outputs/notebooklm/`): Individual episode files, copied from `outputs/episodes/`. One file per episode.

**Gem** (`outputs/gem/`): Core episodes merged in pairs (ep 1–2 → `gem-1.md`, ep 3–4 → `gem-2.md`, etc.) to fit Gem token limits. All frontier episodes share one slot (ep 13–15 → `gem-7.md`), and one additional slot is reserved for misc content. Also copies `scaffold.md` and `final_merge.md` as `gem-0-scaffold.md` and `gem-0-final_merge.md`.

Note: `prep.py all` runs syllabus → content → package automatically.

### 9. Set up Gem

| | |
|---|---|
| **Type** | Manual |
| **Cost** | $0 |
| **Prerequisites** | Step 8 (packaged gem files) |
| **Produces** | A Gemini Gem coaching bot |

1. Render the Gem prompt:
   ```bash
   python3 prep.py render prompts/gem.md --profile <name>
   ```
2. Create a new Gemini Gem at [gemini.google.com](https://gemini.google.com)
3. Paste the rendered prompt as system instructions
4. Upload the gem files from `outputs/gem/` as knowledge files
5. Start a session with: "rapid fire", "interview", or "explore"

The Gem acts as an interview coach with two personas, three modes, and a concept tracking system.

### 10. Set up NotebookLM

| | |
|---|---|
| **Type** | Manual |
| **Cost** | $0 |
| **Prerequisites** | Step 8 (packaged notebooklm files) |
| **Produces** | NotebookLM podcasts (one per episode) |

For each episode:

1. Create a new NotebookLM notebook at [notebooklm.google.com](https://notebooklm.google.com)
2. Upload the episode content file from `outputs/notebooklm/` (or `outputs/episodes/`) as a source
3. Copy the prompt from `prompts/notebooklm.md` and use it as the generation instruction
4. Generate the podcast

The prompt infers the narrative format (postmortem, debate, war story, etc.) from the episode content — no per-episode customization needed.

`prompts/notebooklm-frames.md` has optional per-episode frames that can seed each podcast run for more variety.

---

## Iteration Workflows

These assume a complete first run. All skip existing files unless `--force` is passed.

**Regenerate one episode's content:**
```bash
python3 prep.py content --profile <name> --episode 5
python3 prep.py package --profile <name>
```

**Edit an agenda, then regenerate its content:**
```bash
# Manually edit profiles/<name>/outputs/syllabus/episode-05-agenda.md
python3 prep.py content --profile <name> --episode 5
python3 prep.py package --profile <name>
```

**Force-regenerate everything:**
```bash
python3 prep.py all --profile <name> --force
```

**Add external material** (distill a document into an episode):
```bash
python3 prep.py add paper.md --profile <name>
# Optional: --gem-slot N to control which gem file it appends to
```
The `add` command runs distill → content → append-to-gem (not a full repackage). Input must be UTF-8 text (not binary PDF). The result appears as `misc-<name>-content.md` in episodes and notebooklm directories, and is appended to the specified gem slot (default: last). Run `package` afterward if you want a clean full repackage.

**Change episode counts:** Edit `core_episodes` / `frontier_episodes` in `profile.md` and re-run syllabus + content.

**Switch models mid-run:** Change `model` in `profile.md`. Use `gpt-4o-mini` for cheap validation, then `gpt-5.2-pro` for final content. Re-run with `--force` for episodes you want regenerated.

---

## Prompt Map

Which prompts are consumed by the pipeline vs used manually:

| Prompt | Used by | Type |
|--------|---------|------|
| `prompts/syllabus.md` | `prep.py syllabus` / `prep.py all` | Pipeline-consumed |
| `prompts/content.md` | `prep.py content` / `prep.py all` | Pipeline-consumed |
| `prompts/distill.md` | `prep.py add` | Pipeline-consumed |
| `prompts/setup.md` | `prep.py setup` | Pipeline-consumed |
| `prompts/intake.md` | Paste into any AI chat | Manual (free alternative to `setup`) |
| `prompts/gem.md` | `prep.py render` → paste into Gemini | Manual |
| `prompts/notebooklm.md` | Copy → paste into NotebookLM | Manual |
| `prompts/notebooklm-frames.md` | Optional per-episode podcast seeds | Manual |

---

## Directory Structure (Complete Profile)

Final state after a full pipeline run with 12 core + 3 frontier episodes:

```
profiles/<name>/
  profile.md
  adapted/
    seeds.md
    coverage.md
    lenses.md
    gem-sections.md
  inputs/
    agendas/               <- Pre-existing agendas (pipeline skips what exists here)
    episodes/              <- Pre-existing episodes (pipeline skips what exists here)
    misc/
  outputs/
    syllabus/
      scaffold.md
      episode-01-agenda.md
      ...
      episode-15-agenda.md
      final_merge.md
    episodes/
      episode-01-content.md
      ...
      episode-15-content.md
    notebooklm/
      episode-01-content.md
      ...
      episode-15-content.md
    gem/
      gem-0-scaffold.md
      gem-0-final_merge.md
      gem-1.md             <- Episodes 1–2 merged
      gem-2.md             <- Episodes 3–4 merged
      ...
      gem-7.md             <- All frontier episodes (13–15)
    raw/
      syllabus-01-scaffold.md
      syllabus-02-core_batch.md
      ...
      syllabus-08-final_merge.md
      episode-01-content-raw.md
      ...
      episode-15-content-raw.md
```

---

## Cost Summary

Estimates for a 15-episode profile (12 core + 3 frontier) with `gpt-5.2-pro`:

| Step | Cost |
|------|------|
| Install + configure | $0 |
| `init` | $0 |
| `setup` (adapted files) | ~$2 |
| `status` | $0 |
| `syllabus` | ~$5–10 |
| `content` (15 episodes) | ~$15–30 |
| `package` | $0 |
| Gem setup | $0 |
| NotebookLM setup | $0 |
| **Total** | **~$22–42** |

Tips:
- Test with `gpt-4o-mini` first (much cheaper) to validate adapted content and agenda quality
- The `smoketest` profile ships with 2 episodes + gpt-4o-mini for pennies-level validation
- The pipeline shows a cost estimate and asks for confirmation before each API run
- Use `--yes` to skip the confirmation prompt
