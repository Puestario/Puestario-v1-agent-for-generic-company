"""JOB-CARD.md carries the discovery script and it is a script, not a mood."""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class JobCardTests(unittest.TestCase):
    def setUp(self):
        text = (ROOT / "JOB-CARD.md").read_text(encoding="utf-8")
        start = text.index("## 0. How we pick the job")
        end = text.index("## 1. Every connector")
        self.section = text[start:end]
        self.text = text

    def test_section_comes_first_and_is_short(self):
        self.assertLess(self.text.index("## 0. How we pick the job"), self.text.index("## 1."))
        self.assertLess(len(self.section.split()), 900)

    def test_six_questions_in_order_each_with_a_push_and_a_red_flag(self):
        questions = re.findall(r"\*\*Q(\d)\. ([^*]+)\*\* \*\"", self.section)
        self.assertEqual([int(n) for n, _ in questions], [1, 2, 3, 4, 5, 6])
        blocks = re.split(r"\*\*Q\d\. ", self.section)[1:]
        for block in blocks:
            with self.subTest(question=block[:30]):
                self.assertTrue("Push until" in block or "The installer does this" in block)
                self.assertIn("Red flag", block)

    def test_ends_with_one_job_on_one_line(self):
        self.assertIn("**End with the one job.**", self.section)
        self.assertIn("> **The job:**", self.section)
        self.assertIn("Do not skip Q3", self.section)

    def test_no_softened_phrases(self):
        for phrase in ("interesting approach", "many ways to think about", "you might want to consider"):
            self.assertNotIn(phrase, self.section.lower())

    def test_ties_into_the_rest_of_the_card(self):
        for ref in ("section 1", "section 3", "section 6"):
            self.assertIn(ref, self.section)
        self.assertNotIn("YOUR_", self.section)


if __name__ == "__main__":
    unittest.main()
