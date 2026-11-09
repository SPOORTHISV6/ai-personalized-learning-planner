
import json
from unittest.mock import Mock

import pytest

import app.agents.resource_agent as resource_module


def test_known_topics_map_to_expected_knowledge_bases():
    expected = {
        "Normalization": "normalization",
        "SQL Joins": "sql_joins",
        "Python OOP": "python",
        "SQL Basics": "sql_basics",
    }

    for topic, knowledge_base in expected.items():
        assert resource_module.get_knowledge_base(topic) == knowledge_base


def test_unknown_topic_is_rejected():
    result = resource_module.get_knowledge_base("Unknown Topic")

    assert result is None


@pytest.mark.parametrize(
    "topic_name",
    [
        "../outside",
        "../../secrets",
        "..\\outside",
        "/tmp/outside",
        "",
        None,
    ],
)
def test_unknown_or_traversal_knowledge_base_is_rejected(topic_name):
    index, metadata = resource_module.load_vector_store(topic_name)

    assert index is None
    assert metadata is None


def test_load_vector_store_rejects_non_dictionary_metadata(
    tmp_path,
    monkeypatch,
):
    vector_dir = tmp_path / "vector_store"
    topic_dir = vector_dir / "normalization"
    topic_dir.mkdir(parents=True)

    index_path = topic_dir / "index.faiss"
    metadata_path = topic_dir / "metadata.json"

    index_path.write_bytes(b"fake index")
    metadata_path.write_text(
        json.dumps([
            {
                "section_title": "First Normal Form",
                "content": "A valid educational chunk.",
            },
            "invalid metadata entry",
        ]),
        encoding="utf-8",
    )

    fake_index = Mock()
    fake_index.ntotal = 2

    monkeypatch.setattr(
        resource_module,
        "VECTOR_STORE_DIR",
        str(vector_dir),
    )
    monkeypatch.setattr(
        resource_module.faiss,
        "read_index",
        lambda path: fake_index,
    )

    index, metadata = resource_module.load_vector_store("normalization")

    assert index is None
    assert metadata is None


def test_load_vector_store_rejects_index_metadata_count_mismatch(
    tmp_path,
    monkeypatch,
):
    vector_dir = tmp_path / "vector_store"
    topic_dir = vector_dir / "normalization"
    topic_dir.mkdir(parents=True)

    (topic_dir / "index.faiss").write_bytes(b"fake index")
    (topic_dir / "metadata.json").write_text(
        json.dumps([
            {"section_title": "First Normal Form", "content": "Content 1"},
            {"section_title": "Second Normal Form", "content": "Content 2"},
        ]),
        encoding="utf-8",
    )

    fake_index = Mock()
    fake_index.ntotal = 1

    monkeypatch.setattr(
        resource_module,
        "VECTOR_STORE_DIR",
        str(vector_dir),
    )
    monkeypatch.setattr(
        resource_module.faiss,
        "read_index",
        lambda path: fake_index,
    )

    index, metadata = resource_module.load_vector_store("normalization")

    assert index is None
    assert metadata is None


@pytest.mark.parametrize(
    "state",
    [
        None,
        [],
        "invalid state",
        {"learning_gaps": "invalid"},
        {"learning_gaps": [None]},
        {"learning_gaps": ["invalid gap"]},
    ],
)
def test_resource_agent_handles_malformed_state(state):
    result = resource_module.resource_agent(state)

    assert isinstance(result, dict)
    assert result.get("next_action") == "stop"
    assert result.get("errors")


def test_resource_agent_preserves_valid_learning_gap_data(monkeypatch):
    expected_resources = [
        {
            "section_title": "First Normal Form",
            "content": "First Normal Form explanation.",
            "page_number": 3,
            "similarity_score": 0.91,
            "ranking_score": 1.8,
            "source": "normalization.pdf",
        }
    ]

    monkeypatch.setattr(
        resource_module,
        "retrieve_topic_resources",
        lambda **kwargs: expected_resources,
    )

    state = {
        "student_id": 1,
        "learning_gaps": [
            {
                "topic_id": 3,
                "topic_name": "Normalization",
                "subject_id": 2,
                "subject_name": "DBMS",
                "status": "weak",
            }
        ],
    }

    result = resource_module.resource_agent(state)

    assert result["resources"]
    assert len(result["resources"]) == 1

    resource = result["resources"][0]

    assert resource["topic_id"] == 3
    assert resource["topic_name"] == "Normalization"
    assert resource["subject_name"] == "DBMS"
    assert resource["resource_type"] == "rag_content"
    assert resource["content"] == "First Normal Form explanation."


def test_unknown_topic_does_not_load_vector_store(monkeypatch):
    load_mock = Mock(
        side_effect=AssertionError("Vector store should not be loaded")
    )

    monkeypatch.setattr(
        resource_module,
        "load_vector_store",
        load_mock,
    )

    result = resource_module.retrieve_topic_resources(
        topic_name="Unknown Topic",
        subject_name="DBMS",
        learning_status="weak",
    )

    assert result == []
    load_mock.assert_not_called()


def test_retrieval_handles_embedding_failure(monkeypatch):
    fake_index = Mock()
    fake_index.ntotal = 1

    monkeypatch.setattr(
        resource_module,
        "load_vector_store",
        lambda topic: (
            fake_index,
            [{"section_title": "First Normal Form", "content": "Content"}],
        ),
    )

    monkeypatch.setattr(
        resource_module,
        "get_embedding_model",
        lambda: Mock(
            encode=Mock(side_effect=RuntimeError("Model unavailable"))
        ),
    )

    result = resource_module.retrieve_topic_resources(
        topic_name="Normalization",
        subject_name="DBMS",
        learning_status="weak",
    )

    assert result == []
