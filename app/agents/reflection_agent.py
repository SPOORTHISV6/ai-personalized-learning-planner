import logging
import math
import re

from app.agents.performance_rules import classify_performance


logger = logging.getLogger(__name__)


# ---------------------------------------------------------
# CONSTANTS
# ---------------------------------------------------------

VALID_PERFORMANCE_LEVELS = {
    "weak",
    "moderate",
    "strong",
}

MAX_TOPIC_NAME_LENGTH = 120
MAX_ERROR_LEVEL_LENGTH = 40

SAFE_ERROR_FEEDBACK = "Evaluation could not be processed."


# ---------------------------------------------------------
# HELPER FUNCTIONS
# ---------------------------------------------------------

def stop_workflow(error_message, user_feedback=SAFE_ERROR_FEEDBACK):
    """Return a consistent safe workflow-stop response."""
    return {
        "errors": [error_message],
        "user_feedback": user_feedback,
        "next_action": "stop",
    }


def sanitize_topic_name(topic_name):
    """
    Sanitize a topic name before using it in feedback or logs.

    Removes control characters and limits the maximum length.
    """
    if not isinstance(topic_name, str):
        return "Unknown Topic"

    topic_name = re.sub(r"[\x00-\x1f\x7f]", " ", topic_name)
    topic_name = re.sub(r"\s+", " ", topic_name).strip()

    if not topic_name:
        return "Unknown Topic"

    return topic_name[:MAX_TOPIC_NAME_LENGTH]


def validate_score(raw_score):
    """
    Validate and normalize an evaluation score.

    Valid scores must be numeric, finite, and between 0 and 100.
    Boolean values are explicitly rejected because bool is a
    subclass of int in Python.
    """
    if isinstance(raw_score, bool):
        return None, "Evaluation score is invalid"

    if raw_score is None:
        return None, "Evaluation score is missing or invalid"

    try:
        score = float(raw_score)

    except (TypeError, ValueError, OverflowError):
        return None, "Evaluation score is missing or invalid"

    if not math.isfinite(score):
        return None, "Evaluation score is invalid"

    if not 0 <= score <= 100:
        return None, "Evaluation score is outside the valid range"

    return score, None


# ---------------------------------------------------------
# REFLECTION AGENT
# ---------------------------------------------------------

def reflection_agent(state):
    """
    Analyze student performance and determine the next workflow action.

    Routing:
        weak     -> replan
        moderate -> replan
        strong   -> complete
    """

    print("\n[Reflection Agent] Reflecting on evaluation...")

    # -----------------------------------------------------
    # 1. VALIDATE WORKFLOW STATE
    # -----------------------------------------------------

    if not isinstance(state, dict):
        return stop_workflow(
            "Invalid workflow state",
        )

    # -----------------------------------------------------
    # 2. RETRIEVE AND VALIDATE EVALUATION
    # -----------------------------------------------------

    evaluation = state.get("evaluation")

    if evaluation is None:
        return stop_workflow(
            "Evaluation data is missing",
        )

    if not isinstance(evaluation, dict):
        return stop_workflow(
            "Evaluation data is invalid",
        )

    # -----------------------------------------------------
    # 3. VALIDATE SCORE
    # -----------------------------------------------------

    raw_score = evaluation.get("score")

    score, score_error = validate_score(raw_score)

    if score_error:
        if score_error == "Evaluation score is outside the valid range":
            return stop_workflow(
                score_error,
                "Evaluation score must be between 0 and 100.",
            )

        return stop_workflow(
            score_error,
            "Evaluation could not be processed because the score is invalid.",
        )

    # -----------------------------------------------------
    # 4. DERIVE EXPECTED PERFORMANCE LEVEL
    # -----------------------------------------------------

    try:
        expected_level = classify_performance(score)

    except Exception:
        logger.exception(
            "Performance classification failed"
        )

        return stop_workflow(
            "Performance classification failed",
        )

    if expected_level not in VALID_PERFORMANCE_LEVELS:
        logger.error(
            "Shared performance rules returned an invalid level"
        )

        return stop_workflow(
            "Performance classification returned an invalid result",
        )

    # -----------------------------------------------------
    # 5. VALIDATE SUPPLIED PERFORMANCE LEVEL
    # -----------------------------------------------------

    raw_level = evaluation.get("level")

    if not isinstance(raw_level, str) or not raw_level.strip():
        return stop_workflow(
            "Performance level is missing or invalid",
        )

    level = raw_level.strip().lower()

    if level not in VALID_PERFORMANCE_LEVELS:
        safe_level = re.sub(
            r"[\x00-\x1f\x7f]",
            "",
            level,
        )[:MAX_ERROR_LEVEL_LENGTH]

        return stop_workflow(
            f"Unknown performance level: {safe_level}",
            "The performance level could not be recognized.",
        )

    # -----------------------------------------------------
    # 6. VERIFY SCORE AND PERFORMANCE LEVEL CONSISTENCY
    # -----------------------------------------------------

    if level != expected_level:
        logger.warning(
            "Performance level mismatch: supplied=%s, expected=%s",
            level,
            expected_level,
        )

        return stop_workflow(
            "Performance level does not match evaluation score",
            "Evaluation data is inconsistent and needs to be checked.",
        )

    # -----------------------------------------------------
    # 7. SANITIZE TOPIC NAME
    # -----------------------------------------------------

    topic_name = sanitize_topic_name(
        evaluation.get("topic_name")
    )

    print(f"[Reflection Agent] Topic: {topic_name}")
    print(f"[Reflection Agent] Score: {score:.1f}")
    print(f"[Reflection Agent] Level: {level}")

    # -----------------------------------------------------
    # 8. WEAK PERFORMANCE
    # -----------------------------------------------------

    if level == "weak":

        feedback = (
            f"Performance in {topic_name} is weak "
            f"with a score of {score:.1f}%. "
            "The topic requires additional practice "
            "and should receive higher priority in the "
            "next study plan."
        )

        print(
            "[Reflection Agent] Weak performance detected."
        )

        return {
            "user_feedback": feedback,
            "next_action": "replan",
        }

    # -----------------------------------------------------
    # 9. MODERATE PERFORMANCE
    # -----------------------------------------------------

    if level == "moderate":

        feedback = (
            f"Performance in {topic_name} is moderate "
            f"with a score of {score:.1f}%. "
            "The student should continue practicing "
            "the topic before moving it to a lower priority."
        )

        print(
            "[Reflection Agent] Moderate performance detected."
        )

        return {
            "user_feedback": feedback,
            "next_action": "replan",
        }

    # -----------------------------------------------------
    # 10. STRONG PERFORMANCE
    # -----------------------------------------------------

    feedback = (
        f"Performance in {topic_name} is strong "
        f"with a score of {score:.1f}%. "
        "The topic can receive lower priority "
        "in the next study plan."
    )

    print(
        "[Reflection Agent] Strong performance detected."
    )

    return {
        "user_feedback": feedback,
        "next_action": "complete",
    }