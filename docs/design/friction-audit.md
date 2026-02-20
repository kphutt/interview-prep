# Friction audit — full pipeline walkthrough

Walkthrough of the complete workflow from clone to using outputs in NotebookLM/Gem. Each step tagged as automated, manual, or mixed, with friction points and severity.

## Step 1: Clone + install + env setup

**Type:** Manual

```bash
git clone <repo>
cd interview-prep
pip install -r requirements.txt
cp .env.example .env
# edit .env with API key
set -a && source .env && set +a
```

**Friction:**
- **[Medium]** Env vars not validated until the first API command runs. A typo in `OPENAI_API_KEY` silently passes through `init`, `status`, and `package` — the user only discovers it when `setup` or `syllabus` fails, potentially minutes later.
- **[Low]** `source .env` requires `set -a` / `set +a` wrapper, which is unfamiliar to many users. No instructions for fish/Windows.

## Step 2: `init` — create profile

**Type:** Automated

```bash
python3 prep.py init my-domain
```

Creates `profiles/my-domain/` with template `profile.md` and 4 adapted stub files.

**Friction:**
- **[Low]** No friction — this step works cleanly. Profile name validation catches bad names immediately.

## Step 3: Edit `profile.md`

**Type:** Manual

User fills in `role`, `company`, `domain`, and optional fields in YAML frontmatter.

**Friction:**
- **[Medium]** Profile fields not validated until `setup` or `syllabus` runs. A blank `role:` or missing `domain:` field produces a `SystemExit` at the start of the next command — clear error message, but the user has already context-switched away from the editor.
- **[Low]** No guidance on what makes a good `domain` value. Too broad ("Engineering") or too narrow ("OAuth token binding for mobile apps") both produce suboptimal syllabuses.

## Step 4: `setup` — generate adapted files

**Type:** Automated (or manual alternative via `prompts/intake.md`)

```bash
python3 prep.py setup --profile my-domain
```

Calls LLM once to generate 4 adapted files (`seeds.md`, `coverage.md`, `lenses.md`, `gem-sections.md`).

**Friction:**
- **[High]** Setup parse failures are silent. If the LLM response doesn't contain `=== FILE: ===` delimiters in the expected format, the raw response is saved to `setup-raw.md` but the user gets a generic "Could not parse response" error with no guidance on how to fix it.
- **[Medium]** Adapted file marker format is fragile. Markers must be exactly `<!-- WORD -->` (HTML comment, single word, one space padding). Extra whitespace, missing spaces, or multi-word markers silently fail to match — the content is written but never injected into prompts.
- **[Low]** The manual alternative (`prompts/intake.md` pasted into an external AI) requires a context switch to another tool. The `setup` command eliminates this but costs ~$2.

## Step 5: `syllabus` — generate agendas

**Type:** Automated

```bash
python3 prep.py syllabus --profile my-domain --yes
```

Makes N syllabus runs (scaffold + core batches + frontier digests + final merge). Default config (12+3) = 8 runs.

**Friction:**
- **[Medium]** Agenda parse failures produce warnings but no agendas. If the LLM output format doesn't match the `Episode N:` or `Frontier Digest A:` regex, the raw file is saved but no agenda files are created. The user sees "WARNING: parse_agendas found 0 episodes" but may not know what to do.
- **[Low]** Cost confirmation prompt interrupts automation. The `--yes` flag skips it, but first-time users won't know to use it.

## Step 6: Review agendas

**Type:** Manual

User reads the generated agenda files and decides whether to re-run or proceed.

**Friction:**
- **[Low]** The review checklist (printed after `syllabus`) is helpful but only appears in terminal output — easy to miss if scrolled past.
- **[Low]** No structured way to provide feedback. User must manually edit agenda files or re-run the whole syllabus.

## Step 7: `content` — generate episodes

**Type:** Automated

```bash
python3 prep.py content --profile my-domain --yes
```

One LLM call per episode (default 15). Most expensive step (~$30 at default settings).

**Friction:**
- **[Medium]** No incremental cost tracking. The cost estimate is shown upfront but actual spend per episode isn't reported. A failure at episode 12/15 leaves the user unsure how much they've spent.
- **[Low]** Partial failures return `True`. If 3 of 15 episodes fail, `cmd_content` returns success. The summary line shows "12 generated, 0 skipped" but the 3 warnings are easy to miss.

## Step 8: `package` — create gem + notebooklm files

**Type:** Automated

```bash
python3 prep.py package --profile my-domain
```

No API calls — pure file reorganization.

**Friction:**
- **[Low]** No friction. This step is fast and deterministic.

## Step 9: Set up Gem

**Type:** Manual

1. `python3 prep.py render prompts/gem.md --profile my-domain > /tmp/gem-prompt.md`
2. Create Gem in Gemini UI
3. Paste rendered prompt as system instruction
4. Upload 8 gem files (`gem-0-scaffold.md` through `gem-7.md`)

**Friction:**
- **[High]** Gem requires manual file upload of 8 files. No drag-and-drop batch upload in Gemini UI — each file must be selected individually.
- **[Medium]** The rendered prompt must be manually copied to clipboard and pasted. No direct integration.
- **[Low]** File naming (`gem-0-scaffold.md`, `gem-1.md`, ...) is logical but not documented in the render output.

## Step 10: Set up NotebookLM

**Type:** Manual

1. Create 15 individual notebooks in NotebookLM
2. For each notebook:
   - Upload the episode content file
   - Copy the episode-specific prompt from `prompts/notebooklm-frames.md`
   - Paste into the podcast prompt field
   - Generate podcast

**Friction:**
- **[High]** 15 manual notebook creations is the biggest single time sink in the workflow. Each requires: create notebook → upload file → copy prompt → paste → generate. Approximately 30-45 minutes of repetitive clicking.
- **[Medium]** Episode-specific prompts must be manually extracted from `notebooklm-frames.md`. The file contains all 15 prompts — user must find the right one for each episode.
- **[Low]** NotebookLM has no API — this step cannot be automated with current tooling.

## Summary

| Step | Type | Friction points | Highest severity |
|------|------|----------------|-----------------|
| 1. Clone + install + env | Manual | 2 | Medium |
| 2. `init` | Automated | 0 | — |
| 3. Edit `profile.md` | Manual | 2 | Medium |
| 4. `setup` | Automated | 3 | High |
| 5. `syllabus` | Automated | 2 | Medium |
| 6. Review agendas | Manual | 2 | Low |
| 7. `content` | Automated | 2 | Medium |
| 8. `package` | Automated | 0 | — |
| 9. Set up Gem | Manual | 3 | High |
| 10. Set up NotebookLM | Manual | 3 | High |

**Total: 19 friction points** (3 High, 7 Medium, 9 Low)

**Biggest wins if addressed:**
1. Validate env vars + profile fields early (`prep.py validate` command)
2. Improve setup parse error messages with format examples
3. NotebookLM batch setup documentation or helper script
