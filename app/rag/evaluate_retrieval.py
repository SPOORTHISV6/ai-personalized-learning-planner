
import re
from pathlib import Path

from app.rag.vector_store import VectorStore


PROJECT_ROOT = Path(__file__).resolve().parents[2]
VECTOR_STORE_DIR = PROJECT_ROOT / "data" / "vector_store"

TOP_K = 4
DIAGNOSTIC_K = 12


# Each query represents a different way a student might request help.
# Expected values are section titles in the corresponding PDF.
TEST_CASES = {
    "normalization": [
        {
            "name": "Broad query",
            "query": (
                "Database normalization, first normal form 1NF, "
                "second normal form 2NF, third normal form 3NF, "
                "Boyce Codd normal form BCNF"
            ),
            "expected": ["1NF", "2NF", "3NF", "BCNF"],
        },
        {
            "name": "First normal form",
            "query": "Explain 1NF and first normal form",
            "expected": ["1NF"],
        },
        {
            "name": "Second normal form",
            "query": "What is second normal form 2NF?",
            "expected": ["2NF"],
        },
        {
            "name": "Third normal form",
            "query": "Explain 3NF and transitive dependency",
            "expected": ["3NF"],
        },
        {
            "name": "BCNF",
            "query": "Explain Boyce Codd normal form",
            "expected": ["BCNF"],
        },
    ],

    "python": [
        {
            "name": "Broad OOP query",
            "query": (
                "Python object oriented programming OOP. "
                "Classes and objects, __init__ constructor, "
                "self parameter, encapsulation, private attributes, "
                "data hiding, inheritance, parent class, child class."
            ),
            "expected": [
                "Classes and Objects",
                "Constructor and self",
                "Encapsulation",
                "Inheritance",
            ],
        },
        {
            "name": "Classes and objects",
            "query": "Explain Python classes and objects with examples",
            "expected": ["Classes and Objects"],
        },
        {
            "name": "Constructor",
            "query": "What does __init__ do in Python?",
            "expected": ["Constructor and self"],
        },
        {
            "name": "Self parameter",
            "query": "Why is self used inside Python class methods?",
            "expected": ["Constructor and self"],
        },
        {
            "name": "Encapsulation",
            "query": (
                "Explain encapsulation, data hiding, "
                "and private attributes in Python"
            ),
            "expected": ["Encapsulation"],
        },
        {
            "name": "Inheritance",
            "query": (
                "How does a child class inherit from a parent class "
                "in Python?"
            ),
            "expected": ["Inheritance"],
        },
    ],

    "sql_basics": [
        {
            "name": "Broad SQL query",
            "query": (
                "SQL aggregate functions, GROUP BY and HAVING, "
                "ORDER BY and LIMIT"
            ),
            "expected": [
                "Aggregate functions",
                "GROUP BY and HAVING",
                "ORDER BY and LIMIT",
            ],
        },
        {
            "name": "Aggregate functions",
            "query": "Explain COUNT SUM AVG MIN and MAX in SQL",
            "expected": ["Aggregate functions"],
        },
        {
            "name": "GROUP BY and HAVING",
            "query": (
                "How do GROUP BY and HAVING work in SQL?"
            ),
            "expected": ["GROUP BY and HAVING"],
        },
        {
            "name": "ORDER BY and LIMIT",
            "query": (
                "Sort SQL query results and return only the first "
                "few rows using ORDER BY and LIMIT"
            ),
            "expected": ["ORDER BY and LIMIT"],
        },
    ],

    "sql_joins": [
        {
            "name": "Broad joins query",
            "query": (
                "SQL joins INNER JOIN, LEFT JOIN, RIGHT JOIN, "
                "FULL OUTER JOIN and examples"
            ),
            "expected": [
                "INNER JOIN",
                "LEFT JOIN",
                "RIGHT JOIN",
                "FULL OUTER JOIN",
            ],
        },
        {
            "name": "INNER JOIN",
            "query": (
                "Return only rows matching in both tables "
                "using INNER JOIN"
            ),
            "expected": ["INNER JOIN"],
        },
        {
            "name": "LEFT JOIN",
            "query": (
                "Return every row from the left table, "
                "including unmatched rows, using LEFT JOIN"
            ),
            "expected": ["LEFT JOIN"],
        },
        {
            "name": "RIGHT JOIN",
            "query": (
                "Return every row from the right table "
                "using RIGHT OUTER JOIN"
            ),
            "expected": ["RIGHT JOIN"],
        },
        {
            "name": "FULL OUTER JOIN",
            "query": (
                "Return matching and unmatched rows from both "
                "tables using FULL OUTER JOIN"
            ),
            "expected": ["FULL OUTER JOIN"],
        },
    ],
}


ALIASES = {
    "1NF": ["1nf", "first normal form"],
    "2NF": ["2nf", "second normal form"],
    "3NF": ["3nf", "third normal form"],
    "BCNF": ["bcnf", "boyce codd normal form"],
}


def normalize_title(value):
    """Normalize section titles for reliable comparisons."""
    if not value:
        return ""

    value = str(value).casefold().strip()
    value = re.sub(r"^\s*\d+(?:\.\d+)*[.)]?\s*", "", value)
    value = re.sub(r"[^a-z0-9]+", " ", value)

    return " ".join(value.split())


def get_section(result):
    """Read the section title from a VectorStore result."""
    if not isinstance(result, dict):
        return str(result)

    metadata = result.get("metadata", {})

    if not isinstance(metadata, dict):
        metadata = {}

    for key in ("section_title", "section", "title"):
        value = metadata.get(key)
        if value:
            return str(value)

    for key in ("section_title", "section", "title"):
        value = result.get(key)
        if value:
            return str(value)

    return "Unknown section"


def get_score(result):
    """Read the final ranking score."""
    if not isinstance(result, dict):
        return None

    for key in ("similarity_score", "score", "similarity"):
        value = result.get(key)

        if isinstance(value, (int, float)):
            return float(value)

    return None


def section_matches(expected, actual):
    """Match an expected section without loose keyword matching."""
    expected_norm = normalize_title(expected)
    actual_norm = normalize_title(actual)

    if not expected_norm or not actual_norm:
        return False

    if expected_norm == actual_norm:
        return True

    for alias in ALIASES.get(expected, []):
        alias_norm = normalize_title(alias)

        if actual_norm == alias_norm:
            return True

        if f" {alias_norm} " in f" {actual_norm} ":
            return True

    # Permit extra descriptive words around a complete title.
    if actual_norm.startswith(expected_norm + " "):
        return True

    if actual_norm.endswith(" " + expected_norm):
        return True

    return False


def evaluate_query(topic, test, store):
    """Evaluate one query and return retrieval metrics."""
    print("\n" + "-" * 76)
    print(f"Test: {test['name']}")
    print(f"Query: {test['query']}")

    results = store.search(
        test["query"],
        top_k=DIAGNOSTIC_K,
    )

    if not results:
        print("No results returned.")

        return {
            "precision": 0.0,
            "recall": 0.0,
            "hit_rate": 0.0,
            "mrr": 0.0,
        }

    print("\nRanked results:")

    for rank, result in enumerate(results, start=1):
        title = get_section(result)
        score = get_score(result)

        if score is None:
            print(f"{rank:2}. {title}")
        else:
            print(f"{rank:2}. {title} | Score: {score:.4f}")

    # Each retrieved result can match only one expected section.
    expected_ranks = {}
    used_ranks = set()

    for expected in test["expected"]:
        for rank, result in enumerate(results, start=1):
            if rank in used_ranks:
                continue

            if section_matches(expected, get_section(result)):
                expected_ranks[expected] = rank
                used_ranks.add(rank)
                break

    relevant_top_k = sum(
        1
        for rank in expected_ranks.values()
        if rank <= TOP_K
    )

    total_expected = len(test["expected"])

    precision = relevant_top_k / TOP_K

    recall = (
        relevant_top_k / total_expected
        if total_expected
        else 0.0
    )

    hit_rate = 1.0 if relevant_top_k > 0 else 0.0

    reciprocal_rank_sum = sum(
        1.0 / rank
        for rank in expected_ranks.values()
    )

    # For multiple expected sections, average reciprocal rank
    # across all expected sections, including missing sections.
    mrr = (
        reciprocal_rank_sum / total_expected
        if total_expected
        else 0.0
    )

    print("\nMetrics:")
    print(
        f"Expected sections found in top {TOP_K}: "
        f"{relevant_top_k}/{total_expected}"
    )
    print(f"Precision@{TOP_K}: {precision:.2%}")
    print(f"Recall@{TOP_K}:    {recall:.2%}")
    print(f"Hit Rate@{TOP_K}:  {hit_rate:.2%}")
    print(f"MRR@{DIAGNOSTIC_K}: {mrr:.4f}")

    print("\nExpected-section ranks:")

    for expected in test["expected"]:
        rank = expected_ranks.get(expected)

        if rank is None:
            print(f"  MISSING: {expected}")
        elif rank <= TOP_K:
            print(f"  FOUND:   {expected} at rank {rank}")
        else:
            print(
                f"  LATE:    {expected} at rank {rank}, "
                f"outside top {TOP_K}"
            )

    return {
        "precision": precision,
        "recall": recall,
        "hit_rate": hit_rate,
        "mrr": mrr,
    }


def average_metrics(results):
    """Calculate mean metrics for a list of query results."""
    if not results:
        return {
            "precision": 0.0,
            "recall": 0.0,
            "hit_rate": 0.0,
            "mrr": 0.0,
        }

    count = len(results)

    return {
        key: sum(item[key] for item in results) / count
        for key in ("precision", "recall", "hit_rate", "mrr")
    }


def main():
    print("=" * 76)
    print("FAISS RAG RETRIEVAL EVALUATION")
    print("=" * 76)
    print(f"Precision and recall cutoff: {TOP_K}")
    print(f"Diagnostic ranking depth: {DIAGNOSTIC_K}")

    topic_results = {}
    all_query_results = []

    for topic, tests in TEST_CASES.items():
        print("\n" + "=" * 76)
        print(f"TOPIC: {topic}")
        print("=" * 76)

        index_dir = VECTOR_STORE_DIR / topic
        index_path = index_dir / "index.faiss"
        metadata_path = index_dir / "metadata.json"

        if not index_path.exists() or not metadata_path.exists():
            print(f"SKIPPED: Index or metadata missing in {index_dir}")
            continue

        store = VectorStore()

        try:
            store.load(
                index_path=str(index_path),
                metadata_path=str(metadata_path),
            )
        except Exception as exc:
            print(f"ERROR loading {topic}: {exc}")
            continue

        results_for_topic = []

        for test in tests:
            metrics = evaluate_query(topic, test, store)
            results_for_topic.append(metrics)
            all_query_results.append(metrics)

        topic_results[topic] = average_metrics(results_for_topic)

    if not all_query_results:
        print("\nNo queries were evaluated. Check the index paths.")
        return

    print("\n" + "=" * 76)
    print("AVERAGE RESULTS BY TOPIC")
    print("=" * 76)

    print(
        f"{'Topic':<20}"
        f"{'Precision@4':>15}"
        f"{'Recall@4':>12}"
        f"{'Hit Rate':>12}"
        f"{'MRR':>10}"
    )
    print("-" * 76)

    for topic, metrics in topic_results.items():
        print(
            f"{topic:<20}"
            f"{metrics['precision']:>14.2%}"
            f"{metrics['recall']:>12.2%}"
            f"{metrics['hit_rate']:>12.2%}"
            f"{metrics['mrr']:>10.4f}"
        )

    overall = average_metrics(all_query_results)

    print("-" * 76)
    print(
        f"{'OVERALL':<20}"
        f"{overall['precision']:>14.2%}"
        f"{overall['recall']:>12.2%}"
        f"{overall['hit_rate']:>12.2%}"
        f"{overall['mrr']:>10.4f}"
    )

    print("\nEvaluation notes:")
    print(f"- Queries evaluated: {len(all_query_results)}")
    print("- Metrics are averages across individual queries.")
    print("- Precision@4 uses 4 as its denominator, even for")
    print("  queries with only one expected section.")
    print("- Relevance is based on section-title matching, not")
    print("  human judgment of the retrieved chunk's full content.")
    print("- No FAISS indexes are rebuilt or modified by this script.")


if __name__ == "__main__":
    main()
