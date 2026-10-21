
from app.workflows.adaptive_workflow import adaptive_workflow


def run_adaptive_test(student_id, quiz_result_id, expected_level):
    print("\n" + "=" * 60)
    print(f"Testing quiz result ID: {quiz_result_id}")
    print(f"Expected performance level: {expected_level}")
    print("=" * 60)

    try:
        result = adaptive_workflow.invoke({
            "student_id": student_id,
            "quiz_result_id": quiz_result_id,
        })

        evaluation = result.get("evaluation") or {}
        actual_level = evaluation.get("level")

        print(f"Actual level: {actual_level}")
        print(f"Next action: {result.get('next_action')}")
        print(f"Validation: {result.get('validation')}")
        print(f"Errors: {result.get('errors', [])}")

        if actual_level == expected_level:
            print("PASS: Performance level matches.")
        else:
            print(
                f"CHECK: Expected {expected_level}, "
                f"received {actual_level}."
            )

    except Exception as error:
        print(f"FAIL: Workflow raised an exception: {error}")


if __name__ == "__main__":
    print(
        "This test requires existing quiz result IDs "
        "belonging to student 1."
    )

    run_adaptive_test(
        student_id=1,
        quiz_result_id=7,
        expected_level="weak",
    )
