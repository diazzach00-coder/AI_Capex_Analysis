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
        src = src.replace('plt.close()', 'plt.show()')  # scripts save and close; the notebook also displays inline
    return src

nb = nbf.v4.new_notebook()
cells = [
nbf.v4.new_markdown_cell("""# The AI money loop
**QFE 5335, Module 3 discussion. Zach Diaz.**

The AI buildout is financed in a loop, and the loop is not yet earning its keep. The four largest hyperscalers guide to $735bn of capital expenditure in 2026, three of them have printed a negative free-cash-flow quarter since the start of 2025, and $468bn of the $610bn in announced commitments with a public dollar figure sits on a closed loop, where the money returns to whoever sent it. Adoption is broad, with 24.6% of US employer firms using AI, but the cloud and ad segments the capex was built for added $136bn of revenue over their latest four quarters against $504bn of capex.

Five pieces of evidence, each from a dataset pulled or hand-entered in this notebook:
1. Hyperscaler capex vs. free cash flow (company cash-flow statements)
2. The financing graph between chip vendors, labs, hyperscalers and neoclouds (deal table, one source URL per row)
3. Neocloud balance sheets (CoreWeave, Nebius, IREN, Applied Digital)
4. AI adoption among US firms (Census Bureau BTOS)
5. Cloud and ad segment revenue against capex (8-K earnings exhibits), shown in the dashboard at `docs/index.html`

Data sources and pull dates are printed in each section. Figures are saved to `figures/`. The discussion questions are answered in section 5."""),
nbf.v4.new_markdown_cell("## 0. Data pull\nStatement line items come from Yahoo Finance via `yfinance`. Yahoo's labels are not GAAP line items; the notebook spot-checks Q3 2026 capex against the 8-Ks in `data/deals.csv` (rows with type `capex_actual`)."),
nbf.v4.new_code_cell(code("pull_data.py")),
nbf.v4.new_markdown_cell("""## 1. Capex has outrun free cash flow
The spend has outrun the cash that funds it. Alphabet reported $51.4bn of capital expenditure for the third quarter of 2026, Microsoft $45.2bn and Meta $34.9bn, and the four companies together guide to $735bn for the year: Amazon $220bn, Alphabet $200bn, Microsoft $175bn, Meta $140bn. Amazon's free cash flow was negative $18.2bn in the first quarter of 2026, Alphabet's negative $5.9bn in the second and Meta's negative $1.2bn in the third, so the capex is now paid for from balance sheets and borrowing rather than from operations. Microsoft has not printed a negative quarter. Amazon's Q2 2026 is missing from Yahoo's feed."""),
nbf.v4.new_code_cell(code("figures.py").split("# ---------- Figure 3")[0]),
nbf.v4.new_markdown_cell("""## 2. The money loop
`data/deals.csv` has one row per announced commitment with a source URL and a quote from that page. Rows marked `unverified` (anonymous-sourced press reports only, e.g. OpenAI→Oracle $300bn) or `conditional` (announced but contingent, e.g. the $35bn second tranche of Amazon's OpenAI investment) never enter the graph. Four editorial exclusions are stated in the code.

Cycle dollars are the sum of edge amounts that sit on at least one simple cycle. Edges with no public dollar figure (OpenAI's 10 GW Nvidia and 6 GW AMD commitments) are drawn dashed and carry zero weight, so the closed-loop share is a lower bound.

The money is circular. Of $610bn in announced commitments with a public dollar figure, $468bn sits on a closed loop in which a hyperscaler invests in a lab that commits to buy the hyperscaler's cloud. The largest loop runs Amazon to OpenAI to Microsoft to Anthropic and back to Amazon at $370bn, and the Microsoft and OpenAI pair alone carries $262bn.

For investors, the loop changes what revenue and backlog mean. When Microsoft invests in OpenAI and OpenAI commits $250bn to Azure, part of that commitment is Microsoft's own money coming back as revenue. The same applies to Amazon and Anthropic, where $13bn of investment sits against a $100bn AWS commitment. A backlog figure funded by the vendor deserves a lower multiple than one funded by outside customers, and the deal table lets a reader separate the two."""),
nbf.v4.new_code_cell(code("money_loop.py")),
nbf.v4.new_markdown_cell("""## 3. Neoclouds carry the debt
The borrowing has moved to the companies least able to carry it. CoreWeave, Nebius, IREN and Applied Digital hold $76bn of debt plus lease liabilities and all four reported negative operating income in their latest quarter. Their shares have given back most of their run: from the peak, CoreWeave is down 67%, IREN 66% and Nebius 40%, while Nvidia is down 11%, as of 29 October 2026.

CoreWeave carries $51.6bn of debt plus lease liabilities against $10.3bn of annualized revenue, a ratio of 5.0, and IREN carries 14.3 times. None of the four covers its interest from operations, and CoreWeave's interest expense ran $0.64bn in the June 2026 quarter. Nvidia's $6.3bn commitment to buy CoreWeave's unsold capacity through 2032 means the chip vendor is also the customer of last resort for its own chips.

Yahoo's 'Total Debt' line includes operating and finance leases; for CoreWeave at June 30, 2026 the 10-Q shows $35.1bn of borrowings and $16.5bn of lease liabilities. The figures below show debt plus leases vs. annualized revenue, interest coverage, and price paths since CoreWeave's listing."""),
nbf.v4.new_code_cell("# ---------- Figure 3" + code("figures.py").split("# ---------- Figure 3", 1)[1]),
nbf.v4.new_markdown_cell("## 4. Is anyone paying at the end of the chain?\nCensus BTOS, national workbook, downloaded directly from census.gov. The series starts Nov 2025, when the question was reworded to 'any business function'. The current question text refers to 'Super Intelligence or SI (formerly referred to as Artificial Intelligence or AI)'."),
nbf.v4.new_code_cell(code("btos.py")),
nbf.v4.new_markdown_cell("""## 5. Discussion

### Why the topic matters in financial markets
The spend has outrun the cash that funds it, the borrowing has moved to the companies least able to carry it, and the money is circular. Alphabet, Microsoft and Meta reported $131.5bn of capital expenditure between them for the third quarter of 2026, three of the four hyperscalers have printed a negative free-cash-flow quarter since 2025, and $468bn of $610bn in announced commitments sits on a closed loop. These companies are the largest weights in the S&P 500, so the question of whether this spend earns a return is a question about the index itself.

### Relevance to investors and regulators
For investors, a backlog funded by the vendor's own investment deserves a lower multiple than one funded by outside customers, and the neocloud balance sheets set the credit question: $76bn of debt plus leases, none of it covered by operating income.

For regulators, the record shows three disclosure gaps. Headline commitments are ceilings: Amazon's $50bn OpenAI investment is $15bn firm and $35bn conditional, and Meta's $14.2bn CoreWeave contract is an "up to" figure. Common data feeds blur the balance sheet: Yahoo's "Total Debt" line for CoreWeave includes $16.5bn of lease liabilities that the 10-Q reports separately from $35.1bn of borrowings. Segment reporting shifts under the analysis: Microsoft retired its Intelligent Cloud segment in the September 2026 quarter and printed Azure revenue in dollars, $33.2bn, for the first time. Vendor financing, circular commitments and related-party capacity guarantees are the exposures that disclosure rules exist to surface, and most of these are visible only by reading the filings themselves.

### How the topic relates to the course
Module 3 covers the risk and return of portfolios and the S&P 500. Portfolio variance is a weighted sum of covariances, so what matters for an index holder is not how many names they own but how much those names move together. Microsoft, Alphabet, Amazon, Meta and Nvidia are five of the largest index weights, and the deal graph shows their cash flows are tied: the same dollars count as Microsoft's investment, OpenAI's spending and Nvidia's sales. That raises the covariance term, so an S&P 500 holder is less diversified across these five than the count suggests.

The neocloud price paths show the levered end of the same bet. Indexed to CoreWeave's listing in March 2025, IREN and Nebius rose above 1,000 before giving back most of the gain, while Nvidia moved inside a far narrower band. Same factor, different leverage, different variance.

The break-even calculator in the dashboard turns the capex into a required return. At a $735bn annual run-rate, a five-year useful life, a 10% required return and a 30% operating margin, the AI business must add $735bn of revenue a year to stand still. The four cloud and ad segments added $136bn over their latest four quarters. The gap is the expected-return assumption the market is making, and the width of the outcomes around it is the risk the module asks us to price.

### How the data ties to the discussion
Five datasets carry the argument, each pulled or hand-entered in this notebook with its source and pull date.

| Dataset | What it shows | Caveat |
| --- | --- | --- |
| Hyperscaler cash flows (Yahoo Finance via yfinance) | Capex has outrun free cash flow; three of four printed a negative FCF quarter since 2025 | Yahoo labels are not GAAP lines. Meta's Q3 2026 capex is $33.9bn on Yahoo and $34.9bn in the 8-K; the gap is finance-lease principal. Amazon's Q2 2026 is missing from the feed |
| Deal table (`data/deals.csv`, 50 rows, one URL and quote each) | $468bn of $610bn in announced commitments sits on a closed loop, 77% | Amounts are headline sizes, not cash transferred. Commitments with no dollar figure carry zero weight, so the loop share is a lower bound. Anonymous-sourced reports such as OpenAI to Oracle at $300bn stay out |
| Neocloud financials (Yahoo Finance) | Debt plus leases of $76bn across four companies, all with negative operating income | Yahoo's "Total Debt" includes operating leases; CoreWeave's $51.6bn splits into $35.1bn of borrowings and $16.5bn of leases per the 10-Q |
| Census BTOS, national workbook | AI use among US employer firms rose from 17.3% in November 2025 to 24.6% in October 2026; 28.6% expect to use it within six months | Counts firms, not dollars. The question was reworded in November 2025, so earlier readings do not compare |
| Segment revenue (`data/segment_revenue.csv`, 8-K exhibits) | New segment revenue per dollar of capex over the latest four quarters: Amazon 0.17, Alphabet 0.21, Microsoft 0.27, Meta 0.49 | Capex is company-wide, segment revenue is one segment, and both include non-AI activity. Meta's Family of Apps operating income fell $1.9bn over the window. Microsoft's series stops at June 2026 when it retired the Intelligent Cloud segment |

Each number in the text above comes from one of these rows, and each row links to the filing or release it came from."""),
]
nb["cells"] = cells
nb.metadata["kernelspec"] = {"name": "python3", "display_name": "Python 3", "language": "python"}
nbf.write(nb, R / "ai_money_loop.ipynb")
print("notebook written")
