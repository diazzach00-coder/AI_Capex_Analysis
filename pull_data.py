"""Pull hyperscaler cash-flow statements, neocloud financials, and prices.
Writes CSVs to data/ with a pull timestamp so every number is reproducible."""
import yfinance as yf, pandas as pd, numpy as np, datetime as dt, pathlib, json

OUT = pathlib.Path(__file__).parent / "data"; OUT.mkdir(exist_ok=True)
PULLED = dt.datetime.now(dt.timezone.utc).isoformat(timespec="minutes")

HYPER = ["MSFT", "GOOGL", "AMZN", "META"]
NEO   = ["CRWV", "NBIS", "IREN", "APLD"]

# 1. Hyperscaler quarterly cash flow -------------------------------------
rows = []
for t in HYPER:
    cf = yf.Ticker(t).quarterly_cashflow.T  # rows = quarter end
    cf.index = pd.to_datetime(cf.index)
    for q, r in cf.iterrows():
        rows.append(dict(ticker=t, quarter=q,
                         capex=-r.get("Capital Expenditure", np.nan),
                         ocf=r.get("Operating Cash Flow", np.nan),
                         fcf=r.get("Free Cash Flow", np.nan)))
hyper = pd.DataFrame(rows).sort_values(["ticker", "quarter"])
hyper[["capex", "ocf", "fcf"]] = hyper[["capex", "ocf", "fcf"]] / 1e9
hyper.to_csv(OUT / "hyperscaler_cashflow.csv", index=False)

# 2. Neocloud balance sheet + income ---------------------------------------
rows = []
for t in NEO:
    tk = yf.Ticker(t)
    bs = tk.quarterly_balance_sheet.T; fin = tk.quarterly_financials.T
    bs.index = pd.to_datetime(bs.index); fin.index = pd.to_datetime(fin.index)
    for q in bs.index:
        f = fin.loc[q] if q in fin.index else pd.Series(dtype=float)
        rows.append(dict(ticker=t, quarter=q,
                         total_debt=bs.loc[q].get("Total Debt", np.nan),
                         net_debt=bs.loc[q].get("Net Debt", np.nan),
                         cash=bs.loc[q].get("Cash And Cash Equivalents", np.nan),
                         revenue=f.get("Total Revenue", np.nan),
                         op_income=f.get("Operating Income", np.nan),
                         interest_expense=f.get("Interest Expense", np.nan),
                         ebitda=f.get("EBITDA", np.nan)))
neo = pd.DataFrame(rows).sort_values(["ticker", "quarter"])
num = [c for c in neo.columns if c not in ("ticker", "quarter")]
neo[num] = neo[num] / 1e9
neo.to_csv(OUT / "neocloud_financials.csv", index=False)

# 3. Prices ----------------------------------------------------------------
px = yf.download(HYPER + NEO + ["NVDA", "ORCL", "AMD", "SPY"], start="2025-01-01",
                 progress=False, auto_adjust=True)["Close"]
px.to_csv(OUT / "prices.csv")

json.dump({"pulled_utc": PULLED, "source": "Yahoo Finance via yfinance",
           "note": "Statement line items as labeled by Yahoo; verify against 10-Q/10-K before quoting."},
          open(OUT / "pull_meta.json", "w"), indent=2)
print("pulled", PULLED)
print(hyper.groupby("ticker").quarter.agg(["min", "max", "count"]))
print(neo.groupby("ticker").quarter.agg(["min", "max", "count"]))
