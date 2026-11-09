
import logging

from app.tools.learning_gap import calculate_learning_gaps


logger = logging.getLogger(__name__)

SAFE_ERROR = "Learning gaps could not be calculated. Please try again later."


def learning_gap_agent(state):
    print("\n[Learning Gap Agent] Analyzing performance...")

    # Validate workflow state
    if not isinstance(state, dict):
        return {
            "errors": ["Invalid workflow state"],
            "next_action": "stop",
        }

    student_id = state.get("student_id")

    # Reject bool because bool is a subclass of int in Python
    if (
        isinstance(student_id, bool)
        or not isinstance(student_id, int)
        or student_id <= 0
    ):
        return {
            "errors": ["A valid student ID is required"],
            "next_action": "stop",
        }

    try:
        gaps = calculate_learning_gaps(student_id)

        if not isinstance(gaps, list):
            logger.error(
                "Learning gap helper returned an invalid result type "
                "for student_id=%s",
                student_id,
            )
            return {
                "errors": [SAFE_ERROR],
                "next_action": "stop",
            }

        for gap in gaps:
            if not isinstance(gap, dict):
                logger.error(
                    "Learning gap helper returned an invalid gap record "
                    "for student_id=%s",
                    student_id,
                )
                return {
                    "errors": [SAFE_ERROR],
                    "next_action": "stop",
                }

        print(
            f"[Learning Gap Agent] Found {len(gaps)} topic records"
        )

        for gap in gaps:
            print(
                "[Learning Gap Agent] "
                f"Topic={gap.get('topic_name')} | "
                f"Score={gap.get('score')} | "
                f"Status={gap.get('status')} | "
                f"Priority={gap.get('priority')}"
            )

        return {
            "learning_gaps": gaps,
            "next_action": "resource",
        }

    except Exception:
        logger.exception(
            "Learning gap calculation failed for student_id=%s",
            student_id,
        )

        return {
            "errors": [SAFE_ERROR],
            "next_action": "stop",
        }
