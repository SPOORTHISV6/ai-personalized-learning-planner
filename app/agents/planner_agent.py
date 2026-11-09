
def planner_agent(state):
    print("\n[Planner Agent] Starting workflow...")

    if not isinstance(state, dict):
        return {
            "errors": ["Invalid workflow state"],
            "next_action": "stop",
        }

    student_id = state.get("student_id")

    # bool is a subclass of int in Python, so reject it explicitly.
    if (
        isinstance(student_id, bool)
        or not isinstance(student_id, int)
        or student_id <= 0
    ):
        return {
            "errors": ["A valid student ID is required"],
            "next_action": "stop",
        }

    print(
        f"[Planner Agent] Planning workflow for student {student_id}"
    )

    return {
        "next_action": "profile",
    }
