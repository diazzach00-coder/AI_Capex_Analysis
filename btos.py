"""Census BTOS: share of US employer firms using AI in the last two weeks (national). Figure 4."""
import pandas as pd, numpy as np, matplotlib.pyplot as plt, pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from figures import C, F, D  # reuse palette + paths (figures.py renders on import; harmless)

raw = pathlib.Path(__file__).parent / "raw" / "National.xlsx"
est = pd.read_excel(raw, sheet_name="Response Estimates")
dates = pd.read_excel(raw, sheet_name="Collection and Reference Dates")
dates = dates.rename(columns={"Smpdt": "smpdt", "Ref End": "ref_end"})[["smpdt", "ref_end"]].dropna()
dates["smpdt"] = dates.smpdt.astype(int)

def series(qid, ans="Yes"):
    row = est[(est["Question ID"] == qid) & (est["Answer"] == ans)].iloc[0]
    s = row.drop(["Question ID", "Question", "Answer ID", "Answer"])
    s = s.replace(".", np.nan).astype(str).str.rstrip("%").replace("nan", np.nan).astype(float)
    s.index = s.index.astype(int)
    out = pd.DataFrame({"smpdt": s.index, "pct": s.values}).merge(dates, on="smpdt").dropna()
    return out.sort_values("ref_end").reset_index(drop=True)

use = series(7); plan = series(24)
use.to_csv(D / "btos_ai_use.csv", index=False); plan.to_csv(D / "btos_ai_plan.csv", index=False)
BREAK = pd.Timestamp("2025-11-17")  # question broadened from "producing goods or services" to "any business function"

fig, ax = plt.subplots(figsize=(9, 4.2))
for d, c, lbl in [(use, C["MSFT"], "Currently using"), (plan, C["GOOGL"], "Expect to use within 6 months")]:
    pre, post = d[d.ref_end < BREAK], d[d.ref_end >= BREAK]
    ax.plot(pre.ref_end, pre.pct, color=c, lw=2, label=lbl)
    ax.plot(post.ref_end, post.pct, color=c, lw=2)
    ax.annotate(f"{lbl}: {d.pct.iloc[-1]:.1f}%", (d.ref_end.iloc[-1], d.pct.iloc[-1]), xytext=(5, 0),
                textcoords="offset points", va="center", fontsize=9, color=c)
import matplotlib.dates as mdates
ax.xaxis.set_major_locator(mdates.MonthLocator(interval=2)); ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %y"))
ax.set_ylabel("% of US employer firms"); ax.set_ylim(0, 32)
ax.legend(frameon=False, fontsize=9, loc="lower right")
ax.set_title("Adoption is broad and rising, but it is a usage count, not a revenue line", loc="left",
             fontweight="bold", fontsize=13, color=C["ink"])
fig.text(0.01, 0.005, "Source: US Census Bureau, Business Trends and Outlook Survey, national workbook (biweekly). Series begins Nov 2025 when the question\n"
         f"was reworded to 'any business function'; latest reference period ends {use.ref_end.iloc[-1].date()}.",
         color=C["muted"], fontsize=8)
fig.tight_layout(rect=(0, 0.06, 0.97, 1)); fig.savefig(F / "fig4_btos_adoption.png", dpi=180); plt.close()
print(use.tail(3)); print("first", use.ref_end.iloc[0].date(), use.pct.iloc[0])
