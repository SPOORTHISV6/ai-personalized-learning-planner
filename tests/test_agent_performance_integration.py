import unittest
from unittest.mock import patch

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

    @patch(
        "app.agents.study_plan_agent.get_owned_topic_ids",
        return_value={201, 202, 203},
    )
    def test_study_plan_selects_weak_and_moderate_topics(
        self,
        mock_owned_topics,
    ):
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

    @patch(
        "app.agents.study_plan_agent.get_owned_topic_ids",
        return_value={
            "topic_ids": {301, 302},
            "topic_difficulties": {},
            "topic_details": {
                301: {
                    "topic_name": "SQL Basics",
                    "prerequisite_topic_id": None,
                },
                302: {
                    "topic_name": "SQL Joins",
                    "prerequisite_topic_id": 301,
                },
            },
        },
    )
    def test_unassessed_prerequisite_is_scheduled_first(
        self,
        mock_owned_topics,
    ):
        state = {
            "student_profile": {
                "student_id": 999,
                "daily_available_hours": 4,
                "learning_preference": "Practice",
            },
            "learning_gaps": [
                {
                    "topic_id": 302,
                    "topic_name": "SQL Joins",
                    "score": 40,
                    "status": "weak",
                    "priority": "high",
                    "prerequisite_topic_id": 301,
                }
            ],
            "resources": [],
            "student_memory": {
                "latest_performance": []
            },
        }

        result = study_plan_agent(state)

        self.assertEqual(result["next_action"], "validation")

        plan = result["study_plan"]
        self.assertEqual(plan["total_sessions"], 2)

        sessions = plan["sessions"]

        self.assertEqual(sessions[0]["topic_id"], 301)
        self.assertEqual(
            sessions[0]["session_type"],
            "prerequisite_revision",
        )
        self.assertIsNone(sessions[0]["score"])
        self.assertEqual(
            sessions[0]["learning_status"],
            "not_assessed",
        )
        self.assertEqual(sessions[0]["priority"], "high")

        self.assertEqual(sessions[1]["topic_id"], 302)
        self.assertEqual(
            sessions[1]["session_type"],
            "target_topic",
        )


    @patch(
        "app.agents.study_plan_agent.get_owned_topic_ids",
        return_value={
            "topic_ids": {301, 302},
            "topic_difficulties": {},
            "topic_details": {
                301: {
                    "topic_name": "SQL Basics",
                    "prerequisite_topic_id": None,
                },
                302: {
                    "topic_name": "SQL Joins",
                    "prerequisite_topic_id": 301,
                },
            },
        },
    )
    def test_weak_assessed_prerequisite_is_scheduled_first(
        self,
        mock_owned_topics,
    ):
        state = {
            "student_profile": {
                "student_id": 999,
                "daily_available_hours": 4,
                "learning_preference": "Practice",
            },
            "learning_gaps": [
                {
                    "topic_id": 302,
                    "topic_name": "SQL Joins",
                    "score": 40,
                    "prerequisite_topic_id": 301,
                },
                {
                    "topic_id": 301,
                    "topic_name": "SQL Basics",
                    "score": 40,
                    "prerequisite_topic_id": None,
                },
            ],
            "resources": [],
            "student_memory": {},
        }

        result = study_plan_agent(state)
        sessions = result["study_plan"]["sessions"]

        self.assertEqual(len(sessions), 2)
        self.assertEqual(sessions[0]["topic_id"], 301)
        self.assertEqual(
            sessions[0]["session_type"],
            "prerequisite_revision",
        )
        self.assertEqual(sessions[0]["score"], 40.0)
        self.assertEqual(sessions[1]["topic_id"], 302)

    @patch(
        "app.agents.study_plan_agent.get_owned_topic_ids",
        return_value={
            "topic_ids": {301, 302},
            "topic_difficulties": {},
            "topic_details": {
                301: {
                    "topic_name": "SQL Basics",
                    "prerequisite_topic_id": None,
                },
                302: {
                    "topic_name": "SQL Joins",
                    "prerequisite_topic_id": 301,
                },
            },
        },
    )
    def test_strong_prerequisite_does_not_get_revision_session(
        self,
        mock_owned_topics,
    ):
        state = {
            "student_profile": {
                "student_id": 999,
                "daily_available_hours": 4,
                "learning_preference": "Practice",
            },
            "learning_gaps": [
                {
                    "topic_id": 302,
                    "topic_name": "SQL Joins",
                    "score": 40,
                    "prerequisite_topic_id": 301,
                },
            ],
            "resources": [],
            "student_memory": {
                "latest_performance": [
                    {
                        "topic_id": 301,
                        "topic_name": "SQL Basics",
                        "score": 85,
                    }
                ]
            },
        }

        result = study_plan_agent(state)
        sessions = result["study_plan"]["sessions"]

        self.assertEqual(len(sessions), 1)
        self.assertEqual(sessions[0]["topic_id"], 302)
        self.assertEqual(
            sessions[0]["session_type"],
            "target_topic",
        )

    @patch(
        "app.agents.study_plan_agent.get_owned_topic_ids",
        return_value={
            "topic_ids": {302},
            "topic_difficulties": {},
            "topic_details": {
                302: {
                    "topic_name": "SQL Joins",
                    "prerequisite_topic_id": 301,
                },
            },
        },
    )
    def test_unowned_prerequisite_is_not_scheduled(
        self,
        mock_owned_topics,
    ):
        state = {
            "student_profile": {
                "student_id": 999,
                "daily_available_hours": 4,
                "learning_preference": "Practice",
            },
            "learning_gaps": [
                {
                    "topic_id": 302,
                    "topic_name": "SQL Joins",
                    "score": 40,
                    "prerequisite_topic_id": 301,
                },
            ],
            "resources": [],
            "student_memory": {},
        }

        result = study_plan_agent(state)
        sessions = result["study_plan"]["sessions"]

        self.assertEqual(len(sessions), 1)
        self.assertEqual(sessions[0]["topic_id"], 302)
        self.assertNotIn(
            301,
            [session["topic_id"] for session in sessions],
        )

    @patch(
        "app.agents.study_plan_agent.get_owned_topic_ids",
        return_value={
            "topic_ids": {301, 302, 303},
            "topic_difficulties": {},
            "topic_details": {
                301: {
                    "topic_name": "SQL Basics",
                    "prerequisite_topic_id": None,
                },
                302: {
                    "topic_name": "SQL Joins",
                    "prerequisite_topic_id": 301,
                },
                303: {
                    "topic_name": "SQL Subqueries",
                    "prerequisite_topic_id": 301,
                },
            },
        },
    )
    def test_shared_prerequisite_is_scheduled_only_once(
        self,
        mock_owned_topics,
    ):
        state = {
            "student_profile": {
                "student_id": 999,
                "daily_available_hours": 4,
                "learning_preference": "Practice",
            },
            "learning_gaps": [
                {
                    "topic_id": 302,
                    "topic_name": "SQL Joins",
                    "score": 40,
                    "prerequisite_topic_id": 301,
                },
                {
                    "topic_id": 303,
                    "topic_name": "SQL Subqueries",
                    "score": 60,
                    "prerequisite_topic_id": 301,
                },
            ],
            "resources": [],
            "student_memory": {},
        }

        result = study_plan_agent(state)
        sessions = result["study_plan"]["sessions"]

        topic_ids = [
            session["topic_id"]
            for session in sessions
        ]

        self.assertEqual(len(sessions), 3)
        self.assertEqual(topic_ids.count(301), 1)
        self.assertEqual(topic_ids.count(302), 1)
        self.assertEqual(topic_ids.count(303), 1)

        self.assertEqual(
            sessions[0]["session_type"],
            "prerequisite_revision",
        )


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
