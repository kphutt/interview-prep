# Onboarding — Phased Backlog

Reduce friction for new users getting from clone to generated content.

---

## ~~Phase 1: Rename adapt→setup + auto-run from `all`~~

**Goal:** New users don't need to know `setup` exists. `init` → edit profile → `all` works end-to-end.

**What's in scope:**
- Rename `adapt` → `setup` everywhere (user-facing strings, functions, tests, docs)
- `all` auto-detects stubs, runs setup, reloads domain, verifies, proceeds
- Cost estimate includes +3 setup calls when stubs detected
- Extract `_DOMAIN_FILES` constant, add `_needs_setup()` helper

**What's NOT in scope:**
- Changing init template content (Phase 2)
- README restructure (Phase 3)
- Progress indicators (Phase 4)

**Done when:** `init` → edit → `all` works; "adapt" doesn't appear in user-facing output.

---

## Phase 2: Better init template

**Goal:** Users understand what to put in `profile.md` body and why it matters.

**What's in scope:**
- Rename template body section to "Job Description & Context"
- Add inline guidance: "Paste your job description here. This directly feeds setup and significantly improves domain-specific output quality."
- Update `cmd_init` output to tell users to paste the JD

**What's NOT in scope:**
- Validating JD content
- Auto-fetching JDs from URLs

**Done when:** A user running `init` gets clear guidance to paste their JD.

---

## Phase 3: README Quick Start restructure

**Goal:** The first section a user reads leads to a working result.

**What's in scope:**
- Move "Build your own profile" to the top (it's the primary use case)
- Reframe "Browse reference profile" as secondary ("Want to see what the output looks like first?")
- Fix the misleading "free, no API key" label

**What's NOT in scope:**
- New sections or expanded docs
- Tutorial-style content

**Done when:** A new user following the README top-to-bottom hits no surprises.

---

## Phase 4: Progress indicator during API calls

**Goal:** Users know the pipeline isn't hung during 30-90s API calls.

**What's in scope:**
- Simple elapsed timer in `call_llm` (e.g., "waiting... 30s")
- No progress bar, no ETA, no spinner library

**What's NOT in scope:**
- Token streaming
- Detailed per-step progress

**Done when:** Every API call shows elapsed time while waiting.

---

## Phase 5: Post-run cost summary

**Goal:** Users can compare estimate vs actual and budget for future runs.

**What's in scope:**
- Print "This run used ~N calls (~$X estimated)" at the end of pipeline runs
- Accumulate call count from `call_llm` invocations

**What's NOT in scope:**
- Actual token/cost tracking from API responses
- Persistent cost history

**Done when:** Every API command prints a summary line at completion.
