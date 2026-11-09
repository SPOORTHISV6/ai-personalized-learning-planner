
from langgraph.graph import StateGraph, START, END

from app.workflows.state import LearningState

from app.agents.evaluation_agent import evaluation_agent
from app.agents.reflection_agent import reflection_agent
from app.agents.memory_agent import memory_agent
from app.agents.profile_agent import profile_agent
from app.agents.learning_gap_agent import learning_gap_agent
from app.agents.resource_agent import resource_agent
from app.agents.study_plan_agent import study_plan_agent
from app.agents.validation_agent import validation_agent
from app.agents.persistence_agent import persistence_agent


MAX_VALIDATION_RETRIES = 2

ALLOWED_VALIDATION_ACTIONS = {"complete", "replan", "stop"}


def _sanitize_agent_result(raw_result, allowed_actions):
    """Validate an agent's output before merging it into workflow state."""

    if not isinstance(raw_result, dict):
        return {
            "next_action": "stop",
            "errors": ["Agent returned an invalid result."],
        }

    result = dict(raw_result)
    action = result.get("next_action", "stop")

    if not isinstance(action, str) or action not in allowed_actions:
        result["next_action"] = "stop"

        # Do not expose the unsupported action in workflow errors.
        result["errors"] = [
            "Agent returned an unsupported workflow action."
        ]

    return result


def safe_evaluation_agent(state: LearningState) -> dict:
    try:
        result = evaluation_agent(state)
    except Exception:
        return {
            "next_action": "stop",
            "errors": ["Evaluation agent failed."],
        }

    return _sanitize_agent_result(
        result,
        {"reflection", "stop"},
    )


def safe_reflection_agent(state: LearningState) -> dict:
    try:
        result = reflection_agent(state)
    except Exception:
        return {
            "next_action": "stop",
            "errors": ["Reflection agent failed."],
        }

    return _sanitize_agent_result(
        result,
        {"replan", "complete", "stop"},
    )


def safe_persistence_agent(state: LearningState) -> dict:
    try:
        result = persistence_agent(state)
    except Exception:
        return {
            "next_action": "stop",
            "errors": ["Persistence agent failed."],
        }

    return _sanitize_agent_result(
        result,
        {"complete", "stop"},
    )


def run_session_lifecycle(state: LearningState) -> dict:
    """Execute a session lifecycle operation."""

    from app.agents.session_lifecycle_agent import (
        session_lifecycle_agent,
    )

    return session_lifecycle_agent(state)


def validation_with_retry(state: LearningState) -> dict:
    """Validate a study plan with at most two replanning attempts."""

    if not isinstance(state, dict):
        return {
            "validation": {
                "valid": False,
                "errors": ["Invalid workflow state."],
            },
            "next_action": "stop",
        }

    retry_count = state.get("validation_retry_count", 0)

    if (
        isinstance(retry_count, bool)
        or not isinstance(retry_count, int)
        or retry_count < 0
    ):
        return {
            "validation": {
                "valid": False,
                "errors": ["Invalid validation retry counter."],
            },
            "next_action": "stop",
        }

    if retry_count > MAX_VALIDATION_RETRIES:
        return {
            "validation": {
                "valid": False,
                "errors": ["Validation retry limit exceeded."],
                "retry_limit_reached": True,
            },
            "validation_retry_count": MAX_VALIDATION_RETRIES,
            "next_action": "stop",
        }

    try:
        raw_result = validation_agent(state)
    except Exception:
        return {
            "validation": {
                "valid": False,
                "errors": ["Study plan validation failed."],
            },
            "validation_retry_count": retry_count,
            "next_action": "stop",
        }

    if not isinstance(raw_result, dict):
        return {
            "validation": {
                "valid": False,
                "errors": ["Validation agent returned an invalid result."],
            },
            "validation_retry_count": retry_count,
            "next_action": "stop",
        }

    result = dict(raw_result)
    action = result.get("next_action", "stop")

    if (
        not isinstance(action, str)
        or action not in ALLOWED_VALIDATION_ACTIONS
    ):
        return {
            "validation": {
                "valid": False,
                "errors": [
                    "Validation agent returned an unsupported action."
                ],
            },
            "validation_retry_count": retry_count,
            "next_action": "stop",
        }

    if action == "replan":

        if retry_count >= MAX_VALIDATION_RETRIES:
            result["next_action"] = "stop"

            validation = result.get("validation")

            if not isinstance(validation, dict):
                validation = {}
            else:
                validation = dict(validation)

            validation["retry_limit_reached"] = True
            validation["retry_message"] = (
                "Study plan remained invalid after "
                f"{MAX_VALIDATION_RETRIES} replanning attempts. "
                "Workflow stopped."
            )

            result["validation"] = validation
            result["validation_retry_count"] = retry_count

            print(
                "[Workflow] Maximum validation retries reached. "
                "Stopping workflow."
            )

        else:
            result["validation_retry_count"] = retry_count + 1

            print(
                "[Workflow] Replanning attempt "
                f"{retry_count + 1}/{MAX_VALIDATION_RETRIES}."
            )

    else:
        result["validation_retry_count"] = retry_count

    return result


def route_workflow(state: LearningState) -> str:
    if not isinstance(state, dict):
        return "evaluation"

    if state.get("workflow_mode") == "session_lifecycle":
        return "session_lifecycle"

    return "evaluation"


def route_evaluation(state: LearningState) -> str:
    if not isinstance(state, dict):
        return "stop"

    action = state.get("next_action", "stop")
    return action if action in {"reflection", "stop"} else "stop"


def route_reflection(state: LearningState) -> str:
    if not isinstance(state, dict):
        return "stop"

    action = state.get("next_action", "complete")
    return (
        action
        if action in {"replan", "complete", "stop"}
        else "stop"
    )


def route_persistence(state: LearningState) -> str:
    if not isinstance(state, dict):
        return "stop"

    action = state.get("next_action", "stop")
    return action if action in {"complete", "stop"} else "stop"


def build_adaptive_workflow():
    workflow = StateGraph(LearningState)

    # 1. Register adaptive learning agents.
    workflow.add_node("evaluation", safe_evaluation_agent)
    workflow.add_node("reflection", safe_reflection_agent)

    workflow.add_node("memory", memory_agent)
    workflow.add_node("profile", profile_agent)
    workflow.add_node("learning_gap", learning_gap_agent)
    workflow.add_node("resource", resource_agent)
    workflow.add_node("study_plan", study_plan_agent)

    # 2. Validation and persistence.
    workflow.add_node("validation", validation_with_retry)
    workflow.add_node("persistence", safe_persistence_agent)

    # 3. Session lifecycle.
    workflow.add_node("session_lifecycle", run_session_lifecycle)

    # 4. Workflow selection.
    workflow.add_conditional_edges(
        START,
        route_workflow,
        {
            "evaluation": "evaluation",
            "session_lifecycle": "session_lifecycle",
        },
    )

    # 5. Evaluation routing.
    workflow.add_conditional_edges(
        "evaluation",
        route_evaluation,
        {
            "reflection": "reflection",
            "stop": END,
        },
    )

    # 6. Reflection routing.
    workflow.add_conditional_edges(
        "reflection",
        route_reflection,
        {
            "replan": "memory",
            "complete": END,
            "stop": END,
        },
    )

    # 7. Adaptive replanning pipeline.
    workflow.add_edge("memory", "profile")
    workflow.add_edge("profile", "learning_gap")
    workflow.add_edge("learning_gap", "resource")
    workflow.add_edge("resource", "study_plan")
    workflow.add_edge("study_plan", "validation")

    # 8. Validation routing.
    workflow.add_conditional_edges(
        "validation",
        lambda state: (
            state.get("next_action", "stop")
            if isinstance(state, dict)
            else "stop"
        ),
        {
            "complete": "persistence",
            "replan": "study_plan",
            "stop": END,
        },
    )

    # 9. Persistence routing.
    workflow.add_conditional_edges(
        "persistence",
        route_persistence,
        {
            "complete": END,
            "stop": END,
        },
    )

    # 10. Session lifecycle termination.
    workflow.add_edge("session_lifecycle", END)

    return workflow.compile()


adaptive_workflow = build_adaptive_workflow()
