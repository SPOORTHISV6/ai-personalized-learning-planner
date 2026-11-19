
from app.memory.student_memory import get_student_memory


def memory_agent(state):
    """Load student memory with validated input and safe failure handling."""

    print("\n[Memory Agent] Loading student memory...")

    # Validate workflow state.
    if not isinstance(state, dict):
        return {
            "errors": ["Invalid workflow state provided to memory agent."],
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
            "errors": ["A valid student ID is required to load memory."],
            "next_action": "stop",
        }

    # Retrieve memory safely.
    try:
        memory = get_student_memory(student_id)

    except Exception:
        print("[Memory Agent] Memory retrieval failed.")

        return {
            "errors": ["Student memory could not be loaded."],
            "next_action": "stop",
        }

    # Validate the retrieval result.
    if not isinstance(memory, dict):
        return {
            "errors": ["Memory retrieval returned an invalid result."],
            "next_action": "stop",
        }

    if "error" in memory:
        print("[Memory Agent] Student memory could not be loaded.")

        return {
            "errors": ["Student memory could not be loaded."],
            "next_action": "stop",
        }

    print("[Memory Agent] Student memory loaded.")

    return {
        "student_memory": memory,
        "next_action": "profile",
    }
