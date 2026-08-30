import os, requests
from dotenv import load_dotenv
load_dotenv()
KEY = os.getenv("BEEHIIV_API_KEY")
PUB = "pub_d0ed5a5f-0bca-4054-ab2c-73fd51707f71"
H = {"Authorization": f"Bearer {KEY}"}
# publication stats
r = requests.get(f"https://api.beehiiv.com/v2/publications/{PUB}?expand[]=stats", headers=H)
print("pub status", r.status_code)
st = r.json().get("data", {}).get("stats", {})
print("active_subscriptions:", st.get("active_subscriptions"))
# one page of subs with expands
r2 = requests.get(f"https://api.beehiiv.com/v2/publications/{PUB}/subscriptions",
                  headers=H, params={"limit": 3, "expand[]": ["stats","custom_fields"]})
print("subs status", r2.status_code)
j = r2.json()
import json
print("total_results:", j.get("total_results"), "page:", j.get("page"), "total_pages:", j.get("total_pages"))
d0 = j["data"][0]
print("\nsample keys:", list(d0.keys()))
print("stats:", d0.get("stats"))
print("custom_fields sample:")
for cf in d0.get("custom_fields", []):
    print("  ", cf.get("name"), "=", str(cf.get("value"))[:80])
