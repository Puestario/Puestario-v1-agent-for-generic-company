"""CI drift checks, both directions: the real tree passes, a broken synthetic tree is caught."""
import importlib.util
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("ci_checks", ROOT / "tests/ci_checks.py")
ci = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ci)


class RealTreeTests(unittest.TestCase):
    def test_real_tree_passes_every_check(self):
        for name, check in ci.CHECKS.items():
            with self.subTest(check=name):
                self.assertEqual(check(ROOT), [])

    def test_workflow_runs_the_checks(self):
        workflow = (ROOT / ".github/workflows/tests.yml").read_text()
        for check in ("placeholders", "core-rules", "size-budget"):
            self.assertIn(f"python tests/ci_checks.py {check}", workflow)

    def test_every_session_file_exists(self):
        for name in ci.SESSION_FILES:
            self.assertTrue((ROOT / name).is_file(), name)


class SyntheticTreeTests(unittest.TestCase):
    """Copy the repo, break one thing, and confirm the right check catches it."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "tree"
        shutil.copytree(ROOT, self.root, ignore=shutil.ignore_patterns(".git", "__pycache__", "logs", "records"))

    def base_count(self):
        import re
        return re.search(r"It lists all (\d+)", (self.root / "SETUP.md").read_text()).group(1)

    def edit(self, path, old, new):
        target = self.root / path
        text = target.read_text()
        self.assertIn(old, text)
        target.write_text(text.replace(old, new))

    def test_clean_copy_passes(self):
        for name, check in ci.CHECKS.items():
            self.assertEqual(check(self.root), [], name)

    def test_wrong_count_in_placeholders_md_is_caught(self):
        self.edit("PLACEHOLDERS.md", "placeholders** in the base install", "placeholders** in the base install")
        self.edit("PLACEHOLDERS.md", f"**{self.base_count()} placeholders**", "**90 placeholders**")
        problems = ci.check_placeholders(self.root)
        self.assertTrue(any("PLACEHOLDERS.md says 90" in p for p in problems), problems)

    def test_wrong_count_in_setup_md_is_caught(self):
        self.edit("SETUP.md", f"It lists all {self.base_count()}", "It lists all 85")
        problems = ci.check_placeholders(self.root)
        self.assertTrue(any("SETUP.md says 85" in p for p in problems), problems)

    def test_new_placeholder_without_a_row_is_caught(self):
        (self.root / "client/identity/USER.md").open("a").write("\n- Pet: YOUR_PET_NAME\n")
        problems = ci.check_placeholders(self.root)
        self.assertTrue(any("YOUR_PET_NAME is in the tree but has no row" in p for p in problems), problems)

    def test_row_without_an_occurrence_is_caught(self):
        self.edit("client/identity/USER.md", "YOUR_TIMEZONE", "America/New_York")
        problems = ci.check_placeholders(self.root)
        self.assertTrue(any("YOUR_TIMEZONE has a row" in p for p in problems), problems)

    def test_stale_path_in_a_row_is_caught(self):
        self.edit("PLACEHOLDERS.md", "`extras/agents/operator/AGENTS.md`", "`client/agents/operator/AGENTS.md`")
        problems = ci.check_placeholders(self.root)
        self.assertTrue(any("YOUR_OPERATOR_PAPERCLIP_AGENT_ID" in p for p in problems), problems)

    def test_placeholder_in_core_rules_is_caught(self):
        (self.root / "core/rules/02-the-yes-comes-from-the-owner.md").open("a").write("\nAsk YOUR_OWNER_NAME first.\n")
        problems = ci.check_core_rules(self.root)
        self.assertEqual(len(problems), 1)
        self.assertIn("core/rules/02-the-yes-comes-from-the-owner.md", problems[0])

    def test_owner_name_or_number_in_core_rules_is_caught(self):
        (self.root / "core/rules/02-the-yes-comes-from-the-owner.md").open("a").write("\nCall Mateo at +15555550100 or mateo@example.com.\n")
        problems = ci.check_core_rules(self.root)
        self.assertTrue(any("phone number" in p for p in problems), problems)
        self.assertTrue(any("email address" in p for p in problems), problems)
        self.assertTrue(any("names an owner (Mateo)" in p for p in problems), problems)
        (self.root / "core/config/reserved.md").open("a").write("\nAsk Gerardo first.\n")
        self.assertTrue(any("reserved.md" in p and "Gerardo" in p for p in ci.check_core_rules(self.root)))

    def test_placeholder_elsewhere_in_core_is_caught(self):
        (self.root / "core/config/reserved.md").open("a").write("\nowner: YOUR_OWNER_NAME\n")
        problems = ci.check_core_rules(self.root)
        self.assertTrue(any("core/config/reserved.md" in p for p in problems), problems)

    def test_oversized_session_file_is_caught(self):
        (self.root / "client/operating/AGENTS.md").open("a").write("x" * ci.PER_FILE_BUDGET)
        problems = ci.check_size_budget(self.root)
        self.assertTrue(any("client/operating/AGENTS.md" in p and "per-file" in p for p in problems), problems)

    def test_total_budget_is_caught(self):
        for name in ("client/identity/OWNER.md", "client/identity/USER.md", "client/identity/SOUL.md",
                     "client/identity/IDENTITY.md", "client/identity/MEMORY.md", "client/operating/HEARTBEAT.md"):
            (self.root / name).open("a").write("y" * 9_000)
        problems = ci.check_size_budget(self.root)
        self.assertTrue(any("total" in p for p in problems), problems)

    def test_missing_session_file_is_caught(self):
        (self.root / "core/config/reserved.md").unlink()
        problems = ci.check_size_budget(self.root)
        self.assertTrue(any("reserved.md is missing" in p for p in problems), problems)

    def test_cli_exit_codes(self):
        script = str(ROOT / "tests/ci_checks.py")
        ok = subprocess.run([sys.executable, script, "all", "--root", str(self.root)], capture_output=True, text=True)
        self.assertEqual(ok.returncode, 0, ok.stdout)
        self.edit("SETUP.md", f"It lists all {self.base_count()}", "It lists all 1")
        bad = subprocess.run([sys.executable, script, "placeholders", "--root", str(self.root)],
                             capture_output=True, text=True)
        self.assertEqual(bad.returncode, 1)
        self.assertIn("SETUP.md says 1", bad.stdout)


if __name__ == "__main__":
    unittest.main()
