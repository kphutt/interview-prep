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
#   ./smoke_test.sh                         # live: gpt-4o-mini, effort low, 1+1 episodes
#   ./smoke_test.sh --dry-run               # static fixtures, no API calls

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# --- Detect Python ---
# macOS/Linux: python3, Windows (Git Bash): python or full path
if command -v python3 &>/dev/null && python3 --version &>/dev/null; then
    PYTHON=python3
elif command -v python &>/dev/null && python --version &>/dev/null; then
    PYTHON=python
else
    echo "ERROR: Python not found. Install Python 3.9+ and ensure it's on PATH."
    exit 1
fi

# --- Parse flags ---
DRY_RUN=0
for arg in "$@"; do
    case "$arg" in
        --dry-run) DRY_RUN=1 ;;
        *) echo "Unknown argument: $arg"; exit 1 ;;
    esac
done

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

PROFILE=smoke-test

if [ "$DRY_RUN" -eq 1 ]; then
    echo "=== SMOKE TEST (dry-run, profile: $PROFILE) ==="
else
    echo "=== SMOKE TEST (profile: $PROFILE) ==="
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
# Preflight validation requires distill.md even though `all` doesn't use it
cp "$SCRIPT_DIR/prompts/distill.md" "$WORK/prompts/"

cd "$WORK"

# Only env var not covered by profile config
export OPENAI_MAX_TOKENS=4000

# --- Setup: init + populate profile ---
echo "--- Setting up profile ---"

# 1. Create profile skeleton (tests init command)
$PYTHON prep.py init $PROFILE

# 2. Copy smoketest profile config + domain files
cp "$SCRIPT_DIR/profiles/smoketest/profile.md" profiles/$PROFILE/profile.md
cp "$SCRIPT_DIR/profiles/smoketest/domain/"* profiles/$PROFILE/domain/

# 3. Verify init worked
if [ -f profiles/$PROFILE/profile.md ]; then
    echo "  OK: init created profile"
else
    echo "  FAIL: init failed"
    exit 1
fi
echo ""

FAIL=0

if [ "$DRY_RUN" -eq 1 ]; then
    echo "--- Copying fixtures ---"
    cp "$SCRIPT_DIR/tests/fixtures/syllabus/"* profiles/$PROFILE/outputs/syllabus/
    cp "$SCRIPT_DIR/tests/fixtures/episodes/"* profiles/$PROFILE/outputs/episodes/
    echo "  Copied syllabus + episode fixtures"
    echo ""
    echo "--- Running package (no API calls) ---"
    $PYTHON prep.py package --profile $PROFILE
else
    echo "--- Running pipeline (profile: $PROFILE) ---"
    $PYTHON prep.py all --profile $PROFILE
fi

echo ""
echo "--- Status check ---"
STATUS_OUT=$($PYTHON prep.py status --profile $PROFILE 2>&1)
if echo "$STATUS_OUT" | grep -q "Domain files"; then
    echo "  OK: status shows domain files"
else
    echo "  FAIL: status missing domain files"
    FAIL=1
fi

echo ""
echo "--- Verifying outputs ---"

# Check agenda exists and is non-empty
if [ -s profiles/$PROFILE/outputs/syllabus/episode-01-agenda.md ]; then
    echo "  OK: agenda exists ($(wc -c < profiles/$PROFILE/outputs/syllabus/episode-01-agenda.md) bytes)"
else
    echo "  FAIL: agenda missing or empty"
    FAIL=1
fi

# Check content exists and is non-empty
if [ -s profiles/$PROFILE/outputs/episodes/episode-01-content.md ]; then
    echo "  OK: content exists ($(wc -c < profiles/$PROFILE/outputs/episodes/episode-01-content.md) bytes)"
else
    echo "  FAIL: content missing or empty"
    FAIL=1
fi

# Check gem file exists
if [ -s profiles/$PROFILE/outputs/gem/gem-1.md ]; then
    echo "  OK: gem-1.md exists ($(wc -c < profiles/$PROFILE/outputs/gem/gem-1.md) bytes)"
else
    echo "  FAIL: gem-1.md missing or empty"
    FAIL=1
fi

# Check notebooklm file exists
if [ -s profiles/$PROFILE/outputs/notebooklm/episode-01-content.md ]; then
    echo "  OK: notebooklm exists"
else
    echo "  FAIL: notebooklm missing or empty"
    FAIL=1
fi

# --- Domain marker verification (dry-run only) ---
if [ "$DRY_RUN" -eq 1 ]; then
    echo ""
    echo "--- Domain marker verification ---"
    for marker in "DOMAIN_SEEDS" "COVERAGE_FRAMEWORK"; do
        if grep -q "<!-- $marker -->" profiles/$PROFILE/domain/seeds.md 2>/dev/null || \
           grep -q "<!-- $marker -->" profiles/$PROFILE/domain/coverage.md 2>/dev/null; then
            echo "  OK: $marker marker found"
        else
            echo "  FAIL: $marker marker missing"
            FAIL=1
        fi
    done
    for marker in "DOMAIN_LENS" "STAKEHOLDERS"; do
        if grep -q "<!-- $marker -->" profiles/$PROFILE/domain/lenses.md 2>/dev/null; then
            echo "  OK: $marker marker found"
        else
            echo "  FAIL: $marker marker missing"
            FAIL=1
        fi
    done
fi

echo ""
echo "--- Prompts (input to API) ---"
echo ""
echo ">> Syllabus prompt (rendered with profile):"
$PYTHON prep.py render prompts/syllabus.md --profile $PROFILE
echo ""
echo ">> Content prompt (rendered with profile + domain injection):"
$PYTHON prep.py render "$SCRIPT_DIR/prompts/content.md" --profile $PROFILE

echo ""
echo "--- Generated output ---"
echo ""
echo ">> Agenda (first 20 lines):"
head -20 profiles/$PROFILE/outputs/syllabus/episode-01-agenda.md
echo ""
echo ">> Content (first 40 lines):"
head -40 profiles/$PROFILE/outputs/episodes/episode-01-content.md

echo ""
if [ "$FAIL" -eq 0 ]; then
    echo "=== SMOKE TEST PASSED ==="
else
    echo "=== SMOKE TEST FAILED ==="
    exit 1
fi
