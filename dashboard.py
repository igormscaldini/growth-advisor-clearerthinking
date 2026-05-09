"""ClearerThinking Growth Dashboard. Run: streamlit run dashboard.py"""
# Pull Streamlit Cloud secrets into env vars + /tmp/secrets BEFORE importing client modules.
# On local machines this is a no-op (falls back to .env + secrets/ folder).
from secrets_loader import materialize_cloud_secrets

materialize_cloud_secrets()

from datetime import date, datetime, timedelta

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from streamlit_autorefresh import st_autorefresh

from data_layer import (
    beehiiv_metrics,
    ga4_audience_metrics,
    ga4_daily_users,
    google_ads_metrics,
    stripe_metrics,
)

# ---------- Page config ----------
st.set_page_config(
    page_title="ClearerThinking Growth Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

PASSWORD = "ctteam"


# ---------- Auth gate ----------
def check_password() -> bool:
    if st.session_state.get("authenticated"):
        return True

    st.title("ClearerThinking Growth Dashboard")
    st.caption("Enter team password to continue.")
    pw = st.text_input("Password", type="password", key="pw_input")
    if st.button("Sign in"):
        if pw == PASSWORD:
            st.session_state["authenticated"] = True
            st.rerun()
        else:
            st.error("Wrong password.")
    return False


if not check_password():
    st.stop()


# ---------- Auto-refresh every 10 min ----------
st_autorefresh(interval=10 * 60 * 1000, key="auto_refresh")


# ---------- Sidebar: filters ----------
st.sidebar.title("Filters")

today = date.today()
preset = st.sidebar.radio(
    "Date range",
    ["Last 7 days", "Last 30 days", "Last 90 days", "Custom"],
    index=1,
)
if preset == "Last 7 days":
    start, end = today - timedelta(days=6), today
elif preset == "Last 30 days":
    start, end = today - timedelta(days=29), today
elif preset == "Last 90 days":
    start, end = today - timedelta(days=89), today
else:
    start = st.sidebar.date_input("From", today - timedelta(days=29))
    end = st.sidebar.date_input("To", today)

st.sidebar.markdown("---")
st.sidebar.markdown(f"**Last refreshed:** {datetime.now().strftime('%H:%M:%S')}")
st.sidebar.caption("Auto-refresh: every 10 minutes")
if st.sidebar.button("🔄 Refresh now"):
    st.cache_data.clear()
    st.rerun()
st.sidebar.markdown("---")
if st.sidebar.button("Sign out"):
    st.session_state.clear()
    st.rerun()


# ---------- Header ----------
st.title("📊 ClearerThinking Growth Dashboard")
st.caption(f"**{start}** → **{end}**  •  {(end - start).days + 1} days")


# ---------- Fetch data (cached) ----------
with st.spinner("Loading data..."):
    ga4 = ga4_audience_metrics(start, end)
    ga4_daily = ga4_daily_users(start, end)
    stripe = stripe_metrics(start, end)
    ads = google_ads_metrics(start, end)
    bh = beehiiv_metrics(start, end)


# ---------- Helpers ----------
def fmt_money(v: float) -> str:
    return f"${v:,.2f}" if v < 1000 else f"${v:,.0f}"


def fmt_int(v) -> str:
    return f"{int(v or 0):,}"


def fmt_pct(v: float) -> str:
    return f"{(v or 0) * 100:.1f}%"


# ---------- Star metrics ----------
st.markdown("### ⭐ Headline metrics")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Revenue", fmt_money(stripe.get("revenue_usd", 0)))
c2.metric("Modules Finished", fmt_int(ga4.get("modules_finished")))
c3.metric("Engaged Readers", fmt_int(bh.get("engaged_readers")))
c4.metric("Opens / Campaign", fmt_int(bh.get("opens_per_campaign")))


# ---------- Audience ----------
st.markdown("### 👥 Audience")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Unique Visitors", fmt_int(ga4.get("users")))
c2.metric("Modules Started", fmt_int(ga4.get("modules_started")))
c3.metric("Total Subscribers", fmt_int(bh.get("total_subscribers")))
c4.metric("New Subscribers", fmt_int(bh.get("new_subscribers")), help=f"beehiiv canned period: {bh.get('period_used_for_new_subs')}" if bh.get("period_used_for_new_subs") else None)


# ---------- Email ----------
st.markdown("### 📧 Email")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Emails Sent", fmt_int(bh.get("emails_sent")))
c2.metric("Email Opens", fmt_int(bh.get("email_opens")))
c3.metric("Email Clicks", fmt_int(bh.get("email_clicks")))
c4.metric("# Campaigns", fmt_int(bh.get("campaigns_count")))

c1, c2, c3, c4 = st.columns(4)
c1.metric("Open Rate", fmt_pct(bh.get("open_rate")))
c2.metric("Click Rate", fmt_pct(bh.get("click_rate")))
c3.metric("Total Unsubscribes", fmt_int(bh.get("unsubscribes")))
c4.metric("Unsubscribe Rate", fmt_pct(bh.get("unsubscribe_rate")))


# ---------- Paid ----------
st.markdown("### 💰 Paid")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Spent on Ads", fmt_money(ads.get("spend_usd", 0)))
c2.metric("Ad Impressions", fmt_int(ads.get("impressions")))
c3.metric("Ad Clicks", fmt_int(ads.get("clicks")))
c4.metric("Ad Conversions", f"{ads.get('conversions', 0):.0f}")


# beehiiv error notice (if any)
if bh.get("error"):
    st.warning(f"📧 beehiiv: {bh['error']} — email metrics shown as zero until configured.")
if ads.get("error"):
    st.warning(f"💰 Google Ads: {ads['error']}")


# ---------- Charts ----------
st.markdown("---")
st.markdown("### 📈 Trends")

# Build a combined daily DataFrame
date_index = pd.date_range(start=start, end=end, freq="D").strftime("%Y-%m-%d")
df = pd.DataFrame({"date": date_index})

users_df = pd.DataFrame(ga4_daily) if ga4_daily else pd.DataFrame(columns=["date", "users"])
df = df.merge(users_df, on="date", how="left")

if stripe.get("daily"):
    rev_df = pd.DataFrame(stripe["daily"])
    df = df.merge(rev_df, on="date", how="left")
else:
    df["revenue"] = 0

if ads.get("daily"):
    ads_df = pd.DataFrame(ads["daily"])
    df = df.merge(ads_df, on="date", how="left")
else:
    df["spend"] = 0

df = df.fillna(0)

# Chart 1: Visitors + ad spend (dual y-axis)
col_l, col_r = st.columns(2)
with col_l:
    st.markdown("**Daily visitors vs. ad spend**")
    fig1 = go.Figure()
    fig1.add_trace(go.Scatter(x=df["date"], y=df["users"], name="Visitors", mode="lines", line=dict(color="#4F8BF9", width=2)))
    fig1.add_trace(go.Bar(x=df["date"], y=df["spend"], name="Ad spend ($)", yaxis="y2", marker_color="rgba(255, 100, 100, 0.5)"))
    fig1.update_layout(
        height=320,
        margin=dict(l=0, r=0, t=10, b=0),
        legend=dict(orientation="h", y=1.1),
        yaxis=dict(title="Visitors"),
        yaxis2=dict(title="Ad spend ($)", overlaying="y", side="right"),
    )
    st.plotly_chart(fig1, use_container_width=True)

with col_r:
    st.markdown("**Daily revenue**")
    fig2 = px.bar(df, x="date", y="revenue", color_discrete_sequence=["#16A34A"])
    fig2.update_layout(height=320, margin=dict(l=0, r=0, t=10, b=0), yaxis_title="Revenue ($)", xaxis_title=None)
    st.plotly_chart(fig2, use_container_width=True)


# Funnel: visitors → modules started → modules finished
st.markdown("**Tool funnel — Visitors → Modules Started → Modules Finished**")
funnel_fig = go.Figure(go.Funnel(
    y=["Unique Visitors", "Modules Started", "Modules Finished"],
    x=[ga4.get("users", 0), ga4.get("modules_started", 0), ga4.get("modules_finished", 0)],
    textinfo="value+percent initial",
    marker=dict(color=["#4F8BF9", "#F5A524", "#16A34A"]),
))
funnel_fig.update_layout(height=300, margin=dict(l=0, r=0, t=10, b=0))
st.plotly_chart(funnel_fig, use_container_width=True)


# ---------- Campaign-level table ----------
if bh.get("per_campaign"):
    st.markdown("---")
    st.markdown("### 📨 Campaign performance")
    camp_df = pd.DataFrame(bh["per_campaign"])
    camp_df["open_rate"] = (camp_df["open_rate"] * 100).round(1).astype(str) + "%"
    camp_df["click_rate"] = (camp_df["click_rate"] * 100).round(2).astype(str) + "%"
    camp_df = camp_df.rename(columns={
        "title": "Title", "date": "Date", "sent": "Sent", "opens": "Opens",
        "clicks": "Clicks", "open_rate": "Open %", "click_rate": "Click %", "unsubs": "Unsub",
    })
    st.dataframe(camp_df, hide_index=True, use_container_width=True)


# ---------- Footer ----------
st.markdown("---")
st.caption(f"Data sources: GA4 · Stripe · Google Ads · beehiiv · GSC · Sheets · Ahrefs  •  10-min cache  •  All times in UTC unless noted.")
