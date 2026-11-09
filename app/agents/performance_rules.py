
"""Shared performance classification rules used by learning-planner agents."""

import math


def classify_performance(score):
    """
    Classify a student's score as weak, moderate, or strong.

    Valid score range: 0 to 100, inclusive.
    """

    if isinstance(score, bool):
        raise ValueError("Score must be a numeric value between 0 and 100.")

    try:
        score = float(score)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(
            "Score must be a numeric value between 0 and 100."
        ) from exc

    if not math.isfinite(score) or not 0 <= score <= 100:
        raise ValueError(
            "Score must be a finite number between 0 and 100."
        )

    if score < 50:
        return "weak"

    if score < 75:
        return "moderate"

    return "strong"


def priority_for_level(level):
    """Map performance level to study-plan priority."""

    priorities = {
        "weak": "high",
        "moderate": "medium",
        "strong": "low",
    }

    # Preserve KeyError behavior for unknown levels.
    return priorities[level]


def evaluate_score(score):
    """
    Return the performance level, priority, and recommended action.

    Invalid scores are rejected by classify_performance().
    """

    level = classify_performance(score)

    recommended_actions = {
        "weak": "increase_practice",
        "moderate": "continue_practice",
        "strong": "reduce_priority",
    }

    return {
        "level": level,
        "priority": priority_for_level(level),
        "recommended_action": recommended_actions[level],
    }
