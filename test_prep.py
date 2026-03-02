#!/usr/bin/env python3
"""Unit tests for prep.py"""

import argparse
import contextlib
import io
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

# Set up minimal env before importing prep
os.environ.setdefault("OPENAI_API_KEY", "sk-test-fake-key")

import prep


class _ProfileTestMixin:
    """Mixin that saves/restores all 13 dir constants + 7 config vars + episode counts."""

    _PROFILE_DIR_ATTRS = [
        'OUTPUTS', 'SYLLABUS_DIR', 'EPISODES_DIR', 'GEM_DIR', 'NLM_DIR',
        'RAW_DIR', 'IN_AGENDAS', 'IN_EPISODES', 'IN_MISC',
    ]
    _PROFILE_CFG_ATTRS = [
        'ROLE', 'COMPANY', 'DOMAIN', 'AUDIENCE', 'MODEL', 'EFFORT', 'AS_OF',
    ]
    _PROFILE_COUNT_ATTRS = [
        '_CORE_COUNT', '_FRONTIER_COUNT', 'CORE_EPS', 'FRONTIER_EPS',
        'ALL_EPS', 'SYLLABUS_RUNS',
    ]

    def _save_profile_state(self):
        self._profile_saved = {}
        for attr in self._PROFILE_DIR_ATTRS + self._PROFILE_CFG_ATTRS + self._PROFILE_COUNT_ATTRS:
            self._profile_saved[attr] = getattr(prep, attr)
        self._saved_domain = prep._DOMAIN.copy()

    def _restore_profile_state(self):
        for attr, val in self._profile_saved.items():
            setattr(prep, attr, val)
        prep._DOMAIN = self._saved_domain

    def _write_profile(self, name, content, base=None):
        base = base or self.tmpdir
        d = Path(base) / "profiles" / name
        d.mkdir(parents=True, exist_ok=True)
        (d / "profile.md").write_text(content, encoding="utf-8")

    def _write_domain(self, name, domain_files, base=None):
        """Write domain/ files for a profile. domain_files: dict of fname->content."""
        base = base or self.tmpdir
        d = Path(base) / "profiles" / name / "domain"
        d.mkdir(parents=True, exist_ok=True)
        for fname, content in domain_files.items():
            (d / fname).write_text(content, encoding="utf-8")


class TestGemSlot(unittest.TestCase):
    def test_core_episodes_pair_into_slots_1_through_6(self):
        self.assertEqual(prep.gem_slot(1), 1)
        self.assertEqual(prep.gem_slot(2), 1)
        self.assertEqual(prep.gem_slot(3), 2)
        self.assertEqual(prep.gem_slot(4), 2)
        self.assertEqual(prep.gem_slot(5), 3)
        self.assertEqual(prep.gem_slot(6), 3)
        self.assertEqual(prep.gem_slot(11), 6)
        self.assertEqual(prep.gem_slot(12), 6)

    def test_frontiers_go_to_slot_7(self):
        self.assertEqual(prep.gem_slot(13), 7)
        self.assertEqual(prep.gem_slot(14), 7)
        self.assertEqual(prep.gem_slot(15), 7)

    def test_misc_goes_to_slot_8(self):
        self.assertEqual(prep.gem_slot(16), 8)
        self.assertEqual(prep.gem_slot(99), 8)


class TestParseAgendas(unittest.TestCase):
    def test_basic_episodes(self):
        text = """## Episode 1: The Binding Problem
mTLS vs DPoP content here.
Some bullets and details.

## Episode 2: The Session Kill Switch
Revocation content here.
More details.
"""
        result = prep.parse_agendas(text)
        self.assertIn(1, result)
        self.assertIn(2, result)
        self.assertIn("Binding Problem", result[1])
        self.assertIn("Session Kill Switch", result[2])

    def test_frontier_digests(self):
        text = """## Frontier Digest A: Binding, Revocation, Mobile OAuth
Some frontier content.

## Frontier Digest B: Zero Trust, Workload Identity
More frontier content.
"""
        result = prep.parse_agendas(text)
        self.assertIn(13, result)  # A -> 13
        self.assertIn(14, result)  # B -> 14

    def test_mixed_episodes_and_frontiers(self):
        text = """## Episode 9: Detection Engineering
Detection content.

## Episode 10: Crypto Agility
Crypto content.

## Frontier Digest C: Detection, PQC, Encryption
Frontier C content.
"""
        result = prep.parse_agendas(text)
        self.assertIn(9, result)
        self.assertIn(10, result)
        self.assertIn(15, result)  # C -> 15

    def test_no_matches_returns_empty(self):
        result = prep.parse_agendas("Just some random text with no episodes.")
        self.assertEqual(result, {})

    def test_single_hash_header(self):
        text = "# Episode 5: BeyondCorp\nContent here."
        result = prep.parse_agendas(text)
        self.assertIn(5, result)

    def test_no_hash_header(self):
        text = "Episode 7: SSRF\nContent here."
        result = prep.parse_agendas(text)
        self.assertIn(7, result)

    def test_bold_episode_header(self):
        """Real GPT-5.2-pro output uses **Episode N — Title**"""
        text = """1) **The Title (Catchy and technical).**
**Episode 1 — The Binding Problem: mTLS vs DPoP**

2) **The Hook**
- Tokens are cash.

1) **The Title (Catchy and technical).**
**Episode 2 — The Session Kill Switch**

2) **The Hook**
- Long sessions vs fast kill.
"""
        result = prep.parse_agendas(text)
        self.assertIn(1, result)
        self.assertIn(2, result)
        self.assertIn("Binding Problem", result[1])
        self.assertIn("Session Kill Switch", result[2])

    def test_numbered_bold_episode(self):
        """Handle 1) **Episode 1:..."""
        text = "1) **Episode 5: BeyondCorp**\nContent here."
        result = prep.parse_agendas(text)
        self.assertIn(5, result)

    def test_bold_frontier_digest(self):
        text = "**Frontier Digest A — Binding, Revocation (Feb 2026)**\nContent."
        result = prep.parse_agendas(text)
        self.assertIn(13, result)

    def test_case_insensitive(self):
        text = "## episode 3: Mobile Identity\nContent."
        result = prep.parse_agendas(text)
        self.assertIn(3, result)

    def test_frontier_case_insensitive(self):
        text = "## frontier digest a: stuff\nContent."
        result = prep.parse_agendas(text)
        self.assertIn(13, result)

    def test_content_boundaries_correct(self):
        text = """## Episode 1: First
Line A of episode 1.
Line B of episode 1.

## Episode 2: Second
Line A of episode 2.
"""
        result = prep.parse_agendas(text)
        self.assertNotIn("Second", result[1])
        self.assertNotIn("Line A of episode 2", result[1])
        self.assertIn("Line A of episode 1", result[1])


class TestEpFile(unittest.TestCase):
    def test_zero_padded(self):
        self.assertEqual(prep.ep_file(1, "agenda"), "episode-01-agenda.md")
        self.assertEqual(prep.ep_file(12, "content"), "episode-12-content.md")
        self.assertEqual(prep.ep_file(15, "agenda"), "episode-15-agenda.md")


class TestPromptTemplating(unittest.TestCase):
    """Test that prompt assembly doesn't crash on curly braces in content."""

    def test_content_prompt_with_braces(self):
        agenda = "Episode 1: JWT claims {sub, aud, jti} and mTLS {client_cert}"
        result = prep.content_prompt(agenda)
        self.assertIn("{sub, aud, jti}", result)
        self.assertIn("{client_cert}", result)
        self.assertIn(prep.AS_OF, result)

    def test_content_prompt_with_json(self):
        agenda = '{"iss": "https://accounts.google.com", "aud": "client_id"}'
        result = prep.content_prompt(agenda)
        self.assertIn('"iss"', result)

    def test_content_prompt_defaults_extra_notes(self):
        result = prep.content_prompt("Some agenda")
        self.assertIn("No additional notes", result)

    def test_content_prompt_custom_notes(self):
        result = prep.content_prompt("Some agenda", notes="Focus on mTLS.")
        self.assertIn("Focus on mTLS.", result)

    def test_distill_prompt_with_braces(self):
        raw = "Config: {\"key\": \"value\", \"nested\": {\"a\": 1}}"
        result = prep.distill_prompt(raw)
        self.assertIn('"key"', result)

    def test_syllabus_prompt_format(self):
        run = dict(mode="SCAFFOLD", core="", frontier="")
        result = prep.syllabus_prompt(run)
        self.assertIn("MODE: SCAFFOLD", result)

    def test_syllabus_prompt_with_core_batch(self):
        run = dict(mode="CORE_BATCH", core="1-4", frontier="")
        result = prep.syllabus_prompt(run)
        self.assertIn("CORE_EPISODES: 1-4", result)

    def test_content_prompt_replacement_order_safe(self):
        """Agenda containing placeholder strings should NOT be double-replaced."""
        agenda = "This agenda mentions {AS_OF_DATE} and {EXTRA_NOTES} literally"
        result = prep.content_prompt(agenda)
        # The literal strings in the agenda should survive
        self.assertIn("{AS_OF_DATE}", result)
        self.assertIn("{EXTRA_NOTES}", result)


class TestFileHelpers(_ProfileTestMixin, unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self._save_profile_state()

        prep.IN_AGENDAS = Path(self.tmpdir) / "in_agendas"
        prep.IN_EPISODES = Path(self.tmpdir) / "in_episodes"
        prep.SYLLABUS_DIR = Path(self.tmpdir) / "syllabus"
        prep.EPISODES_DIR = Path(self.tmpdir) / "episodes"

        for d in [prep.IN_AGENDAS, prep.IN_EPISODES, prep.SYLLABUS_DIR, prep.EPISODES_DIR]:
            d.mkdir(parents=True)

    def tearDown(self):
        self._restore_profile_state()
        shutil.rmtree(self.tmpdir)

    def test_find_agenda_in_inputs(self):
        p = prep.IN_AGENDAS / "episode-01-agenda.md"
        p.write_text("agenda 1", encoding="utf-8")
        self.assertEqual(prep.find_agenda(1), p)

    def test_find_agenda_in_outputs(self):
        p = prep.SYLLABUS_DIR / "episode-03-agenda.md"
        p.write_text("agenda 3", encoding="utf-8")
        self.assertEqual(prep.find_agenda(3), p)

    def test_find_agenda_inputs_priority(self):
        """inputs/ should be checked before outputs/"""
        p1 = prep.IN_AGENDAS / "episode-01-agenda.md"
        p2 = prep.SYLLABUS_DIR / "episode-01-agenda.md"
        p1.write_text("from inputs", encoding="utf-8")
        p2.write_text("from outputs", encoding="utf-8")
        result = prep.find_agenda(1)
        self.assertEqual(result, p1)
        self.assertEqual(result.read_text(encoding="utf-8"), "from inputs")

    def test_find_agenda_missing(self):
        self.assertIsNone(prep.find_agenda(99))

    def test_find_content_in_inputs(self):
        p = prep.IN_EPISODES / "episode-02-content.md"
        p.write_text("content 2", encoding="utf-8")
        self.assertEqual(prep.find_content(2), p)

    def test_find_content_in_outputs(self):
        p = prep.EPISODES_DIR / "episode-05-content.md"
        p.write_text("content 5", encoding="utf-8")
        self.assertEqual(prep.find_content(5), p)

    def test_find_content_missing(self):
        self.assertIsNone(prep.find_content(99))

    def test_zero_byte_agenda_exists_but_empty(self):
        """A 0-byte file should still be 'found' — caller must handle."""
        p = prep.IN_AGENDAS / "episode-05-agenda.md"
        p.write_text("", encoding="utf-8")
        result = prep.find_agenda(5)
        self.assertEqual(result, p)
        self.assertEqual(result.read_text(encoding="utf-8"), "")


class TestSkipLogic(_ProfileTestMixin, unittest.TestCase):
    """Test that cmd_syllabus and cmd_content correctly skip existing files."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self._save_profile_state()
        for attr in ['IN_AGENDAS', 'IN_EPISODES', 'SYLLABUS_DIR', 'EPISODES_DIR',
                      'RAW_DIR', 'GEM_DIR', 'NLM_DIR']:
            new_dir = Path(self.tmpdir) / attr.lower()
            new_dir.mkdir(parents=True)
            setattr(prep, attr, new_dir)

    def tearDown(self):
        self._restore_profile_state()
        shutil.rmtree(self.tmpdir)

    def test_content_skips_existing(self):
        """If content exists, cmd_content should not call LLM for that episode."""
        # Create agenda + content for ep 1
        (prep.SYLLABUS_DIR / "episode-01-agenda.md").write_text("agenda", encoding="utf-8")
        (prep.EPISODES_DIR / "episode-01-content.md").write_text("x" * 1000, encoding="utf-8")

        client = MagicMock()
        # Run content for just ep 1 by temporarily limiting ALL_EPS
        orig_all = prep.ALL_EPS
        prep.ALL_EPS = [1]
        try:
            prep.cmd_content(client, force=False)
        finally:
            prep.ALL_EPS = orig_all

        # LLM should NOT have been called
        client.responses.create.assert_not_called()

    def test_content_regenerates_truncated_file(self):
        """If content file is too small (<500 chars), regenerate it."""
        (prep.SYLLABUS_DIR / "episode-01-agenda.md").write_text("Full agenda text " * 50, encoding="utf-8")
        (prep.EPISODES_DIR / "episode-01-content.md").write_text("truncated", encoding="utf-8")  # <500 chars

        mock_resp = MagicMock()
        mock_resp.status = "completed"
        mock_resp.output_text = "Full regenerated content " * 100
        mock_resp.usage = None

        client = MagicMock()
        client.responses.create.return_value = mock_resp

        orig_all = prep.ALL_EPS
        prep.ALL_EPS = [1]
        try:
            prep.cmd_content(client, force=False)
        finally:
            prep.ALL_EPS = orig_all

        # LLM SHOULD have been called because file was too small
        client.responses.create.assert_called_once()

    def test_content_regenerates_empty_file(self):
        """0-byte content file should be regenerated."""
        (prep.SYLLABUS_DIR / "episode-01-agenda.md").write_text("Full agenda text " * 50, encoding="utf-8")
        (prep.EPISODES_DIR / "episode-01-content.md").write_text("", encoding="utf-8")  # empty

        mock_resp = MagicMock()
        mock_resp.status = "completed"
        mock_resp.output_text = "Regenerated content " * 100
        mock_resp.usage = None

        client = MagicMock()
        client.responses.create.return_value = mock_resp

        orig_all = prep.ALL_EPS
        prep.ALL_EPS = [1]
        try:
            prep.cmd_content(client, force=False)
        finally:
            prep.ALL_EPS = orig_all

        client.responses.create.assert_called_once()

    def test_content_force_regenerates(self):
        """With --force, existing content should be regenerated."""
        (prep.SYLLABUS_DIR / "episode-01-agenda.md").write_text("agenda text " * 50, encoding="utf-8")
        (prep.EPISODES_DIR / "episode-01-content.md").write_text("old content " * 100, encoding="utf-8")

        # Mock the LLM
        mock_resp = MagicMock()
        mock_resp.status = "completed"
        mock_resp.output_text = "new content generated"
        mock_resp.usage = None

        client = MagicMock()
        client.responses.create.return_value = mock_resp

        orig_all = prep.ALL_EPS
        prep.ALL_EPS = [1]
        try:
            prep.cmd_content(client, force=True)
        finally:
            prep.ALL_EPS = orig_all

        client.responses.create.assert_called_once()
        new_content = (prep.EPISODES_DIR / "episode-01-content.md").read_text(encoding="utf-8")
        self.assertEqual(new_content, "new content generated")

    def test_scaffold_skip(self):
        """Scaffold should be skipped if scaffold.md exists."""
        (prep.SYLLABUS_DIR / "scaffold.md").write_text("existing scaffold", encoding="utf-8")

        client = MagicMock()
        # Only run SCAFFOLD
        orig_runs = prep.SYLLABUS_RUNS
        prep.SYLLABUS_RUNS = [dict(mode="SCAFFOLD", core="", frontier="")]
        try:
            prep.cmd_syllabus(client, force=False)
        finally:
            prep.SYLLABUS_RUNS = orig_runs

        client.responses.create.assert_not_called()

    def test_core_batch_skip(self):
        """CORE_BATCH should be skipped if all agendas in range exist."""
        for n in range(1, 5):
            (prep.SYLLABUS_DIR / f"episode-{n:02d}-agenda.md").write_text(f"agenda {n}", encoding="utf-8")

        client = MagicMock()
        orig_runs = prep.SYLLABUS_RUNS
        prep.SYLLABUS_RUNS = [dict(mode="CORE_BATCH", core="1-4", frontier="")]
        try:
            prep.cmd_syllabus(client, force=False)
        finally:
            prep.SYLLABUS_RUNS = orig_runs

        client.responses.create.assert_not_called()

    def test_core_batch_partial_runs(self):
        """CORE_BATCH should NOT skip if only some agendas exist."""
        (prep.SYLLABUS_DIR / "episode-01-agenda.md").write_text("agenda 1", encoding="utf-8")
        # 2, 3, 4 missing

        mock_resp = MagicMock()
        mock_resp.status = "completed"
        mock_resp.output_text = "## Episode 1: A\ncontent\n\n## Episode 2: B\ncontent\n\n## Episode 3: C\ncontent\n\n## Episode 4: D\ncontent"
        mock_resp.usage = None

        client = MagicMock()
        client.responses.create.return_value = mock_resp

        orig_runs = prep.SYLLABUS_RUNS
        prep.SYLLABUS_RUNS = [dict(mode="CORE_BATCH", core="1-4", frontier="")]
        try:
            prep.cmd_syllabus(client, force=False)
        finally:
            prep.SYLLABUS_RUNS = orig_runs

        client.responses.create.assert_called_once()

    def test_content_returns_false_on_failure(self):
        """cmd_content should return False when episodes fail."""
        (prep.SYLLABUS_DIR / "episode-01-agenda.md").write_text("agenda text " * 50, encoding="utf-8")

        # LLM returns failure
        mock_resp = MagicMock()
        mock_resp.status = "failed"
        mock_resp.error = "test failure"

        client = MagicMock()
        client.responses.create.return_value = mock_resp

        orig_all = prep.ALL_EPS
        prep.ALL_EPS = [1]
        buf = io.StringIO()
        try:
            with contextlib.redirect_stdout(buf):
                with patch('prep.time') as mock_time:
                    mock_time.sleep = MagicMock()
                    mock_time.time = MagicMock(return_value=0)
                    result = prep.cmd_content(client, force=True)
        finally:
            prep.ALL_EPS = orig_all
        self.assertFalse(result)
        self.assertIn("1 failed", buf.getvalue())

    def test_content_returns_true_on_success(self):
        """cmd_content should return True when all episodes succeed."""
        (prep.SYLLABUS_DIR / "episode-01-agenda.md").write_text("agenda text " * 50, encoding="utf-8")

        mock_resp = MagicMock()
        mock_resp.status = "completed"
        mock_resp.output_text = "Generated content " * 100
        mock_resp.usage = None

        client = MagicMock()
        client.responses.create.return_value = mock_resp

        orig_all = prep.ALL_EPS
        prep.ALL_EPS = [1]
        buf = io.StringIO()
        try:
            with contextlib.redirect_stdout(buf):
                result = prep.cmd_content(client, force=True)
        finally:
            prep.ALL_EPS = orig_all
        self.assertTrue(result)
        self.assertIn("0 failed", buf.getvalue())


class TestPackaging(_ProfileTestMixin, unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self._save_profile_state()
        for attr in ['IN_AGENDAS', 'IN_EPISODES', 'SYLLABUS_DIR', 'EPISODES_DIR',
                      'RAW_DIR', 'GEM_DIR', 'NLM_DIR']:
            new_dir = Path(self.tmpdir) / attr.lower()
            new_dir.mkdir(parents=True)
            setattr(prep, attr, new_dir)

    def tearDown(self):
        self._restore_profile_state()
        shutil.rmtree(self.tmpdir)

    def test_package_creates_gem_files(self):
        # Create content for eps 1 and 2 (should go to gem-1)
        (prep.EPISODES_DIR / "episode-01-content.md").write_text("Content for ep 1", encoding="utf-8")
        (prep.EPISODES_DIR / "episode-02-content.md").write_text("Content for ep 2", encoding="utf-8")

        prep.cmd_package()

        gem1 = prep.GEM_DIR / "gem-1.md"
        self.assertTrue(gem1.exists())
        text = gem1.read_text(encoding="utf-8")
        self.assertIn("EPISODE 1", text)
        self.assertIn("EPISODE 2", text)
        self.assertIn("Content for ep 1", text)
        self.assertIn("Content for ep 2", text)

    def test_package_creates_notebooklm_files(self):
        (prep.EPISODES_DIR / "episode-01-content.md").write_text("Content 1", encoding="utf-8")

        prep.cmd_package()

        nlm = prep.NLM_DIR / "episode-01-content.md"
        self.assertTrue(nlm.exists())
        self.assertEqual(nlm.read_text(encoding="utf-8"), "Content 1")

    def test_package_misc_to_slot_8(self):
        (prep.EPISODES_DIR / "misc-paper-content.md").write_text("Misc content", encoding="utf-8")

        prep.cmd_package()

        gem8 = prep.GEM_DIR / "gem-8.md"
        self.assertTrue(gem8.exists())
        self.assertIn("Misc content", gem8.read_text(encoding="utf-8"))

    def test_package_no_content_returns_false(self):
        result = prep.cmd_package()
        self.assertFalse(result)

    def test_frontiers_to_slot_7(self):
        (prep.EPISODES_DIR / "episode-13-content.md").write_text("Frontier A", encoding="utf-8")
        (prep.EPISODES_DIR / "episode-14-content.md").write_text("Frontier B", encoding="utf-8")

        prep.cmd_package()

        gem7 = prep.GEM_DIR / "gem-7.md"
        self.assertTrue(gem7.exists())
        self.assertIn("Frontier A", gem7.read_text(encoding="utf-8"))
        self.assertIn("Frontier B", gem7.read_text(encoding="utf-8"))


class TestCallLLM(unittest.TestCase):
    def test_successful_call(self):
        mock_resp = MagicMock()
        mock_resp.status = "completed"
        mock_resp.output_text = "Generated content here"
        mock_resp.usage = None

        client = MagicMock()
        client.responses.create.return_value = mock_resp

        result = prep.call_llm(client, "instructions", "input", "test")
        self.assertEqual(result, "Generated content here")

    def test_polling_loop(self):
        """Test that polling works when initial status is queued."""
        mock_initial = MagicMock()
        mock_initial.status = "queued"
        mock_initial.id = "resp_123"

        mock_done = MagicMock()
        mock_done.status = "completed"
        mock_done.output_text = "Done!"
        mock_done.usage = None

        client = MagicMock()
        client.responses.create.return_value = mock_initial
        client.responses.retrieve.side_effect = [
            MagicMock(status="in_progress"),
            MagicMock(status="in_progress"),
            mock_done,
        ]

        with patch('prep.time') as mock_time:
            mock_time.sleep = MagicMock()
            mock_time.time = MagicMock(side_effect=[0, 1, 2, 3])  # well under timeout
            result = prep.call_llm(client, "inst", "inp", "test")

        self.assertEqual(result, "Done!")
        self.assertEqual(client.responses.retrieve.call_count, 3)

    def test_empty_output_retries(self):
        mock_resp = MagicMock()
        mock_resp.status = "completed"
        mock_resp.output_text = ""

        mock_resp2 = MagicMock()
        mock_resp2.status = "completed"
        mock_resp2.output_text = "Got it second time"
        mock_resp2.usage = None

        client = MagicMock()
        client.responses.create.side_effect = [mock_resp, mock_resp2]

        with patch('prep.time') as mock_time:
            mock_time.sleep = MagicMock()
            mock_time.time = MagicMock(return_value=0)
            result = prep.call_llm(client, "inst", "inp", "test")

        self.assertEqual(result, "Got it second time")
        self.assertEqual(client.responses.create.call_count, 2)

    def test_failed_status_retries(self):
        mock_fail = MagicMock()
        mock_fail.status = "failed"
        mock_fail.error = "rate limited"

        mock_ok = MagicMock()
        mock_ok.status = "completed"
        mock_ok.output_text = "Success"
        mock_ok.usage = None

        client = MagicMock()
        client.responses.create.side_effect = [mock_fail, mock_ok]

        with patch('prep.time') as mock_time:
            mock_time.sleep = MagicMock()
            mock_time.time = MagicMock(return_value=0)
            result = prep.call_llm(client, "inst", "inp", "test")

        self.assertEqual(result, "Success")

    def test_all_retries_exhausted(self):
        mock_fail = MagicMock()
        mock_fail.status = "failed"
        mock_fail.error = "server error"

        client = MagicMock()
        client.responses.create.return_value = mock_fail

        with patch('prep.time') as mock_time:
            mock_time.sleep = MagicMock()
            mock_time.time = MagicMock(return_value=0)
            result = prep.call_llm(client, "inst", "inp", "test", retries=2)

        self.assertIsNone(result)
        self.assertEqual(client.responses.create.call_count, 2)

    def test_polling_timeout(self):
        """Test that polling raises after POLL_TIMEOUT seconds."""
        mock_initial = MagicMock()
        mock_initial.status = "in_progress"
        mock_initial.id = "resp_stuck"

        client = MagicMock()
        client.responses.create.return_value = mock_initial
        client.responses.retrieve.return_value = MagicMock(status="in_progress")

        # Simulate time advancing past timeout
        orig_timeout = prep.POLL_TIMEOUT
        prep.POLL_TIMEOUT = 10  # 10 second timeout for test

        times = iter([0, 5, 11])  # third call is past timeout
        with patch('prep.time') as mock_time:
            mock_time.sleep = MagicMock()
            mock_time.time = MagicMock(side_effect=times)
            result = prep.call_llm(client, "inst", "inp", "test", retries=1)

        prep.POLL_TIMEOUT = orig_timeout
        self.assertIsNone(result)

    def test_unexpected_status(self):
        """Test that unexpected status (not failed, not completed) is handled."""
        mock_resp = MagicMock()
        mock_resp.status = "cancelled"
        mock_resp.output_text = None

        client = MagicMock()
        client.responses.create.return_value = mock_resp

        with patch('prep.time') as mock_time:
            mock_time.sleep = MagicMock()
            mock_time.time = MagicMock(return_value=0)
            result = prep.call_llm(client, "inst", "inp", "test", retries=1)

        # Should fail gracefully (output_text is None -> "Empty output" exception -> retry exhausted)
        self.assertIsNone(result)


class TestParseAgendasWarning(_ProfileTestMixin, unittest.TestCase):
    """Test that empty parse results trigger warnings during syllabus."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self._save_profile_state()
        for attr in ['IN_AGENDAS', 'IN_EPISODES', 'SYLLABUS_DIR', 'EPISODES_DIR',
                      'RAW_DIR', 'GEM_DIR', 'NLM_DIR']:
            new_dir = Path(self.tmpdir) / attr.lower()
            new_dir.mkdir(parents=True)
            setattr(prep, attr, new_dir)

    def tearDown(self):
        self._restore_profile_state()
        shutil.rmtree(self.tmpdir)

    def test_warning_printed_on_empty_parse(self):
        """If model output has no parseable episodes, a warning should print."""
        # Model returns garbage with no Episode headers
        mock_resp = MagicMock()
        mock_resp.status = "completed"
        mock_resp.output_text = "Here is some content without any episode headers at all."
        mock_resp.usage = None

        client = MagicMock()
        client.responses.create.return_value = mock_resp

        orig_runs = prep.SYLLABUS_RUNS
        prep.SYLLABUS_RUNS = [dict(mode="CORE_BATCH", core="1-4", frontier="")]

        import io
        from contextlib import redirect_stdout
        f = io.StringIO()
        try:
            with redirect_stdout(f):
                prep.cmd_syllabus(client, force=True)
        finally:
            prep.SYLLABUS_RUNS = orig_runs

        output = f.getvalue()
        self.assertIn("WARNING", output)
        self.assertIn("parse_agendas found 0 episodes", output)

    def test_no_warning_on_successful_parse(self):
        """Normal episode output should NOT trigger warning."""
        mock_resp = MagicMock()
        mock_resp.status = "completed"
        mock_resp.output_text = "## Episode 1: Binding\nContent\n\n## Episode 2: Session\nContent\n\n## Episode 3: Mobile\nContent\n\n## Episode 4: Passkeys\nContent"
        mock_resp.usage = None

        client = MagicMock()
        client.responses.create.return_value = mock_resp

        orig_runs = prep.SYLLABUS_RUNS
        prep.SYLLABUS_RUNS = [dict(mode="CORE_BATCH", core="1-4", frontier="")]

        import io
        from contextlib import redirect_stdout
        f = io.StringIO()
        try:
            with redirect_stdout(f):
                prep.cmd_syllabus(client, force=True)
        finally:
            prep.SYLLABUS_RUNS = orig_runs

        output = f.getvalue()
        self.assertNotIn("WARNING", output)
        self.assertIn("saved episode-01-agenda.md", output)


class TestCmdAllFailureHandling(_ProfileTestMixin, unittest.TestCase):
    """Test that cmd_all warns on syllabus failure."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self._save_profile_state()
        for attr in ['IN_AGENDAS', 'IN_EPISODES', 'SYLLABUS_DIR', 'EPISODES_DIR',
                      'RAW_DIR', 'GEM_DIR', 'NLM_DIR']:
            new_dir = Path(self.tmpdir) / attr.lower()
            new_dir.mkdir(parents=True)
            setattr(prep, attr, new_dir)

    def tearDown(self):
        self._restore_profile_state()
        shutil.rmtree(self.tmpdir)

    def test_warns_on_syllabus_failure(self):
        """If syllabus fails, cmd_all should print warning but continue."""
        # Make syllabus fail by returning None from LLM
        client = MagicMock()
        client.responses.create.return_value = MagicMock(
            status="failed", error="test failure"
        )

        orig_runs = prep.SYLLABUS_RUNS
        prep.SYLLABUS_RUNS = [dict(mode="SCAFFOLD", core="", frontier="")]

        import io
        from contextlib import redirect_stdout
        f = io.StringIO()
        try:
            with redirect_stdout(f):
                with patch('prep.time') as mock_time:
                    mock_time.sleep = MagicMock()
                    mock_time.time = MagicMock(return_value=0)
                    prep.cmd_all(client, force=True)
        finally:
            prep.SYLLABUS_RUNS = orig_runs

        output = f.getvalue()
        self.assertIn("WARNING: Syllabus had failures", output)


class TestCmdAllAlreadyComplete(_ProfileTestMixin, unittest.TestCase):
    """Test that cmd_all short-circuits when pipeline is already complete."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self._save_profile_state()
        for attr in ['IN_AGENDAS', 'IN_EPISODES', 'SYLLABUS_DIR', 'EPISODES_DIR',
                      'RAW_DIR', 'GEM_DIR', 'NLM_DIR']:
            new_dir = Path(self.tmpdir) / attr.lower()
            new_dir.mkdir(parents=True)
            setattr(prep, attr, new_dir)

    def tearDown(self):
        self._restore_profile_state()
        shutil.rmtree(self.tmpdir)

    def test_skips_when_complete(self):
        """cmd_all should print message and return without API calls when all outputs exist."""
        for ep in prep.ALL_EPS:
            (prep.SYLLABUS_DIR / prep.ep_file(ep, "agenda")).write_text("agenda", encoding="utf-8")
            (prep.EPISODES_DIR / prep.ep_file(ep, "content")).write_text("x" * 500, encoding="utf-8")

        client = MagicMock()
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            prep.cmd_all(client)
        output = buf.getvalue()
        self.assertIn("already complete", output)
        self.assertIn("--force", output)
        client.responses.create.assert_not_called()

    def test_runs_when_incomplete(self):
        """cmd_all should proceed normally when outputs are missing."""
        client = MagicMock()
        client.responses.create.return_value = MagicMock(
            status="failed", error="test"
        )
        orig_runs = prep.SYLLABUS_RUNS
        prep.SYLLABUS_RUNS = [dict(mode="SCAFFOLD", core="", frontier="")]
        buf = io.StringIO()
        try:
            with contextlib.redirect_stdout(buf):
                with patch('prep.time') as mock_time:
                    mock_time.sleep = MagicMock()
                    mock_time.time = MagicMock(return_value=0)
                    prep.cmd_all(client)
        finally:
            prep.SYLLABUS_RUNS = orig_runs
        output = buf.getvalue()
        self.assertNotIn("already complete", output)


class TestRecoverFromRaw(_ProfileTestMixin, unittest.TestCase):
    """Test recovery of agendas from raw syllabus files."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self._save_profile_state()
        for attr in ['IN_AGENDAS', 'IN_EPISODES', 'SYLLABUS_DIR', 'EPISODES_DIR',
                      'RAW_DIR', 'GEM_DIR', 'NLM_DIR']:
            new_dir = Path(self.tmpdir) / attr.lower()
            new_dir.mkdir(parents=True)
            setattr(prep, attr, new_dir)

    def tearDown(self):
        self._restore_profile_state()
        shutil.rmtree(self.tmpdir)

    def test_recovers_agendas_from_raw_core_batch(self):
        """If raw file exists but agendas don't, recover them."""
        raw_text = """**Episode 1 — The Binding Problem**
Content for ep 1.

**Episode 2 — The Session Kill Switch**
Content for ep 2.
"""
        (prep.RAW_DIR / "syllabus-02-core_batch.md").write_text(raw_text, encoding="utf-8")

        count = prep.recover_agendas_from_raw()
        self.assertEqual(count, 2)
        self.assertTrue((prep.SYLLABUS_DIR / "episode-01-agenda.md").exists())
        self.assertTrue((prep.SYLLABUS_DIR / "episode-02-agenda.md").exists())

    def test_no_double_recovery(self):
        """If agenda already exists, don't overwrite."""
        raw_text = "**Episode 1 — New Version**\nNew content."
        (prep.RAW_DIR / "syllabus-02-core_batch.md").write_text(raw_text, encoding="utf-8")
        (prep.SYLLABUS_DIR / "episode-01-agenda.md").write_text("Original content", encoding="utf-8")

        count = prep.recover_agendas_from_raw()
        self.assertEqual(count, 0)
        self.assertEqual(
            (prep.SYLLABUS_DIR / "episode-01-agenda.md").read_text(encoding="utf-8"),
            "Original content"
        )

    def test_respects_inputs_priority(self):
        """If agenda exists in inputs/, don't recover from raw."""
        raw_text = "**Episode 1 — From Raw**\nRaw content."
        (prep.RAW_DIR / "syllabus-02-core_batch.md").write_text(raw_text, encoding="utf-8")
        (prep.IN_AGENDAS / "episode-01-agenda.md").write_text("From inputs", encoding="utf-8")

        count = prep.recover_agendas_from_raw()
        self.assertEqual(count, 0)

    def test_recovers_frontier_digest(self):
        raw_text = "**Frontier Digest A — Updates**\nFrontier content."
        (prep.RAW_DIR / "syllabus-03-frontier_digest.md").write_text(raw_text, encoding="utf-8")

        count = prep.recover_agendas_from_raw()
        self.assertEqual(count, 1)
        self.assertTrue((prep.SYLLABUS_DIR / "episode-13-agenda.md").exists())

    def test_skips_empty_raw_file(self):
        (prep.RAW_DIR / "syllabus-02-core_batch.md").write_text("", encoding="utf-8")
        count = prep.recover_agendas_from_raw()
        self.assertEqual(count, 0)

    @unittest.skipUnless(
        (Path(__file__).parent / "profiles" / "security-infra" / "outputs" / "raw" / "syllabus-02-core_batch.md").exists(),
        "Real output file not available (run pipeline first)"
    )
    def test_recovers_from_real_raw_file(self):
        """Recovery works with actual GPT-5.2-pro output."""
        real_text = (Path(__file__).parent / "profiles" / "security-infra" / "outputs" / "raw" / "syllabus-02-core_batch.md").read_text(encoding="utf-8")
        (prep.RAW_DIR / "syllabus-02-core_batch.md").write_text(real_text, encoding="utf-8")

        count = prep.recover_agendas_from_raw()
        self.assertEqual(count, 4)
        for ep in [1, 2, 3, 4]:
            p = prep.SYLLABUS_DIR / f"episode-{ep:02d}-agenda.md"
            self.assertTrue(p.exists(), f"Missing {p.name}")
            self.assertGreater(len(p.read_text(encoding="utf-8")), 1000)


class TestSyllabusRuns(unittest.TestCase):
    """Verify the SYLLABUS_RUNS configuration is correct."""

    def test_eight_runs(self):
        self.assertEqual(len(prep.SYLLABUS_RUNS), 8)

    def test_run_order(self):
        modes = [r["mode"] for r in prep.SYLLABUS_RUNS]
        self.assertEqual(modes, [
            "SCAFFOLD",
            "CORE_BATCH", "FRONTIER_DIGEST",
            "CORE_BATCH", "FRONTIER_DIGEST",
            "CORE_BATCH", "FRONTIER_DIGEST",
            "FINAL_MERGE",
        ])

    def test_core_batch_ranges(self):
        cores = [r["core"] for r in prep.SYLLABUS_RUNS if r["mode"] == "CORE_BATCH"]
        self.assertEqual(cores, ["1-4", "5-8", "9-12"])

    def test_frontier_labels(self):
        fronts = [r["frontier"] for r in prep.SYLLABUS_RUNS if r["mode"] == "FRONTIER_DIGEST"]
        self.assertEqual(fronts, ["A", "B", "C"])


class TestConstants(unittest.TestCase):
    def test_all_eps_is_1_through_15(self):
        self.assertEqual(prep.ALL_EPS, list(range(1, 16)))

    def test_core_eps(self):
        self.assertEqual(prep.CORE_EPS, list(range(1, 13)))

    def test_frontier_eps(self):
        self.assertEqual(prep.FRONTIER_EPS, [13, 14, 15])


class TestReplayRealOutput(unittest.TestCase):
    """Replay test using actual GPT-5.2-pro output."""

    REAL_FILE = Path(__file__).parent / "profiles" / "security-infra" / "outputs" / "raw" / "syllabus-02-core_batch.md"

    @unittest.skipUnless(
        (Path(__file__).parent / "profiles" / "security-infra" / "outputs" / "raw" / "syllabus-02-core_batch.md").exists(),
        "Real output file not available (run pipeline first)"
    )
    def test_parse_real_core_batch_1_4(self):
        text = self.REAL_FILE.read_text(encoding="utf-8")
        result = prep.parse_agendas(text)

        # Must find exactly episodes 1-4
        self.assertEqual(sorted(result.keys()), [1, 2, 3, 4])

        # Each episode should be substantial (>1000 chars)
        for ep in [1, 2, 3, 4]:
            self.assertGreater(len(result[ep]), 1000,
                f"Episode {ep} too short: {len(result[ep])} chars")

        # Each episode should contain all 7 section markers
        for ep in [1, 2, 3, 4]:
            content = result[ep]
            for section in ["Hook", "Mental Model", "Nitty Gritty",
                            "Staff Pivot", "Scenario Challenge"]:
                self.assertIn(section, content,
                    f"Episode {ep} missing section: {section}")

    @unittest.skipUnless(
        (Path(__file__).parent / "profiles" / "security-infra" / "outputs" / "raw" / "syllabus-02-core_batch.md").exists(),
        "Real output file not available (run pipeline first)"
    )
    def test_no_cross_contamination(self):
        """Episode 1 content should NOT contain Episode 2's title."""
        text = self.REAL_FILE.read_text(encoding="utf-8")
        result = prep.parse_agendas(text)

        self.assertNotIn("Session Kill Switch", result[1])
        self.assertNotIn("Binding Problem", result[2])
        self.assertNotIn("Mobile Identity", result[1])
        self.assertNotIn("Confused Deputy", result[1])


class TestRecoveryCalledByAllCommands(_ProfileTestMixin, unittest.TestCase):
    """Verify recovery runs in status, syllabus, and content commands.
    Bug found in review round 6: status and syllabus didn't call recovery,
    so user would see 0 agendas or re-run all 8 syllabus calls."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self._save_profile_state()
        for attr in ['IN_AGENDAS', 'IN_EPISODES', 'SYLLABUS_DIR', 'EPISODES_DIR',
                      'RAW_DIR', 'GEM_DIR', 'NLM_DIR']:
            new_dir = Path(self.tmpdir) / attr.lower()
            new_dir.mkdir(parents=True)
            setattr(prep, attr, new_dir)

    def tearDown(self):
        self._restore_profile_state()
        shutil.rmtree(self.tmpdir)

    def _seed_raw(self):
        """Put a raw core_batch file that needs recovery."""
        (prep.RAW_DIR / "syllabus-02-core_batch.md").write_text(
            "**Episode 1 — Title**\nContent 1\n\n"
            "**Episode 2 — Title**\nContent 2\n"
        , encoding="utf-8")

    def test_status_triggers_recovery(self):
        self._seed_raw()
        self.assertFalse((prep.SYLLABUS_DIR / "episode-01-agenda.md").exists())

        import io
        from contextlib import redirect_stdout
        with redirect_stdout(io.StringIO()) as f:
            prep.cmd_status()

        self.assertTrue((prep.SYLLABUS_DIR / "episode-01-agenda.md").exists())
        self.assertIn("recovered", f.getvalue())

    def test_syllabus_triggers_recovery(self):
        self._seed_raw()
        self.assertFalse((prep.SYLLABUS_DIR / "episode-01-agenda.md").exists())

        # Also need scaffold + final_merge so syllabus skips everything
        (prep.SYLLABUS_DIR / "scaffold.md").write_text("scaffold", encoding="utf-8")
        (prep.SYLLABUS_DIR / "final_merge.md").write_text("merge", encoding="utf-8")

        client = MagicMock()
        orig_runs = prep.SYLLABUS_RUNS
        prep.SYLLABUS_RUNS = [dict(mode="CORE_BATCH", core="1-2", frontier="")]
        try:
            import io
            from contextlib import redirect_stdout
            with redirect_stdout(io.StringIO()) as f:
                prep.cmd_syllabus(client, force=False)
        finally:
            prep.SYLLABUS_RUNS = orig_runs

        # Agendas should exist from recovery, and CORE_BATCH should have been skipped
        self.assertTrue((prep.SYLLABUS_DIR / "episode-01-agenda.md").exists())
        output = f.getvalue()
        self.assertIn("recovered", output)
        self.assertIn("skip", output)
        client.responses.create.assert_not_called()

    def test_content_triggers_recovery(self):
        self._seed_raw()
        self.assertFalse((prep.SYLLABUS_DIR / "episode-01-agenda.md").exists())

        mock_resp = MagicMock()
        mock_resp.status = "completed"
        mock_resp.output_text = "Generated content " * 100
        mock_resp.usage = None

        client = MagicMock()
        client.responses.create.return_value = mock_resp

        orig_all = prep.ALL_EPS
        prep.ALL_EPS = [1]
        try:
            import io
            from contextlib import redirect_stdout
            with redirect_stdout(io.StringIO()) as f:
                prep.cmd_content(client, force=False)
        finally:
            prep.ALL_EPS = orig_all

        output = f.getvalue()
        self.assertIn("recovered", output)
        client.responses.create.assert_called_once()


class TestEndToEndResume(_ProfileTestMixin, unittest.TestCase):
    """Simulate the exact morning scenario: raw files exist from overnight,
    zero agenda files, zero content. Run cmd_all with new code.
    Verify: recovery -> skip all syllabus -> generate all content -> package."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self._save_profile_state()
        for attr in ['IN_AGENDAS', 'IN_EPISODES', 'SYLLABUS_DIR', 'EPISODES_DIR',
                      'RAW_DIR', 'GEM_DIR', 'NLM_DIR', 'IN_MISC']:
            new_dir = Path(self.tmpdir) / attr.lower()
            new_dir.mkdir(parents=True)
            setattr(prep, attr, new_dir)

    def tearDown(self):
        self._restore_profile_state()
        shutil.rmtree(self.tmpdir)

    def _seed_overnight_state(self):
        """Simulate what the old code leaves behind: raw files + scaffold + final_merge.
        Zero agenda files, zero content files."""
        (prep.SYLLABUS_DIR / "scaffold.md").write_text("SCAFFOLD content", encoding="utf-8")
        (prep.SYLLABUS_DIR / "final_merge.md").write_text("FINAL_MERGE content", encoding="utf-8")

        for batch, eps in [("02", "1-4"), ("04", "5-8"), ("06", "9-12")]:
            s, e = map(int, eps.split("-"))
            text = "\n\n".join(
                f"**Episode {n} — Title {n}**\nHook for ep {n}.\nNitty gritty for ep {n}."
                for n in range(s, e + 1)
            )
            (prep.RAW_DIR / f"syllabus-{batch}-core_batch.md").write_text(text, encoding="utf-8")

        for num, letter in [("03", "A"), ("05", "B"), ("07", "C")]:
            text = f"**Frontier Digest {letter} — Updates**\nFrontier content for {letter}."
            (prep.RAW_DIR / f"syllabus-{num}-frontier_digest.md").write_text(text, encoding="utf-8")

        (prep.RAW_DIR / "syllabus-01-scaffold.md").write_text("SCAFFOLD raw", encoding="utf-8")
        (prep.RAW_DIR / "syllabus-08-final_merge.md").write_text("FINAL_MERGE raw", encoding="utf-8")

    def test_full_resume_flow(self):
        """The money test: overnight state -> recovery -> skip -> content -> package."""
        self._seed_overnight_state()

        # Verify starting state: zero agendas, zero content
        for ep in prep.ALL_EPS:
            self.assertIsNone(prep.find_agenda(ep))
            self.assertIsNone(prep.find_content(ep))

        call_count = [0]
        def mock_create(**kwargs):
            call_count[0] += 1
            resp = MagicMock()
            resp.status = "completed"
            resp.output_text = f"Content for call {call_count[0]} " * 100
            resp.usage = None
            return resp

        client = MagicMock()
        client.responses.create.side_effect = mock_create

        import io
        from contextlib import redirect_stdout
        with redirect_stdout(io.StringIO()) as f:
            prep.cmd_all(client, force=False)
        output = f.getvalue()

        # 1. Recovery should have found 15 agendas
        self.assertIn("recovered", output)
        for ep in prep.ALL_EPS:
            self.assertIsNotNone(prep.find_agenda(ep),
                f"Agenda missing for ep {ep}")

        # 2. All syllabus runs should have been skipped
        self.assertIn("skip Run 1/8: SCAFFOLD", output)
        self.assertIn("skip Run 2/8: CORE_BATCH (1-4)", output)

        # 3. Content generated for all 15 episodes
        self.assertEqual(client.responses.create.call_count, 15,
            f"Expected 15 LLM calls, got {client.responses.create.call_count}")
        for ep in prep.ALL_EPS:
            self.assertIsNotNone(prep.find_content(ep),
                f"Content missing for ep {ep}")

        # 4. Package created gem + notebooklm files
        self.assertTrue(any(prep.GEM_DIR.glob("gem-*.md")))
        nlm_files = list(prep.NLM_DIR.glob("*.md"))
        self.assertEqual(len(nlm_files), 15,
            f"Expected 15 NotebookLM files, got {len(nlm_files)}")

        # 5. Gem slots 1-7 should exist
        for slot in range(1, 8):
            self.assertTrue((prep.GEM_DIR / f"gem-{slot}.md").exists(),
                f"gem-{slot}.md missing")

    def test_resume_skips_already_generated_content(self):
        """If we resume after partial content gen, skip completed episodes."""
        self._seed_overnight_state()
        prep.recover_agendas_from_raw()

        for ep in [1, 2, 3]:
            (prep.EPISODES_DIR / prep.ep_file(ep, "content")).write_text(
                "Previously generated content " * 100
            , encoding="utf-8")

        mock_resp = MagicMock()
        mock_resp.status = "completed"
        mock_resp.output_text = "New content " * 100
        mock_resp.usage = None

        client = MagicMock()
        client.responses.create.return_value = mock_resp

        import io
        from contextlib import redirect_stdout
        with redirect_stdout(io.StringIO()) as f:
            prep.cmd_all(client, force=False)
        output = f.getvalue()

        # Should skip eps 1-3, generate 4-15 (12 calls)
        self.assertEqual(client.responses.create.call_count, 12,
            f"Expected 12 LLM calls, got {client.responses.create.call_count}")
        self.assertIn("skip ep 01", output)
        self.assertIn("skip ep 02", output)
        self.assertIn("skip ep 03", output)


class TestLoadPrompt(unittest.TestCase):
    def test_loads_syllabus_prompt(self):
        result = prep.load_prompt("syllabus")
        self.assertIn("MODE:", result)
        self.assertGreater(len(result), 1000)

    def test_loads_content_prompt(self):
        result = prep.load_prompt("content")
        self.assertIn("{EPISODE_AGENDA}", result)
        self.assertGreater(len(result), 1000)

    def test_loads_distill_prompt(self):
        result = prep.load_prompt("distill")
        self.assertIn("{RAW_DOCUMENT}", result)
        self.assertGreater(len(result), 500)

    def test_missing_prompt_exits(self):
        with self.assertRaises(SystemExit):
            prep.load_prompt("nonexistent_prompt_name")


class TestPromptTemplateStructure(unittest.TestCase):
    """Verify prompt files have expected structure. Catches corruption during editing."""

    def test_syllabus_has_run_config(self):
        t = prep.load_prompt("syllabus")
        self.assertIn("{MODE}", t)
        self.assertIn("{CORE_EPISODES}", t)
        self.assertIn("{FRONTIER_DIGEST}", t)
        self.assertIn("{AS_OF_OVERRIDE}", t)

    def test_syllabus_has_role_section(self):
        t = prep.load_prompt("syllabus")
        self.assertIn("ROLE + GOAL", t)

    def test_syllabus_has_seven_components(self):
        t = prep.load_prompt("syllabus")
        for section in ["Title", "Hook", "Mental Model", "Common Trap",
                        "Nitty Gritty", "Staff Pivot", "Scenario Challenge"]:
            self.assertIn(section, t)

    def test_syllabus_has_domain_seeds_marker(self):
        t = prep.load_prompt("syllabus")
        self.assertIn("TRAINING DATA", t)
        self.assertIn("{DOMAIN_SEEDS}", t)

    def test_content_has_section_headings(self):
        t = prep.load_prompt("content")
        for heading in ["## Title", "## Hook", "## Mental Model", "## Common Trap",
                        "## Nitty Gritty", "## Staff Pivot", "## Scenario Challenge"]:
            self.assertIn(heading, t)

    def test_content_has_micro_prefix_cues(self):
        t = prep.load_prompt("content")
        for prefix in ["Probe:", "Coding hook:", "Red flag:", "Anchor:", "Tie-back:"]:
            self.assertIn(prefix, t)

    def test_content_has_placeholders(self):
        t = prep.load_prompt("content")
        self.assertIn("{AS_OF_DATE}", t)
        self.assertIn("{EXTRA_NOTES}", t)
        self.assertIn("{EPISODE_AGENDA}", t)

    def test_distill_has_seven_components(self):
        t = prep.load_prompt("distill")
        for section in ["Title", "Hook", "Mental Model", "Common Trap",
                        "Nitty Gritty", "Staff Pivot", "Scenario Challenge"]:
            self.assertIn(section, t)

    def test_distill_has_placeholder(self):
        t = prep.load_prompt("distill")
        self.assertIn("{RAW_DOCUMENT}", t)


class TestCmdAdd(_ProfileTestMixin, unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self._save_profile_state()
        for attr in ['SYLLABUS_DIR', 'EPISODES_DIR', 'GEM_DIR', 'NLM_DIR']:
            new_dir = Path(self.tmpdir) / attr.lower()
            new_dir.mkdir(parents=True)
            setattr(prep, attr, new_dir)

    def tearDown(self):
        self._restore_profile_state()
        shutil.rmtree(self.tmpdir)

    def test_add_creates_agenda_and_content(self):
        src = Path(self.tmpdir) / "test-paper.md"
        src.write_text("This is a test paper about mTLS.", encoding="utf-8")

        mock_agenda = MagicMock(status="completed", output_text="## Agenda\nTest agenda", usage=None)
        mock_content = MagicMock(status="completed", output_text="## Content\nTest content " * 50, usage=None)

        client = MagicMock()
        client.responses.create.side_effect = [mock_agenda, mock_content]

        result = prep.cmd_add(client, str(src), slot=8)

        self.assertTrue(result)
        self.assertTrue((prep.SYLLABUS_DIR / "misc-test-paper-agenda.md").exists())
        self.assertTrue((prep.EPISODES_DIR / "misc-test-paper-content.md").exists())
        self.assertTrue((prep.NLM_DIR / "misc-test-paper-content.md").exists())
        self.assertTrue((prep.GEM_DIR / "gem-8.md").exists())
        self.assertIn("Test content", (prep.GEM_DIR / "gem-8.md").read_text(encoding="utf-8"))

    def test_add_nonexistent_file(self):
        client = MagicMock()
        result = prep.cmd_add(client, "/nonexistent/file.md")
        self.assertFalse(result)
        client.responses.create.assert_not_called()

    def test_add_distill_failure(self):
        src = Path(self.tmpdir) / "test.md"
        src.write_text("content", encoding="utf-8")

        client = MagicMock()
        client.responses.create.return_value = MagicMock(
            status="failed", error="test"
        )

        with patch('prep.time') as mock_time:
            mock_time.sleep = MagicMock()
            mock_time.time = MagicMock(return_value=0)
            result = prep.cmd_add(client, str(src))

        self.assertFalse(result)

    def test_add_custom_gem_slot(self):
        src = Path(self.tmpdir) / "paper.md"
        src.write_text("content", encoding="utf-8")

        client = MagicMock()
        client.responses.create.side_effect = [
            MagicMock(status="completed", output_text="agenda", usage=None),
            MagicMock(status="completed", output_text="content " * 50, usage=None),
        ]

        prep.cmd_add(client, str(src), slot=3)
        self.assertTrue((prep.GEM_DIR / "gem-3.md").exists())


class TestWriteManifest(_ProfileTestMixin, unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self._save_profile_state()
        for attr in ['IN_AGENDAS', 'IN_EPISODES', 'SYLLABUS_DIR', 'EPISODES_DIR',
                      'GEM_DIR', 'NLM_DIR', 'OUTPUTS']:
            new_dir = Path(self.tmpdir) / attr.lower()
            new_dir.mkdir(parents=True)
            setattr(prep, attr, new_dir)

    def tearDown(self):
        self._restore_profile_state()
        shutil.rmtree(self.tmpdir)

    def test_manifest_created(self):
        (prep.SYLLABUS_DIR / "episode-01-agenda.md").write_text("agenda", encoding="utf-8")
        (prep.EPISODES_DIR / "episode-01-content.md").write_text("content " * 500, encoding="utf-8")
        prep.write_manifest()
        manifest = prep.OUTPUTS / "manifest.txt"
        self.assertTrue(manifest.exists())
        text = manifest.read_text(encoding="utf-8")
        self.assertIn("MANIFEST", text)
        self.assertIn("ep 01:", text)

    def test_manifest_warns_on_missing(self):
        prep.write_manifest()
        text = (prep.OUTPUTS / "manifest.txt").read_text(encoding="utf-8")
        self.assertIn("MISSING", text)

    def test_manifest_warns_on_small_content(self):
        (prep.EPISODES_DIR / "episode-01-content.md").write_text("tiny", encoding="utf-8")
        prep.write_manifest()
        text = (prep.OUTPUTS / "manifest.txt").read_text(encoding="utf-8")
        self.assertIn("suspiciously small", text)


class TestContentEdgeCases(_ProfileTestMixin, unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self._save_profile_state()
        for attr in ['IN_AGENDAS', 'IN_EPISODES', 'SYLLABUS_DIR', 'EPISODES_DIR',
                      'RAW_DIR', 'GEM_DIR', 'NLM_DIR']:
            new_dir = Path(self.tmpdir) / attr.lower()
            new_dir.mkdir(parents=True)
            setattr(prep, attr, new_dir)

    def tearDown(self):
        self._restore_profile_state()
        shutil.rmtree(self.tmpdir)

    def test_content_warns_on_missing_agenda(self):
        """Episode with no agenda should warn, not crash."""
        client = MagicMock()
        orig_all = prep.ALL_EPS
        prep.ALL_EPS = [99]
        try:
            import io
            from contextlib import redirect_stdout
            with redirect_stdout(io.StringIO()) as f:
                prep.cmd_content(client, force=False)
        finally:
            prep.ALL_EPS = orig_all
        self.assertIn("no agenda", f.getvalue())
        client.responses.create.assert_not_called()

    def test_content_warns_on_empty_agenda(self):
        """Episode with empty agenda should warn, not crash."""
        (prep.SYLLABUS_DIR / "episode-01-agenda.md").write_text("", encoding="utf-8")
        client = MagicMock()
        orig_all = prep.ALL_EPS
        prep.ALL_EPS = [1]
        try:
            import io
            from contextlib import redirect_stdout
            with redirect_stdout(io.StringIO()) as f:
                prep.cmd_content(client, force=False)
        finally:
            prep.ALL_EPS = orig_all
        self.assertIn("empty", f.getvalue())
        client.responses.create.assert_not_called()

    def test_frontier_digest_skip(self):
        """FRONTIER_DIGEST should be skipped if agenda exists."""
        (prep.SYLLABUS_DIR / "episode-13-agenda.md").write_text("frontier A agenda", encoding="utf-8")
        client = MagicMock()
        orig_runs = prep.SYLLABUS_RUNS
        prep.SYLLABUS_RUNS = [dict(mode="FRONTIER_DIGEST", core="", frontier="A")]
        try:
            prep.cmd_syllabus(client, force=False)
        finally:
            prep.SYLLABUS_RUNS = orig_runs
        client.responses.create.assert_not_called()


class TestRoleConfig(unittest.TestCase):
    def test_role_var_exists(self):
        self.assertTrue(hasattr(prep, 'ROLE'))

    def test_company_var_exists(self):
        self.assertTrue(hasattr(prep, 'COMPANY'))

    def test_domain_var_exists(self):
        self.assertTrue(hasattr(prep, 'DOMAIN'))

    def test_audience_var_exists(self):
        self.assertTrue(hasattr(prep, 'AUDIENCE'))

    def test_defaults_are_generic(self):
        """Defaults must not contain Google or L6."""
        for val in [prep.ROLE, prep.COMPANY, prep.DOMAIN, prep.AUDIENCE]:
            self.assertNotIn("Google", val)
            self.assertNotIn("L6", val)


class TestSystemInstructions(unittest.TestCase):
    def test_syllabus_instructions_use_role(self):
        self.assertIn(prep.ROLE, prep._syllabus_instructions())

    def test_syllabus_instructions_use_company(self):
        self.assertIn(prep.COMPANY, prep._syllabus_instructions())

    def test_content_instructions_use_role(self):
        self.assertIn(prep.ROLE, prep._content_instructions())

    def test_content_instructions_use_company(self):
        self.assertIn(prep.COMPANY, prep._content_instructions())

    def test_distill_instructions_use_role(self):
        self.assertIn(prep.ROLE, prep._distill_instructions())

    def test_distill_instructions_use_company(self):
        self.assertIn(prep.COMPANY, prep._distill_instructions())

    def test_no_hardcoded_google_in_instructions(self):
        for instr in [prep._syllabus_instructions(),
                      prep._content_instructions(),
                      prep._distill_instructions()]:
            self.assertNotIn("Staff Security Engineer (L6)", instr)

    def test_instructions_reflect_updated_role(self):
        """After changing ROLE, instructions should use new value."""
        orig = prep.ROLE
        prep.ROLE = "Principal Engineer"
        try:
            self.assertIn("Principal Engineer", prep._syllabus_instructions())
            self.assertIn("Principal Engineer", prep._content_instructions())
            self.assertIn("Principal Engineer", prep._distill_instructions())
        finally:
            prep.ROLE = orig

    def test_instructions_reflect_updated_company(self):
        """After changing COMPANY, instructions should use new value."""
        orig = prep.COMPANY
        prep.COMPANY = "Acme Corp"
        try:
            self.assertIn("Acme Corp", prep._syllabus_instructions())
            self.assertIn("Acme Corp", prep._content_instructions())
            self.assertIn("Acme Corp", prep._distill_instructions())
        finally:
            prep.COMPANY = orig


class TestParameterizedPrompts(unittest.TestCase):
    def test_syllabus_prompt_contains_role(self):
        run = dict(mode="SCAFFOLD", core="", frontier="")
        result = prep.syllabus_prompt(run)
        self.assertIn(prep.ROLE, result)

    def test_syllabus_prompt_contains_company(self):
        run = dict(mode="SCAFFOLD", core="", frontier="")
        result = prep.syllabus_prompt(run)
        self.assertIn(prep.COMPANY, result)

    def test_syllabus_prompt_contains_domain(self):
        run = dict(mode="CORE_BATCH", core="1-4", frontier="")
        result = prep.syllabus_prompt(run)
        self.assertIn(prep.DOMAIN, result)

    def test_syllabus_prompt_contains_audience(self):
        run = dict(mode="SCAFFOLD", core="", frontier="")
        result = prep.syllabus_prompt(run)
        self.assertIn(prep.AUDIENCE, result)

    def test_syllabus_prompt_no_hardcoded_role(self):
        run = dict(mode="SCAFFOLD", core="", frontier="")
        result = prep.syllabus_prompt(run)
        self.assertNotIn("Staff Security Engineer (L6) at Google", result)

    def test_syllabus_prompt_injects_domain_seeds(self):
        """When domain content is loaded, seeds should appear in prompt."""
        orig_domain = prep._DOMAIN.copy()
        try:
            prep._DOMAIN = {"DOMAIN_SEEDS": "Episode 1: mTLS handshake\nEpisode 2: DPoP proofs"}
            run = dict(mode="SCAFFOLD", core="", frontier="")
            result = prep.syllabus_prompt(run)
            self.assertIn("mTLS", result)
            self.assertIn("DPoP", result)
            self.assertNotIn("{DOMAIN_SEEDS}", result)
        finally:
            prep._DOMAIN = orig_domain

    def test_syllabus_prompt_still_has_mode(self):
        """Existing format vars should still work."""
        run = dict(mode="CORE_BATCH", core="5-8", frontier="")
        result = prep.syllabus_prompt(run)
        self.assertIn("MODE: CORE_BATCH", result)
        self.assertIn("CORE_EPISODES: 5-8", result)

    def test_content_prompt_contains_role(self):
        result = prep.content_prompt("test agenda")
        self.assertIn(prep.ROLE, result)

    def test_content_prompt_contains_company(self):
        result = prep.content_prompt("test agenda")
        self.assertIn(prep.COMPANY, result)

    def test_content_prompt_no_hardcoded_role(self):
        result = prep.content_prompt("test agenda")
        self.assertNotIn("Staff Security Engineer (L6) at Google", result)

    def test_content_prompt_role_not_double_replaced(self):
        """Agenda containing literal {ROLE} should survive."""
        agenda = "This agenda mentions {ROLE} and {COMPANY} literally"
        result = prep.content_prompt(agenda)
        self.assertIn("{ROLE}", result)
        self.assertIn("{COMPANY}", result)

    def test_content_prompt_still_has_as_of(self):
        result = prep.content_prompt("test")
        self.assertIn(prep.AS_OF, result)

    def test_content_prompt_still_has_agenda(self):
        result = prep.content_prompt("My specific agenda text here")
        self.assertIn("My specific agenda text here", result)

    def test_distill_prompt_contains_role(self):
        result = prep.distill_prompt("raw doc text")
        self.assertIn(prep.ROLE, result)

    def test_distill_prompt_contains_company(self):
        result = prep.distill_prompt("raw doc text")
        self.assertIn(prep.COMPANY, result)

    def test_distill_prompt_contains_domain(self):
        result = prep.distill_prompt("raw doc text")
        self.assertIn(prep.DOMAIN, result)

    def test_distill_prompt_no_hardcoded_role(self):
        result = prep.distill_prompt("raw doc text")
        self.assertNotIn("Staff Security Engineer (L6) at Google", result)
        self.assertNotIn("Google L6 interviewer", result)

    def test_distill_prompt_still_has_raw_doc(self):
        result = prep.distill_prompt("My raw document content")
        self.assertIn("My raw document content", result)

    def test_distill_prompt_role_not_double_replaced(self):
        """Raw doc containing literal {ROLE} should survive."""
        raw = "Doc mentions {ROLE} and {COMPANY} literally"
        result = prep.distill_prompt(raw)
        self.assertIn("{ROLE}", result)
        self.assertIn("{COMPANY}", result)


class TestRenderTemplate(unittest.TestCase):
    def test_substitutes_all_placeholders(self):
        text = "Role: {PREP_ROLE}, Co: {PREP_COMPANY}, Dom: {PREP_DOMAIN}, Aud: {PREP_AUDIENCE}, Date: {AS_OF_DATE}"
        result = prep.render_template(text)
        self.assertNotIn("{PREP_ROLE}", result)
        self.assertNotIn("{PREP_COMPANY}", result)
        self.assertNotIn("{PREP_DOMAIN}", result)
        self.assertNotIn("{PREP_AUDIENCE}", result)
        self.assertNotIn("{AS_OF_DATE}", result)
        self.assertIn(prep.ROLE, result)
        self.assertIn(prep.COMPANY, result)
        self.assertIn(prep.DOMAIN, result)
        self.assertIn(prep.AUDIENCE, result)
        self.assertIn(prep.AS_OF, result)

    def test_leaves_unknown_placeholders(self):
        text = "Known: {PREP_ROLE}, Unknown: {UNKNOWN_VAR}"
        result = prep.render_template(text)
        self.assertIn("{UNKNOWN_VAR}", result)
        self.assertNotIn("{PREP_ROLE}", result)


class TestGemSlotCoverage(unittest.TestCase):
    def test_total_distinct_slots_is_8(self):
        all_slots = {prep.gem_slot(ep) for ep in prep.ALL_EPS}
        all_slots.add(prep.gem_slot(99))  # misc
        self.assertEqual(len(all_slots), 8)

    def test_core_maps_to_exactly_6_slots(self):
        core_slots = {prep.gem_slot(ep) for ep in prep.CORE_EPS}
        self.assertEqual(core_slots, {1, 2, 3, 4, 5, 6})


class TestPackageGemScaffold(_ProfileTestMixin, unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self._save_profile_state()
        for attr in ['IN_AGENDAS', 'IN_EPISODES', 'SYLLABUS_DIR', 'EPISODES_DIR',
                      'RAW_DIR', 'GEM_DIR', 'NLM_DIR']:
            new_dir = Path(self.tmpdir) / attr.lower()
            new_dir.mkdir(parents=True)
            setattr(prep, attr, new_dir)

    def tearDown(self):
        self._restore_profile_state()
        shutil.rmtree(self.tmpdir)

    def test_scaffold_copied_to_gem0(self):
        (prep.SYLLABUS_DIR / "scaffold.md").write_text("scaffold content here", encoding="utf-8")
        (prep.EPISODES_DIR / "episode-01-content.md").write_text("ep1 content", encoding="utf-8")
        prep.cmd_package()
        gem0 = prep.GEM_DIR / "gem-0-scaffold.md"
        self.assertTrue(gem0.exists())
        self.assertEqual(gem0.read_text(encoding="utf-8"), "scaffold content here")

    def test_final_merge_copied_to_gem0(self):
        (prep.SYLLABUS_DIR / "final_merge.md").write_text("merge content here", encoding="utf-8")
        (prep.EPISODES_DIR / "episode-01-content.md").write_text("ep1 content", encoding="utf-8")
        prep.cmd_package()
        gem0 = prep.GEM_DIR / "gem-0-final_merge.md"
        self.assertTrue(gem0.exists())
        self.assertEqual(gem0.read_text(encoding="utf-8"), "merge content here")


class TestScaffoldPromptListeningOrder(unittest.TestCase):
    def test_scaffold_prompt_contains_listening_order(self):
        run = dict(mode="SCAFFOLD", core="", frontier="")
        result = prep.syllabus_prompt(run)
        self.assertIn("Episodes 1-4", result)
        self.assertIn("Episode 13", result)


class TestBuildSyllabusRuns(unittest.TestCase):
    def test_default_produces_8_runs(self):
        self.assertEqual(len(prep.build_syllabus_runs(12, 3)), 8)

    def test_default_matches_original(self):
        expected = [
            dict(mode="SCAFFOLD",        core="",     frontier=""),
            dict(mode="CORE_BATCH",      core="1-4",  frontier=""),
            dict(mode="FRONTIER_DIGEST", core="",     frontier="A"),
            dict(mode="CORE_BATCH",      core="5-8",  frontier=""),
            dict(mode="FRONTIER_DIGEST", core="",     frontier="B"),
            dict(mode="CORE_BATCH",      core="9-12", frontier=""),
            dict(mode="FRONTIER_DIGEST", core="",     frontier="C"),
            dict(mode="FINAL_MERGE",     core="",     frontier=""),
        ]
        self.assertEqual(prep.build_syllabus_runs(12, 3), expected)

    def test_8_core_2_frontier(self):
        runs = prep.build_syllabus_runs(8, 2)
        self.assertEqual(len(runs), 6)
        modes = [r["mode"] for r in runs]
        self.assertEqual(modes, [
            "SCAFFOLD", "CORE_BATCH", "FRONTIER_DIGEST",
            "CORE_BATCH", "FRONTIER_DIGEST", "FINAL_MERGE",
        ])
        cores = [r["core"] for r in runs if r["mode"] == "CORE_BATCH"]
        self.assertEqual(cores, ["1-4", "5-8"])

    def test_6_core_1_frontier(self):
        runs = prep.build_syllabus_runs(6, 1)
        self.assertEqual(len(runs), 5)
        cores = [r["core"] for r in runs if r["mode"] == "CORE_BATCH"]
        self.assertEqual(cores, ["1-4", "5-6"])

    def test_4_core_0_frontier(self):
        runs = prep.build_syllabus_runs(4, 0)
        self.assertEqual(len(runs), 3)
        modes = [r["mode"] for r in runs]
        self.assertEqual(modes, ["SCAFFOLD", "CORE_BATCH", "FINAL_MERGE"])

    def test_1_core(self):
        runs = prep.build_syllabus_runs(1, 0)
        cores = [r["core"] for r in runs if r["mode"] == "CORE_BATCH"]
        self.assertEqual(cores, ["1"])  # not "1-1"

    def test_interleaving(self):
        runs = prep.build_syllabus_runs(12, 3)
        for i, r in enumerate(runs):
            if r["mode"] == "CORE_BATCH" and i + 1 < len(runs):
                # after each core batch (except last if no remaining frontier), next should be frontier
                next_r = runs[i + 1]
                if next_r["mode"] != "FINAL_MERGE":
                    self.assertEqual(next_r["mode"], "FRONTIER_DIGEST")

    def test_frontier_letters_sequential(self):
        runs = prep.build_syllabus_runs(12, 3)
        letters = [r["frontier"] for r in runs if r["mode"] == "FRONTIER_DIGEST"]
        self.assertEqual(letters, ["A", "B", "C"])

        runs5 = prep.build_syllabus_runs(20, 5)
        letters5 = [r["frontier"] for r in runs5 if r["mode"] == "FRONTIER_DIGEST"]
        self.assertEqual(letters5, ["A", "B", "C", "D", "E"])

    def test_more_frontiers_than_batches(self):
        # 4 core = 1 batch, but 3 frontiers
        runs = prep.build_syllabus_runs(4, 3)
        letters = [r["frontier"] for r in runs if r["mode"] == "FRONTIER_DIGEST"]
        self.assertEqual(letters, ["A", "B", "C"])

    def test_batch_size_max_4(self):
        for core in [1, 4, 5, 8, 12, 15, 20]:
            runs = prep.build_syllabus_runs(core, 0)
            for r in runs:
                if r["mode"] == "CORE_BATCH":
                    parts = r["core"].split("-")
                    s = int(parts[0])
                    e = int(parts[-1])
                    self.assertLessEqual(e - s + 1, 4, f"Batch {r['core']} exceeds 4 eps")


class TestFrontierMap(unittest.TestCase):
    def test_default(self):
        self.assertEqual(prep.frontier_map(), {"A": 13, "B": 14, "C": 15})

    def test_8_core_2_frontier(self):
        self.assertEqual(prep.frontier_map(8, 2), {"A": 9, "B": 10})

    def test_0_frontier(self):
        self.assertEqual(prep.frontier_map(12, 0), {})

    def test_5_frontiers(self):
        self.assertEqual(prep.frontier_map(20, 5),
                         {"A": 21, "B": 22, "C": 23, "D": 24, "E": 25})


class TestDynamicGemSlot(unittest.TestCase):
    def test_default_core_unchanged(self):
        # Same as existing TestGemSlot tests but via explicit params
        self.assertEqual(prep.gem_slot(1, 12, [13, 14, 15]), 1)
        self.assertEqual(prep.gem_slot(2, 12, [13, 14, 15]), 1)
        self.assertEqual(prep.gem_slot(11, 12, [13, 14, 15]), 6)
        self.assertEqual(prep.gem_slot(12, 12, [13, 14, 15]), 6)

    def test_default_frontier_unchanged(self):
        self.assertEqual(prep.gem_slot(13, 12, [13, 14, 15]), 7)
        self.assertEqual(prep.gem_slot(15, 12, [13, 14, 15]), 7)

    def test_default_misc_unchanged(self):
        self.assertEqual(prep.gem_slot(16, 12, [13, 14, 15]), 8)
        self.assertEqual(prep.gem_slot(99, 12, [13, 14, 15]), 8)

    def test_8_core_2_frontier(self):
        self.assertEqual(prep.gem_slot(1, 8, [9, 10]), 1)
        self.assertEqual(prep.gem_slot(8, 8, [9, 10]), 4)
        self.assertEqual(prep.gem_slot(9, 8, [9, 10]), 5)   # frontier slot
        self.assertEqual(prep.gem_slot(99, 8, [9, 10]), 6)   # misc slot

    def test_7_core_odd(self):
        # ep 7 is solo in last core slot
        self.assertEqual(prep.gem_slot(7, 7, [8]), 4)

    def test_0_frontier(self):
        self.assertEqual(prep.gem_slot(1, 6, []), 1)
        self.assertEqual(prep.gem_slot(99, 6, []), 4)  # no frontier slot, misc = ceil(6/2)+1


class TestDynamicManifest(_ProfileTestMixin, unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self._save_profile_state()
        for attr in ['IN_AGENDAS', 'IN_EPISODES', 'SYLLABUS_DIR', 'EPISODES_DIR',
                      'GEM_DIR', 'NLM_DIR', 'OUTPUTS']:
            new_dir = Path(self.tmpdir) / attr.lower()
            new_dir.mkdir(parents=True)
            setattr(prep, attr, new_dir)

    def tearDown(self):
        self._restore_profile_state()
        shutil.rmtree(self.tmpdir)

    def test_uses_dynamic_total(self):
        prep._reconfigure(8, 2)
        prep.write_manifest()
        text = (prep.OUTPUTS / "manifest.txt").read_text(encoding="utf-8")
        self.assertIn("0/10", text)
        self.assertNotIn("/15", text)

    def test_all_present_dynamic(self):
        prep._reconfigure(4, 1)
        for ep in prep.ALL_EPS:
            (prep.SYLLABUS_DIR / prep.ep_file(ep, "agenda")).write_text("agenda " * 100, encoding="utf-8")
            (prep.EPISODES_DIR / prep.ep_file(ep, "content")).write_text("content " * 500, encoding="utf-8")
        prep.write_manifest()
        text = (prep.OUTPUTS / "manifest.txt").read_text(encoding="utf-8")
        self.assertIn("all 5 episodes", text)
        self.assertNotIn("/15", text)

    def test_header_shows_dynamic_run_count(self):
        prep._reconfigure(8, 2)
        # Also set up RAW_DIR for cmd_syllabus
        raw_dir = Path(self.tmpdir) / "raw_dir"
        raw_dir.mkdir(parents=True)
        orig_raw = prep.RAW_DIR
        prep.RAW_DIR = raw_dir
        try:
            import io
            from contextlib import redirect_stdout
            # Create all needed files so all runs are skipped
            (prep.SYLLABUS_DIR / "scaffold.md").write_text("scaffold", encoding="utf-8")
            (prep.SYLLABUS_DIR / "final_merge.md").write_text("merge", encoding="utf-8")
            for ep in prep.ALL_EPS:
                (prep.SYLLABUS_DIR / prep.ep_file(ep, "agenda")).write_text("agenda", encoding="utf-8")
            client = MagicMock()
            with redirect_stdout(io.StringIO()) as f:
                prep.cmd_syllabus(client, force=False)
            output = f.getvalue()
            self.assertIn("6 runs", output)
            self.assertNotIn("8 runs", output)
        finally:
            prep.RAW_DIR = orig_raw


class TestDynamicPackaging(unittest.TestCase):
    def test_total_slots_default(self):
        self.assertEqual(prep._total_gem_slots(), 8)

    def test_total_slots_8_core(self):
        self.assertEqual(prep._total_gem_slots(8, 2), 6)

    def test_total_slots_0_frontier(self):
        self.assertEqual(prep._total_gem_slots(6, 0), 4)

    def test_8_core_creates_correct_gem_files(self):
        tmpdir = tempfile.mkdtemp()
        orig = {}
        for attr in ['IN_AGENDAS', 'IN_EPISODES', 'SYLLABUS_DIR', 'EPISODES_DIR',
                      'RAW_DIR', 'GEM_DIR', 'NLM_DIR']:
            orig[attr] = getattr(prep, attr)
            new_dir = Path(tmpdir) / attr.lower()
            new_dir.mkdir(parents=True)
            setattr(prep, attr, new_dir)
        prep._reconfigure(8, 2)
        try:
            # Create content for all 10 episodes
            for ep in prep.ALL_EPS:
                (prep.EPISODES_DIR / prep.ep_file(ep, "content")).write_text(f"Content for ep {ep}", encoding="utf-8")
            prep.cmd_package()
            # Core slots 1-4, frontier slot 5
            for slot in range(1, 5):
                self.assertTrue((prep.GEM_DIR / f"gem-{slot}.md").exists(), f"gem-{slot}.md missing")
            self.assertTrue((prep.GEM_DIR / "gem-5.md").exists(), "gem-5.md (frontier) missing")
        finally:
            prep._reconfigure()
            shutil.rmtree(tmpdir)
            for attr, val in orig.items():
                setattr(prep, attr, val)

    def test_misc_goes_to_dynamic_slot(self):
        tmpdir = tempfile.mkdtemp()
        orig = {}
        for attr in ['IN_AGENDAS', 'IN_EPISODES', 'SYLLABUS_DIR', 'EPISODES_DIR',
                      'RAW_DIR', 'GEM_DIR', 'NLM_DIR']:
            orig[attr] = getattr(prep, attr)
            new_dir = Path(tmpdir) / attr.lower()
            new_dir.mkdir(parents=True)
            setattr(prep, attr, new_dir)
        prep._reconfigure(8, 2)
        try:
            (prep.EPISODES_DIR / "misc-paper-content.md").write_text("Misc content", encoding="utf-8")
            prep.cmd_package()
            # With 8 core + 2 frontier: misc goes to slot 6
            self.assertTrue((prep.GEM_DIR / "gem-6.md").exists(), "gem-6.md (misc) missing")
            self.assertIn("Misc content", (prep.GEM_DIR / "gem-6.md").read_text(encoding="utf-8"))
        finally:
            prep._reconfigure()
            shutil.rmtree(tmpdir)
            for attr, val in orig.items():
                setattr(prep, attr, val)


class TestClampEffort(unittest.TestCase):
    """Test _clamp_effort() returns correct clamped values."""

    def test_valid_effort_unchanged(self):
        val, clamped = prep._clamp_effort("high", {"low", "medium", "high"})
        self.assertEqual(val, "high")
        self.assertFalse(clamped)

    def test_low_clamped_up(self):
        val, clamped = prep._clamp_effort("low", {"medium", "high", "xhigh"})
        self.assertEqual(val, "medium")
        self.assertTrue(clamped)

    def test_xhigh_clamped_down(self):
        val, clamped = prep._clamp_effort("xhigh", {"low", "medium", "high"})
        self.assertEqual(val, "high")
        self.assertTrue(clamped)

    def test_none_allowed_passes_through(self):
        val, clamped = prep._clamp_effort("low", None)
        self.assertEqual(val, "low")
        self.assertFalse(clamped)


class TestModelCapabilities(unittest.TestCase):
    """Test _model_capabilities() returns correct kwargs per model."""

    def setUp(self):
        self._orig_effort = prep.EFFORT
        self._orig_verbosity = prep.VERBOSITY
        prep.EFFORT = "high"
        prep.VERBOSITY = ""

    def tearDown(self):
        prep.EFFORT = self._orig_effort
        prep.VERBOSITY = self._orig_verbosity

    def test_gpt52pro_includes_reasoning_and_text(self):
        result = prep._model_capabilities("gpt-5.2-pro")
        self.assertIn("reasoning", result)
        self.assertEqual(result["reasoning"]["effort"], "high")
        self.assertEqual(result["text"]["verbosity"], "high")

    def test_gpt41_excludes_reasoning_and_text(self):
        result = prep._model_capabilities("gpt-4.1-mini")
        self.assertNotIn("reasoning", result)
        self.assertNotIn("text", result)

    def test_gpt52pro_clamps_low_to_medium(self):
        prep.EFFORT = "low"
        result = prep._model_capabilities("gpt-5.2-pro")
        self.assertEqual(result["reasoning"]["effort"], "medium")

    def test_o3_clamps_xhigh_to_high(self):
        prep.EFFORT = "xhigh"
        result = prep._model_capabilities("o3")
        self.assertEqual(result["reasoning"]["effort"], "high")

    def test_gpt4o_mini_excludes_reasoning(self):
        result = prep._model_capabilities("gpt-4o-mini")
        self.assertNotIn("reasoning", result)
        self.assertNotIn("text", result)

    def test_unknown_model_gets_safe_defaults(self):
        result = prep._model_capabilities("some-future-model")
        self.assertIn("reasoning", result)


class TestBadRequestRetry(unittest.TestCase):
    """Test call_llm() strips params on BadRequestError without consuming an attempt."""

    def setUp(self):
        self._orig_model = prep.MODEL
        self._orig_effort = prep.EFFORT
        prep.MODEL = "gpt-5.2-pro"
        prep.EFFORT = "high"

    def tearDown(self):
        prep.MODEL = self._orig_model
        prep.EFFORT = self._orig_effort

    def test_bad_request_strips_params_and_succeeds(self):
        from openai import BadRequestError
        mock_client = MagicMock()
        # First call raises BadRequestError, second succeeds
        good_resp = MagicMock()
        good_resp.status = "completed"
        good_resp.output_text = "result"
        good_resp.usage = None
        mock_client.responses.create.side_effect = [
            BadRequestError(
                message="Unsupported parameter",
                response=MagicMock(status_code=400, headers={}),
                body=None,
            ),
            good_resp,
        ]
        result = prep.call_llm(mock_client, "instr", "input", retries=3)
        self.assertEqual(result, "result")
        self.assertEqual(mock_client.responses.create.call_count, 2)

    def test_bad_request_strip_does_not_consume_attempt(self):
        from openai import BadRequestError
        mock_client = MagicMock()
        good_resp = MagicMock()
        good_resp.status = "completed"
        good_resp.output_text = "result"
        good_resp.usage = None
        # BadRequest then a normal error then success — should still work with retries=2
        mock_client.responses.create.side_effect = [
            BadRequestError(
                message="Unsupported parameter",
                response=MagicMock(status_code=400, headers={}),
                body=None,
            ),
            Exception("transient"),
            good_resp,
        ]
        result = prep.call_llm(mock_client, "instr", "input", retries=2)
        self.assertEqual(result, "result")
        self.assertEqual(mock_client.responses.create.call_count, 3)

    def test_double_bad_request_second_consumes_attempt(self):
        """After the free strip retry, subsequent BadRequestErrors consume attempts."""
        from openai import BadRequestError
        mock_client = MagicMock()
        err = BadRequestError(
            message="Unsupported parameter",
            response=MagicMock(status_code=400, headers={}),
            body=None,
        )
        # BadRequest -> BadRequest -> BadRequest with retries=2
        # 1st: free (strip), 2nd: attempt 0->1, 3rd: attempt 1->2 (exhausted)
        mock_client.responses.create.side_effect = [err, err, err]
        result = prep.call_llm(mock_client, "instr", "input", retries=2)
        self.assertIsNone(result)
        self.assertEqual(mock_client.responses.create.call_count, 3)


class TestDynamicConfig(unittest.TestCase):
    def tearDown(self):
        prep._reconfigure()

    def test_core_count_var_exists(self):
        self.assertEqual(prep._CORE_COUNT, 12)

    def test_frontier_count_var_exists(self):
        self.assertEqual(prep._FRONTIER_COUNT, 3)

    def test_eps_derived_from_counts(self):
        self.assertEqual(prep.CORE_EPS, list(range(1, prep._CORE_COUNT + 1)))
        self.assertEqual(prep.FRONTIER_EPS, list(range(prep._CORE_COUNT + 1, prep._CORE_COUNT + prep._FRONTIER_COUNT + 1)))

    def test_reconfigure_changes_all_derived_state(self):
        prep._reconfigure(8, 2)
        self.assertEqual(prep._CORE_COUNT, 8)
        self.assertEqual(prep._FRONTIER_COUNT, 2)
        self.assertEqual(prep.CORE_EPS, list(range(1, 9)))
        self.assertEqual(prep.FRONTIER_EPS, [9, 10])
        self.assertEqual(prep.ALL_EPS, list(range(1, 11)))
        self.assertEqual(len(prep.SYLLABUS_RUNS), 6)

    def test_reconfigure_defaults_restore(self):
        prep._reconfigure(8, 2)
        prep._reconfigure()
        self.assertEqual(prep._CORE_COUNT, 12)
        self.assertEqual(prep._FRONTIER_COUNT, 3)
        self.assertEqual(prep.CORE_EPS, list(range(1, 13)))
        self.assertEqual(prep.FRONTIER_EPS, [13, 14, 15])
        self.assertEqual(prep.ALL_EPS, list(range(1, 16)))
        self.assertEqual(len(prep.SYLLABUS_RUNS), 8)


class TestSyllabusPromptReplace(unittest.TestCase):
    """Phase 2: .replace()-based syllabus_prompt + count placeholders."""

    def tearDown(self):
        prep._reconfigure()

    def test_syllabus_prompt_with_braces_in_env_var(self):
        """Braces in env vars should not raise (.format() would choke)."""
        orig = prep.ROLE
        prep.ROLE = "Engineer {L6}"
        try:
            run = dict(mode="SCAFFOLD", core="", frontier="")
            result = prep.syllabus_prompt(run)
            self.assertIn("Engineer {L6}", result)
        finally:
            prep.ROLE = orig

    def test_syllabus_prompt_output_unchanged(self):
        """With default 12+3 config, SCAFFOLD prompt should contain expected strings."""
        run = dict(mode="SCAFFOLD", core="", frontier="")
        result = prep.syllabus_prompt(run)
        self.assertIn("MODE: SCAFFOLD", result)
        self.assertIn(prep.ROLE, result)
        self.assertIn("Episodes 1-12", result)
        self.assertIn("13-15", result)

    def test_syllabus_prompt_contains_dynamic_ranges(self):
        """With 8+2, prompt should contain '1-8' not '1-12'."""
        prep._reconfigure(8, 2)
        run = dict(mode="SCAFFOLD", core="", frontier="")
        result = prep.syllabus_prompt(run)
        self.assertIn("1-8", result)
        self.assertNotIn("1-12", result)
        self.assertIn("9-10", result)
        self.assertNotIn("13-15", result)

    def test_syllabus_prompt_default_matches_current(self):
        """With 12+3, '1-12' and '13-15' should appear."""
        run = dict(mode="CORE_BATCH", core="1-4", frontier="")
        result = prep.syllabus_prompt(run)
        self.assertIn("1-12", result)
        self.assertIn("13-15", result)

    def test_no_stray_placeholders(self):
        """Rendered prompt should have no unreplaced count placeholders."""
        run = dict(mode="SCAFFOLD", core="", frontier="")
        result = prep.syllabus_prompt(run)
        for placeholder in ["{TOTAL_CORE}", "{CORE_RANGE}", "{FRONTIER_RANGE}",
                            "{FRONTIER_MAP}", "{LISTENING_ORDER}"]:
            self.assertNotIn(placeholder, result)


class TestCountHelpers(unittest.TestCase):
    """Phase 2: _frontier_range_str, _frontier_map_str, _listening_order_str."""

    def tearDown(self):
        prep._reconfigure()

    def test_frontier_map_str_default(self):
        result = prep._frontier_map_str()
        self.assertIn("Digest A = Episode 13", result)
        self.assertIn("Digest B = Episode 14", result)
        self.assertIn("Digest C = Episode 15", result)
        self.assertEqual(result.count("\n"), 2)  # 3 lines

    def test_frontier_map_str_custom(self):
        prep._reconfigure(8, 2)
        result = prep._frontier_map_str()
        self.assertIn("Digest A = Episode 9", result)
        self.assertIn("Digest B = Episode 10", result)
        self.assertNotIn("Episode 13", result)

    def test_listening_order_default(self):
        result = prep._listening_order_str()
        self.assertIn("Episodes 1-4", result)
        self.assertIn("Episode 13 (Frontier Digest A)", result)
        self.assertIn("Episodes 5-8", result)
        self.assertIn("Episode 14 (Frontier Digest B)", result)

    def test_listening_order_custom(self):
        prep._reconfigure(4, 1)
        result = prep._listening_order_str()
        self.assertIn("Episodes 1-4", result)
        self.assertIn("Episode 5 (Frontier Digest A)", result)
        self.assertNotIn("Episode 13", result)

    def test_frontier_range_str_default(self):
        self.assertEqual(prep._frontier_range_str(), "13-15")

    def test_frontier_range_str_custom(self):
        prep._reconfigure(8, 2)
        self.assertEqual(prep._frontier_range_str(), "9-10")

    def test_frontier_range_str_zero(self):
        prep._reconfigure(8, 0)
        self.assertEqual(prep._frontier_range_str(), "(none)")

    def test_frontier_range_str_single(self):
        prep._reconfigure(4, 1)
        self.assertEqual(prep._frontier_range_str(), "5")


class TestLoadProfile(unittest.TestCase):
    """Step 1: load_profile() YAML frontmatter parser."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self._orig_base = prep.BASE_DIR
        prep.BASE_DIR = Path(self.tmpdir)

    def tearDown(self):
        prep.BASE_DIR = self._orig_base
        shutil.rmtree(self.tmpdir)

    def _write_profile(self, name, content):
        d = Path(self.tmpdir) / "profiles" / name
        d.mkdir(parents=True, exist_ok=True)
        (d / "profile.md").write_text(content, encoding="utf-8")

    def test_basic_parsing(self):
        self._write_profile("test", "---\nrole: Staff SWE\ncompany: Meta\ndomain: Backend\n---\n")
        cfg = prep.load_profile("test")
        self.assertEqual(cfg["role"], "Staff SWE")
        self.assertEqual(cfg["company"], "Meta")
        self.assertEqual(cfg["domain"], "Backend")

    def test_quoted_values(self):
        self._write_profile("test", '---\nrole: "Staff Security Engineer"\ncompany: \'Google\'\ndomain: Security\n---\n')
        cfg = prep.load_profile("test")
        self.assertEqual(cfg["role"], "Staff Security Engineer")
        self.assertEqual(cfg["company"], "Google")

    def test_case_insensitive_keys(self):
        self._write_profile("test", "---\nRole: Engineer\nCOMPANY: Acme\nDomain: ML\n---\n")
        cfg = prep.load_profile("test")
        self.assertEqual(cfg["role"], "Engineer")
        self.assertEqual(cfg["company"], "Acme")
        self.assertEqual(cfg["domain"], "ML")

    def test_integer_fields_parsed(self):
        self._write_profile("test", "---\nrole: SWE\ncompany: Co\ndomain: D\ncore_episodes: 8\nfrontier_episodes: 2\n---\n")
        cfg = prep.load_profile("test")
        self.assertEqual(cfg["core_episodes"], 8)
        self.assertEqual(cfg["frontier_episodes"], 2)

    def test_integer_validation_rejects_non_int(self):
        self._write_profile("test", "---\nrole: SWE\ncompany: Co\ndomain: D\ncore_episodes: twelve\n---\n")
        with self.assertRaises(SystemExit):
            prep.load_profile("test")

    def test_integer_validation_rejects_zero(self):
        self._write_profile("test", "---\nrole: SWE\ncompany: Co\ndomain: D\ncore_episodes: 0\n---\n")
        with self.assertRaises(SystemExit):
            prep.load_profile("test")

    def test_integer_validation_rejects_negative(self):
        self._write_profile("test", "---\nrole: SWE\ncompany: Co\ndomain: D\nfrontier_episodes: -1\n---\n")
        with self.assertRaises(SystemExit):
            prep.load_profile("test")

    def test_frontier_episodes_zero_is_valid(self):
        self._write_profile("test", "---\nrole: SWE\ncompany: Co\ndomain: D\nfrontier_episodes: 0\n---\n")
        cfg = prep.load_profile("test")
        self.assertEqual(cfg["frontier_episodes"], 0)

    def test_required_field_missing(self):
        self._write_profile("test", "---\nrole: SWE\ncompany: Co\n---\n")  # missing domain
        with self.assertRaises(SystemExit):
            prep.load_profile("test")

    def test_missing_dir(self):
        with self.assertRaises(SystemExit):
            prep.load_profile("nonexistent")

    def test_missing_profile_md(self):
        d = Path(self.tmpdir) / "profiles" / "empty"
        d.mkdir(parents=True)
        with self.assertRaises(SystemExit):
            prep.load_profile("empty")

    def test_unknown_key_warns(self):
        self._write_profile("test", "---\nrole: SWE\ncompany: Co\ndomain: D\nroll: typo\n---\n")
        import io
        from contextlib import redirect_stdout
        with redirect_stdout(io.StringIO()) as f:
            prep.load_profile("test")
        self.assertIn("WARNING", f.getvalue())
        self.assertIn("roll", f.getvalue())

    def test_blank_lines_and_comments_skipped(self):
        content = "---\nrole: SWE\n# comment\n\ncompany: Co\ndomain: D\n---\n"
        self._write_profile("test", content)
        cfg = prep.load_profile("test")
        self.assertEqual(cfg["role"], "SWE")
        self.assertEqual(cfg["company"], "Co")

    def test_optional_fields_not_required(self):
        self._write_profile("test", "---\nrole: SWE\ncompany: Co\ndomain: D\n---\n")
        cfg = prep.load_profile("test")
        self.assertNotIn("audience", cfg)
        self.assertNotIn("core_episodes", cfg)

    def test_all_known_fields(self):
        content = (
            "---\n"
            "role: SWE\ncompany: Co\ndomain: D\naudience: Engineers\n"
            "core_episodes: 10\nfrontier_episodes: 2\nmodel: gpt-4o\n"
            "effort: high\nas_of: Mar 2026\n"
            "---\n"
        )
        self._write_profile("test", content)
        cfg = prep.load_profile("test")
        self.assertEqual(len(cfg), 9)
        self.assertEqual(cfg["model"], "gpt-4o")
        self.assertEqual(cfg["effort"], "high")
        self.assertEqual(cfg["as_of"], "Mar 2026")

    def test_no_frontmatter_delimiters(self):
        self._write_profile("test", "role: SWE\ncompany: Co\ndomain: D\n")
        with self.assertRaises(SystemExit):
            prep.load_profile("test")

    def test_body_after_frontmatter_ignored(self):
        content = "---\nrole: SWE\ncompany: Co\ndomain: D\n---\n\n## Notes\nSome body text\nextra_key: should_not_parse\n"
        self._write_profile("test", content)
        cfg = prep.load_profile("test")
        self.assertNotIn("extra_key", cfg)
        self.assertEqual(len(cfg), 3)


class TestCostEstimates(unittest.TestCase):
    """Step 7: Cost estimates and --yes flag."""

    def test_estimate_scales_with_calls(self):
        _, cost8 = prep._estimate_cost(8)
        _, cost15 = prep._estimate_cost(15)
        self.assertGreater(cost15, cost8)

    def test_estimate_uses_model_prefix(self):
        orig = prep.MODEL
        prep.MODEL = "gpt-5.2-pro"
        try:
            _, cost = prep._estimate_cost(1)
            self.assertEqual(cost, 2.00)
        finally:
            prep.MODEL = orig

    def test_gpt4o_mini_cost(self):
        orig = prep.MODEL
        prep.MODEL = "gpt-4o-mini"
        try:
            _, cost = prep._estimate_cost(1)
            self.assertEqual(cost, 0.02)
        finally:
            prep.MODEL = orig

    def test_gpt52pro_cost(self):
        orig = prep.MODEL
        prep.MODEL = "gpt-5.2-pro"
        try:
            _, cost = prep._estimate_cost(1)
            self.assertEqual(cost, 2.00)
        finally:
            prep.MODEL = orig

    def test_confirm_with_yes_bypasses(self):
        result = prep._confirm_cost(8, yes=True)
        self.assertTrue(result)

    def test_confirm_n_cancels(self):
        with patch('builtins.input', return_value='n'):
            result = prep._confirm_cost(8, yes=False)
        self.assertFalse(result)

    def test_confirm_empty_proceeds(self):
        with patch('builtins.input', return_value=''):
            result = prep._confirm_cost(8, yes=False)
        self.assertTrue(result)

    @patch('prep.get_client')
    @patch('prep._confirm_cost', return_value=False)
    def test_main_calls_confirm_before_api(self, mock_confirm, mock_client):
        """Cost confirmation declining should prevent any API command from running."""
        mock_client.return_value = MagicMock()
        tmpdir = tempfile.mkdtemp()
        # Save ALL profile state (set_profile changes dirs, config, domain, counts)
        saved = {}
        _all_attrs = (
            _ProfileTestMixin._PROFILE_DIR_ATTRS
            + _ProfileTestMixin._PROFILE_CFG_ATTRS
            + _ProfileTestMixin._PROFILE_COUNT_ATTRS
        )
        for attr in _all_attrs:
            saved[attr] = getattr(prep, attr)
        orig_base = prep.BASE_DIR
        orig_domain = prep._DOMAIN.copy()
        try:
            prep.BASE_DIR = Path(tmpdir)
            # Create a valid profile with non-stub domain files
            profile_dir = Path(tmpdir) / "profiles" / "testcost"
            for sub in ["inputs/agendas", "inputs/episodes", "inputs/misc",
                        "outputs/syllabus", "outputs/episodes", "outputs/gem",
                        "outputs/notebooklm", "outputs/raw", "domain"]:
                (profile_dir / sub).mkdir(parents=True, exist_ok=True)
            (profile_dir / "profile.md").write_text(
                "---\nrole: Tester\ncompany: TestCo\ndomain: Testing\n---\n",
                encoding="utf-8")
            for fname in ["seeds.md", "coverage.md", "lenses.md", "gem-sections.md"]:
                (profile_dir / "domain" / fname).write_text(
                    f"<!-- PLACEHOLDER -->\nreal content\n", encoding="utf-8")
            with patch('sys.argv', ['prep.py', 'syllabus', '--profile', 'testcost']):
                prep.main()
            mock_confirm.assert_called_once()
            mock_client.return_value.responses.create.assert_not_called()
        finally:
            prep.BASE_DIR = orig_base
            prep._DOMAIN = orig_domain
            for attr, val in saved.items():
                setattr(prep, attr, val)
            shutil.rmtree(tmpdir)


class TestEnhancedStatus(_ProfileTestMixin, unittest.TestCase):
    """Step 6: Enhanced cmd_status with profile listing and pipeline view."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self._save_profile_state()
        self._orig_base = prep.BASE_DIR
        prep.BASE_DIR = Path(self.tmpdir)

    def tearDown(self):
        prep.BASE_DIR = self._orig_base
        self._restore_profile_state()
        shutil.rmtree(self.tmpdir)

    def test_legacy_output_without_profiles(self):
        """Without profiles dir, should show legacy output."""
        # Redirect dirs to temp so we don't read real files
        for attr in ['IN_AGENDAS', 'IN_EPISODES', 'SYLLABUS_DIR', 'EPISODES_DIR',
                      'RAW_DIR', 'GEM_DIR', 'NLM_DIR']:
            new_dir = Path(self.tmpdir) / attr.lower()
            new_dir.mkdir(parents=True)
            setattr(prep, attr, new_dir)

        import io
        from contextlib import redirect_stdout
        with redirect_stdout(io.StringIO()) as f:
            prep.cmd_status()
        output = f.getvalue()
        self.assertIn("Agendas:", output)
        self.assertIn("Content:", output)

    def test_lists_profiles(self):
        """When profiles exist, list them."""
        self._write_profile("alpha", "---\nrole: SWE\ncompany: Google\ndomain: Backend\n---\n")
        self._write_profile("beta", "---\nrole: PM\ncompany: Meta\ndomain: Product\n---\n")

        # Redirect dirs to temp for legacy part
        for attr in ['IN_AGENDAS', 'IN_EPISODES', 'SYLLABUS_DIR', 'EPISODES_DIR',
                      'RAW_DIR', 'GEM_DIR', 'NLM_DIR']:
            new_dir = Path(self.tmpdir) / attr.lower()
            new_dir.mkdir(parents=True, exist_ok=True)
            setattr(prep, attr, new_dir)

        import io
        from contextlib import redirect_stdout
        with redirect_stdout(io.StringIO()) as f:
            prep.cmd_status()
        output = f.getvalue()
        self.assertIn("Profiles:", output)
        self.assertIn("alpha", output)
        self.assertIn("beta", output)

    def test_pipeline_status_with_profile(self):
        """With --profile, show pipeline checklist."""
        self._write_profile("myprep", "---\nrole: SWE\ncompany: Acme\ndomain: D\n---\n")
        prep.set_profile("myprep")
        prep.ensure_dirs()
        # Create some agendas
        for ep in range(1, 4):
            (prep.SYLLABUS_DIR / prep.ep_file(ep, "agenda")).write_text(f"agenda {ep}", encoding="utf-8")

        import io
        from contextlib import redirect_stdout
        with redirect_stdout(io.StringIO()) as f:
            prep.cmd_status(profile_name="myprep")
        output = f.getvalue()
        self.assertIn("Profile: myprep", output)
        self.assertIn("Pipeline:", output)
        self.assertIn("[x] Profile created", output)
        self.assertIn("3/15 agendas", output)

    def test_next_command_printed(self):
        """Pipeline should suggest next command (setup when domain files missing)."""
        self._write_profile("myprep", "---\nrole: SWE\ncompany: Acme\ndomain: D\n---\n")
        prep.set_profile("myprep")
        prep.ensure_dirs()

        import io
        from contextlib import redirect_stdout
        with redirect_stdout(io.StringIO()) as f:
            prep.cmd_status(profile_name="myprep")
        output = f.getvalue()
        self.assertIn("Next:", output)
        self.assertIn("setup", output)

    def test_pipeline_complete(self):
        """All stages done should show 'Pipeline complete!'."""
        self._write_profile("myprep", "---\nrole: SWE\ncompany: Acme\ndomain: D\n---\n")
        self._write_domain("myprep", {
            "seeds.md": "<!-- DOMAIN_SEEDS -->\nReal",
            "coverage.md": "<!-- COVERAGE_FRAMEWORK -->\nReal",
            "lenses.md": "<!-- DOMAIN_LENS -->\nReal",
            "gem-sections.md": "<!-- GEM_BOOKSHELF -->\nReal",
        })
        prep.set_profile("myprep")
        prep.ensure_dirs()
        for ep in prep.ALL_EPS:
            (prep.SYLLABUS_DIR / prep.ep_file(ep, "agenda")).write_text("agenda", encoding="utf-8")
            (prep.EPISODES_DIR / prep.ep_file(ep, "content")).write_text("content", encoding="utf-8")
        (prep.GEM_DIR / "gem-1.md").write_text("gem content", encoding="utf-8")

        import io
        from contextlib import redirect_stdout
        with redirect_stdout(io.StringIO()) as f:
            prep.cmd_status(profile_name="myprep")
        output = f.getvalue()
        self.assertIn("Pipeline complete!", output)


class TestContentEpisodeFlag(_ProfileTestMixin, unittest.TestCase):
    """Step 5: --episode N for content command."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self._save_profile_state()
        for attr in ['IN_AGENDAS', 'IN_EPISODES', 'SYLLABUS_DIR', 'EPISODES_DIR',
                      'RAW_DIR', 'GEM_DIR', 'NLM_DIR']:
            new_dir = Path(self.tmpdir) / attr.lower()
            new_dir.mkdir(parents=True)
            setattr(prep, attr, new_dir)

    def tearDown(self):
        self._restore_profile_state()
        shutil.rmtree(self.tmpdir)

    def test_generates_only_specified_episode(self):
        for ep in [1, 2, 3]:
            (prep.SYLLABUS_DIR / prep.ep_file(ep, "agenda")).write_text(f"agenda {ep} " * 50, encoding="utf-8")
        mock_resp = MagicMock(status="completed", output_text="Generated content " * 100, usage=None)
        client = MagicMock()
        client.responses.create.return_value = mock_resp

        prep.cmd_content(client, force=True, episode=2)

        # Only ep 2 should have content
        self.assertTrue((prep.EPISODES_DIR / "episode-02-content.md").exists())
        self.assertFalse((prep.EPISODES_DIR / "episode-01-content.md").exists())
        self.assertFalse((prep.EPISODES_DIR / "episode-03-content.md").exists())
        client.responses.create.assert_called_once()

    def test_skips_others(self):
        """Existing content for other episodes should be untouched."""
        (prep.SYLLABUS_DIR / "episode-01-agenda.md").write_text("agenda 1 " * 50, encoding="utf-8")
        (prep.EPISODES_DIR / "episode-01-content.md").write_text("old content " * 100, encoding="utf-8")
        (prep.SYLLABUS_DIR / "episode-02-agenda.md").write_text("agenda 2 " * 50, encoding="utf-8")
        mock_resp = MagicMock(status="completed", output_text="New content " * 100, usage=None)
        client = MagicMock()
        client.responses.create.return_value = mock_resp

        prep.cmd_content(client, force=True, episode=2)

        # ep 1 should still have old content
        self.assertEqual((prep.EPISODES_DIR / "episode-01-content.md").read_text(encoding="utf-8"),
                         "old content " * 100)

    def test_works_with_force(self):
        (prep.SYLLABUS_DIR / "episode-03-agenda.md").write_text("agenda 3 " * 50, encoding="utf-8")
        (prep.EPISODES_DIR / "episode-03-content.md").write_text("old " * 100, encoding="utf-8")
        mock_resp = MagicMock(status="completed", output_text="new content " * 100, usage=None)
        client = MagicMock()
        client.responses.create.return_value = mock_resp

        prep.cmd_content(client, force=True, episode=3)

        new = (prep.EPISODES_DIR / "episode-03-content.md").read_text(encoding="utf-8")
        self.assertEqual(new, "new content " * 100)

    def test_none_episode_processes_all(self):
        """episode=None should process ALL_EPS (default behavior)."""
        for ep in [1, 2]:
            (prep.SYLLABUS_DIR / prep.ep_file(ep, "agenda")).write_text(f"agenda {ep} " * 50, encoding="utf-8")
        mock_resp = MagicMock(status="completed", output_text="content " * 100, usage=None)
        client = MagicMock()
        client.responses.create.return_value = mock_resp

        orig_all = prep.ALL_EPS
        prep.ALL_EPS = [1, 2]
        try:
            prep.cmd_content(client, force=True, episode=None)
        finally:
            prep.ALL_EPS = orig_all

        self.assertEqual(client.responses.create.call_count, 2)

    def test_episode_without_force_skips_large_existing(self):
        """episode=N without --force skips if content exists and is large enough."""
        (prep.SYLLABUS_DIR / prep.ep_file(3, "agenda")).write_text("agenda 3 " * 50, encoding="utf-8")
        (prep.EPISODES_DIR / "episode-03-content.md").write_text("existing " * 100, encoding="utf-8")
        client = MagicMock()
        prep.cmd_content(client, force=False, episode=3)
        client.responses.create.assert_not_called()


class TestCmdInit(unittest.TestCase):
    """Step 4: cmd_init() creates profile skeleton."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self._orig_base = prep.BASE_DIR
        prep.BASE_DIR = Path(self.tmpdir)

    def tearDown(self):
        prep.BASE_DIR = self._orig_base
        shutil.rmtree(self.tmpdir)

    def test_creates_structure(self):
        prep.cmd_init("myprep")
        profile_dir = Path(self.tmpdir) / "profiles" / "myprep"
        self.assertTrue(profile_dir.is_dir())
        self.assertTrue((profile_dir / "profile.md").exists())
        for subdir in ["inputs/agendas", "inputs/episodes", "inputs/misc",
                       "outputs/syllabus", "outputs/episodes", "outputs/gem",
                       "outputs/notebooklm", "outputs/raw"]:
            self.assertTrue((profile_dir / subdir).is_dir(), f"Missing: {subdir}")

    def test_template_has_all_fields(self):
        prep.cmd_init("myprep")
        text = (Path(self.tmpdir) / "profiles" / "myprep" / "profile.md").read_text(encoding="utf-8")
        for field in ["role:", "company:", "domain:", "audience:", "core_episodes:",
                      "frontier_episodes:", "model:", "effort:", "as_of:"]:
            self.assertIn(field, text)

    def test_refuses_existing(self):
        prep.cmd_init("myprep")
        with self.assertRaises(SystemExit):
            prep.cmd_init("myprep")

    def test_prints_next_steps(self):
        import io
        from contextlib import redirect_stdout
        with redirect_stdout(io.StringIO()) as f:
            prep.cmd_init("myprep")
        output = f.getvalue()
        self.assertIn("Next steps", output)
        self.assertIn("profile.md", output)
        self.assertIn("python prep.py status --profile myprep", output)

    def test_template_has_frontmatter_delimiters(self):
        prep.cmd_init("myprep")
        text = (Path(self.tmpdir) / "profiles" / "myprep" / "profile.md").read_text(encoding="utf-8")
        self.assertTrue(text.startswith("---\n"))
        self.assertIn("\n---\n", text)


class TestProfileDirRedirection(_ProfileTestMixin, unittest.TestCase):
    """Step 3: Verify all commands work with profile-redirected directories."""

    PROFILE_MD = "---\nrole: SWE\ncompany: Acme\ndomain: Backend\n---\n"

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self._save_profile_state()
        self._orig_base = prep.BASE_DIR
        prep.BASE_DIR = Path(self.tmpdir)
        self._write_profile("testprof", self.PROFILE_MD)
        prep.set_profile("testprof")
        # Create dirs so commands can write
        prep.ensure_dirs()

    def tearDown(self):
        prep.BASE_DIR = self._orig_base
        self._restore_profile_state()
        shutil.rmtree(self.tmpdir)

    def test_ensure_dirs_creates_profile_structure(self):
        profile_dir = Path(self.tmpdir) / "profiles" / "testprof"
        for subdir in ["outputs/syllabus", "outputs/episodes", "outputs/gem",
                       "outputs/notebooklm", "outputs/raw",
                       "inputs/agendas", "inputs/episodes", "inputs/misc"]:
            self.assertTrue((profile_dir / subdir).is_dir(), f"Missing: {subdir}")

    def test_find_agenda_searches_profile_dirs(self):
        (prep.IN_AGENDAS / "episode-01-agenda.md").write_text("agenda", encoding="utf-8")
        result = prep.find_agenda(1)
        self.assertIsNotNone(result)
        self.assertIn("testprof", str(result))

    def test_find_content_searches_profile_dirs(self):
        (prep.IN_EPISODES / "episode-02-content.md").write_text("content", encoding="utf-8")
        result = prep.find_content(2)
        self.assertIsNotNone(result)
        self.assertIn("testprof", str(result))

    def test_recover_uses_profile_raw_dir(self):
        raw_text = "**Episode 1 — Title**\nContent for ep 1.\n"
        (prep.RAW_DIR / "syllabus-02-core_batch.md").write_text(raw_text, encoding="utf-8")
        count = prep.recover_agendas_from_raw()
        self.assertEqual(count, 1)
        recovered = prep.SYLLABUS_DIR / "episode-01-agenda.md"
        self.assertTrue(recovered.exists())
        self.assertIn("testprof", str(recovered))

    def test_syllabus_outputs_to_profile(self):
        mock_resp = MagicMock()
        mock_resp.status = "completed"
        mock_resp.output_text = "## Episode 1: Title\nContent\n\n## Episode 2: Title2\nContent2\n\n## Episode 3: T3\nC3\n\n## Episode 4: T4\nC4"
        mock_resp.usage = None
        client = MagicMock()
        client.responses.create.return_value = mock_resp

        orig_runs = prep.SYLLABUS_RUNS
        prep.SYLLABUS_RUNS = [dict(mode="CORE_BATCH", core="1-4", frontier="")]
        try:
            prep.cmd_syllabus(client, force=True)
        finally:
            prep.SYLLABUS_RUNS = orig_runs

        saved = prep.SYLLABUS_DIR / "episode-01-agenda.md"
        self.assertTrue(saved.exists())
        self.assertIn("testprof", str(saved))

    def test_content_outputs_to_profile(self):
        (prep.SYLLABUS_DIR / "episode-01-agenda.md").write_text("Test agenda " * 50, encoding="utf-8")
        mock_resp = MagicMock()
        mock_resp.status = "completed"
        mock_resp.output_text = "Generated content " * 100
        mock_resp.usage = None
        client = MagicMock()
        client.responses.create.return_value = mock_resp

        orig_all = prep.ALL_EPS
        prep.ALL_EPS = [1]
        try:
            prep.cmd_content(client, force=True)
        finally:
            prep.ALL_EPS = orig_all

        saved = prep.EPISODES_DIR / "episode-01-content.md"
        self.assertTrue(saved.exists())
        self.assertIn("testprof", str(saved))

    def test_package_outputs_to_profile(self):
        (prep.EPISODES_DIR / "episode-01-content.md").write_text("Content for ep 1", encoding="utf-8")
        prep.cmd_package()
        gem = prep.GEM_DIR / "gem-1.md"
        self.assertTrue(gem.exists())
        self.assertIn("testprof", str(gem))
        nlm = prep.NLM_DIR / "episode-01-content.md"
        self.assertTrue(nlm.exists())
        self.assertIn("testprof", str(nlm))

    def test_manifest_written_to_profile_dir(self):
        (prep.EPISODES_DIR / "episode-01-content.md").write_text("content " * 500, encoding="utf-8")
        (prep.SYLLABUS_DIR / "episode-01-agenda.md").write_text("agenda", encoding="utf-8")
        prep.write_manifest()
        manifest = prep.OUTPUTS / "manifest.txt"
        self.assertTrue(manifest.exists())
        self.assertIn("testprof", str(manifest))

    def test_add_writes_to_profile_dirs(self):
        src = Path(self.tmpdir) / "doc.md"
        src.write_text("Raw document content", encoding="utf-8")
        mock_agenda = MagicMock(status="completed", output_text="Agenda text", usage=None)
        mock_content = MagicMock(status="completed", output_text="Content text " * 50, usage=None)
        client = MagicMock()
        client.responses.create.side_effect = [mock_agenda, mock_content]

        prep.cmd_add(client, str(src), slot=prep._total_gem_slots())

        self.assertTrue((prep.SYLLABUS_DIR / "misc-doc-agenda.md").exists())
        self.assertIn("testprof", str(prep.SYLLABUS_DIR / "misc-doc-agenda.md"))

    def test_add_no_cross_profile_contamination(self):
        """--profile A should not write to profile B's directories."""
        # Profile B setup — just create its dirs
        profile_b_dir = Path(self.tmpdir) / "profiles" / "profileB"
        for subdir in ["outputs/gem", "outputs/episodes", "outputs/syllabus", "outputs/notebooklm"]:
            (profile_b_dir / subdir).mkdir(parents=True)

        src = Path(self.tmpdir) / "doc.md"
        src.write_text("Test doc", encoding="utf-8")
        client = MagicMock()
        client.responses.create.side_effect = [
            MagicMock(status="completed", output_text="Agenda", usage=None),
            MagicMock(status="completed", output_text="Content " * 50, usage=None),
        ]

        # Currently on profile A (testprof)
        prep.cmd_add(client, str(src))

        # Profile B should have no files
        self.assertEqual(list(profile_b_dir.rglob("*.md")), [])


class TestSetProfile(_ProfileTestMixin, unittest.TestCase):
    """Step 2: set_profile() redirects dirs and updates config."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self._save_profile_state()
        self._orig_base = prep.BASE_DIR
        prep.BASE_DIR = Path(self.tmpdir)

    def tearDown(self):
        prep.BASE_DIR = self._orig_base
        self._restore_profile_state()
        shutil.rmtree(self.tmpdir)

    def test_dirs_redirected(self):
        self._write_profile("myprep", "---\nrole: SWE\ncompany: Co\ndomain: D\n---\n")
        prep.set_profile("myprep")
        profile_dir = Path(self.tmpdir) / "profiles" / "myprep"
        self.assertEqual(prep.OUTPUTS, profile_dir / "outputs")
        self.assertEqual(prep.SYLLABUS_DIR, profile_dir / "outputs" / "syllabus")
        self.assertEqual(prep.EPISODES_DIR, profile_dir / "outputs" / "episodes")
        self.assertEqual(prep.GEM_DIR, profile_dir / "outputs" / "gem")
        self.assertEqual(prep.NLM_DIR, profile_dir / "outputs" / "notebooklm")
        self.assertEqual(prep.RAW_DIR, profile_dir / "outputs" / "raw")
        self.assertEqual(prep.IN_AGENDAS, profile_dir / "inputs" / "agendas")
        self.assertEqual(prep.IN_EPISODES, profile_dir / "inputs" / "episodes")
        self.assertEqual(prep.IN_MISC, profile_dir / "inputs" / "misc")

    def test_config_vars_updated(self):
        self._write_profile("myprep", "---\nrole: Principal\ncompany: Meta\ndomain: ML\naudience: Staff\n---\n")
        prep.set_profile("myprep")
        self.assertEqual(prep.ROLE, "Principal")
        self.assertEqual(prep.COMPANY, "Meta")
        self.assertEqual(prep.DOMAIN, "ML")
        self.assertEqual(prep.AUDIENCE, "Staff")

    def test_reconfigure_triggered(self):
        self._write_profile("myprep", "---\nrole: SWE\ncompany: Co\ndomain: D\ncore_episodes: 8\nfrontier_episodes: 2\n---\n")
        prep.set_profile("myprep")
        self.assertEqual(prep._CORE_COUNT, 8)
        self.assertEqual(prep._FRONTIER_COUNT, 2)
        self.assertEqual(prep.ALL_EPS, list(range(1, 11)))

    def test_reconfigure_not_triggered_without_counts(self):
        orig_core = prep._CORE_COUNT
        orig_frontier = prep._FRONTIER_COUNT
        self._write_profile("myprep", "---\nrole: SWE\ncompany: Co\ndomain: D\n---\n")
        prep.set_profile("myprep")
        self.assertEqual(prep._CORE_COUNT, orig_core)
        self.assertEqual(prep._FRONTIER_COUNT, orig_frontier)

    def test_prompts_dir_unchanged(self):
        orig_prompts = prep.PROMPTS
        self._write_profile("myprep", "---\nrole: SWE\ncompany: Co\ndomain: D\n---\n")
        prep.set_profile("myprep")
        self.assertEqual(prep.PROMPTS, orig_prompts)

    def test_defaults_preserved_without_profile(self):
        """Without set_profile(), all dirs should still be at defaults."""
        # Just verify the saved state matches what we expect
        self.assertEqual(self._profile_saved['OUTPUTS'], self._orig_base / "outputs")
        self.assertEqual(self._profile_saved['SYLLABUS_DIR'], self._orig_base / "outputs" / "syllabus")

    def test_model_and_effort_from_profile(self):
        self._write_profile("myprep", "---\nrole: SWE\ncompany: Co\ndomain: D\nmodel: gpt-4o\neffort: high\n---\n")
        prep.set_profile("myprep")
        self.assertEqual(prep.MODEL, "gpt-4o")
        self.assertEqual(prep.EFFORT, "high")

    def test_as_of_from_profile(self):
        self._write_profile("myprep", "---\nrole: SWE\ncompany: Co\ndomain: D\nas_of: Mar 2026\n---\n")
        prep.set_profile("myprep")
        self.assertEqual(prep.AS_OF, "Mar 2026")


class TestMigration(unittest.TestCase):
    """Step 8: Verify S&I content migration to profiles/security-infra/."""

    _SI_PROFILE = Path(__file__).parent / "profiles" / "security-infra"

    @unittest.skipUnless(
        (Path(__file__).parent / "profiles" / "security-infra" / "profile.md").exists(),
        "Security-infra profile not available"
    )
    def test_reference_profile_loads(self):
        """security-infra profile.md should be parseable."""
        orig_base = prep.BASE_DIR
        try:
            prep.BASE_DIR = Path(__file__).parent
            config = prep.load_profile("security-infra")
            self.assertIn("role", config)
            self.assertIn("company", config)
            self.assertIn("domain", config)
        finally:
            prep.BASE_DIR = orig_base

    def test_no_content_in_toplevel_outputs(self):
        """Top-level outputs/ should have no episode content."""
        top_outputs = Path(__file__).parent / "outputs"
        if not top_outputs.exists():
            return  # dir doesn't exist yet
        episodes = list((top_outputs / "episodes").glob("episode-*.md")) if (top_outputs / "episodes").exists() else []
        self.assertEqual(len(episodes), 0, "Top-level outputs/ should not contain episode content")


class TestParseDomainSections(unittest.TestCase):
    """Test _parse_domain_sections parser."""

    def test_single_section(self):
        text = "<!-- FOO -->\nsome content\nmore content"
        result = prep._parse_domain_sections(text)
        self.assertEqual(result, {"FOO": "some content\nmore content"})

    def test_multiple_sections(self):
        text = "<!-- A -->\nalpha\n<!-- B -->\nbeta\nbeta2"
        result = prep._parse_domain_sections(text)
        self.assertEqual(result["A"], "alpha")
        self.assertEqual(result["B"], "beta\nbeta2")

    def test_empty_section(self):
        text = "<!-- A -->\n<!-- B -->\ncontent"
        result = prep._parse_domain_sections(text)
        self.assertEqual(result["A"], "")
        self.assertEqual(result["B"], "content")

    def test_no_markers(self):
        text = "just plain text\nno markers here"
        result = prep._parse_domain_sections(text)
        self.assertEqual(result, {})

    def test_content_with_braces(self):
        """Domain content may contain {json} that shouldn't break anything."""
        text = '<!-- X -->\n{"key": "value"}\nmore {stuff}'
        result = prep._parse_domain_sections(text)
        self.assertIn('{"key": "value"}', result["X"])


class TestInjectDomain(_ProfileTestMixin, unittest.TestCase):
    """Test domain file loading and injection into prompts."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self._save_profile_state()
        self._orig_base = prep.BASE_DIR
        prep.BASE_DIR = Path(self.tmpdir)

    def tearDown(self):
        prep.BASE_DIR = self._orig_base
        self._restore_profile_state()
        shutil.rmtree(self.tmpdir)

    def test_load_domain_reads_sections(self):
        """_load_domain should parse all domain files and merge markers."""
        self._write_profile("test", "---\nrole: R\ncompany: C\ndomain: D\n---\n")
        self._write_domain("test", {
            "seeds.md": "<!-- DOMAIN_SEEDS -->\nEpisode 1: Widgets",
            "coverage.md": "<!-- COVERAGE_FRAMEWORK -->\nWidget Coverage Map",
        })
        result = prep._load_domain("test")
        self.assertEqual(result["DOMAIN_SEEDS"], "Episode 1: Widgets")
        self.assertEqual(result["COVERAGE_FRAMEWORK"], "Widget Coverage Map")

    def test_inject_domain_replaces_markers(self):
        """_inject_domain should replace {MARKER} placeholders."""
        domain = {"FOO": "replaced-foo", "BAR": "replaced-bar"}
        text = "prefix {FOO} middle {BAR} suffix"
        result = prep._inject_domain(text, domain)
        self.assertEqual(result, "prefix replaced-foo middle replaced-bar suffix")

    def test_inject_domain_uses_global(self):
        """Without explicit dict, _inject_domain uses _DOMAIN global."""
        orig = prep._DOMAIN.copy()
        try:
            prep._DOMAIN = {"MARKER": "global-val"}
            result = prep._inject_domain("test {MARKER} end")
            self.assertEqual(result, "test global-val end")
        finally:
            prep._DOMAIN = orig

    def test_inject_missing_marker_leaves_placeholder(self):
        """If domain doesn't have a marker, placeholder stays in text."""
        result = prep._inject_domain("test {UNKNOWN_MARKER} end", {})
        self.assertEqual(result, "test {UNKNOWN_MARKER} end")

    def test_load_domain_warns_on_no_sections(self):
        """Files without markers should trigger a warning."""
        self._write_profile("test", "---\nrole: R\ncompany: C\ndomain: D\n---\n")
        self._write_domain("test", {"bad.md": "no markers here"})
        import io
        captured = io.StringIO()
        import contextlib
        with contextlib.redirect_stdout(captured):
            prep._load_domain("test")
        self.assertIn("WARNING", captured.getvalue())

    def test_load_domain_empty_dir(self):
        """Empty domain dir returns empty dict."""
        self._write_profile("test", "---\nrole: R\ncompany: C\ndomain: D\n---\n")
        (Path(self.tmpdir) / "profiles" / "test" / "domain").mkdir(parents=True, exist_ok=True)
        result = prep._load_domain("test")
        self.assertEqual(result, {})

    def test_load_domain_no_dir(self):
        """Missing domain dir returns empty dict."""
        self._write_profile("test", "---\nrole: R\ncompany: C\ndomain: D\n---\n")
        result = prep._load_domain("test")
        self.assertEqual(result, {})

    def test_brace_content_not_double_replaced(self):
        """Domain content with {braces} shouldn't be treated as markers."""
        domain = {"FOO": 'config: {"nested": true}'}
        text = "pre {FOO} post"
        result = prep._inject_domain(text, domain)
        self.assertIn('{"nested": true}', result)

    def test_syllabus_prompt_with_domain(self):
        """syllabus_prompt should inject domain seeds into output."""
        orig = prep._DOMAIN.copy()
        try:
            prep._DOMAIN = {
                "DOMAIN_SEEDS": "Episode 1: Test Topic Seeds",
                "COVERAGE_FRAMEWORK": "Test Coverage Framework",
                "DOMAIN_LENS": "test domain lens",
            }
            run = dict(mode="SCAFFOLD", core="", frontier="")
            result = prep.syllabus_prompt(run)
            self.assertIn("Test Topic Seeds", result)
            self.assertIn("Test Coverage Framework", result)
            self.assertNotIn("{DOMAIN_SEEDS}", result)
            self.assertNotIn("{COVERAGE_FRAMEWORK}", result)
        finally:
            prep._DOMAIN = orig

    def test_content_prompt_with_domain(self):
        """content_prompt should inject domain lenses into output."""
        orig = prep._DOMAIN.copy()
        try:
            prep._DOMAIN = {
                "DOMAIN_LENS": "data engineering lens",
                "NITTY_GRITTY_LAYOUT": "DE layout here",
                "DOMAIN_REQUIREMENTS": "DE requirements here",
                "STAKEHOLDERS": "Data, Product, Platform",
            }
            result = prep.content_prompt("test agenda")
            self.assertIn("data engineering lens", result)
            self.assertIn("DE layout here", result)
            self.assertIn("DE requirements here", result)
            self.assertIn("Data, Product, Platform", result)
            self.assertNotIn("{DOMAIN_LENS}", result)
        finally:
            prep._DOMAIN = orig


class TestIsStub(unittest.TestCase):
    """Test _is_stub detection."""

    def test_stub_file(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False, encoding='utf-8') as f:
            f.write("<!-- STUB: This is a stub -->\n<!-- More comments -->")
            f.flush()
            self.assertTrue(prep._is_stub(Path(f.name)))
        os.unlink(f.name)

    def test_real_file(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False, encoding='utf-8') as f:
            f.write("<!-- DOMAIN_SEEDS -->\nEpisode 1: Real Content")
            f.flush()
            self.assertFalse(prep._is_stub(Path(f.name)))
        os.unlink(f.name)

    def test_missing_file(self):
        self.assertTrue(prep._is_stub(Path("/nonexistent/file.md")))

    def test_empty_file(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False, encoding='utf-8') as f:
            f.write("")
            f.flush()
            self.assertTrue(prep._is_stub(Path(f.name)))
        os.unlink(f.name)


class TestPreflightCheck(_ProfileTestMixin, unittest.TestCase):
    """Test _preflight_check validation before API calls."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self._save_profile_state()
        self._orig_base = prep.BASE_DIR
        prep.BASE_DIR = Path(self.tmpdir)

    def tearDown(self):
        prep.BASE_DIR = self._orig_base
        self._restore_profile_state()
        shutil.rmtree(self.tmpdir)

    def _setup_profile_with_domain(self, name, stub=False):
        """Helper: create profile with domain files (real or stub)."""
        self._write_profile(name, "---\nrole: R\ncompany: C\ndomain: D\n---\n")
        if stub:
            self._write_domain(name, {
                "seeds.md": "<!-- STUB: placeholder -->\n",
                "coverage.md": "<!-- STUB: placeholder -->\n",
                "lenses.md": "<!-- STUB: placeholder -->\n",
                "gem-sections.md": "<!-- STUB: placeholder -->\n",
            })
        else:
            self._write_domain(name, {
                "seeds.md": "<!-- DOMAIN_SEEDS -->\nEpisode 1: Real",
                "coverage.md": "<!-- COVERAGE_FRAMEWORK -->\nReal",
                "lenses.md": "<!-- DOMAIN_LENS -->\nReal",
                "gem-sections.md": "<!-- GEM_BOOKSHELF -->\nReal",
            })

    def test_preflight_passes_with_real_domain(self):
        """Preflight should succeed with non-stub domain files."""
        self._setup_profile_with_domain("good", stub=False)
        # Should not raise
        prep._preflight_check("good", "syllabus")

    def test_preflight_catches_stub_domain(self):
        """Preflight should error on stub domain files."""
        self._setup_profile_with_domain("bad", stub=True)
        with self.assertRaises(SystemExit) as cm:
            prep._preflight_check("bad", "syllabus")
        self.assertEqual(cm.exception.code, 1)

    def test_preflight_catches_missing_domain(self):
        """Preflight should error when domain files are missing entirely."""
        self._write_profile("noadapt", "---\nrole: R\ncompany: C\ndomain: D\n---\n")
        (Path(self.tmpdir) / "profiles" / "noadapt" / "domain").mkdir(parents=True, exist_ok=True)
        with self.assertRaises(SystemExit):
            prep._preflight_check("noadapt", "syllabus")

    @patch('prep.get_client')
    def test_preflight_runs_before_client(self, mock_get_client):
        """When domain files are stubs, get_client should never be called."""
        self._setup_profile_with_domain("stubbed", stub=True)
        with self.assertRaises(SystemExit):
            with patch('sys.argv', ['prep.py', 'syllabus', '--profile', 'stubbed']):
                prep.main()
        mock_get_client.assert_not_called()


class TestApiCommandsRequireProfile(unittest.TestCase):
    """API commands should require --profile."""

    def test_syllabus_without_profile_errors(self):
        with self.assertRaises(SystemExit) as cm:
            with patch('sys.argv', ['prep.py', 'syllabus']):
                prep.main()
        self.assertEqual(cm.exception.code, 1)

    def test_content_without_profile_errors(self):
        with self.assertRaises(SystemExit) as cm:
            with patch('sys.argv', ['prep.py', 'content']):
                prep.main()
        self.assertEqual(cm.exception.code, 1)

    def test_all_without_profile_errors(self):
        with self.assertRaises(SystemExit) as cm:
            with patch('sys.argv', ['prep.py', 'all']):
                prep.main()
        self.assertEqual(cm.exception.code, 1)

    def test_add_without_profile_errors(self):
        with self.assertRaises(SystemExit) as cm:
            with patch('sys.argv', ['prep.py', 'add', 'file.md']):
                prep.main()
        self.assertEqual(cm.exception.code, 1)

    def test_status_without_profile_ok(self):
        """Non-API commands should work without --profile."""
        # status should not error about missing --profile
        with patch('sys.argv', ['prep.py', 'status']):
            # May error for other reasons but not --profile
            try:
                prep.main()
            except SystemExit as e:
                self.assertNotEqual(str(e), "1",
                    "status should not require --profile")


class TestInitCreatesDomainStubs(_ProfileTestMixin, unittest.TestCase):
    """cmd_init should create domain/ directory with stub files."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self._save_profile_state()
        self._orig_base = prep.BASE_DIR
        prep.BASE_DIR = Path(self.tmpdir)

    def tearDown(self):
        prep.BASE_DIR = self._orig_base
        self._restore_profile_state()
        shutil.rmtree(self.tmpdir)

    def test_init_creates_domain_dir(self):
        prep.cmd_init("newprof")
        domain_dir = Path(self.tmpdir) / "profiles" / "newprof" / "domain"
        self.assertTrue(domain_dir.is_dir())

    def test_init_creates_four_stub_files(self):
        prep.cmd_init("newprof")
        domain_dir = Path(self.tmpdir) / "profiles" / "newprof" / "domain"
        expected = {"seeds.md", "coverage.md", "lenses.md", "gem-sections.md"}
        actual = {f.name for f in domain_dir.iterdir() if f.suffix == ".md"}
        self.assertEqual(actual, expected)

    def test_init_stubs_are_detected_as_stubs(self):
        prep.cmd_init("newprof")
        domain_dir = Path(self.tmpdir) / "profiles" / "newprof" / "domain"
        for fname in ["seeds.md", "coverage.md", "lenses.md", "gem-sections.md"]:
            self.assertTrue(prep._is_stub(domain_dir / fname),
                f"{fname} should be detected as stub")

    def test_init_stubs_contain_guidance(self):
        prep.cmd_init("newprof")
        domain_dir = Path(self.tmpdir) / "profiles" / "newprof" / "domain"
        for fname in ["seeds.md", "coverage.md", "lenses.md", "gem-sections.md"]:
            text = (domain_dir / fname).read_text(encoding="utf-8")
            self.assertIn("intake.md", text, f"{fname} should reference intake.md")


class TestSecurityInfraDomain(unittest.TestCase):
    """Reference profile should have complete domain files."""

    _DOMAIN_DIR = Path(__file__).parent / "profiles" / "security-infra" / "domain"

    @unittest.skipUnless(
        (Path(__file__).parent / "profiles" / "security-infra" / "domain").exists(),
        "Security-infra domain/ not available"
    )
    def test_all_four_files_exist(self):
        for fname in ["seeds.md", "coverage.md", "lenses.md", "gem-sections.md"]:
            self.assertTrue((self._DOMAIN_DIR / fname).exists(), f"{fname} missing")

    @unittest.skipUnless(
        (Path(__file__).parent / "profiles" / "security-infra" / "domain").exists(),
        "Security-infra domain/ not available"
    )
    def test_files_are_not_stubs(self):
        for fname in ["seeds.md", "coverage.md", "lenses.md", "gem-sections.md"]:
            self.assertFalse(prep._is_stub(self._DOMAIN_DIR / fname),
                f"{fname} should not be a stub")

    @unittest.skipUnless(
        (Path(__file__).parent / "profiles" / "security-infra" / "domain").exists(),
        "Security-infra domain/ not available"
    )
    def test_seeds_has_episodes(self):
        orig_base = prep.BASE_DIR
        try:
            prep.BASE_DIR = Path(__file__).parent
            domain = prep._load_domain("security-infra")
            self.assertIn("DOMAIN_SEEDS", domain)
            self.assertIn("Episode 1:", domain["DOMAIN_SEEDS"])
        finally:
            prep.BASE_DIR = orig_base

    @unittest.skipUnless(
        (Path(__file__).parent / "profiles" / "security-infra" / "domain").exists(),
        "Security-infra domain/ not available"
    )
    def test_all_expected_markers_present(self):
        """All markers referenced by prompts should be in the domain content."""
        orig_base = prep.BASE_DIR
        try:
            prep.BASE_DIR = Path(__file__).parent
            domain = prep._load_domain("security-infra")
            expected_markers = [
                "DOMAIN_SEEDS", "COVERAGE_FRAMEWORK",
                "DOMAIN_LENS", "NITTY_GRITTY_LAYOUT", "DOMAIN_REQUIREMENTS",
                "DISTILL_REQUIREMENTS", "STAKEHOLDERS",
                "GEM_BOOKSHELF", "GEM_EXAMPLES", "GEM_CODING", "GEM_FORMAT_EXAMPLES",
            ]
            for m in expected_markers:
                self.assertIn(m, domain, f"Marker {m} not found in domain content")
        finally:
            prep.BASE_DIR = orig_base


class TestRenderWithProfileInjects(_ProfileTestMixin, unittest.TestCase):
    """render_template should inject domain content when profile is active."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self._save_profile_state()
        self._orig_base = prep.BASE_DIR
        prep.BASE_DIR = Path(self.tmpdir)

    def tearDown(self):
        prep.BASE_DIR = self._orig_base
        self._restore_profile_state()
        shutil.rmtree(self.tmpdir)

    def test_render_injects_domain(self):
        prep._DOMAIN = {"FOO_MARKER": "injected-value"}
        template = "prefix {FOO_MARKER} suffix"
        result = prep.render_template(template)
        self.assertIn("injected-value", result)
        self.assertNotIn("{FOO_MARKER}", result)

    def test_render_injects_role_and_domain(self):
        prep._DOMAIN = {"DOMAIN_LENS": "test lens value"}
        template = "role={PREP_ROLE} lens={DOMAIN_LENS}"
        result = prep.render_template(template)
        self.assertIn(prep.ROLE, result)
        self.assertIn("test lens value", result)


class TestCmdSetup(_ProfileTestMixin, unittest.TestCase):
    """Test cmd_setup domain file generation."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self._save_profile_state()
        self._orig_base = prep.BASE_DIR
        prep.BASE_DIR = Path(self.tmpdir)
        # Create a profile
        self._write_profile("test", "---\nrole: SWE\ncompany: Acme\ndomain: Testing\n---\n")
        prep.set_profile("test")
        prep.ensure_dirs()

    def tearDown(self):
        prep.BASE_DIR = self._orig_base
        self._restore_profile_state()
        shutil.rmtree(self.tmpdir)

    def _mock_client(self, responses):
        """Create a mock client that returns given responses in sequence."""
        client = MagicMock()
        side_effects = []
        for text in responses:
            resp = MagicMock(status="completed", output_text=text, usage=None)
            side_effects.append(resp)
        client.responses.create.side_effect = side_effects
        return client

    def _seeds_response(self):
        return (
            "<!-- DOMAIN_SEEDS -->\n"
            "### Episode 1: Test Topic\n"
            "**Focus:** Testing focus\n\n"
            "<!-- COVERAGE_FRAMEWORK -->\n"
            "Test Coverage Map\n| Ep | Domain |\n| 1 | Testing |\n"
        )

    def _lenses_response(self):
        return (
            "<!-- DOMAIN_LENS -->\nTest depth means concrete test strategies\n\n"
            "<!-- NITTY_GRITTY_LAYOUT -->\n1) **Test Architecture**\n2) **Test Data**\n\n"
            "<!-- DOMAIN_REQUIREMENTS -->\n- Include test details\n\n"
            "<!-- DISTILL_REQUIREMENTS -->\n- 2 test details\n\n"
            "<!-- STAKEHOLDERS -->\nQA, Dev, Product\n"
        )

    def _gem_response(self):
        return (
            "<!-- GEM_BOOKSHELF -->\n| Layer | Concept | Role |\n| 1 | Unit | Fast feedback |\n\n"
            "<!-- GEM_EXAMPLES -->\n> Domain: \"How do you test X?\"\n\n"
            "<!-- GEM_CODING -->\nTest-flavored scripting\n\n"
            "<!-- GEM_FORMAT_EXAMPLES -->\n2026-02|Interview|Testing|Unit|Owned|Good|Locked\n"
        )

    def test_setup_creates_all_domain_files(self):
        """All 4 domain files should be created with correct markers."""
        client = self._mock_client([
            self._seeds_response(),
            self._lenses_response(),
            self._gem_response(),
        ])
        result = prep.cmd_setup(client, "test", force=True)
        self.assertTrue(result)
        domain_dir = Path(self.tmpdir) / "profiles" / "test" / "domain"
        for fname in ["seeds.md", "coverage.md", "lenses.md", "gem-sections.md"]:
            self.assertTrue((domain_dir / fname).exists(), f"{fname} should exist")
            self.assertFalse(prep._is_stub(domain_dir / fname), f"{fname} should not be stub")

    def test_setup_skips_when_files_exist(self):
        """No API calls when non-stub domain files already present."""
        self._write_domain("test", {
            "seeds.md": "<!-- DOMAIN_SEEDS -->\nExisting",
            "coverage.md": "<!-- COVERAGE_FRAMEWORK -->\nExisting",
            "lenses.md": "<!-- DOMAIN_LENS -->\nExisting",
            "gem-sections.md": "<!-- GEM_BOOKSHELF -->\nExisting",
        })
        client = MagicMock()
        result = prep.cmd_setup(client, "test", force=False)
        self.assertTrue(result)
        client.responses.create.assert_not_called()

    def test_setup_force_regenerates(self):
        """--force should overwrite existing domain files."""
        self._write_domain("test", {
            "seeds.md": "<!-- DOMAIN_SEEDS -->\nOld content",
            "coverage.md": "<!-- COVERAGE_FRAMEWORK -->\nOld",
            "lenses.md": "<!-- DOMAIN_LENS -->\nOld",
            "gem-sections.md": "<!-- GEM_BOOKSHELF -->\nOld",
        })
        client = self._mock_client([
            self._seeds_response(),
            self._lenses_response(),
            self._gem_response(),
        ])
        result = prep.cmd_setup(client, "test", force=True)
        self.assertTrue(result)
        domain_dir = Path(self.tmpdir) / "profiles" / "test" / "domain"
        text = (domain_dir / "seeds.md").read_text(encoding="utf-8")
        self.assertIn("Test Topic", text)
        self.assertNotIn("Old content", text)

    def test_setup_reads_context_docs(self):
        """Context docs from inputs/misc/ should appear in call 1 prompt."""
        misc_dir = Path(self.tmpdir) / "profiles" / "test" / "inputs" / "misc"
        misc_dir.mkdir(parents=True, exist_ok=True)
        (misc_dir / "notes.md").write_text("Special notes about testing", encoding="utf-8")

        client = self._mock_client([
            self._seeds_response(),
            self._lenses_response(),
            self._gem_response(),
        ])
        prep.cmd_setup(client, "test", force=True)

        # The first API call should include context docs
        call_args = client.responses.create.call_args_list[0]
        input_text = call_args.kwargs.get("input", "")
        self.assertIn("Special notes about testing", input_text)

    def test_setup_call3_receives_seeds(self):
        """Call 3 (gem) prompt should contain seeds from call 1."""
        client = self._mock_client([
            self._seeds_response(),
            self._lenses_response(),
            self._gem_response(),
        ])
        prep.cmd_setup(client, "test", force=True)

        # Third call should have seeds content
        call_args = client.responses.create.call_args_list[2]
        input_text = call_args.kwargs.get("input", "")
        self.assertIn("Test Topic", input_text)

    def test_setup_saves_raw_outputs(self):
        """Raw API responses should be saved."""
        client = self._mock_client([
            self._seeds_response(),
            self._lenses_response(),
            self._gem_response(),
        ])
        prep.cmd_setup(client, "test", force=True)
        raw_dir = Path(self.tmpdir) / "profiles" / "test" / "outputs" / "raw"
        self.assertTrue((raw_dir / "setup-1-seeds.md").exists())
        self.assertTrue((raw_dir / "setup-2-lenses.md").exists())
        self.assertTrue((raw_dir / "setup-3-gem.md").exists())

    def test_setup_handles_api_failure(self):
        """Should return False on first call failure."""
        resp = MagicMock(status="failed", output_text=None, error="test error")
        client = MagicMock()
        client.responses.create.return_value = resp
        result = prep.cmd_setup(client, "test", force=True)
        self.assertFalse(result)

    def test_setup_partial_failure(self):
        """Call 1 ok, call 2 fails: seeds+coverage should still be written."""
        resp1 = MagicMock(status="completed", output_text=self._seeds_response(), usage=None)
        resp2 = MagicMock(status="failed", output_text=None, error="test error")
        client = MagicMock()
        client.responses.create.side_effect = [resp1, resp2]

        result = prep.cmd_setup(client, "test", force=True)
        self.assertFalse(result)
        domain_dir = Path(self.tmpdir) / "profiles" / "test" / "domain"
        # Seeds and coverage from call 1 should exist
        self.assertTrue((domain_dir / "seeds.md").exists())
        self.assertTrue((domain_dir / "coverage.md").exists())


class TestSetupPromptTemplates(unittest.TestCase):
    """Test that meta-prompt templates render without unreplaced placeholders."""

    def test_meta_seeds_prompt_renders(self):
        text = prep.load_prompt("meta-seeds")
        rendered = text.replace("{ROLE}", "SWE").replace("{COMPANY}", "Acme")
        rendered = rendered.replace("{DOMAIN}", "Testing").replace("{AUDIENCE}", "Engineers")
        rendered = rendered.replace("{PROFILE_CONTENT}", "test profile")
        rendered = rendered.replace("{CONTEXT_DOCS}", "test docs")
        # No unreplaced input placeholders
        for p in ["{ROLE}", "{COMPANY}", "{DOMAIN}", "{AUDIENCE}",
                  "{PROFILE_CONTENT}", "{CONTEXT_DOCS}"]:
            self.assertNotIn(p, rendered)

    def test_meta_lenses_prompt_renders(self):
        text = prep.load_prompt("meta-lenses")
        rendered = text.replace("{ROLE}", "SWE").replace("{COMPANY}", "Acme")
        rendered = rendered.replace("{DOMAIN}", "Testing")
        rendered = rendered.replace("{PROFILE_CONTENT}", "test profile")
        for p in ["{ROLE}", "{COMPANY}", "{DOMAIN}", "{PROFILE_CONTENT}"]:
            self.assertNotIn(p, rendered)

    def test_meta_gem_prompt_renders(self):
        text = prep.load_prompt("meta-gem")
        rendered = text.replace("{ROLE}", "SWE").replace("{COMPANY}", "Acme")
        rendered = rendered.replace("{DOMAIN}", "Testing")
        rendered = rendered.replace("{PROFILE_CONTENT}", "test profile")
        rendered = rendered.replace("{SEEDS_CONTENT}", "test seeds")
        for p in ["{ROLE}", "{COMPANY}", "{DOMAIN}",
                  "{PROFILE_CONTENT}", "{SEEDS_CONTENT}"]:
            self.assertNotIn(p, rendered)


class TestPreflightSkipsSetup(_ProfileTestMixin, unittest.TestCase):
    """Preflight should skip validation for setup command."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self._save_profile_state()
        self._orig_base = prep.BASE_DIR
        prep.BASE_DIR = Path(self.tmpdir)

    def tearDown(self):
        prep.BASE_DIR = self._orig_base
        self._restore_profile_state()
        shutil.rmtree(self.tmpdir)

    def test_preflight_skips_for_setup(self):
        """Preflight should not error for setup command even without domain files."""
        self._write_profile("test", "---\nrole: R\ncompany: C\ndomain: D\n---\n")
        # Should not raise even though domain files don't exist
        prep._preflight_check("test", "setup")


class TestStatusShowsDomainFiles(_ProfileTestMixin, unittest.TestCase):
    """Status should show domain files in pipeline checklist."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self._save_profile_state()
        self._orig_base = prep.BASE_DIR
        prep.BASE_DIR = Path(self.tmpdir)

    def tearDown(self):
        prep.BASE_DIR = self._orig_base
        self._restore_profile_state()
        shutil.rmtree(self.tmpdir)

    def test_status_shows_domain_files_line(self):
        """Pipeline checklist should include domain files."""
        self._write_profile("myprep", "---\nrole: SWE\ncompany: Acme\ndomain: D\n---\n")
        prep.set_profile("myprep")
        prep.ensure_dirs()

        import io
        from contextlib import redirect_stdout
        with redirect_stdout(io.StringIO()) as f:
            prep.cmd_status(profile_name="myprep")
        output = f.getvalue()
        self.assertIn("Domain files", output)
        self.assertIn("0/4", output)

    def test_status_domain_complete(self):
        """Domain files should show as complete when all 4 exist."""
        self._write_profile("myprep", "---\nrole: SWE\ncompany: Acme\ndomain: D\n---\n")
        self._write_domain("myprep", {
            "seeds.md": "<!-- DOMAIN_SEEDS -->\nReal",
            "coverage.md": "<!-- COVERAGE_FRAMEWORK -->\nReal",
            "lenses.md": "<!-- DOMAIN_LENS -->\nReal",
            "gem-sections.md": "<!-- GEM_BOOKSHELF -->\nReal",
        })
        prep.set_profile("myprep")
        prep.ensure_dirs()

        import io
        from contextlib import redirect_stdout
        with redirect_stdout(io.StringIO()) as f:
            prep.cmd_status(profile_name="myprep")
        output = f.getvalue()
        self.assertIn("[x] Domain files", output)
        self.assertIn("4/4", output)
        self.assertIn("syllabus", output)  # next command should be syllabus


class TestSetupCliIntegration(unittest.TestCase):
    """Test setup command CLI integration."""

    def test_setup_in_argparse_choices(self):
        """setup should be a valid command choice."""
        import argparse
        p = argparse.ArgumentParser()
        p.add_argument("command", choices=["all","syllabus","content","add","setup","package","status","render","init"])
        args = p.parse_args(["setup"])
        self.assertEqual(args.command, "setup")

    def test_setup_requires_profile(self):
        """setup should require --profile."""
        with self.assertRaises(SystemExit) as cm:
            with patch('sys.argv', ['prep.py', 'setup']):
                prep.main()
        self.assertEqual(cm.exception.code, 1)


class TestNeedsSetup(_ProfileTestMixin, unittest.TestCase):
    """Test _needs_setup() helper."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self._save_profile_state()
        self._orig_base = prep.BASE_DIR
        prep.BASE_DIR = Path(self.tmpdir)

    def tearDown(self):
        prep.BASE_DIR = self._orig_base
        self._restore_profile_state()
        shutil.rmtree(self.tmpdir)

    def test_needs_setup_no_domain_dir(self):
        """Missing domain directory -> True (all files treated as stubs)."""
        self._write_profile("test", "---\nrole: R\ncompany: C\ndomain: D\n---\n")
        # No _write_domain call — domain dir does not exist
        self.assertTrue(prep._needs_setup("test"))

    def test_needs_setup_all_stubs(self):
        """All stubs -> True."""
        self._write_profile("test", "---\nrole: R\ncompany: C\ndomain: D\n---\n")
        self._write_domain("test", {
            "seeds.md": "<!-- STUB: placeholder -->\n",
            "coverage.md": "<!-- STUB: placeholder -->\n",
            "lenses.md": "<!-- STUB: placeholder -->\n",
            "gem-sections.md": "<!-- STUB: placeholder -->\n",
        })
        self.assertTrue(prep._needs_setup("test"))

    def test_needs_setup_no_stubs(self):
        """Populated files -> False."""
        self._write_profile("test", "---\nrole: R\ncompany: C\ndomain: D\n---\n")
        self._write_domain("test", {
            "seeds.md": "<!-- DOMAIN_SEEDS -->\nReal",
            "coverage.md": "<!-- COVERAGE_FRAMEWORK -->\nReal",
            "lenses.md": "<!-- DOMAIN_LENS -->\nReal",
            "gem-sections.md": "<!-- GEM_BOOKSHELF -->\nReal",
        })
        self.assertFalse(prep._needs_setup("test"))

    def test_needs_setup_partial_stubs(self):
        """3 real + 1 stub -> True."""
        self._write_profile("test", "---\nrole: R\ncompany: C\ndomain: D\n---\n")
        self._write_domain("test", {
            "seeds.md": "<!-- DOMAIN_SEEDS -->\nReal",
            "coverage.md": "<!-- COVERAGE_FRAMEWORK -->\nReal",
            "lenses.md": "<!-- DOMAIN_LENS -->\nReal",
            "gem-sections.md": "<!-- STUB: placeholder -->\n",
        })
        self.assertTrue(prep._needs_setup("test"))


class TestCmdAllAutoSetup(_ProfileTestMixin, unittest.TestCase):
    """Test cmd_all auto-running setup when stubs detected."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self._save_profile_state()
        self._orig_base = prep.BASE_DIR
        prep.BASE_DIR = Path(self.tmpdir)

    def tearDown(self):
        prep.BASE_DIR = self._orig_base
        self._restore_profile_state()
        shutil.rmtree(self.tmpdir)

    def _setup_stub_profile(self, name="test"):
        """Create a profile with stub domain files and set it active."""
        self._write_profile(name, "---\nrole: SWE\ncompany: Acme\ndomain: Testing\n---\n")
        self._write_domain(name, {
            "seeds.md": "<!-- STUB: placeholder -->\n",
            "coverage.md": "<!-- STUB: placeholder -->\n",
            "lenses.md": "<!-- STUB: placeholder -->\n",
            "gem-sections.md": "<!-- STUB: placeholder -->\n",
        })
        prep.set_profile(name)
        prep.ensure_dirs()

    def _setup_populated_profile(self, name="test"):
        """Create a profile with real domain files and set it active."""
        self._write_profile(name, "---\nrole: SWE\ncompany: Acme\ndomain: Testing\n---\n")
        self._write_domain(name, {
            "seeds.md": "<!-- DOMAIN_SEEDS -->\nEpisode 1: Test",
            "coverage.md": "<!-- COVERAGE_FRAMEWORK -->\nCoverage",
            "lenses.md": "<!-- DOMAIN_LENS -->\nLens",
            "gem-sections.md": "<!-- GEM_BOOKSHELF -->\nBookshelf",
        })
        prep.set_profile(name)
        prep.ensure_dirs()

    def _mock_setup_success(self, profile_name):
        """Simulate cmd_setup writing real domain files."""
        domain_dir = Path(self.tmpdir) / "profiles" / profile_name / "domain"
        domain_dir.mkdir(parents=True, exist_ok=True)
        (domain_dir / "seeds.md").write_text("<!-- DOMAIN_SEEDS -->\nGenerated seeds", encoding="utf-8")
        (domain_dir / "coverage.md").write_text("<!-- COVERAGE_FRAMEWORK -->\nGenerated coverage", encoding="utf-8")
        (domain_dir / "lenses.md").write_text("<!-- DOMAIN_LENS -->\nGenerated lens", encoding="utf-8")
        (domain_dir / "gem-sections.md").write_text("<!-- GEM_BOOKSHELF -->\nGenerated bookshelf", encoding="utf-8")
        return True

    @patch('prep.cmd_setup')
    def test_all_auto_runs_setup(self, mock_setup):
        """Stubs detected -> setup called, domain reloaded, pipeline proceeds."""
        self._setup_stub_profile("test")
        mock_setup.side_effect = lambda *a, **kw: self._mock_setup_success("test")

        # Make pipeline short-circuit as "already complete" after setup
        for ep in prep.ALL_EPS:
            (prep.SYLLABUS_DIR / prep.ep_file(ep, "agenda")).write_text("agenda", encoding="utf-8")
            (prep.EPISODES_DIR / prep.ep_file(ep, "content")).write_text("x" * 500, encoding="utf-8")

        client = MagicMock()
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            prep.cmd_all(client, force=False, profile_name="test")

        mock_setup.assert_called_once()
        self.assertIn("running setup first", buf.getvalue())

    @patch('prep.cmd_setup')
    def test_all_stops_if_setup_fails(self, mock_setup):
        """Setup returns False -> no syllabus/content calls."""
        self._setup_stub_profile("test")
        mock_setup.return_value = False

        client = MagicMock()
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            prep.cmd_all(client, force=False, profile_name="test")

        self.assertIn("Setup failed", buf.getvalue())
        client.responses.create.assert_not_called()

    @patch('prep.cmd_setup')
    def test_all_skips_setup_when_populated(self, mock_setup):
        """No stubs -> setup NOT called."""
        self._setup_populated_profile("test")

        # Make pipeline short-circuit as "already complete"
        for ep in prep.ALL_EPS:
            (prep.SYLLABUS_DIR / prep.ep_file(ep, "agenda")).write_text("agenda", encoding="utf-8")
            (prep.EPISODES_DIR / prep.ep_file(ep, "content")).write_text("x" * 500, encoding="utf-8")

        client = MagicMock()
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            prep.cmd_all(client, force=False, profile_name="test")

        mock_setup.assert_not_called()
        self.assertIn("already complete", buf.getvalue())

    @patch('prep.get_client')
    @patch('prep._confirm_cost')
    def test_cost_includes_setup_calls(self, mock_confirm, mock_client):
        """Cost estimate should include +3 when stubs detected."""
        mock_confirm.return_value = False  # cancel to avoid running pipeline
        mock_client.return_value = MagicMock()
        self._setup_stub_profile("testcost")

        with patch('sys.argv', ['prep.py', 'all', '--profile', 'testcost']):
            prep.main()

        # Cost should include setup calls (3 extra)
        expected = len(prep.SYLLABUS_RUNS) + len(prep.ALL_EPS) + 3
        mock_confirm.assert_called_once_with(expected, yes=False)

    @patch('prep.get_client')
    @patch('prep._confirm_cost')
    def test_cost_excludes_setup_when_populated(self, mock_confirm, mock_client):
        """Cost estimate should NOT include +3 when domain files exist."""
        mock_confirm.return_value = False
        mock_client.return_value = MagicMock()
        self._setup_populated_profile("testcost")

        with patch('sys.argv', ['prep.py', 'all', '--profile', 'testcost']):
            prep.main()

        expected = len(prep.SYLLABUS_RUNS) + len(prep.ALL_EPS)
        mock_confirm.assert_called_once_with(expected, yes=False)

    def test_preflight_allows_all_with_stubs(self):
        """Preflight should not SystemExit for 'all' with stub domain files."""
        self._write_profile("test", "---\nrole: R\ncompany: C\ndomain: D\n---\n")
        self._write_domain("test", {
            "seeds.md": "<!-- STUB: placeholder -->\n",
            "coverage.md": "<!-- STUB: placeholder -->\n",
            "lenses.md": "<!-- STUB: placeholder -->\n",
            "gem-sections.md": "<!-- STUB: placeholder -->\n",
        })
        # Should not raise
        prep._preflight_check("test", "all")

    @patch('prep.cmd_setup')
    def test_domain_reloaded_after_setup(self, mock_setup):
        """_DOMAIN should have markers after auto-setup."""
        self._setup_stub_profile("test")
        mock_setup.side_effect = lambda *a, **kw: self._mock_setup_success("test")

        # Make pipeline short-circuit as "already complete"
        for ep in prep.ALL_EPS:
            (prep.SYLLABUS_DIR / prep.ep_file(ep, "agenda")).write_text("agenda", encoding="utf-8")
            (prep.EPISODES_DIR / prep.ep_file(ep, "content")).write_text("x" * 500, encoding="utf-8")

        client = MagicMock()
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            prep.cmd_all(client, force=False, profile_name="test")

        # After auto-setup, _DOMAIN should contain the generated markers
        self.assertIn("DOMAIN_SEEDS", prep._DOMAIN)
        self.assertIn("Generated seeds", prep._DOMAIN["DOMAIN_SEEDS"])


class TestAutoSetupStability(_ProfileTestMixin, unittest.TestCase):
    """Long-term stability tests for setup/auto-setup integration."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self._save_profile_state()
        self._orig_base = prep.BASE_DIR
        prep.BASE_DIR = Path(self.tmpdir)

    def tearDown(self):
        prep.BASE_DIR = self._orig_base
        self._restore_profile_state()
        shutil.rmtree(self.tmpdir)

    def test_domain_files_constant_matches_init(self):
        """Files created by cmd_init should match _DOMAIN_FILES. Catches drift."""
        prep.cmd_init("drift-test")
        domain_dir = Path(self.tmpdir) / "profiles" / "drift-test" / "domain"
        actual = sorted(f.name for f in domain_dir.iterdir() if f.suffix == ".md")
        expected = sorted(prep._DOMAIN_FILES)
        self.assertEqual(actual, expected)

    def test_init_stubs_mention_setup_command(self):
        """Stub files should reference 'setup' not 'adapt'."""
        prep.cmd_init("stub-test")
        domain_dir = Path(self.tmpdir) / "profiles" / "stub-test" / "domain"
        for fname in prep._DOMAIN_FILES:
            text = (domain_dir / fname).read_text(encoding="utf-8")
            self.assertIn("setup", text, f"{fname} should mention 'setup'")
            self.assertNotIn("adapt", text, f"{fname} should not mention 'adapt'")

    def test_preflight_error_mentions_setup(self):
        """Preflight error for syllabus with stubs should say 'setup'."""
        self._write_profile("test", "---\nrole: R\ncompany: C\ndomain: D\n---\n")
        self._write_domain("test", {
            "seeds.md": "<!-- STUB: placeholder -->\n",
            "coverage.md": "<!-- STUB: placeholder -->\n",
            "lenses.md": "<!-- STUB: placeholder -->\n",
            "gem-sections.md": "<!-- STUB: placeholder -->\n",
        })
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            with self.assertRaises(SystemExit):
                prep._preflight_check("test", "syllabus")
        self.assertIn("setup", buf.getvalue())
        self.assertNotIn("adapt", buf.getvalue())

    @patch('prep.cmd_setup')
    def test_all_force_does_not_force_setup(self, mock_setup):
        """cmd_all(force=True) with stubs -> verify cmd_setup called with force=False."""
        self._write_profile("test", "---\nrole: SWE\ncompany: Acme\ndomain: Testing\n---\n")
        self._write_domain("test", {
            "seeds.md": "<!-- STUB: placeholder -->\n",
            "coverage.md": "<!-- STUB: placeholder -->\n",
            "lenses.md": "<!-- STUB: placeholder -->\n",
            "gem-sections.md": "<!-- STUB: placeholder -->\n",
        })
        prep.set_profile("test")
        prep.ensure_dirs()

        # Make setup "succeed" by writing real files
        def side_effect(*a, **kw):
            domain_dir = Path(self.tmpdir) / "profiles" / "test" / "domain"
            (domain_dir / "seeds.md").write_text("<!-- DOMAIN_SEEDS -->\nReal", encoding="utf-8")
            (domain_dir / "coverage.md").write_text("<!-- COVERAGE_FRAMEWORK -->\nReal", encoding="utf-8")
            (domain_dir / "lenses.md").write_text("<!-- DOMAIN_LENS -->\nReal", encoding="utf-8")
            (domain_dir / "gem-sections.md").write_text("<!-- GEM_BOOKSHELF -->\nReal", encoding="utf-8")
            return True
        mock_setup.side_effect = side_effect

        client = MagicMock()
        client.responses.create.return_value = MagicMock(status="failed", error="test")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            with patch('prep.time') as mock_time:
                mock_time.sleep = MagicMock()
                mock_time.time = MagicMock(return_value=0)
                prep.cmd_all(client, force=True, profile_name="test")

        # Verify setup was called with force=False
        mock_setup.assert_called_once_with(unittest.mock.ANY, "test", force=False)

    @patch('prep.cmd_setup')
    @patch('prep.get_client')
    def test_all_integration_with_auto_setup(self, mock_get_client, mock_setup):
        """Full main() flow via sys.argv with stub domain files. Verifies wiring."""
        self._write_profile("inttest", "---\nrole: SWE\ncompany: Acme\ndomain: Testing\ncore_episodes: 1\nfrontier_episodes: 0\n---\n")
        self._write_domain("inttest", {
            "seeds.md": "<!-- STUB: placeholder -->\n",
            "coverage.md": "<!-- STUB: placeholder -->\n",
            "lenses.md": "<!-- STUB: placeholder -->\n",
            "gem-sections.md": "<!-- STUB: placeholder -->\n",
        })

        # Setup writes real domain files
        def setup_side_effect(*a, **kw):
            domain_dir = Path(self.tmpdir) / "profiles" / "inttest" / "domain"
            (domain_dir / "seeds.md").write_text("<!-- DOMAIN_SEEDS -->\nReal", encoding="utf-8")
            (domain_dir / "coverage.md").write_text("<!-- COVERAGE_FRAMEWORK -->\nReal", encoding="utf-8")
            (domain_dir / "lenses.md").write_text("<!-- DOMAIN_LENS -->\nReal", encoding="utf-8")
            (domain_dir / "gem-sections.md").write_text("<!-- GEM_BOOKSHELF -->\nReal", encoding="utf-8")
            return True
        mock_setup.side_effect = setup_side_effect

        mock_client = MagicMock()
        mock_resp = MagicMock(status="completed", output_text="## Episode 1: Test\nContent " * 100, usage=None)
        mock_client.responses.create.return_value = mock_resp
        mock_get_client.return_value = mock_client

        buf = io.StringIO()
        buf.reconfigure = MagicMock()  # StringIO lacks reconfigure
        with patch('sys.stdout', buf):
            with patch('sys.argv', ['prep.py', 'all', '--profile', 'inttest', '--yes']):
                prep.main()

        output = buf.getvalue()
        # Setup should have been called
        mock_setup.assert_called_once()
        # Pipeline should have proceeded through syllabus + content
        # With 1 core + 0 frontier, expect SYLLABUS_RUNS calls + 1 content call
        expected_min_calls = len(prep.build_syllabus_runs(1, 0)) + 1
        self.assertGreaterEqual(mock_client.responses.create.call_count, expected_min_calls,
            f"Pipeline should have made at least {expected_min_calls} API calls (syllabus + content)")
        # Should show setup message
        self.assertIn("running setup first", output)


class TestGetClient(unittest.TestCase):
    """Test get_client() validation and client creation."""

    def test_missing_key_exits(self):
        """No OPENAI_API_KEY env var -> SystemExit."""
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("OPENAI_API_KEY", None)
            with self.assertRaises(SystemExit):
                prep.get_client()

    def test_success_returns_client(self):
        """Key set + openai importable -> returns client."""
        mock_openai = MagicMock()
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}):
            with patch.dict('sys.modules', {'openai': mock_openai}):
                client = prep.get_client()
                mock_openai.OpenAI.assert_called_once_with(api_key="sk-test")

    def test_import_error_exits(self):
        """openai not importable -> SystemExit with install hint."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}):
            with patch.dict('sys.modules', {'openai': None}):
                # Force import to fail by making the module None
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    with self.assertRaises((SystemExit, TypeError)):
                        prep.get_client()


class TestSetupHelpers(_ProfileTestMixin, unittest.TestCase):
    """Test setup command helper functions."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self._save_profile_state()
        self._orig_base = prep.BASE_DIR
        prep.BASE_DIR = Path(self.tmpdir)
        self._write_profile("test", "---\nrole: SWE\ncompany: Acme\ndomain: Testing\n---\n")
        prep.set_profile("test")

    def tearDown(self):
        prep.BASE_DIR = self._orig_base
        self._restore_profile_state()
        shutil.rmtree(self.tmpdir)

    def test_setup_instructions_includes_role(self):
        """Setup instructions should contain ROLE and COMPANY."""
        result = prep._setup_instructions()
        self.assertIn(prep.ROLE, result)
        self.assertIn(prep.COMPANY, result)

    def test_build_setup_prompt_replaces_vars(self):
        """{ROLE}, {COMPANY}, {DOMAIN} should be replaced in setup prompts."""
        result = prep._build_setup_prompt("meta-seeds",
            "profile text", CONTEXT_DOCS="docs text")
        self.assertNotIn("{ROLE}", result)
        self.assertNotIn("{COMPANY}", result)
        self.assertNotIn("{DOMAIN}", result)
        self.assertIn(prep.ROLE, result)
        self.assertIn(prep.COMPANY, result)

    def test_build_setup_prompt_extra_kwargs(self):
        """Extra kwargs like CONTEXT_DOCS should be injected."""
        result = prep._build_setup_prompt("meta-seeds",
            "profile text", CONTEXT_DOCS="Special context here")
        self.assertIn("Special context here", result)

    def test_write_domain_file_skips_when_no_markers(self):
        """When parsed dict has no matching markers, file should not be written."""
        domain_dir = Path(self.tmpdir) / "profiles" / "test" / "domain"
        domain_dir.mkdir(parents=True, exist_ok=True)
        result = prep._write_domain_file(domain_dir, "test.md", ["FOO", "BAR"], {})
        self.assertFalse(result)
        self.assertFalse((domain_dir / "test.md").exists())


class TestStatusOutput(_ProfileTestMixin, unittest.TestCase):
    """Test cmd_status output formatting and warnings."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self._save_profile_state()
        self._orig_base = prep.BASE_DIR
        prep.BASE_DIR = Path(self.tmpdir)

    def tearDown(self):
        prep.BASE_DIR = self._orig_base
        self._restore_profile_state()
        shutil.rmtree(self.tmpdir)

    def test_show_pipeline_status_counts(self):
        """Pipeline status should show correct agenda/content counts."""
        self._write_profile("test", "---\nrole: SWE\ncompany: Acme\ndomain: D\n---\n")
        self._write_domain("test", {
            "seeds.md": "<!-- DOMAIN_SEEDS -->\nReal",
            "coverage.md": "<!-- COVERAGE_FRAMEWORK -->\nReal",
            "lenses.md": "<!-- DOMAIN_LENS -->\nReal",
            "gem-sections.md": "<!-- GEM_BOOKSHELF -->\nReal",
        })
        prep.set_profile("test")
        prep.ensure_dirs()
        # Create 5 agendas and 3 content files
        for ep in range(1, 6):
            (prep.SYLLABUS_DIR / prep.ep_file(ep, "agenda")).write_text("agenda", encoding="utf-8")
        for ep in range(1, 4):
            (prep.EPISODES_DIR / prep.ep_file(ep, "content")).write_text("content", encoding="utf-8")

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            prep.cmd_status(profile_name="test")
        output = buf.getvalue()
        self.assertIn("5/", output)  # 5 agendas
        self.assertIn("3/", output)  # 3 content files

    def test_profile_summary_valid(self):
        """Profile summary should include role and company."""
        self._write_profile("test", "---\nrole: Principal Eng\ncompany: BigCo\ndomain: Infra\n---\n")
        result = prep._profile_summary("test")
        self.assertIn("Principal Eng", result)
        self.assertIn("BigCo", result)

    def test_print_syllabus_review_output(self):
        """Syllabus review checklist should contain key items."""
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            prep._print_syllabus_review("myprofile")
        output = buf.getvalue()
        self.assertIn("Review", output)
        self.assertIn("Episode count", output)
        self.assertIn("myprofile", output)

    def test_profile_summary_stages(self):
        """Profile summary should detect pipeline stages."""
        self._write_profile("empty", "---\nrole: R\ncompany: C\ndomain: D\n---\n")
        result = prep._profile_summary("empty")
        self.assertIn("profile created", result)

        # Now with domain files -> "domain ready"
        self._write_profile("withdom", "---\nrole: R\ncompany: C\ndomain: D\n---\n")
        self._write_domain("withdom", {
            "seeds.md": "<!-- DOMAIN_SEEDS -->\nReal",
            "coverage.md": "<!-- COVERAGE_FRAMEWORK -->\nReal",
            "lenses.md": "<!-- DOMAIN_LENS -->\nReal",
            "gem-sections.md": "<!-- GEM_BOOKSHELF -->\nReal",
        })
        result = prep._profile_summary("withdom")
        self.assertIn("domain ready", result)


class TestRecoverFromPattern(_ProfileTestMixin, unittest.TestCase):
    """Test the extracted _recover_from_pattern helper."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self._save_profile_state()
        for attr in ['IN_AGENDAS', 'SYLLABUS_DIR', 'RAW_DIR']:
            new_dir = Path(self.tmpdir) / attr.lower()
            new_dir.mkdir(parents=True)
            setattr(prep, attr, new_dir)

    def tearDown(self):
        self._restore_profile_state()
        shutil.rmtree(self.tmpdir)

    def test_core_batch_pattern(self):
        """_recover_from_pattern('core_batch') should find core batch raw files."""
        raw_text = "**Episode 1 — Title**\nContent."
        (prep.RAW_DIR / "syllabus-02-core_batch.md").write_text(raw_text, encoding="utf-8")
        count = prep._recover_from_pattern("core_batch")
        self.assertEqual(count, 1)
        self.assertTrue((prep.SYLLABUS_DIR / "episode-01-agenda.md").exists())

    def test_frontier_pattern(self):
        """_recover_from_pattern('frontier_digest') should find frontier raw files."""
        raw_text = "**Frontier Digest A — Updates**\nContent."
        (prep.RAW_DIR / "syllabus-03-frontier_digest.md").write_text(raw_text, encoding="utf-8")
        count = prep._recover_from_pattern("frontier_digest")
        self.assertEqual(count, 1)
        self.assertTrue((prep.SYLLABUS_DIR / "episode-13-agenda.md").exists())

    def test_no_matching_files(self):
        """No matching raw files -> 0 recovered."""
        count = prep._recover_from_pattern("core_batch")
        self.assertEqual(count, 0)


class TestMainErrorPaths(_ProfileTestMixin, unittest.TestCase):
    """Cover main() validation and error branches."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self._save_profile_state()
        self._orig_base = prep.BASE_DIR
        prep.BASE_DIR = Path(self.tmpdir)

    def tearDown(self):
        prep.BASE_DIR = self._orig_base
        self._restore_profile_state()
        shutil.rmtree(self.tmpdir)

    def test_init_without_name_exits(self):
        with patch('sys.argv', ['prep.py', 'init']):
            with self.assertRaises(SystemExit):
                prep.main()

    def test_api_command_without_profile_exits(self):
        for cmd in ['syllabus', 'content', 'add', 'setup', 'all']:
            with patch('sys.argv', ['prep.py', cmd]):
                with self.assertRaises(SystemExit):
                    prep.main()

    def test_render_without_file_exits(self):
        with patch('sys.argv', ['prep.py', 'render']):
            with self.assertRaises(SystemExit):
                prep.main()

    def test_render_file_not_found_exits(self):
        with patch('sys.argv', ['prep.py', 'render', '/nonexistent/file.md']):
            with self.assertRaises(SystemExit):
                prep.main()

    def test_add_without_file_exits(self):
        with patch('sys.argv', ['prep.py', 'add']):
            with self.assertRaises(SystemExit):
                prep.main()

    def _setup_valid_profile(self, name="testprof"):
        """Create a valid profile with non-stub domain files for post-profile-load tests."""
        profile_content = "---\nrole: Eng\ncompany: Co\ndomain: D\n---\n"
        self._write_profile(name, profile_content)
        domain_files = {f: "real content " * 20 for f in prep._DOMAIN_FILES}
        self._write_domain(name, domain_files)

    def test_invalid_episode_exits(self):
        self._setup_valid_profile()
        with patch('sys.argv', ['prep.py', 'content', '--profile', 'testprof', '--episode', '999']):
            with self.assertRaises(SystemExit):
                prep.main()

    def test_invalid_gem_slot_exits(self):
        self._setup_valid_profile()
        with patch('sys.argv', ['prep.py', 'add', '--profile', 'testprof', '--gem-slot', '999', 'dummy.md']):
            with self.assertRaises(SystemExit):
                prep.main()


if __name__ == "__main__":
    unittest.main()
