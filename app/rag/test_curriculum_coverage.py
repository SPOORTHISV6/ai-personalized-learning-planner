
import unittest

from app.rag.evaluate_curriculum_coverage import (
    normalize_text,
    contains_phrase,
    match_content,
    has_strong_body_evidence,
)


class TestCurriculumCoverageHelpers(unittest.TestCase):

    def test_normalize_text_removes_formatting_differences(self):
        text = "  First   Normal Form (1NF)  "

        result = normalize_text(text)

        self.assertIn("first normal form", result)
        self.assertIn("1nf", result)

    def test_normalize_text_handles_empty_input(self):
        self.assertEqual(normalize_text(""), "")

    def test_contains_phrase_finds_existing_phrase(self):
        text = "A primary key uniquely identifies each row."

        self.assertTrue(
            contains_phrase(text, "primary key")
        )

    def test_contains_phrase_rejects_missing_phrase(self):
        text = "A primary key uniquely identifies each row."

        self.assertFalse(
            contains_phrase(text, "foreign key")
        )

    def test_match_content_finds_relevant_evidence(self):
        content = (
            "Database decomposition divides a relation "
            "into smaller relations."
        )

        results = match_content(
            content,
            ["decomposition", "functional dependency"],
        )

        self.assertTrue(results)
        self.assertTrue(
            any(
                "decomposition" in str(result).lower()
                for result in results
            )
        )

    def test_match_content_returns_no_match_for_unrelated_text(self):
        content = (
            "Python classes contain methods and attributes."
        )

        results = match_content(
            content,
            ["functional dependency", "database decomposition"],
        )

        self.assertEqual(results, [])


class TestStrongBodyEvidence(unittest.TestCase):

    def test_decomposition_with_explanation_is_strong(self):
        text = (
            "Decomposition divides a relation into smaller relations "
            "while aiming for lossless decomposition and "
            "dependency preservation."
        )

        self.assertTrue(
            has_strong_body_evidence("DECOMPOSITION", text)
        )

    def test_keyword_only_decomposition_is_not_strong(self):
        text = "The word decomposition appears in this sentence."

        self.assertFalse(
            has_strong_body_evidence("DECOMPOSITION", text)
        )

    def test_key_with_explanation_is_strong(self):
        text = (
            "A candidate key is a minimal set of attributes "
            "that uniquely identifies each row."
        )

        self.assertTrue(
            has_strong_body_evidence("KEYS", text)
        )

    def test_keyword_only_key_is_not_strong(self):
        text = "This chapter mentions composite key."

        self.assertFalse(
            has_strong_body_evidence("KEYS", text)
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
