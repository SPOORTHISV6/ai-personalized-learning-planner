from app.agents.resource_agent import resource_agent


def main():

    print("\n==============================")
    print("RESOURCE RAG TEST")
    print("==============================")

    state = {
        "student_id": 1,
        "learning_gaps": [
            {
                "topic_id": 3,
                "topic_name": "Normalization",
                "score": 45,
                "difficulty": 4,
                "status": "weak",
                "priority": "high",
                "prerequisite_topic_id": 1
            },
            {
                "topic_id": 2,
                "topic_name": "SQL Joins",
                "score": 60,
                "difficulty": 3,
                "status": "moderate",
                "priority": "medium",
                "prerequisite_topic_id": 1
            }
        ]
    }

    result = resource_agent(state)

    print("\n==============================")
    print("RETRIEVED RESOURCES")
    print("==============================")

    resources = result.get(
        "resources",
        []
    )

    for i, resource in enumerate(
        resources,
        start=1
    ):

        print(
            f"\n--- Resource {i} ---"
        )

        print(
            f"Topic: "
            f"{resource['topic_name']}"
        )

        print(
            f"Type: "
            f"{resource['resource_type']}"
        )

        print(
            f"Source: "
            f"{resource['source']}"
        )

        print(
            f"Page: "
            f"{resource['page_number']}"
        )

        print(
            f"Similarity: "
            f"{resource['similarity_score']:.4f}"
        )

        print("\nContent:")

        print(
            resource["content"]
        )


if __name__ == "__main__":
    main()