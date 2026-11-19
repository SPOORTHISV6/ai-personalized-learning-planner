
import app.agents.resource_agent as resource_module


def make_state():
    return {
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


def test_resource_agent_handles_retrieval_exception(monkeypatch):
    def fail_retrieval(**kwargs):
        raise RuntimeError("Internal error")

    monkeypatch.setattr(
        resource_module,
        "retrieve_topic_resources",
        fail_retrieval,
    )

    result = resource_module.resource_agent(make_state())

    assert result["resources"] == []
    assert result["resource_warnings"]
    assert "Normalization" in result["resource_warnings"][0]


def test_resource_agent_handles_non_list_retrieval_result(monkeypatch):
    monkeypatch.setattr(
        resource_module,
        "retrieve_topic_resources",
        lambda **kwargs: None,
    )

    result = resource_module.resource_agent(make_state())

    assert result["resources"] == []
    assert result["resource_warnings"]


def test_resource_agent_skips_invalid_resource_entries(monkeypatch):
    monkeypatch.setattr(
        resource_module,
        "retrieve_topic_resources",
        lambda **kwargs: [
            None,
            "invalid",
            {
                "section_title": "First Normal Form",
                "content": "Normalization explanation",
            },
        ],
    )

    result = resource_module.resource_agent(make_state())

    assert len(result["resources"]) == 1
    assert result["resources"][0]["topic_name"] == "Normalization"
    assert result["resource_warnings"]


def test_resource_agent_does_not_mutate_input_state(monkeypatch):
    state = make_state()
    original_state = {
        key: value.copy() if isinstance(value, list) else value
        for key, value in state.items()
    }

    monkeypatch.setattr(
        resource_module,
        "retrieve_topic_resources",
        lambda **kwargs: [],
    )

    resource_module.resource_agent(state)

    assert state == original_state
    assert "resources" not in state


def test_resource_agent_handles_empty_learning_gaps():
    result = resource_module.resource_agent({
        "student_id": 1,
        "learning_gaps": [],
    })

    assert result["resources"] == []
    assert result["resource_warnings"] == []
