import os
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import streamlit as st
from dotenv import load_dotenv

from frontend.api_client import request_api
from frontend.resource_security import resolve_resource_path
from frontend.styles import apply_dark_orange_theme


# ============================================================
# CONFIGURATION
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]

load_dotenv(
    dotenv_path=PROJECT_ROOT / ".env",
    override=False,
)

API_BASE_URL = os.getenv(
    "API_BASE_URL",
    "http://127.0.0.1:8001",
).strip().rstrip("/")

if not API_BASE_URL.startswith(("http://", "https://")):
    raise RuntimeError(
        "API_BASE_URL must start with http:// or https://."
    )

REQUEST_TIMEOUT = 60
TOPIC_NAMES = {}

st.set_page_config(
    page_title="Learnova | AI Learning Planner",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)

apply_dark_orange_theme()


# ============================================================
# SESSION STATE
# ============================================================

DEFAULT_STATE = {
    "quiz_result": None,
    "access_token": None,
    "student": None,
    "active_page": "Dashboard",
    "main_navigation": "Dashboard",
}

for key, value in DEFAULT_STATE.items():
    if key not in st.session_state:
        st.session_state[key] = value


# ============================================================
# LEARNOVA LOGO
# ============================================================

def get_learnova_logo():
    """
    Returns the Learnova open-book SVG emblem without leading
    indentation so Streamlit Markdown does not treat it as a code block.
    """
    return (
        '<svg viewBox="0 0 64 64" xmlns="http://www.w3.org/2000/svg" '
        'width="36" height="36" role="img" aria-label="Learnova open book logo">'
        '<defs>'
        '<linearGradient id="learnovaLeftPage" x1="0" y1="0" x2="1" y2="1">'
        '<stop offset="0%" stop-color="#FFB547"/>'
        '<stop offset="100%" stop-color="#F47721"/>'
        '</linearGradient>'
        '<linearGradient id="learnovaRightPage" x1="0" y1="0" x2="1" y2="1">'
        '<stop offset="0%" stop-color="#F47721"/>'
        '<stop offset="100%" stop-color="#C65A13"/>'
        '</linearGradient>'
        '</defs>'
        '<path d="M8 17 C16 14 24 17 31 23 L31 49 C23 43 15 41 8 44 Z" '
        'fill="url(#learnovaLeftPage)" stroke="#FFB547" stroke-width="1.5" stroke-linejoin="round"/>'
        '<path d="M56 17 C48 14 40 17 33 23 L33 49 C41 43 49 41 56 44 Z" '
        'fill="url(#learnovaRightPage)" stroke="#FF963F" stroke-width="1.5" stroke-linejoin="round"/>'
        '<path d="M27 12 Q32 7 37 12 L35 47 Q32 44 29 47 Z" '
        'fill="#FFB547" stroke="#FFD08A" stroke-width="1.5" stroke-linejoin="round"/>'
        '<path d="M14 25 Q21 24 26 29" fill="none" stroke="#71340F" stroke-width="1.5" stroke-linecap="round"/>'
        '<path d="M14 33 Q21 32 26 37" fill="none" stroke="#71340F" stroke-width="1.5" stroke-linecap="round"/>'
        '<path d="M38 29 Q43 24 50 25" fill="none" stroke="#71340F" stroke-width="1.5" stroke-linecap="round"/>'
        '<path d="M38 37 Q43 32 50 33" fill="none" stroke="#71340F" stroke-width="1.5" stroke-linecap="round"/>'
        '<path d="M8 48 Q20 44 31 53 Q43 44 56 48" fill="none" stroke="#FF963F" stroke-width="2" stroke-linecap="round"/>'
        '</svg>'
    )


# ============================================================
# SMALL UI HELPERS
# ============================================================

def section_heading(title, subtitle=None):
    st.markdown(
        f'<div class="section-heading">{title}</div>',
        unsafe_allow_html=True,
    )

    if subtitle:
        st.markdown(
            f'<div class="section-subtitle">{subtitle}</div>',
            unsafe_allow_html=True,
        )


def page_header(eyebrow, title, description=None):
    st.markdown(
        f'<div class="page-header">'
        f'<div class="eyebrow">{eyebrow}</div>'
        f'<div class="page-title">{title}</div>'
        f'<div class="page-description">{description or ""}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )


def metric_card(label, value, caption="", icon="✦"):
    st.markdown(
        f'<div class="metric-card">'
        f'<div class="metric-top">'
        f'<span class="metric-icon">{icon}</span>'
        f'<span class="metric-label">{label}</span>'
        f'</div>'
        f'<div class="metric-value">{value}</div>'
        f'<div class="metric-caption">{caption}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )


def info_card(title, description, tag=None):
    tag_html = f'<span class="mini-tag">{tag}</span>' if tag else ""

    st.markdown(
        f'<div class="content-card">'
        f'<div class="content-card-title">{title}</div>'
        f'<div class="content-card-description">{description}</div>'
        f'{tag_html}'
        f'</div>',
        unsafe_allow_html=True,
    )


def safe_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def safe_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def format_date(value):
    if not value:
        return "Not scheduled"

    try:
        parsed = datetime.fromisoformat(
            str(value).replace("Z", "+00:00")
        )
        return parsed.strftime("%d %b %Y")
    except (ValueError, TypeError):
        return str(value)


def normalize_list_response(data, *possible_keys):
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


def is_safe_external_url(value):
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
# API HELPERS
# ============================================================
def clear_authentication():
    st.session_state.access_token = None
    st.session_state.student = None
    st.session_state.quiz_result = None
    st.session_state.active_page = "Dashboard"



def api_request(method, endpoint, *, show_errors=True, **kwargs):
    token = st.session_state.get("access_token")

    result = request_api(
        method,
        endpoint,
        api_base_url=API_BASE_URL,
        token=token,
        timeout=REQUEST_TIMEOUT,
        **kwargs,
    )

    if result.unauthorized:
        clear_authentication()
        st.warning(result.error or "Your session has expired.")
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
# AUTHENTICATION PAGE
# ============================================================

def show_authentication_page():

    st.markdown(
        f'<div class="auth-brand">'
        f'<div class="auth-logo">{get_learnova_logo()}</div>'
        f'<div>'
        f'<div class="auth-brand-name">Learnova</div>'
        f'<div class="auth-brand-caption">YOUR PERSONAL AI LEARNING SPACE</div>'
        f'</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    left, center, right = st.columns([1, 1.35, 1])

    with center:

        st.markdown(
            '<div class="auth-intro">'
            '<div class="eyebrow">LEARN WITH A PLAN</div>'
            '<div class="auth-title">'
            'Your goals.<br>'
            'Your pace.<br>'
            '<span>Your progress.</span>'
            '</div>'
            '<div class="auth-description">'
            'Sign in to access your personalized study '
            'plan, adaptive assessments and learning resources.'
            '</div>'
            '</div>',
            unsafe_allow_html=True,
        )

        login_tab, register_tab = st.tabs(
            ["Sign in", "Create account"]
        )

        # ----------------------------------------------------
        # LOGIN
        # ----------------------------------------------------

        with login_tab:

            with st.form("login_form"):

                email = st.text_input(
                    "Email",
                    placeholder="you@example.com",
                    key="login_email",
                )

                password = st.text_input(
                    "Password",
                    type="password",
                    placeholder="Enter your password",
                    key="login_password",
                )

                submitted = st.form_submit_button(
                    "Sign in",
                    use_container_width=True,
                )

            if submitted:

                if not email.strip() or not password:
                    st.warning(
                        "Enter both your email and password."
                    )

                else:

                    token_data = api_post(
                        "/auth/login",
                        {
                            "email": email.strip(),
                            "password": password,
                        },
                    )

                    if (
                        not token_data
                        or not token_data.get("access_token")
                    ):

                        st.error(
                            "Login failed. Check the API error "
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

        # ----------------------------------------------------
        # REGISTRATION
        # ----------------------------------------------------

        with register_tab:

            with st.form("register_form"):

                name = st.text_input(
                    "Full name",
                    placeholder="Your name",
                    key="register_name",
                )

                register_email = st.text_input(
                    "Email address",
                    placeholder="you@example.com",
                    key="register_email",
                )

                register_password = st.text_input(
                    "Password",
                    type="password",
                    placeholder="Minimum 8 characters",
                    key="register_password",
                )

                daily_hours = st.number_input(
                    "Daily available study hours",
                    min_value=0.25,
                    max_value=24.0,
                    value=2.0,
                    step=0.25,
                )

                preference = st.selectbox(
                    "Learning preference",
                    ["Practice", "Reading", "Video", "Mixed"],
                )

                register_submitted = st.form_submit_button(
                    "Create account",
                    use_container_width=True,
                )

            if register_submitted:

                if not name.strip() or not register_email.strip():

                    st.warning("Name and email are required.")

                elif len(register_password) < 8:

                    st.warning(
                        "Password must contain at least 8 characters."
                    )

                else:

                    registration = api_post(
                        "/auth/register",
                        {
                            "name": name.strip(),
                            "email": register_email.strip(),
                            "password": register_password,
                            "daily_available_hours": daily_hours,
                            "learning_preference": preference,
                        },
                    )

                    if not registration:

                        st.error(
                            "Registration failed. Check the API error."
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
                            token_data
                            and token_data.get("access_token")
                        ):

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
                            "Account created. Please sign in "
                            "using the Sign in tab."
                        )


# ============================================================
# AUTHENTICATION GATE
# ============================================================

if (
    not st.session_state.get("access_token")
    or not st.session_state.get("student")
):

    show_authentication_page()
    st.stop()


# ============================================================
# LOAD AUTHENTICATED DATA
# ============================================================

profile = get_student_profile()

if profile is None:

    clear_authentication()

    st.warning(
        "Your session is invalid or has expired. Please sign in again."
    )

    st.stop()


st.session_state.student = profile

STUDENT_ID = safe_int(profile.get("student_id"))

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
    subject["subject_id"]: subject.get("subject_name", "Subject")
    for subject in student_subjects
    if isinstance(subject, dict)
    and subject.get("subject_id") is not None
}


TOPIC_NAMES = {
    topic["topic_id"]: topic.get("topic_name", "Topic")
    for topic in student_topics
    if isinstance(topic, dict)
    and topic.get("topic_id") is not None
}


active_plan = next(
    (
        plan for plan in plans
        if isinstance(plan, dict)
        and str(plan.get("status", "")).lower() == "active"
    ),
    None,
)


plan_items = []

if active_plan:

    active_plan_id = active_plan.get("plan_id")

    plan_items_response = get_plan_items(active_plan_id)

    plan_items = normalize_list_response(
        plan_items_response,
        "items",
        "study_plan_items",
    )


# ============================================================
# SIDEBAR NAVIGATION
# ============================================================

def navigate_to_study_plan():
    st.session_state["active_page"] = "My Study Plan"
    st.session_state["main_navigation"] = "My Study Plan"


student_name = profile.get("name", "Student")

first_name = (
    student_name.split()[0]
    if student_name
    else "Student"
)


PAGES = [
    "Dashboard",
    "My Study Plan",
    "Subjects & Topics",
    "Practice & Quizzes",
    "My Progress",
    "Learning Resources",
    "My Profile",
]

PAGE_LABELS = {
    "Dashboard": "🏠   Dashboard",
    "My Study Plan": "🗓️   My Study Plan",
    "Subjects & Topics": "📚   Subjects & Topics",
    "Practice & Quizzes": "🎯   Practice & Quizzes",
    "My Progress": "📈   My Progress",
    "Learning Resources": "💡   Learning Resources",
    "My Profile": "👤   My Profile",
}


with st.sidebar:

    st.markdown(
        f'<div class="sidebar-brand">'
        f'<div class="sidebar-logo">{get_learnova_logo()}</div>'
        f'<div>'
        f'<div class="sidebar-brand-name">Learnova</div>'
        f'<div class="sidebar-brand-subtitle">AI STUDY COMPANION</div>'
        f'</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    st.markdown(
        '<div class="sidebar-divider"></div>',
        unsafe_allow_html=True,
    )

    st.markdown(
        '<div class="sidebar-section-label">WORKSPACE</div>',
        unsafe_allow_html=True,
    )

    current_page = st.session_state.get(
        "active_page",
        "Dashboard",
    )

    if current_page not in PAGES:
        current_page = "Dashboard"

    selected_page = st.radio(
        "Navigation",
        PAGES,
        index=PAGES.index(current_page),
        format_func=lambda page: PAGE_LABELS.get(page, page),
        label_visibility="collapsed",
        key="main_navigation",
    )

    st.session_state.active_page = selected_page

    st.markdown(
        '<div class="sidebar-bottom">',
        unsafe_allow_html=True,
    )

    st.markdown(
        f'<div class="sidebar-user">'
        f'<div class="sidebar-avatar">{first_name[:1].upper()}</div>'
        f'<div class="sidebar-user-info">'
        f'<div class="sidebar-user-name">{student_name}</div>'
        f'<div class="sidebar-user-email">{profile.get("email", "")}</div>'
        f'</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    if st.button(
        "↪  Log out",
        use_container_width=True,
        key="sidebar_logout",
    ):

        clear_authentication()
        st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)


# ============================================================
# QUIZ SUBMISSION
# ============================================================

def submit_quiz(quiz_id, answers):

    payload = {
        "student_id": STUDENT_ID,
        "answers": answers,
    }

    return api_post(
        f"/quiz-results/?quiz_id={quiz_id}",
        payload,
    )


# ============================================================
# DASHBOARD PAGE
# ============================================================

def render_dashboard():

    page_header(
        "YOUR LEARNING OVERVIEW",
        f"Welcome back, {first_name} 👋",
        "A clearer view of your learning journey starts here.",
    )

    average_score = safe_float(
        dashboard.get("average_score", 0)
    )

    weak_topics = safe_int(
        dashboard.get("weak_topics", 0)
    )

    moderate_topics = safe_int(
        dashboard.get("moderate_topics", 0)
    )

    strong_topics = safe_int(
        dashboard.get("strong_topics", 0)
    )


    metric_cols = st.columns(4)

    with metric_cols[0]:

        metric_card(
            "Average score",
            f"{average_score:g}%",
            "Across recorded assessments",
            "◉",
        )

    with metric_cols[1]:

        metric_card(
            "Weak topics",
            weak_topics,
            "Topics needing more attention",
            "↗",
        )

    with metric_cols[2]:

        metric_card(
            "Moderate topics",
            moderate_topics,
            "Topics to keep practicing",
            "◎",
        )

    with metric_cols[3]:

        metric_card(
            "Strong topics",
            strong_topics,
            "Topics you've built confidence in",
            "✦",
        )


    st.write("")

    left, right = st.columns([1.35, 1])


    with left:

        section_heading(
            "Learning distribution",
            "Your current topic-level performance overview.",
        )

        performance_data = {
            "Weak": weak_topics,
            "Moderate": moderate_topics,
            "Strong": strong_topics,
        }

        if sum(performance_data.values()) > 0:

            st.bar_chart(
                performance_data,
                color="#F47721",
                height=245,
            )

        else:

            st.info(
                "Performance distribution will appear after "
                "your assessments have been recorded."
            )


    with right:

        section_heading(
            "Your learning space",
            "A quick snapshot of your learning setup.",
        )

        c1, c2 = st.columns(2)

        with c1:

            st.metric(
                "Subjects",
                dashboard.get("total_subjects", 0),
            )

        with c2:

            st.metric(
                "Topics",
                dashboard.get("total_topics", 0),
            )


        c3, c4 = st.columns(2)

        with c3:

            st.metric(
                "Active plans",
                dashboard.get("active_study_plans", 0),
            )

        with c4:

            st.metric(
                "Daily study hours",
                profile.get("daily_available_hours", 0),
            )


        st.markdown(
            '<div class="tip-card">'
            '<div class="tip-label">LEARNING TIP</div>'
            '<div class="tip-title">Small, consistent sessions add up.</div>'
            '<div class="tip-description">'
            'Complete your scheduled sessions and use '
            'assessments to identify what needs more practice.'
            '</div>'
            '</div>',
            unsafe_allow_html=True,
        )


    st.write("")

    section_heading(
        "Your active study plan",
        "A snapshot of the sessions currently in your plan.",
    )


    if not active_plan:

        st.info(
            "You don't have an active study plan yet. "
            "Complete an assessment to trigger the adaptive workflow."
        )

    elif not plan_items:

        st.info(
            "Your active plan does not have any sessions yet."
        )

    else:

        completed = sum(
            1 for item in plan_items
            if str(item.get("status", "")).lower() == "completed"
        )

        total = len(plan_items)

        progress = completed / total if total else 0


        st.markdown(
            f'<div class="plan-overview">'
            f'<div>'
            f'<div class="plan-overview-title">Plan #{active_plan.get("plan_id")}</div>'
            f'<div class="plan-overview-subtitle">{completed} of {total} sessions completed</div>'
            f'</div>'
            f'<div class="plan-overview-percent">{progress * 100:.0f}%</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

        st.progress(progress)


        pending_items = [
            item for item in plan_items
            if str(item.get("status", "")).lower() != "completed"
        ]


        for item in pending_items[:4]:

            topic_id = item.get("topic_id")

            topic_name = TOPIC_NAMES.get(
                topic_id,
                f"Topic {topic_id}",
            )

            status = str(
                item.get("status", "pending")
            ).replace("_", " ").title()


            with st.container(border=True):

                col1, col2, col3 = st.columns([2.2, 1, 1])

                with col1:

                    st.markdown(f"**{topic_name}**")

                    st.caption(
                        format_date(item.get("scheduled_date"))
                    )

                with col2:

                    st.caption("DURATION")

                    st.write(
                        f"{item.get('duration_minutes', 0)} min"
                    )

                with col3:

                    st.caption("STATUS")
                    st.write(status)


        st.button(
            "Open my study plan →",
            key="dashboard_open_plan",
            on_click=navigate_to_study_plan,
        )


    st.write("")

    section_heading(
        "How your plan adapts",
        "Your assessment performance informs the learning workflow.",
    )


    adaptation_cols = st.columns(3)

    with adaptation_cols[0]:

        info_card(
            "Weak performance",
            "Increase study priority and reinforce prerequisite topics.",
            "NEEDS ATTENTION",
        )

    with adaptation_cols[1]:

        info_card(
            "Moderate performance",
            "Continue practice and strengthen understanding.",
            "KEEP PRACTICING",
        )

    with adaptation_cols[2]:

        info_card(
            "Strong performance",
            "Reduce topic priority or remove it from a future plan "
            "when appropriate.",
            "GOOD PROGRESS",
        )


# ============================================================
# STUDY PLAN PAGE
# ============================================================

def render_study_plan():

    page_header(
        "PLAN YOUR LEARNING",
        "My Study Plan",
        "Review your sessions, manage their status and stay on track.",
    )


    if not active_plan:

        st.info(
            "No active study plan is available. Submit an assessment "
            "to trigger the adaptive workflow."
        )

        return


    st.markdown(
        f'<div class="plan-banner">'
        f'<div>'
        f'<div class="eyebrow">CURRENT ACTIVE PLAN</div>'
        f'<div class="plan-banner-title">Study Plan #{active_plan.get("plan_id")}</div>'
        f'<div class="plan-banner-meta">'
        f'{format_date(active_plan.get("start_date"))} &nbsp; · &nbsp; {format_date(active_plan.get("end_date"))}'
        f'</div>'
        f'</div>'
        f'<div class="plan-status-pill">ACTIVE</div>'
        f'</div>',
        unsafe_allow_html=True,
    )


    if not plan_items:

        st.info(
            "No study sessions were found for this plan."
        )

        return


    completed = sum(
        1 for item in plan_items
        if str(item.get("status", "")).lower() == "completed"
    )

    total = len(plan_items)

    in_progress = sum(
        1 for item in plan_items
        if str(item.get("status", "")).lower() == "in_progress"
    )

    pending = total - completed - in_progress


    cols = st.columns(3)

    with cols[0]:

        metric_card(
            "Completed",
            completed,
            "Finished sessions",
            "✓",
        )

    with cols[1]:

        metric_card(
            "In progress",
            in_progress,
            "Currently underway",
            "◷",
        )

    with cols[2]:

        metric_card(
            "Pending",
            pending,
            "Still to be completed",
            "○",
        )


    st.write("")

    section_heading(
        "Session progress",
        "Update a session when its status changes.",
    )

    st.progress(
        completed / total if total else 0
    )


    status_options = [
        "pending",
        "in_progress",
        "completed",
    ]


    for index, item in enumerate(plan_items, start=1):

        item_id = item.get("item_id")
        topic_id = item.get("topic_id")

        topic_name = TOPIC_NAMES.get(
            topic_id,
            f"Topic {topic_id}",
        )

        duration = item.get("duration_minutes", 0)

        priority = safe_int(
            item.get("priority", 3),
            3,
        )


        if priority >= 5:
            priority_label = "High"

        elif priority >= 3:
            priority_label = "Medium"

        else:
            priority_label = "Low"


        current_status = str(
            item.get("status", "pending")
        ).lower()

        if current_status not in status_options:
            current_status = "pending"


        with st.container(border=True):

            title_col, status_col = st.columns([2, 1])

            with title_col:

                st.markdown(
                    f"**{index:02d}  {topic_name}**"
                )

                st.caption(
                    f"{format_date(item.get('scheduled_date'))} "
                    f"· {duration} minutes · "
                    f"{priority_label} priority"
                )

            with status_col:

                st.markdown(
                    f'<div class="session-status">'
                    f'{current_status.replace("_", " ").title()}'
                    f'</div>',
                    unsafe_allow_html=True,
                )


            edit_col, button_col = st.columns([2, 1])

            with edit_col:

                new_status = st.selectbox(
                    "Session status",
                    options=status_options,
                    index=status_options.index(current_status),
                    format_func=lambda value: value.replace(
                        "_", " "
                    ).title(),
                    key=f"status_{item_id}",
                )

            with button_col:

                st.write("")

                if st.button(
                    "Save status",
                    key=f"update_{item_id}",
                    use_container_width=True,
                ):

                    updated = update_session_status(
                        item_id,
                        new_status,
                    )

                    if updated is not None:

                        st.success(
                            f"{topic_name} updated successfully."
                        )

                        st.rerun()


# ============================================================
# SUBJECTS AND TOPICS PAGE
# ============================================================

def render_subjects_topics():

    page_header(
        "YOUR LEARNING CONTENT",
        "Subjects & Topics",
        "Explore the subjects and topics available in your learning space.",
    )


    if subjects_response is None or topics_response is None:

        st.warning(
            "Unable to load subjects or topics. Check the API errors."
        )

        return


    if not student_subjects:

        st.info("No subjects are available yet.")
        return


    section_heading(
        "Your subjects",
        f"{len(student_subjects)} subjects available.",
    )


    for subject in student_subjects:

        if not isinstance(subject, dict):
            continue

        subject_id = subject.get("subject_id")

        subject_name = subject.get(
            "subject_name",
            "Subject",
        )

        related_topics = [
            topic for topic in student_topics
            if isinstance(topic, dict)
            and topic.get("subject_id") == subject_id
        ]


        with st.container(border=True):

            st.markdown(f"### {subject_name}")

            st.caption(
                f"{len(related_topics)} topics"
            )


            if not related_topics:

                st.info(
                    "No topics have been added to this subject."
                )

                continue


            topic_cols = st.columns(2)

            for index, topic in enumerate(related_topics):

                with topic_cols[index % 2]:

                    st.markdown(
                        f'<div class="topic-card">'
                        f'<div class="topic-card-title">{topic.get("topic_name", "Topic")}</div>'
                        f'<div class="topic-card-meta">Topic ID: {topic.get("topic_id")}</div>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )

                    difficulty = topic.get("difficulty")

                    if difficulty is not None:
                        st.caption(f"Difficulty: {difficulty}")


    st.write("")

    section_heading(
        "Topic performance categories",
        "These counts come from your learning dashboard.",
    )


    cols = st.columns(3)

    with cols[0]:

        metric_card(
            "Weak topics",
            dashboard.get("weak_topics", 0),
            "Need additional practice",
            "↗",
        )

    with cols[1]:

        metric_card(
            "Moderate topics",
            dashboard.get("moderate_topics", 0),
            "Need continued revision",
            "◎",
        )

    with cols[2]:

        metric_card(
            "Strong topics",
            dashboard.get("strong_topics", 0),
            "Currently performing well",
            "✦",
        )


# ============================================================
# QUIZ RESULT VIEW
# ============================================================

def render_quiz_result():

    result = st.session_state.get("quiz_result")

    if not result:
        return


    st.write("")

    section_heading(
        "Latest assessment result",
        "Your answers and the adaptive workflow response.",
    )


    evaluation = result.get("evaluation") or {}

    cols = st.columns(3)


    with cols[0]:

        st.metric(
            "Score",
            f"{result.get('score', 0)}%",
        )

    with cols[1]:

        st.metric(
            "Performance level",
            str(
                evaluation.get("level", "Not available")
            ).title(),
        )

    with cols[2]:

        action = evaluation.get(
            "recommended_action",
            "Not available",
        )

        st.metric(
            "Recommended action",
            str(action).replace("_", " ").title(),
        )


    st.write(
        f"**Correct answers:** "
        f"{result.get('correct_answers', 0)} / "
        f"{result.get('total_questions', 0)}"
    )


    with st.expander(
        "Review your answers",
        expanded=True,
    ):

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


    with st.expander("Adaptive workflow details"):

        workflow_status = result.get(
            "workflow_status",
            "unknown",
        )

        st.write(
            f"**Workflow status:** {workflow_status}"
        )

        if result.get("user_feedback"):
            st.info(result["user_feedback"])

        if result.get("validation"):

            st.write("**Plan validation:**")
            st.json(result["validation"])

        for error in result.get("errors", []):
            st.warning(str(error))

        if result.get("workflow_error"):
            st.error(result["workflow_error"])


# ============================================================
# PRACTICE AND QUIZZES PAGE
# ============================================================

def render_quizzes():

    page_header(
        "CHECK YOUR UNDERSTANDING",
        "Practice & Quizzes",
        "Choose a topic, attempt its quiz and let the adaptive workflow "
        "use your result to guide your next study sessions.",
    )


    if subjects_response is None or topics_response is None:

        st.warning(
            "Unable to load subjects or topics. Check the API errors."
        )

        return


    valid_topics = [
        topic for topic in student_topics
        if isinstance(topic, dict)
        and isinstance(topic.get("topic_id"), int)
        and not isinstance(topic.get("topic_id"), bool)
        and topic.get("topic_id") > 0
    ]


    if not valid_topics:

        st.info(
            "No valid topics are available. Add subjects and topics first."
        )

        return


    topic_labels = {
        topic["topic_id"]: (
            f"{subject_names.get(topic.get('subject_id'), 'Subject')} "
            f"· {topic.get('topic_name', 'Topic')}"
        )
        for topic in valid_topics
    }


    selected_topic_id = st.selectbox(
        "Choose a topic",
        options=list(topic_labels.keys()),
        format_func=lambda topic_id: topic_labels[topic_id],
        key="assessment_topic_id",
    )


    quizzes_response = api_get(
        f"/quizzes/topic/{selected_topic_id}"
    )

    available_quizzes = normalize_list_response(
        quizzes_response,
        "quizzes",
    )


    if quizzes_response is None:

        st.warning(
            "Unable to load quizzes for this topic."
        )

        return


    available_quizzes = [
        quiz for quiz in available_quizzes
        if isinstance(quiz, dict)
        and quiz.get("quiz_id") is not None
    ]


    if not available_quizzes:

        st.info(
            f"No quiz exists for "
            f"{TOPIC_NAMES.get(selected_topic_id, 'this topic')} yet."
        )

        return


    quiz_labels = {}

    for quiz in available_quizzes:

        quiz_id = quiz["quiz_id"]

        title = quiz.get("title") or f"Quiz {quiz_id}"

        count = quiz.get("question_count", 0)

        quiz_labels[quiz_id] = (
            f"{title} · {count} questions"
        )


    selected_quiz_id = st.selectbox(
        "Choose a quiz",
        options=list(quiz_labels.keys()),
        format_func=lambda quiz_id: quiz_labels[quiz_id],
        key=f"assessment_quiz_id_{selected_topic_id}",
    )


    questions_response = get_quiz_questions(
        selected_quiz_id
    )

    quiz_questions = normalize_list_response(
        questions_response,
        "questions",
    )


    if questions_response is None:

        st.warning(
            "Unable to load quiz questions."
        )

        return


    if not quiz_questions:

        st.info(
            "This quiz does not contain any questions yet."
        )

        return


    st.write("")

    section_heading(
        "Assessment",
        f"{len(quiz_questions)} questions · "
        f"{TOPIC_NAMES.get(selected_topic_id, 'Selected topic')}",
    )


    with st.form(
        key=f"quiz_form_{selected_quiz_id}"
    ):

        submitted_answers = []

        for index, question in enumerate(
            quiz_questions,
            start=1,
        ):

            question_id = question.get("question_id")

            st.markdown(
                f"**Q{index}. {question.get('question_text', '')}**"
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

                submitted_answers.append(
                    {
                        "question_id": question_id,
                        "selected_option": (
                            selected.split(".", 1)[0].strip()
                        ),
                    }
                )


            st.caption(
                f"Points: {question.get('points', 1)}"
            )

            st.divider()


        submit_button = st.form_submit_button(
            "Submit assessment",
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
                    selected_quiz_id,
                    submitted_answers,
                )


            if result is not None:

                st.session_state.quiz_result = result

                st.success(
                    "Assessment submitted and evaluated successfully."
                )

                st.rerun()


    render_quiz_result()


# ============================================================
# PROGRESS PAGE
# ============================================================

def render_progress():

    page_header(
        "YOUR PERFORMANCE",
        "My Progress",
        "Track your topic performance and study-session completion.",
    )


    average_score = safe_float(
        dashboard.get("average_score", 0)
    )


    cols = st.columns(4)

    with cols[0]:

        metric_card(
            "Average score",
            f"{average_score:g}%",
            "Assessment performance",
            "◉",
        )

    with cols[1]:

        metric_card(
            "Strong topics",
            dashboard.get("strong_topics", 0),
            "Good performance",
            "✦",
        )

    with cols[2]:

        metric_card(
            "Moderate topics",
            dashboard.get("moderate_topics", 0),
            "Keep practicing",
            "◎",
        )

    with cols[3]:

        metric_card(
            "Weak topics",
            dashboard.get("weak_topics", 0),
            "Need more attention",
            "↗",
        )


    st.write("")

    left, right = st.columns([1.2, 1])


    with left:

        section_heading(
            "Topic performance",
            "Current distribution of your topic-level performance.",
        )


        performance_data = {
            "Weak": safe_int(dashboard.get("weak_topics", 0)),
            "Moderate": safe_int(dashboard.get("moderate_topics", 0)),
            "Strong": safe_int(dashboard.get("strong_topics", 0)),
        }


        if sum(performance_data.values()) > 0:

            st.bar_chart(
                performance_data,
                color="#F47721",
                height=280,
            )

        else:

            st.info(
                "Topic performance data will appear after "
                "the system records assessment results."
            )


    with right:

        section_heading(
            "Session completion",
            "Your study-plan activity.",
        )


        completed = safe_int(
            dashboard.get(
                "overall_completed_sessions",
                dashboard.get("completed_sessions", 0),
            )
        )

        pending = safe_int(
            dashboard.get(
                "overall_pending_sessions",
                dashboard.get("pending_sessions", 0),
            )
        )

        in_progress = safe_int(
            dashboard.get(
                "overall_in_progress_sessions",
                dashboard.get("active_in_progress_sessions", 0),
            )
        )


        total_sessions = completed + pending + in_progress


        st.metric(
            "Completed sessions",
            completed,
        )

        st.metric(
            "In-progress sessions",
            in_progress,
        )

        st.metric(
            "Pending sessions",
            pending,
        )


        if total_sessions:

            st.progress(
                completed / total_sessions
            )

            st.caption(
                f"{completed} of {total_sessions} sessions completed"
            )

        else:

            st.info(
                "No study-session activity is recorded yet."
            )


    st.write("")

    section_heading(
        "All-time study activity",
        "Counts returned by your student dashboard API.",
    )


    activity_cols = st.columns(3)

    with activity_cols[0]:
        st.metric("Completed", completed)

    with activity_cols[1]:
        st.metric("Pending", pending)

    with activity_cols[2]:
        st.metric("In progress", in_progress)


    if st.session_state.get("quiz_result"):

        st.write("")

        section_heading(
            "Latest assessment",
            "Your most recently submitted assessment.",
        )

        render_quiz_result()


# ============================================================
# LEARNING RESOURCES PAGE
# ============================================================

def render_resources():

    page_header(
        "STUDY MATERIAL",
        "Learning Resources",
        "Access learning materials associated with topics in your active plan.",
    )


    if not active_plan:

        st.info(
            "Resources will appear here when an active study plan "
            "is available."
        )

        return


    resource_topic_ids = sorted(
        {
            item.get("topic_id")
            for item in plan_items
            if isinstance(item, dict)
            and item.get("topic_id") is not None
        }
    )


    if not resource_topic_ids:

        st.info(
            "There are no topics in the active plan for resource retrieval."
        )

        return


    for topic_id in resource_topic_ids:

        topic_name = TOPIC_NAMES.get(
            topic_id,
            f"Topic {topic_id}",
        )

        st.write("")

        section_heading(topic_name)


        resources_response = get_topic_resources(topic_id)

        resources = normalize_list_response(
            resources_response,
            "resources",
        )


        if resources_response is None:

            st.warning(
                f"Unable to load resources for {topic_name}."
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

            if not isinstance(resource, dict):
                continue


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


        for index, resource in enumerate(unique_resources):

            resource_title = resource.get(
                "title",
                resource.get("resource_name", "Learning Resource"),
            )


            with st.container(border=True):

                st.markdown(
                    f"**{resource_title}**"
                )


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

                            with open(
                                resolved_path,
                                "rb",
                            ) as file:

                                pdf_data = file.read()


                            st.download_button(
                                label="Download study material",
                                data=pdf_data,
                                file_name=os.path.basename(
                                    resolved_path
                                ),
                                mime="application/pdf",
                                key=(
                                    f"download_resource_{topic_id}_"
                                    f"{resource.get('resource_id', index)}"
                                ),
                            )

                        except OSError:

                            st.error(
                                "Unable to read this study material."
                            )

                    else:

                        st.warning(
                            "The requested study material is unavailable."
                        )


                elif resource.get("url"):

                    resource_url = resource.get("url")

                    if is_safe_external_url(resource_url):

                        st.link_button(
                            "Open resource",
                            resource_url,
                        )

                    else:

                        st.warning(
                            "This resource link is invalid or not permitted."
                        )

                else:

                    st.info(
                        "No downloadable file or external link is available."
                    )


# ============================================================
# PROFILE PAGE
# ============================================================

def render_profile():

    page_header(
        "YOUR ACCOUNT",
        "My Profile",
        "Your student details and learning preferences.",
    )


    st.markdown(
        f'<div class="profile-banner">'
        f'<div class="profile-avatar">{first_name[:1].upper()}</div>'
        f'<div>'
        f'<div class="profile-name">{profile.get("name", "Student")}</div>'
        f'<div class="profile-email">{profile.get("email", "")}</div>'
        f'<div class="profile-tag">STUDENT ACCOUNT</div>'
        f'</div>'
        f'</div>',
        unsafe_allow_html=True,
    )


    st.write("")

    section_heading("Learning preferences")


    col1, col2 = st.columns(2)


    with col1:

        st.markdown(
            "**Daily available study time**"
        )

        st.markdown(
            f'<div class="profile-value">'
            f'{profile.get("daily_available_hours", "N/A")} hours'
            f'</div>',
            unsafe_allow_html=True,
        )


    with col2:

        st.markdown(
            "**Learning preference**"
        )

        st.markdown(
            f'<div class="profile-value">'
            f'{profile.get("learning_preference", "N/A")}'
            f'</div>',
            unsafe_allow_html=True,
        )


    st.write("")

    section_heading("Account information")


    with st.container(border=True):

        st.write("**Student ID**")

        st.code(
            str(profile.get("student_id", "N/A"))
        )

        st.write("**Name**")

        st.write(
            profile.get("name", "N/A")
        )

        st.write("**Email**")

        st.write(
            profile.get("email", "N/A")
        )


    st.write("")

    if st.button(
        "Log out of your account",
        key="profile_logout",
    ):

        clear_authentication()
        st.rerun()


# ============================================================
# PAGE ROUTER
# ============================================================

PAGE_RENDERERS = {
    "Dashboard": render_dashboard,
    "My Study Plan": render_study_plan,
    "Subjects & Topics": render_subjects_topics,
    "Practice & Quizzes": render_quizzes,
    "My Progress": render_progress,
    "Learning Resources": render_resources,
    "My Profile": render_profile,
}


selected_page = st.session_state.get(
    "active_page",
    "Dashboard",
)


renderer = PAGE_RENDERERS.get(
    selected_page,
    render_dashboard,
)

renderer()


# ============================================================
# FOOTER / REFRESH
# ============================================================

st.write("")

st.markdown(
    '<div class="app-footer">'
    '<span>Learnova</span>'
    '<span>Personalized learning, one session at a time.</span>'
    '</div>',
    unsafe_allow_html=True,
)


if st.button(
    "↻ Refresh dashboard data",
    key="refresh_dashboard",
):

    st.session_state.quiz_result = None
    st.rerun()