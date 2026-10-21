from datetime import datetime

from app.database.connection import SessionLocal

from app.database.models import (
    StudyPlan,
    StudyPlanItem
)


def persistence_agent(state):

    print("[Persistence Agent] Persisting adaptive study plan...")

    student_id = state.get("student_id")
    study_plan = state.get("study_plan")
    validation = state.get("validation")

    # ---------------------------------------------------------
    # Basic validation
    # ---------------------------------------------------------

    if not student_id:
        return {
            "errors": ["Student ID is missing"],
            "next_action": "stop"
        }

    if not study_plan:
        return {
            "errors": ["Study plan is missing"],
            "next_action": "stop"
        }

    if not validation or not validation.get("valid"):
        return {
            "errors": ["Study plan validation failed"],
            "next_action": "stop"
        }

    sessions = study_plan.get("sessions", [])

    if not sessions:
        return {
            "errors": ["Study plan contains no sessions"],
            "next_action": "stop"
        }

    db = SessionLocal()

    try:

        # -----------------------------------------------------
        # Calculate plan dates
        # -----------------------------------------------------

        session_dates = [
            session["date"]
            for session in sessions
            if session.get("date")
        ]

        if not session_dates:
            return {
                "errors": ["No valid session dates found"],
                "next_action": "stop"
            }

        start_date = min(session_dates)
        end_date = max(session_dates)

        # -----------------------------------------------------
        # Find active plans for this student
        # -----------------------------------------------------

        active_plans = (
            db.query(StudyPlan)
            .filter(
                StudyPlan.student_id == student_id,
                StudyPlan.status == "active"
            )
            .all()
        )

        # -----------------------------------------------------
        # Compare generated plan with existing active plans
        # -----------------------------------------------------

        identical_plan = None

        for existing_plan in active_plans:

            existing_items = (
                db.query(StudyPlanItem)
                .filter(
                    StudyPlanItem.plan_id == existing_plan.plan_id
                )
                .order_by(
                    StudyPlanItem.scheduled_date
                )
                .all()
            )

            if len(existing_items) != len(sessions):
                continue

            plan_matches = True

            for existing_item, session in zip(
                existing_items,
                sessions
            ):

                generated_priority = session.get(
                    "priority",
                    "medium"
                )

                # Convert human-readable priority
                # into database integer.
                if isinstance(generated_priority, str):

                    priority_map = {
                        "high": 5,
                        "medium": 3,
                        "low": 1
                    }

                    generated_priority = priority_map.get(
                        generated_priority.lower(),
                        3
                    )

                generated_date = session.get("date")

                generated_duration = session.get(
                    "duration_minutes",
                    0
                )

                if (
                    existing_item.topic_id
                    != session.get("topic_id")
                ):
                    plan_matches = False
                    break

                if str(existing_item.scheduled_date)[:10] != str(
                    generated_date
                )[:10]:
                    plan_matches = False
                    break

                if (
                    existing_item.duration_minutes
                    != generated_duration
                ):
                    plan_matches = False
                    break

                if (
                    existing_item.priority
                    != generated_priority
                ):
                    plan_matches = False
                    break

            if plan_matches:
                identical_plan = existing_plan
                break

        # -----------------------------------------------------
        # CASE 1: Identical active plan already exists
        # -----------------------------------------------------

        if identical_plan:

            print(
                "[Persistence Agent] "
                "Identical active plan already exists."
            )

            print(
                f"[Persistence Agent] "
                f"Reusing StudyPlan ID: "
                f"{identical_plan.plan_id}"
            )

            existing_items = (
                db.query(StudyPlanItem)
                .filter(
                    StudyPlanItem.plan_id
                    == identical_plan.plan_id
                )
                .order_by(
                    StudyPlanItem.scheduled_date
                )
                .all()
            )

            persisted_items = []

            for item in existing_items:

                persisted_items.append(
                    {
                        "item_id": item.item_id,
                        "topic_id": item.topic_id,
                        "scheduled_date": str(
                            item.scheduled_date
                        )[:10],
                        "duration_minutes":
                            item.duration_minutes,
                        "priority":
                            item.priority,
                        "status":
                            item.status
                    }
                )

            return {
                "persisted_plan": {
                    "plan_id":
                        identical_plan.plan_id,

                    "student_id":
                        identical_plan.student_id,

                    "start_date":
                        str(
                            identical_plan.start_date
                        ),

                    "end_date":
                        str(
                            identical_plan.end_date
                        ),

                    "status":
                        identical_plan.status,

                    "total_sessions":
                        len(persisted_items),

                    "created_new_plan":
                        False,

                    "items":
                        persisted_items
                },

                "persistence_action":
                    "reused",

                "next_action":
                    "complete"
            }

        # -----------------------------------------------------
        # CASE 2: New plan is different
        # -----------------------------------------------------

        print(
            "[Persistence Agent] "
            "New adaptive plan detected."
        )

        # -----------------------------------------------------
        # Supersede previous active plans
        # -----------------------------------------------------

        for old_plan in active_plans:

            old_plan.status = "superseded"

        db.flush()

        print(
            "[Persistence Agent] "
            f"Superseded {len(active_plans)} "
            "previous active plan(s)."
        )

        # -----------------------------------------------------
        # Create new study plan
        # -----------------------------------------------------

        new_plan = StudyPlan(
            student_id=student_id,
            start_date=start_date,
            end_date=end_date,
            status="active"
        )

        db.add(new_plan)

        db.flush()

        # -----------------------------------------------------
        # Create study plan items
        # -----------------------------------------------------

        persisted_items = []

        for session in sessions:

            priority = session.get(
                "priority",
                "medium"
            )

            # -------------------------------------------------
            # Convert priority label to DB integer
            # -------------------------------------------------

            if isinstance(priority, str):

                priority_map = {
                    "high": 5,
                    "medium": 3,
                    "low": 1
                }

                priority = priority_map.get(
                    priority.lower(),
                    3
                )

            item = StudyPlanItem(
                plan_id=new_plan.plan_id,

                topic_id=session.get(
                    "topic_id"
                ),

                scheduled_date=session.get(
                    "date"
                ),

                duration_minutes=session.get(
                    "duration_minutes",
                    0
                ),

                priority=priority,

                status="pending"
            )

            db.add(item)

            db.flush()

            persisted_items.append(
                {
                    "item_id": item.item_id,

                    "topic_id":
                        item.topic_id,

                    "scheduled_date":
                        str(
                            item.scheduled_date
                        )[:10],

                    "duration_minutes":
                        item.duration_minutes,

                    "priority":
                        item.priority,

                    "status":
                        item.status
                }
            )

        # -----------------------------------------------------
        # Commit everything
        # -----------------------------------------------------

        db.commit()

        db.refresh(new_plan)

        print(
            "[Persistence Agent] "
            f"Created new StudyPlan ID: "
            f"{new_plan.plan_id}"
        )

        return {

            "persisted_plan": {

                "plan_id":
                    new_plan.plan_id,

                "student_id":
                    new_plan.student_id,

                "start_date":
                    str(
                        new_plan.start_date
                    ),

                "end_date":
                    str(
                        new_plan.end_date
                    ),

                "status":
                    new_plan.status,

                "total_sessions":
                    len(persisted_items),

                "created_new_plan":
                    True,

                "items":
                    persisted_items
            },

            "persistence_action":
                "created_new_plan",

            "next_action":
                "complete"
        }

    except Exception as e:

        db.rollback()

        print(
            "[Persistence Agent] "
            f"Error: {str(e)}"
        )

        return {
            "errors": [
                f"Persistence failed: {str(e)}"
            ],
            "next_action": "stop"
        }

    finally:

        db.close()