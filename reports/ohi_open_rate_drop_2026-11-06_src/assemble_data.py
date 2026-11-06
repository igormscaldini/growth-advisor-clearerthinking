"""Merge the raw pulls into data.json (the only input of analysis.py).

    python assemble_data.py RAW_DIR

RAW_DIR must hold:
  posts_raw.json              beehiiv v2 API, GET /publications/{pub}/posts?expand[]=stats&status=confirmed (all pages)
  segments.json               beehiiv v2 API, GET /publications/{pub}/segments (all pages)
  isp/batch_*_output.json     per-provider rows from the beehiiv MCP connector tool get_post_isp_breakdown
                              (not in the v2 API): [{"date", "post_id", "domains": {"gmail.com": {sent, delivered, opens, clicks}, ...}}]
  html_sizes.json             {post_id: {"html_bytes": ...}} from GET /posts/{id}?expand[]=free_email_content
  ga4_email_open_hourly.json  {ISO hour (US Eastern): eventCount} for the GA4 event email_open (Igor's own pixel)

Raw pulls stay out of the repo; data.json holds aggregate send statistics only (no subscriber data).
"""
from __future__ import annotations

import glob
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
ET = ZoneInfo("America/New_York")
PROVIDERS = ["gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "icloud.com", "aol.com"]


def is_ohi(p: dict) -> bool:
    return "helpful idea" in ((p.get("title") or "") + " " + (p.get("subject_line") or "")).lower()


def main(raw: Path) -> None:
    posts = sorted(json.load(open(raw / "posts_raw.json")), key=lambda p: p["publish_date"])
    seg_name = {s["id"].replace("seg_", ""): s["name"].strip() for s in json.load(open(raw / "segments.json"))}
    isp = {}
    for f in sorted(glob.glob(str(raw / "isp" / "batch_*_output.json"))):
        for r in json.load(open(f)):
            isp[r["post_id"]] = {k: r["domains"][k] for k in PROVIDERS}
    sizes = json.load(open(raw / "html_sizes.json"))
    hourly = {datetime.fromisoformat(k): v for k, v in json.load(open(raw / "ga4_email_open_hourly.json")).items()}

    sends, all_sends = [], []
    for p in posts:
        e = (p.get("stats") or {}).get("email") or {}
        if (e.get("delivered") or 0) < 1000:
            continue
        t = datetime.fromtimestamp(p["publish_date"], tz=timezone.utc).astimezone(ET)
        slim = {"post_id": p["id"], "date": f"{t:%Y-%m-%d}", "sent_at_et": t.isoformat(), "kind": "ohi" if is_ohi(p) else "other",
                "title": (p.get("title") or "").strip(), "subject": (p.get("subject_line") or "").strip(),
                "from_domain": "ohi" if "ohi." in (p.get("from_address") or "") else "ct",
                "recipients": e["recipients"], "delivered": e["delivered"], "opens": e["opens"], "unique_opens": e["unique_opens"],
                "unique_verified_clicks": e["unique_verified_clicks"], "unsubscribes": e["unsubscribes"], "spam_reports": e["spam_reports"]}
        all_sends.append(slim)
        if p["id"] not in isp:
            continue
        h0 = t.replace(minute=0, second=0, microsecond=0)
        targets = []
        for tg in p.get("send_targets") or []:
            name = seg_name.get(tg.get("receiver_id") or "", tg.get("receiver_type") or "?")
            targets.append(("" if tg.get("action") == "include" else "minus ") + name)
        sends.append({**slim, "segment": "; ".join(targets), "html_kb": round(sizes[p["id"]]["html_bytes"] / 1024, 1) if p["id"] in sizes else None,
                      "pixel_24h": sum(v for k, v in hourly.items() if h0 <= k < h0 + timedelta(hours=24)),
                      "providers": isp[p["id"]]})
    out = {"pulled": datetime.now(ET).strftime("%Y-%m-%d"), "sends": sends, "all_sends": all_sends}
    json.dump(out, open(HERE / "data.json", "w"), indent=1, ensure_ascii=False)
    print(f"sends with provider rows: {len(sends)} ({sum(s['kind'] == 'ohi' for s in sends)} OHI); all sends >= 1,000 delivered: {len(all_sends)}")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
