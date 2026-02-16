#!/usr/bin/env python3
"""Unit tests for prep.py"""

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


class TestFileHelpers(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self._orig_in_agendas = prep.IN_AGENDAS
        self._orig_in_episodes = prep.IN_EPISODES
        self._orig_syllabus_dir = prep.SYLLABUS_DIR
        self._orig_episodes_dir = prep.EPISODES_DIR

        prep.IN_AGENDAS = Path(self.tmpdir) / "in_agendas"
        prep.IN_EPISODES = Path(self.tmpdir) / "in_episodes"
        prep.SYLLABUS_DIR = Path(self.tmpdir) / "syllabus"
        prep.EPISODES_DIR = Path(self.tmpdir) / "episodes"

        for d in [prep.IN_AGENDAS, prep.IN_EPISODES, prep.SYLLABUS_DIR, prep.EPISODES_DIR]:
            d.mkdir(parents=True)

    def tearDown(self):
        shutil.rmtree(self.tmpdir)
        prep.IN_AGENDAS = self._orig_in_agendas
        prep.IN_EPISODES = self._orig_in_episodes
        prep.SYLLABUS_DIR = self._orig_syllabus_dir
        prep.EPISODES_DIR = self._orig_episodes_dir

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


class TestSkipLogic(unittest.TestCase):
    """Test that cmd_syllabus and cmd_content correctly skip existing files."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self._orig = {}
        for attr in ['IN_AGENDAS', 'IN_EPISODES', 'SYLLABUS_DIR', 'EPISODES_DIR',
                      'RAW_DIR', 'GEM_DIR', 'NLM_DIR']:
            self._orig[attr] = getattr(prep, attr)
            new_dir = Path(self.tmpdir) / attr.lower()
            new_dir.mkdir(parents=True)
            setattr(prep, attr, new_dir)

    def tearDown(self):
        shutil.rmtree(self.tmpdir)
        for attr, val in self._orig.items():
            setattr(prep, attr, val)

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


class TestPackaging(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self._orig = {}
        for attr in ['IN_AGENDAS', 'IN_EPISODES', 'SYLLABUS_DIR', 'EPISODES_DIR',
                      'RAW_DIR', 'GEM_DIR', 'NLM_DIR']:
            self._orig[attr] = getattr(prep, attr)
            new_dir = Path(self.tmpdir) / attr.lower()
            new_dir.mkdir(parents=True)
            setattr(prep, attr, new_dir)

    def tearDown(self):
        shutil.rmtree(self.tmpdir)
        for attr, val in self._orig.items():
            setattr(prep, attr, val)

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


class TestParseAgendasWarning(unittest.TestCase):
    """Test that empty parse results trigger warnings during syllabus."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self._orig = {}
        for attr in ['IN_AGENDAS', 'IN_EPISODES', 'SYLLABUS_DIR', 'EPISODES_DIR',
                      'RAW_DIR', 'GEM_DIR', 'NLM_DIR']:
            self._orig[attr] = getattr(prep, attr)
            new_dir = Path(self.tmpdir) / attr.lower()
            new_dir.mkdir(parents=True)
            setattr(prep, attr, new_dir)

    def tearDown(self):
        shutil.rmtree(self.tmpdir)
        for attr, val in self._orig.items():
            setattr(prep, attr, val)

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


class TestCmdAllFailureHandling(unittest.TestCase):
    """Test that cmd_all warns on syllabus failure."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self._orig = {}
        for attr in ['IN_AGENDAS', 'IN_EPISODES', 'SYLLABUS_DIR', 'EPISODES_DIR',
                      'RAW_DIR', 'GEM_DIR', 'NLM_DIR']:
            self._orig[attr] = getattr(prep, attr)
            new_dir = Path(self.tmpdir) / attr.lower()
            new_dir.mkdir(parents=True)
            setattr(prep, attr, new_dir)

    def tearDown(self):
        shutil.rmtree(self.tmpdir)
        for attr, val in self._orig.items():
            setattr(prep, attr, val)

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


class TestRecoverFromRaw(unittest.TestCase):
    """Test recovery of agendas from raw syllabus files."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self._orig = {}
        for attr in ['IN_AGENDAS', 'IN_EPISODES', 'SYLLABUS_DIR', 'EPISODES_DIR',
                      'RAW_DIR', 'GEM_DIR', 'NLM_DIR']:
            self._orig[attr] = getattr(prep, attr)
            new_dir = Path(self.tmpdir) / attr.lower()
            new_dir.mkdir(parents=True)
            setattr(prep, attr, new_dir)

    def tearDown(self):
        shutil.rmtree(self.tmpdir)
        for attr, val in self._orig.items():
            setattr(prep, attr, val)

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
        (Path(__file__).parent / "outputs" / "raw" / "syllabus-02-core_batch.md").exists(),
        "Real output file not available (run pipeline first)"
    )
    def test_recovers_from_real_raw_file(self):
        """Recovery works with actual GPT-5.2-pro output."""
        real_text = (Path(__file__).parent / "outputs" / "raw" / "syllabus-02-core_batch.md").read_text(encoding="utf-8")
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

    REAL_FILE = Path(__file__).parent / "outputs" / "raw" / "syllabus-02-core_batch.md"

    @unittest.skipUnless(
        (Path(__file__).parent / "outputs" / "raw" / "syllabus-02-core_batch.md").exists(),
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
        (Path(__file__).parent / "outputs" / "raw" / "syllabus-02-core_batch.md").exists(),
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


class TestRecoveryCalledByAllCommands(unittest.TestCase):
    """Verify recovery runs in status, syllabus, and content commands.
    Bug found in review round 6: status and syllabus didn't call recovery,
    so user would see 0 agendas or re-run all 8 syllabus calls."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self._orig = {}
        for attr in ['IN_AGENDAS', 'IN_EPISODES', 'SYLLABUS_DIR', 'EPISODES_DIR',
                      'RAW_DIR', 'GEM_DIR', 'NLM_DIR']:
            self._orig[attr] = getattr(prep, attr)
            new_dir = Path(self.tmpdir) / attr.lower()
            new_dir.mkdir(parents=True)
            setattr(prep, attr, new_dir)

    def tearDown(self):
        shutil.rmtree(self.tmpdir)
        for attr, val in self._orig.items():
            setattr(prep, attr, val)

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


class TestEndToEndResume(unittest.TestCase):
    """Simulate the exact morning scenario: raw files exist from overnight,
    zero agenda files, zero content. Run cmd_all with new code.
    Verify: recovery -> skip all syllabus -> generate all content -> package."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self._orig = {}
        for attr in ['IN_AGENDAS', 'IN_EPISODES', 'SYLLABUS_DIR', 'EPISODES_DIR',
                      'RAW_DIR', 'GEM_DIR', 'NLM_DIR', 'IN_MISC']:
            self._orig[attr] = getattr(prep, attr)
            new_dir = Path(self.tmpdir) / attr.lower()
            new_dir.mkdir(parents=True)
            setattr(prep, attr, new_dir)

    def tearDown(self):
        shutil.rmtree(self.tmpdir)
        for attr, val in self._orig.items():
            setattr(prep, attr, val)

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
        for section in ["Title", "Hook", "Mental Model", "L4 Trap",
                        "Nitty Gritty", "Staff Pivot", "Scenario Challenge"]:
            self.assertIn(section, t)

    def test_syllabus_has_training_data(self):
        t = prep.load_prompt("syllabus")
        self.assertIn("TRAINING DATA", t)
        self.assertIn("Episode 1:", t)
        self.assertIn("Episode 12:", t)

    def test_content_has_section_headings(self):
        t = prep.load_prompt("content")
        for heading in ["## Title", "## Hook", "## Mental Model", "## L4 Trap",
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
        for section in ["Title", "Hook", "Mental Model", "L4 Trap",
                        "Nitty Gritty", "Staff Pivot", "Scenario Challenge"]:
            self.assertIn(section, t)

    def test_distill_has_placeholder(self):
        t = prep.load_prompt("distill")
        self.assertIn("{RAW_DOCUMENT}", t)


class TestCmdAdd(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self._orig = {}
        for attr in ['SYLLABUS_DIR', 'EPISODES_DIR', 'GEM_DIR', 'NLM_DIR']:
            self._orig[attr] = getattr(prep, attr)
            new_dir = Path(self.tmpdir) / attr.lower()
            new_dir.mkdir(parents=True)
            setattr(prep, attr, new_dir)

    def tearDown(self):
        shutil.rmtree(self.tmpdir)
        for attr, val in self._orig.items():
            setattr(prep, attr, val)

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


class TestWriteManifest(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self._orig = {}
        for attr in ['IN_AGENDAS', 'IN_EPISODES', 'SYLLABUS_DIR', 'EPISODES_DIR',
                      'GEM_DIR', 'NLM_DIR', 'OUTPUTS']:
            self._orig[attr] = getattr(prep, attr)
            new_dir = Path(self.tmpdir) / attr.lower()
            new_dir.mkdir(parents=True)
            setattr(prep, attr, new_dir)

    def tearDown(self):
        shutil.rmtree(self.tmpdir)
        for attr, val in self._orig.items():
            setattr(prep, attr, val)

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


class TestContentEdgeCases(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self._orig = {}
        for attr in ['IN_AGENDAS', 'IN_EPISODES', 'SYLLABUS_DIR', 'EPISODES_DIR',
                      'RAW_DIR', 'GEM_DIR', 'NLM_DIR']:
            self._orig[attr] = getattr(prep, attr)
            new_dir = Path(self.tmpdir) / attr.lower()
            new_dir.mkdir(parents=True)
            setattr(prep, attr, new_dir)

    def tearDown(self):
        shutil.rmtree(self.tmpdir)
        for attr, val in self._orig.items():
            setattr(prep, attr, val)

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
        self.assertIn(prep.ROLE, prep.SYLLABUS_INSTRUCTIONS)

    def test_syllabus_instructions_use_company(self):
        self.assertIn(prep.COMPANY, prep.SYLLABUS_INSTRUCTIONS)

    def test_content_instructions_use_role(self):
        self.assertIn(prep.ROLE, prep.CONTENT_INSTRUCTIONS)

    def test_content_instructions_use_company(self):
        self.assertIn(prep.COMPANY, prep.CONTENT_INSTRUCTIONS)

    def test_distill_instructions_use_role(self):
        self.assertIn(prep.ROLE, prep.DISTILL_INSTRUCTIONS)

    def test_distill_instructions_use_company(self):
        self.assertIn(prep.COMPANY, prep.DISTILL_INSTRUCTIONS)

    def test_no_hardcoded_google_in_instructions(self):
        for instr in [prep.SYLLABUS_INSTRUCTIONS,
                      prep.CONTENT_INSTRUCTIONS,
                      prep.DISTILL_INSTRUCTIONS]:
            self.assertNotIn("Staff Security Engineer (L6)", instr)


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

    def test_syllabus_prompt_still_has_training_data(self):
        """Training data should be preserved (has Google internals as examples)."""
        run = dict(mode="SCAFFOLD", core="", frontier="")
        result = prep.syllabus_prompt(run)
        self.assertIn("mTLS", result)
        self.assertIn("DPoP", result)

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


class TestPackageGemScaffold(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self._orig = {}
        for attr in ['IN_AGENDAS', 'IN_EPISODES', 'SYLLABUS_DIR', 'EPISODES_DIR',
                      'RAW_DIR', 'GEM_DIR', 'NLM_DIR']:
            self._orig[attr] = getattr(prep, attr)
            new_dir = Path(self.tmpdir) / attr.lower()
            new_dir.mkdir(parents=True)
            setattr(prep, attr, new_dir)

    def tearDown(self):
        shutil.rmtree(self.tmpdir)
        for attr, val in self._orig.items():
            setattr(prep, attr, val)

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


class TestDynamicManifest(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self._orig = {}
        for attr in ['IN_AGENDAS', 'IN_EPISODES', 'SYLLABUS_DIR', 'EPISODES_DIR',
                      'GEM_DIR', 'NLM_DIR', 'OUTPUTS']:
            self._orig[attr] = getattr(prep, attr)
            new_dir = Path(self.tmpdir) / attr.lower()
            new_dir.mkdir(parents=True)
            setattr(prep, attr, new_dir)

    def tearDown(self):
        prep._reconfigure()
        shutil.rmtree(self.tmpdir)
        for attr, val in self._orig.items():
            setattr(prep, attr, val)

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


if __name__ == "__main__":
    unittest.main()
