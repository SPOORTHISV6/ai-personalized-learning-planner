from langgraph.graph import StateGraph, END

from app.workflows.state import LearningState

from app.agents.planner_agent import planner_agent
from app.agents.memory_agent import memory_agent
from app.agents.profile_agent import profile_agent
from app.agents.learning_gap_agent import learning_gap_agent
from app.agents.resource_agent import resource_agent
from app.agents.study_plan_agent import study_plan_agent
from app.agents.validation_agent import validation_agent


def build_learning_workflow():

    # Create LangGraph workflow
    workflow = StateGraph(LearningState)

    # =========================================================
    # ADD AGENTS
    # =========================================================

    workflow.add_node(
        "planner",
        planner_agent
    )

    workflow.add_node(
        "memory",
        memory_agent
    )

    workflow.add_node(
        "profile",
        profile_agent
    )

    workflow.add_node(
        "learning_gap",
        learning_gap_agent
    )

    workflow.add_node(
        "resource",
        resource_agent
    )

    workflow.add_node(
        "study_plan",
        study_plan_agent
    )

    workflow.add_node(
        "validation",
        validation_agent
    )

    # =========================================================
    # ENTRY POINT
    # =========================================================

    workflow.set_entry_point("planner")

    # =========================================================
    # MAIN WORKFLOW
    # =========================================================

    # Planner
    #    ↓
    # Memory
    workflow.add_edge(
        "planner",
        "memory"
    )

    # Memory
    #    ↓
    # Profile
    workflow.add_edge(
        "memory",
        "profile"
    )

    # Profile
    #    ↓
    # Learning Gap
    workflow.add_edge(
        "profile",
        "learning_gap"
    )

    # Learning Gap
    #    ↓
    # Resource Recommendation
    workflow.add_edge(
        "learning_gap",
        "resource"
    )

    # Resource
    #    ↓
    # Study Plan
    workflow.add_edge(
        "resource",
        "study_plan"
    )

    # Study Plan
    #    ↓
    # Validation
    workflow.add_edge(
        "study_plan",
        "validation"
    )

    # =========================================================
    # VALIDATION DECISION
    # =========================================================

    workflow.add_conditional_edges(
        "validation",

        lambda state: state.get(
            "next_action",
            "complete"
        ),

        {
            "complete": END,

            # If validation says the plan needs changes,
            # generate the study plan again.
            "replan": "study_plan",

            # Stop workflow if an error occurs.
            "stop": END
        }
    )

    # =========================================================
    # COMPILE WORKFLOW
    # =========================================================

    return workflow.compile()