from app.memory.student_memory import get_student_memory


def main():

    student_id = 1

    memory = get_student_memory(student_id)

    if "error" in memory:

        print("\nERROR:")
        print(memory["error"])
        return

    print("\n==============================")
    print("STUDENT MEMORY")
    print("==============================")

    print("\nPROFILE:")
    print(memory["profile"])

    print("\nPERFORMANCE HISTORY:")
    print(memory["performance_history"])

    print("\nLATEST PERFORMANCE:")
    print(memory["latest_performance"])

    print("\nWEAK TOPICS:")
    print(memory["weak_topics"])

    print("\nMODERATE TOPICS:")
    print(memory["moderate_topics"])

    print("\nSTRONG TOPICS:")
    print(memory["strong_topics"])

    print("\nSTUDY PLAN HISTORY:")
    print(memory["study_plan_history"])

    print("\nSESSION HISTORY:")
    print(memory["session_history"])

    print("\nQUIZ HISTORY:")
    print(memory["quiz_history"])


if __name__ == "__main__":
    main()