
from app.workflows.learning_workflow import build_learning_workflow


def main():
    workflow = build_learning_workflow()

    initial_state = {
        "student_id": 1,
        "errors": []
    }

    result = workflow.invoke(initial_state)

    print("\n==============================")
    print("FINAL WORKFLOW RESULT")
    print("==============================")
    print(result)


if __name__ == "__main__":
    main()
