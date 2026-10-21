
import os
import requests
import streamlit as st
from datetime import datetime

# ============================================================
# CONFIGURATION
# ============================================================

API_BASE_URL = os.getenv(
    "API_BASE_URL",
    "http://127.0.0.1:8000",
)

STUDENT_ID = 1
QUIZ_ID = 2
REQUEST_TIMEOUT = 60

PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)

TOPIC_NAMES = {
    1: "SQL Basics",
    2: "SQL Joins",
    3: "Normalization",
    4: "Python OOP",
}


# ============================================================
# PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="AI Personalized Learning Planner",
    page_icon="🎓",
    layout="wide",
)


# ============================================================
# SESSION STATE
# ============================================================

if "quiz_result" not in st.session_state:
    st.session_state.quiz_result = None


# ============================================================
# API HELPERS
# ============================================================

def api_request(method, endpoint, **kwargs):
    """Send an HTTP request to the FastAPI backend."""

    url = f"{API_BASE_URL}{endpoint}"

    try:
        response = requests.request(
            method,
            url,
            timeout=REQUEST_TIMEOUT,
            **kwargs,
        )

        response.raise_for_status()

        if not response.content:
            return {}

        return response.json()

    except requests.exceptions.ConnectionError:
        st.error(
            "Cannot connect to FastAPI.\n\n"
            "Start the backend using:\n\n"
            ".venv\\Scripts\\python.exe -m "
            "uvicorn app.main:app --reload"
        )
        return None

    except requests.exceptions.Timeout:
        st.error(f"Request timed out: {endpoint}")
        return None

    except requests.exceptions.HTTPError as error:
        try:
            details = response.json()
        except ValueError:
            details = response.text

        st.error(
            f"API error: {error}\n\n"
            f"Details: {details}"
        )
        return None

    except requests.exceptions.RequestException as error:
        st.error(f"Request failed: {error}")
        return None


def api_get(endpoint):
    return api_request("GET", endpoint)


def api_post(endpoint, payload):
    return api_request(
        "POST",
        endpoint,
        json=payload,
    )


def get_student_profile():
    return api_get(f"/students/{STUDENT_ID}")


def get_dashboard():
    return api_get(
        f"/dashboard/student/{STUDENT_ID}"
    )


def get_study_plans():
    return api_get(
        f"/study-plans/student/{STUDENT_ID}"
    )


def get_plan_items(plan_id):
    return api_get(
        f"/study-plan-items/plan/{plan_id}"
    )


def get_topic_resources(topic_id):
    return api_get(
        f"/resources/topic/{topic_id}"
    )


def get_quiz_questions(quiz_id):
    return api_get(
        f"/quizzes/{quiz_id}/questions"
    )


def update_session_status(item_id, status):
    return api_request(
        "PUT",
        f"/study-plan-items/{item_id}/status",
        json={"status": status},
    )


# ============================================================
# QUIZ SUBMISSION
# ============================================================

def submit_quiz(quiz_id, answers):
    """Submit MCQ answers for server-side grading."""

    payload = {
        "student_id": STUDENT_ID,
        "answers": answers,
    }

    return api_post(
        f"/quiz-results/?quiz_id={quiz_id}",
        payload,
    )


# ============================================================
# RESPONSE NORMALIZATION HELPERS
# ============================================================

def normalize_list_response(data, *possible_keys):
    """Handle APIs that return either a list or a wrapped list."""

    if isinstance(data, list):
        return data

    if isinstance(data, dict):
        for key in possible_keys:
            value = data.get(key)
            if isinstance(value, list):
                return value

    return []


def resolve_resource_path(resource):
    """Resolve a resource PDF path relative to the project root."""

    raw_path = (
        resource.get("content_path")
        or resource.get("file_path")
        or resource.get("path")
        or ""
    )

    if not raw_path:
        return ""

    if os.path.isabs(raw_path):
        return os.path.normpath(raw_path)

    return os.path.normpath(
        os.path.join(PROJECT_ROOT, raw_path)
    )


# ============================================================
# DATA LOADING
# ============================================================

profile = get_student_profile()
dashboard = get_dashboard()
study_plans_response = get_study_plans()

if profile is None or dashboard is None:
    st.stop()

if study_plans_response is None:
    study_plans_response = []

plans = normalize_list_response(
    study_plans_response,
    "plans",
    "study_plans",
)


# ============================================================
# HEADER
# ============================================================

st.title("🎓 AI Personalized Learning & Study Planner")

st.write(
    "An adaptive AI-powered learning system that analyzes "
    "student performance, retrieves learning resources, "
    "and dynamically generates personalized study plans."
)

st.divider()


# ============================================================
# STUDENT PROFILE
# ============================================================

st.subheader("👤 Student Profile")

profile_col1, profile_col2, profile_col3, profile_col4 = (
    st.columns(4)
)

with profile_col1:
    st.metric(
        "Student",
        profile.get("name", "N/A"),
    )

with profile_col2:
    st.metric(
        "Email",
        profile.get("email", "N/A"),
    )

with profile_col3:
    st.metric(
        "Daily Study Time",
        f"{profile.get('daily_available_hours', 0)} hrs",
    )

with profile_col4:
    st.metric(
        "Learning Preference",
        profile.get("learning_preference", "N/A"),
    )

st.divider()


# ============================================================
# LEARNING DASHBOARD
# ============================================================

st.subheader("📊 Learning Dashboard")

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric(
        "Average Score",
        f"{dashboard.get('average_score', 0)}%",
    )

with col2:
    st.metric(
        "Weak Topics",
        dashboard.get("weak_topics", 0),
    )

with col3:
    st.metric(
        "Moderate Topics",
        dashboard.get("moderate_topics", 0),
    )

with col4:
    st.metric(
        "Strong Topics",
        dashboard.get("strong_topics", 0),
    )

col1, col2, col3 = st.columns(3)

with col1:
    st.metric(
        "Subjects",
        dashboard.get("total_subjects", 0),
    )

with col2:
    st.metric(
        "Active Plans",
        dashboard.get("active_study_plans", 0),
    )

with col3:
    st.metric(
        "Total Topics",
        dashboard.get("total_topics", 0),
    )

st.divider()


# ============================================================
# TAKE ASSESSMENT
# ============================================================

st.subheader("📝 Take Assessment")

st.caption(
    "Answer every question. The backend grades your answers "
    "and runs the adaptive learning workflow."
)

quiz_questions_response = get_quiz_questions(QUIZ_ID)

quiz_questions = normalize_list_response(
    quiz_questions_response,
    "questions",
)

if not quiz_questions:
    st.info(
        f"No questions are available for Quiz #{QUIZ_ID}. "
        "Add questions through the quiz API first."
    )

else:
    with st.form(key=f"quiz_form_{QUIZ_ID}"):

        st.caption(
            f"Quiz ID: {QUIZ_ID} | "
            f"Total Questions: {len(quiz_questions)}"
        )

        submitted_answers = []

        for index, question in enumerate(quiz_questions, start=1):

            question_id = question.get("question_id")

            st.markdown(
                f"**Q{index}. "
                f"{question.get('question_text', '')}**"
            )

            option_values = {
                "A": question.get("option_a", ""),
                "B": question.get("option_b", ""),
                "C": question.get("option_c", ""),
                "D": question.get("option_d", ""),
            }

            option_labels = [
                f"{letter}. {value}"
                for letter, value in option_values.items()
                if value
            ]

            selected = st.radio(
                "Choose your answer",
                options=option_labels,
                index=None,
                key=f"quiz_{QUIZ_ID}_question_{question_id}",
            )

            if selected:
                selected_option = selected.split(".", 1)[0].strip()

                submitted_answers.append({
                    "question_id": question_id,
                    "selected_option": selected_option,
                })

            st.caption(
                f"Points: {question.get('points', 1)}"
            )

            st.divider()

        submit_button = st.form_submit_button(
            "🚀 Submit Quiz",
            use_container_width=True,
        )

    if submit_button:

        if len(submitted_answers) != len(quiz_questions):
            st.warning(
                "Please answer every question before submitting."
            )

        else:
            with st.spinner(
                "Grading answers and running adaptive workflow..."
            ):
                result = submit_quiz(
                    QUIZ_ID,
                    submitted_answers,
                )

            if result is not None:
                st.session_state.quiz_result = result
                st.success(
                    "Quiz submitted and evaluated successfully."
                )
                st.rerun()


# ============================================================
# LATEST ASSESSMENT RESULT
# ============================================================

result = st.session_state.quiz_result

if result:

    st.divider()
    st.subheader("🎯 Latest Assessment Result")

    result_col1, result_col2, result_col3 = st.columns(3)

    with result_col1:
        st.metric(
            "Score",
            f"{result.get('score', 0)}%",
        )

    evaluation = result.get("evaluation") or {}

    with result_col2:
        st.metric(
            "Performance Level",
            evaluation.get(
                "level",
                "Not available",
            ).title(),
        )

    with result_col3:
        recommended_action = evaluation.get(
            "recommended_action",
            "Not available",
        )

        st.metric(
            "Recommended Action",
            recommended_action.replace("_", " ").title(),
        )

    st.write(
        f"**Correct answers:** "
        f"{result.get('correct_answers', 0)} / "
        f"{result.get('total_questions', 0)}"
    )

    st.markdown("### Answer Review")

    for index, answer in enumerate(
        result.get("answers", []),
        start=1,
    ):

        if answer.get("is_correct"):
            st.success(
                f"Question {index}: Correct "
                f"(+{answer.get('points_awarded', 0)} points)"
            )
        else:
            st.error(f"Question {index}: Incorrect")

        st.write(
            f"Your answer: {answer.get('selected_option', 'N/A')}"
        )

        st.write(
            f"Correct answer: {answer.get('correct_option', 'N/A')}"
        )

        if answer.get("explanation"):
            st.info(answer["explanation"])

    st.markdown("### 🤖 Adaptive Workflow Result")

    workflow_status = result.get(
        "workflow_status",
        "unknown",
    )

    if workflow_status == "completed":
        st.success(
            f"Workflow status: {workflow_status.title()}"
        )
    else:
        st.warning(
            f"Workflow status: {workflow_status}"
        )

    if result.get("user_feedback"):
        st.info(result["user_feedback"])

    if result.get("validation"):
        st.write("**Plan validation:**")
        st.json(result["validation"])

    workflow_errors = result.get("errors", [])

    if workflow_errors:
        st.warning("Workflow messages:")
        for error in workflow_errors:
            st.write(f"- {error}")

    if result.get("workflow_error"):
        st.error(result["workflow_error"])


st.divider()


# ============================================================
# CURRENT STUDY PLAN
# ============================================================

st.subheader("📚 Current Study Plan")

active_plan = next(
    (
        plan
        for plan in plans
        if str(plan.get("status", "")).lower() == "active"
    ),
    None,
)

plan_items = []

if active_plan is None:

    st.info(
        "No active study plan is available. "
        "Submit an assessment to trigger the adaptive workflow."
    )

else:

    plan_id = active_plan.get("plan_id")

    st.success(f"Active Plan: Plan #{plan_id}")

    if active_plan.get("start_date"):
        st.write(
            f"**Start Date:** {active_plan['start_date']}"
        )

    if active_plan.get("end_date"):
        st.write(
            f"**End Date:** {active_plan['end_date']}"
        )

    st.write(
        f"**Status:** "
        f"{active_plan.get('status', 'active').title()}"
    )

    plan_items_response = get_plan_items(plan_id)

    plan_items = normalize_list_response(
        plan_items_response,
        "items",
        "study_plan_items",
    )

    if not plan_items:

        st.info(
            "No study sessions were found for this plan."
        )

    else:

        st.markdown("### Study Sessions")

        for item in plan_items:

            item_id = item.get("item_id")
            topic_id = item.get("topic_id")

            topic_name = TOPIC_NAMES.get(
                topic_id,
                f"Topic {topic_id}",
            )

            scheduled_date = item.get(
                "scheduled_date",
                "Not scheduled",
            )

            if scheduled_date and scheduled_date != "Not scheduled":
                try:
                    parsed_date = datetime.fromisoformat(
                        scheduled_date.replace("Z", "+00:00")
                    )
                    scheduled_date = parsed_date.strftime("%d %b %Y")
                except (ValueError, TypeError):
                    pass

            duration = item.get("duration_minutes", 0)
            priority_value = item.get("priority", 3)

            if priority_value >= 5:
                priority_label = "High"
            elif priority_value >= 3:
                priority_label = "Medium"
            else:
                priority_label = "Low"

            current_status = str(
                item.get("status", "pending")
            ).lower()

            status_options = [
                "pending",
                "in_progress",
                "completed",
            ]

            if current_status not in status_options:
                current_status = "pending"

            with st.container(border=True):

                st.markdown(f"**{topic_name}**")

                details_col1, details_col2, details_col3 = (
                    st.columns(3)
                )

                with details_col1:
                    st.write(f"📅 {scheduled_date}")

                with details_col2:
                    st.write(f"⏱️ {duration} minutes")

                with details_col3:
                    st.write(f"Priority: {priority_label}")

                st.write(
                    f"Current status: "
                    f"**{current_status.replace('_', ' ').title()}**"
                )

                status_col, button_col = st.columns([3, 1])

                with status_col:
                    new_status = st.selectbox(
                        "Update session status",
                        options=status_options,
                        index=status_options.index(current_status),
                        format_func=lambda value: value.replace(
                            "_", " "
                        ).title(),
                        key=f"status_{item_id}",
                    )

                with button_col:
                    st.write("")
                    st.write("")

                    if st.button(
                        "Update",
                        key=f"update_{item_id}",
                        use_container_width=True,
                    ):

                        updated = update_session_status(
                            item_id,
                            new_status,
                        )

                        if updated is not None:
                            st.success(
                                f"{topic_name} updated to "
                                f"{new_status.replace('_', ' ')}."
                            )
                            st.rerun()


st.divider()


# ============================================================
# RECOMMENDED LEARNING RESOURCES
# ============================================================

st.subheader("📖 Recommended Learning Resources")

if active_plan is None:

    st.info(
        "Resources will appear when an active study plan is available."
    )

else:

    resource_topic_ids = sorted({
        item.get("topic_id")
        for item in plan_items
        if item.get("topic_id") is not None
    })

    if not resource_topic_ids:
        st.info(
            "No topics are available for resource retrieval."
        )

    for topic_id in resource_topic_ids:

        topic_name = TOPIC_NAMES.get(
            topic_id,
            f"Topic {topic_id}",
        )

        with st.expander(
            f"📘 {topic_name}",
            expanded=True,
        ):

            resources_response = get_topic_resources(topic_id)

            resources = normalize_list_response(
                resources_response,
                "resources",
            )

            if resources_response is None:

                st.warning(
                    "Unable to load resources for this topic."
                )
                continue

            if not resources:

                st.info(
                    f"No learning resources found for {topic_name}."
                )
                continue

            # Deduplicate resources by their actual file path.
            # Different database IDs can still point to the same PDF.
            unique_resources = []
            seen_paths = set()
            seen_resource_ids = set()

            for resource in resources:

                resolved_path = resolve_resource_path(resource)

                resource_id = resource.get("resource_id")

                if resolved_path:
                    deduplication_key = os.path.normcase(
                        os.path.normpath(resolved_path)
                    )
                elif resource_id is not None:
                    deduplication_key = f"resource_id:{resource_id}"
                else:
                    deduplication_key = (
                        f"title:{resource.get('title', '')}"
                    )

                if deduplication_key in seen_paths:
                    continue

                if (
                    resource_id is not None
                    and resource_id in seen_resource_ids
                ):
                    continue

                seen_paths.add(deduplication_key)

                if resource_id is not None:
                    seen_resource_ids.add(resource_id)

                unique_resources.append(resource)

            for resource in unique_resources:

                resource_title = resource.get(
                    "title",
                    resource.get(
                        "resource_name",
                        "Learning Resource",
                    ),
                )

                st.markdown(f"**{resource_title}**")

                if resource.get("description"):
                    st.write(resource["description"])

                if resource.get("section_title"):
                    st.caption(
                        f"Section: {resource['section_title']}"
                    )

                resolved_path = resolve_resource_path(resource)

                if resolved_path:

                    display_path = resource.get(
                        "content_path",
                        resource.get(
                            "file_path",
                            resource.get("path", resolved_path),
                        ),
                    )

                    st.caption(f"File: {display_path}")

                    if os.path.isfile(resolved_path):

                        try:
                            with open(resolved_path, "rb") as pdf_file:
                                pdf_data = pdf_file.read()

                            st.download_button(
                                label="📥 Download Study Material",
                                data=pdf_data,
                                file_name=os.path.basename(resolved_path),
                                mime="application/pdf",
                                key=(
                                    f"download_resource_{topic_id}_"
                                    f"{resource.get('resource_id', resource_title)}"
                                ),
                            )

                        except OSError as error:
                            st.error(
                                f"Could not read the PDF: {error}"
                            )

                    else:
                        st.warning(
                            "PDF file not found at the resolved path: "
                            f"{resolved_path}"
                        )

                elif resource.get("url"):

                    st.markdown(
                        f"[Open Resource]({resource['url']})"
                    )

                else:

                    st.warning(
                        "This resource has no file path or URL."
                    )

                st.divider()


# ============================================================
# HOW YOUR PLAN ADAPTS
# ============================================================

st.divider()
st.subheader("🤖 How Your Plan Adapts")

st.info(
    """
🔴 **Weak performance** → Increase study priority and reinforce prerequisites.

🟡 **Moderate performance** → Continue practice and strengthen understanding.

🟢 **Strong performance** → Reduce topic priority or remove it from the next plan when appropriate.

Quiz results are stored in MySQL and used by the adaptive workflow to evaluate performance and generate or reuse a study plan.
"""
)


# ============================================================
# ADAPTIVE LEARNING STATUS
# ============================================================

st.divider()
st.subheader("🔄 Adaptive Learning Status")

active_plan_id = dashboard.get("active_plan_id")

if active_plan_id is None and active_plan:
    active_plan_id = active_plan.get("plan_id")

status_col1, status_col2, status_col3 = st.columns(3)

with status_col1:
    st.metric(
        "Active Plan",
        f"Plan #{active_plan_id}"
        if active_plan_id
        else "None",
    )

with status_col2:
    st.metric(
        "Active Plan: Pending",
        dashboard.get(
            "active_pending_sessions",
            dashboard.get("pending_sessions", 0),
        ),
    )

with status_col3:
    st.metric(
        "Active Plan: Completed",
        dashboard.get(
            "active_completed_sessions",
            dashboard.get("completed_sessions", 0),
        ),
    )

st.markdown("### 📈 Overall Learning Progress")

overall_col1, overall_col2, overall_col3 = st.columns(3)

with overall_col1:
    st.metric(
        "All Completed Sessions",
        dashboard.get(
            "overall_completed_sessions",
            dashboard.get("completed_sessions", 0),
        ),
    )

with overall_col2:
    st.metric(
        "All Pending Sessions",
        dashboard.get(
            "overall_pending_sessions",
            dashboard.get("pending_sessions", 0),
        ),
    )

with overall_col3:
    st.metric(
        "All In-Progress Sessions",
        dashboard.get(
            "overall_in_progress_sessions",
            dashboard.get(
                "active_in_progress_sessions",
                0,
            ),
        ),
    )


# ============================================================
# REFRESH DASHBOARD
# ============================================================

st.divider()

if st.button(
    "🔄 Refresh Dashboard",
    use_container_width=True,
):
    st.session_state.quiz_result = None
    st.rerun()
