import pytest

from app.rag.experimental_join_reranker import (
    detect_preservation_intent,
    extract_preserved_entity,
    normalize_entity,
    infer_join_type,
    rerank_join_results,
)


@pytest.mark.parametrize(
    "query",
    [
        "Return every student including students without enrollments",
        "Show all students even if they have no matching enrollment",
        "Return every customer including customers without orders",
        "List every product whether or not it has a category",
    ],
)
def test_detects_preservation_intent(query):
    assert detect_preservation_intent(query) is True


@pytest.mark.parametrize(
    "query",
    [
        "Return only students who have matching enrollments",
        "Find every student with their matching enrollment",
        "Explain how SQL joins combine two tables",
    ],
)
def test_rejects_non_preservation_queries(query):
    assert detect_preservation_intent(query) is False


@pytest.mark.parametrize(
    "query, expected",
    [
        ("Return every student without enrollments", "student"),
        ("Show all employees without departments", "employees"),
        ("Return every enrollment without a student", "enrollment"),
    ],
)
def test_extracts_preserved_entity(query, expected):
    assert extract_preserved_entity(query) == expected


@pytest.mark.parametrize(
    "entity, expected",
    [
        ("students", "student"),
        ("employees", "employee"),
        ("departments", "department"),
        ("categories", "category"),
        ("student", "student"),
    ],
)
def test_normalizes_entity(entity, expected):
    assert normalize_entity(entity) == expected


@pytest.mark.parametrize(
    "query, expected",
    [
        (
            "Return every student including students without enrollments",
            "LEFT JOIN",
        ),
        (
            "Return every enrollment including those without a student",
            "RIGHT JOIN",
        ),
        (
            "Return only students who have matching enrollments",
            None,
        ),
        (
            "Return every customer including customers without orders",
            None,
        ),
    ],
)
def test_infers_join_type(query, expected):
    assert infer_join_type(query) == expected


def test_reranker_promotes_left_join():
    query = "Return every student including students without enrollments"

    results = [
        {"chunk_id": 2, "section_title": "Sample Tables", "similarity_score": 0.60},
        {"chunk_id": 5, "section_title": "RIGHT JOIN", "similarity_score": 0.54},
        {"chunk_id": 4, "section_title": "LEFT JOIN", "similarity_score": 0.52},
    ]

    reranked = rerank_join_results(results, query)

    assert reranked[0]["section_title"] == "LEFT JOIN"
    assert reranked[0]["chunk_id"] == 4


def test_reranker_promotes_right_join():
    query = "Return every enrollment including those without a student"

    results = [
        {"chunk_id": 2, "section_title": "Sample Tables", "similarity_score": 0.60},
        {"chunk_id": 4, "section_title": "LEFT JOIN", "similarity_score": 0.54},
        {"chunk_id": 5, "section_title": "RIGHT JOIN", "similarity_score": 0.52},
    ]

    reranked = rerank_join_results(results, query)

    assert reranked[0]["section_title"] == "RIGHT JOIN"
    assert reranked[0]["chunk_id"] == 5


def test_non_preservation_query_keeps_original_ranking():
    query = "Return only students who have matching enrollments"

    results = [
        {"chunk_id": 2, "section_title": "Sample Tables", "similarity_score": 0.60},
        {"chunk_id": 3, "section_title": "INNER JOIN", "similarity_score": 0.55},
        {"chunk_id": 4, "section_title": "LEFT JOIN", "similarity_score": 0.52},
    ]

    reranked = rerank_join_results(results, query)

    assert reranked == results


def test_unknown_entity_does_not_apply_join_boost():
    query = "Return every customer including customers without orders"

    results = [
        {"chunk_id": 2, "section_title": "Sample Tables", "similarity_score": 0.60},
        {"chunk_id": 4, "section_title": "LEFT JOIN", "similarity_score": 0.52},
    ]

    reranked = rerank_join_results(results, query)

    assert reranked == results


def test_original_results_are_not_modified():
    query = "Return every student including students without enrollments"

    results = [
        {"chunk_id": 2, "section_title": "Sample Tables", "similarity_score": 0.60},
        {"chunk_id": 4, "section_title": "LEFT JOIN", "similarity_score": 0.52},
    ]

    original = [item.copy() for item in results]

    rerank_join_results(results, query)

    assert results == original
