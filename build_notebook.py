"""Assemble the four scripts into one executable notebook."""
import nbformat as nbf, pathlib, re
R = pathlib.Path(__file__).parent
def code(path, strip_imports=True):
    src = (R / path).read_text()
    if strip_imports:
        src = re.sub(r"^sys\.path\.insert.*\n", "", src, flags=re.M)
        src = re.sub(r"^from figures import.*\n", "", src, flags=re.M)
        src = src.replace('ROOT = pathlib.Path(__file__).parent', 'ROOT = pathlib.Path.cwd()')
        src = src.replace('pathlib.Path(__file__).parent', 'pathlib.Path.cwd()')
    return src

nb = nbf.v4.new_notebook()
cells = [
nbf.v4.new_markdown_cell("""# The AI money loop
**QFE 5335, Module 3 discussion. Zach Diaz.**

One question: who is paying for the AI buildout, and does the money come back?

Four pieces of evidence, each from a dataset pulled in this notebook:
1. Hyperscaler capex vs. free cash flow (company cash-flow statements)
2. The financing graph between chip vendors, labs, hyperscalers and neoclouds (deal table, one source URL per row)
3. Neocloud balance sheets (CoreWeave, Nebius, IREN, Applied Digital)
4. AI adoption among US firms (Census Bureau BTOS)

Data sources and pull dates are printed in each section. Figures are saved to `figures/`."""),
nbf.v4.new_markdown_cell("## 0. Data pull\nStatement line items come from Yahoo Finance via `yfinance`. Yahoo's labels are not GAAP line items; the notebook spot-checks Q3 2026 capex against the 8-Ks in `data/deals.csv` (rows with type `capex_actual`)."),
nbf.v4.new_code_cell(code("pull_data.py")),
nbf.v4.new_markdown_cell("## 1. Capex has outrun free cash flow\nMeta (Q3 26), Alphabet (Q2 26) and Amazon (Q1 26) each printed a negative free-cash-flow quarter. Microsoft has not. Amazon's Q2 2026 is missing from Yahoo's feed."),
nbf.v4.new_code_cell(code("figures.py").split("# ---------- Figure 3")[0]),
nbf.v4.new_markdown_cell("""## 2. The money loop
`data/deals.csv` has one row per announced commitment with a source URL and a quote from that page. Rows marked `unverified` (anonymous-sourced press reports only, e.g. OpenAI→Oracle $300bn) or `conditional` (announced but contingent, e.g. the $35bn second tranche of Amazon's OpenAI investment) never enter the graph. Four editorial exclusions are stated in the code.

Cycle dollars are the sum of edge amounts that sit on at least one simple cycle. Edges with no public dollar figure (OpenAI's 10 GW Nvidia and 6 GW AMD commitments) are drawn dashed and carry zero weight, so the closed-loop share is a lower bound."""),
nbf.v4.new_code_cell(code("money_loop.py")),
nbf.v4.new_markdown_cell("## 3. Neoclouds carry the debt\nDebt plus lease liabilities vs. annualized revenue, interest coverage, and price paths since CoreWeave's listing. Yahoo's 'Total Debt' line includes operating and finance leases; for CoreWeave at June 30, 2026 the 10-Q shows $35.1bn of borrowings and $16.5bn of lease liabilities."),
nbf.v4.new_code_cell("# ---------- Figure 3" + code("figures.py").split("# ---------- Figure 3", 1)[1]),
nbf.v4.new_markdown_cell("## 4. Is anyone paying at the end of the chain?\nCensus BTOS, national workbook, downloaded directly from census.gov. The series starts Nov 2025, when the question was reworded to 'any business function'. The current question text refers to 'Super Intelligence or SI (formerly referred to as Artificial Intelligence or AI)'."),
nbf.v4.new_code_cell(code("btos.py")),
]
nb["cells"] = cells
nb.metadata["kernelspec"] = {"name": "python3", "display_name": "Python 3", "language": "python"}
nbf.write(nb, R / "ai_money_loop.ipynb")
print("notebook written")
