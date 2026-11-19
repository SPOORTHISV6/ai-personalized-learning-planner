import streamlit as st


def apply_dark_orange_theme():
    st.markdown(
        """<style>
:root {
    --bg: #0B0B0D;
    --sidebar: #101012;
    --surface: #171719;
    --surface-2: #202023;
    --surface-3: #29292D;
    --orange: #F47721;
    --orange-hover: #FF8B35;
    --amber: #FFB547;
    --white: #F5F5F5;
    --muted: #A7A7AE;
    --border: #303034;
    --green: #36B37E;
    --red: #EF6461;
}

/* GLOBAL */
html, body, [data-testid="stAppViewContainer"] {
    background: var(--bg) !important;
    color: var(--white) !important;
}

[data-testid="stAppViewContainer"] {
    background:
        radial-gradient(
            ellipse at 85% 0%,
            rgba(244,119,33,.07),
            transparent 34%
        ),
        var(--bg) !important;
}

[data-testid="stHeader"] {
    background: rgba(11,11,13,.94) !important;
    border-bottom: 1px solid var(--border);
}

.block-container {
    max-width: 1480px;
    padding-top: 4rem !important;
    padding-bottom: 3rem !important;
}

#MainMenu, footer {
    visibility: hidden;
}

h1, h2, h3, h4, h5, h6,
p, label, li, span,
[data-testid="stMarkdownContainer"] {
    color: var(--white);
}

[data-testid="stCaptionContainer"],
.stCaption {
    color: var(--muted) !important;
}

hr {
    border-color: var(--border) !important;
}

/* SIDEBAR */
[data-testid="stSidebar"] {
    background: var(--sidebar) !important;
    border-right: 1px solid var(--border);
}

[data-testid="stSidebar"] > div:first-child {
    background: var(--sidebar) !important;
}

[data-testid="stSidebar"] * {
    color: var(--white);
}

.sidebar-brand {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 12px 5px 22px 5px;
}

.sidebar-logo, .auth-logo {
    width: 43px;
    height: 43px;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 13px;
    color: white !important;
    font-size: 23px;
    font-weight: 800;
    background: linear-gradient(145deg, #FF963F, #C65A13);
    box-shadow: 0 5px 18px rgba(244,119,33,.2);
}

.sidebar-brand-name {
    color: #FFFFFF !important;
    font-size: 19px;
    font-weight: 750;
    letter-spacing: -.4px;
}

.sidebar-brand-subtitle {
    color: #929298 !important;
    font-size: 9px;
    letter-spacing: 1.6px;
    margin-top: 2px;
}

.sidebar-divider {
    border-top: 1px solid var(--border);
    margin: 3px 0 22px 0;
}

.sidebar-section-label {
    color: #77777F !important;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 1.5px;
    padding: 0 8px 10px 8px;
}

[data-testid="stSidebar"] [data-testid="stRadio"] > div {
    gap: 6px;
}


/* Hide default radio button circles in sidebar */
[data-testid="stSidebar"] [data-testid="stRadio"] label > div:first-child,
[data-testid="stSidebar"] [data-testid="stRadio"] input[type="radio"] {
    display: none !important;
    width: 0 !important;
    height: 0 !important;
}



[data-testid="stSidebar"] [data-testid="stRadio"] label {
    background: transparent;
    border: 1px solid transparent;
    border-radius: 10px;
    padding: 10px 14px !important;
    color: #B9B9C0 !important;
    width: 100%;
    cursor: pointer;
    transition: all .15s ease;
}

[data-testid="stSidebar"] [data-testid="stRadio"] label:hover {
    background: #202023;
    color: white !important;
}

[data-testid="stSidebar"] [data-testid="stRadio"] label:has(input:checked) {
    background: #352216;
    border: 1px solid #674020;
    color: #FF9A45 !important;
}

[data-testid="stSidebar"] [data-testid="stRadio"] label p {
    color: inherit !important;
    font-weight: 600;
    font-size: 14px;
    margin: 0 !important;
}

.sidebar-bottom {
    margin-top: 28px;
    padding-top: 18px;
    border-top: 1px solid var(--border);
}

.sidebar-user {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 8px 2px 13px 2px;
}

.sidebar-avatar, .profile-avatar {
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 50%;
    background: linear-gradient(145deg, #FF963F, #C65A13);
    color: #FFFFFF !important;
    font-weight: 800;
    flex-shrink: 0;
}

.sidebar-avatar {
    width: 37px;
    height: 37px;
    font-size: 16px;
}

.sidebar-user-info {
    min-width: 0;
}

.sidebar-user-name {
    font-size: 12px;
    font-weight: 700;
    color: white !important;
}

.sidebar-user-email {
    font-size: 10px;
    color: #929298 !important;
    overflow-wrap: anywhere;
}

/* PAGE HEADERS */
.page-header {
    padding: 4px 0 24px 0;
}

.eyebrow {
    color: var(--orange) !important;
    font-size: 10px;
    font-weight: 800;
    letter-spacing: 2px;
    margin-bottom: 9px;
}

.page-title {
    color: #FFFFFF !important;
    font-size: clamp(27px, 3vw, 38px);
    font-weight: 780;
    letter-spacing: -1.2px;
    line-height: 1.18;
}

.page-description {
    color: var(--muted) !important;
    font-size: 13px;
    margin-top: 9px;
    line-height: 1.6;
}

.section-heading {
    color: #F7F7F7 !important;
    font-size: 19px;
    font-weight: 750;
    letter-spacing: -.35px;
    margin: 15px 0 4px 0;
}

.section-subtitle {
    color: var(--muted) !important;
    font-size: 12px;
    margin-bottom: 15px;
}

/* METRIC CARDS */
.metric-card {
    background: linear-gradient(145deg, #202023, #171719);
    border: 1px solid #343438;
    border-radius: 15px;
    padding: 17px 18px;
    min-height: 130px;
    box-shadow: 0 8px 24px rgba(0,0,0,.12);
}

.metric-top {
    display: flex;
    align-items: center;
    gap: 9px;
}

.metric-icon {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 29px;
    height: 29px;
    border-radius: 9px;
    color: #FF9A45 !important;
    background: rgba(244,119,33,.13);
    font-size: 15px;
}

.metric-label {
    color: #AFAFB6 !important;
    font-size: 11px;
    font-weight: 600;
}

.metric-value {
    color: #FFFFFF !important;
    font-size: 29px;
    font-weight: 800;
    letter-spacing: -.8px;
    margin-top: 13px;
    line-height: 1.1;
}

.metric-caption {
    color: #85858D !important;
    font-size: 10px;
    margin-top: 7px;
}

[data-testid="stMetric"] {
    background: linear-gradient(145deg, #202023, #171719);
    border: 1px solid var(--border);
    border-radius: 13px;
    padding: 15px;
}

[data-testid="stMetricLabel"] {
    color: var(--muted) !important;
}

[data-testid="stMetricValue"] {
    color: #FFFFFF !important;
    font-weight: 750;
}

[data-testid="stMetricDelta"] {
    color: var(--muted) !important;
}

/* CONTENT CARDS */
.content-card {
    background: linear-gradient(145deg, #1E1E21, #171719);
    border: 1px solid var(--border);
    border-radius: 14px;
    padding: 18px;
    min-height: 145px;
}

.content-card-title {
    color: #FFFFFF !important;
    font-size: 15px;
    font-weight: 750;
    margin-bottom: 10px;
}

.content-card-description {
    color: #A7A7AE !important;
    font-size: 12px;
    line-height: 1.65;
}

.mini-tag {
    display: inline-block;
    color: #FFAC68 !important;
    background: #352216;
    border: 1px solid #674020;
    border-radius: 20px;
    font-size: 9px;
    font-weight: 750;
    letter-spacing: .7px;
    padding: 5px 9px;
    margin-top: 13px;
}

.tip-card {
    background: linear-gradient(
        120deg,
        rgba(244,119,33,.16),
        rgba(244,119,33,.04)
    );
    border: 1px solid rgba(244,119,33,.3);
    border-radius: 14px;
    padding: 17px;
    margin-top: 17px;
}

.tip-label {
    color: #FF9A45 !important;
    font-size: 9px;
    font-weight: 800;
    letter-spacing: 1.5px;
}

.tip-title {
    color: white !important;
    font-size: 15px;
    font-weight: 750;
    margin-top: 9px;
}

.tip-description {
    color: #B7B7BE !important;
    font-size: 11px;
    line-height: 1.6;
    margin-top: 6px;
}

/* STUDY PLAN */
.plan-banner {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 15px;
    background: linear-gradient(110deg, #2A1B12, #1B1715);
    border: 1px solid #684023;
    border-radius: 16px;
    padding: 22px;
    margin: 8px 0 20px 0;
}

.plan-banner-title {
    color: #FFFFFF !important;
    font-size: 23px;
    font-weight: 800;
    margin-top: 5px;
}

.plan-banner-meta {
    color: #B5A69B !important;
    font-size: 11px;
    margin-top: 7px;
}

.plan-status-pill {
    color: #FFB477 !important;
    background: #4A2A18;
    border: 1px solid #8C512A;
    border-radius: 30px;
    font-size: 10px;
    font-weight: 800;
    letter-spacing: 1px;
    padding: 7px 12px;
}

.plan-overview {
    display: flex;
    align-items: center;
    justify-content: space-between;
    background: #1B1B1E;
    border: 1px solid var(--border);
    border-radius: 13px;
    padding: 16px 18px;
    margin-top: 10px;
}

.plan-overview-title {
    color: white !important;
    font-size: 15px;
    font-weight: 750;
}

.plan-overview-subtitle {
    color: var(--muted) !important;
    font-size: 11px;
    margin-top: 4px;
}

.plan-overview-percent {
    color: #FF9744 !important;
    font-size: 25px;
    font-weight: 800;
}

.session-status {
    color: #FFAB6A !important;
    background: #352216;
    border: 1px solid #674020;
    border-radius: 20px;
    display: inline-block;
    font-size: 10px;
    padding: 5px 10px;
}

/* SUBJECTS / TOPICS */
.topic-card {
    background: #202023;
    border: 1px solid #38383D;
    border-radius: 10px;
    padding: 12px;
    margin: 5px 0;
}

.topic-card-title {
    color: #FFFFFF !important;
    font-size: 13px;
    font-weight: 700;
}

.topic-card-meta {
    color: #929298 !important;
    font-size: 10px;
    margin-top: 5px;
}

/* PROFILE */
.profile-banner {
    display: flex;
    align-items: center;
    gap: 18px;
    background: linear-gradient(120deg, #251A14, #1B1B1E);
    border: 1px solid #59402F;
    border-radius: 16px;
    padding: 24px;
}

.profile-avatar {
    width: 64px;
    height: 64px;
    font-size: 27px;
}

.profile-name {
    color: white !important;
    font-size: 22px;
    font-weight: 800;
}

.profile-email {
    color: #B4A69D !important;
    font-size: 12px;
    margin-top: 4px;
}

.profile-tag {
    display: inline-block;
    color: #FFAC68 !important;
    background: #352216;
    border: 1px solid #674020;
    border-radius: 20px;
    font-size: 9px;
    font-weight: 800;
    letter-spacing: 1px;
    padding: 5px 9px;
    margin-top: 10px;
}

.profile-value {
    color: #FFFFFF !important;
    font-size: 18px;
    font-weight: 750;
    background: #1D1D20;
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 13px;
    margin-top: 7px;
}

/* AUTHENTICATION */
.auth-brand {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 12px;
    margin: 30px 0 35px 0;
}

.auth-brand-name {
    color: #FFFFFF !important;
    font-size: 21px;
    font-weight: 800;
}

.auth-brand-caption {
    color: #8C8C94 !important;
    font-size: 9px;
    letter-spacing: 1.4px;
}

.auth-intro {
    text-align: center;
    padding: 10px 0 24px 0;
}

.auth-title {
    color: #FFFFFF !important;
    font-size: 37px;
    font-weight: 850;
    line-height: 1.15;
    letter-spacing: -1.2px;
    margin-top: 12px;
}

.auth-title span {
    color: #FF9341 !important;
}

.auth-description {
    color: #A7A7AE !important;
    font-size: 12px;
    line-height: 1.7;
    margin: 13px auto 0 auto;
    max-width: 390px;
}

/* BUTTONS */
.stButton > button,
.stFormSubmitButton > button,
[data-testid="stDownloadButton"] button,
[data-testid="stLinkButton"] a {
    background: linear-gradient(
        110deg,
        #C65A13,
        #F47721
    ) !important;
    color: #FFFFFF !important;
    border: 1px solid transparent !important;
    border-radius: 9px !important;
    font-weight: 700 !important;
    min-height: 40px;
    transition: all .15s ease;
}

.stButton > button:hover,
.stFormSubmitButton > button:hover,
[data-testid="stDownloadButton"] button:hover,
[data-testid="stLinkButton"] a:hover {
    background: #FF8B35 !important;
    color: #FFFFFF !important;
    border-color: #FFB547 !important;
    box-shadow: 0 4px 15px rgba(244,119,33,.18);
}

/* INPUTS */
[data-testid="stTextInput"] input,
[data-testid="stNumberInput"] input,
[data-testid="stTextArea"] textarea {
    background: #202023 !important;
    color: #F5F5F5 !important;
    -webkit-text-fill-color: #F5F5F5 !important;
    border: 1px solid #3A3A40 !important;
    border-radius: 9px !important;
}

[data-testid="stTextInput"] input::placeholder,
[data-testid="stTextArea"] textarea::placeholder {
    color: #929298 !important;
    -webkit-text-fill-color: #929298 !important;
}

[data-testid="stSelectbox"] [data-baseweb="select"] > div,
[data-testid="stMultiSelect"] [data-baseweb="select"] > div {
    background: #202023 !important;
    color: #F5F5F5 !important;
    border-color: #3A3A40 !important;
    border-radius: 9px !important;
}

[data-testid="stSelectbox"] [data-baseweb="select"] *,
[data-testid="stMultiSelect"] [data-baseweb="select"] * {
    color: #F5F5F5 !important;
}

[data-baseweb="popover"],
[data-baseweb="popover"] > div,
[data-baseweb="menu"],
[role="listbox"] {
    background: #202023 !important;
    color: #F5F5F5 !important;
    border: 1px solid #45454A !important;
}

[role="option"],
[role="option"] * {
    background: #202023 !important;
    color: #F5F5F5 !important;
    -webkit-text-fill-color: #F5F5F5 !important;
}

[role="option"]:hover {
    background: #3A281E !important;
    color: #FF9A45 !important;
}

[aria-selected="true"] {
    background: #4A2A18 !important;
    color: #FFFFFF !important;
}

/* TABS / RADIO / CHECKBOX */
[data-testid="stTabs"] [role="tablist"] {
    border-bottom: 1px solid var(--border);
    gap: 12px;
}

[data-testid="stTabs"] button[role="tab"] {
    color: var(--muted) !important;
}

[data-testid="stTabs"] button[aria-selected="true"] {
    color: var(--orange) !important;
    border-bottom: 2px solid var(--orange) !important;
}

[data-testid="stRadio"] label,
[data-testid="stCheckbox"] label {
    color: var(--white) !important;
}

/* CONTAINERS / EXPANDERS / ALERTS */
[data-testid="stVerticalBlockBorderWrapper"] {
    background: #171719 !important;
    border: 1px solid #343438 !important;
    border-radius: 13px !important;
}

[data-testid="stExpander"],
[data-testid="stExpander"] details {
    background: #171719 !important;
    border: 1px solid var(--border) !important;
    border-radius: 12px !important;
    overflow: hidden;
}

[data-testid="stExpander"] summary {
    background: #202023 !important;
    color: #F5F5F5 !important;
}

[data-testid="stExpander"] summary *,
[data-testid="stExpander"] details > div {
    color: #F5F5F5 !important;
}

[data-testid="stAlert"] {
    background: #1D1D20 !important;
    color: #F5F5F5 !important;
    border: 1px solid var(--border) !important;
    border-radius: 10px !important;
}

/* CHARTS / PROGRESS */
[data-testid="stProgressBar"] > div > div {
    background: #F47721 !important;
}

[data-testid="stProgressBar"] {
    background: #303034 !important;
}

/* FOOTER */
.app-footer {
    display: flex;
    justify-content: space-between;
    gap: 10px;
    border-top: 1px solid var(--border);
    padding: 15px 2px 5px 2px;
    margin-top: 18px;
    color: #77777F !important;
    font-size: 10px;
}

.app-footer span:first-child {
    color: #FF9341 !important;
    font-weight: 800;
}

/* LINKS / JSON / SCROLLBAR */
a {
    color: #FF9A45 !important;
}

[data-testid="stJson"] {
    background: #171719 !important;
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 12px;
}

::-webkit-scrollbar {
    width: 8px;
    height: 8px;
}

::-webkit-scrollbar-track {
    background: var(--bg);
}

::-webkit-scrollbar-thumb {
    background: #45454A;
    border-radius: 10px;
}

::-webkit-scrollbar-thumb:hover {
    background: var(--orange);
}

/* RESPONSIVE */
@media (max-width: 768px) {
    .block-container {
        padding: 1rem;
    }

    .page-title {
        font-size: 27px;
    }

    .auth-title {
        font-size: 30px;
    }

    .metric-card {
        min-height: 115px;
        padding: 13px;
    }

    .metric-value {
        font-size: 24px;
    }

    .plan-banner {
        align-items: flex-start;
        flex-direction: column;
    }

    .app-footer {
        flex-direction: column;
    }
}
</style>""",
        unsafe_allow_html=True,
    )