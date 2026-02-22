#!/usr/bin/env python3
"""
prep.py - Interview Prep Content Pipeline
==========================================
Automates: Syllabus (8 runs) -> Content (per episode) -> Package (Gem + NotebookLM)

Usage:
    python prep.py init <profile-name>                    # Create new profile skeleton
    python prep.py adapt  --profile P                     # Generate domain files (3 API calls)
    python prep.py all    --profile P                     # Full pipeline
    python prep.py syllabus --profile P                   # Generate agendas only
    python prep.py content --profile P [--episode N]      # Generate content
    python prep.py add <file> --profile P [--gem-slot N]  # Distill doc -> content -> package
    python prep.py package [--profile P]                  # Repackage outputs
    python prep.py render <file> [--profile P]            # Substitute env vars, print to stdout
    python prep.py status  [--profile P]                  # Show what exists

Setup:
    pip install -r requirements.txt
    cp .env.example .env   # edit .env with your API key
    set -a && source .env && set +a
    python prep.py adapt --profile <name>
"""

import argparse
import math
import os
import re
import string
import sys
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------
BASE_DIR   = Path(__file__).parent
PROMPTS    = BASE_DIR / "prompts"
INPUTS     = BASE_DIR / "inputs"
OUTPUTS    = BASE_DIR / "outputs"

SYLLABUS_DIR   = OUTPUTS / "syllabus"
EPISODES_DIR   = OUTPUTS / "episodes"
GEM_DIR        = OUTPUTS / "gem"
NLM_DIR        = OUTPUTS / "notebooklm"
RAW_DIR        = OUTPUTS / "raw"

IN_AGENDAS     = INPUTS / "agendas"
IN_EPISODES    = INPUTS / "episodes"
IN_MISC        = INPUTS / "misc"

MODEL  = os.environ.get("OPENAI_MODEL", "gpt-5.2-pro")
AS_OF  = os.environ.get("AS_OF_DATE", "Feb 2026")

# Role config — set in .env to customize for your target role
# NOTE: these must be defined before SYLLABUS_INSTRUCTIONS etc. (which use them)
ROLE     = os.environ.get("PREP_ROLE", "Staff Engineer")
COMPANY  = os.environ.get("PREP_COMPANY", "a top tech company")
DOMAIN   = os.environ.get("PREP_DOMAIN", "Security & Infrastructure")
AUDIENCE = os.environ.get("PREP_AUDIENCE", "Senior Software Engineers")

_CORE_COUNT     = int(os.environ.get("PREP_CORE_EPISODES", "12"))
_FRONTIER_COUNT = int(os.environ.get("PREP_FRONTIER_EPISODES", "3"))

CORE_EPS     = list(range(1, _CORE_COUNT + 1))
FRONTIER_EPS = list(range(_CORE_COUNT + 1, _CORE_COUNT + _FRONTIER_COUNT + 1))
ALL_EPS      = CORE_EPS + FRONTIER_EPS

def frontier_map(core_count=None, frontier_count=None):
    """Map frontier letters to episode numbers. e.g. {"A": 13, "B": 14, "C": 15}."""
    if core_count is None: core_count = _CORE_COUNT
    if frontier_count is None: frontier_count = _FRONTIER_COUNT
    return {chr(65 + i): core_count + i + 1 for i in range(frontier_count)}

def gem_slot(ep, core_count=None, frontier_eps=None):
    """Return the gem file slot number for an episode."""
    if core_count is None: core_count = _CORE_COUNT
    if frontier_eps is None: frontier_eps = FRONTIER_EPS
    core_slots = math.ceil(core_count / 2)
    if 1 <= ep <= core_count:
        return (ep - 1) // 2 + 1
    if ep in frontier_eps:
        return core_slots + 1
    return core_slots + (2 if frontier_eps else 1)

def _total_gem_slots(core_count=None, frontier_count=None):
    """Total number of gem slots: ceil(core/2) + (1 if frontiers) + 1 misc."""
    if core_count is None: core_count = _CORE_COUNT
    if frontier_count is None: frontier_count = _FRONTIER_COUNT
    return math.ceil(core_count / 2) + (1 if frontier_count > 0 else 0) + 1

def build_syllabus_runs(core_count, frontier_count, batch_size=4):
    """Build the SYLLABUS_RUNS list dynamically from episode counts."""
    runs = [dict(mode="SCAFFOLD", core="", frontier="")]
    num_batches = math.ceil(core_count / batch_size) if core_count > 0 else 0
    letters = list(string.ascii_uppercase[:frontier_count])
    for b in range(num_batches):
        s = b * batch_size + 1
        e = min((b + 1) * batch_size, core_count)
        core_str = str(s) if s == e else f"{s}-{e}"
        runs.append(dict(mode="CORE_BATCH", core=core_str, frontier=""))
        if b < len(letters):
            runs.append(dict(mode="FRONTIER_DIGEST", core="", frontier=letters[b]))
    for extra in letters[num_batches:]:
        runs.append(dict(mode="FRONTIER_DIGEST", core="", frontier=extra))
    runs.append(dict(mode="FINAL_MERGE", core="", frontier=""))
    return runs

SYLLABUS_RUNS = build_syllabus_runs(_CORE_COUNT, _FRONTIER_COUNT)

def _reconfigure(core_count=12, frontier_count=3):
    """Regenerate all derived state from counts. Used by tests and profile loading."""
    global _CORE_COUNT, _FRONTIER_COUNT, CORE_EPS, FRONTIER_EPS, ALL_EPS, SYLLABUS_RUNS
    _CORE_COUNT = core_count
    _FRONTIER_COUNT = frontier_count
    CORE_EPS = list(range(1, core_count + 1))
    FRONTIER_EPS = list(range(core_count + 1, core_count + frontier_count + 1))
    ALL_EPS = CORE_EPS + FRONTIER_EPS
    SYLLABUS_RUNS = build_syllabus_runs(core_count, frontier_count)

def _frontier_range_str():
    """e.g. '13-15'"""
    if not FRONTIER_EPS:
        return "(none)"
    return f"{FRONTIER_EPS[0]}-{FRONTIER_EPS[-1]}" if len(FRONTIER_EPS) > 1 else str(FRONTIER_EPS[0])

def _frontier_map_str():
    """e.g. '  - Digest A = Episode 13 (covers core Episodes 1-4)\n  ...'"""
    fm = frontier_map()
    lines = []
    batch_size = 4
    for letter, ep_num in sorted(fm.items(), key=lambda x: x[1]):
        idx = ord(letter) - ord('A')
        start = idx * batch_size + 1
        end = min((idx + 1) * batch_size, _CORE_COUNT)
        lines.append(f"  - Digest {letter} = Episode {ep_num} (covers core Episodes {start}-{end})")
    return "\n".join(lines) if lines else "  (no frontier digests)"

def _listening_order_str():
    """e.g. 'Episodes 1-4 -> Episode 13 (Frontier Digest A) -> Episodes 5-8 -> ...'"""
    fm = frontier_map()
    parts = []
    batch_size = 4
    for i in range(0, _CORE_COUNT, batch_size):
        start = i + 1
        end = min(i + batch_size, _CORE_COUNT)
        parts.append(f"Episodes {start}-{end}")
        letter = chr(ord('A') + i // batch_size)
        if letter in fm:
            ep = fm[letter]
            parts.append(f"Episode {ep} (Frontier Digest {letter})")
    return " -> ".join(parts)

# ---------------------------------------------------------------------------
# DOMAIN CONTENT (domain-specific prompt injection)
# ---------------------------------------------------------------------------
_DOMAIN = {}  # marker -> content, populated by set_profile()

# Stub comment prefix — files starting with this are considered empty stubs
_STUB_PREFIX = "<!-- STUB:"

def _parse_domain_sections(text):
    """Parse <!-- MARKER --> delimited sections from domain file content."""
    result = {}
    current_marker = None
    current_lines = []
    for line in text.split("\n"):
        stripped = line.strip()
        if re.match(r"^<!--\s+(\w+)\s+-->$", stripped):
            if current_marker:
                result[current_marker] = "\n".join(current_lines).strip()
            current_marker = re.match(r"^<!--\s+(\w+)\s+-->$", stripped).group(1)
            current_lines = []
        elif current_marker is not None:
            current_lines.append(line)
    if current_marker:
        result[current_marker] = "\n".join(current_lines).strip()
    return result


def _load_domain(profile_name):
    """Load domain files from profiles/{name}/domain/. Returns dict of marker->content."""
    domain_dir = BASE_DIR / "profiles" / profile_name / "domain"
    result = {}
    if not domain_dir.is_dir():
        return result
    for f in sorted(domain_dir.iterdir()):
        if f.suffix == ".md":
            text = f.read_text(encoding="utf-8")
            sections = _parse_domain_sections(text)
            if not sections:
                print(f"  WARNING: {f.name} has no <!-- MARKER --> sections")
            result.update(sections)
    return result


def _inject_domain(text, domain=None):
    """Replace {MARKER} placeholders with domain content."""
    if domain is None:
        domain = _DOMAIN
    for marker, content in domain.items():
        text = text.replace("{" + marker + "}", content)
    return text


def _is_stub(filepath):
    """Check if a domain file is a stub (starts with STUB comment)."""
    if not filepath.exists():
        return True
    text = filepath.read_text(encoding="utf-8").strip()
    return not text or text.startswith(_STUB_PREFIX)


def _preflight_check(profile_name, command, force=False):
    """Validate profile completeness before API calls. Errors early to avoid wasted spend."""
    profile_dir = BASE_DIR / "profiles" / profile_name
    domain_dir = profile_dir / "domain"

    # adapt creates domain files, doesn't need them
    if command == "adapt":
        return

    # 1. Domain files exist and are non-stub
    domain_files = ["seeds.md", "coverage.md", "lenses.md", "gem-sections.md"]
    for name in domain_files:
        f = domain_dir / name
        if _is_stub(f):
            print(f"ERROR: domain/{name} is empty or missing.")
            print(f"  Run 'python prep.py adapt --profile {profile_name}' or see prompts/intake.md")
            sys.exit(1)

    # 2. Prompt files exist
    for prompt_name in ["syllabus", "content", "distill"]:
        p = PROMPTS / f"{prompt_name}.md"
        if not p.exists():
            print(f"ERROR: {p} not found")
            sys.exit(1)


# ---------------------------------------------------------------------------
# PROFILES
# ---------------------------------------------------------------------------
_PROFILE_KNOWN_FIELDS = {
    "role", "company", "domain", "audience",
    "core_episodes", "frontier_episodes",
    "model", "effort", "as_of",
}
_PROFILE_REQUIRED_FIELDS = {"role", "company", "domain"}
_PROFILE_INT_FIELDS = {"core_episodes", "frontier_episodes"}

def load_profile(name):
    """Parse profiles/{name}/profile.md YAML frontmatter. Returns config dict."""
    profile_dir = BASE_DIR / "profiles" / name
    if not profile_dir.is_dir():
        print(f"ERROR: profile '{name}' not found at {profile_dir}/")
        sys.exit(1)
    profile_path = profile_dir / "profile.md"
    if not profile_path.exists():
        print(f"ERROR: {profile_path} not found. Run 'python prep.py init {name}' first.")
        sys.exit(1)

    text = profile_path.read_text(encoding="utf-8")
    lines = text.split("\n")

    # Find frontmatter delimiters
    delimiters = [i for i, line in enumerate(lines) if line.strip() == "---"]
    if len(delimiters) < 2:
        print(f"ERROR: {profile_path} has no YAML frontmatter (expected --- delimiters)")
        sys.exit(1)

    config = {}
    for line in lines[delimiters[0] + 1 : delimiters[1]]:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if ":" not in stripped:
            continue
        key, _, value = stripped.partition(":")
        key = key.strip().lower()
        value = value.strip().strip('"').strip("'")
        if not value:
            if key in _PROFILE_REQUIRED_FIELDS:
                print(f"ERROR: {profile_path.name} field '{key}' is blank — add a value.")
                sys.exit(1)
            continue

        if key not in _PROFILE_KNOWN_FIELDS:
            print(f"WARNING: unknown field '{key}' in {profile_path.name}")
        config[key] = value

    # Validate required fields
    for field in _PROFILE_REQUIRED_FIELDS:
        if field not in config:
            print(f"ERROR: {profile_path.name} missing required field '{field}'.")
            sys.exit(1)

    # Validate integer fields
    _NONNEG_INT_FIELDS = {"frontier_episodes"}  # 0 is valid
    for field in _PROFILE_INT_FIELDS:
        if field in config:
            try:
                val = int(config[field])
                min_val = 0 if field in _NONNEG_INT_FIELDS else 1
                if val < min_val:
                    raise ValueError()
                config[field] = val
            except (ValueError, TypeError):
                label = "non-negative" if field in _NONNEG_INT_FIELDS else "positive"
                print(f"ERROR: {field} must be a {label} integer, got '{config[field]}'.")
                sys.exit(1)

    return config


def set_profile(name):
    """Load a profile and redirect all directory constants + config vars."""
    global OUTPUTS, SYLLABUS_DIR, EPISODES_DIR, GEM_DIR, NLM_DIR, RAW_DIR
    global IN_AGENDAS, IN_EPISODES, IN_MISC
    global ROLE, COMPANY, DOMAIN, AUDIENCE, MODEL, EFFORT, AS_OF
    global _DOMAIN

    config = load_profile(name)

    # Load domain content for prompt injection
    _DOMAIN = _load_domain(name)

    # Redirect directories to profile paths (PROMPTS stays shared)
    profile_dir = BASE_DIR / "profiles" / name
    OUTPUTS      = profile_dir / "outputs"
    SYLLABUS_DIR = OUTPUTS / "syllabus"
    EPISODES_DIR = OUTPUTS / "episodes"
    GEM_DIR      = OUTPUTS / "gem"
    NLM_DIR      = OUTPUTS / "notebooklm"
    RAW_DIR      = OUTPUTS / "raw"
    IN_AGENDAS   = profile_dir / "inputs" / "agendas"
    IN_EPISODES  = profile_dir / "inputs" / "episodes"
    IN_MISC      = profile_dir / "inputs" / "misc"

    # Update config vars from profile (fallback to current values)
    ROLE     = config.get("role", ROLE)
    COMPANY  = config.get("company", COMPANY)
    DOMAIN   = config.get("domain", DOMAIN)
    AUDIENCE = config.get("audience", AUDIENCE)
    MODEL    = config.get("model", MODEL)
    EFFORT   = config.get("effort", EFFORT)
    AS_OF    = config.get("as_of", AS_OF)

    # Reconfigure episode counts if profile overrides them
    core = config.get("core_episodes")
    frontier = config.get("frontier_episodes")
    if core is not None or frontier is not None:
        _reconfigure(
            core if core is not None else _CORE_COUNT,
            frontier if frontier is not None else _FRONTIER_COUNT,
        )

    return config

# ---------------------------------------------------------------------------
# OPENAI CLIENT
# ---------------------------------------------------------------------------
EFFORT = os.environ.get("OPENAI_EFFORT", "xhigh")  # xhigh | high | medium | low
VERBOSITY = os.environ.get("OPENAI_VERBOSITY", "")   # "" = auto-detect from model
MAX_OUTPUT = int(os.environ.get("OPENAI_MAX_TOKENS", "16000"))

# Model family capabilities: (supports_reasoning, default_verbosity, allowed_efforts)
_MODEL_CAPS = {
    "gpt-5.2-pro": (True,  "high",   {"medium", "high", "xhigh"}),
    "gpt-5.2":     (True,  "high",   {"none", "low", "medium", "high", "xhigh"}),
    "o3":          (True,  "medium", {"low", "medium", "high"}),
    "o4-mini":     (True,  "medium", {"low", "medium", "high"}),
    "o4":          (True,  "medium", {"low", "medium", "high"}),
    "gpt-4.1":     (False, None,     None),
    "gpt-4o-mini": (False, None,     None),
    "gpt-4o":      (False, None,     None),
}

_EFFORT_SCALE = ["none", "low", "medium", "high", "xhigh"]

def _clamp_effort(effort, allowed):
    """Clamp effort to nearest valid level. Returns (value, was_clamped)."""
    if allowed is None or effort in allowed:
        return effort, False
    idx = _EFFORT_SCALE.index(effort) if effort in _EFFORT_SCALE else 2
    # Search outward: up first (higher effort is safer than lower)
    for dist in range(1, len(_EFFORT_SCALE)):
        for candidate_idx in [idx + dist, idx - dist]:
            if 0 <= candidate_idx < len(_EFFORT_SCALE):
                candidate = _EFFORT_SCALE[candidate_idx]
                if candidate in allowed:
                    return candidate, True
    return effort, False  # shouldn't happen

def _model_capabilities(model):
    """Build optional kwargs for responses.create() based on model name."""
    # Match longest prefix
    supports_reasoning, default_verbosity, allowed_efforts = True, None, None
    best_len = 0
    for prefix, caps in _MODEL_CAPS.items():
        if model.startswith(prefix) and len(prefix) > best_len:
            supports_reasoning, default_verbosity, allowed_efforts = caps
            best_len = len(prefix)

    kwargs = {}
    if supports_reasoning:
        effort, clamped = _clamp_effort(EFFORT, allowed_efforts)
        if clamped:
            print(f"  WARNING: effort '{EFFORT}' not supported by {model}, using '{effort}'")
        kwargs["reasoning"] = {"effort": effort}

    verbosity = VERBOSITY or default_verbosity
    if verbosity and verbosity != "none":
        kwargs["text"] = {"verbosity": verbosity}

    return kwargs
POLL_TIMEOUT = int(os.environ.get("POLL_TIMEOUT", "1800"))  # 30 min default

def get_client():
    try:
        from openai import OpenAI
    except ImportError:
        print("ERROR: openai not installed. Run: pip install openai")
        sys.exit(1)
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        print("ERROR: OPENAI_API_KEY not set.")
        print("  Set in .env or: export OPENAI_API_KEY='sk-...'")
        sys.exit(1)
    return OpenAI(api_key=key)

def call_llm(client, instructions, user_input, label="", retries=3):
    """Call OpenAI Responses API with background mode + polling."""
    model_kwargs = _model_capabilities(MODEL)
    attempt = 0
    stripped = False
    while attempt < retries:
        try:
            if label: print(f"  -> {MODEL} (effort={EFFORT}): {label}...")

            # Create background response
            resp = client.responses.create(
                model=MODEL,
                background=True,
                store=True,
                **model_kwargs,
                max_output_tokens=MAX_OUTPUT,
                instructions=instructions,
                input=user_input,
            )

            # Poll until complete
            poll_count = 0
            poll_start = time.time()
            while resp.status in ("queued", "in_progress"):
                elapsed = time.time() - poll_start
                if elapsed > POLL_TIMEOUT:
                    raise Exception(f"Polling timeout after {int(elapsed)}s (limit={POLL_TIMEOUT}s)")
                time.sleep(3)
                resp = client.responses.retrieve(resp.id)
                poll_count += 1
                if poll_count % 10 == 0:
                    print(f"     still running... ({poll_count * 3}s)")

            if resp.status == "failed":
                print(f"     API returned status=failed")
                if hasattr(resp, 'error') and resp.error:
                    print(f"     error: {resp.error}")
                raise Exception(f"Response failed: {resp.status}")

            text = resp.output_text
            if not text:
                raise Exception("Empty output_text returned")

            # Log usage if available
            if hasattr(resp, 'usage') and resp.usage:
                u = resp.usage
                inp = getattr(u, 'input_tokens', '?')
                out = getattr(u, 'output_tokens', '?')
                print(f"     tokens: {inp} in / {out} out")

            return text

        except Exception as e:
            # One-shot: strip reasoning/text kwargs on BadRequestError
            from openai import BadRequestError
            if isinstance(e, BadRequestError) and not stripped:
                model_kwargs.pop("reasoning", None)
                model_kwargs.pop("text", None)
                stripped = True
                print(f"  WARNING: bad request, retrying without reasoning/text params")
                continue  # don't consume an attempt

            wait = 2 ** (attempt + 1)
            print(f"     ERROR ({attempt+1}/{retries}): {e}")
            if attempt < retries - 1:
                print(f"     retry in {wait}s...")
                time.sleep(wait)
            attempt += 1
    print(f"     FAILED after {retries} attempts")
    return None

# ---------------------------------------------------------------------------
# PROMPTS
# ---------------------------------------------------------------------------
def load_prompt(name):
    p = PROMPTS / f"{name}.md"
    if not p.exists():
        print(f"ERROR: {p} not found")
        sys.exit(1)
    return p.read_text(encoding="utf-8")

def syllabus_prompt(run):
    t = load_prompt("syllabus")
    # Run-specific vars
    t = t.replace("{MODE}", run["mode"])
    t = t.replace("{CORE_EPISODES}", run["core"])
    t = t.replace("{FRONTIER_DIGEST}", run["frontier"])
    t = t.replace("{AS_OF_OVERRIDE}", AS_OF)
    # Role vars
    t = t.replace("{ROLE}", ROLE)
    t = t.replace("{COMPANY}", COMPANY)
    t = t.replace("{DOMAIN}", DOMAIN)
    t = t.replace("{AUDIENCE}", AUDIENCE)
    # Count vars
    t = t.replace("{TOTAL_CORE}", str(_CORE_COUNT))
    t = t.replace("{CORE_RANGE}", f"1-{_CORE_COUNT}")
    t = t.replace("{FRONTIER_RANGE}", _frontier_range_str())
    t = t.replace("{FRONTIER_MAP}", _frontier_map_str())
    t = t.replace("{LISTENING_ORDER}", _listening_order_str())
    # Domain content injection
    t = _inject_domain(t)
    return t

def content_prompt(agenda, notes=""):
    t = load_prompt("content")
    # Use replace() instead of format() because agenda text may contain {braces}
    # Replace role vars BEFORE agenda injection to avoid replacing literals in user content
    t = t.replace("{ROLE}", ROLE)
    t = t.replace("{COMPANY}", COMPANY)
    t = t.replace("{AS_OF_DATE}", AS_OF)
    # Domain content (after role vars, before user content)
    t = _inject_domain(t)
    t = t.replace("{EXTRA_NOTES}", notes or "- No additional notes.")
    t = t.replace("{EPISODE_AGENDA}", agenda)
    return t

def distill_prompt(raw):
    t = load_prompt("distill")
    # Use replace() because raw doc may contain {braces}
    # Replace role vars BEFORE raw doc injection to avoid replacing literals in user content
    t = t.replace("{ROLE}", ROLE)
    t = t.replace("{COMPANY}", COMPANY)
    t = t.replace("{DOMAIN}", DOMAIN)
    # Domain content (after role vars, before user content)
    t = _inject_domain(t)
    t = t.replace("{RAW_DOCUMENT}", raw)
    return t

def render_template(text):
    """Replace all {PREP_*} and {AS_OF_DATE} placeholders with env var values."""
    t = text
    t = t.replace("{PREP_ROLE}", ROLE)
    t = t.replace("{PREP_COMPANY}", COMPANY)
    t = t.replace("{PREP_DOMAIN}", DOMAIN)
    t = t.replace("{PREP_AUDIENCE}", AUDIENCE)
    t = t.replace("{AS_OF_DATE}", AS_OF)
    # Domain content (for gem.md etc.)
    t = _inject_domain(t)
    return t

def _syllabus_instructions():
    """System instructions for syllabus generation (dynamic for profile support)."""
    return f"You are a {ROLE} at {COMPANY} acting as an expert interview coach. Follow the prompt instructions exactly. Output ONLY what the MODE asks for."

def _content_instructions():
    """System instructions for content generation (dynamic for profile support)."""
    return f"You are a {ROLE} at {COMPANY} acting as an expert interview coach. Generate a dense, Staff-level technical content document. Output ONLY the content document."

def _distill_instructions():
    """System instructions for document distillation (dynamic for profile support)."""
    return f"You are a {ROLE} at {COMPANY} acting as an expert interview coach. Distill the provided document into an interview prep episode agenda. Output ONLY the agenda."

# ---------------------------------------------------------------------------
# PARSING
# ---------------------------------------------------------------------------
def parse_agendas(text):
    """Parse episode agendas from syllabus output. Returns {ep_num: text}."""
    result = {}
    # Match Episode N or Frontier Digest A/B/C at start of line,
    # with optional prefixes: ##, **, numbering like "1) ", combinations thereof
    pat = re.compile(
        r'^[\s*#\d\)\.]*(?:Episode\s+(\d+))|'
        r'^[\s*#\d\)\.]*(?:Frontier\s+Digest\s+([A-Z]))',
        re.MULTILINE | re.IGNORECASE
    )
    matches = list(pat.finditer(text))
    for i, m in enumerate(matches):
        if m.group(1):   ep = int(m.group(1))
        elif m.group(2):
            fmap = frontier_map()
            letter = m.group(2).upper()
            if letter not in fmap: continue
            ep = fmap[letter]
        else: continue
        start = m.start()
        end = matches[i+1].start() if i+1 < len(matches) else len(text)
        result[ep] = text[start:end].strip()
    return result

# ---------------------------------------------------------------------------
# FILE HELPERS
# ---------------------------------------------------------------------------
def ensure_dirs():
    for d in [SYLLABUS_DIR, EPISODES_DIR, GEM_DIR, NLM_DIR, RAW_DIR,
              IN_AGENDAS, IN_EPISODES, IN_MISC]:
        d.mkdir(parents=True, exist_ok=True)

def ep_file(ep, kind):
    return f"episode-{ep:02d}-{kind}.md"

def find_agenda(ep):
    for d in [IN_AGENDAS, SYLLABUS_DIR]:
        p = d / ep_file(ep, "agenda")
        if p.exists(): return p
    return None

def find_content(ep):
    for d in [IN_EPISODES, EPISODES_DIR]:
        p = d / ep_file(ep, "content")
        if p.exists(): return p
    return None

def recover_agendas_from_raw():
    """If raw syllabus files exist but agenda files don't, re-parse them."""
    recovered = 0
    for raw_file in sorted(RAW_DIR.glob("syllabus-*-core_batch*.md")):
        text = raw_file.read_text(encoding="utf-8")
        if not text.strip():
            continue
        parsed = parse_agendas(text)
        for ep, txt in parsed.items():
            p = SYLLABUS_DIR / ep_file(ep, "agenda")
            if not p.exists() and not (IN_AGENDAS / ep_file(ep, "agenda")).exists():
                p.write_text(txt, encoding="utf-8")
                print(f"  recovered {p.name} from {raw_file.name}")
                recovered += 1

    for raw_file in sorted(RAW_DIR.glob("syllabus-*-frontier_digest*.md")):
        text = raw_file.read_text(encoding="utf-8")
        if not text.strip():
            continue
        parsed = parse_agendas(text)
        for ep, txt in parsed.items():
            p = SYLLABUS_DIR / ep_file(ep, "agenda")
            if not p.exists() and not (IN_AGENDAS / ep_file(ep, "agenda")).exists():
                p.write_text(txt, encoding="utf-8")
                print(f"  recovered {p.name} from {raw_file.name}")
                recovered += 1

    if recovered:
        print(f"  recovered {recovered} agendas from raw files\n")
    return recovered


# ---------------------------------------------------------------------------
# COMMANDS
# ---------------------------------------------------------------------------
def cmd_syllabus(client, force=False):
    print(f"\n=== SYLLABUS ({len(SYLLABUS_RUNS)} runs) ===\n")
    if force: print("  (--force: regenerating all)\n")
    recover_agendas_from_raw()
    prior_outputs = []  # accumulate prior run outputs as context

    for i, run in enumerate(SYLLABUS_RUNS):
        num = i + 1
        mode = run["mode"]
        tag = f"Run {num}/{len(SYLLABUS_RUNS)}: {mode}"
        if run["core"]:    tag += f" ({run['core']})"
        if run["frontier"]: tag += f" (Digest {run['frontier']})"

        # Skip if agendas exist (unless --force)
        if not force and mode == "SCAFFOLD":
            p = SYLLABUS_DIR / "scaffold.md"
            if p.exists():
                print(f"  skip {tag} - scaffold exists")
                prior_outputs.append(p.read_text(encoding="utf-8"))
                continue

        if not force and mode == "FINAL_MERGE":
            p = SYLLABUS_DIR / "final_merge.md"
            if p.exists():
                print(f"  skip {tag} - final_merge exists")
                prior_outputs.append(p.read_text(encoding="utf-8"))
                continue

        if not force and mode == "CORE_BATCH":
            parts = run["core"].split("-")
            s, e = int(parts[0]), int(parts[-1])
            if all(find_agenda(n) for n in range(s, e+1)):
                print(f"  skip {tag} - agendas exist")
                for n in range(s, e+1):
                    prior_outputs.append(find_agenda(n).read_text(encoding="utf-8"))
                continue

        if not force and mode == "FRONTIER_DIGEST":
            ep = frontier_map()[run["frontier"]]
            if find_agenda(ep):
                print(f"  skip {tag} - agenda exists")
                prior_outputs.append(find_agenda(ep).read_text(encoding="utf-8"))
                continue

        # Build prompt with prior context embedded in input
        prompt = syllabus_prompt(run)
        if prior_outputs:
            context = "\n\n---\nPRIOR SYLLABUS OUTPUTS (for context continuity):\n---\n\n"
            context += "\n\n---\n\n".join(prior_outputs)
            user_input = context + "\n\n---\nCURRENT RUN:\n---\n\n" + prompt
        else:
            user_input = prompt

        resp = call_llm(client, _syllabus_instructions(), user_input, label=tag)
        if not resp:
            print(f"  FAIL {tag}"); return False

        (RAW_DIR / f"syllabus-{num:02d}-{mode.lower()}.md").write_text(resp, encoding="utf-8")
        prior_outputs.append(resp)

        if mode in ("CORE_BATCH", "FRONTIER_DIGEST"):
            parsed = parse_agendas(resp)
            if not parsed:
                print(f"    WARNING: parse_agendas found 0 episodes in {tag} output!")
                print(f"    Raw output saved to {RAW_DIR / f'syllabus-{num:02d}-{mode.lower()}.md'}")
                print(f"    Check format: expected '## Episode N:' or '## Frontier Digest A/B/C:'")
            for ep, txt in parsed.items():
                p = SYLLABUS_DIR / ep_file(ep, "agenda")
                p.write_text(txt, encoding="utf-8")
                print(f"    saved {p.name}")

        if mode in ("SCAFFOLD", "FINAL_MERGE"):
            p = SYLLABUS_DIR / f"{mode.lower()}.md"
            p.write_text(resp, encoding="utf-8")
            print(f"    saved {p.name}")

        print(f"  done {tag}")

    print("\n=== SYLLABUS COMPLETE ===\n")
    return True


def _print_syllabus_review(profile_name):
    """Print review checklist after standalone syllabus generation."""
    total = len(ALL_EPS)
    print(f"Review before running content generation:")
    print(f"")
    print(f"  [ ] Episode count matches expectations ({total} episodes)")
    print(f"  [ ] Topics cover JD requirements (cross-reference with adapted/coverage.md)")
    print(f"  [ ] No duplicate topics across episodes")
    print(f"  [ ] No obvious domain gaps")
    print(f"  [ ] Frontier digests cover emerging/advanced topics")
    print(f"  [ ] Mental models are distinct (not variations of the same idea)")
    print(f"")
    print(f"Satisfied? Run: python3 prep.py content --profile {profile_name}")
    print(f"To regenerate: python3 prep.py syllabus --profile {profile_name} --force")

def cmd_content(client, force=False, episode=None):
    print("\n=== CONTENT GENERATION ===\n")
    if force: print("  (--force: regenerating all)\n")
    recover_agendas_from_raw()
    gen = skip = warn = fail = 0

    eps_to_process = [episode] if episode is not None else ALL_EPS
    for ep in eps_to_process:
        c = find_content(ep)
        if not force and c:
            if len(c.read_text(encoding="utf-8").strip()) < 500:
                print(f"  warn ep {ep:02d} - content file too small ({c}), regenerating")
            else:
                print(f"  skip ep {ep:02d} - content exists")
                skip += 1; continue

        ag = find_agenda(ep)
        if not ag:
            print(f"  warn ep {ep:02d} - no agenda"); warn += 1; continue

        agenda_text = ag.read_text(encoding="utf-8").strip()
        if not agenda_text:
            print(f"  warn ep {ep:02d} - agenda file is empty ({ag})"); warn += 1; continue

        prompt = content_prompt(agenda_text)
        resp = call_llm(client, _content_instructions(), prompt, label=f"Episode {ep:02d}")
        if not resp:
            print(f"  FAIL ep {ep:02d}"); fail += 1; continue

        p = EPISODES_DIR / ep_file(ep, "content")
        p.write_text(resp, encoding="utf-8")
        (RAW_DIR / ep_file(ep, "content-raw")).write_text(resp, encoding="utf-8")
        print(f"  saved ep {ep:02d} ({len(resp):,} chars)")
        gen += 1

    print(f"\n=== CONTENT: {gen} generated, {skip} skipped, {fail} failed ===\n")
    if gen == 0 and warn > 0:
        print(f"  WARNING: {warn} episode(s) had no agenda.")
        print(f"  Run syllabus first: python3 prep.py syllabus --profile <name>\n")
    if fail > 0:
        print(f"  WARNING: {fail} episode(s) failed. Re-run to retry.\n")
    return fail == 0

def cmd_package():
    print("\n=== PACKAGING ===\n")

    content = {}
    total = _total_gem_slots()
    # Search ALL_EPS plus a buffer for extra episodes beyond the configured range
    search_range = ALL_EPS + list(range(len(ALL_EPS) + 1, len(ALL_EPS) + 15))
    for ep in search_range:
        c = find_content(ep)
        if c: content[ep] = c.read_text(encoding="utf-8")

    # Also find misc content
    misc_files = sorted(EPISODES_DIR.glob("misc-*-content.md"))

    if not content and not misc_files:
        print("  No content found."); return False

    # NotebookLM: individual files
    for ep, txt in content.items():
        (NLM_DIR / ep_file(ep, "content")).write_text(txt, encoding="utf-8")
    for f in misc_files:
        (NLM_DIR / f.name).write_text(f.read_text(encoding="utf-8"))
    print(f"  NotebookLM: {len(content) + len(misc_files)} files")

    # Gem: dynamic merged files
    buckets = {i: [] for i in range(1, total + 1)}
    for ep, txt in sorted(content.items()):
        buckets[gem_slot(ep)].append((f"EPISODE {ep}", txt))
    for f in misc_files:
        buckets[total].append((f"MISC: {f.stem}", f.read_text(encoding="utf-8")))

    for slot, items in buckets.items():
        if not items: continue
        merged = []
        for label, txt in items:
            merged.append(f"{'='*60}\n{label}\n{'='*60}\n\n{txt}")
        (GEM_DIR / f"gem-{slot}.md").write_text("\n\n".join(merged), encoding="utf-8")
        names = [lbl for lbl, _ in items]
        print(f"  gem-{slot}.md: {', '.join(names)}")

    # Copy scaffold/merge for reference
    for n in ["scaffold.md", "final_merge.md"]:
        src = SYLLABUS_DIR / n
        if src.exists(): (GEM_DIR / f"gem-0-{n}").write_text(src.read_text(encoding="utf-8"))

    print(f"\n=== PACKAGE COMPLETE ===")
    print(f"  NotebookLM -> {NLM_DIR}/")
    print(f"  Gem        -> {GEM_DIR}/\n")
    return True

def cmd_add(client, filepath, slot=None):
    slot = slot or _total_gem_slots()
    print(f"\n=== ADD: {filepath} -> gem-{slot} ===\n")
    src = Path(filepath)
    if not src.exists():
        print(f"ERROR: {filepath} not found"); return False

    try:
        raw = src.read_text(encoding="utf-8")
    except (UnicodeDecodeError, ValueError):
        print(f"ERROR: {filepath} is not valid UTF-8 text.")
        print(f"  The 'add' command requires text files (.md, .txt, .html).")
        return False

    name = re.sub(r'[^a-zA-Z0-9_-]', '_', src.stem)[:50]

    # Step 1: Distill
    print("  1. Distill -> Agenda")
    agenda = call_llm(client, _distill_instructions(), distill_prompt(raw), "Distill")
    if not agenda: return False
    (SYLLABUS_DIR / f"misc-{name}-agenda.md").write_text(agenda, encoding="utf-8")

    # Step 2: Content
    print("  2. Agenda -> Content")
    cont = call_llm(client, _content_instructions(), content_prompt(agenda), "Content")
    if not cont: return False
    (EPISODES_DIR / f"misc-{name}-content.md").write_text(cont, encoding="utf-8")
    (NLM_DIR / f"misc-{name}-content.md").write_text(cont, encoding="utf-8")

    # Step 3: Append to gem
    gem_path = GEM_DIR / f"gem-{slot}.md"
    sep = f"\n\n{'='*60}\nMISC: {src.name}\n{'='*60}\n\n"
    with open(gem_path, "a", encoding="utf-8") as f:
        f.write(sep + cont)
    print(f"  Appended to gem-{slot}.md")

    print(f"\n=== ADD COMPLETE ===\n")
    return True


# ---------------------------------------------------------------------------
# ADAPT COMMAND (generate domain files via API)
# ---------------------------------------------------------------------------
def _adapt_instructions():
    """System instructions for adapt calls (domain file generation)."""
    return f"You are a {ROLE} at {COMPANY} acting as an expert interview coach. Generate the requested domain-specific content sections exactly as specified. Output ONLY the sections with their marker comments — no preamble, no explanations."


def _gather_context_docs():
    """Read .md/.txt files from IN_MISC, return concatenated text or fallback."""
    texts = []
    if IN_MISC.is_dir():
        for f in sorted(IN_MISC.iterdir()):
            if f.suffix in (".md", ".txt"):
                texts.append(f"--- {f.name} ---\n{f.read_text(encoding='utf-8')}")
    return "\n\n".join(texts) if texts else "(No additional context documents provided.)"


def _write_domain_file(domain_dir, filename, markers, parsed):
    """Write a single domain file from parsed sections dict. Warns on missing markers."""
    found = {m: parsed[m] for m in markers if m in parsed}
    missing = [m for m in markers if m not in parsed]
    if missing:
        print(f"  WARNING: {filename} missing markers: {', '.join(missing)}")
    if not found:
        print(f"  WARNING: {filename} has no recognized markers, skipping")
        return False
    lines = []
    for marker in markers:
        if marker in found:
            lines.append(f"<!-- {marker} -->")
            lines.append(found[marker])
            lines.append("")
    (domain_dir / filename).write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
    return True


def _build_adapt_prompt(prompt_name, profile_text, **extra):
    """Load a meta-prompt and replace role/domain/profile placeholders."""
    t = load_prompt(prompt_name)
    t = t.replace("{ROLE}", ROLE)
    t = t.replace("{COMPANY}", COMPANY)
    t = t.replace("{DOMAIN}", DOMAIN)
    t = t.replace("{AUDIENCE}", AUDIENCE)
    t = t.replace("{PROFILE_CONTENT}", profile_text)
    for key, value in extra.items():
        t = t.replace("{" + key + "}", value)
    return t


def cmd_adapt(client, profile_name, force=False):
    """Generate domain files via 3 API calls."""
    print(f"\n=== ADAPT: {profile_name} (3 calls) ===\n")
    profile_dir = BASE_DIR / "profiles" / profile_name
    domain_dir = profile_dir / "domain"
    domain_dir.mkdir(parents=True, exist_ok=True)

    # Check if domain files already exist (skip unless --force)
    domain_files = ["seeds.md", "coverage.md", "lenses.md", "gem-sections.md"]
    if not force:
        existing = [f for f in domain_files if not _is_stub(domain_dir / f)]
        if existing:
            print(f"  Domain files already exist: {', '.join(existing)}")
            print(f"  Use --force to regenerate.")
            return True

    # Read profile text + context docs
    profile_text = (profile_dir / "profile.md").read_text(encoding="utf-8")
    context_docs = _gather_context_docs()

    # Call 1: meta-seeds -> seeds.md + coverage.md
    print("  1/3: Generating seeds + coverage framework...")
    prompt1 = _build_adapt_prompt("meta-seeds", profile_text,
                                   CONTEXT_DOCS=context_docs)
    resp1 = call_llm(client, _adapt_instructions(), prompt1, label="Seeds + Coverage")
    if not resp1:
        print("  FAILED: call 1 (seeds + coverage)")
        return False
    (RAW_DIR / f"adapt-1-seeds.md").write_text(resp1, encoding="utf-8")

    parsed1 = _parse_domain_sections(resp1)
    _write_domain_file(domain_dir, "seeds.md", ["DOMAIN_SEEDS"], parsed1)
    _write_domain_file(domain_dir, "coverage.md", ["COVERAGE_FRAMEWORK"], parsed1)

    # Call 2: meta-lenses -> lenses.md
    print("  2/3: Generating lenses...")
    prompt2 = _build_adapt_prompt("meta-lenses", profile_text)
    resp2 = call_llm(client, _adapt_instructions(), prompt2, label="Lenses")
    if not resp2:
        print("  FAILED: call 2 (lenses)")
        return False
    (RAW_DIR / f"adapt-2-lenses.md").write_text(resp2, encoding="utf-8")

    parsed2 = _parse_domain_sections(resp2)
    _write_domain_file(domain_dir, "lenses.md",
                       ["DOMAIN_LENS", "NITTY_GRITTY_LAYOUT", "DOMAIN_REQUIREMENTS",
                        "DISTILL_REQUIREMENTS", "STAKEHOLDERS"], parsed2)

    # Call 3: meta-gem -> gem-sections.md (includes seeds from call 1)
    print("  3/3: Generating gem sections...")
    seeds_content = parsed1.get("DOMAIN_SEEDS", "")
    prompt3 = _build_adapt_prompt("meta-gem", profile_text,
                                   SEEDS_CONTENT=seeds_content)
    resp3 = call_llm(client, _adapt_instructions(), prompt3, label="Gem Sections")
    if not resp3:
        print("  FAILED: call 3 (gem sections)")
        return False
    (RAW_DIR / f"adapt-3-gem.md").write_text(resp3, encoding="utf-8")

    parsed3 = _parse_domain_sections(resp3)
    _write_domain_file(domain_dir, "gem-sections.md",
                       ["GEM_BOOKSHELF", "GEM_EXAMPLES", "GEM_CODING",
                        "GEM_FORMAT_EXAMPLES"], parsed3)

    print(f"\n=== ADAPT COMPLETE ===")
    print(f"  Domain files written to {domain_dir}/")
    print(f"  Next: python prep.py syllabus --profile {profile_name}")
    print()
    return True


def _show_pipeline_status():
    """Show detailed pipeline status (agendas, content, gem files, etc.)."""
    recover_agendas_from_raw()
    print("Agendas:")
    for ep in ALL_EPS:
        a = find_agenda(ep)
        print(f"  ep {ep:02d}: {'Y ' + a.parent.name + '/' + a.name if a else 'X missing'}")

    print("\nContent:")
    for ep in ALL_EPS:
        c = find_content(ep)
        print(f"  ep {ep:02d}: {'Y ' + c.parent.name + '/' + c.name if c else 'X missing'}")

    print("\nGem files:")
    for i in range(1, _total_gem_slots() + 1):
        g = GEM_DIR / f"gem-{i}.md"
        if g.exists():
            chars = len(g.read_text(encoding="utf-8"))
            print(f"  gem-{i}.md: Y {chars:,} chars")
        else:
            print(f"  gem-{i}.md: X")

    print(f"\nMisc: {len(list(EPISODES_DIR.glob('misc-*')))} episodes")

    nlm = list(NLM_DIR.glob("*.md"))
    print(f"NotebookLM: {len(nlm)} files")

    key = os.environ.get("OPENAI_API_KEY", "")
    print(f"\nModel: {MODEL} (effort={EFFORT})")
    print(f"API key: {'set' if key else 'NOT SET'}")
    print(f"As-of: {AS_OF}\n")


def _profile_summary(name):
    """One-line summary for a profile: role @ company + pipeline stage."""
    try:
        config = load_profile(name)
    except SystemExit:
        return f"{name:20s} (invalid profile)"
    role = config.get("role", "?")
    company = config.get("company", "?")

    # Check pipeline stage
    profile_dir = BASE_DIR / "profiles" / name
    syllabus_dir = profile_dir / "outputs" / "syllabus"
    episodes_dir = profile_dir / "outputs" / "episodes"
    gem_dir = profile_dir / "outputs" / "gem"

    domain_dir = profile_dir / "domain"
    domain_files = ["seeds.md", "coverage.md", "lenses.md", "gem-sections.md"]
    domain_ready = domain_dir.is_dir() and all(
        not _is_stub(domain_dir / f) for f in domain_files
    )

    agendas = len(list(syllabus_dir.glob("episode-*-agenda.md"))) if syllabus_dir.exists() else 0
    content = len(list(episodes_dir.glob("episode-*-content.md"))) if episodes_dir.exists() else 0
    gems = len(list(gem_dir.glob("gem-*.md"))) if gem_dir.exists() else 0

    if gems > 0:
        stage = "packaged"
    elif content > 0:
        stage = "content generated"
    elif agendas > 0:
        stage = "syllabus generated"
    elif domain_ready:
        stage = "domain ready"
    else:
        stage = "profile created"

    return f"{name:20s} {role} @ {company:20s} {stage}"


def cmd_status(profile_name=None):
    print("\n=== STATUS ===\n")

    if profile_name:
        # Show pipeline status for specific profile
        print(f"Profile: {profile_name} ({ROLE} @ {COMPANY})\n")
        print(f"  Config:        {_CORE_COUNT} core + {_FRONTIER_COUNT} frontier episodes, model={MODEL}\n")

        # Pipeline checklist
        profile_dir = BASE_DIR / "profiles" / profile_name
        domain_dir = profile_dir / "domain"
        domain_files = ["seeds.md", "coverage.md", "lenses.md", "gem-sections.md"]
        domain_count = sum(1 for f in domain_files if not _is_stub(domain_dir / f))
        domain_total = len(domain_files)
        agenda_count = sum(1 for ep in ALL_EPS if find_agenda(ep))
        content_count = sum(1 for ep in ALL_EPS if find_content(ep))
        gem_count = len(list(GEM_DIR.glob("gem-*.md"))) if GEM_DIR.exists() else 0
        total = len(ALL_EPS)

        print("  Pipeline:")
        print(f"    [x] Profile created          {profile_dir / 'profile.md'}")
        print(f"    [{'x' if domain_count == domain_total else ' '}] Domain files             {domain_dir}/ ({domain_count}/{domain_total} files)")
        print(f"    [{'x' if agenda_count == total else ' '}] Syllabus generated       {SYLLABUS_DIR}/ ({agenda_count}/{total} agendas)")
        print(f"    [{'x' if content_count == total else ' '}] Content generated        {EPISODES_DIR}/ ({content_count}/{total} episodes)")
        print(f"    [{'x' if gem_count > 0 else ' '}] Packaged                 {GEM_DIR}/ ({gem_count} gem files)")

        # Next command
        if domain_count < domain_total:
            print(f"\n  Next: python prep.py adapt --profile {profile_name}")
        elif agenda_count < total:
            print(f"\n  Next: python prep.py syllabus --profile {profile_name}")
        elif content_count < total:
            print(f"\n  Next: python prep.py content --profile {profile_name}")
        elif gem_count == 0:
            print(f"\n  Next: python prep.py package --profile {profile_name}")
        else:
            print(f"\n  Pipeline complete!")
        print()
        return

    # Without --profile: list all profiles, then show legacy status
    profiles_dir = BASE_DIR / "profiles"
    if profiles_dir.is_dir():
        profile_names = sorted(
            d.name for d in profiles_dir.iterdir()
            if d.is_dir() and (d / "profile.md").exists()
        )
        if profile_names:
            print("Profiles:")
            for name in profile_names:
                print(f"  {_profile_summary(name)}")
            print()

    _show_pipeline_status()

# Cost per API call by model prefix (rough estimates in USD)
_COST_PER_CALL = {
    "gpt-5.2-pro": 2.00,
    "gpt-5.2": 1.50,
    "o3": 2.00,
    "o4-mini": 0.20,
    "o4": 1.00,
    "gpt-4.1": 0.50,
    "gpt-4o-mini": 0.02,
    "gpt-4o": 0.30,
}

def _estimate_cost(num_calls):
    """Return (num_calls, estimated_cost_usd) based on current MODEL."""
    cost = 0.50  # fallback
    for prefix, c in _COST_PER_CALL.items():
        if MODEL.startswith(prefix):
            cost = c
            break
    return num_calls, round(num_calls * cost, 2)

def _confirm_cost(num_calls, yes=False):
    """Print cost estimate and prompt for confirmation. Returns True to proceed."""
    calls, est = _estimate_cost(num_calls)
    print(f"  Estimated: {calls} API calls, ~${est:.0f}")
    if yes:
        return True
    try:
        answer = input("  Proceed? [Y/n] ").strip().lower()
    except EOFError:
        return True  # non-interactive (piped input)
    return answer != "n"


def write_manifest():
    """Write a manifest of all output files with sizes and gap detection."""
    lines = [f"MANIFEST — {time.strftime('%Y-%m-%d %H:%M:%S')}",
             f"Model: {MODEL} (effort={EFFORT})", ""]

    # Agendas
    lines.append("AGENDAS:")
    agenda_count = 0
    for ep in ALL_EPS:
        a = find_agenda(ep)
        if a:
            sz = a.stat().st_size
            lines.append(f"  ep {ep:02d}: {a.name} ({sz:,} bytes)")
            agenda_count += 1
        else:
            lines.append(f"  ep {ep:02d}: MISSING")
    total = len(ALL_EPS)
    lines.append(f"  Total: {agenda_count}/{total}\n")

    # Content
    lines.append("CONTENT:")
    content_count = 0
    total_bytes = 0
    for ep in ALL_EPS:
        c = find_content(ep)
        if c:
            sz = c.stat().st_size
            lines.append(f"  ep {ep:02d}: {c.name} ({sz:,} bytes)")
            content_count += 1
            total_bytes += sz
        else:
            lines.append(f"  ep {ep:02d}: MISSING")
    lines.append(f"  Total: {content_count}/{total} ({total_bytes:,} bytes)\n")

    # Gem files
    lines.append("GEM FILES:")
    for slot in range(0, _total_gem_slots() + 1):
        for g in sorted(GEM_DIR.glob(f"gem-{slot}*.md")):
            lines.append(f"  {g.name} ({g.stat().st_size:,} bytes)")
    lines.append("")

    # NotebookLM files
    nlm = sorted(NLM_DIR.glob("*.md"))
    lines.append(f"NOTEBOOKLM: {len(nlm)} files")
    for f in nlm:
        lines.append(f"  {f.name} ({f.stat().st_size:,} bytes)")
    lines.append("")

    # Gaps / warnings
    lines.append("WARNINGS:")
    warnings = 0
    if agenda_count < total:
        lines.append(f"  MISSING {total - agenda_count} agenda(s)")
        warnings += 1
    if content_count < total:
        lines.append(f"  MISSING {total - content_count} content file(s)")
        warnings += 1
    for ep in ALL_EPS:
        c = find_content(ep)
        if c and c.stat().st_size < 2000:
            lines.append(f"  ep {ep:02d} content suspiciously small ({c.stat().st_size} bytes)")
            warnings += 1
    if warnings == 0:
        lines.append(f"  None — all {total} episodes present and reasonable size")

    manifest = "\n".join(lines)
    p = OUTPUTS / "manifest.txt"
    p.write_text(manifest, encoding="utf-8")
    print(f"\n{manifest}")
    print(f"\n  Manifest saved to {p}\n")


def cmd_init(name):
    """Create a new profile skeleton with template profile.md and domain/ stubs."""
    profile_dir = BASE_DIR / "profiles" / name
    if profile_dir.exists():
        print(f"ERROR: profile '{name}' already exists at {profile_dir}/")
        sys.exit(1)

    # Create directory structure
    for subdir in ["inputs/agendas", "inputs/episodes", "inputs/misc",
                   "outputs/syllabus", "outputs/episodes", "outputs/gem",
                   "outputs/notebooklm", "outputs/raw",
                   "domain"]:
        (profile_dir / subdir).mkdir(parents=True, exist_ok=True)

    # Write template profile.md
    template = (
        "---\n"
        "role: \n"
        "company: \n"
        "domain: \n"
        "audience: \n"
        "core_episodes: 12\n"
        "frontier_episodes: 3\n"
        "model: gpt-5.2-pro\n"
        "effort: xhigh\n"
        "as_of: \n"
        "---\n"
        "\n"
        "## Notes\n"
        "Add any extra context here.\n"
    )
    (profile_dir / "profile.md").write_text(template, encoding="utf-8")

    # Write domain/ stub files with guidance comments
    _stubs = {
        "seeds.md": (
            "<!-- STUB: Episode seed data for syllabus generation -->\n"
            "<!-- Replace this file with your domain's episode seeds.\n"
            "     Use <!-- DOMAIN_SEEDS --> as the section header.\n"
            "     See profiles/security-infra/domain/seeds.md for an example.\n"
            "     Generate via: python prep.py adapt --profile {name}\n"
            "     Or manually using prompts/intake.md in any AI chat. -->\n"
        ),
        "coverage.md": (
            "<!-- STUB: Coverage framework for syllabus generation -->\n"
            "<!-- Replace this file with your domain's coverage framework.\n"
            "     Use <!-- COVERAGE_FRAMEWORK --> as the section header.\n"
            "     See profiles/security-infra/domain/coverage.md for an example.\n"
            "     Generate via: python prep.py adapt --profile {name}\n"
            "     Or manually using prompts/intake.md in any AI chat. -->\n"
        ),
        "lenses.md": (
            "<!-- STUB: Domain lenses for content and distill prompts -->\n"
            "<!-- Replace this file with your domain's lenses.\n"
            "     Required sections: <!-- DOMAIN_LENS -->, <!-- NITTY_GRITTY_LAYOUT -->,\n"
            "     <!-- DOMAIN_REQUIREMENTS -->, <!-- DISTILL_REQUIREMENTS -->, <!-- STAKEHOLDERS -->\n"
            "     See profiles/security-infra/domain/lenses.md for an example.\n"
            "     Generate via: python prep.py adapt --profile {name}\n"
            "     Or manually using prompts/intake.md in any AI chat. -->\n"
        ),
        "gem-sections.md": (
            "<!-- STUB: Domain-specific Gem coaching bot sections -->\n"
            "<!-- Replace this file with your domain's gem sections.\n"
            "     Required sections: <!-- GEM_BOOKSHELF -->, <!-- GEM_EXAMPLES -->,\n"
            "     <!-- GEM_CODING -->, <!-- GEM_FORMAT_EXAMPLES -->\n"
            "     See profiles/security-infra/domain/gem-sections.md for an example.\n"
            "     Generate via: python prep.py adapt --profile {name}\n"
            "     Or manually using prompts/intake.md in any AI chat. -->\n"
        ),
    }
    for fname, content in _stubs.items():
        (profile_dir / "domain" / fname).write_text(content, encoding="utf-8")

    print(f"Created profile '{name}' at {profile_dir}/")
    print(f"""
Next steps:
  1. Edit your profile:
       {profile_dir / 'profile.md'}
     Fill in role, company, domain, and other fields.

  2. Generate domain-specific content:
       Option A (automated): python prep.py adapt --profile {name}
       Option B (manual):    Paste prompts/intake.md into any AI chat,
                             save files into {profile_dir / 'domain'}/

  3. Check your profile:
       python prep.py status --profile {name}
""")


def cmd_all(client, force=False):
    print("\n" + "="*60)
    print("  FULL PIPELINE")
    print("="*60 + "\n")

    # Detect already-complete pipeline
    if not force:
        agendas = sum(1 for ep in ALL_EPS if find_agenda(ep))
        contents = sum(1 for ep in ALL_EPS if find_content(ep))
        total = len(ALL_EPS)
        if agendas == total and contents == total:
            print("  Pipeline already complete — all agendas and content exist.")
            print("  To regenerate, run again with --force.\n")
            return

    ok = cmd_syllabus(client, force)
    if not ok:
        print("\n  WARNING: Syllabus had failures. Content will skip missing agendas.\n")
    cmd_content(client, force)
    cmd_package()
    write_manifest()

    print("="*60)
    print(f"  DONE.")
    print(f"  NotebookLM -> {NLM_DIR}/")
    print(f"  Gem        -> {GEM_DIR}/")
    print("="*60 + "\n")

# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------
def main():
    sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(description="Interview Prep Pipeline")
    p.add_argument("command", choices=["all","syllabus","content","add","adapt","package","status","render","init"])
    p.add_argument("file", nargs="?", help="File path for 'add'/'render', or profile name for 'init'")
    p.add_argument("--profile", type=str, default=None,
                   help="Profile name (uses profiles/{name}/ for config and data)")
    p.add_argument("--gem-slot", type=int, default=None,
                   help="Gem slot for misc content (default: last slot)")
    p.add_argument("--episode", type=int, default=None,
                   help="Generate content for a single episode only")
    p.add_argument("--force", action="store_true",
                   help="Regenerate everything, even if files exist")
    p.add_argument("--yes", action="store_true",
                   help="Skip cost confirmation prompts")
    args = p.parse_args()

    # Handle init before profile loading (profile doesn't exist yet)
    if args.command == "init":
        name = args.file
        if not name:
            print("Usage: python prep.py init <profile-name>")
            sys.exit(1)
        cmd_init(name)
        return

    # API commands require --profile
    _API_COMMANDS = {"all", "syllabus", "content", "add", "adapt"}
    if args.command in _API_COMMANDS and not args.profile:
        print(f"ERROR: --profile required for '{args.command}'.")
        print(f"  Run 'python prep.py init <name>' to create a profile.")
        sys.exit(1)

    # Load profile if specified (redirects dirs + sets config)
    if args.profile:
        set_profile(args.profile)

    # Validate --gem-slot after profile loading (choices depend on episode counts)
    if args.gem_slot is None:
        args.gem_slot = _total_gem_slots()
    elif not (1 <= args.gem_slot <= _total_gem_slots()):
        p.error(f"--gem-slot must be 1-{_total_gem_slots()}")

    # Validate --episode
    if args.episode is not None and args.episode not in ALL_EPS:
        p.error(f"--episode must be one of {ALL_EPS[0]}-{ALL_EPS[-1]}")

    # Only create dirs for write commands
    if args.command in ("all", "syllabus", "content", "add", "adapt", "package"):
        ensure_dirs()

    if args.command == "status":   cmd_status(profile_name=args.profile); return
    if args.command == "package":  cmd_package(); return
    if args.command == "render":
        if not args.file:
            print("Usage: python prep.py render <prompt-file>")
            sys.exit(1)
        rp = Path(args.file)
        if not rp.exists():
            print(f"ERROR: {rp} not found")
            sys.exit(1)
        print(render_template(rp.read_text(encoding="utf-8")), end="")
        return

    # Pre-flight validation before API calls (runs before get_client / cost confirmation)
    _preflight_check(args.profile, args.command, args.force)

    client = get_client()
    force = args.force

    # Cost confirmation before API calls
    call_counts = {
        "all": len(SYLLABUS_RUNS) + len(ALL_EPS),
        "syllabus": len(SYLLABUS_RUNS),
        "content": 1 if args.episode else len(ALL_EPS),
        "add": 2,  # distill + content
        "adapt": 3,  # seeds+coverage, lenses, gem
    }
    num_calls = call_counts.get(args.command, 0)
    if num_calls and not _confirm_cost(num_calls, yes=args.yes):
        print("Cancelled.")
        return

    if args.command == "all":      cmd_all(client, force)
    elif args.command == "syllabus":
        ok = cmd_syllabus(client, force)
        if ok:
            _print_syllabus_review(args.profile)
    elif args.command == "content":  cmd_content(client, force, episode=args.episode)
    elif args.command == "adapt":    cmd_adapt(client, args.profile, force)
    elif args.command == "add":
        if not args.file:
            print("Usage: python prep.py add <file> [--gem-slot N]")
            sys.exit(1)
        cmd_add(client, args.file, args.gem_slot)

if __name__ == "__main__":
    main()
