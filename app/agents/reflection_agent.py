def reflection_agent(state):
    print("\n[Reflection Agent] Reflecting on evaluation...")

    evaluation = state.get("evaluation")

    if not evaluation:
        print(
            "[Reflection Agent] "
            "Evaluation data is missing."
        )

        return {
            "errors": ["Evaluation data is missing"],
            "user_feedback": "Evaluation could not be processed.",
            "next_action": "stop"
        }

    score = float(
        evaluation.get("score", 0)
    )

    level = evaluation.get(
        "level",
        "unknown"
    )

    topic_name = evaluation.get(
        "topic_name",
        "Unknown Topic"
    )

    recommended_action = evaluation.get(
        "recommended_action",
        "continue_practice"
    )

    print(
        f"[Reflection Agent] "
        f"Topic: {topic_name}"
    )

    print(
        f"[Reflection Agent] "
        f"Score: {score}"
    )

    print(
        f"[Reflection Agent] "
        f"Level: {level}"
    )

    # ---------------------------------------------------------
    # Weak performance
    # ---------------------------------------------------------
    if level == "weak":

        feedback = (
            f"Performance in {topic_name} is weak "
            f"with a score of {score:.1f}%. "
            "The topic requires additional practice "
            "and should receive higher priority in the "
            "next study plan."
        )

        print(
            "[Reflection Agent] "
            "Weak performance detected."
        )

        return {
            "user_feedback": feedback,
            "next_action": "replan"
        }

    # ---------------------------------------------------------
    # Moderate performance
    # ---------------------------------------------------------
    elif level == "moderate":

        feedback = (
            f"Performance in {topic_name} is moderate "
            f"with a score of {score:.1f}%. "
            "The student should continue practicing "
            "the topic before moving it to a lower priority."
        )

        print(
            "[Reflection Agent] "
            "Moderate performance detected."
        )

        return {
            "user_feedback": feedback,
            "next_action": "replan"
        }

    # ---------------------------------------------------------
    # Strong performance
    # ---------------------------------------------------------
    elif level == "strong":

        feedback = (
            f"Performance in {topic_name} is strong "
            f"with a score of {score:.1f}%. "
            "The topic can receive lower priority "
            "in the next study plan."
        )

        print(
            "[Reflection Agent] "
            "Strong performance detected."
        )

        return {
            "user_feedback": feedback,
            "next_action": "complete"
        }

    # ---------------------------------------------------------
    # Unknown level
    # ---------------------------------------------------------
    else:

        feedback = (
            f"Evaluation completed for {topic_name}, "
            f"but the performance level '{level}' "
            "is not recognized."
        )

        print(
            "[Reflection Agent] "
            "Unknown performance level."
        )

        return {
            "user_feedback": feedback,
            "errors": [
                f"Unknown performance level: {level}"
            ],
            "next_action": "stop"
        }