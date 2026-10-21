def planner_agent(state):

    print("\n[Planner Agent] Starting workflow...")

    student_id = state.get("student_id")

    if not student_id:
        return {
            "errors": ["Student ID is missing"],
            "next_action": "stop"
        }

    print(f"[Planner Agent] Planning workflow for student {student_id}")

    return {
        "next_action": "profile"
    }