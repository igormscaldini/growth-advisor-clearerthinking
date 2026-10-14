import csv, sys, re, json, random, collections, os
csv.field_size_limit(10**9)
src, dst, title = sys.argv[1], sys.argv[2], sys.argv[3]
N_ROWS = 6
random.seed(42)
EMAIL = re.compile(r'[\w.+-]+@[\w-]+\.[\w.-]+')
PHONE = re.compile(r'(\+?\d[\d .()-]{7,}\d)')
URL = re.compile(r'https?://|www\.')
HEXID = re.compile(r'\b[0-9a-f]{8,}\b', re.I)
PII_NAME = re.compile(r'email|mail|name|contact|phone|address|\bip\b|user|token|url|text|comment|feedback|why|describe|explain|note|situation|convenient|clid|utm|referr|input|principle|answer|response|friend|who|city|country|zip|postal|birth|age$|handle|domain|^tev|login|account|first|last|surname|nick|twitter|instagram|facebook|linkedin|link|slug|_id$|^id$', re.I)
IDENT_LIKE = re.compile(r'^(?=.*[A-Za-z])(?=.*\d)[A-Za-z0-9._\-+]{4,}$|[@.]\w{2,}$|\\.(com|net|org|edu|io|co|uk|de|br)\b', re.I)
QUESTION_COL = re.compile(r'\([a-z0-9]{5,8}\)\s*$')
def pii_value(v):
    return bool(EMAIL.search(v) or PHONE.search(v) or URL.search(v) or HEXID.search(v))
with open(src, newline='', encoding='utf-8', errors='replace') as f:
    r = csv.reader(f); header = next(r); rows = []
    for row in r:
        if len(row) == len(header): rows.append(row)
    rows = rows[-3000:]
nrows = len(rows)
def is_num(v): return re.fullmatch(r'-?\d+(\.\d+)?(e[+-]?\d+)?', v, re.I) is not None
DT = re.compile(r'^(\d{4})-(\d{2})-(\d{2})([ T])(\d{2}):(\d{2})(:(\d{2}))?(.*)$')
def rand_dt(suffix, sep, secs):
    m = random.randint(1, 9); d = random.randint(1, 28); h = random.randint(0, 23); mi = random.randint(0, 59); s = random.randint(0, 59)
    return f"2026-{m:02d}-{d:02d}{sep}{h:02d}:{mi:02d}" + (f":{s:02d}" if secs else "") + suffix
def mock_json(obj, depth=0):
    if isinstance(obj, list):
        if not obj: return []
        if all(isinstance(x, str) for x in obj): return [f"Mock item {k+1}" for k in range(min(len(obj), 4))]
        if all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in obj):
            lo, hi = min(obj), max(obj); 
            return [round(random.uniform(lo, hi), 2) if any(isinstance(x, float) for x in obj) else random.randint(int(lo), int(hi)) for _ in range(min(len(obj), 6))]
        return [mock_json(x, depth+1) for x in obj[:3]]
    if isinstance(obj, dict):
        return {k if not pii_value(k) else f"mock_key_{i+1}": mock_json(v, depth+1) for i, (k, v) in enumerate(list(obj.items())[:8])}
    if isinstance(obj, bool): return random.choice([True, False])
    if isinstance(obj, int): return random.randint(0, 10)
    if isinstance(obj, float): return round(random.random(), 3)
    if isinstance(obj, str): return "mock value"
    return obj
specs = []; kinds = collections.Counter(); approved = []
for j, col in enumerate(header):
    vals = [row[j] for row in rows if row[j] != '']; n = len(vals); cnt = collections.Counter(vals); distinct = set(vals)
    fill = n / nrows if nrows else 0
    spec = {"fill": fill, "ok": set()}
    lname = col.strip()
    if n == 0: spec["kind"] = "empty"
    elif lname == "Run": spec["kind"] = "run"
    elif lname == "Program Version": spec["kind"] = "const"; spec["ok"] = {max(cnt, key=cnt.get)}; spec["v"] = spec["ok"]
    elif lname == "User": spec["kind"] = "user"
    elif lname in ("Time Started (UTC)", "Time Finished (UTC)") or all(DT.match(v) for v in vals):
        m = DT.match(vals[0]); spec["kind"] = "dt"; spec["sep"] = m.group(4); spec["secs"] = bool(m.group(7)); spec["suffix"] = m.group(9)
    elif lname == "Position": spec["kind"] = "pos"
    elif all(is_num(v) for v in vals):
        nums = [float(v) for v in vals]; spec["kind"] = "num"; spec["lo"], spec["hi"] = min(nums), max(nums)
        spec["int"] = all(re.fullmatch(r'-?\d+', v) for v in vals)
        spec["dec"] = max((len(v.split('.')[1]) if '.' in v else 0) for v in vals) if not spec["int"] else 0
    elif len(distinct) == 1 and n >= 10 and not pii_value(vals[0]) and len(vals[0]) <= 400 and not PII_NAME.search(lname):
        spec["kind"] = "const"; spec["v"] = {vals[0]}; spec["ok"] = {vals[0]}
    elif len(distinct) == 1 and n >= 10 and len(vals[0]) > 400:
        spec["kind"] = "const"; spec["v"] = {'{"mock_key_1": "mock value (long constant shortened)"}' if vals[0][:1] in '[{' else 'Mock long constant text'}; spec["ok"] = set()
    elif vals[0][:1] in '[{' and sum(v[:1] in '[{' for v in vals) >= 0.9 * n:
        parsed = None
        for v in vals[:50]:
            try: parsed = json.loads(v); break
            except Exception: continue
        spec["kind"] = "json"; spec["proto"] = parsed
    else:
        if QUESTION_COL.search(lname):
            opts = [v for v, c in cnt.items() if c >= 3 and len(v) <= 120 and not pii_value(v) and not IDENT_LIKE.search(v)]
        else:
            opts = [v for v, c in cnt.items() if c >= 5 and len(v) <= 60 and not pii_value(v) and not IDENT_LIKE.search(v) and ' ' in v.strip() or (c >= 5 and len(v) <= 60 and not pii_value(v) and not IDENT_LIKE.search(v) and re.fullmatch(r'[A-Za-z][A-Za-z_\- ]*', v))]
        cover = sum(cnt[v] for v in opts) / n if n else 0
        if opts and not PII_NAME.search(lname) and ((len(opts) <= 20 and cover >= 0.8) or (len(opts) <= 6 and cover >= 0.95)):
            spec["kind"] = "cat"; spec["opts"] = sorted(opts); spec["ok"] = set(opts)
        else:
            spec["kind"] = "text"
            spec["flavor"] = "email" if re.search(r'mail', lname, re.I) else "url" if re.search(r'url|pdf|link', lname, re.I) else "id" if re.search(r'\bid\b|id$|\bref|hash|token', lname, re.I) else "text"
    specs.append(spec); kinds[spec["kind"]] += 1
def gen(j, spec, i):
    k = spec["kind"]
    if k == "empty": return ""
    if k == "run": return str(9000001 + i)
    if header[j] == "Minutes Spent": return str(random.randint(3, 45))
    if header[j] == "Time Started (UTC)": return STARTS[i]
    if header[j] == "Time Finished (UTC)": return FINS[i]
    if k == "const": return next(iter(spec["v"]))
    if k == "user": return f"mockuser{i+1}" if i % 5 == 0 else ""
    if k == "dt": return rand_dt(spec["suffix"], spec["sep"], spec["secs"])
    if k == "pos": return ''.join(random.choice('abcdefghijklmnopqrstuvwxyz0123456789') for _ in range(6))
    if k == "num":
        if spec["int"]: return str(random.randint(int(spec["lo"]), int(spec["hi"])))
        return f"{random.uniform(spec['lo'], spec['hi']):.{max(1, min(spec['dec'], 4))}f}"
    if k == "json": return json.dumps(mock_json(spec["proto"]), ensure_ascii=False) if spec["proto"] is not None else '["Mock item 1","Mock item 2"]'
    if k == "cat": return random.choice(spec["opts"])
    fl = spec["flavor"]
    if fl == "email": return f"mock.user{i+1}@example.com"
    if fl == "url": return f"https://example.com/mock/{i+1}"
    if fl == "id": return f"mockid{i+1:04d}"
    return f"Mock free text {i+1}"
import datetime
STARTS=[]; FINS=[]
for i in range(N_ROWS):
    st = datetime.datetime(2026, random.randint(1,9), random.randint(1,28), random.randint(0,23), random.randint(0,59), random.randint(0,59))
    STARTS.append(st.strftime("%Y-%m-%d %H:%M:%S")); FINS.append((st + datetime.timedelta(minutes=random.randint(3,45))).strftime("%Y-%m-%d %H:%M:%S"))
out = []
for i in range(N_ROWS):
    row = []
    for j, spec in enumerate(specs):
        filled = (i == 0 and spec["kind"] != "empty") or random.random() < spec["fill"]
        row.append(gen(j, spec, i) if filled else "")
    out.append(row)
with open(dst, "w", newline='', encoding='utf-8') as f:
    w = csv.writer(f); w.writerow(header); w.writerows(out)
keep = [j for j, s in enumerate(specs) if s["kind"] != "empty"]
with open(dst.replace(".csv", "_trimmed.csv"), "w", newline='', encoding='utf-8') as f:
    w = csv.writer(f, lineterminator="\n"); w.writerow([header[j] for j in keep]); w.writerows([[r[j] for j in keep] for r in out])
print(f"  trimmed: {len(keep)} columns kept, {os.path.getsize(dst.replace('.csv','_trimmed.csv'))} bytes")
# leak check: no mock cell may equal a real value unless it is an approved option/constant
leaks = 0; pii = 0; leak_cols = []
real_sets = [set(row[j] for row in rows if row[j] != '') for j in range(len(header))]
for row in out:
    for j, v in enumerate(row):
        if v == "": continue
        if specs[j]["kind"] in ("text","json","cat","const","user") and v in real_sets[j] and v not in specs[j]["ok"] and v not in ("[]","{}","true","false"): leaks += 1; leak_cols.append((header[j][:40], specs[j]["kind"], len(v)))
        if (EMAIL.search(v) and "example.com" not in v) or PHONE.search(v) and specs[j]["kind"] not in ("num","dt","run"): pii += 1
print(f"{title}: {len(header)} columns, {N_ROWS} mock rows, {os.path.getsize(dst)} bytes; header {len(','.join(header))} chars; real rows sampled {nrows}")
print("  kinds:", dict(kinds))
print(f"  LEAK CHECK: {leaks} real-value matches outside approved options, {pii} pii-pattern cells"); print("  flagged (col, kind, len):", leak_cols[:8])
