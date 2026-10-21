
import unittest


def classify_performance(score):
    """Match the performance thresholds used by the project."""
    if score < 50:
        return "weak"
    elif score < 75:
        return "moderate"
    return "strong"


def priority_for_level(level):
    """Convert performance level to the expected priority."""
    priorities = {
        "weak": 5,
        "moderate": 3,
        "strong": 1,
    }
    return priorities[level]


class TestPerformanceRules(unittest.TestCase):

    def test_weak_performance(self):
        self.assertEqual(classify_performance(40), "weak")
        self.assertEqual(priority_for_level("weak"), 5)

    def test_moderate_performance(self):
        self.assertEqual(classify_performance(60), "moderate")
        self.assertEqual(priority_for_level("moderate"), 3)

    def test_strong_performance(self):
        self.assertEqual(classify_performance(90), "strong")
        self.assertEqual(priority_for_level("strong"), 1)

    def test_boundary_scores(self):
        self.assertEqual(classify_performance(0), "weak")
        self.assertEqual(classify_performance(49.99), "weak")
        self.assertEqual(classify_performance(50), "moderate")
        self.assertEqual(classify_performance(74.99), "moderate")
        self.assertEqual(classify_performance(75), "strong")
        self.assertEqual(classify_performance(100), "strong")

    def test_invalid_priority_level(self):
        with self.assertRaises(KeyError):
            priority_for_level("unknown")


if __name__ == "__main__":
    unittest.main(verbosity=2)
