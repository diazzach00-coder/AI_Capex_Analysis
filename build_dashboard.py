"""Build docs/index.html: a self-contained dashboard that follows the announced AI money from source to fate.
Reads only files the other scripts write (data/*.csv, figures/table_*.csv). No network, no CDN."""
import pandas as pd, numpy as np, json, pathlib, re

ROOT = pathlib.Path(__file__).parent; D = ROOT / "data"; F = ROOT / "figures"; OUT = ROOT / "docs"; OUT.mkdir(exist_ok=True)
META = json.load(open(D / "pull_meta.json"))["pulled_utc"][:10]
NAMES = {"MSFT": "Microsoft", "GOOGL": "Alphabet", "AMZN": "Amazon", "META": "Meta",
         "CRWV": "CoreWeave", "NBIS": "Nebius", "IREN": "IREN", "APLD": "Applied Digital"}
SEGMENT = {"MSFT": "Intelligent Cloud", "GOOGL": "Google Cloud", "AMZN": "AWS", "META": "Advertising"}

# ---------- 1. Deal graph, same filters as money_loop.py ----------
deals = pd.read_csv(D / "deals.csv", dtype=str, keep_default_na=False)
deals["amount_usd_bn"] = pd.to_numeric(deals.amount_usd_bn, errors="coerce")
guidance = deals[deals.type == "capex_guidance"][["from", "amount_usd_bn", "date", "source_url", "quote"]]
g = deals[~deals.type.isin(["capex_guidance", "capex_actual"]) & deals.status.isin(["LOI", "committed", "funded"])].copy()
g = g[(g.to != "")]
drop = ((g["from"] == "Nvidia") & (g["to"] == "OpenAI") & (g.amount_usd_bn == 100)) | g["from"].str.contains(";") | (g["from"] == "SK Group")
g = g[~drop]
ALIAS = {"Amazon (AWS)": "Amazon", "Google Cloud": "Google", "bond investors": "Credit markets", "convertible investors": "Credit markets"}
g["from"] = g["from"].replace(ALIAS); g["to"] = g["to"].replace(ALIAS)
g["amount_usd_bn"] = g.amount_usd_bn.fillna(0.0)

cycles = pd.read_csv(F / "table_cycles.csv")
on_cycle = set()
for c in cycles.cycle:
    nodes = [n.strip() for n in c.split("→")]
    on_cycle.update(zip(nodes, nodes[1:]))

def fate(r):
    if (r["from"], r["to"]) in on_cycle: return "round_trip"
    if r.type == "debt_financing": return "carried_as_debt"
    return "one_way"
g["fate"] = g.apply(fate, axis=1)
FATE_LABEL = {"round_trip": "Round trip (on a closed loop)", "carried_as_debt": "Carried as neocloud debt", "one_way": "One-way, not yet resolved"}
flows = g.groupby(["from", "to", "fate"], as_index=False).amount_usd_bn.sum()
fate_totals = g.groupby("fate").amount_usd_bn.sum().reindex(FATE_LABEL).fillna(0).round(1).to_dict()
loop = pd.read_csv(F / "table_loop_summary.csv", index_col=0).iloc[:, 0]

deal_rows = g[["from", "to", "type", "amount_usd_bn", "date", "status", "fate", "source_url", "quote", "note"]].copy()
deal_rows["amount_usd_bn"] = deal_rows.amount_usd_bn.round(2)

# ---------- 2. Capex vs segment revenue ----------
h = pd.read_csv(D / "hyperscaler_cashflow.csv", parse_dates=["quarter"])
h = h[h.quarter >= "2025-01-01"].dropna(subset=["capex"])
seg = pd.read_csv(D / "segment_revenue.csv", dtype={"value": float}, parse_dates=["quarter_end"]) if (D / "segment_revenue.csv").exists() else pd.DataFrame()
earn = {}
for t in NAMES:
    if t not in SEGMENT: continue
    cap = h[h.ticker == t].set_index("quarter").capex
    rev = seg[(seg.ticker == t) & (seg.metric == "segment_revenue")].set_index("quarter_end").value if len(seg) else pd.Series(dtype=float)
    opi = seg[(seg.ticker == t) & (seg.metric == "segment_operating_income")].set_index("quarter_end").value if len(seg) else pd.Series(dtype=float)
    qs = sorted(q for q in set(cap.index) | set(rev.index) if q >= pd.Timestamp("2025-01-01"))
    earn[t] = dict(name=NAMES[t], segment=SEGMENT[t],
                   quarters=[q.strftime("%Y-%m-%d") for q in qs],
                   capex=[None if q not in cap.index or pd.isna(cap[q]) else round(float(cap[q]), 2) for q in qs],
                   revenue=[None if q not in rev.index else round(float(rev[q]), 2) for q in qs],
                   op_income=[None if q not in opi.index else round(float(opi[q]), 2) for q in qs])
    # Trailing-4Q capex vs the year-over-year change in trailing-4Q segment revenue, both ending at the last quarter
    # where capex and segment revenue are both available. Needs eight quarters of revenue and four of capex.
    common = sorted(set(cap.dropna().index) & set(rev.index))
    if common:
        end = common[-1]; r4 = rev.sort_index().loc[:end]; c4 = cap.sort_index().loc[:end]; o4 = opi.sort_index().loc[:end]
        if len(r4) >= 8 and len(c4) >= 4:
            d_rev = float(r4.iloc[-4:].sum() - r4.iloc[-8:-4].sum()); d_opi = float(o4.iloc[-4:].sum() - o4.iloc[-8:-4].sum()) if len(o4) >= 8 else None
            c_sum = float(c4.iloc[-4:].sum())
            earn[t].update(t4_capex=round(c_sum, 1), t4_delta_rev=round(d_rev, 1), t4_delta_opi=None if d_opi is None else round(d_opi, 1),
                           rev_per_capex=round(d_rev / c_sum, 2) if c_sum else None, window_end=end.strftime("%Y-%m-%d"))
seg_sources = seg[["ticker", "segment", "metric", "quarter_end", "value", "source_url", "quote"]].copy() if len(seg) else pd.DataFrame()
if len(seg_sources): seg_sources["quarter_end"] = seg_sources.quarter_end.dt.strftime("%Y-%m-%d")

# ---------- 3. Neoclouds ----------
neo = pd.read_csv(F / "table_neocloud_coverage.csv")
neo["name"] = neo.ticker.map(NAMES)
neo_at_risk = round(float(neo[neo.op_income < 0].total_debt.sum()), 1)

# ---------- 4. Adoption ----------
use = pd.read_csv(D / "btos_ai_use.csv"); plan = pd.read_csv(D / "btos_ai_plan.csv")

# ---------- 5. Scenario defaults ----------
capex_2026 = round(float(guidance.amount_usd_bn.sum()), 0)
negative_fcf = h[h.fcf < 0][["ticker", "quarter", "fcf"]]

DATA = dict(
    pulled=META, names=NAMES,
    kpi=dict(capex_2026=capex_2026, loop_dollars=float(loop["dollars_on_a_cycle_bn"]), total_dollars=float(loop["total_edge_dollars_bn"]),
             share=float(loop["share_on_cycle"]), neo_at_risk=neo_at_risk, adoption=float(use.pct.iloc[-1]), adoption_date=str(use.ref_end.iloc[-1]),
             n_negative_fcf=int(negative_fcf.ticker.nunique())),
    guidance=guidance.round(1).to_dict("records"),
    flows=flows.round(2).to_dict("records"), fate_totals=fate_totals, fate_label=FATE_LABEL,
    deals=deal_rows.to_dict("records"),
    earn=earn, seg_sources=seg_sources.to_dict("records"),
    neo=neo.round(2).to_dict("records"),
    adoption=dict(dates=list(use.ref_end), use=list(use.pct), plan=list(plan.pct)),
    negative_fcf=[dict(ticker=r.ticker, quarter=r.quarter.strftime("%Y-%m-%d"), fcf=round(float(r.fcf), 1)) for r in negative_fcf.itertuples()],
)

HTML = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>AI money loop dashboard</title>
<style>
:root { color-scheme: light; --surface: #fcfcfb; --page: #f9f9f7; --ink: #0b0b0b; --ink2: #52514e; --muted: #898781; --grid: #e1e0d9; --axis: #c3c2b7;
  --ring: rgba(11,11,11,0.10); --msft: #2a78d6; --googl: #eb6834; --amzn: #1baf7a; --meta: #eda100; --red: #e34948; --gray: #898781;
  --loop: #eb6834; --debt: #6250d6; --oneway: #b4b2a9; --earn: #1baf7a; }
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) { color-scheme: dark; --surface: #1a1a19; --page: #0d0d0d; --ink: #f0efec; --ink2: #c3c2b7;
  --muted: #898781; --grid: #2c2c2a; --axis: #383835; --ring: rgba(255,255,255,0.10); --msft: #3987e5; --googl: #d95926; --amzn: #199e70; --meta: #c98500;
  --red: #e66767; --loop: #d95926; --debt: #9085e9; --oneway: #5f5e5a; --earn: #199e70; } }
:root[data-theme="dark"] { color-scheme: dark; --surface: #1a1a19; --page: #0d0d0d; --ink: #f0efec; --ink2: #c3c2b7; --muted: #898781; --grid: #2c2c2a;
  --axis: #383835; --ring: rgba(255,255,255,0.10); --msft: #3987e5; --googl: #d95926; --amzn: #199e70; --meta: #c98500; --red: #e66767; --loop: #d95926;
  --debt: #9085e9; --oneway: #5f5e5a; --earn: #199e70; }
* { box-sizing: border-box; }
body { margin: 0; background: var(--page); color: var(--ink); font: 15px/1.55 system-ui, -apple-system, "Segoe UI", sans-serif; }
main { max-width: 1100px; margin: 0 auto; padding: 32px 16px 64px; }
h1 { font-size: 28px; font-weight: 600; margin: 0 0 4px; letter-spacing: -0.01em; }
h2 { font-size: 20px; font-weight: 600; margin: 48px 0 4px; }
h3 { font-size: 15px; font-weight: 600; margin: 0 0 8px; }
p { margin: 0 0 12px; color: var(--ink2); max-width: 72ch; }
.sub { color: var(--ink2); font-size: 15px; margin-bottom: 16px; }
.kpis { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 12px; margin: 24px 0 8px; }
.tile { background: var(--surface); border: 1px solid var(--ring); border-radius: 12px; padding: 14px 16px; }
.tile .label { font-size: 13px; color: var(--ink2); }
.tile .value { font-size: 30px; font-weight: 600; line-height: 1.15; margin: 4px 0 2px; }
.tile .delta { font-size: 13px; color: var(--muted); }
.card { background: var(--surface); border: 1px solid var(--ring); border-radius: 12px; padding: 16px; margin: 12px 0; }
.grid2 { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 12px; }
.legend { display: flex; flex-wrap: wrap; gap: 14px; font-size: 13px; color: var(--ink2); margin: 4px 0 8px; }
.legend span::before { content: ""; display: inline-block; width: 14px; height: 10px; border-radius: 2px; margin-right: 6px; vertical-align: -1px; background: var(--c); }
.legend .line::before { height: 2px; vertical-align: 3px; }
svg { display: block; width: 100%; height: auto; font: 12px system-ui, sans-serif; }
svg text { fill: var(--ink2); }
.axis line, .grid line { stroke: var(--grid); stroke-width: 1; }
.base { stroke: var(--axis); stroke-width: 1; }
.tip { position: fixed; pointer-events: none; background: var(--surface); color: var(--ink); border: 1px solid var(--ring); border-radius: 8px;
  padding: 8px 10px; font-size: 13px; box-shadow: 0 4px 16px rgba(0,0,0,0.12); display: none; z-index: 10; max-width: 320px; }
.tip b { font-size: 14px; }
.tip .k { display: inline-block; width: 12px; height: 2px; vertical-align: middle; margin-right: 6px; }
.controls { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px 20px; margin: 12px 0 16px; }
.controls label { display: block; font-size: 13px; color: var(--ink2); }
.controls input[type=range] { width: 100%; accent-color: var(--msft); }
.controls output { font-weight: 600; color: var(--ink); }
.hero { font-size: 52px; font-weight: 600; letter-spacing: -0.02em; line-height: 1.05; margin: 8px 0 2px; }
.hero small { font-size: 16px; font-weight: 400; color: var(--ink2); margin-left: 8px; }
.bars { display: grid; gap: 6px; margin: 12px 0; }
.bar { display: grid; grid-template-columns: 240px 1fr 90px; align-items: center; gap: 10px; font-size: 13px; }
.bar .track { height: 14px; background: var(--grid); border-radius: 4px; overflow: hidden; }
.bar .fill { height: 100%; border-radius: 0 4px 4px 0; }
.bar .v { text-align: right; font-variant-numeric: tabular-nums; }
table { border-collapse: collapse; width: 100%; font-size: 13px; }
th, td { text-align: left; padding: 6px 8px; border-bottom: 1px solid var(--grid); vertical-align: top; }
th { color: var(--ink2); font-weight: 600; }
td.num, th.num { text-align: right; font-variant-numeric: tabular-nums; }
.chips { display: flex; flex-wrap: wrap; gap: 8px; margin: 8px 0 12px; }
.chip { border: 1px solid var(--ring); background: var(--surface); color: var(--ink); border-radius: 999px; padding: 4px 12px; font-size: 13px; cursor: pointer; }
.chip[aria-pressed="true"] { background: var(--ink); color: var(--surface); border-color: var(--ink); }
details { margin: 8px 0; }
summary { cursor: pointer; color: var(--ink2); font-size: 13px; }
a { color: inherit; }
.foot { color: var(--muted); font-size: 12px; margin-top: 40px; }
.note { font-size: 13px; color: var(--muted); }
.theme { float: right; font-size: 13px; background: none; border: 1px solid var(--ring); color: var(--ink2); border-radius: 999px; padding: 4px 12px; cursor: pointer; }
.tbl-wrap { overflow-x: auto; }
@media (max-width: 640px) { .bar { grid-template-columns: 1fr; gap: 2px; } .bar .v { text-align: left; } .hero { font-size: 40px; } }
</style>
</head>
<body>
<main>
<button class="theme" id="theme" type="button">Dark mode</button>
<h1>The AI money loop</h1>
<div class="sub">Who is financing the AI buildout, where the money ends up, and what has to happen for it to come back. Every number traces to a row in <code>data/</code>; hover any mark for its value.</div>

<div class="kpis" id="kpis"></div>
<p class="note" id="kpinote"></p>

<h2>1. Where the announced money goes</h2>
<p>Every announced commitment in <code>data/deals.csv</code> that has a public dollar figure, drawn from the party that pays to the party that receives, then sorted by what happens to it. A dollar is a <em>round trip</em> when its edge sits on a closed loop in the deal graph (a hyperscaler invests in a lab that commits to buy its cloud). It is <em>carried as debt</em> when it is a neocloud bond or convertible. Everything else is <em>one-way</em>: real money, but nothing in the public record yet says whether it earns a return.</p>
<div class="legend"><span style="--c: var(--loop)">Round trip</span><span style="--c: var(--debt)">Carried as neocloud debt</span><span style="--c: var(--oneway)">One-way, not yet resolved</span></div>
<div class="card"><svg id="sankey" viewBox="0 0 1060 560" role="img" aria-labelledby="sk-title"><title id="sk-title">Flow of announced AI commitments from funder to recipient to fate</title></svg></div>
<div class="bars" id="fatebars"></div>
<p class="note">Amounts are announced headline sizes, not cash transferred. Commitments with no public dollar figure (OpenAI's 10 GW Nvidia and 6 GW AMD purchases, Meta's Nvidia order) carry zero weight here, so the round-trip share is a lower bound. Click a fate below to filter the deal table.</p>
<div class="chips" id="fatechips"></div>
<div class="card tbl-wrap"><table id="dealtable"><thead><tr><th>From</th><th>To</th><th>Type</th><th class="num">$bn</th><th>Date</th><th>Status</th><th>Fate</th><th>Source</th></tr></thead><tbody></tbody></table></div>

<h2>2. Is the capex earning anything yet?</h2>
<p>The only place a return can show up is the revenue line of the business the capex was built for. For each hyperscaler: quarterly capital expenditure (bars) against the revenue of its cloud or ad segment (line), both in billions of dollars on one axis. The tile above each panel compares trailing-four-quarter capex with the year-over-year change in trailing-four-quarter segment revenue: dollars of new segment revenue per dollar of capex.</p>
<div class="legend"><span style="--c: var(--ink)" class="line">Segment revenue</span><span style="--c: var(--muted)">Capex (company-wide)</span></div>
<div class="grid2" id="earn"></div>
<p class="note">Capex is company-wide and includes non-AI spend; segment revenue is one segment. Microsoft does not disclose Azure revenue in dollars, so its panel uses the Intelligent Cloud segment. A ratio near or above 1.0 means the segment is adding revenue at the pace of the spend; below it, the spend is running ahead of any visible return. Segment figures are hand-entered from each company's 8-K earnings exhibit; see <code>data/segment_revenue.csv</code>.</p>

<h2>3. Who carries the debt</h2>
<p>Neoclouds borrow to buy the chips the labs rent. Debt plus lease liabilities (Yahoo's "Total Debt" line, which includes operating leases) against annualized revenue and operating income, latest reported quarter.</p>
<div class="card tbl-wrap"><table id="neotable"><thead><tr><th>Company</th><th>Quarter</th><th class="num">Debt plus leases, $bn</th><th class="num">Revenue, $bn/q</th><th class="num">Operating income, $bn/q</th><th class="num">Interest expense, $bn/q</th><th class="num">Debt to annualized revenue</th></tr></thead><tbody></tbody></table></div>
<p class="note">All four have negative operating income in their latest quarter, so none covers its interest from operations. CoreWeave's figure splits into $35.1bn of recourse and non-recourse debt and $16.5bn of lease liabilities per its June 30, 2026 10-Q.</p>

<h2>4. Is anyone paying at the end of the chain?</h2>
<p>Share of US employer firms using AI in the last two weeks, from the Census Bureau's Business Trends and Outlook Survey. Adoption is broad and rising, but it counts firms, not dollars.</p>
<div class="legend"><span style="--c: var(--msft)" class="line">Currently using</span><span style="--c: var(--googl)" class="line">Expect to use within six months</span></div>
<div class="card"><svg id="btos" viewBox="0 0 1060 300" role="img" aria-labelledby="bt-title"><title id="bt-title">AI adoption among US employer firms over time</title></svg></div>

<h2>5. What has to happen</h2>
<p>A stylized break-even. The four hyperscalers guide to a combined annual capex run-rate; that hardware wears out over a useful life and the money behind it needs a return. Dividing by the operating margin earned on the new revenue gives the annual revenue the AI business must add just to stand still. Move the sliders; the hero number is the required new annual revenue, and the bars below set it against what is visible today.</p>
<div class="controls">
  <label>Annual capex run-rate, $bn <output id="o-capex"></output><input type="range" id="s-capex" min="300" max="1200" step="5"></label>
  <label>Useful life of the hardware, years <output id="o-life"></output><input type="range" id="s-life" min="3" max="8" step="0.5" value="5"></label>
  <label>Required pre-tax return on capital <output id="o-ret"></output><input type="range" id="s-ret" min="4" max="20" step="0.5" value="10"></label>
  <label>Operating margin on the new revenue <output id="o-margin"></output><input type="range" id="s-margin" min="10" max="60" step="1" value="30"></label>
  <label>Share of round-trip commitments that becomes outside demand <output id="o-share"></output><input type="range" id="s-share" min="0" max="100" step="5" value="50"></label>
  <label>Years over which announced commitments are spent <output id="o-years"></output><input type="range" id="s-years" min="2" max="10" step="1" value="5"></label>
</div>
<div class="hero" id="hero"></div>
<div class="note" id="heroformula"></div>
<div class="bars" id="scenbars"></div>
<p class="note" id="scennote"></p>

<details><summary>Segment revenue sources</summary><div class="tbl-wrap"><table id="segtable"><thead><tr><th>Company</th><th>Segment</th><th>Metric</th><th>Quarter</th><th class="num">$bn</th><th>Quote</th></tr></thead><tbody></tbody></table></div></details>

<div class="foot" id="foot"></div>
</main>
<div class="tip" id="tip"></div>
<script id="data" type="application/json">__DATA__</script>
<script>
const DATA = JSON.parse(document.getElementById('data').textContent);
const $ = (s, el=document) => el.querySelector(s);
const NS = 'http://www.w3.org/2000/svg';
const el = (tag, attrs={}, parent) => { const n = document.createElementNS(NS, tag); for (const [k,v] of Object.entries(attrs)) n.setAttribute(k, v); if (parent) parent.appendChild(n); return n; };
const txt = (parent, x, y, s, attrs={}) => { const t = el('text', {x, y, ...attrs}, parent); t.textContent = s; return t; };
const fmt = (v, d=0) => v == null ? '—' : '$' + Number(v).toLocaleString('en-US', {maximumFractionDigits: d, minimumFractionDigits: d}) + 'bn';
const COMPANY = {MSFT: 'var(--msft)', GOOGL: 'var(--googl)', AMZN: 'var(--amzn)', META: 'var(--meta)', CRWV: 'var(--msft)', NBIS: 'var(--googl)', IREN: 'var(--amzn)', APLD: 'var(--meta)'};
const FATE = {round_trip: 'var(--loop)', carried_as_debt: 'var(--debt)', one_way: 'var(--oneway)'};
const tip = $('#tip');
function showTip(e, html) { tip.innerHTML = ''; tip.appendChild(html); tip.style.display = 'block'; moveTip(e); }
function moveTip(e) { const w = tip.offsetWidth, h = tip.offsetHeight; tip.style.left = Math.min(e.clientX + 14, innerWidth - w - 8) + 'px'; tip.style.top = Math.min(e.clientY + 14, innerHeight - h - 8) + 'px'; }
function hideTip() { tip.style.display = 'none'; }
function tipRows(title, rows) { const f = document.createDocumentFragment(); const b = document.createElement('b'); b.textContent = title; f.appendChild(b);
  rows.forEach(([k, v, c]) => { const d = document.createElement('div'); if (c) { const s = document.createElement('span'); s.className = 'k'; s.style.background = c; d.appendChild(s); }
    const vv = document.createElement('strong'); vv.textContent = v; d.appendChild(vv); d.appendChild(document.createTextNode(' ' + k)); f.appendChild(d); }); return f; }

// ---------- theme ----------
const root = document.documentElement, tb = $('#theme');
function setTheme(t) { if (t) root.dataset.theme = t; else delete root.dataset.theme; try { localStorage.setItem('theme', t || ''); } catch(e) {}
  const dark = root.dataset.theme === 'dark' || (!root.dataset.theme && matchMedia('(prefers-color-scheme: dark)').matches); tb.textContent = dark ? 'Light mode' : 'Dark mode'; }
try { setTheme(localStorage.getItem('theme') || ''); } catch(e) { setTheme(''); }
tb.onclick = () => setTheme(tb.textContent === 'Dark mode' ? 'dark' : 'light');

// ---------- KPIs ----------
const k = DATA.kpi;
[['2026 capex guidance, four hyperscalers', fmt(k.capex_2026), 'sum of the latest company guidance'],
 ['Announced commitments on a closed loop', fmt(k.loop_dollars), `of ${fmt(k.total_dollars)} with a public figure (${Math.round(k.share*100)}%)`],
 ['Neocloud debt plus leases with negative operating income', fmt(k.neo_at_risk, 1), 'CoreWeave, Nebius, IREN, Applied Digital'],
 ['US firms using AI', k.adoption.toFixed(1) + '%', 'Census BTOS, period ending ' + k.adoption_date],
].forEach(([l, v, d]) => { const t = document.createElement('div'); t.className = 'tile'; const a = document.createElement('div'); a.className = 'label'; a.textContent = l;
  const b = document.createElement('div'); b.className = 'value'; b.textContent = v; const c = document.createElement('div'); c.className = 'delta'; c.textContent = d; t.append(a, b, c); $('#kpis').appendChild(t); });
$('#kpinote').textContent = `${k.n_negative_fcf} of the four hyperscalers printed at least one negative free-cash-flow quarter since 2025: ` +
  DATA.negative_fcf.map(r => `${DATA.names[r.ticker]} ${r.quarter.slice(0,7)} (${fmt(r.fcf, 1)})`).join(', ') + '.';

// ---------- Sankey ----------
(function sankey() {
  const svg = $('#sankey'); const W = 1060, H = 560, PAD = 24, NW = 10, GAP = 10;
  const flows = DATA.flows.filter(f => f.amount_usd_bn > 0);
  const sum = (arr, f) => arr.reduce((a, x) => a + f(x), 0);
  const col = (key) => { const m = {}; flows.forEach(f => { m[f[key]] = (m[f[key]] || 0) + f.amount_usd_bn; }); return Object.entries(m).sort((a, b) => b[1] - a[1]); };
  const cols = [col('from'), col('to'), Object.entries(DATA.fate_totals).filter(([, v]) => v > 0)];
  const total = sum(flows, f => f.amount_usd_bn);
  const MINH = 12;  // a node never thinner than its label, so small recipients stay readable
  let scale = (H - 2 * PAD - GAP * (Math.max(...cols.map(c => c.length)) - 1)) / total;
  const colHeight = c => sum(c, x => Math.max(x[1] * scale, MINH)) + GAP * (c.length - 1);
  while (Math.max(...cols.map(colHeight)) > H - 2 * PAD) scale *= 0.95;
  const X = [PAD + 90, W / 2 - NW / 2, W - PAD - 230];
  const nodes = [{}, {}, {}];
  cols.forEach((c, ci) => { let y = PAD + (H - 2 * PAD - colHeight(c)) / 2;
    c.forEach(([name, v]) => { const h = Math.max(v * scale, MINH); nodes[ci][name] = {x: X[ci], y, h, v, used0: (h - v * scale) / 2, used1: (h - v * scale) / 2}; y += h + GAP; }); });
  const link = (a, b, v, color, title, rows) => {
    const h = v * scale; const y0 = a.y + a.used1; a.used1 += h; const y1 = b.y + b.used0; b.used0 += h;
    const x0 = a.x + NW, x1 = b.x, cx = (x0 + x1) / 2;
    const p = el('path', {d: `M${x0},${y0} C${cx},${y0} ${cx},${y1} ${x1},${y1} L${x1},${y1 + h} C${cx},${y1 + h} ${cx},${y0 + h} ${x0},${y0 + h} Z`, fill: color, opacity: 0.55}, svg);
    p.addEventListener('pointerenter', e => { p.setAttribute('opacity', 0.9); showTip(e, tipRows(title, rows)); }); p.addEventListener('pointermove', moveTip);
    p.addEventListener('pointerleave', () => { p.setAttribute('opacity', 0.55); hideTip(); });
  };
  // links: funder -> recipient (colored by fate), recipient -> fate
  const byRec = {};
  flows.sort((a, b) => b.amount_usd_bn - a.amount_usd_bn).forEach(f => {
    link(nodes[0][f.from], nodes[1][f.to], f.amount_usd_bn, FATE[f.fate], `${f.from} → ${f.to}`, [[DATA.fate_label[f.fate], fmt(f.amount_usd_bn, 1), FATE[f.fate]]]);
    byRec[f.to] = byRec[f.to] || {}; byRec[f.to][f.fate] = (byRec[f.to][f.fate] || 0) + f.amount_usd_bn; });
  Object.entries(byRec).forEach(([to, fates]) => Object.entries(fates).sort((a, b) => b[1] - a[1]).forEach(([fate, v]) =>
    link(nodes[1][to], nodes[2][fate], v, FATE[fate], `${to} → ${DATA.fate_label[fate]}`, [['', fmt(v, 1), FATE[fate]]])));
  nodes.forEach((layer, ci) => Object.entries(layer).forEach(([name, n]) => {
    el('rect', {x: n.x, y: n.y, width: NW, height: n.h, rx: 2, fill: ci === 2 ? FATE[name] : 'var(--ink)'}, svg);
    const label = ci === 2 ? DATA.fate_label[name] : name;
    const t = txt(svg, ci === 0 ? n.x - 6 : n.x + NW + 6, n.y + n.h / 2, `${label}  ${fmt(n.v, 0)}`, {'text-anchor': ci === 0 ? 'end' : 'start', 'dominant-baseline': 'central'});
    if (ci === 2) t.style.fontWeight = '600'; }));
  txt(svg, X[0] - 6, 14, 'Pays', {'text-anchor': 'end', 'font-weight': 600}); txt(svg, X[1] + NW + 6, 14, 'Receives', {'font-weight': 600}); txt(svg, X[2] + NW + 6, 14, 'Fate', {'font-weight': 600});
  // fate bars
  const fb = $('#fatebars'); Object.entries(DATA.fate_totals).forEach(([f, v]) => { const r = document.createElement('div'); r.className = 'bar';
    const a = document.createElement('div'); a.textContent = DATA.fate_label[f]; const t = document.createElement('div'); t.className = 'track'; const fl = document.createElement('div'); fl.className = 'fill';
    fl.style.width = (100 * v / total).toFixed(1) + '%'; fl.style.background = FATE[f]; t.appendChild(fl); const c = document.createElement('div'); c.className = 'v'; c.textContent = `${fmt(v)} · ${Math.round(100 * v / total)}%`; r.append(a, t, c); fb.appendChild(r); });
})();

// ---------- deal table with fate filter ----------
(function dealTable() {
  const tb = $('#dealtable tbody'); const chips = $('#fatechips'); let active = null;
  const draw = () => { tb.innerHTML = ''; DATA.deals.filter(d => !active || d.fate === active).sort((a, b) => b.amount_usd_bn - a.amount_usd_bn).forEach(d => {
    const tr = document.createElement('tr'); [d.from, d.to, d.type.replace(/_/g, ' '), d.amount_usd_bn ? d.amount_usd_bn.toFixed(1) : 'n.q.', d.date, d.status, DATA.fate_label[d.fate]].forEach((v, i) => { const td = document.createElement('td'); if (i === 3) td.className = 'num'; td.textContent = v; tr.appendChild(td); });
    const td = document.createElement('td'); const a = document.createElement('a'); a.href = d.source_url; a.target = '_blank'; a.rel = 'noopener'; a.textContent = 'source'; a.title = d.quote; td.appendChild(a); tr.appendChild(td); tb.appendChild(tr); }); };
  [['All', null], ...Object.entries(DATA.fate_label).map(([key, label]) => [label, key])].forEach(([label, key]) => { const b = document.createElement('button'); b.type = 'button'; b.className = 'chip'; b.textContent = label;
    b.setAttribute('aria-pressed', key === active); b.onclick = () => { active = key; chips.querySelectorAll('.chip').forEach(c => c.setAttribute('aria-pressed', 'false')); b.setAttribute('aria-pressed', 'true'); draw(); }; chips.appendChild(b); });
  draw();
})();

// ---------- capex vs segment revenue ----------
(function earn() {
  const wrap = $('#earn'); const W = 520, H = 260, L = 44, R = 16, T = 20, B = 36;
  const allMax = Math.max(...Object.values(DATA.earn).flatMap(e => [...e.capex, ...e.revenue].filter(v => v != null)));
  Object.entries(DATA.earn).forEach(([t, e]) => {
    const card = document.createElement('div'); card.className = 'card';
    const head = document.createElement('div'); head.className = 'tile'; head.style.border = 'none'; head.style.padding = '0 0 8px';
    const a = document.createElement('div'); a.className = 'label'; a.textContent = `${e.name} · ${e.segment}`;
    const b = document.createElement('div'); b.className = 'value'; b.style.fontSize = '24px'; b.textContent = e.rev_per_capex == null ? 'n/a' : `${e.rev_per_capex.toFixed(2)}×`;
    const c = document.createElement('div'); c.className = 'delta'; c.textContent = e.rev_per_capex == null ? 'needs eight quarters of segment revenue' : `${fmt(e.t4_delta_rev)} new segment revenue per ${fmt(e.t4_capex)} capex, trailing 4Q to ${e.window_end}`;
    head.append(a, b, c); card.appendChild(head);
    const svg = el('svg', {viewBox: `0 0 ${W} ${H}`, role: 'img'}, card); const tt = el('title', {}, svg); tt.textContent = `${e.name}: quarterly capex and ${e.segment} revenue`;
    const n = e.quarters.length, slot = (W - L - R) / n, bw = Math.min(24, slot * 0.5);
    const y = v => T + (H - T - B) * (1 - v / (allMax * 1.08)); const x = i => L + slot * (i + 0.5);
    const g = el('g', {class: 'grid'}, svg); [0, 20, 40, 60].filter(v => v <= allMax * 1.08).forEach(v => { el('line', {x1: L, x2: W - R, y1: y(v), y2: y(v)}, g); txt(svg, L - 6, y(v), v, {'text-anchor': 'end', 'dominant-baseline': 'central'}); });
    el('line', {x1: L, x2: W - R, y1: y(0), y2: y(0), class: 'base'}, svg);
    e.quarters.forEach((q, i) => { const lab = q.slice(2, 4) + 'Q' + Math.ceil(+q.slice(5, 7) / 3); txt(svg, x(i), H - B + 16, lab, {'text-anchor': 'middle'});
      if (e.capex[i] != null) { const r = el('rect', {x: x(i) - bw / 2, y: y(e.capex[i]), width: bw, height: y(0) - y(e.capex[i]), fill: COMPANY[t], opacity: 0.35}, svg);
        const hit = el('rect', {x: x(i) - slot / 2, y: T, width: slot, height: H - T - B, fill: 'transparent'}, svg);
        const rows = [['capex', fmt(e.capex[i], 1), COMPANY[t]]]; if (e.revenue[i] != null) rows.push([`${e.segment} revenue`, fmt(e.revenue[i], 1), 'var(--ink)']); if (e.op_income[i] != null) rows.push([`${e.segment} operating income`, fmt(e.op_income[i], 1)]);
        hit.addEventListener('pointerenter', ev => { r.setAttribute('opacity', 0.6); showTip(ev, tipRows(`${e.name} ${lab}`, rows)); }); hit.addEventListener('pointermove', moveTip); hit.addEventListener('pointerleave', () => { r.setAttribute('opacity', 0.35); hideTip(); }); } });
    const pts = e.quarters.map((q, i) => e.revenue[i] == null ? null : [x(i), y(e.revenue[i])]).filter(Boolean);
    if (pts.length) { el('path', {d: 'M' + pts.map(p => p.join(',')).join(' L'), fill: 'none', stroke: 'var(--ink)', 'stroke-width': 2, 'stroke-linejoin': 'round', 'stroke-linecap': 'round'}, svg);
      pts.forEach(p => el('circle', {cx: p[0], cy: p[1], r: 4, fill: 'var(--ink)', stroke: 'var(--surface)', 'stroke-width': 2}, svg));
      const last = pts[pts.length - 1]; txt(svg, last[0], last[1] - 10, fmt(e.revenue.filter(v => v != null).slice(-1)[0], 1), {'text-anchor': 'middle', 'font-weight': 600}); }
    const lc = e.capex.map((v, i) => v == null ? null : i).filter(v => v != null).slice(-1)[0]; if (lc != null) txt(svg, x(lc), y(e.capex[lc]) - 6, fmt(e.capex[lc], 1), {'text-anchor': 'middle'});
    wrap.appendChild(card); });
})();

// ---------- neocloud table ----------
(function neo() { const tb = $('#neotable tbody'); DATA.neo.forEach(r => { const tr = document.createElement('tr');
  [r.name, r.quarter, r.total_debt.toFixed(1), r.revenue.toFixed(2), r.op_income.toFixed(2), r.interest_expense.toFixed(2), r.debt_to_annualized_rev.toFixed(1) + '×'].forEach((v, i) => { const td = document.createElement('td'); if (i > 1) td.className = 'num'; td.textContent = v; tr.appendChild(td); }); tb.appendChild(tr); }); })();

// ---------- BTOS line ----------
(function btos() {
  const svg = $('#btos'); const W = 1060, H = 300, L = 44, R = 230, T = 16, B = 36; const d = DATA.adoption; const n = d.dates.length;
  const x = i => L + (W - L - R) * i / (n - 1); const ymax = 32; const y = v => T + (H - T - B) * (1 - v / ymax);
  const g = el('g', {class: 'grid'}, svg); [0, 10, 20, 30].forEach(v => { el('line', {x1: L, x2: W - R, y1: y(v), y2: y(v)}, g); txt(svg, L - 6, y(v), v + '%', {'text-anchor': 'end', 'dominant-baseline': 'central'}); });
  d.dates.forEach((dt, i) => { if (i % 4 === 0) txt(svg, x(i), H - B + 16, dt.slice(0, 7), {'text-anchor': 'middle'}); });
  [['use', 'var(--msft)', 'Currently using'], ['plan', 'var(--googl)', 'Expect to use within six months']].forEach(([key, c, label]) => {
    el('path', {d: 'M' + d[key].map((v, i) => `${x(i)},${y(v)}`).join(' L'), fill: 'none', stroke: c, 'stroke-width': 2, 'stroke-linejoin': 'round'}, svg);
    const last = d[key][n - 1]; el('circle', {cx: x(n - 1), cy: y(last), r: 4, fill: c, stroke: 'var(--surface)', 'stroke-width': 2}, svg);
    txt(svg, x(n - 1) + 10, y(last), `${label}: ${last.toFixed(1)}%`, {'dominant-baseline': 'central'}); });
  const cross = el('line', {x1: 0, x2: 0, y1: T, y2: H - B, stroke: 'var(--axis)', 'stroke-width': 1, opacity: 0}, svg);
  const hit = el('rect', {x: L, y: T, width: W - L - R, height: H - T - B, fill: 'transparent'}, svg);
  hit.addEventListener('pointermove', ev => { const r = svg.getBoundingClientRect(); const px = (ev.clientX - r.left) / r.width * W; const i = Math.max(0, Math.min(n - 1, Math.round((px - L) / (W - L - R) * (n - 1))));
    cross.setAttribute('x1', x(i)); cross.setAttribute('x2', x(i)); cross.setAttribute('opacity', 1);
    showTip(ev, tipRows('Period ending ' + d.dates[i], [['currently using', d.use[i].toFixed(1) + '%', 'var(--msft)'], ['expect within six months', d.plan[i].toFixed(1) + '%', 'var(--googl)']])); });
  hit.addEventListener('pointerleave', () => { cross.setAttribute('opacity', 0); hideTip(); });
})();

// ---------- scenario ----------
(function scenario() {
  const s = id => $('#s-' + id), o = id => $('#o-' + id); s('capex').value = DATA.kpi.capex_2026;
  const visible = Object.values(DATA.earn).reduce((a, e) => a + (e.t4_delta_rev || 0), 0);
  const visibleOpi = Object.values(DATA.earn).reduce((a, e) => a + (e.t4_delta_opi || 0), 0);
  const windowEnd = Object.values(DATA.earn).map(e => e.window_end).filter(Boolean).sort().slice(-1)[0];
  const row = (label, v, c, max) => { const r = document.createElement('div'); r.className = 'bar'; const a = document.createElement('div'); a.textContent = label; const t = document.createElement('div'); t.className = 'track';
    const f = document.createElement('div'); f.className = 'fill'; f.style.width = Math.min(100, 100 * v / max).toFixed(1) + '%'; f.style.background = c; t.appendChild(f); const n = document.createElement('div'); n.className = 'v'; n.textContent = fmt(v); r.append(a, t, n); return r; };
  const run = () => {
    const C = +s('capex').value, L = +s('life').value, r = +s('ret').value / 100, m = +s('margin').value / 100, sh = +s('share').value / 100, yrs = +s('years').value;
    o('capex').value = fmt(C); o('life').value = L + ' yrs'; o('ret').value = (r * 100).toFixed(1) + '%'; o('margin').value = Math.round(m * 100) + '%'; o('share').value = Math.round(sh * 100) + '%'; o('years').value = yrs + ' yrs';
    const need = C * (1 / L + r) / m; const loopAnnual = DATA.kpi.loop_dollars * sh / yrs; const onewayAnnual = (DATA.kpi.total_dollars - DATA.kpi.loop_dollars - (DATA.fate_totals.carried_as_debt || 0)) / yrs;
    $('#hero').innerHTML = ''; $('#hero').appendChild(document.createTextNode(fmt(need) + ' a year')); const sm = document.createElement('small'); sm.textContent = 'of new revenue needed to cover depreciation and the required return'; $('#hero').appendChild(sm);
    $('#heroformula').textContent = `${fmt(C)} × (1/${L} + ${(r * 100).toFixed(1)}%) ÷ ${Math.round(m * 100)}% = ${fmt(need)}. Depreciation alone is ${fmt(C / L)} a year; the return on capital adds ${fmt(C * r)}.`;
    const sb = $('#scenbars'); sb.innerHTML = ''; const max = Math.max(need, visible, loopAnnual, onewayAnnual) * 1.05;
    sb.appendChild(row('Needed each year', need, 'var(--ink)', max));
    sb.appendChild(row(`Visible today: new segment revenue, trailing 4Q${windowEnd ? ' to ' + windowEnd : ''}`, visible, 'var(--earn)', max));
    sb.appendChild(row(`Round-trip commitments that become outside demand, per year`, loopAnnual, 'var(--loop)', max));
    sb.appendChild(row('One-way commitments spent per year', onewayAnnual, 'var(--oneway)', max));
    const covered = visible + loopAnnual + onewayAnnual;
    $('#scennote').textContent = `Under these settings the visible and announced sources add up to ${fmt(covered)} a year, ${Math.round(100 * covered / need)}% of what is needed. ` +
      `The gap, ${fmt(Math.max(0, need - covered))} a year, is revenue nobody has announced yet. Segment revenue is the four cloud and ad segments combined (new segment operating income over the same window: ${fmt(visibleOpi)}); it includes non-AI growth, so it flatters the comparison.`;
  };
  ['capex', 'life', 'ret', 'margin', 'share', 'years'].forEach(id => s(id).addEventListener('input', run)); run();
})();

// ---------- segment sources ----------
(function seg() { const tb = $('#segtable tbody'); DATA.seg_sources.forEach(r => { const tr = document.createElement('tr');
  [DATA.names[r.ticker] || r.ticker, r.segment, r.metric.replace(/_/g, ' '), r.quarter_end, Number(r.value).toFixed(2)].forEach((v, i) => { const td = document.createElement('td'); if (i === 4) td.className = 'num'; td.textContent = v; tr.appendChild(td); });
  const td = document.createElement('td'); const a = document.createElement('a'); a.href = r.source_url; a.target = '_blank'; a.rel = 'noopener'; a.textContent = r.quote; td.appendChild(a); tr.appendChild(td); tb.appendChild(tr); }); })();

$('#foot').textContent = `Data pulled ${DATA.pulled} (Yahoo Finance via yfinance for statements and prices; SEC filings and company releases for deals and segment figures; US Census Bureau BTOS for adoption). Built by build_dashboard.py from the same files the notebook writes. Amounts in US dollars, billions.`;
</script>
</body>
</html>
"""
html = HTML.replace("__DATA__", json.dumps(DATA, default=str).replace("</", "<\\/"))
(OUT / "index.html").write_text(html, encoding="utf-8")
print("dashboard written:", OUT / "index.html", f"{len(html) / 1024:.0f} KB")
print("fate totals:", fate_totals, "| capex 2026:", capex_2026, "| neo at risk:", neo_at_risk)
