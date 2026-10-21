
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


def run_session_lifecycle(state: LearningState) -> dict:
    """
    Execute a session lifecycle operation.

    Import the agent at runtime so tests can mock the function
    without being affected by an earlier module-level import.
    """
    from app.agents.session_lifecycle_agent import (
        session_lifecycle_agent,
    )

    return session_lifecycle_agent(state)


def validation_with_retry(state: LearningState) -> dict:
    """
    Validate a study plan and allow at most two replanning attempts.
    """

    result = dict(validation_agent(state) or {})

    action = result.get(
        "next_action",
        state.get("next_action", "stop"),
    )

    retry_count = int(
        state.get("validation_retry_count", 0) or 0
    )

    if action == "replan":

        if retry_count >= MAX_VALIDATION_RETRIES:
            result["next_action"] = "stop"

            validation = dict(
                result.get("validation")
                or state.get("validation")
                or {}
            )

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
    """
    Route to the requested workflow.

    Default:
        Normal adaptive learning workflow.

    If workflow_mode == 'session_lifecycle':
        Run the session lifecycle agent.
    """

    if state.get("workflow_mode") == "session_lifecycle":
        return "session_lifecycle"

    return "evaluation"


def build_adaptive_workflow():
    workflow = StateGraph(LearningState)

    # --------------------------------------------------
    # 1. Register adaptive learning agents
    # --------------------------------------------------

    workflow.add_node("evaluation", evaluation_agent)
    workflow.add_node("reflection", reflection_agent)
    workflow.add_node("memory", memory_agent)
    workflow.add_node("profile", profile_agent)
    workflow.add_node("learning_gap", learning_gap_agent)
    workflow.add_node("resource", resource_agent)
    workflow.add_node("study_plan", study_plan_agent)

    # Validation wrapper handles retry limits.
    workflow.add_node("validation", validation_with_retry)

    workflow.add_node("persistence", persistence_agent)

    # --------------------------------------------------
    # 2. Register session lifecycle agent
    # --------------------------------------------------

    workflow.add_node(
        "session_lifecycle",
        run_session_lifecycle,
    )

    # --------------------------------------------------
    # 3. Select workflow at START
    # --------------------------------------------------

    workflow.add_conditional_edges(
        START,
        route_workflow,
        {
            "evaluation": "evaluation",
            "session_lifecycle": "session_lifecycle",
        },
    )

    # --------------------------------------------------
    # 4. Evaluation routing
    # --------------------------------------------------

    workflow.add_conditional_edges(
        "evaluation",
        lambda state: state.get("next_action", "stop"),
        {
            "reflection": "reflection",
            "stop": END,
        },
    )

    # --------------------------------------------------
    # 5. Reflection routing
    # --------------------------------------------------

    workflow.add_conditional_edges(
        "reflection",
        lambda state: state.get("next_action", "complete"),
        {
            "replan": "memory",
            "complete": END,
            "stop": END,
        },
    )

    # --------------------------------------------------
    # 6. Adaptive replanning pipeline
    # --------------------------------------------------

    workflow.add_edge("memory", "profile")
    workflow.add_edge("profile", "learning_gap")
    workflow.add_edge("learning_gap", "resource")
    workflow.add_edge("resource", "study_plan")
    workflow.add_edge("study_plan", "validation")

    # --------------------------------------------------
    # 7. Validation routing
    # --------------------------------------------------

    workflow.add_conditional_edges(
        "validation",
        lambda state: state.get("next_action", "stop"),
        {
            "complete": "persistence",
            "replan": "study_plan",
            "stop": END,
        },
    )

    # --------------------------------------------------
    # 8. Persistence routing
    # --------------------------------------------------

    workflow.add_conditional_edges(
        "persistence",
        lambda state: state.get("next_action", "stop"),
        {
            "complete": END,
            "stop": END,
        },
    )

    # --------------------------------------------------
    # 9. Session lifecycle routing
    # --------------------------------------------------

    # Complete the requested lifecycle operation and end.
    workflow.add_edge("session_lifecycle", END)

    # --------------------------------------------------
    # 10. Compile workflow
    # --------------------------------------------------

    return workflow.compile()


# Compiled workflow instance
adaptive_workflow = build_adaptive_workflow()
