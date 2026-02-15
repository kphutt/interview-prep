#!/usr/bin/env bash
# smoke_test.sh — Manual API smoke test (COSTS REAL MONEY ~$0.05-$1.00)
#
# This is NOT an automated test. Run it manually after significant changes
# to verify the full pipeline works end-to-end with the real OpenAI API.
#
# Prerequisites:
#   export OPENAI_API_KEY='sk-...'
#
# Usage:
#   ./smoke_test.sh                         # default: gpt-4.1-mini, medium effort
#   ./smoke_test.sh --dry-run               # static fixtures, no API calls
#   ./smoke_test.sh o4-mini medium          # reasoning model
#   ./smoke_test.sh gpt-5.2-pro medium      # production model

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# --- Parse flags ---
DRY_RUN=0
POSITIONAL=()
for arg in "$@"; do
    case "$arg" in
        --dry-run) DRY_RUN=1 ;;
        *) POSITIONAL+=("$arg") ;;
    esac
done

MODEL="${POSITIONAL[0]:-gpt-4.1-mini}"
EFFORT="${POSITIONAL[1]:-medium}"

# --- API key check (skip for dry-run) ---
if [ "$DRY_RUN" -eq 0 ]; then
    # Source .env if key isn't already set
    if [ -z "${OPENAI_API_KEY:-}" ] && [ -f "$SCRIPT_DIR/.env" ]; then
        set -a && source "$SCRIPT_DIR/.env" && set +a
    fi

    if [ -z "${OPENAI_API_KEY:-}" ]; then
        echo "ERROR: OPENAI_API_KEY not set."
        echo "  Option 1: cp .env.example .env && edit .env"
        echo "  Option 2: export OPENAI_API_KEY='sk-...'"
        echo "  Option 3: ./smoke_test.sh --dry-run  (no API calls)"
        exit 1
    fi
fi

if [ "$DRY_RUN" -eq 1 ]; then
    echo "=== SMOKE TEST (dry-run) ==="
else
    echo "=== SMOKE TEST ==="
    echo "  Model:  $MODEL"
    echo "  Effort: $EFFORT"
fi
echo ""

# Work in a temp dir so we don't clobber real outputs
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT

# Copy project files to temp dir
cp prep.py "$WORK/"
cp requirements.txt "$WORK/"

# Use minimal test prompts instead of full prompts
if [ ! -d "$SCRIPT_DIR/tests/prompts" ]; then
    echo "ERROR: tests/prompts/ not found. Expected minimal test prompts."
    exit 1
fi
cp -r "$SCRIPT_DIR/tests/prompts" "$WORK/prompts"

cd "$WORK"

# Create minimal directory structure
mkdir -p inputs/agendas inputs/episodes inputs/misc
mkdir -p outputs/syllabus outputs/episodes outputs/gem outputs/notebooklm outputs/raw

# Run with 1 core episode, 0 frontiers for minimal cost
export OPENAI_MODEL="$MODEL"
export OPENAI_EFFORT="$EFFORT"
export OPENAI_MAX_TOKENS=4000
export PREP_CORE_EPISODES=1
export PREP_FRONTIER_EPISODES=0

if [ "$DRY_RUN" -eq 1 ]; then
    echo "--- Copying fixtures ---"
    cp "$SCRIPT_DIR/tests/fixtures/syllabus/"* outputs/syllabus/
    cp "$SCRIPT_DIR/tests/fixtures/episodes/"* outputs/episodes/
    echo "  Copied syllabus + episode fixtures"
    echo ""
    echo "--- Running package (no API calls) ---"
    python3 prep.py package
else
    echo "--- Running pipeline (1 core, 0 frontier) ---"
    python3 prep.py all
fi

echo ""
echo "--- Verifying outputs ---"

FAIL=0

# Check agenda exists and is non-empty
if [ -s outputs/syllabus/episode-01-agenda.md ]; then
    echo "  OK: agenda exists ($(wc -c < outputs/syllabus/episode-01-agenda.md) bytes)"
else
    echo "  FAIL: agenda missing or empty"
    FAIL=1
fi

# Check content exists and is non-empty
if [ -s outputs/episodes/episode-01-content.md ]; then
    echo "  OK: content exists ($(wc -c < outputs/episodes/episode-01-content.md) bytes)"
else
    echo "  FAIL: content missing or empty"
    FAIL=1
fi

# Check gem file exists
if [ -s outputs/gem/gem-1.md ]; then
    echo "  OK: gem-1.md exists ($(wc -c < outputs/gem/gem-1.md) bytes)"
else
    echo "  FAIL: gem-1.md missing or empty"
    FAIL=1
fi

# Check notebooklm file exists
if [ -s outputs/notebooklm/episode-01-content.md ]; then
    echo "  OK: notebooklm exists"
else
    echo "  FAIL: notebooklm missing or empty"
    FAIL=1
fi

echo ""
echo "--- Prompts (input to API) ---"
echo ""
echo ">> Syllabus prompt (rendered):"
python3 prep.py render prompts/syllabus.md
echo ""
echo ">> Content prompt (rendered):"
python3 prep.py render prompts/content.md

echo ""
echo "--- Generated output ---"
echo ""
echo ">> Agenda (first 20 lines):"
head -20 outputs/syllabus/episode-01-agenda.md
echo ""
echo ">> Content (first 40 lines):"
head -40 outputs/episodes/episode-01-content.md

echo ""
if [ "$FAIL" -eq 0 ]; then
    echo "=== SMOKE TEST PASSED ==="
else
    echo "=== SMOKE TEST FAILED ==="
    exit 1
fi
