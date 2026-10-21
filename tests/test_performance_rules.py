
import unittest

from app.agents.performance_rules import (
    classify_performance,
    evaluate_score,
    priority_for_level,
)


class TestPerformanceRules(unittest.TestCase):

    def test_weak_performance(self):
        self.assertEqual(classify_performance(40), "weak")
        self.assertEqual(priority_for_level("weak"), "high")
        self.assertEqual(
            evaluate_score(40)["recommended_action"],
            "increase_practice",
        )

    def test_moderate_performance(self):
        self.assertEqual(classify_performance(60), "moderate")
        self.assertEqual(priority_for_level("moderate"), "medium")
        self.assertEqual(
            evaluate_score(60)["recommended_action"],
            "continue_practice",
        )

    def test_strong_performance(self):
        self.assertEqual(classify_performance(90), "strong")
        self.assertEqual(priority_for_level("strong"), "low")
        self.assertEqual(
            evaluate_score(90)["recommended_action"],
            "reduce_priority",
        )

    def test_boundary_scores(self):
        test_cases = [
            (0, "weak"),
            (49.99, "weak"),
            (50, "moderate"),
            (74.99, "moderate"),
            (75, "strong"),
            (100, "strong"),
        ]

        for score, expected_level in test_cases:
            with self.subTest(score=score):
                self.assertEqual(
                    classify_performance(score),
                    expected_level,
                )

    def test_invalid_priority_level(self):
        with self.assertRaises(KeyError):
            priority_for_level("unknown")


if __name__ == "__main__":
    unittest.main(verbosity=2)
