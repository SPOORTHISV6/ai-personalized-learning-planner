
import logging

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


logger = logging.getLogger(__name__)

MAX_VALIDATION_RETRIES = 2

ALLOWED_VALIDATION_ACTIONS = {"complete", "replan", "stop"}


def _failure_result(message: str) -> dict:
    """Return a safe workflow failure update."""

    return {
        "workflow_failed": True,
        "next_action": "stop",
        "errors": [message],
    }


def _sanitize_agent_result(raw_result, allowed_actions) -> dict:
    """Validate an agent's output before merging it into workflow state."""

    if not isinstance(raw_result, dict):
        return _failure_result("Agent returned an invalid result.")

    result = dict(raw_result)
    action = result.get("next_action", "stop")

    if not isinstance(action, str) or action not in allowed_actions:
        result["next_action"] = "stop"
        result["workflow_failed"] = True
        result["errors"] = [
            "Agent returned an unsupported workflow action."
        ]
    else:
        result["next_action"] = action

    return result


def _run_pipeline_agent(
    agent,
    state: LearningState,
    agent_name: str,
    expected_action: str,
) -> dict:
    """
    Run a pipeline agent safely.

    A successful result must be a dictionary. If next_action is supplied,
    it must either be the expected next node or stop. If omitted, the
    expected next action is assigned explicitly.
    """

    try:
        raw_result = agent(state)

        if not isinstance(raw_result, dict):
            logger.error(
                "[Workflow] %s returned a non-dictionary result.",
                agent_name,
            )
            return _failure_result(
                f"{agent_name} returned an invalid result."
            )

        result = dict(raw_result)
        action = result.get("next_action")

        if action is None:
            result["next_action"] = expected_action

        elif not isinstance(action, str):
            logger.error(
                "[Workflow] %s returned an invalid action type.",
                agent_name,
            )
            return _failure_result(
                f"{agent_name} returned an invalid workflow action."
            )

        elif action == "stop":
            result["workflow_failed"] = True
            result["next_action"] = "stop"

        elif action != expected_action:
            logger.error(
                "[Workflow] %s returned an unexpected action.",
                agent_name,
            )
            return _failure_result(
                f"{agent_name} returned an unsupported workflow action."
            )

        return result

    except Exception as exc:
        logger.exception(
            "[Workflow] %s failed: %s",
            agent_name,
            type(exc).__name__,
        )
        return _failure_result(f"{agent_name} failed.")


def safe_memory_agent(state: LearningState) -> dict:
    return _run_pipeline_agent(
        memory_agent,
        state,
        "Memory Agent",
        "profile",
    )


def safe_profile_agent(state: LearningState) -> dict:
    return _run_pipeline_agent(
        profile_agent,
        state,
        "Profile Agent",
        "learning_gap",
    )


def safe_learning_gap_agent(state: LearningState) -> dict:
    return _run_pipeline_agent(
        learning_gap_agent,
        state,
        "Learning Gap Agent",
        "resource",
    )


def safe_resource_agent(state: LearningState) -> dict:
    return _run_pipeline_agent(
        resource_agent,
        state,
        "Resource Agent",
        "study_plan",
    )


def safe_study_plan_agent(state: LearningState) -> dict:
    return _run_pipeline_agent(
        study_plan_agent,
        state,
        "Study Plan Agent",
        "validation",
    )


def safe_evaluation_agent(state: LearningState) -> dict:
    try:
        result = evaluation_agent(state)

    except Exception as exc:
        logger.exception(
            "[Workflow] Evaluation Agent failed: %s",
            type(exc).__name__,
        )
        return _failure_result("Evaluation agent failed.")

    return _sanitize_agent_result(
        result,
        {"reflection", "stop"},
    )


def safe_reflection_agent(state: LearningState) -> dict:
    try:
        result = reflection_agent(state)

    except Exception as exc:
        logger.exception(
            "[Workflow] Reflection Agent failed: %s",
            type(exc).__name__,
        )
        return _failure_result("Reflection agent failed.")

    return _sanitize_agent_result(
        result,
        {"replan", "complete", "stop"},
    )


def safe_persistence_agent(state: LearningState) -> dict:
    try:
        result = persistence_agent(state)

    except Exception as exc:
        logger.exception(
            "[Workflow] Persistence Agent failed: %s",
            type(exc).__name__,
        )
        return _failure_result("Persistence agent failed.")

    return _sanitize_agent_result(
        result,
        {"complete", "stop"},
    )


def run_session_lifecycle(state: LearningState) -> dict:
    """Execute a session lifecycle operation safely."""

    from app.agents.session_lifecycle_agent import (
        session_lifecycle_agent,
    )

    try:
        result = session_lifecycle_agent(state)

        if not isinstance(result, dict):
            logger.error(
                "[Workflow] Session Lifecycle Agent returned invalid data."
            )
            return _failure_result(
                "Session lifecycle agent returned an invalid result."
            )

        return result

    except Exception as exc:
        logger.exception(
            "[Workflow] Session Lifecycle Agent failed: %s",
            type(exc).__name__,
        )
        return _failure_result(
            "Session lifecycle operation failed."
        )


def validation_with_retry(state: LearningState) -> dict:
    """Validate a study plan with at most two replanning attempts."""

    if not isinstance(state, dict):
        return {
            "validation": {
                "valid": False,
                "errors": ["Invalid workflow state."],
            },
            "next_action": "stop",
            "workflow_failed": True,
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
            "workflow_failed": True,
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
            "workflow_failed": True,
        }

    try:
        raw_result = validation_agent(state)

    except Exception as exc:
        logger.exception(
            "[Workflow] Validation Agent failed: %s",
            type(exc).__name__,
        )
        return {
            "validation": {
                "valid": False,
                "errors": ["Study plan validation failed."],
            },
            "validation_retry_count": retry_count,
            "next_action": "stop",
            "workflow_failed": True,
        }

    if not isinstance(raw_result, dict):
        return {
            "validation": {
                "valid": False,
                "errors": [
                    "Validation agent returned an invalid result."
                ],
            },
            "validation_retry_count": retry_count,
            "next_action": "stop",
            "workflow_failed": True,
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
            "workflow_failed": True,
        }

    validation = result.get("validation")

    # A replan result may omit validation details.
    # Preserve the retry contract with a safe default.
    if validation is None and action == "replan":
        validation = {
            "valid": False,
            "errors": ["Study plan requires replanning."],
        }
        result["validation"] = validation

    elif not isinstance(validation, dict):
        return {
            "validation": {
                "valid": False,
                "errors": [
                    "Validation agent returned invalid validation data."
                ],
            },
            "validation_retry_count": retry_count,
            "next_action": "stop",
            "workflow_failed": True,
        }

    is_valid = validation.get("valid")

    if not isinstance(is_valid, bool):
        return {
            "validation": {
                "valid": False,
                "errors": [
                    "Validation agent returned an invalid validity flag."
                ],
            },
            "validation_retry_count": retry_count,
            "next_action": "stop",
            "workflow_failed": True,
        }

    # An invalid plan must never proceed to persistence.
    if action == "complete" and not is_valid:
        return {
            "validation": {
                "valid": False,
                "errors": [
                    "Invalid study plan cannot be marked complete."
                ],
            },
            "validation_retry_count": retry_count,
            "next_action": "stop",
            "workflow_failed": True,
        }

    # A valid plan should not request another planning attempt.
    if action == "replan" and is_valid:
        return {
            "validation": {
                "valid": False,
                "errors": [
                    "A valid study plan cannot request replanning."
                ],
            },
            "validation_retry_count": retry_count,
            "next_action": "stop",
            "workflow_failed": True,
        }

    if action == "replan":

        if retry_count >= MAX_VALIDATION_RETRIES:
            result["next_action"] = "stop"

            validation = dict(validation)
            validation["retry_limit_reached"] = True
            validation["retry_message"] = (
                "Study plan remained invalid after "
                f"{MAX_VALIDATION_RETRIES} replanning attempts. "
                "Workflow stopped."
            )

            result["validation"] = validation
            result["validation_retry_count"] = retry_count

            logger.warning(
                "[Workflow] Maximum validation retries reached."
            )

        else:
            result["validation_retry_count"] = retry_count + 1

            logger.info(
                "[Workflow] Replanning attempt %s/%s.",
                retry_count + 1,
                MAX_VALIDATION_RETRIES,
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

    if not isinstance(action, str):
        return "stop"

    return action if action in {"reflection", "stop"} else "stop"


def route_reflection(state: LearningState) -> str:
    if not isinstance(state, dict):
        return "stop"

    action = state.get("next_action", "stop")

    if not isinstance(action, str):
        return "stop"

    return (
        action
        if action in {"replan", "complete", "stop"}
        else "stop"
    )


def route_persistence(state: LearningState) -> str:
    if not isinstance(state, dict):
        return "stop"

    action = state.get("next_action", "stop")

    if not isinstance(action, str):
        return "stop"

    return action if action in {"complete", "stop"} else "stop"


def route_pipeline_node(
    state: LearningState,
    expected_action: str,
) -> str:
    """Continue only when the preceding pipeline agent succeeded."""

    if not isinstance(state, dict):
        return "stop"

    if state.get("workflow_failed") is True:
        return "stop"

    action = state.get("next_action")

    if not isinstance(action, str):
        return "stop"

    if action == "stop":
        return "stop"

    return "continue" if action == expected_action else "stop"


def route_validation(state: LearningState) -> str:
    """Route validated plans to persistence and invalid plans to replanning."""

    if not isinstance(state, dict):
        return "stop"

    if state.get("workflow_failed") is True:
        return "stop"

    action = state.get("next_action", "stop")

    if not isinstance(action, str):
        return "stop"

    return (
        action
        if action in ALLOWED_VALIDATION_ACTIONS
        else "stop"
    )


def build_adaptive_workflow():
    workflow = StateGraph(LearningState)

    # 1. Adaptive learning agents.
    workflow.add_node("evaluation", safe_evaluation_agent)
    workflow.add_node("reflection", safe_reflection_agent)

    workflow.add_node("memory", safe_memory_agent)
    workflow.add_node("profile", safe_profile_agent)
    workflow.add_node("learning_gap", safe_learning_gap_agent)
    workflow.add_node("resource", safe_resource_agent)
    workflow.add_node("study_plan", safe_study_plan_agent)

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

    # 7. Safe adaptive replanning pipeline.
    workflow.add_conditional_edges(
        "memory",
        lambda state: route_pipeline_node(state, "profile"),
        {
            "continue": "profile",
            "stop": END,
        },
    )

    workflow.add_conditional_edges(
        "profile",
        lambda state: route_pipeline_node(state, "learning_gap"),
        {
            "continue": "learning_gap",
            "stop": END,
        },
    )

    workflow.add_conditional_edges(
        "learning_gap",
        lambda state: route_pipeline_node(state, "resource"),
        {
            "continue": "resource",
            "stop": END,
        },
    )

    workflow.add_conditional_edges(
        "resource",
        lambda state: route_pipeline_node(state, "study_plan"),
        {
            "continue": "study_plan",
            "stop": END,
        },
    )

    workflow.add_conditional_edges(
        "study_plan",
        lambda state: route_pipeline_node(state, "validation"),
        {
            "continue": "validation",
            "stop": END,
        },
    )

    # 8. Validation routing.
    workflow.add_conditional_edges(
        "validation",
        route_validation,
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
