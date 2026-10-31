"""Figure 5: the loop as a portfolio problem. Daily return correlations among the five largest index weights tied by the
deal graph, and how much of an equal-weight basket's variance comes from the covariance term."""
import pandas as pd, numpy as np, matplotlib.pyplot as plt, pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from figures import C, F, D

FIVE = ["MSFT", "GOOGL", "AMZN", "META", "NVDA"]
NAMES = {"MSFT": "Microsoft", "GOOGL": "Alphabet", "AMZN": "Amazon", "META": "Meta", "NVDA": "Nvidia", "SPY": "S&P 500 (SPY)"}
px = pd.read_csv(D / "prices.csv", parse_dates=["Date"]).set_index("Date")
r = px[FIVE + ["SPY"]].loc["2025-01-01":].pct_change().dropna()
ann = 252

# Correlation matrix and the variance decomposition of an equal-weight basket of the five
corr = r[FIVE].corr()
cov = r[FIVE].cov() * ann
w = np.full(len(FIVE), 1 / len(FIVE))
var_total = float(w @ cov.values @ w)
var_diag = float((w ** 2 * np.diag(cov.values)).sum())  # what the variance would be if the five were uncorrelated
pairs = corr.values[np.triu_indices(len(FIVE), 1)]
spy_corr = r[FIVE].corrwith(r["SPY"])
summary = pd.Series({
    "window_start": r.index[0].date(), "window_end": r.index[-1].date(), "trading_days": len(r),
    "avg_pairwise_corr_five": round(float(pairs.mean()), 3), "min_pairwise_corr_five": round(float(pairs.min()), 3),
    "avg_corr_with_spy": round(float(spy_corr.mean()), 3),
    "basket_vol_annual": round(np.sqrt(var_total), 3), "basket_vol_if_uncorrelated": round(np.sqrt(var_diag), 3),
    "covariance_share_of_variance": round(1 - var_diag / var_total, 3),
    "effective_n_assets": round(var_diag / var_total * len(FIVE), 2),  # independent assets that would give the same variance
})
corr.round(3).to_csv(F / "table_correlation.csv"); summary.to_csv(F / "table_portfolio_variance.csv")
print(corr.round(2).to_string()); print(summary.to_string())

# Rolling 60-day average pairwise correlation
roll = pd.concat([r[a].rolling(60).corr(r[b]) for a, b in zip(*np.triu_indices(len(FIVE), 1)) for a, b in [(FIVE[a], FIVE[b])]], axis=1).mean(axis=1).dropna()

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 4.6), gridspec_kw=dict(width_ratios=[1, 1.4]))
im = ax1.imshow(corr.values, cmap="Blues", vmin=0, vmax=1)
ax1.set_xticks(range(len(FIVE))); ax1.set_yticks(range(len(FIVE)))
ax1.set_xticklabels([NAMES[t] for t in FIVE], rotation=30, ha="right", fontsize=9); ax1.set_yticklabels([NAMES[t] for t in FIVE], fontsize=9)
for i in range(len(FIVE)):
    for j in range(len(FIVE)):
        v = corr.values[i, j]; ax1.text(j, i, f"{v:.2f}", ha="center", va="center", fontsize=9, color="white" if v > 0.6 else C["ink"])
ax1.grid(False); ax1.set_title("Daily return correlation since Jan 2025", loc="left", fontweight="bold", color=C["ink"])
for s in ax1.spines.values(): s.set_visible(False)

ax2.plot(roll.index, roll, color=C["MSFT"], lw=2)
ax2.axhline(summary["avg_pairwise_corr_five"], color=C["muted"], lw=0.8, ls=(0, (4, 2)))
ax2.text(roll.index[0], summary["avg_pairwise_corr_five"] + 0.02, f"full-window average {summary['avg_pairwise_corr_five']:.2f}", fontsize=8.5, color=C["ink2"])
ax2.set_ylim(0, 1); ax2.set_ylabel("Average pairwise correlation, 60-day window")
ax2.set_title("Correlation spiked in the spring 2025 selloff and has run 0.2 to 0.5 since", loc="left", fontweight="bold", color=C["ink"])
fig.suptitle("An index holder is less diversified across these five than the count suggests", x=0.01, ha="left", fontsize=14, fontweight="bold", color=C["ink"])
fig.text(0.01, 0.90, f"Equal-weight basket of the five: {summary['basket_vol_annual']:.0%} annualized volatility, {summary['basket_vol_if_uncorrelated']:.0%} if they were uncorrelated; "
         f"the covariance term is {summary['covariance_share_of_variance']:.0%} of the variance, so five names carry the risk of {summary['effective_n_assets']:.1f} independent ones.",
         color=C["ink2"], fontsize=9.5)
fig.text(0.01, 0.005, f"Source: Yahoo Finance adjusted closes via yfinance, {summary['window_start']} to {summary['window_end']}, {summary['trading_days']} trading days. Variance = w'Σw with equal weights; the uncorrelated case keeps only the diagonal of Σ.",
         color=C["muted"], fontsize=8)
fig.tight_layout(rect=(0, 0.03, 1, 0.87)); fig.savefig(F / "fig5_correlation.png", dpi=180); plt.close()
print("fig5 written")
