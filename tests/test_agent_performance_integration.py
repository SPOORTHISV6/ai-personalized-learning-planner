
import unittest

from app.agents.performance_rules import (
    classify_performance,
    priority_for_level,
)
from app.agents.study_plan_agent import (
    build_topic_lookup,
    study_plan_agent,
)


class TestStudyPlanAgentPerformance(unittest.TestCase):

    def test_topic_lookup_classifies_boundary_scores(self):
        memory = {
            "latest_performance": [
                {"topic_id": 101, "topic_name": "Topic 1", "score": 49.99},
                {"topic_id": 102, "topic_name": "Topic 2", "score": 50},
                {"topic_id": 103, "topic_name": "Topic 3", "score": 74.99},
                {"topic_id": 104, "topic_name": "Topic 4", "score": 75},
            ]
        }

        lookup = build_topic_lookup([], memory)

        expected = {
            101: ("weak", "high"),
            102: ("moderate", "medium"),
            103: ("moderate", "medium"),
            104: ("strong", "low"),
        }

        for topic_id, (status, priority) in expected.items():
            with self.subTest(topic_id=topic_id):
                self.assertEqual(lookup[topic_id]["status"], status)
                self.assertEqual(lookup[topic_id]["priority"], priority)

    def test_study_plan_selects_weak_and_moderate_topics(self):
        state = {
            "student_profile": {
                "student_id": 999,
                "daily_available_hours": 4,
                "learning_preference": "Practice",
            },
            "learning_gaps": [
                {
                    "topic_id": 201,
                    "topic_name": "Weak Topic",
                    "score": 40,
                    "status": "weak",
                    "priority": "high",
                    "prerequisite_topic_id": None,
                },
                {
                    "topic_id": 202,
                    "topic_name": "Moderate Topic",
                    "score": 60,
                    "status": "moderate",
                    "priority": "medium",
                    "prerequisite_topic_id": None,
                },
                {
                    "topic_id": 203,
                    "topic_name": "Strong Topic",
                    "score": 90,
                    "status": "strong",
                    "priority": "low",
                    "prerequisite_topic_id": None,
                },
            ],
            "resources": [],
            "student_memory": {},
        }

        result = study_plan_agent(state)

        self.assertEqual(result["next_action"], "validation")

        plan = result["study_plan"]
        self.assertEqual(plan["total_sessions"], 2)

        sessions = {
            session["topic_id"]: session
            for session in plan["sessions"]
        }

        self.assertEqual(set(sessions), {201, 202})

        self.assertEqual(sessions[201]["priority"], "high")
        self.assertEqual(sessions[201]["duration_minutes"], 60)

        self.assertEqual(sessions[202]["priority"], "medium")
        self.assertEqual(sessions[202]["duration_minutes"], 45)

        self.assertNotIn(203, sessions)

    def test_shared_rules_match_topic_lookup(self):
        scores = [20, 49.99, 50, 74.99, 75, 100]

        memory = {
            "latest_performance": [
                {
                    "topic_id": index + 1,
                    "topic_name": f"Topic {index + 1}",
                    "score": score,
                }
                for index, score in enumerate(scores)
            ]
        }

        lookup = build_topic_lookup([], memory)

        for index, score in enumerate(scores):
            topic_id = index + 1
            level = classify_performance(score)

            with self.subTest(score=score):
                self.assertEqual(lookup[topic_id]["status"], level)
                self.assertEqual(
                    lookup[topic_id]["priority"],
                    priority_for_level(level),
                )


if __name__ == "__main__":
    unittest.main(verbosity=2)
