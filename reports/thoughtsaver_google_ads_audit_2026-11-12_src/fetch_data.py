"""Read-only pull of the Thought Saver Google Ads account (9679377392) for the optimization audit.

Writes data/ads_pull.json (gitignored). Window = the GA4 cohort window (Oct 11 - Nov 10, 2026) unless
overridden, plus a 6-month monthly trend. Nothing in the account is changed.

Usage: .venv/bin/python reports/thoughtsaver_google_ads_audit_2026-11-12_src/fetch_data.py [--start ... --end ...]
"""
import argparse
import datetime as dt
import json
from pathlib import Path

from gads import client, query

HERE = Path(__file__).resolve().parent
MAIN = "20789758929"  # [MAX] User Acq. - Classic, the only campaign spending


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2026-10-11")
    ap.add_argument("--end", default="2026-11-10")
    a = ap.parse_args()
    w = f"segments.date BETWEEN '{a.start}' AND '{a.end}'"
    c = client()
    q = lambda gaql: query(gaql, c)  # noqa: E731
    camp = f"campaign.id = {MAIN}"
    out = {"window": [a.start, a.end], "pulled_at": dt.datetime.now().isoformat(timespec="minutes")}

    out["campaigns"] = q("""SELECT campaign.id, campaign.name, campaign.status, campaign.advertising_channel_type,
        campaign.bidding_strategy_type, campaign.maximize_conversion_value.target_roas, campaign.start_date_time,
        campaign_budget.amount_micros, campaign.primary_status, campaign.primary_status_reasons,
        campaign.geo_target_type_setting.positive_geo_target_type
        FROM campaign WHERE campaign.status != 'REMOVED'""")
    out["conversion_actions"] = q("""SELECT conversion_action.id, conversion_action.name, conversion_action.category,
        conversion_action.type, conversion_action.primary_for_goal, conversion_action.include_in_conversions_metric,
        conversion_action.value_settings.default_value, conversion_action.counting_type,
        conversion_action.click_through_lookback_window_days, conversion_action.attribution_model_settings.attribution_model
        FROM conversion_action WHERE conversion_action.status = 'ENABLED'""")
    out["by_conversion_action"] = q(f"""SELECT campaign.id, segments.conversion_action_name, segments.conversion_action, metrics.conversions,
        metrics.conversions_value, metrics.all_conversions, metrics.all_conversions_value
        FROM campaign WHERE {camp} AND {w}""")
    out["by_conversion_action_by_conv_date"] = q(f"""SELECT campaign.id, segments.conversion_action_name, metrics.conversions_by_conversion_date,
        metrics.conversions_value_by_conversion_date FROM campaign WHERE {camp} AND {w}""")
    out["totals"] = q(f"""SELECT campaign.id, metrics.cost_micros, metrics.impressions, metrics.clicks, metrics.conversions,
        metrics.conversions_value, metrics.search_impression_share, metrics.search_budget_lost_impression_share,
        metrics.search_rank_lost_impression_share FROM campaign WHERE {camp} AND {w}""")
    out["daily"] = q(f"""SELECT campaign.id, segments.date, metrics.cost_micros, metrics.clicks, metrics.conversions, metrics.conversions_value
        FROM campaign WHERE {camp} AND {w}""")
    out["monthly"] = q("""SELECT campaign.name, segments.month, metrics.cost_micros, metrics.impressions, metrics.clicks,
        metrics.conversions, metrics.conversions_value FROM campaign
        WHERE segments.date BETWEEN '2026-05-01' AND '2026-11-11' AND metrics.impressions > 0""")
    out["by_network"] = q(f"""SELECT campaign.id, segments.ad_network_type, metrics.cost_micros, metrics.impressions, metrics.clicks,
        metrics.conversions, metrics.conversions_value FROM campaign WHERE {camp} AND {w}""")
    out["by_device"] = q(f"""SELECT campaign.id, segments.device, metrics.cost_micros, metrics.impressions, metrics.clicks,
        metrics.conversions, metrics.conversions_value FROM campaign WHERE {camp} AND {w}""")
    out["by_country"] = q(f"""SELECT campaign.id, user_location_view.country_criterion_id, user_location_view.targeting_location,
        metrics.cost_micros, metrics.clicks, metrics.conversions, metrics.conversions_value
        FROM user_location_view WHERE {camp} AND {w}""")
    out["geo_targets"] = q(f"""SELECT campaign.id, campaign_criterion.location.geo_target_constant, campaign_criterion.negative,
        campaign_criterion.type FROM campaign_criterion WHERE {camp} AND campaign_criterion.type IN ('LOCATION', 'LANGUAGE')""")
    out["search_terms"] = q(f"""SELECT campaign.id, campaign_search_term_view.search_term, metrics.cost_micros, metrics.impressions,
        metrics.clicks, metrics.conversions, metrics.conversions_value
        FROM campaign_search_term_view WHERE {camp} AND {w}""")
    out["landing_pages"] = q(f"""SELECT campaign.id, expanded_landing_page_view.expanded_final_url, metrics.cost_micros, metrics.clicks,
        metrics.conversions, metrics.conversions_value FROM expanded_landing_page_view WHERE {camp} AND {w}""")
    out["asset_groups"] = q(f"""SELECT campaign.id, asset_group.id, asset_group.name, asset_group.status, asset_group.final_urls,
        asset_group.ad_strength, metrics.cost_micros, metrics.impressions, metrics.clicks, metrics.conversions,
        metrics.conversions_value FROM asset_group WHERE {camp} AND {w}""")
    out["asset_group_signals"] = q(f"""SELECT campaign.id, asset_group_signal.asset_group, asset_group_signal.audience.audience,
        asset_group_signal.search_theme.text FROM asset_group_signal WHERE {camp}""")
    out["assets"] = q(f"""SELECT campaign.id, asset_group_asset.field_type, asset_group_asset.status, asset.type, asset.text_asset.text,
        asset.name, asset.youtube_video_asset.youtube_video_title FROM asset_group_asset
        WHERE {camp} AND asset_group_asset.status != 'REMOVED'""")
    out["negatives"] = q(f"""SELECT campaign.id, campaign_criterion.keyword.text, campaign_criterion.keyword.match_type, campaign_criterion.negative
        FROM campaign_criterion WHERE {camp} AND campaign_criterion.type = 'KEYWORD'""")
    last30 = (dt.date.today() - dt.timedelta(days=29)).isoformat()  # change_event allows at most 30 days back from today
    out["changes"] = q(f"""SELECT change_event.change_date_time, change_event.change_resource_type, change_event.resource_change_operation,
        change_event.changed_fields, change_event.user_email, change_event.campaign
        FROM change_event WHERE change_event.change_date_time BETWEEN '{last30}' AND '{a.end} 23:59:59'
        ORDER BY change_event.change_date_time DESC LIMIT 200""")
    (HERE / "data").mkdir(exist_ok=True)
    (HERE / "data" / "ads_pull.json").write_text(json.dumps(out, indent=1))
    print({k: len(v) if isinstance(v, list) else v for k, v in out.items()})


if __name__ == "__main__":
    main()
