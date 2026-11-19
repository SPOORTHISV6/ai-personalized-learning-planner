
"""
Production RAG evaluation.

Evaluates the actual Resource Agent retrieval function without
rebuilding or modifying FAISS indexes, PDFs, or application data.

This is a retrieval-pipeline diagnostic, not a human relevance
or answer-quality evaluation.
"""

from collections import Counter

from app.agents.resource_agent import (
    get_knowledge_base,
    is_excluded_section,
    retrieve_topic_resources,
)


TEST_TOPICS = [
    {
        "topic": "Normalization",
        "subject": "DBMS",
    },
    {
        "topic": "SQL Joins",
        "subject": "DBMS",
    },
    {
        "topic": "Python OOP",
        "subject": "Python",
    },
    {
        "topic": "SQL Basics",
        "subject": "DBMS",
    },
]

LEARNING_STATUSES = ["weak", "moderate", "strong"]

UNSUPPORTED_TOPICS = [
    ("DBMS", "Database Management Systems"),
    ("Machine Learning", "Artificial Intelligence"),
    ("", "DBMS"),
    (None, "DBMS"),
]


def normalize_title(value):
    """Normalize section titles for duplicate detection."""
    return " ".join(
        str(value or "").casefold().replace("_", " ").split()
    )


def inspect_resources(resources):
    """Collect structural quality checks for retrieved resources."""
    if not isinstance(resources, list):
        return {
            "valid_list": False,
            "count": 0,
            "unique_sections": 0,
            "duplicate_sections": 0,
            "excluded_sections": 0,
            "empty_content": 0,
            "missing_titles": 0,
        }

    titles = []
    excluded_count = 0
    empty_content_count = 0
    missing_title_count = 0

    for resource in resources:
        if not isinstance(resource, dict):
            missing_title_count += 1
            empty_content_count += 1
            continue

        title = resource.get("section_title", "")
        content = (
            resource.get("content")
            or resource.get("text")
            or ""
        )

        if not isinstance(title, str) or not title.strip():
            missing_title_count += 1
        else:
            titles.append(normalize_title(title))

            if is_excluded_section(title):
                excluded_count += 1

        if not isinstance(content, str) or not content.strip():
            empty_content_count += 1

    section_counts = Counter(titles)

    duplicate_count = sum(
        count - 1
        for count in section_counts.values()
        if count > 1
    )

    return {
        "valid_list": True,
        "count": len(resources),
        "unique_sections": len(section_counts),
        "duplicate_sections": duplicate_count,
        "excluded_sections": excluded_count,
        "empty_content": empty_content_count,
        "missing_titles": missing_title_count,
    }


def evaluate_supported_topics():
    """Evaluate every supported topic at all learning statuses."""
    all_results = []
    topic_results = []

    print("\n" + "=" * 88)
    print("PRODUCTION RESOURCE AGENT RAG EVALUATION")
    print("=" * 88)

    print("Retrieval function: retrieve_topic_resources")
    print("Learning statuses: weak, moderate, strong")
    print("Expected retrieval runs: 12")
    print("FAISS indexes will not be rebuilt or modified.")

    for case in TEST_TOPICS:
        topic = case["topic"]
        subject = case["subject"]

        knowledge_base = get_knowledge_base(topic)

        print("\n" + "-" * 88)
        print(f"TOPIC: {topic}")
        print(f"SUBJECT: {subject}")
        print(f"KNOWLEDGE BASE: {knowledge_base}")

        if knowledge_base is None:
            print("ERROR: Topic is not supported.")
            continue

        for status in LEARNING_STATUSES:
            print("\n" + "." * 72)
            print(f"LEARNING STATUS: {status.upper()}")

            try:
                resources = retrieve_topic_resources(
                    topic_name=topic,
                    subject_name=subject,
                    learning_status=status,
                )

                metrics = inspect_resources(resources)

                result = {
                    "topic": topic,
                    "status": status,
                    **metrics,
                }

                all_results.append(result)

                print("\nRetrieval diagnostics:")
                print(f"Resources returned: {metrics['count']}")
                print(f"Unique sections: {metrics['unique_sections']}")
                print(
                    "Duplicate sections: "
                    f"{metrics['duplicate_sections']}"
                )
                print(
                    "Excluded sections: "
                    f"{metrics['excluded_sections']}"
                )
                print(
                    "Empty content: "
                    f"{metrics['empty_content']}"
                )
                print(
                    "Missing section titles: "
                    f"{metrics['missing_titles']}"
                )

                if resources:
                    print("\nSelected sections:")

                    for rank, resource in enumerate(
                        resources,
                        start=1,
                    ):
                        if not isinstance(resource, dict):
                            print(f"{rank}. Invalid resource")
                            continue

                        title = resource.get(
                            "section_title",
                            "Missing title",
                        )

                        score = resource.get("ranking_score")

                        if isinstance(score, (int, float)):
                            print(
                                f"{rank}. {title} "
                                f"| Ranking score: {score:.4f}"
                            )
                        else:
                            print(f"{rank}. {title}")
                else:
                    print("No resources returned.")

                topic_results.append(result)

            except Exception as exc:
                print(
                    "EVALUATION ERROR: "
                    f"{type(exc).__name__}"
                )

                result = {
                    "topic": topic,
                    "status": status,
                    "valid_list": False,
                    "count": 0,
                    "unique_sections": 0,
                    "duplicate_sections": 0,
                    "excluded_sections": 0,
                    "empty_content": 0,
                    "missing_titles": 0,
                }

                all_results.append(result)
                topic_results.append(result)

    return all_results, topic_results


def evaluate_unsupported_topics():
    """Confirm that unsupported topics are rejected."""
    print("\n" + "=" * 88)
    print("UNSUPPORTED TOPIC VALIDATION")
    print("=" * 88)

    passed = 0

    for topic, subject in UNSUPPORTED_TOPICS:
        print(f"\nTopic: {topic!r}")

        try:
            resources = retrieve_topic_resources(
                topic_name=topic,
                subject_name=subject,
                learning_status="weak",
            )

            success = isinstance(resources, list) and not resources

            if success:
                passed += 1
                print("PASSED: Unsupported topic returned an empty list.")
            else:
                print("FAILED: Unexpected retrieval result.")

        except Exception as exc:
            print(
                "FAILED: Unexpected exception "
                f"{type(exc).__name__}"
            )

    print(
        f"\nUnsupported-topic checks: "
        f"{passed}/{len(UNSUPPORTED_TOPICS)} passed"
    )

    return passed, len(UNSUPPORTED_TOPICS)


def print_summary(results):
    """Print overall structural diagnostics."""
    print("\n" + "=" * 88)
    print("PRODUCTION RAG SUMMARY")
    print("=" * 88)

    if not results:
        print("No retrieval runs were completed.")
        return

    total_runs = len(results)
    total_resources = sum(item["count"] for item in results)

    successful_runs = sum(
        1
        for item in results
        if item["valid_list"] and item["count"] > 0
    )

    duplicate_runs = sum(
        1
        for item in results
        if item["duplicate_sections"] > 0
    )

    invalid_runs = sum(
        1
        for item in results
        if (
            not item["valid_list"]
            or item["empty_content"] > 0
            or item["missing_titles"] > 0
            or item["excluded_sections"] > 0
        )
    )

    print(f"Retrieval runs: {total_runs}")
    print(f"Runs returning resources: {successful_runs}")
    print(f"Total resources returned: {total_resources}")
    print(f"Runs containing duplicate sections: {duplicate_runs}")
    print(f"Runs with structural issues: {invalid_runs}")

    print("\nResults by topic and status:")
    print(
        f"{'Topic':<18}"
        f"{'Status':<12}"
        f"{'Count':>8}"
        f"{'Unique':>9}"
        f"{'Duplicates':>13}"
        f"{'Issues':>9}"
    )

    print("-" * 78)

    for item in results:
        issues = (
            item["excluded_sections"]
            + item["empty_content"]
            + item["missing_titles"]
        )

        print(
            f"{item['topic']:<18}"
            f"{item['status']:<12}"
            f"{item['count']:>8}"
            f"{item['unique_sections']:>9}"
            f"{item['duplicate_sections']:>13}"
            f"{issues:>9}"
        )

    print("\nEvaluation limitations:")
    print("- This evaluates production retrieval, filtering and selection.")
    print("- It does not measure answer correctness or human relevance.")
    print("- Learning status changes query wording, not PDF content.")
    print("- It does not test arbitrary free-form student questions.")
    print("- Unsupported-topic rejection is evaluated separately.")
    print("- No application database records are modified.")
    print("- No PDFs or FAISS indexes are rebuilt.")


def main():
    results, _ = evaluate_supported_topics()

    unsupported_passed, unsupported_total = (
        evaluate_unsupported_topics()
    )

    print_summary(results)

    print("\n" + "=" * 88)
    print("FINAL EVALUATION STATUS")
    print("=" * 88)

    retrieval_runs = len(results)

    structural_issues = sum(
        1
        for item in results
        if (
            not item["valid_list"]
            or item["empty_content"] > 0
            or item["missing_titles"] > 0
            or item["excluded_sections"] > 0
        )
    )

    if (
        retrieval_runs == 12
        and structural_issues == 0
        and unsupported_passed == unsupported_total
    ):
        print("PRODUCTION RAG STRUCTURAL EVALUATION: PASSED")
    else:
        print("PRODUCTION RAG STRUCTURAL EVALUATION: NEEDS REVIEW")

    print(f"Retrieval runs completed: {retrieval_runs}/12")
    print(
        "Unsupported-topic checks: "
        f"{unsupported_passed}/{unsupported_total}"
    )


if __name__ == "__main__":
    main()
