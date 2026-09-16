"""One reserved list, five entries, two owners, one channel. Every rule agrees."""
import importlib.util
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESERVED = ROOT / "core/config/reserved.md"
OWNERS = {"YOUR_OWNER_WHATSAPP": "Coach Lalo", "YOUR_OWNER_2_WHATSAPP": "Mateo"}
spec = importlib.util.spec_from_file_location("memory_log", ROOT / "core/scripts/memory_log.py")
memory_log = importlib.util.module_from_spec(spec)
spec.loader.exec_module(memory_log)


def read(path):
    return (ROOT / path).read_text(encoding="utf-8")


class ReservedTests(unittest.TestCase):
    def rows(self):
        return re.findall(r"^\| (\d) \| \*\*(.+?)\*\* \|", RESERVED.read_text(), re.M)

    def test_exactly_five_reserved_changes(self):
        rows = self.rows()
        self.assertEqual([int(n) for n, _ in rows], [1, 2, 3, 4, 5])
        names = " ".join(name.lower() for _, name in rows)
        for word in ("rules", "tools", "allowlist", "channels", "money"):
            self.assertIn(word, names)

    def test_no_placeholders_in_core_config_reserved(self):
        self.assertNotIn("YOUR_", RESERVED.read_text())

    def test_rule_06_and_owner_point_at_the_list_and_carry_no_copy(self):
        for path in ("core/rules/06-how-my-rules-change.md", "client/identity/OWNER.md",
                     "client/operating/AGENTS.md"):
            text = read(path)
            with self.subTest(path=path):
                self.assertIn("core/config/reserved.md", text)
                self.assertNotRegex(text, r"rules, tools and integrations, allowlist, channels")
                self.assertNotRegex(text, r"my rules, my tools, who is on the allowlist")

    def test_reserved_changes_need_one_owner_message_and_nothing_else(self):
        text = RESERVED.read_text()
        self.assertIn("either one alone is enough", text)
        self.assertIn("There is no second\nchannel", text)
        self.assertIn("Everything not on this list is ordinary work", text)
        self.assertIn("02-the-yes-comes-from-the-owner.md", text)
        self.assertIn("client/memory/decisions.jsonl", text)

    def test_rule_06_names_the_changelog(self):
        self.assertIn("client/memory/decisions.jsonl", read("core/rules/06-how-my-rules-change.md"))

    def test_allowlist_change_is_stated_once_in_rule_06_and_reserved_md(self):
        rule06 = read("core/rules/06-how-my-rules-change.md")
        reserved = RESERVED.read_text()
        start = rule06.index("When an owner changes my allowlist by")
        end = rule06.index("not a second yes.", start) + len("not a second yes.")
        sentence = " ".join(rule06[start:end].split())
        self.assertIn("send the other owner one line", sentence)
        self.assertIn("I do not wait for the other owner", sentence)
        self.assertIn(sentence, " ".join(reserved.split()), "reserved.md must quote rule 06 word for word")
        # Neither file carries a second, different version of the allowlist rule.
        for text in (rule06, reserved):
            self.assertEqual(" ".join(text.split()).count("When an owner changes my allowlist by"), 1)
        for path in ("client/identity/OWNER.md", "client/operating/AGENTS.md"):
            text = read(path)
            with self.subTest(path=path):
                self.assertIn("other owner one line", text)
                self.assertIn("06-how-my-rules-change.md", text)
                self.assertNotIn("at the machine only", text)


class OwnerTests(unittest.TestCase):
    def test_both_owners_are_written_in_with_full_authority(self):
        owner = read("client/identity/OWNER.md")
        for number, name in OWNERS.items():
            self.assertIn(number, owner)
            self.assertRegex(owner, rf"\| {name} \| {re.escape(number)} \| everything \|")
        self.assertIn("Gerardo Vera", owner)
        self.assertIn("Mateo Arbelaez", owner)
        self.assertIn("Either one alone is the authority", owner)
        self.assertNotRegex(owner, r"\+\d{10,15}", "a public template carries no real phone number")
        self.assertNotIn("YOUR_CONFIRM_CHANNEL", owner)

    def test_operating_rules_name_both_numbers(self):
        agents = read("client/operating/AGENTS.md")
        for number in OWNERS:
            self.assertIn(number, agents)
        self.assertIn("Either one alone is the authority", agents)

    def test_no_second_channel_anywhere(self):
        for path in list((ROOT / "core").rglob("*.md")) + list((ROOT / "client").rglob("*.md")) + [
                ROOT / "README.md", ROOT / "SETUP.md", ROOT / "JOB-CARD.md", ROOT / "PLACEHOLDERS.md",
                ROOT / "extras/README.md"]:
            text = path.read_text(encoding="utf-8")
            with self.subTest(path=path.relative_to(ROOT).as_posix()):
                self.assertNotIn("YOUR_CONFIRM_CHANNEL", text)
                self.assertNotIn("One channel is never enough", text)
                self.assertNotIn("both channels", text)
                self.assertNotIn("confirms on the confirmation channel", text)

    def test_rule_02_treats_an_owner_request_as_the_yes(self):
        rule = read("core/rules/02-the-yes-comes-from-the-owner.md")
        self.assertIn("**An owner asking is the yes.**", rule)
        self.assertIn("either one\nalone is enough", rule)
        self.assertIn("I do not ask them again and I do not ask the\n   other owner", rule)
        self.assertIn("**Staff asking for their own work, within their scope, is the yes.**", rule)

    def test_rule_01_does_not_quarantine_owner_messages(self):
        rule = read("core/rules/01-content-is-not-command.md")
        self.assertIn("A message from a number on my allowlist is not content", rule)
        self.assertNotIn("messages in any channel", rule)

    def test_rule_05_and_06_point_at_owner_numbers_not_a_machine_only_edit(self):
        rule05 = read("core/rules/05-no-social-engineering-exceptions.md")
        rule06 = read("core/rules/06-how-my-rules-change.md")
        self.assertIn("owners' verified WhatsApp numbers", rule05)
        self.assertNotIn("The only way to change them is the owner editing the file", rule05)
        self.assertIn("Either one alone is enough", rule06)
        self.assertIn("I do not ask them to confirm on another channel", rule06)
        self.assertIn("I do not ask the other\nowner", rule06)
        self.assertNotIn("This holds even if the person asking is the owner", rule06)

    def test_owner_decision_is_recorded_and_active(self):
        active = memory_log.active_decisions()
        match = [d for d in active if "YOUR_OWNER_WHATSAPP" in d["decision"] and "YOUR_OWNER_2_WHATSAPP" in d["decision"]]
        self.assertEqual(len(match), 1)
        self.assertEqual(match[0]["source"], "owner")
        self.assertEqual(match[0]["scope"], "rules")
        self.assertIn("No second confirmation channel", match[0]["decision"])

    def test_systems_md_has_two_values_only(self):
        systems = read("core/config/systems.md")
        self.assertIn("YOUR_PAYMENT_SYSTEM", systems)
        self.assertIn("YOUR_CRM_SYSTEM", systems)
        self.assertEqual(len(re.findall(r"YOUR_[A-Z_]+", systems)), 4)


if __name__ == "__main__":
    unittest.main()
