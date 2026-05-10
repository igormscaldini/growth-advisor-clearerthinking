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
    beehiiv_daily_rates,
    beehiiv_metrics,
    ga4_audience_metrics,
    ga4_daily_users_and_events,
    ga4_funnel_events,
    google_ads_metrics,
    stripe_metrics,
    stripe_mrr_history,
    stripe_revenue_by_product,
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


# ---------- Sidebar ----------
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


# ---------- Fetch data ----------
with st.spinner("Loading data..."):
    ga4 = ga4_audience_metrics(start, end)
    ga4_daily = ga4_daily_users_and_events(start, end)
    funnel = ga4_funnel_events(start, end)
    stripe = stripe_metrics(start, end)
    mrr_history = stripe_mrr_history(start, end)
    rev_by_product = stripe_revenue_by_product(start, end)
    ads = google_ads_metrics(start, end)
    bh = beehiiv_metrics(start, end)
    bh_daily = beehiiv_daily_rates(start, end)


# ---------- Helpers ----------
def fmt_money(v: float) -> str:
    return f"${v:,.2f}" if v < 1000 else f"${v:,.0f}"


def fmt_int(v) -> str:
    return f"{int(v or 0):,}"


def fmt_pct(v: float) -> str:
    return f"{(v or 0) * 100:.1f}%"


# Tooltip strings — short, point at the data source
TIPS = {
    "revenue": "Stripe • sum of net charges (gross − refunded) in window",
    "modules_finished": 'GA4 • count of "Submitted Email" event in window',
    "engaged_readers": "Computed: beehiiv active subscribers × open rate",
    "opens_per_campaign": "Computed: total beehiiv opens / number of email posts in window",
    "users": "GA4 • totalUsers metric for window",
    "modules_started": 'GA4 • count of "Viewed Privacy Policy" event in window',
    "total_subscribers": "beehiiv • current_active_subscriptions (live snapshot)",
    "new_subscribers": "beehiiv • subscriptions metric over the canned period closest to your window",
    "emails_sent": "beehiiv • sum of recipients across all email posts in window",
    "email_opens": "beehiiv • sum of opens across email posts in window",
    "email_clicks": "beehiiv • sum of clicks across email posts in window",
    "campaigns_count": "beehiiv • count of email posts published in window",
    "open_rate": "beehiiv • total opens / total recipients in window",
    "click_rate": "beehiiv • total clicks / total recipients in window",
    "unsubscribes": "beehiiv • sum of unsubscribes across email posts in window",
    "unsubscribe_rate": "beehiiv • total unsubscribes / total recipients in window",
    "ad_spend": "Google Ads • sum of cost_micros / 1M for window",
    "ad_impressions": "Google Ads • sum of impressions for window",
    "ad_clicks": "Google Ads • sum of clicks for window",
    "ad_conversions": "Google Ads • sum of conversions (your configured Conversion Actions)",
}


# ---------- Star metrics ----------
st.markdown("### ⭐ Headline metrics")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Revenue", fmt_money(stripe.get("revenue_usd", 0)), help=TIPS["revenue"])
c2.metric("Modules Finished", fmt_int(ga4.get("modules_finished")), help=TIPS["modules_finished"])
c3.metric("Engaged Readers", fmt_int(bh.get("engaged_readers")), help=TIPS["engaged_readers"])
c4.metric("Opens / Campaign", fmt_int(bh.get("opens_per_campaign")), help=TIPS["opens_per_campaign"])


# ---------- Audience ----------
st.markdown("### 👥 Audience")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Unique Visitors", fmt_int(ga4.get("users")), help=TIPS["users"])
c2.metric("Modules Started", fmt_int(ga4.get("modules_started")), help=TIPS["modules_started"])
c3.metric("Total Subscribers", fmt_int(bh.get("total_subscribers")), help=TIPS["total_subscribers"])
c4.metric("New Subscribers", fmt_int(bh.get("new_subscribers")), help=TIPS["new_subscribers"] + (f" — uses canned period: {bh.get('period_used_for_new_subs')}" if bh.get("period_used_for_new_subs") else ""))


# ---------- Email ----------
st.markdown("### 📧 Email")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Emails Sent", fmt_int(bh.get("emails_sent")), help=TIPS["emails_sent"])
c2.metric("Email Opens", fmt_int(bh.get("email_opens")), help=TIPS["email_opens"])
c3.metric("Email Clicks", fmt_int(bh.get("email_clicks")), help=TIPS["email_clicks"])
c4.metric("# Campaigns", fmt_int(bh.get("campaigns_count")), help=TIPS["campaigns_count"])

c1, c2, c3, c4 = st.columns(4)
c1.metric("Open Rate", fmt_pct(bh.get("open_rate")), help=TIPS["open_rate"])
c2.metric("Click Rate", fmt_pct(bh.get("click_rate")), help=TIPS["click_rate"])
c3.metric("Total Unsubscribes", fmt_int(bh.get("unsubscribes")), help=TIPS["unsubscribes"])
c4.metric("Unsubscribe Rate", fmt_pct(bh.get("unsubscribe_rate")), help=TIPS["unsubscribe_rate"])


# ---------- Paid ----------
st.markdown("### 💰 Paid")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Spent on Ads", fmt_money(ads.get("spend_usd", 0)), help=TIPS["ad_spend"])
c2.metric("Ad Impressions", fmt_int(ads.get("impressions")), help=TIPS["ad_impressions"])
c3.metric("Ad Clicks", fmt_int(ads.get("clicks")), help=TIPS["ad_clicks"])
c4.metric("Ad Conversions", f"{ads.get('conversions', 0):.0f}", help=TIPS["ad_conversions"])


if bh.get("error"):
    st.warning(f"📧 beehiiv: {bh['error']} — email metrics shown as zero until configured.")
if ads.get("error"):
    st.warning(f"💰 Google Ads: {ads['error']}")


# =============================================================================
# Charts
# =============================================================================
st.markdown("---")

# Build a date index for charts that need missing-day filling
date_idx = pd.date_range(start=start, end=end, freq="D").strftime("%Y-%m-%d")


# ---------- Chart 1: Audience curves ----------
st.markdown("### 👥 Audience trend  ·  *Source: GA4*")
st.caption("Unique visitors, Modules Started (Viewed Privacy Policy), Modules Finished (Submitted Email)")
df_aud = pd.DataFrame(date_idx, columns=["date"]).merge(
    pd.DataFrame(ga4_daily) if ga4_daily else pd.DataFrame(columns=["date", "users", "modules_started", "modules_finished"]),
    on="date", how="left",
).fillna(0)
fig_aud = go.Figure()
fig_aud.add_trace(go.Scatter(x=df_aud["date"], y=df_aud["users"], name="Unique visitors", mode="lines", line=dict(color="#4F8BF9", width=2)))
fig_aud.add_trace(go.Scatter(x=df_aud["date"], y=df_aud["modules_started"], name="Modules Started", mode="lines", line=dict(color="#F5A524", width=2)))
fig_aud.add_trace(go.Scatter(x=df_aud["date"], y=df_aud["modules_finished"], name="Modules Finished", mode="lines", line=dict(color="#16A34A", width=2)))
fig_aud.update_layout(height=320, margin=dict(l=0, r=0, t=10, b=0), legend=dict(orientation="h", y=1.1), yaxis_title="Count", xaxis_title=None, hovermode="x unified")
st.plotly_chart(fig_aud, use_container_width=True)


# ---------- Chart 2: Revenue split curves ----------
st.markdown("### 💵 Revenue trend  ·  *Source: Stripe*")
st.caption("Total revenue, Subscription revenue (charges with invoice), Non-subscription revenue (one-time charges)")
rev_df = pd.DataFrame(stripe.get("daily_split", []))
if not rev_df.empty:
    fig_rev = go.Figure()
    fig_rev.add_trace(go.Scatter(x=rev_df["date"], y=rev_df["total"], name="Total revenue", mode="lines", line=dict(color="#16A34A", width=2.5)))
    fig_rev.add_trace(go.Scatter(x=rev_df["date"], y=rev_df["subscription"], name="Subscription", mode="lines", line=dict(color="#4F8BF9", width=2)))
    fig_rev.add_trace(go.Scatter(x=rev_df["date"], y=rev_df["non_subscription"], name="Non-subscription", mode="lines", line=dict(color="#F5A524", width=2)))
    fig_rev.update_layout(height=320, margin=dict(l=0, r=0, t=10, b=0), legend=dict(orientation="h", y=1.1), yaxis_title="USD", xaxis_title=None, hovermode="x unified")
    st.plotly_chart(fig_rev, use_container_width=True)
else:
    st.info("No revenue data in window.")


# ---------- Chart 3: Email rates ----------
st.markdown("### 📧 Email rates trend  ·  *Source: beehiiv*")
st.caption("Open rate, Click rate, Unsubscribe rate (each day = aggregated across posts sent that day)")
if bh_daily:
    rates_df = pd.DataFrame(bh_daily)
    fig_rates = go.Figure()
    fig_rates.add_trace(go.Scatter(x=rates_df["date"], y=rates_df["open_rate"] * 100, name="Open rate", mode="lines+markers", line=dict(color="#4F8BF9", width=2)))
    fig_rates.add_trace(go.Scatter(x=rates_df["date"], y=rates_df["click_rate"] * 100, name="Click rate", mode="lines+markers", line=dict(color="#F5A524", width=2)))
    fig_rates.add_trace(go.Scatter(x=rates_df["date"], y=rates_df["unsubscribe_rate"] * 100, name="Unsubscribe rate", mode="lines+markers", line=dict(color="#DC2626", width=2)))
    fig_rates.update_layout(height=320, margin=dict(l=0, r=0, t=10, b=0), legend=dict(orientation="h", y=1.1), yaxis_title="Rate (%)", xaxis_title=None, hovermode="x unified")
    st.plotly_chart(fig_rates, use_container_width=True)
else:
    st.info("No email rate data in window (no posts sent or beehiiv API key missing).")


# ---------- Chart 4: Ads multi-metric ----------
st.markdown("### 💰 Paid trend  ·  *Source: Google Ads*")
st.caption("Spend (left axis, $) — Impressions, Clicks, Conversions (right axis, count)")
ads_df = pd.DataFrame(date_idx, columns=["date"]).merge(
    pd.DataFrame(ads.get("daily", [])),
    on="date", how="left",
).fillna(0)
fig_ads = go.Figure()
fig_ads.add_trace(go.Scatter(x=ads_df["date"], y=ads_df["spend"], name="Spend ($)", mode="lines", line=dict(color="#DC2626", width=2.5), yaxis="y1"))
fig_ads.add_trace(go.Scatter(x=ads_df["date"], y=ads_df["impressions"], name="Impressions", mode="lines", line=dict(color="#4F8BF9", width=2), yaxis="y2"))
fig_ads.add_trace(go.Scatter(x=ads_df["date"], y=ads_df["clicks"], name="Clicks", mode="lines", line=dict(color="#F5A524", width=2), yaxis="y2"))
fig_ads.add_trace(go.Scatter(x=ads_df["date"], y=ads_df["conversions"], name="Conversions", mode="lines", line=dict(color="#16A34A", width=2), yaxis="y2"))
fig_ads.update_layout(
    height=340,
    margin=dict(l=0, r=0, t=10, b=0),
    legend=dict(orientation="h", y=1.12),
    xaxis_title=None,
    yaxis=dict(title="Spend ($)", side="left"),
    yaxis2=dict(title="Impressions / Clicks / Conversions", overlaying="y", side="right"),
    hovermode="x unified",
)
st.plotly_chart(fig_ads, use_container_width=True)


# ---------- Chart 5: MRR + total subscribers ----------
st.markdown("### 📈 MRR & Total subscribers  ·  *Sources: Stripe + beehiiv*")
st.caption("MRR computed from Stripe subscription history. Total subscribers shown as current beehiiv value (historical not exposed by beehiiv API).")
if mrr_history:
    mrr_df = pd.DataFrame(mrr_history)
    total_subs_now = bh.get("total_subscribers", 0) or 0
    fig_mrr = go.Figure()
    fig_mrr.add_trace(go.Scatter(x=mrr_df["date"], y=mrr_df["mrr"], name="MRR ($)", mode="lines", line=dict(color="#16A34A", width=2.5), yaxis="y1"))
    fig_mrr.add_trace(go.Scatter(x=mrr_df["date"], y=[total_subs_now] * len(mrr_df), name="Total Subscribers (current)", mode="lines", line=dict(color="#4F8BF9", width=2, dash="dash"), yaxis="y2"))
    fig_mrr.update_layout(
        height=320,
        margin=dict(l=0, r=0, t=10, b=0),
        legend=dict(orientation="h", y=1.1),
        xaxis_title=None,
        yaxis=dict(title="MRR ($)", side="left"),
        yaxis2=dict(title="Subscribers", overlaying="y", side="right"),
        hovermode="x unified",
    )
    st.plotly_chart(fig_mrr, use_container_width=True)
else:
    st.info("No MRR data available.")


# ---------- Funnel ----------
st.markdown("### 🔻 Tool funnel  ·  *Source: GA4*")
st.caption("Viewed Privacy Policy → Accepted Privacy Policy → Submitted Email")
fig_funnel = go.Figure(go.Funnel(
    y=["Viewed Privacy Policy", "Accepted Privacy Policy", "Submitted Email"],
    x=[
        funnel.get("viewed_privacy", 0),
        funnel.get("accepted_privacy", 0),
        funnel.get("submitted_email", 0),
    ],
    textinfo="value+percent initial",
    marker=dict(color=["#4F8BF9", "#F5A524", "#16A34A"]),
))
fig_funnel.update_layout(height=320, margin=dict(l=0, r=0, t=10, b=0))
st.plotly_chart(fig_funnel, use_container_width=True)


# ---------- Revenue per product ----------
st.markdown("### 💼 Revenue by product  ·  *Source: Stripe*")
st.caption("Sum of paid invoice line items grouped by product over the selected window.")
if rev_by_product:
    rp_df = pd.DataFrame(rev_by_product)
    fig_rp = px.bar(
        rp_df,
        x="revenue",
        y="product",
        orientation="h",
        text=rp_df["revenue"].apply(lambda v: f"${v:,.0f}"),
        color="revenue",
        color_continuous_scale="Greens",
    )
    fig_rp.update_layout(
        height=max(300, 60 * len(rp_df)),
        margin=dict(l=0, r=0, t=10, b=0),
        yaxis=dict(title=None, autorange="reversed"),
        xaxis=dict(title="Revenue ($)"),
        coloraxis_showscale=False,
    )
    st.plotly_chart(fig_rp, use_container_width=True)
else:
    st.info("No invoiced revenue in window. (Non-subscription revenue may not show here — only paid invoices are tracked.)")


# ---------- Footer ----------
st.markdown("---")
st.caption(f"Data sources: GA4 · Stripe · Google Ads · beehiiv · GSC · Sheets · Ahrefs  •  10-min cache  •  All times in UTC unless noted.")
