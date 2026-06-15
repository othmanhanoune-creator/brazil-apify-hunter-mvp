from __future__ import annotations

import base64
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from src.supabase_client.lead_repository import (
    fetch_available_leads,
    fetch_my_leads,
    fetch_all_leads,
    fetch_claim_summary,
    fetch_claim_log,
    claim_many_leads,
)


# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="B2B Flooring Lead Portal / B2B地面材料商机线索门户",
    layout="wide",
    initial_sidebar_state="collapsed",
)


# ============================================================
# PATHS / ASSETS
# ============================================================

APP_DIR = Path(__file__).resolve().parent
ASSETS_DIR = APP_DIR / "assets"

LOGO_CANDIDATES = [
    ASSETS_DIR / "logo.png",
    ASSETS_DIR / "logo.jpg",
    ASSETS_DIR / "logo.jpeg",
    ASSETS_DIR / "logo.webp",
    ASSETS_DIR / "Logo.png",
    ASSETS_DIR / "Logo.jpg",
    ASSETS_DIR / "JCL.png",
    ASSETS_DIR / "jcl.png",
]

COVER_CANDIDATES = [
    ASSETS_DIR / "cover.png",
    ASSETS_DIR / "cover.gif",
    ASSETS_DIR / "cover.jpg",
    ASSETS_DIR / "cover.jpeg",
    ASSETS_DIR / "banner.png",
    ASSETS_DIR / "banner.gif",
]


# ============================================================
# STRICT ACCESS SETTINGS
# ============================================================

ADMIN_SUMMARY_EMAILS = {
    "gina@jcl.com",
    "lucas@jcl.com",
    "bi1@jcl.com",
    "bi2@jcl.com",
    "sales.manager@jcl.com",
    "salesmanager@jcl.com",
}

FULL_EXPORT_EMAILS = {
    "gina@jcl.com",
    "lucas@jcl.com",
    "bi1@jcl.com",
}

CLAIM_ACCESS_ROLES = {
    "ceo",
    "business_gm",
    "bi_admin",
    "bi_partial",
    "sales_manager",
    "sales_rep",
}


# ============================================================
# CSS
# ============================================================

st.markdown(
    """
    <style>
        .main .block-container {
            padding-top: 0.5rem;
            padding-bottom: 2rem;
            max-width: 1500px;
        }

        .merged-cover {
            position: relative;
            width: 100vw;
            height: 350px;
            margin-left: calc(-50vw + 50%);
            margin-right: calc(-50vw + 50%);
            margin-top: 0;
            margin-bottom: 36px;
            overflow: hidden;
            background: #0f172a;
        }

        .merged-cover img.cover-bg {
            width: 100%;
            height: 100%;
            object-fit: cover;
            object-position: center center;
            display: block;
            opacity: 0.72;
        }

        .merged-cover-overlay {
            position: absolute;
            inset: 0;
            background: linear-gradient(
                90deg,
                rgba(15, 23, 42, 0.82) 0%,
                rgba(15, 23, 42, 0.48) 45%,
                rgba(15, 23, 42, 0.22) 100%
            );
        }

        .merged-cover-nav {
            position: absolute;
            top: 28px;
            left: max(56px, calc((100vw - 1280px) / 2 + 24px));
            right: max(56px, calc((100vw - 1280px) / 2 + 24px));
            display: flex;
            justify-content: space-between;
            align-items: center;
            z-index: 5;
        }

        .merged-brand {
            display: flex;
            align-items: center;
            gap: 16px;
        }

        .merged-logo-box {
            width: 110px;
            height: 110px;
            background: rgba(255, 255, 255, 0.96);
            border-radius: 22px;
            padding: 10px;
            box-shadow: 0 16px 38px rgba(0, 0, 0, 0.30);
            display: flex;
            align-items: center;
            justify-content: center;
        }

        .merged-logo-box img {
            width: 100%;
            height: 100%;
            object-fit: contain;
            display: block;
        }

        .merged-logo-fallback {
            width: 110px;
            height: 110px;
            background: rgba(255, 255, 255, 0.96);
            border-radius: 22px;
            color: #166534;
            font-size: 36px;
            font-weight: 900;
            display: flex;
            align-items: center;
            justify-content: center;
            box-shadow: 0 16px 38px rgba(0, 0, 0, 0.30);
        }

        .merged-brand-title {
            color: #ffffff;
            font-size: 26px;
            font-weight: 850;
            letter-spacing: -0.4px;
        }

        .merged-brand-subtitle {
            color: #dbeafe;
            font-size: 14px;
            margin-top: 4px;
        }

        .merged-cover-date {
            color: #e2e8f0;
            font-size: 14px;
            line-height: 1.5;
            text-align: right;
        }

        .merged-cover-content {
            position: absolute;
            left: max(56px, calc((100vw - 1280px) / 2 + 24px));
            bottom: 52px;
            color: white;
            max-width: 760px;
            z-index: 5;
        }

        .merged-cover-title {
            font-size: 42px;
            line-height: 1.08;
            font-weight: 900;
            letter-spacing: -1px;
            margin-bottom: 14px;
        }

        .merged-cover-subtitle {
            font-size: 18px;
            line-height: 1.55;
            color: #e2e8f0;
            max-width: 720px;
        }

        .merged-cover-fallback {
            width: 100vw;
            height: 350px;
            margin-left: calc(-50vw + 50%);
            margin-right: calc(-50vw + 50%);
            margin-bottom: 36px;
            position: relative;
            overflow: hidden;
            background: linear-gradient(135deg, #0f172a 0%, #14532d 55%, #0f766e 100%);
        }

        .hero-card {
            background: #ffffff;
            border: 1px solid #e5e7eb;
            border-radius: 22px;
            padding: 32px;
            box-shadow: 0 18px 44px rgba(15, 23, 42, 0.08);
            min-height: 280px;
        }

        .badge {
            display: inline-block;
            padding: 7px 12px;
            border-radius: 999px;
            background: #dcfce7;
            color: #166534;
            font-size: 13px;
            font-weight: 700;
            margin-bottom: 18px;
        }

        .hero-title {
            font-size: 34px;
            font-weight: 850;
            color: #0f172a;
            margin-bottom: 14px;
            line-height: 1.15;
        }

        .hero-subtitle {
            font-size: 17px;
            color: #334155;
            line-height: 1.7;
            margin-bottom: 18px;
        }

        .hero-note {
            font-size: 14px;
            color: #64748b;
            line-height: 1.6;
        }

        .login-box {
            background: #ffffff;
            border: 1px solid #e5e7eb;
            border-radius: 22px;
            padding: 30px;
            box-shadow: 0 18px 44px rgba(15, 23, 42, 0.08);
        }

        .login-title {
            font-size: 26px;
            font-weight: 850;
            color: #0f172a;
            margin-bottom: 8px;
        }

        .login-text {
            color: #64748b;
            font-size: 15px;
            margin-bottom: 18px;
            line-height: 1.6;
        }

        .footer {
            text-align: center;
            color: #94a3b8;
            font-size: 13px;
            margin-top: 36px;
            margin-bottom: 12px;
        }

        div[data-testid="stMetric"] {
            background: #ffffff;
            border: 1px solid #eeeeee;
            padding: 14px 16px;
            border-radius: 16px;
            box-shadow: 0 8px 20px rgba(0,0,0,0.035);
        }
    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def get_first_existing_path(paths: list[Path]) -> Path | None:
    for path in paths:
        if path.exists() and path.is_file():
            return path
    return None


def get_image_mime(path: Path) -> str:
    suffix = path.suffix.lower()

    if suffix == ".png":
        return "image/png"
    if suffix in [".jpg", ".jpeg"]:
        return "image/jpeg"
    if suffix == ".webp":
        return "image/webp"
    if suffix == ".gif":
        return "image/gif"

    return "image/png"


def file_to_base64(path: Path) -> str:
    with open(path, "rb") as file:
        return base64.b64encode(file.read()).decode("utf-8")


def safe_text(value: Any) -> str:
    if pd.isna(value) or value is None:
        return ""
    return str(value).strip()


def get_users() -> dict[str, dict[str, Any]]:
    if "users" not in st.secrets:
        return {}

    users = {}

    for username, user_data in st.secrets["users"].items():
        email = str(user_data.get("email", "")).strip().lower()
        password = str(user_data.get("password", "")).strip()
        name = str(user_data.get("name", username)).strip()
        role = str(user_data.get("role", "sales_rep")).strip().lower()

        if not email or not password:
            continue

        users[email] = {
            "username": str(username).strip().lower(),
            "email": email,
            "password": password,
            "name": name,
            "role": role,
        }

    return users


def authenticate(email: str, password: str) -> dict[str, Any] | None:
    users = get_users()

    email = str(email).lower().strip()
    password = str(password).strip()

    user = users.get(email)

    if user is None:
        return None

    if user["password"] != password:
        return None

    return {
        "username": user["username"],
        "email": user["email"],
        "name": user["name"],
        "role": user["role"],
    }


def login_user(user: dict[str, Any]) -> None:
    st.session_state.logged_in = True
    st.session_state.user = user


def logout_user() -> None:
    st.session_state.logged_in = False
    st.session_state.user = None


def can_view_summary(user: dict[str, Any]) -> bool:
    email = str(user.get("email", "")).strip().lower()
    return email in ADMIN_SUMMARY_EMAILS


def can_download_all_data(user: dict[str, Any]) -> bool:
    email = str(user.get("email", "")).strip().lower()
    return email in FULL_EXPORT_EMAILS


def can_claim_leads(user: dict[str, Any]) -> bool:
    role = str(user.get("role", "sales_rep")).strip().lower()
    return role in CLAIM_ACCESS_ROLES


def role_label(role: str) -> str:
    labels = {
        "ceo": "CEO / 总裁",
        "business_gm": "Business GM / 业务总经理",
        "bi_admin": "BI Admin / BI管理员",
        "bi_partial": "BI Partial / BI部分权限",
        "sales_manager": "Sales Manager / 销售经理",
        "sales_rep": "Sales Representative / 销售代表",
    }

    return labels.get(role, role)


def ensure_market_column(df: pd.DataFrame, default_market: str = "Brazil") -> pd.DataFrame:
    if df.empty:
        return df

    df = df.copy()

    if "market" not in df.columns:
        df["market"] = default_market

    df["market"] = df["market"].fillna(default_market).astype(str)

    return df


def normalize_dataframe_for_display(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    df = df.copy()

    for col in df.columns:
        if df[col].dtype == "object":
            df[col] = df[col].fillna("")

    return df


def render_header() -> None:
    logo_path = get_first_existing_path(LOGO_CANDIDATES)
    cover_path = get_first_existing_path(COVER_CANDIDATES)

    if logo_path:
        logo_base64 = file_to_base64(logo_path)
        logo_html = f"""
        <div class="merged-logo-box">
            <img src="data:{get_image_mime(logo_path)};base64,{logo_base64}" />
        </div>
        """
    else:
        logo_html = '<div class="merged-logo-fallback">JCL</div>'

    if cover_path:
        cover_base64 = file_to_base64(cover_path)
        cover_html = f"""
        <img class="cover-bg" src="data:{get_image_mime(cover_path)};base64,{cover_base64}" />
        """
        cover_class = "merged-cover"
    else:
        cover_html = ""
        cover_class = "merged-cover-fallback"

    st.markdown(
        f"""
        <div class="{cover_class}">
            {cover_html}
            <div class="merged-cover-overlay"></div>

            <div class="merged-cover-nav">
                <div class="merged-brand">
                    {logo_html}
                    <div>
                        <div class="merged-brand-title">B2B Flooring Lead Portal</div>
                        <div class="merged-brand-subtitle">Internal Sales Intelligence System / 内部销售情报系统</div>
                    </div>
                </div>

                <div class="merged-cover-date">
                    Lead Distribution Portal / 线索分配门户<br>
                    {datetime.now().strftime("%B %d, %Y")}
                </div>
            </div>

            <div class="merged-cover-content">
                <div class="merged-cover-title">Controlled Lead Distribution / 可控线索分配</div>
                <div class="merged-cover-subtitle">
                    Claim qualified leads, track ownership, and manage Brazil sales opportunities.
                    <br>
                    认领高质量线索，追踪负责人，并管理巴西市场商机。
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ============================================================
# SESSION STATE
# ============================================================

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if "user" not in st.session_state:
    st.session_state.user = None


# ============================================================
# HEADER
# ============================================================

render_header()


# ============================================================
# LOGIN PAGE
# ============================================================

if not st.session_state.logged_in:
    hero_left, hero_right = st.columns([1.12, 0.88], gap="large")

    with hero_left:
        st.markdown(
            """
            <div class="hero-card">
                <div class="badge">Internal Portal · BI & Sales Operations / 内部门户 · BI与销售运营</div>
                <div class="hero-title">B2B Flooring Lead Distribution / B2B地面材料销售线索分配</div>
                <div class="hero-subtitle">
                    Access qualified flooring distributor and wholesale leads selected by the BI team.
                    Claim leads, manage ownership, and manage Brazil market opportunities.
                    <br><br>
                    获取由 BI 团队筛选的高质量地面材料分销商与批发商线索。
                    认领线索、管理负责人，并管理巴西市场。
                </div>
                <div class="hero-note">
                    This portal replaces uncontrolled CSV sharing with role-based and traceable lead access.
                    <br>
                    本系统用于替代缺乏管控的 CSV 共享，实现基于角色的可追溯线索访问。
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with hero_right:
        st.markdown(
            """
            <div class="login-box">
                <div class="login-title">Welcome Back / 欢迎回来</div>
                <div class="login-text">
                    Log in to view available leads, claim new opportunities, and manage your assigned accounts.
                    <br>
                    登录后可查看可用线索、认领新商机，并管理您负责的客户。
                </div>
            """,
            unsafe_allow_html=True,
        )

        with st.form("login_form"):
            email = st.text_input("Email / 邮箱", placeholder="name@jcl.com")
            password = st.text_input("Password / 密码", type="password", placeholder="Password / 密码")
            submitted = st.form_submit_button("Login / 登录")

            if submitted:
                user = authenticate(email, password)

                if user:
                    login_user(user)
                    st.rerun()
                else:
                    st.error("Invalid email or password. / 邮箱或密码错误。")

        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown(
        """
        <div class="footer">
            B2B Flooring Lead Portal · Internal Sales Intelligence System · Built by BI Team
            <br>
            B2B 地面材料商机线索门户 · 内部销售情报系统 · 由 BI 团队构建
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.stop()


# ============================================================
# LOGGED-IN APP
# ============================================================

user = st.session_state.user
role = str(user.get("role", "sales_rep")).strip().lower()

summary_allowed = can_view_summary(user)
claim_allowed = can_claim_leads(user)
full_data_allowed = can_download_all_data(user)

st.success(
    f"Logged in / 当前登录：{user['name']} · {role_label(role)} · {user['email']}"
)

try:
    available = fetch_available_leads()
    my_leads = fetch_my_leads(user["email"])

    available = ensure_market_column(available)
    my_leads = ensure_market_column(my_leads)

    available = normalize_dataframe_for_display(available)
    my_leads = normalize_dataframe_for_display(my_leads)

    if summary_allowed:
        all_leads = fetch_all_leads()
        claim_summary = fetch_claim_summary()
        claim_log = fetch_claim_log()

        all_leads = ensure_market_column(all_leads)
        all_leads = normalize_dataframe_for_display(all_leads)
        claim_summary = normalize_dataframe_for_display(claim_summary)
        claim_log = normalize_dataframe_for_display(claim_log)
    else:
        all_leads = pd.DataFrame()
        claim_summary = pd.DataFrame()
        claim_log = pd.DataFrame()

except Exception as exc:
    st.error("Could not load data from Supabase. / 无法从 Supabase 加载数据。")
    st.exception(exc)
    st.stop()


# ============================================================
# KPI ROW
# ============================================================

if summary_allowed:
    total_leads = len(all_leads)
    available_count = len(available)
    claimed_count = (
        int((all_leads["lead_status"] == "claimed").sum())
        if not all_leads.empty and "lead_status" in all_leads.columns
        else 0
    )
    my_count = len(my_leads)

    kpi1, kpi2, kpi3, kpi4 = st.columns(4)

    with kpi1:
        st.metric("Total Leads / 线索总数", total_leads)

    with kpi2:
        st.metric("Available Leads / 可用线索", available_count)

    with kpi3:
        st.metric("Claimed Leads / 已认领线索", claimed_count)

    with kpi4:
        st.metric("My Leads / 我的线索", my_count)

else:
    kpi1, kpi2 = st.columns(2)

    with kpi1:
        st.metric("Available Leads / 可用线索", len(available))

    with kpi2:
        st.metric("My Leads / 我的线索", len(my_leads))


# ============================================================
# TABS
# ============================================================

if summary_allowed:
    tab_available, tab_my, tab_admin = st.tabs(
        [
            "Available Leads / 可用线索",
            "My Leads / 我的线索",
            "Admin Summary / 管理汇总",
        ]
    )
else:
    tab_available, tab_my = st.tabs(
        [
            "Available Leads / 可用线索",
            "My Leads / 我的线索",
        ]
    )
    tab_admin = None


# ============================================================
# AVAILABLE LEADS
# ============================================================

with tab_available:
    st.markdown("### Available Sales-Ready Leads / 可用高质量销售线索")
    st.caption(
        "Select leads using the checkbox, then click Claim Selected Leads. "
        "/ 勾选线索后，点击“认领所选线索”。"
    )

    if available.empty:
        st.info("No available leads. / 暂无可用线索。")
    else:
        filtered = available.copy()

        filter_col1, filter_col2, filter_col3 = st.columns([1, 1, 2])

        with filter_col1:
            if "market" in filtered.columns:
                market_options = ["All / 全部"] + sorted(
                    filtered["market"]
                    .replace("", pd.NA)
                    .dropna()
                    .astype(str)
                    .unique()
                    .tolist()
                )

                selected_market = st.selectbox(
                    "Market / 市场",
                    market_options,
                )

                if selected_market != "All / 全部":
                    filtered = filtered[filtered["market"].astype(str) == selected_market]

        with filter_col2:
            if "state" in filtered.columns:
                state_options = ["All / 全部"] + sorted(
                    filtered["state"]
                    .replace("", pd.NA)
                    .dropna()
                    .astype(str)
                    .unique()
                    .tolist()
                )

                selected_state = st.selectbox(
                    "State / 州",
                    state_options,
                )

                if selected_state != "All / 全部":
                    filtered = filtered[filtered["state"].astype(str) == selected_state]

        with filter_col3:
            search_text = st.text_input(
                "Search company, city, website, phone, or email / 搜索公司、城市、网站、电话或邮箱"
            )

        if search_text:
            searchable_cols = [
                col
                for col in ["market", "name", "city", "state", "website", "phone", "email"]
                if col in filtered.columns
            ]

            if searchable_cols:
                search_blob = (
                    filtered[searchable_cols]
                    .fillna("")
                    .astype(str)
                    .agg(" ".join, axis=1)
                    .str.lower()
                )

                filtered = filtered[
                    search_blob.str.contains(search_text.lower(), na=False)
                ]

        if "lead_id" not in filtered.columns:
            st.error(
                "System error: lead_id is missing from Supabase data. "
                "/ 系统错误：Supabase 数据中缺少 lead_id。"
            )
            st.stop()

        display_cols = [
            "lead_id",
            "market",
            "name",
            "city",
            "state",
            "country",
            "phone",
            "website",
            "email",
            "email_status",
            "email_confidence",
            "b2b_score",
            "gold_split_reason",
        ]

        display_cols = [col for col in display_cols if col in filtered.columns]

        view = filtered[display_cols].copy()
        view.insert(0, "claim", False)

        if not claim_allowed:
            st.info("Your role can view leads but cannot claim them. / 您的角色可以查看线索，但不能认领。")

        edited = st.data_editor(
            view,
            hide_index=True,
            use_container_width=True,
            disabled=[col for col in display_cols] + ([] if claim_allowed else ["claim"]),
            column_config={
                "claim": st.column_config.CheckboxColumn("Claim / 认领"),
                "lead_id": st.column_config.TextColumn("Lead ID / 线索ID"),
                "market": st.column_config.TextColumn("Market / 市场"),
                "name": st.column_config.TextColumn("Company / 公司"),
                "city": st.column_config.TextColumn("City / 城市"),
                "state": st.column_config.TextColumn("State / 州"),
                "country": st.column_config.TextColumn("Country / 国家"),
                "phone": st.column_config.TextColumn("Phone / 电话"),
                "website": st.column_config.LinkColumn("Website / 网站"),
                "email": st.column_config.TextColumn("Email / 邮箱"),
                "email_status": st.column_config.TextColumn("Email Status / 邮箱状态"),
                "email_confidence": st.column_config.TextColumn("Email Confidence / 邮箱置信度"),
                "b2b_score": st.column_config.NumberColumn("B2B Score / B2B评分"),
                "gold_split_reason": st.column_config.TextColumn("Reason / 入选原因"),
            },
        )

        selected = edited[edited["claim"] == True].copy()

        if claim_allowed:
            if st.button("Claim Selected Leads / 认领所选线索", use_container_width=True):
                if selected.empty:
                    st.warning("No leads selected. / 尚未选择任何线索。")

                elif "lead_id" not in selected.columns:
                    st.error(
                        "System error: lead_id is missing from the selected table. "
                        "/ 系统错误：所选表格缺少 lead_id。"
                    )

                else:
                    selected_lead_ids = (
                        selected["lead_id"]
                        .dropna()
                        .astype(str)
                        .str.strip()
                        .tolist()
                    )

                    selected_lead_ids = [
                        lead_id for lead_id in selected_lead_ids if lead_id
                    ]

                    if not selected_lead_ids:
                        st.warning("Selected rows have no lead_id. / 所选行没有 lead_id。")
                    else:
                        result = claim_many_leads(
                            lead_ids=selected_lead_ids,
                            user_email=user["email"],
                            user_name=user["name"],
                        )

                        claimed = result.get("claimed", 0)
                        failed = result.get("failed", 0)

                        if claimed > 0:
                            st.success(
                                f"Claimed {claimed} lead(s). / 成功认领 {claimed} 条线索。"
                            )

                        if failed > 0:
                            st.warning(
                                f"{failed} lead(s) could not be claimed. They may already be taken. "
                                f"/ {failed} 条线索无法认领，可能已被他人认领。"
                            )

                        st.rerun()


# ============================================================
# MY LEADS
# ============================================================

with tab_my:
    st.markdown("### My Claimed Leads / 我的已认领线索")

    if my_leads.empty:
        st.info("You have not claimed any leads yet. / 您还没有认领任何线索。")
    else:
        my_display_cols = [
            "market",
            "lead_id",
            "name",
            "city",
            "state",
            "country",
            "phone",
            "website",
            "email",
            "email_source",
            "email_status",
            "email_confidence",
            "assigned_at",
            "gold_split_reason",
        ]

        my_display_cols = [col for col in my_display_cols if col in my_leads.columns]

        st.dataframe(
            my_leads[my_display_cols],
            hide_index=True,
            use_container_width=True,
            column_config={
                "market": st.column_config.TextColumn("Market / 市场"),
                "lead_id": st.column_config.TextColumn("Lead ID / 线索ID"),
                "name": st.column_config.TextColumn("Company / 公司"),
                "city": st.column_config.TextColumn("City / 城市"),
                "state": st.column_config.TextColumn("State / 州"),
                "country": st.column_config.TextColumn("Country / 国家"),
                "phone": st.column_config.TextColumn("Phone / 电话"),
                "website": st.column_config.LinkColumn("Website / 网站"),
                "email": st.column_config.TextColumn("Email / 邮箱"),
                "assigned_at": st.column_config.TextColumn("Claimed At / 认领时间"),
            },
        )

        csv = my_leads.to_csv(index=False).encode("utf-8-sig")

        st.download_button(
            label="Download My Claimed Leads / 下载我的已认领线索",
            data=csv,
            file_name=f"my_claimed_leads_{user['email'].replace('@', '_at_')}.csv",
            mime="text/csv",
            use_container_width=True,
        )


# ============================================================
# ADMIN SUMMARY
# ============================================================

if summary_allowed and tab_admin is not None:
    with tab_admin:
        st.markdown("### Admin Summary / 管理汇总")

        if all_leads.empty:
            st.info("No leads available. / 暂无线索数据。")
        else:
            market_summary = (
                all_leads
                .groupby("market", dropna=False)
                .agg(
                    total_leads=("lead_id", "count"),
                    available_leads=("lead_status", lambda x: (x == "available").sum()),
                    claimed_leads=("lead_status", lambda x: (x == "claimed").sum()),
                    leads_with_email=("email", lambda x: x.fillna("").astype(str).str.strip().ne("").sum()),
                )
                .reset_index()
            )

            st.markdown("#### Market Summary / 市场汇总")
            st.dataframe(
                market_summary,
                hide_index=True,
                use_container_width=True,
            )

            col1, col2 = st.columns(2)

            with col1:
                st.markdown("#### Lead Status / 线索状态")

                if "lead_status" in all_leads.columns:
                    lead_status_summary = (
                        all_leads["lead_status"]
                        .fillna("unknown")
                        .value_counts()
                        .reset_index()
                    )

                    lead_status_summary.columns = ["lead_status / 线索状态", "count / 数量"]

                    st.dataframe(
                        lead_status_summary,
                        hide_index=True,
                        use_container_width=True,
                    )

            with col2:
                st.markdown("#### Email Coverage / 邮箱覆盖情况")

                if "email" in all_leads.columns:
                    email_count = (
                        all_leads["email"]
                        .fillna("")
                        .astype(str)
                        .str.strip()
                        .ne("")
                        .sum()
                    )

                    no_email_count = len(all_leads) - email_count

                    email_summary = pd.DataFrame(
                        [
                            {
                                "metric / 指标": "With Email / 有邮箱",
                                "count / 数量": int(email_count),
                            },
                            {
                                "metric / 指标": "Without Email / 无邮箱",
                                "count / 数量": int(no_email_count),
                            },
                        ]
                    )

                    st.dataframe(
                        email_summary,
                        hide_index=True,
                        use_container_width=True,
                    )

            st.markdown("#### Leads Claimed by User / 按用户统计认领数量")

            if claim_summary.empty:
                st.info("No claims have been made yet. / 目前还没有任何认领记录。")
            else:
                st.dataframe(
                    claim_summary,
                    hide_index=True,
                    use_container_width=True,
                )

            st.markdown("#### Full Claim Log / 完整认领记录")

            if claim_log.empty:
                st.info("No claim log yet. / 暂无认领日志。")
            else:
                st.dataframe(
                    claim_log,
                    hide_index=True,
                    use_container_width=True,
                )

            if full_data_allowed:
                st.markdown("#### Full Leads Export / 完整线索导出")

                csv_all = all_leads.to_csv(index=False).encode("utf-8-sig")

                st.download_button(
                    label="Download All Leads / 下载全部线索",
                    data=csv_all,
                    file_name="all_leads_export.csv",
                    mime="text/csv",
                    use_container_width=True,
                )


# ============================================================
# LOGOUT
# ============================================================

st.markdown("---")

if st.button("Log out / 退出登录"):
    logout_user()
    st.rerun()