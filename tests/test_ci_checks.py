"""The release checks must reject broken dependencies, links and instruction overflow."""
import importlib.util
import shutil
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('ci_checks', ROOT / 'tests/ci_checks.py')
ci = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ci)


class ReleaseChecks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'tree'
        shutil.copytree(ROOT, self.root, ignore=shutil.ignore_patterns('.git', '__pycache__', 'logs', 'records'))

    def test_real_tree_passes(self):
        for name, check in ci.CHECKS.items():
            self.assertEqual(check(ROOT), [], name)

    def test_missing_logger_is_rejected(self):
        (self.root / 'managed/action_log.py').unlink()
        self.assertTrue(ci.check_release(self.root))

    def test_missing_plugin_entry_is_rejected(self):
        (self.root / 'runtimes/openclaw/plugins/action-log/index.js').unlink()
        self.assertTrue(ci.check_release(self.root))

    def test_large_generated_instructions_are_rejected(self):
        target = self.root / 'managed/runtime.py'
        target.write_text(target.read_text().replace('"# Voice\\n\\nBe helpful', '"x" * 60000 + "# Voice\\n\\nBe helpful'))
        issues = ci.check_size_budget(self.root)
        self.assertTrue(any('SOUL.md' in row for row in issues), issues)
        self.assertTrue(any('total' in row for row in issues), issues)

    def test_missing_document_link_is_rejected(self):
        (self.root / 'README.md').write_text('[Missing](docs/not-a-file.md)\n')
        self.assertTrue(ci.check_docs(self.root))


if __name__ == '__main__':
    unittest.main()
