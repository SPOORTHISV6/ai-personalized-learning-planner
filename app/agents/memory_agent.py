from app.memory.student_memory import get_student_memory


def memory_agent(state):

    print("\n[Memory Agent] Loading student memory...")

    student_id = state["student_id"]

    memory = get_student_memory(student_id)

    if "error" in memory:

        print(
            "[Memory Agent] Student memory could not be loaded."
        )

        return {
            "errors": [
                memory["error"]
            ],
            "next_action": "stop"
        }

    print(
        "[Memory Agent] Student memory loaded."
    )

    return {
        "student_memory": memory,
        "next_action": "profile"
    }