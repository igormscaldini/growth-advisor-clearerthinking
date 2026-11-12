"""Tiny GAQL helper for the Thought Saver Google Ads account (9679377392), read-only."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import google_ads_client as G  # noqa: E402
from google.ads.googleads.client import GoogleAdsClient  # noqa: E402
from google.protobuf.json_format import MessageToDict  # noqa: E402

CUSTOMER = "9679377392"


def client():
    cid, sec = G._load_oauth_client_secrets()
    return GoogleAdsClient.load_from_dict({
        "developer_token": G.DEVELOPER_TOKEN, "client_id": cid, "client_secret": sec,
        "refresh_token": G._load_refresh_token(), "login_customer_id": CUSTOMER, "use_proto_plus": True})


def query(gaql, c=None):
    """Rows as plain dicts (camelCase keys, as in the API's JSON)."""
    svc = (c or client()).get_service("GoogleAdsService")
    out = []
    for batch in svc.search_stream(customer_id=CUSTOMER, query=gaql):
        for row in batch.results:
            out.append(MessageToDict(type(row).pb(row)))
    return out


import logging  # noqa: E402
logging.getLogger("google.ads.googleads.client").setLevel(logging.CRITICAL)
_raw_query = query


def query(gaql, c=None):  # noqa: F811
    from google.ads.googleads.errors import GoogleAdsException
    try:
        return _raw_query(gaql, c)
    except GoogleAdsException as e:
        raise SystemExit("GAQL error: " + "; ".join(err.message for err in e.failure.errors)) from None
