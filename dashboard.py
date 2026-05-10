"""ClearerThinking Growth Dashboard. Run: streamlit run dashboard.py"""
from secrets_loader import materialize_cloud_secrets

materialize_cloud_secrets()

from datetime import date, datetime, timedelta

import pandas as pd
import plotly.express as px
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
    ga4_modules_finished_by_channel,
    gsc_keyword_position,
    stripe_active_subscriber_count,
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
preset = st.sidebar.radio("Date range", ["Last 7 days", "Last 30 days", "Last 90 days", "Custom"], index=1)
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


st.title("📊 ClearerThinking Growth Dashboard")
st.caption(f"**{start}** → **{end}**  •  {(end - start).days + 1} days")


# ---------- Data ----------
COG_AMOUNTS = (3500, 1750)
PERSONALITY_AMOUNTS = (900,)

with st.spinner("Loading data..."):
    ga4 = ga4_audience_metrics(start, end)
    ga4_daily = ga4_daily_users_and_events(start, end)
    stripe_m = stripe_metrics(start, end)
    mrr_history = stripe_mrr_history(start, end)
    current_mrr = stripe_current_mrr()
    active_subs = stripe_active_subscriber_count()
    bh = beehiiv_metrics(start, end)
    bh_daily_rates = beehiiv_daily_rates(start, end)
    new_subs_daily = beehiiv_daily_new_subscribers(start, end)
    engaged = beehiiv_engaged_readers()
    cog_sales = stripe_charges_daily_by_amounts(start, end, COG_AMOUNTS)
    pdf_sales = stripe_charges_daily_by_amounts(start, end, PERSONALITY_AMOUNTS, exclude_subscriptions=True)
    keyword_pos = gsc_keyword_position("personality test")
    modules_by_channel = ga4_modules_finished_by_channel(start, end)


# ---------- Helpers ----------
def fmt_money(v: float) -> str:
    return f"${v:,.2f}" if v < 1000 else f"${v:,.0f}"


def fmt_int(v) -> str:
    return f"{int(v or 0):,}"


def fmt_pct(v: float) -> str:
    return f"{(v or 0) * 100:.1f}%"


def line_chart(title: str, df: pd.DataFrame, y_col: str, color: str, y_title: str = "", is_percent: bool = False) -> None:
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
    st.markdown(f"### {label}", help=tooltip)
    c_left, c_right = st.columns([1, 4])
    c_left.markdown(f"<div style='font-size: 2.4em; font-weight: 700; line-height: 1.1;'>{value}</div>", unsafe_allow_html=True)
    with c_right:
        line_chart(label, df, y_col, color, y_title=y_title, is_percent=is_percent)
    st.markdown("---")


date_idx = pd.date_range(start=start, end=end, freq="D").strftime("%Y-%m-%d")


# ============================================================================
# Tabs
# ============================================================================
tab_overview, tab_channels = st.tabs(["📊 Overview", "🎯 Modules by Channel"])


# ============================================================================
# Tab 1: Overview
# ============================================================================
with tab_overview:
    # 1. Modules Finished
    mf_df = pd.DataFrame(date_idx, columns=["date"]).merge(
        pd.DataFrame(ga4_daily) if ga4_daily else pd.DataFrame(columns=["date", "modules_finished"]),
        on="date", how="left",
    ).fillna(0)
    metric_section(
        label="🎯 Modules Finished",
        value=fmt_int(ga4.get("modules_finished")),
        tooltip='GA4 • count of "Submitted Email" event in window.',
        df=mf_df, y_col="modules_finished", color="#16A34A", y_title="Submissions / day",
    )

    # 2. New Subscribers
    ns_df = pd.DataFrame(new_subs_daily.get("daily", []))
    metric_section(
        label="📨 New Subscribers",
        value=fmt_int(new_subs_daily.get("total")),
        tooltip="beehiiv • count of subscriptions with `created` timestamp inside window. Paginated `created desc` until below window.",
        df=ns_df, y_col="count", color="#4F8BF9", y_title="New subs / day",
    )

    # 3. Engaged Readers
    seg_name = engaged.get("segment_name") or "Engaged Reades - Open > 40%"
    last_calc = engaged.get("last_calculated", "?")
    tooltip_engaged = f'beehiiv • subscriber count from segment "{seg_name}" (open rate > 40%). Last recalculated by beehiiv: {last_calc}.'
    st.markdown("### 💚 Engaged Readers", help=tooltip_engaged)
    c_left, c_right = st.columns([1, 4])
    c_left.markdown(f"<div style='font-size: 2.4em; font-weight: 700; line-height: 1.1;'>{fmt_int(engaged.get('engaged'))}</div>", unsafe_allow_html=True)
    c_left.caption(f'segment: "{seg_name}"')
    with c_right:
        flat_df = pd.DataFrame({"date": date_idx, "engaged": [engaged.get("engaged", 0)] * len(date_idx)})
        line_chart("Engaged Readers", flat_df, "engaged", "#10B981", y_title="Subs in segment (current)")
    if engaged.get("error"):
        st.warning(f"Engaged Readers: {engaged['error']}")
    else:
        st.caption("⚠️ Curve is flat — beehiiv segments only expose a current count, not a historical time series.")
    st.markdown("---")

    # 4. Unsubscribe Rate
    ur_df = pd.DataFrame(bh_daily_rates) if bh_daily_rates else pd.DataFrame(columns=["date", "unsubscribe_rate"])
    metric_section(
        label="🚪 Unsubscribe Rate",
        value=fmt_pct(bh.get("unsubscribe_rate")),
        tooltip="beehiiv • total unsubscribes / total recipients in window.",
        df=ur_df, y_col="unsubscribe_rate", color="#DC2626", is_percent=True, y_title="Rate (%)",
    )

    # 5. Total Revenue
    rev_df = pd.DataFrame(stripe_m.get("daily_split", []))
    metric_section(
        label="💵 Total Revenue (Gross)",
        value=fmt_money(stripe_m.get("gross_usd", 0)),
        tooltip="Stripe • gross volume = sum of all successful charge amounts (pre-refund) in window.",
        df=rev_df, y_col="total", color="#16A34A", y_title="Revenue ($)",
    )

    # 6. MRR
    mrr_df = pd.DataFrame(mrr_history) if mrr_history else pd.DataFrame(columns=["date", "mrr"])
    metric_section(
        label="📈 MRR",
        value=fmt_money(current_mrr),
        tooltip="Stripe • Monthly Recurring Revenue. KPI is current snapshot. Curve reconstructs daily MRR from active+canceled subscription history.",
        df=mrr_df, y_col="mrr", color="#4F8BF9", y_title="MRR ($)",
    )

    # 7. Cognitive Assessment Sales
    cog_df = pd.DataFrame(cog_sales.get("daily", []))
    metric_section(
        label="🧠 Cognitive Assessment Sales",
        value=fmt_int(cog_sales.get("total")),
        tooltip="Stripe • count of successful charges with amount $35.00 or $17.50 in window.",
        df=cog_df, y_col="count", color="#F5A524", y_title="Sales / day",
    )

    # 8. Personality Test PDF Sales
    pdf_df = pd.DataFrame(pdf_sales.get("daily", []))
    metric_section(
        label="📄 Personality Test PDF Sales",
        value=fmt_int(pdf_sales.get("total")),
        tooltip="Stripe • count of successful charges with amount $9.00, EXCLUDING subscription charges. Detection: charges from a subscription invoice or with description starting with 'Subscription' are skipped (a $9 sub tier exists, so without this filter we'd count subscription renewals as PDF sales).",
        df=pdf_df, y_col="count", color="#A855F7", y_title="Sales / day",
    )

    # ------------------------------------------------------------------------
    # Goals table (bottom of Overview)
    # ------------------------------------------------------------------------
    st.markdown("## 🎯 Progress against goals")
    st.caption("Goals defined in [GOALS.md](https://github.com/igormscaldini/growth-advisor-clearerthinking/blob/main/GOALS.md). Update that file to change targets.")

    # Build the rows
    rev_current = stripe_m.get("gross_usd", 0)
    rev_target = 120_000
    rev_pct = (rev_current / rev_target * 100) if rev_target else 0

    subs_current = active_subs
    subs_target = 100
    subs_pct = (subs_current / subs_target * 100) if subs_target else 0

    rank_pos = keyword_pos.get("position")
    rank_target = 1
    if rank_pos and rank_pos > 0:
        rank_pct = min(100, (rank_target / rank_pos) * 100)  # 1/pos: pos=1 → 100%, pos=2 → 50%
        rank_current_str = f"Position {rank_pos:.1f}"
    else:
        rank_pct = 0
        rank_current_str = "(no impressions)"

    engaged_current = engaged.get("engaged", 0)
    engaged_target = 200_000
    engaged_pct = (engaged_current / engaged_target * 100) if engaged_target else 0

    goals_df = pd.DataFrame([
        {
            "Goal": "💵 Gross revenue",
            "Current Result": fmt_money(rev_current),
            "Target": "$120,000",
            "% of Target Achieved": f"{rev_pct:.1f}%",
            "_pct": rev_pct,
        },
        {
            "Goal": "👥 Active Stripe subscribers",
            "Current Result": fmt_int(subs_current),
            "Target": "100",
            "% of Target Achieved": f"{subs_pct:.1f}%",
            "_pct": subs_pct,
        },
        {
            "Goal": '🔍 #1 ranking for "personality test"',
            "Current Result": rank_current_str,
            "Target": "Position #1",
            "% of Target Achieved": f"{rank_pct:.1f}%",
            "_pct": rank_pct,
        },
        {
            "Goal": "💚 Engaged subscribers (>40% open rate)",
            "Current Result": fmt_int(engaged_current),
            "Target": "200,000",
            "% of Target Achieved": f"{engaged_pct:.1f}%",
            "_pct": engaged_pct,
        },
    ])

    # Render with progress bars
    st.dataframe(
        goals_df,
        column_config={
            "Goal": st.column_config.TextColumn("Goal", width="large"),
            "Current Result": st.column_config.TextColumn("Current Result"),
            "Target": st.column_config.TextColumn("Target"),
            "% of Target Achieved": st.column_config.TextColumn("% Achieved"),
            "_pct": st.column_config.ProgressColumn("Progress", min_value=0, max_value=100, format="%.0f%%"),
        },
        hide_index=True,
        use_container_width=True,
    )

    st.caption(
        "ℹ️ Ranking % uses the formula `1 / current_position × 100` (position 1 → 100%, position 2 → 50%, etc.). "
        "Other metrics use `current / target × 100`."
    )


# ============================================================================
# Tab 2: Modules Finished by Channel
# ============================================================================
with tab_channels:
    st.markdown("### 🎯 Modules Finished by Channel  ·  *Source: GA4*")
    st.caption(
        f'Count of `Submitted Email` events grouped by `sessionDefaultChannelGroup` in {start} → {end}. '
        "Channel attribution comes from GA4's default channel grouping — based on the session's source/medium that brought the user in."
    )

    if not modules_by_channel:
        st.info("No 'Submitted Email' events recorded in this window.")
    else:
        ch_df = pd.DataFrame(modules_by_channel)
        total = ch_df["count"].sum()
        ch_df["%"] = (ch_df["count"] / total * 100).round(1)

        c_kpi, c_chart = st.columns([1, 3])
        c_kpi.metric("Total submissions", fmt_int(total), help="Sum across all channels")
        c_kpi.metric("# channels with submissions", str(len(ch_df)))

        with c_chart:
            fig = px.bar(
                ch_df,
                x="count",
                y="channel",
                orientation="h",
                text=ch_df.apply(lambda r: f"{int(r['count']):,} ({r['%']}%)", axis=1),
                color="count",
                color_continuous_scale="Greens",
            )
            fig.update_layout(
                height=max(280, 50 * len(ch_df)),
                margin=dict(l=0, r=0, t=10, b=0),
                yaxis=dict(title=None, autorange="reversed"),
                xaxis=dict(title="Submissions"),
                coloraxis_showscale=False,
            )
            st.plotly_chart(fig, use_container_width=True)

        st.markdown("#### Detail")
        st.dataframe(
            ch_df.rename(columns={"count": "Submissions", "channel": "Channel", "%": "% of total"}),
            hide_index=True,
            use_container_width=True,
        )


st.caption("Sources: GA4 · Stripe · beehiiv · Search Console  •  10-min cache  •  All times in UTC.")
