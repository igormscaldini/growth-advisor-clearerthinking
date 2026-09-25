"""Per-asset performance table for a Performance Max campaign.

Usage:
    .venv/bin/python google_ads_pmax_assets.py --campaign 23221804730 [--since 2025-03-01] [--json out.json]

Prints every asset in the campaign's asset groups with lifetime (since --since) impressions,
clicks, cost, Submitted Email conversions, Search-only CTR, and the last 30 days, so a creative
audit can be repeated for any PMax campaign. Google Ads API v24 has no asset performance labels,
so verdicts must come from these metrics.

Gotchas learned 2026-09-25: `DURING LAST_90_DAYS` is not a valid literal (use explicit dates);
`change_event` only allows a 30-day window; `asset_group_asset` supports metrics segmented by
`segments.ad_network_type` and `segments.conversion_action_name` but not both in one query.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import warnings
from collections import defaultdict
from datetime import date, timedelta

warnings.filterwarnings("ignore")
logging.disable(logging.CRITICAL)

from google.ads.googleads.v24.enums.types import ad_network_type, asset_field_type, asset_link_status, asset_source

from google_ads_client import CUSTOMER_ID, get_client

FT = asset_field_type.AssetFieldTypeEnum.AssetFieldType
NET = ad_network_type.AdNetworkTypeEnum.AdNetworkType
LS = asset_link_status.AssetLinkStatusEnum.AssetLinkStatus
SRC = asset_source.AssetSourceEnum.AssetSource
EMAIL_ACTION = "Submitted Email"


def _rows(svc, query):
    out = []
    for batch in svc.search_stream(customer_id=CUSTOMER_ID, query=query):
        for r in batch.results:
            out.append(json.loads(type(r).to_json(r, preserving_proto_field_name=True)))
    return out


def _zero():
    return {"impr": 0, "clicks": 0, "cost": 0.0, "conv": 0.0, "emails": 0.0}


def _add(bucket, mm):
    bucket["impr"] += int(mm.get("impressions", 0))
    bucket["clicks"] += int(mm.get("clicks", 0))
    bucket["cost"] += int(mm.get("cost_micros", 0)) / 1e6
    bucket["conv"] += float(mm.get("conversions", 0))


def asset_table(campaign_id: int, since: date, until: date | None = None) -> dict:
    """Return {asset_id: {...}} with lifetime / last-30-day / Search-only buckets."""
    until = until or date.today()
    last30 = until - timedelta(days=29)
    svc = get_client().get_service("GoogleAdsService")
    rows = {}
    for r in _rows(svc, f"""
        SELECT asset_group.id, asset_group.name, asset_group_asset.field_type, asset_group_asset.status,
          asset_group_asset.source, asset.id, asset.name, asset.text_asset.text,
          asset.image_asset.full_size.url, asset.image_asset.full_size.width_pixels,
          asset.image_asset.full_size.height_pixels, asset.youtube_video_asset.youtube_video_id,
          asset.youtube_video_asset.youtube_video_title
        FROM asset_group_asset WHERE campaign.id = {campaign_id}
          AND asset_group.status != 'REMOVED' AND asset_group_asset.status != 'REMOVED'"""):
        a, l = r["asset"], r["asset_group_asset"]
        rows[(r["asset_group"]["id"], a["id"])] = {
            "asset_group": r["asset_group"]["name"], "id": a["id"], "field_type": FT(int(l["field_type"])).name,
            "status": LS(int(l["status"])).name, "source": SRC(int(l.get("source", 0))).name,
            "text": a.get("text_asset", {}).get("text"), "name": a.get("name"),
            "image_url": a.get("image_asset", {}).get("full_size", {}).get("url"),
            "size": (a.get("image_asset", {}).get("full_size", {}).get("width_pixels"),
                     a.get("image_asset", {}).get("full_size", {}).get("height_pixels")),
            "youtube_id": a.get("youtube_video_asset", {}).get("youtube_video_id"),
            "life": _zero(), "life_search": _zero(), "last30": _zero(), "last30_search": _zero(),
        }
    for r in _rows(svc, f"""
        SELECT asset_group.id, asset.id, segments.date, segments.ad_network_type,
          metrics.impressions, metrics.clicks, metrics.cost_micros, metrics.conversions
        FROM asset_group_asset WHERE campaign.id = {campaign_id}
          AND segments.date BETWEEN '{since}' AND '{until}'"""):
        row = rows.get((r["asset_group"]["id"], r["asset"]["id"]))
        if not row:
            continue
        search = NET(int(r["segments"]["ad_network_type"])).name in ("SEARCH", "SEARCH_PARTNERS")
        recent = r["segments"]["date"] >= str(last30)
        _add(row["life"], r["metrics"])
        if search:
            _add(row["life_search"], r["metrics"])
        if recent:
            _add(row["last30"], r["metrics"])
            if search:
                _add(row["last30_search"], r["metrics"])
    for r in _rows(svc, f"""
        SELECT asset_group.id, asset.id, segments.date, segments.conversion_action_name, metrics.conversions
        FROM asset_group_asset WHERE campaign.id = {campaign_id}
          AND segments.date BETWEEN '{since}' AND '{until}'"""):
        row = rows.get((r["asset_group"]["id"], r["asset"]["id"]))
        if not row or EMAIL_ACTION not in r["segments"]["conversion_action_name"]:
            continue
        e = float(r["metrics"].get("conversions", 0))
        row["life"]["emails"] += e
        if r["segments"]["date"] >= str(last30):
            row["last30"]["emails"] += e
    return {f"{g}:{a}": v for (g, a), v in rows.items()}


def _fmt(b):
    ctr = b["clicks"] / b["impr"] * 100 if b["impr"] else 0
    cpe = b["cost"] / b["emails"] if b["emails"] else 0
    return f"impr {b['impr']:>9,} clk {b['clicks']:>6,} ctr {ctr:5.2f}% ${b['cost']:>7.0f} emails {b['emails']:>6.0f} $/em {cpe:5.2f}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--campaign", type=int, required=True)
    ap.add_argument("--since", default=str(date.today() - timedelta(days=365)))
    ap.add_argument("--json", help="write the table to this path")
    args = ap.parse_args()
    table = asset_table(args.campaign, date.fromisoformat(args.since))
    if args.json:
        json.dump(table, open(args.json, "w"), indent=1)
    by_ft = defaultdict(list)
    for row in table.values():
        by_ft[(row["asset_group"], row["field_type"])].append(row)
    for (group, ft), rows in sorted(by_ft.items()):
        print(f"\n== {group} / {ft} ==")
        for row in sorted(rows, key=lambda r: -r["life"]["emails"]):
            label = (row["text"] or row["name"] or row["youtube_id"] or "")[:50]
            s = row["life_search"]
            sctr = f"{s['clicks'] / s['impr'] * 100:4.1f}%" if s["impr"] else "   - "
            print(f"{row['id']} {row['status'][:3]} {row['source'][:3]} {label:50s} | {_fmt(row['life'])} | search ctr {sctr} | 30d: {_fmt(row['last30'])}")


if __name__ == "__main__":
    if not CUSTOMER_ID:
        sys.exit("GOOGLE_ADS_CUSTOMER_ID not set in .env")
    main()
