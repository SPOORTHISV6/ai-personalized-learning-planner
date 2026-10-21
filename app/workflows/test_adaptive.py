from app.workflows.adaptive_workflow import (
    build_adaptive_workflow
)


def main():

    student_id = 1

    # Existing quiz result
    quiz_result_id = 7

    initial_state = {

        "student_id":
            student_id,

        "quiz_result_id":
            quiz_result_id,

        "errors":
            []
    }

    print("\n==============================")
    print("ADAPTIVE LEARNING WORKFLOW")
    print("==============================")

    workflow = build_adaptive_workflow()

    result = workflow.invoke(
        initial_state
    )

    print("\n==============================")
    print("FINAL ADAPTIVE RESULT")
    print("==============================")

    print(result)


if __name__ == "__main__":
    main()