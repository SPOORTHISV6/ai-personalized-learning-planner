import re


ENTITY_JOIN_MAPPING = {
    "student": "LEFT JOIN",
    "enrollment": "RIGHT JOIN",
}


def detect_preservation_intent(query):
    patterns = [
        r"\b(?:every|all)\s+\w+\b.*\bincluding\b.*\bwithout\b",
        r"\b(?:every|all)\s+\w+\b.*\beven if\b.*\bno\b",
        r"\b(?:every|all)\s+\w+\b.*\bwhether or not\b",
        r"\b(?:every|all)\s+\w+\b.*\bincluding\b.*\bempty\b",
        r"\b(?:every|all)\s+\w+\b.*\bregardless of\b",
        r"\b(?:every|all)\s+\w+\b.*\bwithout matching\b",
    ]

    normalized = query.casefold()

    return any(
        re.search(pattern, normalized)
        for pattern in patterns
    )


def extract_preserved_entity(query):
    match = re.search(
        r"\b(?:every|all)\s+([a-z]+)",
        query.casefold()
    )

    return match.group(1) if match else None


def normalize_entity(entity):
    if not entity:
        return None

    if entity.endswith("ies"):
        return entity[:-3] + "y"

    if entity.endswith("s"):
        return entity[:-1]

    return entity


def infer_join_type(query):
    if not detect_preservation_intent(query):
        return None

    entity = normalize_entity(
        extract_preserved_entity(query)
    )

    return ENTITY_JOIN_MAPPING.get(entity)


def rerank_join_results(results, query, boost=0.20):
    inferred_join = infer_join_type(query)

    if inferred_join is None:
        return results

    reranked = []

    for item in results:
        updated = item.copy()

        if (
            updated.get("section_title", "").casefold()
            == inferred_join.casefold()
        ):
            updated["experimental_join_boost"] = boost
        else:
            updated["experimental_join_boost"] = 0.0

        updated["experimental_score"] = (
            updated.get("similarity_score", 0.0)
            + updated["experimental_join_boost"]
        )

        reranked.append(updated)

    reranked.sort(
        key=lambda item: item["experimental_score"],
        reverse=True
    )

    return reranked
