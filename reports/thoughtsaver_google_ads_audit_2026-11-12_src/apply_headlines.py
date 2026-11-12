"""Replace the four most repetitive headlines in the Thought Saver PMax asset group (Igor approved 2026-11-12).

Why: ad strength is POOR and Google's action items ask for 3 more headlines, because all 15 are "Daily Routine"
variants. The new ones come from features the campaign's long headlines already claim (journaling, mood/sleep
tracking, flashcards) and from the searches that convert (diary/journal, planner, habit tracker).

Removes the old links first (15 is the cap), then creates the text assets and links them. Each step is sent with
validate_only first. Log with the removed asset ids (re-link them to undo): headlines_<timestamp>.json.
"""
import datetime as dt
import json
from pathlib import Path

from google.ads.googleads.errors import GoogleAdsException

from gads import CUSTOMER, client, query

HERE = Path(__file__).resolve().parent
CAMPAIGN, ASSET_GROUP = "20789758929", "6483163039"
REMOVE = ["Daily Routine Mastery", "Craft Your Daily Routine", "Tailor Your Daily Routine", "Master Your Daily Routine"]
ADD = ["Online Journal & Habit Tracker", "Daily Planner & Journal App", "Track Mood, Sleep & Habits",
       "Flashcards To Learn Anything"]


def headlines():
    return query(f"""SELECT campaign.id, asset_group_asset.resource_name, asset_group_asset.status, asset.id, asset.text_asset.text
        FROM asset_group_asset WHERE asset_group.id = {ASSET_GROUP} AND asset_group_asset.field_type = 'HEADLINE'
        AND asset_group_asset.status != 'REMOVED'""")


def mutate(fn, ops, validate_only):
    try:
        return fn(request={"customer_id": CUSTOMER, "operations": ops, "validate_only": validate_only}), None
    except GoogleAdsException as e:
        return None, "; ".join(err.message for err in e.failure.errors)


def main():
    assert all(len(h) <= 30 for h in ADD), "headline over 30 characters"
    c = client()
    before = headlines()
    by_text = {r["asset"]["textAsset"]["text"]: r for r in before}
    missing = [t for t in REMOVE if t not in by_text]
    if missing:
        raise SystemExit(f"not found, nothing changed: {missing}")
    aga, asset_svc = c.get_service("AssetGroupAssetService"), c.get_service("AssetService")

    remove_ops = []
    for t in REMOVE:
        op = c.get_type("AssetGroupAssetOperation")
        op.remove = by_text[t]["assetGroupAsset"]["resourceName"]
        remove_ops.append(op)
    create_ops = []
    for t in ADD:
        op = c.get_type("AssetOperation")
        op.create.text_asset.text = t
        create_ops.append(op)

    for name, fn, ops in [("remove links", aga.mutate_asset_group_assets, remove_ops), ("create assets", asset_svc.mutate_assets, create_ops)]:
        _, err = mutate(fn, ops, True)
        if err:
            raise SystemExit(f"validation failed ({name}), nothing changed: {err}")
    print("validated")

    _, err = mutate(aga.mutate_asset_group_assets, remove_ops, False)
    if err:
        raise SystemExit(f"remove failed, nothing changed: {err}")
    resp, err = mutate(asset_svc.mutate_assets, create_ops, False)
    if err:
        raise SystemExit(f"OLD HEADLINES REMOVED but creating new ones failed: {err}. Re-link {REMOVE} from the log.")
    link_ops = []
    for res in resp.results:
        op = c.get_type("AssetGroupAssetOperation")
        op.create.asset = res.resource_name
        op.create.asset_group = c.get_service("AssetGroupService").asset_group_path(CUSTOMER, ASSET_GROUP)
        op.create.field_type = c.enums.AssetFieldTypeEnum.HEADLINE
        link_ops.append(op)
    _, err = mutate(aga.mutate_asset_group_assets, link_ops, False)
    after = headlines()
    stamp = dt.datetime.now().strftime("%Y-%m-%d_%H%M%S")
    (HERE / f"headlines_{stamp}.json").write_text(json.dumps(
        {"removed": [{"text": t, "asset_id": by_text[t]["asset"]["id"]} for t in REMOVE],
         "added": ADD, "new_assets": [r.resource_name for r in resp.results], "link_error": err,
         "before": before, "after": after}, indent=1))
    if err:
        raise SystemExit(f"assets created but linking failed: {err}")
    print("now:", sorted(r["asset"]["textAsset"]["text"] for r in after))


if __name__ == "__main__":
    main()
