"""Drift fixes: one count, one rule-change story, one job and one agent in the base install."""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return (ROOT / path).read_text(encoding="utf-8")


class PlaceholderCountTests(unittest.TestCase):
    def test_setup_and_placeholders_state_the_same_number(self):
        setup = re.search(r"It lists all (\d+)\s+placeholders", read("SETUP.md"))
        header = re.search(r"\*\*(\d+) placeholders\*\* in the base install", read("PLACEHOLDERS.md"))
        readme = re.search(r"All (\d+) base placeholders", read("README.md"))
        self.assertTrue(setup and header and readme)
        self.assertEqual(setup.group(1), header.group(1))
        self.assertEqual(readme.group(1), header.group(1))

    def test_no_row_for_a_placeholder_that_appears_nowhere(self):
        self.assertNotIn("YOUR_RUN_TIME", read("PLACEHOLDERS.md"))


class KnownAndOpenTests(unittest.TestCase):
    def test_readme_says_live_tests_have_not_been_run(self):
        readme = read("README.md")
        section = readme[readme.index("## KNOWN AND OPEN"):]
        self.assertIn("unit-tested, not yet proven on an install", section)
        self.assertIn("SETUP.md step 7 tests 7, 8, 9 and", section)
        self.assertIn("runtimes/openclaw/", readme)
        setup = read("SETUP.md")
        self.assertIn("## Step 7 — Test the rules", setup)
        self.assertIn("9. **Every send is logged.**", setup)
        self.assertIn("10. **Session start.**", setup)


class RuleChangeTests(unittest.TestCase):
    def test_hard_rule_7_matches_rule_06(self):
        text = read("client/operating/AGENTS.md")
        rule = re.search(r"^7\. Immutability clause — (.+)$", text, re.M).group(1)
        # Nobody but an owner; an owner by message from their number; logged; no second step.
        self.assertNotIn("explicitly authorize", rule)
        self.assertIn("anyone who is not an owner", rule)
        self.assertIn("WhatsApp message from their verified number", rule)
        self.assertIn("no second confirmation step", rule)
        self.assertIn("06-how-my-rules-change.md", rule)
        self.assertIn("decisions.jsonl", rule)

    def test_rule_06_and_rule_7_agree(self):
        rule06 = read("core/rules/06-how-my-rules-change.md")
        self.assertIn("My rules change on an owner's word", rule06)
        self.assertIn("Either one alone is enough", rule06)
        self.assertIn("Nobody else can change my rules", rule06)
        self.assertIn("client/memory/decisions.jsonl", rule06)


class OneJobOneAgentTests(unittest.TestCase):
    def test_sub_agents_and_fitness_pieces_live_in_extras(self):
        self.assertFalse((ROOT / "client/agents").exists())
        for name in ("operator", "researcher", "industry-researcher", "ad-architect"):
            self.assertTrue((ROOT / "extras/agents" / name / "AGENTS.md").is_file(), name)
        for name in ("scripts/progress_photos.py", "scripts/build_before_after.py",
                     "TOOLS-skool.md", "heartbeat-checks.md"):
            self.assertTrue((ROOT / "extras/fitness" / name).is_file(), name)
        self.assertFalse((ROOT / "client/scripts/progress_photos.py").exists())
        self.assertFalse((ROOT / "client/scripts/build_before_after.py").exists())
        self.assertTrue((ROOT / "extras/README.md").is_file())

    def test_base_install_carries_no_brand_specific_checks(self):
        heartbeat = read("client/operating/HEARTBEAT.md")
        self.assertNotIn("STRIPE", heartbeat)
        self.assertNotIn("META ADS", heartbeat)
        self.assertIn("extras/fitness/heartbeat-checks.md", heartbeat)
        tools = read("client/connections/TOOLS.md")
        self.assertNotIn("Skool", tools)
        self.assertNotIn("YOUR_SKOOL", tools)
        extras = read("extras/fitness/heartbeat-checks.md") + read("extras/fitness/TOOLS-skool.md")
        self.assertIn("## STRIPE", extras)
        self.assertIn("## META ADS", extras)
        self.assertIn("YOUR_SKOOL_LOGIN_PASSWORD", extras)

    def test_docs_no_longer_point_at_moved_paths(self):
        for path in ("README.md", "SETUP.md", "PLACEHOLDERS.md", "JOB-CARD.md",
                     "client/operating/AGENTS.md", "client/operating/HEARTBEAT.md"):
            text = read(path)
            with self.subTest(path=path):
                self.assertNotIn("client/agents", text)
                self.assertNotIn("client/scripts/progress_photos", text)
                self.assertNotIn("client/scripts/build_before_after", text)


if __name__ == "__main__":
    unittest.main()
