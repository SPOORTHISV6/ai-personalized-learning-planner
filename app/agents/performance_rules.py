
"""Shared performance classification rules used by learning-planner agents."""


def classify_performance(score):
    """Classify a student's score as weak, moderate, or strong."""
    score = float(score)

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

    return priorities[level]


def evaluate_score(score):
    """Return the performance level, priority, and recommended action."""
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
