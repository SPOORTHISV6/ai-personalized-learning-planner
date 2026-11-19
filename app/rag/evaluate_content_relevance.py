
from pathlib import Path
import math

from app.rag.vector_store import VectorStore


# ---------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[2]

VECTOR_STORE_DIR = PROJECT_ROOT / "data" / "vector_store"

TOP_K = 5

# Binary relevance:
# 1 = chunk contains useful information for answering the query
# 0 = chunk does not contain useful answer information
#
# Chunk IDs are based on the existing metadata.json files.
#
# Practice-question-only chunks are not automatically marked
# relevant because they do not necessarily contain answers.

TEST_CASES = {
    "normalization": [
        {
            "name": "2NF and partial dependency",
            "query": (
                "Explain how 2NF removes partial dependency "
                "with an example"
            ),
            "relevant_chunks": [1, 4, 7, 8, 9],
        },
        {
            "name": "3NF versus BCNF",
            "query": "What is the difference between 3NF and BCNF?",
            "relevant_chunks": [5, 6, 7, 9],
        },
    ],

    "sql_joins": [
        {
            "name": "Every student including unmatched students",
            "query": (
                "How can I retrieve every student including "
                "students without enrollments?"
            ),
            "relevant_chunks": [2, 4, 9, 10],
        },
        {
            "name": "INNER JOIN versus LEFT JOIN",
            "query": (
                "What is the difference between INNER JOIN "
                "and LEFT JOIN?"
            ),
            "relevant_chunks": [2, 3, 4, 10, 11],
        },
    ],

    "python": [
        {
            "name": "__init__ versus self",
            "query": (
                "Explain the difference between __init__ "
                "and self in Python"
            ),
            "relevant_chunks": [2, 3, 12, 13],
        },
        {
            "name": "Inheritance and super",
            "query": (
                "How does inheritance work and how can "
                "super() be used?"
            ),
            "relevant_chunks": [5, 6, 12],
        },
    ],

    "sql_basics": [
        {
            "name": "COUNT, AVG and GROUP BY",
            "query": (
                "How do COUNT, AVG and GROUP BY work "
                "together in SQL?"
            ),
            "relevant_chunks": [6, 7],
        },
        {
            "name": "WHERE versus HAVING",
            "query": (
                "What is the difference between WHERE "
                "and HAVING?"
            ),
            "relevant_chunks": [3, 7, 11],
        },
    ],
}


# ---------------------------------------------------------
# METRIC CALCULATIONS
# ---------------------------------------------------------

def precision_at_k(retrieved_ids, relevant_ids, k):
    """
    Precision@K:
    Number of relevant retrieved chunks / K.
    """

    retrieved_top_k = retrieved_ids[:k]

    if k == 0:
        return 0.0

    relevant_count = sum(
        1 for chunk_id in retrieved_top_k
        if chunk_id in relevant_ids
    )

    return relevant_count / k


def recall_at_k(retrieved_ids, relevant_ids, k):
    """
    Recall@K:
    Relevant retrieved chunks / Total relevant chunks.
    """

    if not relevant_ids:
        return 0.0

    retrieved_top_k = retrieved_ids[:k]

    relevant_count = sum(
        1 for chunk_id in retrieved_top_k
        if chunk_id in relevant_ids
    )

    return relevant_count / len(relevant_ids)


def reciprocal_rank_at_k(retrieved_ids, relevant_ids, k):
    """
    MRR@K:
    Reciprocal rank of the first relevant retrieved chunk.
    """

    for rank, chunk_id in enumerate(retrieved_ids[:k], start=1):
        if chunk_id in relevant_ids:
            return 1.0 / rank

    return 0.0


def ndcg_at_k(retrieved_ids, relevant_ids, k):
    """
    nDCG@K using binary relevance.
    """

    retrieved_top_k = retrieved_ids[:k]

    dcg = 0.0

    for rank, chunk_id in enumerate(retrieved_top_k, start=1):
        relevance = 1 if chunk_id in relevant_ids else 0

        dcg += relevance / math.log2(rank + 1)

    ideal_relevant_count = min(len(relevant_ids), k)

    idcg = sum(
        1.0 / math.log2(rank + 1)
        for rank in range(1, ideal_relevant_count + 1)
    )

    if idcg == 0:
        return 0.0

    return dcg / idcg


# ---------------------------------------------------------
# VECTOR STORE LOADING
# ---------------------------------------------------------

def load_vector_store(topic):
    """
    Load an existing FAISS index and metadata
    using the VectorStore instance.
    """

    index_path = VECTOR_STORE_DIR / topic / "index.faiss"
    metadata_path = VECTOR_STORE_DIR / topic / "metadata.json"

    if not index_path.exists():
        raise FileNotFoundError(
            f"FAISS index not found: {index_path}"
        )

    if not metadata_path.exists():
        raise FileNotFoundError(
            f"Metadata file not found: {metadata_path}"
        )

    # Create VectorStore instance first.
    store = VectorStore()

    # Load the existing index into that instance.
    store.load(
        str(index_path),
        str(metadata_path),
    )

    return store




# ---------------------------------------------------------
# RUN EVALUATION FOR ONE QUERY
# ---------------------------------------------------------

def evaluate_query(store, test_case, topic):
    """
    Retrieve chunks and calculate evaluation metrics.
    """

    query = test_case["query"]

    relevant_ids = set(test_case["relevant_chunks"])

    # Retrieve all indexed chunks so the top 5 are selected
    # from the complete search result.
    results = store.search(
        query,
        top_k=store.index.ntotal,
    )

    retrieved_ids = []

    for result in results:
        chunk_id = result.get("chunk_id")

        if chunk_id is None:
            raise ValueError(
                f"Missing chunk_id in search result for topic: {topic}"
            )

        retrieved_ids.append(int(chunk_id))

    # Limit metric calculations to TOP_K.
    metrics = {
        "precision": precision_at_k(
            retrieved_ids,
            relevant_ids,
            TOP_K,
        ),
        "recall": recall_at_k(
            retrieved_ids,
            relevant_ids,
            TOP_K,
        ),
        "mrr": reciprocal_rank_at_k(
            retrieved_ids,
            relevant_ids,
            TOP_K,
        ),
        "ndcg": ndcg_at_k(
            retrieved_ids,
            relevant_ids,
            TOP_K,
        ),
    }

    # Display query results.
    print("\n" + "-" * 90)
    print(f"TOPIC: {topic.upper()}")
    print(f"TEST CASE: {test_case['name']}")
    print(f"QUERY: {query}")
    print("-" * 90)

    print(
        f"{'Rank':<8}"
        f"{'Chunk ID':<12}"
        f"{'Relevant':<12}"
        f"{'Similarity':<15}"
        f"{'Section'}"
    )

    print("-" * 90)

    for rank, result in enumerate(results[:TOP_K], start=1):

        chunk_id = int(result["chunk_id"])

        is_relevant = chunk_id in relevant_ids

        score = result.get(
            "similarity_score",
            result.get("raw_similarity_score", 0.0),
        )

        section = result.get(
            "section_title",
            "Unknown section",
        )

        print(
            f"{rank:<8}"
            f"{chunk_id:<12}"
            f"{str(is_relevant):<12}"
            f"{score:<15.4f}"
            f"{section}"
        )

    print("-" * 90)

    print(
        f"Precision@{TOP_K}: {metrics['precision']:.4f}"
    )
    print(
        f"Recall@{TOP_K}:    {metrics['recall']:.4f}"
    )
    print(
        f"MRR@{TOP_K}:       {metrics['mrr']:.4f}"
    )
    print(
        f"nDCG@{TOP_K}:      {metrics['ndcg']:.4f}"
    )

    return metrics


# ---------------------------------------------------------
# MAIN EVALUATION
# ---------------------------------------------------------

def main():

    print("\n" + "=" * 90)
    print("CONTENT-BASED RETRIEVAL EVALUATION")
    print("=" * 90)

    print(f"Top K: {TOP_K}")
    print("Relevance: Manually reviewed binary chunk labels")
    print("Index modification: Disabled")
    print("=" * 90)

    topic_results = {}

    all_metrics = []

    total_queries = 0

    for topic, test_cases in TEST_CASES.items():

        print("\n" + "#" * 90)
        print(f"LOADING TOPIC: {topic.upper()}")
        print("#" * 90)

        store = load_vector_store(topic)

        current_topic_metrics = []

        for test_case in test_cases:

            metrics = evaluate_query(
                store=store,
                test_case=test_case,
                topic=topic,
            )

            current_topic_metrics.append(metrics)
            all_metrics.append(metrics)

            total_queries += 1

        # Average metrics for the current topic.
        topic_results[topic] = {
            metric: sum(
                result[metric]
                for result in current_topic_metrics
            ) / len(current_topic_metrics)
            for metric in (
                "precision",
                "recall",
                "mrr",
                "ndcg",
            )
        }

    # -----------------------------------------------------
    # FINAL SUMMARY
    # -----------------------------------------------------

    print("\n\n")
    print("=" * 90)
    print("AVERAGE CONTENT RELEVANCE RESULTS")
    print("=" * 90)

    print(
        f"{'Topic':<22}"
        f"{'Precision@5':>14}"
        f"{'Recall@5':>13}"
        f"{'MRR@5':>12}"
        f"{'nDCG@5':>12}"
    )

    print("-" * 90)

    for topic, metrics in topic_results.items():

        print(
            f"{topic:<22}"
            f"{metrics['precision'] * 100:>13.2f}%"
            f"{metrics['recall'] * 100:>12.2f}%"
            f"{metrics['mrr']:>12.4f}"
            f"{metrics['ndcg']:>12.4f}"
        )

    # Macro average across all queries.
    overall_metrics = {
        metric: sum(
            result[metric]
            for result in all_metrics
        ) / len(all_metrics)
        for metric in (
            "precision",
            "recall",
            "mrr",
            "ndcg",
        )
    }

    print("-" * 90)

    print(
        f"{'OVERALL':<22}"
        f"{overall_metrics['precision'] * 100:>13.2f}%"
        f"{overall_metrics['recall'] * 100:>12.2f}%"
        f"{overall_metrics['mrr']:>12.4f}"
        f"{overall_metrics['ndcg']:>12.4f}"
    )

    print("=" * 90)

    print("\nEvaluation summary:")
    print(f"Queries evaluated: {total_queries}")
    print(f"Topics evaluated: {len(topic_results)}")
    print("Relevance labels: Manually reviewed chunk IDs")
    print("Existing indexes were not modified.")
    print("Existing retrieval evaluator was not modified.")

    print("\nEvaluation completed successfully.")


# ---------------------------------------------------------
# ENTRY POINT
# ---------------------------------------------------------

if __name__ == "__main__":
    main()
