
from app.tools.learning_gap import calculate_learning_gaps


def learning_gap_agent(state):
    print("\n[Learning Gap Agent] Analyzing performance...")

    student_id = state.get("student_id")

    if not student_id:
        return {
            "errors": ["Student ID is missing"],
            "next_action": "stop",
        }

    gaps = calculate_learning_gaps(student_id)

    print(f"[Learning Gap Agent] Found {len(gaps)} topic records")

    for gap in gaps:
        print(
            "[Learning Gap Agent] "
            f"Topic={gap.get('topic_name')} | "
            f"Score={gap.get('score')} | "
            f"Status={gap.get('status')} | "
            f"Priority={gap.get('priority')}"
        )

    return {
        "learning_gaps": gaps,
        "next_action": "resource",
    }
