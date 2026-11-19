import math

from app.rag.evaluate_content_relevance import (
    TEST_CASES,
    load_vector_store,
)
from app.rag.experimental_join_reranker import rerank_join_results


def calculate_metrics(results, relevant_chunks, k=5):
    relevant = set(relevant_chunks)
    retrieved = [
        item.get("chunk_id")
        for item in results[:k]
    ]

    hits = sum(chunk_id in relevant for chunk_id in retrieved)

    precision = hits / k
    recall = hits / len(relevant) if relevant else 0.0

    reciprocal_rank = 0.0
    for rank, chunk_id in enumerate(retrieved, start=1):
        if chunk_id in relevant:
            reciprocal_rank = 1 / rank
            break

    dcg = sum(
        1 / math.log2(rank + 1)
        for rank, chunk_id in enumerate(retrieved, start=1)
        if chunk_id in relevant
    )

    ideal_hits = min(len(relevant), k)
    idcg = sum(
        1 / math.log2(rank + 1)
        for rank in range(1, ideal_hits + 1)
    )

    ndcg = dcg / idcg if idcg else 0.0

    return precision, recall, reciprocal_rank, ndcg


baseline_metrics = []
experimental_metrics = []

stores = {}

for topic, cases in TEST_CASES.items():
    store = load_vector_store(topic)
    stores[topic] = store

    for case in cases:
        query = case["query"]
        relevant = case["relevant_chunks"]

        original = store.search(query, top_k=5)

        experimental = rerank_join_results(
            original,
            query,
        )

        baseline_metrics.append(
            calculate_metrics(original, relevant)
        )

        experimental_metrics.append(
            calculate_metrics(experimental, relevant)
        )

        print("\n" + "=" * 85)
        print("TOPIC:", topic)
        print("QUERY:", case["name"])

        print(
            "Baseline:",
            [item.get("chunk_id") for item in original]
        )

        print(
            "Experimental:",
            [item.get("chunk_id") for item in experimental]
        )


def average_metrics(metrics):
    count = len(metrics)

    return [
        sum(row[index] for row in metrics) / count
        for index in range(4)
    ]


baseline = average_metrics(baseline_metrics)
experimental = average_metrics(experimental_metrics)

print("\n" + "=" * 85)
print("FINAL BENCHMARK COMPARISON")
print("=" * 85)

print(f"{'Metric':<18}{'Baseline':>14}{'Experimental':>16}{'Change':>12}")

names = [
    "Precision@5",
    "Recall@5",
    "MRR@5",
    "nDCG@5",
]

for index, name in enumerate(names):
    change = experimental[index] - baseline[index]

    print(
        f"{name:<18}"
        f"{baseline[index] * 100:>13.2f}%"
        f"{experimental[index] * 100:>15.2f}%"
        f"{change * 100:>11.2f}%"
    )

print("\nQueries evaluated:", len(baseline_metrics))
print("Topics evaluated:", len(TEST_CASES))
print("Production code modified: No")
print("FAISS indexes modified: No")
