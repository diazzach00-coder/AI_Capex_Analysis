"""Fill quarters that Yahoo's feed lacks from SEC XBRL, using the same two cash-flow tags Yahoo reads.
Runs after pull_data.py. Only quarters missing from data/hyperscaler_cashflow.csv are added, each marked source=sec."""
import pandas as pd, numpy as np, json, pathlib, urllib.request, datetime as dt, os, sys

ROOT = pathlib.Path(__file__).parent; D = ROOT / "data"
# SEC's fair-access policy requires a User-Agent with a contact email. Set SEC_CONTACT="Name email@domain" before running.
CONTACT = os.environ.get("SEC_CONTACT")
UA = {"User-Agent": f"ai-money-loop {CONTACT}", "Accept-Encoding": "gzip, deflate"}
# Tags per company. Yahoo's Capital Expenditure for Amazon equals PaymentsToAcquireProductiveAssets to the million (Q1 2026: 44,203),
# and its Operating Cash Flow equals NetCashProvidedByUsedInOperatingActivities (26,032), so these fills carry Yahoo's own definition.
TAGS = {"AMZN": dict(cik="0001018724", ocf="NetCashProvidedByUsedInOperatingActivities", capex="PaymentsToAcquireProductiveAssets")}

def concept(cik, tag):
    url = f"https://data.sec.gov/api/xbrl/companyconcept/CIK{cik}/us-gaap/{tag}.json"
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as r:
        import gzip; raw = r.read(); raw = gzip.decompress(raw) if r.headers.get("Content-Encoding") == "gzip" else raw
    rows = pd.DataFrame(json.loads(raw)["units"]["USD"])
    rows["start"] = pd.to_datetime(rows.start); rows["end"] = pd.to_datetime(rows.end); rows["filed"] = pd.to_datetime(rows.filed)
    return rows

def quarterly(rows):
    """Discrete quarters: three-month facts as filed, plus Q4 = full year minus nine months. Latest filing wins on duplicates."""
    span = (rows.end - rows.start).dt.days
    q = rows[(span > 80) & (span < 100)].sort_values("filed").groupby("end").tail(1).set_index("end").val
    fy = rows[(span > 360) & (span < 370) & (rows.form == "10-K")].sort_values("filed").groupby("end").tail(1).set_index("end").val
    nine = rows[(span > 265) & (span < 280)].sort_values("filed").groupby("end").tail(1).set_index("end").val
    for end, v in fy.items():
        sep = pd.Timestamp(end.year, 9, 30)
        if end not in q.index and sep in nine.index: q.loc[end] = v - nine[sep]
    return q.sort_index()

h = pd.read_csv(D / "hyperscaler_cashflow.csv", parse_dates=["quarter"])
if "source" not in h.columns: h["source"] = "yahoo"
added = []
if not CONTACT:
    print("SEC_CONTACT is not set (SEC requires a name and email in the User-Agent); leaving the Yahoo rows as they are.")
    TAGS = {}
for t, cfg in TAGS.items():
    ocf = quarterly(concept(cfg["cik"], cfg["ocf"])); capex = quarterly(concept(cfg["cik"], cfg["capex"]))
    have = set(h[h.ticker == t].quarter)
    for q in sorted(set(ocf.index) & set(capex.index)):
        if q < pd.Timestamp("2025-01-01") or q in have: continue
        row = dict(ticker=t, quarter=q, capex=capex[q] / 1e9, ocf=ocf[q] / 1e9, fcf=(ocf[q] - capex[q]) / 1e9, source="sec")
        h = pd.concat([h, pd.DataFrame([row])], ignore_index=True); added.append(row)
h = h.sort_values(["ticker", "quarter"]).reset_index(drop=True)
h.to_csv(D / "hyperscaler_cashflow.csv", index=False)
meta = json.load(open(D / "pull_meta.json"))
meta["sec_fill"] = {"pulled_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="minutes"),
                    "rows": [dict(ticker=r["ticker"], quarter=r["quarter"].strftime("%Y-%m-%d"), capex=round(r["capex"], 3), ocf=round(r["ocf"], 3)) for r in added],
                    "tags": {t: [c["ocf"], c["capex"]] for t, c in TAGS.items()}}
json.dump(meta, open(D / "pull_meta.json", "w"), indent=2)
print("sec-filled rows:", len(added))
for r in added: print(f"  {r['ticker']} {r['quarter'].date()}  capex {r['capex']:.1f}  ocf {r['ocf']:.1f}  fcf {r['fcf']:.1f}")
