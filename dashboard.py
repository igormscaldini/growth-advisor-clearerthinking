"""ClearerThinking Growth Dashboard. Run: streamlit run dashboard.py"""
from secrets_loader import materialize_cloud_secrets

materialize_cloud_secrets()

import concurrent.futures
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
    ga4_modules_finished_by_campaign,
    ga4_modules_finished_by_channel,
    google_ads_metrics,
    gsc_keyword_position,
    gsc_keyword_position_daily,
    stripe_revenue_by_category,
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

# Manually-tracked revenue lines for the Monetization Summary table.
# Update both the line items and the date below when revenue is reported.
MANUAL_REVENUE_LAST_UPDATED = "2026-05-15"
MANUAL_REVENUE: dict[str, list[tuple[str, float]]] = {
    "MLA": [("ACE", 2_500.00), ("FarmKind", 2_500.00)],
    "Affiliates": [("Kitted Decks", 2_529.53)],
    "Newsletter Sponsorships": [("80,000 Hours", 4_200.00)],
    "Beehiiv Ad Network": [("Beehiiv", 431.85)],
}

# Compute the prior comparison window: same length, immediately before `start`
period_days = (end - start).days + 1
prior_end = start - timedelta(days=1)
prior_start = prior_end - timedelta(days=period_days - 1)


# Single thread pool runs current + prior period fetches in parallel (~28 tasks).
# Each call hits @st.cache_data, so repeat runs reuse cached values.
def _fetch_period(ex, start_, end_) -> dict:
    """Submit all per-period tasks. Returns dict of futures."""
    return {
        "ga4": ex.submit(ga4_audience_metrics, start_, end_),
        "ga4_daily": ex.submit(ga4_daily_users_and_events, start_, end_),
        "stripe_m": ex.submit(stripe_metrics, start_, end_),
        "mrr_history": ex.submit(stripe_mrr_history, start_, end_),
        "bh": ex.submit(beehiiv_metrics, start_, end_),
        "bh_daily_rates": ex.submit(beehiiv_daily_rates, start_, end_),
        "new_subs_daily": ex.submit(beehiiv_daily_new_subscribers, start_, end_),
        "cog_sales": ex.submit(stripe_charges_daily_by_amounts, start_, end_, COG_AMOUNTS, False),
        "pdf_sales": ex.submit(stripe_charges_daily_by_amounts, start_, end_, PERSONALITY_AMOUNTS, True),
        "ads": ex.submit(google_ads_metrics, start_, end_),
        "modules_by_channel": ex.submit(ga4_modules_finished_by_channel, start_, end_),
        "modules_by_campaign": ex.submit(ga4_modules_finished_by_campaign, start_, end_),
        "kw_pos": ex.submit(gsc_keyword_position_daily, "personality test", start_, end_),
        "revenue_cat": ex.submit(stripe_revenue_by_category, start_, end_),
    }


with st.spinner("Loading data (current + prior period in parallel)..."):
    _t0 = datetime.now()
    with concurrent.futures.ThreadPoolExecutor(max_workers=24) as ex:
        # Period-independent fetches once
        f_current_mrr = ex.submit(stripe_current_mrr)
        f_active_subs = ex.submit(stripe_active_subscriber_count)
        f_engaged = ex.submit(beehiiv_engaged_readers)
        f_keyword = ex.submit(gsc_keyword_position, "personality test")
        # Per-period fetches
        f_curr = _fetch_period(ex, start, end)
        f_prior = _fetch_period(ex, prior_start, prior_end)
        cur = {k: f.result() for k, f in f_curr.items()}
        pri = {k: f.result() for k, f in f_prior.items()}
        current_mrr = f_current_mrr.result()
        active_subs = f_active_subs.result()
        engaged = f_engaged.result()
        keyword_pos = f_keyword.result()
    _elapsed = (datetime.now() - _t0).total_seconds()

ga4 = cur["ga4"]
ga4_daily = cur["ga4_daily"]
stripe_m = cur["stripe_m"]
mrr_history = cur["mrr_history"]
bh = cur["bh"]
bh_daily_rates = cur["bh_daily_rates"]
new_subs_daily = cur["new_subs_daily"]
cog_sales = cur["cog_sales"]
pdf_sales = cur["pdf_sales"]
ads = cur["ads"]
modules_by_channel = cur["modules_by_channel"]
modules_by_campaign = cur["modules_by_campaign"]
kw_pos = cur["kw_pos"]
revenue_cat = cur["revenue_cat"]

st.sidebar.caption(f"⏱ Last fetch: {_elapsed:.1f}s")
st.sidebar.caption(f"Comparing vs prior {period_days}d ({prior_start} → {prior_end})")


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


def variance(curr, prev) -> float | None:
    """Return % change. None if prior is missing/zero."""
    if prev is None or curr is None:
        return None
    try:
        prev_f = float(prev)
        curr_f = float(curr)
    except (TypeError, ValueError):
        return None
    if prev_f == 0:
        return None
    return ((curr_f - prev_f) / prev_f) * 100


def metric_section(
    label: str, value: str, tooltip: str, df: pd.DataFrame, y_col: str, color: str,
    *, delta_pct: float | None = None, delta_inverse: bool = False,
    is_percent: bool = False, y_title: str = "",
) -> None:
    st.markdown(f"### {label}", help=tooltip)
    c_left, c_right = st.columns([1, 4])
    c_left.markdown(
        f"<div style='font-size: 2.4em; font-weight: 700; line-height: 1.1;'>{value}</div>",
        unsafe_allow_html=True,
    )
    if delta_pct is not None:
        sign = "▲" if delta_pct >= 0 else "▼"
        is_good = (delta_pct >= 0) ^ delta_inverse  # invert when "more = bad" (e.g., unsub rate)
        col = "#16A34A" if is_good else "#DC2626"
        c_left.markdown(
            f"<div style='color:{col}; font-size:0.95em; margin-top:0.25em;'>{sign} {abs(delta_pct):.1f}% vs prior {period_days}d</div>",
            unsafe_allow_html=True,
        )
    elif delta_pct is None:
        c_left.markdown(
            "<div style='color:#888; font-size:0.85em; margin-top:0.25em;'>(no comparison available)</div>",
            unsafe_allow_html=True,
        )
    with c_right:
        line_chart(label, df, y_col, color, y_title=y_title, is_percent=is_percent)
    st.markdown("---")


date_idx = pd.date_range(start=start, end=end, freq="D").strftime("%Y-%m-%d")


# ============================================================================
# Tabs
# ============================================================================
tab_overview, tab_channels, tab_monetization = st.tabs([
    "📊 Overview",
    "🎯 Modules by Channel",
    "💰 Monetization Breakdown",
])


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
        delta_pct=variance(ga4.get("modules_finished"), pri["ga4"].get("modules_finished")),
    )

    # 2. New Subscribers
    ns_df = pd.DataFrame(new_subs_daily.get("daily", []))
    capped_note = " (capped at 10K — beehiiv's pagination cap; actual may be higher)" if new_subs_daily.get("capped") else ""
    metric_section(
        label="📨 New Subscribers",
        value=fmt_int(new_subs_daily.get("total")) + ("+" if new_subs_daily.get("capped") else ""),
        tooltip=f"beehiiv • subscriptions with `created` timestamp in window, deduped by id. Paginated until subs go below window or beehiiv's pagination cap.{capped_note}",
        df=ns_df, y_col="count", color="#4F8BF9", y_title="New subs / day",
        delta_pct=variance(new_subs_daily.get("total"), pri["new_subs_daily"].get("total")),
    )

    # 3. Engaged Readers (snapshot — no variance)
    seg_name = engaged.get("segment_name") or "Engaged Reades - Open > 40%"
    last_calc = engaged.get("last_calculated", "?")
    tooltip_engaged = f'beehiiv • subscriber count from segment "{seg_name}" (open rate > 40%). Last recalculated by beehiiv: {last_calc}.'
    st.markdown("### 💚 Engaged Readers", help=tooltip_engaged)
    c_left, c_right = st.columns([1, 4])
    c_left.markdown(f"<div style='font-size: 2.4em; font-weight: 700; line-height: 1.1;'>{fmt_int(engaged.get('engaged'))}</div>", unsafe_allow_html=True)
    c_left.markdown("<div style='color:#888; font-size:0.85em; margin-top:0.25em;'>(snapshot — no historical comparison)</div>", unsafe_allow_html=True)
    c_left.caption(f'segment: "{seg_name}"')
    with c_right:
        flat_df = pd.DataFrame({"date": date_idx, "engaged": [engaged.get("engaged", 0)] * len(date_idx)})
        line_chart("Engaged Readers", flat_df, "engaged", "#10B981", y_title="Subs in segment (current)")
    if engaged.get("error"):
        st.warning(f"Engaged Readers: {engaged['error']}")
    else:
        st.caption("⚠️ Curve is flat — beehiiv segments only expose a current count, not a historical time series.")
    st.markdown("---")

    # 4. Unsubscribe Rate (delta_inverse: increase is bad)
    ur_df = pd.DataFrame(bh_daily_rates) if bh_daily_rates else pd.DataFrame(columns=["date", "unsubscribe_rate"])
    metric_section(
        label="🚪 Unsubscribe Rate",
        value=fmt_pct(bh.get("unsubscribe_rate")),
        tooltip="beehiiv • total unsubscribes / total recipients in window.",
        df=ur_df, y_col="unsubscribe_rate", color="#DC2626", is_percent=True, y_title="Rate (%)",
        delta_pct=variance(bh.get("unsubscribe_rate"), pri["bh"].get("unsubscribe_rate")),
        delta_inverse=True,
    )

    # 5. Total Revenue
    rev_df = pd.DataFrame(stripe_m.get("daily_split", []))
    metric_section(
        label="💵 Total Revenue (Gross)",
        value=fmt_money(stripe_m.get("gross_usd", 0)),
        tooltip="Stripe • gross volume = sum of all successful charge amounts (pre-refund) in window.",
        df=rev_df, y_col="total", color="#16A34A", y_title="Revenue ($)",
        delta_pct=variance(stripe_m.get("gross_usd"), pri["stripe_m"].get("gross_usd")),
    )

    # 6. MRR — compare current snapshot to MRR at end of prior period (from prior period's history)
    mrr_df = pd.DataFrame(mrr_history) if mrr_history else pd.DataFrame(columns=["date", "mrr"])
    prior_mrr_history = pri["mrr_history"]
    prior_mrr_end = prior_mrr_history[-1]["mrr"] if prior_mrr_history else None
    metric_section(
        label="📈 MRR",
        value=fmt_money(current_mrr),
        tooltip="Stripe • Monthly Recurring Revenue. KPI is current snapshot. Curve reconstructs daily MRR from active+canceled subscription history. Δ compares current MRR to MRR at the end of the prior window.",
        df=mrr_df, y_col="mrr", color="#4F8BF9", y_title="MRR ($)",
        delta_pct=variance(current_mrr, prior_mrr_end),
    )

    # 7. Cognitive Assessment Sales
    cog_df = pd.DataFrame(cog_sales.get("daily", []))
    metric_section(
        label="🧠 Cognitive Assessment Sales",
        value=fmt_int(cog_sales.get("total")),
        tooltip="Stripe • count of successful charges with amount $35.00 or $17.50 in window.",
        df=cog_df, y_col="count", color="#F5A524", y_title="Sales / day",
        delta_pct=variance(cog_sales.get("total"), pri["cog_sales"].get("total")),
    )

    # 8. Personality Test PDF Sales
    pdf_df = pd.DataFrame(pdf_sales.get("daily", []))
    metric_section(
        label="📄 Personality Test PDF Sales",
        value=fmt_int(pdf_sales.get("total")),
        tooltip="Stripe • count of successful charges with amount $9.00, EXCLUDING subscription charges. Detection: charges from a subscription invoice or with description starting with 'Subscription' are skipped.",
        df=pdf_df, y_col="count", color="#A855F7", y_title="Sales / day",
        delta_pct=variance(pdf_sales.get("total"), pri["pdf_sales"].get("total")),
    )

    # 9. Spent on Ads (NEW)
    ads_df = pd.DataFrame(date_idx, columns=["date"]).merge(
        pd.DataFrame(ads.get("daily", [])),
        on="date", how="left",
    ).fillna(0)
    metric_section(
        label="💰 Spent on Ads",
        value=fmt_money(ads.get("spend_usd", 0)),
        tooltip="Google Ads • sum of cost_micros / 1M for window. Δ compares spend in current window to prior window.",
        df=ads_df, y_col="spend", color="#DC2626", y_title="Spend ($)",
        delta_pct=variance(ads.get("spend_usd"), pri["ads"].get("spend_usd")),
        delta_inverse=False,  # increased spend is "good" for trend tracking; use inverse if ROAS-focused
    )

    # 10. GSC Ranking — "personality test" (Goal #3 tracker)
    # Gaps are meaningful here (no impressions that day → no position), so do NOT fillna.
    kw_daily_raw = pd.DataFrame(kw_pos.get("daily", []))
    kw_df = pd.DataFrame(date_idx, columns=["date"]).merge(
        kw_daily_raw if not kw_daily_raw.empty else pd.DataFrame(columns=["date", "position"]),
        on="date", how="left",
    )
    kw_avg = kw_pos.get("avg_position")
    prior_kw_avg = pri["kw_pos"].get("avg_position")
    metric_section(
        label='🔍 GSC Ranking — "personality test"',
        value=f"#{kw_avg:.1f}" if kw_avg else "—",
        tooltip=(
            'Search Console • impression-weighted average position for the query "personality test" in window. '
            "Lower is better (#1 = top of page 1). GSC has a 3-day data lag — recent days may be missing. "
            "Tracks Goal #3 from GOALS.md."
        ),
        df=kw_df, y_col="position", color="#8B5CF6", y_title="Avg position (lower = better)",
        delta_pct=variance(kw_avg, prior_kw_avg),
        delta_inverse=True,  # position number going up = ranking got worse
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

        st.markdown("#### Detail by channel")
        st.dataframe(
            ch_df.rename(columns={"count": "Submissions", "channel": "Channel", "%": "% of total"}),
            hide_index=True,
            use_container_width=True,
        )

    # ------------------------------------------------------------------------
    # Campaign breakdown
    # ------------------------------------------------------------------------
    st.markdown("---")
    st.markdown("### 📢 Modules Finished by Campaign  ·  *Source: GA4*")
    st.caption(
        f'Count of `Submitted Email` events grouped by `sessionCampaignName` in {start} → {end}. '
        "Campaign attribution comes from GA4's session-level UTM `utm_campaign` (or auto-tagged Google Ads campaign)."
    )
    if not modules_by_campaign:
        st.info("No campaign-attributed 'Submitted Email' events in this window.")
    else:
        camp_df = pd.DataFrame(modules_by_campaign)
        camp_total = camp_df["count"].sum()
        camp_df["%"] = (camp_df["count"] / camp_total * 100).round(1)
        st.caption(f"Total campaign-attributed submissions: **{camp_total:,}** across **{len(camp_df)}** campaigns")
        st.dataframe(
            camp_df.rename(columns={"campaign": "Campaign", "count": "Submissions", "%": "% of total"}),
            hide_index=True,
            use_container_width=True,
        )


# ============================================================================
# Tab 3: Monetization Breakdown
# ============================================================================
with tab_monetization:
    st.markdown("### 💰 Monetization Breakdown")
    st.caption(
        f"Stripe lines scoped to **{start} → {end}** (controlled by the sidebar date filter). "
        "Manual lines are absolute totals (not window-scoped)."
    )

    rev_subs = revenue_cat.get("subscriptions", 0.0)
    rev_pdf = revenue_cat.get("pdf", 0.0)
    rev_cog = revenue_cat.get("cognitive", 0.0)

    mon_rows = [
        {"Source": "Revenue from Subscriptions", "Detail": "Stripe — invoice-attached charges + descriptions starting with 'Subscription'", "Revenue": rev_subs},
        {"Source": "Revenue from Personality Test PDF", "Detail": "Stripe — $9.00 charges (excl. subscriptions)", "Revenue": rev_pdf},
        {"Source": "Revenue from Cognitive Assessment", "Detail": "Stripe — $35.00 or $17.50 charges (excl. subscriptions)", "Revenue": rev_cog},
    ]
    for label, items in MANUAL_REVENUE.items():
        detail = "; ".join(f"{src}: {fmt_money(amt)}" for src, amt in items)
        mon_rows.append({"Source": label, "Detail": f"Manual — {detail}", "Revenue": sum(a for _, a in items)})
    total_rev = sum(r["Revenue"] for r in mon_rows)
    mon_rows.append({"Source": "Total revenue", "Detail": "", "Revenue": total_rev})

    mon_df = pd.DataFrame(mon_rows)
    mon_df["Revenue"] = mon_df["Revenue"].apply(fmt_money)

    st.dataframe(
        mon_df,
        column_config={
            "Source": st.column_config.TextColumn("Source", width="medium"),
            "Detail": st.column_config.TextColumn("Detail", width="large"),
            "Revenue": st.column_config.TextColumn("Revenue", width="small"),
        },
        hide_index=True,
        use_container_width=True,
    )

    manual_sources = ", ".join(MANUAL_REVENUE.keys())
    st.caption(
        f"📝 Manual values (**{manual_sources}**) last updated by Igor: **{MANUAL_REVENUE_LAST_UPDATED}**. "
        "Update via the `MANUAL_REVENUE` constant near the top of `dashboard.py`."
    )


st.caption("Sources: GA4 · Stripe · beehiiv · Search Console · Google Ads  •  10-min cache  •  All times in UTC.")
