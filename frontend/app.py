import os
import streamlit as st
from datetime import datetime
from urllib.parse import urlparse

from frontend.resource_security import resolve_resource_path
from frontend.api_client import request_api

# ============================================================
from pathlib import Path
from dotenv import load_dotenv

# Project root directory
PROJECT_ROOT = Path(__file__).resolve().parents[1]

# Load environment variables from the project root .env
load_dotenv(
    dotenv_path=PROJECT_ROOT / ".env",
    override=False,
)

# Read API URL
API_BASE_URL = os.getenv(
    "API_BASE_URL",
    "http://127.0.0.1:8001",
).strip().rstrip("/")

# Validate API URL
if not API_BASE_URL.startswith(("http://", "https://")):
    raise RuntimeError(
        "API_BASE_URL must start with http:// or https://."
    )
REQUEST_TIMEOUT = 60
TOPIC_NAMES = {}


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

for key, default in {
    "quiz_result": None,
    "access_token": None,
    "student": None,
}.items():
    if key not in st.session_state:
        st.session_state[key] = default


# ============================================================
# API HELPERS
# ============================================================

def api_request(method, endpoint, *, show_errors=True, **kwargs):
    """Send an API request using the isolated API client."""

    token = st.session_state.get("access_token")

    result = request_api(
        method,
        endpoint,
        api_base_url=API_BASE_URL,
        token=token,
        timeout=REQUEST_TIMEOUT,
        **kwargs
    )

    if result.unauthorized:
        clear_authentication()
        st.warning(result.error)
        st.rerun()
        return None

    if result.error:
        if show_errors:
            st.error(result.error)
        return None

    return result.data


def api_get(endpoint, *, show_errors=True):
    return api_request(
        "GET",
        endpoint,
        show_errors=show_errors,
    )


def api_post(endpoint, payload, *, show_errors=True):
    return api_request(
        "POST",
        endpoint,
        json=payload,
        show_errors=show_errors,
    )


def get_student_profile():
    return api_get("/auth/me")


def get_dashboard():
    student_id = st.session_state.student["student_id"]
    return api_get(f"/dashboard/student/{student_id}")


def get_study_plans():
    student_id = st.session_state.student["student_id"]
    return api_get(f"/study-plans/student/{student_id}")


def get_plan_items(plan_id):
    return api_get(f"/study-plan-items/plan/{plan_id}")


def get_topic_resources(topic_id):
    return api_get(f"/resources/topic/{topic_id}")


def get_quiz_questions(quiz_id):
    return api_get(f"/quizzes/{quiz_id}/questions")


def update_session_status(item_id, status):
    return api_request(
        "PUT",
        f"/study-plan-items/{item_id}/status",
        json={"status": status},
    )


# ============================================================
# RESPONSE NORMALIZATION
# ============================================================

def normalize_list_response(data, *possible_keys):
    """Handle list responses and common wrapped-list responses."""

    if isinstance(data, list):
        return data

    if isinstance(data, dict):
        for key in possible_keys:
            value = data.get(key)
            if isinstance(value, list):
                return value

        value = data.get("value")
        if isinstance(value, list):
            return value

    return []


# ============================================================
# EXTERNAL URL VALIDATION
# ============================================================

def is_safe_external_url(value):
    """Allow absolute HTTP(S) URLs without embedded credentials."""

    if not isinstance(value, str) or not value.strip():
        return False

    try:
        parsed = urlparse(value.strip())

        return (
            parsed.scheme.lower() in {"http", "https"}
            and bool(parsed.netloc)
            and parsed.username is None
            and parsed.password is None
        )

    except (TypeError, ValueError):
        return False


# ============================================================
# AUTHENTICATION
# ============================================================

def clear_authentication():
    st.session_state.access_token = None
    st.session_state.student = None
    st.session_state.quiz_result = None


def show_authentication_page():

    st.title("🎓 AI Personalized Learning & Study Planner")

    st.write(
        "Sign in to access your personalized study plan, "
        "learning dashboard, quizzes, and resources."
    )

    login_tab, register_tab = st.tabs(
        ["Login", "Create Account"]
    )

    # --------------------------------------------------------
    # LOGIN
    # --------------------------------------------------------

    with login_tab:

        with st.form("login_form"):

            login_email = st.text_input(
                "Email",
                key="login_email",
            )

            login_password = st.text_input(
                "Password",
                type="password",
                key="login_password",
            )

            login_submitted = st.form_submit_button(
                "Login",
                use_container_width=True,
            )

        if login_submitted:

            if not login_email.strip() or not login_password:

                st.warning("Enter both your email and password.")

            else:

                token_data = api_post(
                    "/auth/login",
                    {
                        "email": login_email.strip(),
                        "password": login_password,
                    },
                )

                if (
                    not token_data
                    or not token_data.get("access_token")
                ):

                    st.error(
                        "Login failed. Check the API error above "
                        "and verify your credentials."
                    )

                else:

                    st.session_state.access_token = (
                        token_data["access_token"]
                    )

                    student = api_get("/auth/me")

                    if (
                        not student
                        or not student.get("student_id")
                    ):

                        clear_authentication()

                        st.error(
                            "Login succeeded, but the student "
                            "profile could not be loaded."
                        )

                    else:

                        st.session_state.student = student
                        st.session_state.quiz_result = None
                        st.rerun()

    # --------------------------------------------------------
    # REGISTRATION
    # --------------------------------------------------------

    with register_tab:

        with st.form("register_form"):

            register_name = st.text_input(
                "Full Name",
                key="register_name",
            )

            register_email = st.text_input(
                "Email Address",
                key="register_email",
            )

            register_password = st.text_input(
                "Password (minimum 8 characters)",
                type="password",
                key="register_password",
            )

            daily_hours = st.number_input(
                "Daily Available Study Hours",
                min_value=0.25,
                max_value=24.0,
                value=2.0,
                step=0.25,
            )

            learning_preference = st.selectbox(
                "Learning Preference",
                ["Practice", "Reading", "Video", "Mixed"],
            )

            register_submitted = st.form_submit_button(
                "Create Account",
                use_container_width=True,
            )

        if register_submitted:

            if (
                not register_name.strip()
                or not register_email.strip()
            ):

                st.warning("Name and email are required.")

            elif len(register_password) < 8:

                st.warning(
                    "Password must contain at least 8 characters."
                )

            else:

                registration = api_post(
                    "/auth/register",
                    {
                        "name": register_name.strip(),
                        "email": register_email.strip(),
                        "password": register_password,
                        "daily_available_hours": daily_hours,
                        "learning_preference": learning_preference,
                    },
                )

                if not registration:

                    st.error(
                        "Registration failed. Check the API error above."
                    )

                else:

                    token_data = api_post(
                        "/auth/login",
                        {
                            "email": register_email.strip(),
                            "password": register_password,
                        },
                    )

                    if (
                        not token_data
                        or not token_data.get("access_token")
                    ):

                        st.success(
                            "Account created successfully. "
                            "Please log in using the Login tab."
                        )

                    else:

                        st.session_state.access_token = (
                            token_data["access_token"]
                        )

                        student = api_get("/auth/me")

                        if (
                            student
                            and student.get("student_id")
                        ):

                            st.session_state.student = student
                            st.session_state.quiz_result = None
                            st.rerun()

                        clear_authentication()

                        st.success(
                            "Account created successfully. "
                            "Please log in using the Login tab."
                        )


# ============================================================
# REQUIRE AUTHENTICATION
# ============================================================

if (
    not st.session_state.get("access_token")
    or not st.session_state.get("student")
):

    show_authentication_page()
    st.stop()


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.write(
        f"Signed in as **"
        f"{st.session_state.student.get('name', 'Student')}**"
    )

    st.caption(
        st.session_state.student.get("email", "")
    )

    if st.button(
        "Log Out",
        use_container_width=True,
    ):

        clear_authentication()
        st.rerun()


STUDENT_ID = int(
    st.session_state.student["student_id"]
)


# ============================================================
# QUIZ SUBMISSION
# ============================================================

def submit_quiz(quiz_id, answers):
    """Submit answers for server-side grading."""

    payload = {
        "student_id": STUDENT_ID,
        "answers": answers,
    }

    return api_post(
        f"/quiz-results/?quiz_id={quiz_id}",
        payload,
    )


# ============================================================
# LOAD AUTHENTICATED STUDENT DATA
# ============================================================

profile = get_student_profile()

if profile is None:

    clear_authentication()

    st.warning(
        "Your session is invalid or has expired. "
        "Please log in again."
    )

    st.stop()


st.session_state.student = profile
STUDENT_ID = int(profile["student_id"])

dashboard = get_dashboard()
study_plans_response = get_study_plans()

if dashboard is None:
    st.stop()

if study_plans_response is None:
    study_plans_response = []


plans = normalize_list_response(
    study_plans_response,
    "plans",
    "study_plans",
)


# ============================================================
# LOAD SUBJECTS AND TOPICS
# ============================================================

subjects_response = api_get("/subjects/")
topics_response = api_get("/topics/")


student_subjects = normalize_list_response(
    subjects_response,
    "subjects",
)


student_topics = normalize_list_response(
    topics_response,
    "topics",
)


subject_names = {
    subject["subject_id"]: subject.get(
        "subject_name",
        "Subject",
    )
    for subject in student_subjects
    if isinstance(subject, dict)
    and subject.get("subject_id") is not None
}


TOPIC_NAMES = {
    topic["topic_id"]: topic.get(
        "topic_name",
        "Topic",
    )
    for topic in student_topics
    if isinstance(topic, dict)
    and topic.get("topic_id") is not None
}


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
    st.metric("Student", profile.get("name", "N/A"))

with profile_col2:
    st.metric("Email", profile.get("email", "N/A"))

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
    "Choose a topic and an available quiz. "
    "The backend grades your answers and runs the adaptive workflow."
)


if subjects_response is None or topics_response is None:

    st.warning(
        "Unable to load subjects or topics. "
        "Check the API errors above."
    )

elif not student_topics:

    st.info(
        "No topics are available for your account. "
        "Create a subject and add topics first."
    )

else:

    topic_labels = {
        topic["topic_id"]: (
            f"{subject_names.get(topic.get('subject_id'), 'Subject')} · "
            f"{topic.get('topic_name', 'Topic')} "
            f"(ID {topic['topic_id']})"
        )
        for topic in student_topics
        if isinstance(topic, dict)
        and isinstance(topic.get("topic_id"), int)
        and not isinstance(topic.get("topic_id"), bool)
        and topic.get("topic_id") > 0
    }

    # --------------------------------------------------------
    # VALIDATE TOPIC OPTIONS
    # --------------------------------------------------------

    if not topic_labels:

        st.warning(
            "No valid topics were returned by the API. "
            "Refresh the dashboard or check the topic records."
        )

    else:

        selected_topic_id = st.selectbox(
            "Select topic",
            options=list(topic_labels.keys()),
            format_func=lambda topic_id: topic_labels[topic_id],
            key="assessment_topic_id",
        )

        # ----------------------------------------------------
        # LOAD AVAILABLE QUIZZES
        # ----------------------------------------------------

        quizzes_response = api_get(
            f"/quizzes/topic/{selected_topic_id}"
        )

        available_quizzes = normalize_list_response(
            quizzes_response,
            "quizzes",
        )

        if quizzes_response is None:

            st.warning("Unable to load quizzes for this topic.")

        elif not available_quizzes:

            st.info(
                f"No quiz exists for "
                f"{TOPIC_NAMES.get(selected_topic_id, 'this topic')} yet. "
                "A quiz with questions must be created before assessment."
            )

        else:

            available_quizzes = [
                quiz
                for quiz in available_quizzes
                if isinstance(quiz, dict)
                and quiz.get("quiz_id") is not None
            ]

            quiz_labels = {}

            for quiz in available_quizzes:

                quiz_id = quiz["quiz_id"]
                quiz_title = quiz.get("title") or f"Quiz {quiz_id}"
                question_count = quiz.get("question_count", 0)

                quiz_labels[quiz_id] = (
                    f"{quiz_title} (ID {quiz_id}, "
                    f"{question_count} questions)"
                )

            if not quiz_labels:

                st.info(
                    "The API did not return any valid quiz IDs."
                )

            else:

                selected_quiz_id = st.selectbox(
                    "Select quiz",
                    options=list(quiz_labels.keys()),
                    format_func=lambda quiz_id: quiz_labels[quiz_id],
                    key=f"assessment_quiz_id_{selected_topic_id}",
                )

                # --------------------------------------------
                # LOAD QUIZ QUESTIONS
                # --------------------------------------------

                questions_response = get_quiz_questions(
                    selected_quiz_id
                )

                quiz_questions = normalize_list_response(
                    questions_response,
                    "questions",
                )

                if questions_response is None:

                    st.warning(
                        "Unable to load questions for this quiz."
                    )

                elif not quiz_questions:

                    st.info(
                        "This quiz has no questions yet. "
                        "Questions must be added before it can be attempted."
                    )

                else:

                    with st.form(
                        key=f"quiz_form_{selected_quiz_id}"
                    ):

                        st.caption(
                            f"Topic: "
                            f"{TOPIC_NAMES.get(selected_topic_id, 'Topic')} | "
                            f"Quiz ID: {selected_quiz_id} | "
                            f"Questions: {len(quiz_questions)}"
                        )

                        submitted_answers = []

                        for index, question in enumerate(
                            quiz_questions,
                            start=1,
                        ):

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

                            if not option_labels:

                                st.warning(
                                    f"Question {index} has no answer options."
                                )

                                continue

                            selected = st.radio(
                                "Choose your answer",
                                options=option_labels,
                                index=None,
                                key=(
                                    f"quiz_{selected_quiz_id}_"
                                    f"question_{question_id}"
                                ),
                            )

                            if selected:

                                submitted_answers.append({
                                    "question_id": question_id,
                                    "selected_option": (
                                        selected.split(".", 1)[0].strip()
                                    ),
                                })

                            st.caption(
                                f"Points: {question.get('points', 1)}"
                            )

                            st.divider()

                        submit_button = st.form_submit_button(
                            "🚀 Submit Quiz",
                            use_container_width=True,
                        )

                    # ----------------------------------------
                    # SUBMIT QUIZ
                    # ----------------------------------------

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
                                    selected_quiz_id,
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

            st.error(
                f"Question {index}: Incorrect"
            )

        st.write(
            f"Your answer: "
            f"{answer.get('selected_option', 'N/A')}"
        )

        st.write(
            f"Correct answer: "
            f"{answer.get('correct_option', 'N/A')}"
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
        st.write(f"**Start Date:** {active_plan['start_date']}")

    if active_plan.get("end_date"):
        st.write(f"**End Date:** {active_plan['end_date']}")

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

        st.info("No study sessions were found for this plan.")

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
        st.info("No topics are available for resource retrieval.")

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

                raw_resource_path = (
                    resource.get("content_path")
                    or resource.get("file_path")
                    or resource.get("path")
                    or ""
                )

                resolved_path = resolve_resource_path(resource)

                if raw_resource_path:

                    if not resolved_path:

                        st.warning(
                            "This resource file is unavailable "
                            "or its path is not permitted."
                        )

                    elif os.path.isfile(resolved_path):

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

                        except OSError:

                            st.error(
                                "Unable to read this study material."
                            )

                    else:

                        st.warning(
                            "The requested study material is currently unavailable."
                        )

                elif resource.get("url"):

                    resource_url = resource.get("url")

                    if is_safe_external_url(resource_url):

                        st.markdown(
                            f"[Open Resource]({resource_url})"
                        )

                    else:

                        st.warning(
                            "This resource link is invalid or not permitted."
                        )

                else:

                    st.info(
                        "No downloadable file or external link is available."
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
        f"Plan #{active_plan_id}" if active_plan_id else "None",
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