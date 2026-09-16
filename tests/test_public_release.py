"""Public release gates: example installs, runtime files and accidental publication."""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from managed import install
from managed.store import DeskError
from managed.control import initial
from managed.runtime import workspace_files

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('public_scan', ROOT / 'tests/public_scan.py')
scan = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scan)


class PublicRelease(unittest.TestCase):
    def example(self):
        return json.loads((ROOT / 'managed/company.example.json').read_text())

    def test_real_install_refuses_example_before_writing_or_running_commands(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(install.subprocess, 'run') as run:
            target = Path(folder) / 'company'
            with self.assertRaisesRegex(DeskError, 'example'):
                install.initialize(target, ROOT, self.example(), 'a' * 40)
            self.assertFalse(target.exists())
            run.assert_not_called()

    def test_renaming_company_is_not_enough_to_accept_example_owners(self):
        config = self.example()
        config.update(company_id='sample-team', company_name='Sample Team')
        with self.assertRaisesRegex(DeskError, 'administrator'):
            install.require_real_company(config)
        # UK drama numbers are synthetic positive fixtures, never contacted.
        config['founders'] = [{'name':'Admin One','number':'+447700900001'}, {'name':'Admin Two','number':'+447700900002'}]
        install.require_real_company(config)

    def test_every_generated_instruction_is_at_workspace_root_and_has_no_owner_identity(self):
        config = self.example()
        files = workspace_files(initial(config))
        self.assertEqual(set(files), {'IDENTITY.md','SOUL.md','USER.md','AGENTS.md','TOOLS.md','MEMORY.md','HEARTBEAT.md'})
        for name, content in files.items():
            self.assertEqual(Path(name).name, name)
            for person in config['founders']:
                self.assertNotIn(person['number'], content)
                self.assertNotIn(person['name'], content)

    def test_secret_scan_catches_credentials_without_printing_them(self):
        token = 'sk_' + 'live_' + 'A' * 30
        findings = scan.inspect_text('example.txt', token)
        self.assertTrue(findings)
        self.assertNotIn(token, str(findings))
        private_key = 'AGE-' + 'SECRET-KEY-1' + 'A' * 30
        self.assertTrue(scan.inspect_text('key.txt', private_key))

    def test_scan_allows_documented_fake_contacts_and_public_support(self):
        self.assertEqual(scan.inspect_text('example.txt', '+12025550101 support@example.com info@puestario.com'), [])
        self.assertTrue(scan.inspect_text('example.txt', 'someone@' + 'private-company.invalid'))
        self.assertTrue(scan.private_path('client/secrets/token.json'))
        self.assertFalse(scan.private_path('managed/company.example.json'))


if __name__ == '__main__':
    unittest.main()
