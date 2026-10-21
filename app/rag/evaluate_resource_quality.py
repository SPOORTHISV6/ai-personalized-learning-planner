
import json
from pathlib import Path

from app.agents.resource_agent import (
    TOPIC_MAP,
    retrieve_topic_resources,
    is_substantive_chunk,
    is_excluded_section,
    is_sentence_like_heading,
    normalize_content,
)


# ---------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------

TOPICS = {
    "normalization": {
        "display_name": "Normalization",
        "subject_name": "DBMS",
    },
    "sql joins": {
        "display_name": "SQL Joins",
        "subject_name": "DBMS",
    },
    "python oop": {
        "display_name": "Python OOP",
        "subject_name": "Python",
    },
    "sql basics": {
        "display_name": "SQL Basics",
        "subject_name": "DBMS",
    },
}

OUTPUT_PATH = Path("data/resource_quality_report.json")


# ---------------------------------------------------------
# RESOURCE HELPERS
# ---------------------------------------------------------

def get_content(resource):
    """
    Support both metadata formats:
    - content
    - text
    """
    return str(
        resource.get("content")
        or resource.get("text")
        or ""
    ).strip()


def get_title(resource):
    """Return a normalized string representation of the section title."""
    return str(
        resource.get("section_title") or ""
    ).strip()


def has_source_reference(resource):
    """Check whether a resource has a section title and page number."""
    page_number = resource.get("page_number")
    section_title = get_title(resource)

    valid_page = (
        page_number is not None
        and str(page_number).strip() != ""
    )

    valid_section = bool(section_title)

    return valid_page and valid_section


def duplicate_rate(resources):
    """
    Calculate the exact-text duplicate rate.

    This detects identical normalized content, not semantic duplicates.
    """
    if not resources:
        return 0.0

    seen = set()
    duplicate_count = 0

    for resource in resources:
        content = normalize_content(get_content(resource))

        if not content:
            continue

        if content in seen:
            duplicate_count += 1
        else:
            seen.add(content)

    return duplicate_count / len(resources)


# ---------------------------------------------------------
# EVALUATE ONE TOPIC
# ---------------------------------------------------------

def evaluate_topic(topic_key, topic_config):
    """
    Evaluate the resources returned by the existing resource agent.

    Parameters
    ----------
    topic_key : str
        Exact topic key used by TOPIC_MAP.
    topic_config : dict
        Display name and subject name.
    """
    display_name = topic_config["display_name"]
    subject_name = topic_config["subject_name"]

    print("\n" + "=" * 72)
    print(f"TOPIC: {display_name}")
    print(f"TOPIC KEY: {topic_key}")
    print(f"SUBJECT: {subject_name}")
    print("=" * 72)

    # Verify that the topic has a configured knowledge base.
    if topic_key not in TOPIC_MAP:
        print(f"ERROR: Topic key '{topic_key}' is not configured.")

        return {
            "topic": topic_key,
            "display_name": display_name,
            "resource_count": 0,
            "error": "Topic key missing from TOPIC_MAP",
        }

    # Retrieve resources through the existing implementation.
    try:
        resources = retrieve_topic_resources(
            topic_name=topic_key,
            subject_name=subject_name,
            learning_status="weak",
        )

    except Exception as exc:
        print(f"ERROR: Resource retrieval failed: {exc}")

        return {
            "topic": topic_key,
            "display_name": display_name,
            "resource_count": 0,
            "error": str(exc),
        }

    total = len(resources)

    # Empty results are reported rather than treated as a crash.
    if total == 0:
        print("WARNING: No resources were retrieved.")

        return {
            "topic": topic_key,
            "display_name": display_name,
            "resource_count": 0,
            "content_validity": 0.0,
            "section_validity": 0.0,
            "substantive_rate": 0.0,
            "source_traceability": 0.0,
            "duplicate_rate": 0.0,
        }

    valid_content_count = 0
    valid_section_count = 0
    substantive_count = 0
    traceable_count = 0

    # -----------------------------------------------------
    # Inspect each selected resource
    # -----------------------------------------------------

    for index, resource in enumerate(resources, start=1):
        content = get_content(resource)
        title = get_title(resource)

        content_valid = bool(content)

        section_valid = (
            bool(title)
            and not is_excluded_section(title)
            and not is_sentence_like_heading(title)
        )

        substantive_valid = is_substantive_chunk(
            {
                "content": content,
                "section_title": title,
            },
            TOPIC_MAP[topic_key],
        )

        source_valid = has_source_reference(resource)

        valid_content_count += int(content_valid)
        valid_section_count += int(section_valid)
        substantive_count += int(substantive_valid)
        traceable_count += int(source_valid)

        print(f"\nResource {index}")
        print("-" * 45)
        print(f"Section: {title or 'MISSING'}")
        print(
            f"Page: {resource.get('page_number', 'MISSING')}"
        )
        print(f"Characters: {len(content)}")
        print(f"Content present: {content_valid}")
        print(f"Section valid: {section_valid}")
        print(f"Substantive content: {substantive_valid}")
        print(f"Source traceable: {source_valid}")
        print(f"Similarity score: {resource.get('similarity_score', 'N/A')}")
        print(f"Ranking score: {resource.get('ranking_score', 'N/A')}")
        print(f"Preview: {content[:180]}")

    # -----------------------------------------------------
    # Calculate topic metrics
    # -----------------------------------------------------

    result = {
        "topic": topic_key,
        "display_name": display_name,
        "subject_name": subject_name,
        "knowledge_base": TOPIC_MAP[topic_key],
        "resource_count": total,
        "content_validity": round(
            valid_content_count / total, 4
        ),
        "section_validity": round(
            valid_section_count / total, 4
        ),
        "substantive_rate": round(
            substantive_count / total, 4
        ),
        "source_traceability": round(
            traceable_count / total, 4
        ),
        "duplicate_rate": round(
            duplicate_rate(resources), 4
        ),
    }

    print("\nTOPIC SUMMARY")
    print("-" * 45)
    print(json.dumps(result, indent=2))

    return result


# ---------------------------------------------------------
# EVALUATE ALL TOPICS
# ---------------------------------------------------------

def main():
    results = []

    print("=" * 72)
    print("RESOURCE QUALITY EVALUATION")
    print("=" * 72)

    for topic_key, topic_config in TOPICS.items():
        result = evaluate_topic(
            topic_key=topic_key,
            topic_config=topic_config,
        )

        results.append(result)

    successful_results = [
        result
        for result in results
        if "error" not in result
    ]

    total_resources = sum(
        result["resource_count"]
        for result in successful_results
    )

    report = {
        "evaluation": "Resource Quality Evaluation",
        "topics_tested": len(TOPICS),
        "topics_successful": len(successful_results),
        "total_resources": total_resources,
        "results": results,
    }

    # Save the report.
    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    OUTPUT_PATH.write_text(
        json.dumps(report, indent=2),
        encoding="utf-8",
    )

    # -----------------------------------------------------
    # Final summary table
    # -----------------------------------------------------

    print("\n" + "=" * 100)
    print("FINAL RESOURCE QUALITY SUMMARY")
    print("=" * 100)

    print(
        f"{'Topic':<18}"
        f"{'Count':>8}"
        f"{'Content':>12}"
        f"{'Sections':>12}"
        f"{'Substantive':>14}"
        f"{'Traceable':>12}"
        f"{'Duplicates':>13}"
    )

    print("-" * 100)

    for result in successful_results:
        print(
            f"{result['topic']:<18}"
            f"{result['resource_count']:>8}"
            f"{result['content_validity']:>11.1%}"
            f"{result['section_validity']:>11.1%}"
            f"{result['substantive_rate']:>13.1%}"
            f"{result['source_traceability']:>11.1%}"
            f"{result['duplicate_rate']:>12.1%}"
        )

    print("-" * 100)
    print(f"Topics tested: {len(TOPICS)}")
    print(f"Topics successful: {len(successful_results)}")
    print(f"Total resources: {total_resources}")
    print(f"Report saved to: {OUTPUT_PATH.resolve()}")


if __name__ == "__main__":
    main()
