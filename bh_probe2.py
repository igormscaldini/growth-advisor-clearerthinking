import os, requests, json
from collections import Counter
from dotenv import load_dotenv
load_dotenv()
KEY = os.getenv("BEEHIIV_API_KEY")
PUB = "pub_d0ed5a5f-0bca-4054-ab2c-73fd51707f71"
H = {"Authorization": f"Bearer {KEY}"}

# Pull one page of 100 with expands; inspect pagination + Tools Tried coverage
params = {"limit": 100, "expand[]": ["stats","custom_fields"], "order_by":"created", "direction":"asc"}
r = requests.get(f"https://api.beehiiv.com/v2/publications/{PUB}/subscriptions", headers=H, params=params)
j = r.json()
print("top-level keys:", list(j.keys()))
print("limit/page fields:", {k:j.get(k) for k in ("limit","page","total_pages","total_results","next_cursor")})
data = j["data"]
print("rows:", len(data))
has_tools = 0
tool_counter = Counter()
field_names = Counter()
for s in data:
    cfs = {cf.get("name"): cf.get("value") for cf in s.get("custom_fields", [])}
    for n in cfs: field_names[n]+=1
    tt = cfs.get("Tools Tried (Pipe-Separated)")
    if tt:
        has_tools += 1
        for t in str(tt).split("|"):
            t=t.strip()
            if t: tool_counter[t]+=1
print("created range:", data[0]["created"], "->", data[-1]["created"])
print("with Tools Tried:", has_tools, "/", len(data))
print("\nmost common custom field names:")
for n,c in field_names.most_common(15): print(f"  {c:>3}  {n}")
print("\nsample tools seen:")
for t,c in tool_counter.most_common(15): print(f"  {c:>3}  {t}")
