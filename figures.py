"""Figures 1, 3 (and 4 if BTOS available). Palette: one hue per entity, fixed order, no dual axes."""
import pandas as pd, numpy as np, matplotlib as mpl, matplotlib.pyplot as plt, pathlib, json

ROOT = pathlib.Path(__file__).parent; D = ROOT / "data"; F = ROOT / "figures"; F.mkdir(exist_ok=True)
META = json.load(open(D / "pull_meta.json"))["pulled_utc"][:10]

C = {"MSFT": "#2a78d6", "GOOGL": "#eb6834", "AMZN": "#1baf7a", "META": "#eda100",
     "CRWV": "#2a78d6", "NBIS": "#eb6834", "IREN": "#1baf7a", "APLD": "#eda100",
     "ink": "#0b0b0b", "ink2": "#52514e", "muted": "#898781", "grid": "#e1e0d9", "neg": "#e34948"}
mpl.rcParams.update({"font.family": "sans-serif", "axes.spines.top": False, "axes.spines.right": False,
                     "axes.edgecolor": C["muted"], "axes.labelcolor": C["ink2"], "xtick.color": C["ink2"],
                     "ytick.color": C["ink2"], "axes.grid": True, "grid.color": C["grid"], "grid.linewidth": 0.6,
                     "axes.axisbelow": True, "figure.facecolor": "#fcfcfb", "axes.facecolor": "#fcfcfb",
                     "font.size": 10})
def qlabel(ts): ts = pd.Timestamp(ts); return f"{ts.year % 100:02d}Q{(ts.month - 1) // 3 + 1}"

# ---------- Figure 1: capex vs free cash flow, small multiples ----------
h = pd.read_csv(D / "hyperscaler_cashflow.csv", parse_dates=["quarter"])
h = h[h.quarter >= "2025-01-01"].dropna(subset=["capex", "fcf"])
NAMES = {"MSFT": "Microsoft", "GOOGL": "Alphabet", "AMZN": "Amazon", "META": "Meta"}
fig, axes = plt.subplots(1, 4, figsize=(13, 4.2), sharey=True)
ymax = h.capex.max() * 1.15
for ax, t in zip(axes, NAMES):
    d = h[h.ticker == t].reset_index(drop=True)
    x = np.arange(len(d))
    ax.bar(x, d.capex, width=0.62, color=C[t], alpha=0.35, linewidth=0, label="Capex")
    ax.plot(x, d.fcf, color=C["ink"], lw=2, marker="o", ms=5, label="Free cash flow")
    neg = d.fcf < 0
    ax.scatter(x[neg], d.fcf[neg], color=C["neg"], s=60, zorder=5)
    for i, v in zip(x[neg], d.fcf[neg]): ax.annotate(f"{v:.1f}", (i, v), xytext=(0, -12), textcoords="offset points",
                                                   ha="center", color=C["neg"], fontsize=9, fontweight="bold")
    ax.axhline(0, color=C["muted"], lw=0.8)
    ax.set_xticks(x); ax.set_xticklabels([qlabel(q) for q in d.quarter], fontsize=8.5)
    ax.set_title(NAMES[t], loc="left", color=C["ink"], fontweight="bold")
    ax.set_ylim(min(-25, h.fcf.min() * 1.2), ymax)
axes[0].set_ylabel("USD bn, quarterly")
axes[0].legend(frameon=False, loc="upper left", fontsize=9)
fig.suptitle("Capex has outrun free cash flow", x=0.01, ha="left", fontsize=14, fontweight="bold", color=C["ink"])
fig.text(0.01, 0.90, "Quarterly capital expenditure (bars) and free cash flow (line); red = negative FCF quarter",
         color=C["ink2"], fontsize=10)
fig.text(0.01, 0.005, f"Source: company cash-flow statements via Yahoo Finance, pulled {META}. Amazon Q2 and Q3 2026 absent from feed.",
         color=C["muted"], fontsize=8)
fig.tight_layout(rect=(0, 0.03, 1, 0.88)); fig.savefig(F / "fig1_capex_vs_fcf.png", dpi=180); plt.close()
print("fig1 written; quarters per ticker:", h.groupby("ticker").quarter.max().dt.date.to_dict())

# ---------- Figure 3: neocloud debt vs revenue ----------
n = pd.read_csv(D / "neocloud_financials.csv", parse_dates=["quarter"]).dropna(subset=["total_debt"])
NEO = {"CRWV": "CoreWeave", "NBIS": "Nebius", "IREN": "IREN", "APLD": "Applied Digital"}
fig, axes = plt.subplots(1, 4, figsize=(13, 4.2), sharey=True)
for ax, t in zip(axes, NEO):
    d = n[n.ticker == t].reset_index(drop=True); x = np.arange(len(d))
    ax.bar(x - 0.18, d.total_debt, width=0.36, color=C[t], linewidth=0, label="Debt plus lease liabilities")
    ax.bar(x + 0.18, d.revenue * 4, width=0.36, color=C[t], alpha=0.35, linewidth=0, label="Revenue, annualized (×4)")
    ax.set_xticks(x); ax.set_xticklabels([qlabel(q) for q in d.quarter], fontsize=8.5)
    ax.set_title(NEO[t], loc="left", color=C["ink"], fontweight="bold")
    last = d.iloc[-1]
    ax.annotate(f"{last.total_debt:.1f}", (x[-1] - 0.18, last.total_debt), xytext=(0, 4), textcoords="offset points",
                ha="center", fontsize=9, color=C["ink"])
axes[0].set_ylabel("USD bn"); axes[0].legend(frameon=False, loc="upper left", fontsize=9)
fig.suptitle("Neoclouds: debt is growing faster than revenue", x=0.01, ha="left", fontsize=14, fontweight="bold", color=C["ink"])
fig.text(0.01, 0.90, "Debt plus operating and finance lease liabilities vs. annualized quarterly revenue, latest available quarters",
         color=C["ink2"], fontsize=10)
fig.text(0.01, 0.005, f"Source: company balance sheets and income statements via Yahoo Finance, pulled {META}. Yahoo's 'Total Debt' line includes lease liabilities. "
         "Applied Digital fiscal quarters end Feb/May/Aug/Nov.", color=C["muted"], fontsize=8)
fig.tight_layout(rect=(0, 0.03, 1, 0.88)); fig.savefig(F / "fig3_neocloud_debt.png", dpi=180); plt.close()

# Coverage table (interest coverage = operating income / interest expense)
cov = n.copy()
cov["interest_coverage"] = cov.op_income / cov.interest_expense
cov["debt_to_annualized_rev"] = cov.total_debt / (cov.revenue * 4)
tbl = cov.groupby("ticker").tail(1)[["ticker", "quarter", "total_debt", "revenue", "op_income", "interest_expense",
                                      "interest_coverage", "debt_to_annualized_rev"]].round(2)
tbl.to_csv(F / "table_neocloud_coverage.csv", index=False); print(tbl.to_string(index=False))

# ---------- Figure 3b: neocloud + Nvidia price paths since Jan 2025 ----------
px = pd.read_csv(D / "prices.csv", parse_dates=["Date"]).set_index("Date")
idx = px[["CRWV", "NBIS", "IREN", "NVDA"]].dropna()
idx = idx / idx.iloc[0] * 100
fig, ax = plt.subplots(figsize=(9, 4.2))
LBL = {**NEO, "NVDA": "Nvidia"}
for t, c in [("CRWV", C["CRWV"]), ("NBIS", C["NBIS"]), ("IREN", C["IREN"]), ("NVDA", C["ink"])]:
    ax.plot(idx.index, idx[t], lw=2 if t != "NVDA" else 1.5, color=c, label=LBL[t])
    ax.annotate(LBL[t], (idx.index[-1], idx[t].iloc[-1]), xytext=(4, 0),
                textcoords="offset points", va="center", fontsize=9, color=c)
ax.axvspan(pd.Timestamp("2026-10-15"), idx.index[-1], color=C["grid"], alpha=0.6, lw=0)
ax.text(pd.Timestamp("2026-10-15"), ax.get_ylim()[1] * 0.97, " neocloud sell-off", fontsize=8.5, color=C["ink2"], va="top")
ax.set_ylabel(f"Index, {idx.index[0].date()} = 100"); ax.legend(frameon=False, fontsize=9, loc="upper left")
dd = (idx / idx.cummax() - 1).iloc[-1] * 100
ax.set_title("Neoclouds ran far ahead of Nvidia, then gave much of it back", loc="left", fontweight="bold", fontsize=13,
             color=C["ink"], pad=20)
ax.text(0, 1.015, "Drawdown from peak: " + ", ".join(f"{LBL[t]} {dd[t]:.0f}%" for t in ["CRWV", "NBIS", "IREN", "NVDA"]),
        transform=ax.transAxes, fontsize=9, color=C["ink2"], va="bottom")
dd.round(1).to_csv(F / "table_drawdowns.csv")
fig.text(0.01, 0.005, f"Source: Yahoo Finance adjusted closes, pulled {META}. CoreWeave listed 28 Mar 2025; series starts at first common date.",
         color=C["muted"], fontsize=8)
fig.tight_layout(rect=(0, 0.03, 1, 1)); fig.savefig(F / "fig3b_neocloud_prices.png", dpi=180); plt.close()
print("figures written")
