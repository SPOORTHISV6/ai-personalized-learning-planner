from app.workflows.evaluation_workflow import (
    build_evaluation_workflow
)


def main():

    # Student
    student_id = 1

    # Existing seeded quiz result
    quiz_result_id = 1

    state = {

        "student_id":
            student_id,

        "quiz_result_id":
            quiz_result_id,

        "errors":
            []
    }

    print("\n==============================")
    print("EVALUATION WORKFLOW")
    print("==============================")

    workflow = build_evaluation_workflow()

    result = workflow.invoke(
        state
    )

    print("\n==============================")
    print("FINAL EVALUATION RESULT")
    print("==============================")

    print(result)


if __name__ == "__main__":
    main()