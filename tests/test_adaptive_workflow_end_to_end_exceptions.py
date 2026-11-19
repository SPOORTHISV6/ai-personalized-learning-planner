
import importlib
from unittest.mock import Mock


workflow_module = importlib.import_module(
    "app.workflows.adaptive_workflow"
)

lifecycle_module = importlib.import_module(
    "app.agents.session_lifecycle_agent"
)


def prepare_replanning_workflow(monkeypatch):
    """Prepare a controlled adaptive workflow for graph-level tests."""

    monkeypatch.setattr(
        workflow_module,
        "evaluation_agent",
        lambda state: {"next_action": "reflection"},
    )

    monkeypatch.setattr(
        workflow_module,
        "reflection_agent",
        lambda state: {"next_action": "replan"},
    )

    return {
        "student_id": 1,
    }


class TestAdaptiveWorkflowEndToEndFailures:

    def test_memory_failure_prevents_profile_execution(self, monkeypatch):
        state = prepare_replanning_workflow(monkeypatch)

        profile_mock = Mock(
            return_value={"next_action": "learning_gap"}
        )

        def failing_memory(state):
            raise RuntimeError("Memory database failure")

        monkeypatch.setattr(
            workflow_module,
            "memory_agent",
            failing_memory,
        )

        monkeypatch.setattr(
            workflow_module,
            "profile_agent",
            profile_mock,
        )

        graph = workflow_module.build_adaptive_workflow()
        result = graph.invoke(state)

        assert result["workflow_failed"] is True
        assert result["next_action"] == "stop"
        profile_mock.assert_not_called()

    def test_profile_failure_prevents_learning_gap_execution(
        self,
        monkeypatch,
    ):
        state = prepare_replanning_workflow(monkeypatch)

        monkeypatch.setattr(
            workflow_module,
            "memory_agent",
            lambda state: {
                "student_memory": {},
                "next_action": "profile",
            },
        )

        learning_gap_mock = Mock(
            return_value={"next_action": "resource"}
        )

        def failing_profile(state):
            raise RuntimeError("Profile query failure")

        monkeypatch.setattr(
            workflow_module,
            "profile_agent",
            failing_profile,
        )

        monkeypatch.setattr(
            workflow_module,
            "learning_gap_agent",
            learning_gap_mock,
        )

        graph = workflow_module.build_adaptive_workflow()
        result = graph.invoke(state)

        assert result["workflow_failed"] is True
        assert result["next_action"] == "stop"
        learning_gap_mock.assert_not_called()

    def test_learning_gap_failure_prevents_resource_execution(
        self,
        monkeypatch,
    ):
        state = prepare_replanning_workflow(monkeypatch)

        monkeypatch.setattr(
            workflow_module,
            "memory_agent",
            lambda state: {"next_action": "profile"},
        )

        monkeypatch.setattr(
            workflow_module,
            "profile_agent",
            lambda state: {"next_action": "learning_gap"},
        )

        resource_mock = Mock(
            return_value={"next_action": "study_plan"}
        )

        def failing_learning_gap(state):
            raise RuntimeError("Learning gap calculation failed")

        monkeypatch.setattr(
            workflow_module,
            "learning_gap_agent",
            failing_learning_gap,
        )

        monkeypatch.setattr(
            workflow_module,
            "resource_agent",
            resource_mock,
        )

        graph = workflow_module.build_adaptive_workflow()
        result = graph.invoke(state)

        assert result["workflow_failed"] is True
        assert result["next_action"] == "stop"
        resource_mock.assert_not_called()

    def test_resource_failure_prevents_study_plan_execution(
        self,
        monkeypatch,
    ):
        state = prepare_replanning_workflow(monkeypatch)

        monkeypatch.setattr(
            workflow_module,
            "memory_agent",
            lambda state: {"next_action": "profile"},
        )

        monkeypatch.setattr(
            workflow_module,
            "profile_agent",
            lambda state: {"next_action": "learning_gap"},
        )

        monkeypatch.setattr(
            workflow_module,
            "learning_gap_agent",
            lambda state: {"next_action": "resource"},
        )

        study_plan_mock = Mock(
            return_value={"next_action": "validation"}
        )

        def failing_resource(state):
            raise RuntimeError("Resource retrieval failed")

        monkeypatch.setattr(
            workflow_module,
            "resource_agent",
            failing_resource,
        )

        monkeypatch.setattr(
            workflow_module,
            "study_plan_agent",
            study_plan_mock,
        )

        graph = workflow_module.build_adaptive_workflow()
        result = graph.invoke(state)

        assert result["workflow_failed"] is True
        assert result["next_action"] == "stop"
        study_plan_mock.assert_not_called()

    def test_study_plan_failure_prevents_validation_execution(
        self,
        monkeypatch,
    ):
        state = prepare_replanning_workflow(monkeypatch)

        monkeypatch.setattr(
            workflow_module,
            "memory_agent",
            lambda state: {"next_action": "profile"},
        )

        monkeypatch.setattr(
            workflow_module,
            "profile_agent",
            lambda state: {"next_action": "learning_gap"},
        )

        monkeypatch.setattr(
            workflow_module,
            "learning_gap_agent",
            lambda state: {"next_action": "resource"},
        )

        monkeypatch.setattr(
            workflow_module,
            "resource_agent",
            lambda state: {"next_action": "study_plan"},
        )

        validation_mock = Mock(
            return_value={
                "validation": {
                    "valid": True,
                    "errors": [],
                },
                "next_action": "complete",
            }
        )

        def failing_study_plan(state):
            raise RuntimeError("Study plan generation failed")

        monkeypatch.setattr(
            workflow_module,
            "study_plan_agent",
            failing_study_plan,
        )

        monkeypatch.setattr(
            workflow_module,
            "validation_agent",
            validation_mock,
        )

        graph = workflow_module.build_adaptive_workflow()
        result = graph.invoke(state)

        assert result["workflow_failed"] is True
        assert result["next_action"] == "stop"
        validation_mock.assert_not_called()

    def test_validation_failure_prevents_persistence_execution(
        self,
        monkeypatch,
    ):
        state = prepare_replanning_workflow(monkeypatch)

        monkeypatch.setattr(
            workflow_module,
            "memory_agent",
            lambda state: {"next_action": "profile"},
        )

        monkeypatch.setattr(
            workflow_module,
            "profile_agent",
            lambda state: {"next_action": "learning_gap"},
        )

        monkeypatch.setattr(
            workflow_module,
            "learning_gap_agent",
            lambda state: {"next_action": "resource"},
        )

        monkeypatch.setattr(
            workflow_module,
            "resource_agent",
            lambda state: {"next_action": "study_plan"},
        )

        monkeypatch.setattr(
            workflow_module,
            "study_plan_agent",
            lambda state: {"next_action": "validation"},
        )

        persistence_mock = Mock(
            return_value={"next_action": "complete"}
        )

        def failing_validation(state):
            raise RuntimeError("Validation query failed")

        monkeypatch.setattr(
            workflow_module,
            "validation_agent",
            failing_validation,
        )

        monkeypatch.setattr(
            workflow_module,
            "persistence_agent",
            persistence_mock,
        )

        graph = workflow_module.build_adaptive_workflow()
        result = graph.invoke(state)

        assert result["workflow_failed"] is True
        assert result["next_action"] == "stop"
        persistence_mock.assert_not_called()

    def test_persistence_failure_does_not_report_success(
        self,
        monkeypatch,
    ):
        state = prepare_replanning_workflow(monkeypatch)

        monkeypatch.setattr(
            workflow_module,
            "memory_agent",
            lambda state: {"next_action": "profile"},
        )

        monkeypatch.setattr(
            workflow_module,
            "profile_agent",
            lambda state: {"next_action": "learning_gap"},
        )

        monkeypatch.setattr(
            workflow_module,
            "learning_gap_agent",
            lambda state: {"next_action": "resource"},
        )

        monkeypatch.setattr(
            workflow_module,
            "resource_agent",
            lambda state: {"next_action": "study_plan"},
        )

        monkeypatch.setattr(
            workflow_module,
            "study_plan_agent",
            lambda state: {"next_action": "validation"},
        )

        monkeypatch.setattr(
            workflow_module,
            "validation_agent",
            lambda state: {
                "validation": {
                    "valid": True,
                    "errors": [],
                },
                "next_action": "complete",
            },
        )

        def failing_persistence(state):
            raise RuntimeError("Persistence database failure")

        monkeypatch.setattr(
            workflow_module,
            "persistence_agent",
            failing_persistence,
        )

        graph = workflow_module.build_adaptive_workflow()
        result = graph.invoke(state)

        assert result["workflow_failed"] is True
        assert result["next_action"] == "stop"

    def test_session_lifecycle_failure_is_captured_by_graph(
        self,
        monkeypatch,
    ):
        def failing_lifecycle(state):
            raise RuntimeError("Lifecycle database failure")

        monkeypatch.setattr(
            lifecycle_module,
            "session_lifecycle_agent",
            failing_lifecycle,
        )

        graph = workflow_module.build_adaptive_workflow()

        result = graph.invoke(
            {
                "student_id": 1,
                "workflow_mode": "session_lifecycle",
                "session_action": "complete",
                "session_item_id": 1,
            }
        )

        assert result["workflow_failed"] is True
        assert result["next_action"] == "stop"
