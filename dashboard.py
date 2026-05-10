"""ClearerThinking Growth Dashboard. Run: streamlit run dashboard.py"""
from secrets_loader import materialize_cloud_secrets

materialize_cloud_secrets()

from datetime import date, datetime, timedelta

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from streamlit_autorefresh import st_autorefresh

from data_layer import (
    beehiiv_daily_new_subscribers,
    beehiiv_daily_rates,
    beehiiv_engaged_readers,
    beehiiv_metrics,
    ga4_audience_metrics,
    ga4_daily_users_and_events,
    stripe_charges_daily_by_amounts,
    stripe_current_mrr,
    stripe_metrics,
    stripe_mrr_history,
)

st.set_page_config(
    page_title="ClearerThinking Growth Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

PASSWORD = "ctteam"


# ---------- Auth ----------
def check_password() -> bool:
    if st.session_state.get("authenticated"):
        return True
    st.title("ClearerThinking Growth Dashboard")
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
COG_AMOUNTS = (3500, 1750)         # $35.00, $17.50
PERSONALITY_AMOUNTS = (900,)        # $9.00

with st.spinner("Loading data..."):
    ga4 = ga4_audience_metrics(start, end)
    ga4_daily = ga4_daily_users_and_events(start, end)
    stripe_m = stripe_metrics(start, end)
    mrr_history = stripe_mrr_history(start, end)
    current_mrr = stripe_current_mrr()
    bh = beehiiv_metrics(start, end)
    bh_daily_rates = beehiiv_daily_rates(start, end)
    new_subs_daily = beehiiv_daily_new_subscribers(start, end)
    engaged = beehiiv_engaged_readers()
    cog_sales = stripe_charges_daily_by_amounts(start, end, COG_AMOUNTS)
    pdf_sales = stripe_charges_daily_by_amounts(start, end, PERSONALITY_AMOUNTS)


# ---------- Helpers ----------
def fmt_money(v: float) -> str:
    return f"${v:,.2f}" if v < 1000 else f"${v:,.0f}"


def fmt_int(v) -> str:
    return f"{int(v or 0):,}"


def fmt_pct(v: float) -> str:
    return f"{(v or 0) * 100:.1f}%"


def line_chart(title: str, df: pd.DataFrame, y_col: str, color: str, y_title: str = "", is_percent: bool = False) -> None:
    """Render a single-line curve chart."""
    if df.empty:
        st.info(f"No data for {title} in this window.")
        return
    fig = go.Figure()
    y_vals = df[y_col] * 100 if is_percent else df[y_col]
    fig.add_trace(go.Scatter(
        x=df["date"],
        y=y_vals,
        mode="lines+markers",
        line=dict(color=color, width=2.5),
        fill="tozeroy",
        fillcolor=f"rgba({','.join(str(int(color.lstrip('#')[i:i+2], 16)) for i in (0, 2, 4))},0.1)",
    ))
    fig.update_layout(
        height=240,
        margin=dict(l=0, r=0, t=10, b=0),
        showlegend=False,
        xaxis_title=None,
        yaxis_title=y_title or ("Rate (%)" if is_percent else "Count"),
        hovermode="x unified",
    )
    st.plotly_chart(fig, use_container_width=True)


def metric_section(label: str, value: str, tooltip: str, df: pd.DataFrame, y_col: str, color: str, is_percent: bool = False, y_title: str = "") -> None:
    """One row: label + KPI + chart underneath."""
    st.markdown(f"### {label}", help=tooltip)
    c_left, c_right = st.columns([1, 4])
    c_left.metric(label="Total in window", value=value, help=tooltip, label_visibility="collapsed")
    c_left.markdown(f"<div style='font-size: 2.4em; font-weight: 700; line-height: 1.1;'>{value}</div>", unsafe_allow_html=True)
    with c_right:
        line_chart(label, df, y_col, color, y_title=y_title, is_percent=is_percent)
    st.markdown("---")


# Build a date index used by some charts that need missing days zero-filled
date_idx = pd.date_range(start=start, end=end, freq="D").strftime("%Y-%m-%d")


# ============================================================================
# 1. Modules Finished — GA4 "Submitted Email"
# ============================================================================
mf_df = pd.DataFrame(date_idx, columns=["date"]).merge(
    pd.DataFrame(ga4_daily) if ga4_daily else pd.DataFrame(columns=["date", "modules_finished"]),
    on="date", how="left",
).fillna(0)
metric_section(
    label="🎯 Modules Finished",
    value=fmt_int(ga4.get("modules_finished")),
    tooltip='GA4 • count of "Submitted Email" event in window. (Note: your spec said "email_submitted" but the actual GA4 event is "Submitted Email" with that exact casing.)',
    df=mf_df,
    y_col="modules_finished",
    color="#16A34A",
    y_title="Submissions / day",
)


# ============================================================================
# 2. New Subscribers — beehiiv
# ============================================================================
ns_df = pd.DataFrame(new_subs_daily.get("daily", []))
metric_section(
    label="📨 New Subscribers",
    value=fmt_int(new_subs_daily.get("total")),
    tooltip="beehiiv • count of subscriptions with `created` timestamp inside window. Pulled from /v2/publications/{id}/subscriptions paginated.",
    df=ns_df,
    y_col="count",
    color="#4F8BF9",
    y_title="New subs / day",
)


# ============================================================================
# 3. Engaged Readers — beehiiv segment "Engaged Reades - Open > 40%"
# ============================================================================
seg_name = engaged.get("segment_name") or "Engaged Reades - Open > 40%"
last_calc = engaged.get("last_calculated", "?")
tooltip_engaged = f'beehiiv • subscriber count from the segment "{seg_name}" (open rate > 40%). beehiiv recalculates segments periodically; last_calculated: {last_calc}.'
st.markdown("### 💚 Engaged Readers", help=tooltip_engaged)
c_left, c_right = st.columns([1, 4])
c_left.markdown(f"<div style='font-size: 2.4em; font-weight: 700; line-height: 1.1;'>{fmt_int(engaged.get('engaged'))}</div>", unsafe_allow_html=True)
c_left.caption(f'segment: "{seg_name}"')
with c_right:
    # Engaged Readers is a snapshot — beehiiv segments are stateful, not historical.
    # Plot a flat line at the current value for visual consistency.
    flat_df = pd.DataFrame({"date": date_idx, "engaged": [engaged.get("engaged", 0)] * len(date_idx)})
    line_chart("Engaged Readers", flat_df, "engaged", "#10B981", y_title="Subs in segment (current)")
if engaged.get("error"):
    st.warning(f"Engaged Readers: {engaged['error']}")
else:
    st.caption(f"⚠️ Curve is flat because beehiiv segments only expose a current count, not a historical time series. Last segment recalculation by beehiiv: {last_calc}.")
st.markdown("---")


# ============================================================================
# 4. Unsubscribe Rate — beehiiv
# ============================================================================
ur_df = pd.DataFrame(bh_daily_rates) if bh_daily_rates else pd.DataFrame(columns=["date", "unsubscribe_rate"])
metric_section(
    label="🚪 Unsubscribe Rate",
    value=fmt_pct(bh.get("unsubscribe_rate")),
    tooltip='beehiiv • total unsubscribes / total recipients in window. (Your spec said "from Stripe" — assuming you meant beehiiv since Stripe doesn\'t track email unsubscribes. If you wanted Stripe paid-subscription cancellation rate, tell me.)',
    df=ur_df,
    y_col="unsubscribe_rate",
    color="#DC2626",
    is_percent=True,
    y_title="Rate (%)",
)


# ============================================================================
# 5. Total Revenue — Stripe gross
# ============================================================================
rev_df = pd.DataFrame(stripe_m.get("daily_split", []))
metric_section(
    label="💵 Total Revenue (Gross)",
    value=fmt_money(stripe_m.get("gross_usd", 0)),
    tooltip="Stripe • gross volume = sum of all successful charge amounts in window (BEFORE refunds, in USD).",
    df=rev_df,
    y_col="total",
    color="#16A34A",
    y_title="Revenue ($)",
)


# ============================================================================
# 6. MRR — Stripe subscription
# ============================================================================
mrr_df = pd.DataFrame(mrr_history) if mrr_history else pd.DataFrame(columns=["date", "mrr"])
metric_section(
    label="📈 MRR",
    value=fmt_money(current_mrr),
    tooltip="Stripe • Monthly Recurring Revenue. Computed by summing the monthly-normalized price × quantity of all currently active subscriptions. Daily curve reconstructs MRR over time from active+canceled subscription history.",
    df=mrr_df,
    y_col="mrr",
    color="#4F8BF9",
    y_title="MRR ($)",
)


# ============================================================================
# 7. Cognitive Assessment Sales — Stripe charges $35 or $17.50
# ============================================================================
cog_df = pd.DataFrame(cog_sales.get("daily", []))
metric_section(
    label="🧠 Cognitive Assessment Sales",
    value=fmt_int(cog_sales.get("total")),
    tooltip="Stripe • count of successful charges with amount = $35.00 or $17.50 in window. (Heuristic: any charge at one of these prices is assumed to be a Cognitive Assessment.)",
    df=cog_df,
    y_col="count",
    color="#F5A524",
    y_title="Sales / day",
)


# ============================================================================
# 8. Personality Test PDF Sales — Stripe charges $9
# ============================================================================
pdf_df = pd.DataFrame(pdf_sales.get("daily", []))
metric_section(
    label="📄 Personality Test PDF Sales",
    value=fmt_int(pdf_sales.get("total")),
    tooltip="Stripe • count of successful charges with amount = $9.00 in window. (Heuristic: any $9 charge is assumed to be the Personality Test PDF.)",
    df=pdf_df,
    y_col="count",
    color="#A855F7",
    y_title="Sales / day",
)


# ---------- Footer ----------
st.caption(f"Sources: GA4 · Stripe · beehiiv  •  10-min cache (1-hour cache for Engaged Readers)  •  All times in UTC.")
