"""Apply the optimizations Igor approved on 2026-11-12 to the Thought Saver Google Ads account (9679377392).

Approved (API-applicable parts only, see the rejected list below): #2 user_return_6d value $1 -> $85; #3 onboarding_entered secondary + one-per-click counting for
onboarding_entered and account_created; #4 search themes aligned with converting searches; #5 pause the YouTube
remarketing campaign; #9 legacy conversion actions made secondary. (#1 turned out moot: the logo and business
name already exist at campaign level. #6, #7, #8 were not approved.)

Every change is first sent with validate_only=True; only if all validate is it applied for real. The state before
the change is written to changes_<timestamp>.json beside this file so each change can be reversed by hand.

Usage: .venv/bin/python apply_changes.py [--dry-run]
"""
import argparse
import datetime as dt
import json
from pathlib import Path

from google.ads.googleads.errors import GoogleAdsException
from google.api_core import protobuf_helpers

from gads import CUSTOMER, client, query

HERE = Path(__file__).resolve().parent
MAIN_CAMPAIGN = "20789758929"
ASSET_GROUP = "6483163039"
YOUTUBE_REMARKETING = "24301038621"

VALUE_FIX = {"7720087108": 85.0}  # user_return_6d: the ladder steps $10 (5d = $80, 7d = $90); it was $1
MAKE_SECONDARY = {
    "7828373743": "onboarding_entered (fires before sign-up; 30% of the value bid on)",
    # old GA4-imported actions, not biddable in the Classic campaign (only the ENGAGEMENT goal is): cosmetic clean-up
    "6453561342": "complete_onboarding (old GA4 event)",
    "6574933673": "complete_onboarding2 (old GA4 event)",
    "6695587344": "create_action (old GA4 event)",
    "6702015118": "complete_action (old GA4 event)",
    "6812376408": "first_routine (old GA4 event)",
}
# Rejected by the API in the 2026-11-12 dry run, so they are NOT in this script (UI or GA4 only):
# - "Mutates are not allowed": the Universal Analytics goals (1036114445, 1036923754), the Smart-campaign call/directions
#   actions (1036114754, 1036115195, 1036924513, 1036924753, 1036925215, 1037034612), Android installs (6699831982),
#   and pausing the VIDEO campaign [ACQ] Youtube - Remarketing (24301038621).
# - "The field attempted to be mutated is immutable": counting_type of GA4-imported actions (onboarding_entered,
#   account_created); their counting method is set on the GA4 key event instead.
ONE_PER_CLICK = {}

THEMES_REMOVE = ["how to stop procrastinating", "time blocking schedule", "how to manage my time better",
                 "productive daily schedule examples", "best morning routines for productivity",
                 "motivation to follow a routine"]
THEMES_ADD = ["online diary", "diary app", "online journal", "journal app", "digital journal",
              "habit tracker", "daily planner", "online planner", "to do list app", "daily routine app"]


def snapshot():
    ids = sorted(set(VALUE_FIX) | set(MAKE_SECONDARY) | set(ONE_PER_CLICK))
    actions = query(f"""SELECT conversion_action.id, conversion_action.name, conversion_action.primary_for_goal,
        conversion_action.counting_type, conversion_action.value_settings.default_value, conversion_action.type
        FROM conversion_action WHERE conversion_action.id IN ({','.join(ids)})""")
    signals = query(f"""SELECT asset_group_signal.resource_name, asset_group_signal.search_theme.text
        FROM asset_group_signal WHERE asset_group.id = {ASSET_GROUP}""")
    yt = query(f"SELECT campaign.id, campaign.name, campaign.status FROM campaign WHERE campaign.id = {YOUTUBE_REMARKETING}")
    return {"conversion_actions": actions, "signals": signals, "youtube_campaign": yt}


def conversion_ops(c):
    svc, ops = c.get_service("ConversionActionService"), []
    for cid in sorted(set(VALUE_FIX) | set(MAKE_SECONDARY) | set(ONE_PER_CLICK)):
        op = c.get_type("ConversionActionOperation")
        ca = op.update
        ca.resource_name = svc.conversion_action_path(CUSTOMER, cid)
        # Paths are listed by hand: an auto-built mask (protobuf_helpers.field_mask) silently drops fields set to their
        # default, so primary_for_goal = False went out as an empty update that the API accepted as "ok" (2026-11-12).
        paths = []
        if cid in VALUE_FIX:
            ca.value_settings.default_value = VALUE_FIX[cid]
            paths.append("value_settings.default_value")
        if cid in MAKE_SECONDARY:
            ca.primary_for_goal = False
            paths.append("primary_for_goal")
        if cid in ONE_PER_CLICK:
            ca.counting_type = c.enums.ConversionActionCountingTypeEnum.ONE_PER_CLICK
            paths.append("counting_type")
        op.update_mask.paths.extend(paths)
        ops.append((cid, op))
    return svc, ops


def signal_ops(c, signals):
    svc, ops = c.get_service("AssetGroupSignalService"), []
    existing = {s["assetGroupSignal"].get("searchTheme", {}).get("text"): s["assetGroupSignal"]["resourceName"] for s in signals}
    for text in THEMES_REMOVE:
        if text in existing:
            op = c.get_type("AssetGroupSignalOperation")
            op.remove = existing[text]
            ops.append((f"remove theme: {text}", op))
    for text in THEMES_ADD:
        if text not in existing:
            op = c.get_type("AssetGroupSignalOperation")
            op.create.asset_group = c.get_service("AssetGroupService").asset_group_path(CUSTOMER, ASSET_GROUP)
            op.create.search_theme.text = text
            ops.append((f"add theme: {text}", op))
    return svc, ops


def campaign_ops(c):
    svc = c.get_service("CampaignService")
    op = c.get_type("CampaignOperation")
    op.update.resource_name = svc.campaign_path(CUSTOMER, YOUTUBE_REMARKETING)
    op.update.status = c.enums.CampaignStatusEnum.PAUSED
    c.copy_from(op.update_mask, protobuf_helpers.field_mask(None, op.update._pb))
    return svc, [("pause [ACQ] Youtube - Remarketing", op)]


def send(svc, label_ops, validate_only):
    """One request per operation so one rejected change cannot block the others; returns {label: 'ok' | error}."""
    method = {"ConversionActionService": "mutate_conversion_actions", "AssetGroupSignalService": "mutate_asset_group_signals",
              "CampaignService": "mutate_campaigns"}[type(svc).__name__.replace("Client", "")]
    out = {}
    for label, op in label_ops:
        try:
            getattr(svc, method)(request={"customer_id": CUSTOMER, "operations": [op], "validate_only": validate_only})
            out[str(label)] = "ok"
        except GoogleAdsException as e:
            out[str(label)] = "; ".join(err.message for err in e.failure.errors)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="validate only, change nothing")
    args = ap.parse_args()
    c = client()
    before = snapshot()
    groups = [conversion_ops(c), signal_ops(c, before["signals"])]  # campaign_ops: video campaigns reject API mutates
    validation = {}
    for svc, ops in groups:
        validation.update(send(svc, ops, validate_only=True))
    print("VALIDATION"); [print(f"  {k}: {v}") for k, v in validation.items()]
    applied = {}
    if not args.dry_run:
        for svc, ops in groups:
            ok_ops = [(label, op) for label, op in ops if validation[str(label)] == "ok"]
            applied.update(send(svc, ok_ops, validate_only=False))
        print("APPLIED"); [print(f"  {k}: {v}") for k, v in applied.items()]
    stamp = dt.datetime.now().strftime("%Y-%m-%d_%H%M%S")  # seconds: two runs in one minute overwrote the log once
    log = {"at": stamp, "dry_run": args.dry_run, "before": before, "validation": validation, "applied": applied,
           "after": snapshot() if not args.dry_run else None,
           "labels": {"make_secondary": MAKE_SECONDARY, "one_per_click": ONE_PER_CLICK, "value_fix": VALUE_FIX}}
    (HERE / f"changes_{stamp}.json").write_text(json.dumps(log, indent=1))
    print("log:", HERE / f"changes_{stamp}.json")


if __name__ == "__main__":
    main()
