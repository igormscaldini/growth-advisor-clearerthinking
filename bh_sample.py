import os, requests, json, time
from collections import Counter, defaultdict
from dotenv import load_dotenv
load_dotenv()
KEY = os.getenv("BEEHIIV_API_KEY")
PUB = "pub_d0ed5a5f-0bca-4054-ab2c-73fd51707f71"
H = {"Authorization": f"Bearer {KEY}"}
URL = f"https://api.beehiiv.com/v2/publications/{PUB}/subscriptions"

native_src = Counter()
cf_utmsrc_cov = 0
cf_tools_cov = 0
total = 0
created_min = None; created_max = None
# source -> [sum_received, sum_unique_opened, sum_unique_clicked, n_subs(received>=3)]
agg = defaultdict(lambda: [0,0,0,0])

def classify(s):
    """Return a source bucket using native utm fields + custom UTM Sources."""
    cfs = {cf.get("name"): (cf.get("value") or "") for cf in s.get("custom_fields", [])}
    blob = " ".join([
        str(s.get("utm_source") or ""), str(s.get("utm_medium") or ""),
        str(s.get("utm_channel") or ""), str(s.get("utm_campaign") or ""),
        str(cfs.get("UTM Sources (Comma-Separated)") or ""),
        str(cfs.get("UTM Campaigns (Comma-Separated)") or ""),
    ]).lower()
    if any(k in blob for k in ["facebook","meta","fb","instagram","ig_"]): return "Meta/Facebook"
    if "google" in blob or "gads" in blob or "pmax" in blob: return "Google"
    return "other/none"

cursor = None
PAGES = 200
for i in range(PAGES):
    params = {"limit":100, "expand[]":["stats","custom_fields"]}
    if cursor: params["cursor"] = cursor
    r = requests.get(URL, headers=H, params=params)
    if r.status_code != 200:
        print("ERR", r.status_code, r.text[:200]); break
    j = r.json()
    for s in j["data"]:
        total += 1
        c = s.get("created")
        if c:
            created_min = c if created_min is None else min(created_min,c)
            created_max = c if created_max is None else max(created_max,c)
        native_src[(s.get("utm_source") or "(none)").lower()] += 1
        cfs = {cf.get("name"): cf.get("value") for cf in s.get("custom_fields", [])}
        if cfs.get("UTM Sources (Comma-Separated)"): cf_utmsrc_cov += 1
        if cfs.get("Tools Tried (Pipe-Separated)"): cf_tools_cov += 1
        bucket = classify(s)
        st = s.get("stats") or {}
        rec = st.get("total_received") or 0
        if rec >= 3:
            agg[bucket][0]+=rec
            agg[bucket][1]+=st.get("total_unique_opened") or 0
            agg[bucket][2]+=st.get("total_unique_clicked") or 0
            agg[bucket][3]+=1
    cursor = j.get("next_cursor")
    if not j.get("has_more"): 
        print("no more after page", i); break

from datetime import datetime, timezone
def fmt(ts): return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d") if ts else "?"
print(f"sampled subs: {total}")
print(f"created span: {fmt(created_min)} -> {fmt(created_max)}")
print(f"UTM Sources custom-field coverage: {cf_utmsrc_cov}/{total} ({cf_utmsrc_cov/total*100:.1f}%)")
print(f"Tools Tried custom-field coverage:  {cf_tools_cov}/{total} ({cf_tools_cov/total*100:.1f}%)")
print("\nnative utm_source top 15:")
for k,c in native_src.most_common(15): print(f"  {c:>5}  {k}")
print("\nOpen/click rate by source bucket (received>=3):")
print(f"{'bucket':<16}{'subs':>7}{'recv':>9}{'opens':>8}{'open%':>8}{'click%':>8}")
for b,(rec,op,cl,n) in agg.items():
    print(f"{b:<16}{n:>7}{rec:>9}{op:>8}{op/rec*100 if rec else 0:>7.1f}%{cl/rec*100 if rec else 0:>7.1f}%")
