
import importlib

import pytest


workflow_module = importlib.import_module(
    "app.workflows.adaptive_workflow"
)


class TestPipelineAgentWrappers:

    @pytest.mark.parametrize(
        "wrapper_name",
        [
            "safe_memory_agent",
            "safe_profile_agent",
            "safe_learning_gap_agent",
            "safe_resource_agent",
            "safe_study_plan_agent",
        ],
    )
    def test_pipeline_agent_exception_stops_workflow(
        self,
        monkeypatch,
        wrapper_name,
    ):
        def failing_agent(state):
            raise RuntimeError("Internal database details")

        monkeypatch.setattr(
            workflow_module,
            wrapper_name.replace("safe_", ""),
            failing_agent,
        )

        wrapper = getattr(workflow_module, wrapper_name)
        result = wrapper({"student_id": 1})

        assert result["next_action"] == "stop"
        assert result["workflow_failed"] is True
        assert result["errors"]
        assert "Internal database details" not in str(result)

    @pytest.mark.parametrize(
        "wrapper_name",
        [
            "safe_memory_agent",
            "safe_profile_agent",
            "safe_learning_gap_agent",
            "safe_resource_agent",
            "safe_study_plan_agent",
        ],
    )
    def test_pipeline_agent_non_dict_result_stops_workflow(
        self,
        monkeypatch,
        wrapper_name,
    ):
        def invalid_agent(state):
            return ["invalid", "result"]

        monkeypatch.setattr(
            workflow_module,
            wrapper_name.replace("safe_", ""),
            invalid_agent,
        )

        wrapper = getattr(workflow_module, wrapper_name)
        result = wrapper({"student_id": 1})

        assert result["next_action"] == "stop"
        assert result["workflow_failed"] is True

    def test_pipeline_agent_missing_action_gets_expected_action(
        self,
        monkeypatch,
    ):
        monkeypatch.setattr(
            workflow_module,
            "memory_agent",
            lambda state: {"student_memory": {}},
        )

        result = workflow_module.safe_memory_agent(
            {"student_id": 1}
        )

        assert result["next_action"] == "profile"
        assert result.get("workflow_failed") is not True

    def test_pipeline_agent_unexpected_action_stops_workflow(
        self,
        monkeypatch,
    ):
        monkeypatch.setattr(
            workflow_module,
            "memory_agent",
            lambda state: {"next_action": "complete"},
        )

        result = workflow_module.safe_memory_agent(
            {"student_id": 1}
        )

        assert result["next_action"] == "stop"
        assert result["workflow_failed"] is True


class TestPipelineRouting:

    def test_failed_workflow_routes_to_stop(self):
        state = {
            "workflow_failed": True,
            "next_action": "profile",
        }

        assert (
            workflow_module.route_pipeline_node(state, "profile")
            == "stop"
        )

    def test_valid_pipeline_action_continues(self):
        state = {
            "workflow_failed": False,
            "next_action": "profile",
        }

        assert (
            workflow_module.route_pipeline_node(state, "profile")
            == "continue"
        )

    def test_unexpected_pipeline_action_stops(self):
        state = {"next_action": "complete"}

        assert (
            workflow_module.route_pipeline_node(state, "profile")
            == "stop"
        )

    def test_unhashable_evaluation_action_stops(self):
        assert workflow_module.route_evaluation(
            {"next_action": []}
        ) == "stop"

    def test_unhashable_reflection_action_stops(self):
        assert workflow_module.route_reflection(
            {"next_action": {}}
        ) == "stop"

    def test_unhashable_persistence_action_stops(self):
        assert workflow_module.route_persistence(
            {"next_action": []}
        ) == "stop"

    def test_unhashable_validation_action_stops(self):
        assert workflow_module.route_validation(
            {"next_action": []}
        ) == "stop"


class TestSessionLifecycleWrapper:

    def test_session_lifecycle_exception_returns_safe_failure(
        self,
        monkeypatch,
    ):
        def failing_lifecycle(state):
            raise RuntimeError("Sensitive internal error")

        module = importlib.import_module(
            "app.agents.session_lifecycle_agent"
        )

        monkeypatch.setattr(
            module,
            "session_lifecycle_agent",
            failing_lifecycle,
        )

        result = workflow_module.run_session_lifecycle(
            {"student_id": 1}
        )

        assert result["next_action"] == "stop"
        assert result["workflow_failed"] is True
        assert "Sensitive internal error" not in str(result)

    def test_session_lifecycle_invalid_result_stops(
        self,
        monkeypatch,
    ):
        module = importlib.import_module(
            "app.agents.session_lifecycle_agent"
        )

        monkeypatch.setattr(
            module,
            "session_lifecycle_agent",
            lambda state: None,
        )

        result = workflow_module.run_session_lifecycle(
            {"student_id": 1}
        )

        assert result["next_action"] == "stop"
        assert result["workflow_failed"] is True


class TestValidationWorkflowConsistency:

    def test_invalid_plan_cannot_route_to_persistence(
        self,
        monkeypatch,
    ):
        monkeypatch.setattr(
            workflow_module,
            "validation_agent",
            lambda state: {
                "validation": {
                    "valid": False,
                    "errors": ["Invalid plan"],
                },
                "next_action": "complete",
            },
        )

        result = workflow_module.validation_with_retry(
            {"validation_retry_count": 0}
        )

        assert result["next_action"] == "stop"
        assert result["workflow_failed"] is True

    def test_valid_plan_cannot_request_replanning(
        self,
        monkeypatch,
    ):
        monkeypatch.setattr(
            workflow_module,
            "validation_agent",
            lambda state: {
                "validation": {
                    "valid": True,
                    "errors": [],
                },
                "next_action": "replan",
            },
        )

        result = workflow_module.validation_with_retry(
            {"validation_retry_count": 0}
        )

        assert result["next_action"] == "stop"
        assert result["workflow_failed"] is True

    def test_validation_retry_limit_remains_two(
        self,
        monkeypatch,
    ):
        monkeypatch.setattr(
            workflow_module,
            "validation_agent",
            lambda state: {
                "validation": {
                    "valid": False,
                    "errors": ["Invalid plan"],
                },
                "next_action": "replan",
            },
        )

        first = workflow_module.validation_with_retry(
            {"validation_retry_count": 0}
        )
        second = workflow_module.validation_with_retry(
            {"validation_retry_count": 1}
        )
        third = workflow_module.validation_with_retry(
            {"validation_retry_count": 2}
        )

        assert first["validation_retry_count"] == 1
        assert second["validation_retry_count"] == 2
        assert third["next_action"] == "stop"
        assert third["validation"]["retry_limit_reached"] is True


class TestWorkflowCompilation:

    def test_adaptive_workflow_compiles(self):
        compiled = workflow_module.build_adaptive_workflow()

        assert compiled is not None
