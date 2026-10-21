from langgraph.graph import StateGraph, END

from app.workflows.state import LearningState

from app.agents.evaluation_agent import evaluation_agent
from app.agents.reflection_agent import reflection_agent


def build_evaluation_workflow():

    workflow = StateGraph(
        LearningState
    )

    # =====================================================
    # ADD AGENTS
    # =====================================================

    workflow.add_node(
        "evaluation",
        evaluation_agent
    )

    workflow.add_node(
        "reflection",
        reflection_agent
    )

    # =====================================================
    # ENTRY POINT
    # =====================================================

    workflow.set_entry_point(
        "evaluation"
    )

    # =====================================================
    # EVALUATION → REFLECTION
    # =====================================================

    workflow.add_conditional_edges(

        "evaluation",

        lambda state: state.get(
            "next_action",
            "stop"
        ),

        {
            "reflection": "reflection",
            "stop": END
        }
    )

    # =====================================================
    # REFLECTION DECISION
    # =====================================================

    workflow.add_conditional_edges(

        "reflection",

        lambda state: state.get(
            "next_action",
            "complete"
        ),

        {
            "complete": END,

            # Replanning will be connected to the
            # learning workflow in the next stage.
            "replan": END,

            "stop": END
        }
    )

    # =====================================================
    # COMPILE
    # =====================================================

    return workflow.compile()