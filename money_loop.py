"""Figure 2: the AI money loop as a directed, dollar-weighted graph. Edges come only from data/deals.csv,
where every row carries a source URL and a quote. Computes closed-loop (cycle) dollars."""
import pandas as pd, numpy as np, networkx as nx, matplotlib.pyplot as plt, pathlib, sys
from matplotlib.patches import FancyArrowPatch
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from figures import C, F, D

deals = pd.read_csv(D / "deals.csv")
deals = deals[~deals.type.isin(["capex_guidance", "capex_actual"])].copy()
deals = deals[deals.status.isin(["LOI", "committed", "funded"])]  # unverified rows never enter the graph
deals["amount_usd_bn"] = pd.to_numeric(deals.amount_usd_bn, errors="coerce")
deals = deals.dropna(subset=["from", "to"])
# Editorial exclusions, each stated in the notebook:
#  - the Sept 2025 $100bn Nvidia->OpenAI LOI was superseded by the $30bn that closed in the Feb 2026 round
#  - the Aug 2026 financing-platform MOU is a $500bn *third-party* capital target across six firms, not one funder's money
#  - the Meta FWP "indication of interest" from three cornerstone buyers is non-binding and not attributable to one buyer
#  - the July 2026 SK Group / Nvidia $500bn-plus partnership LOI runs both ways with no disclosed split
drop = ((deals["from"] == "Nvidia") & (deals["to"] == "OpenAI") & (deals.amount_usd_bn == 100)) \
     | deals["from"].str.contains(";") \
     | (deals["from"] == "SK Group")
deals = deals[~drop]
ALIAS = {"Amazon (AWS)": "Amazon", "Google Cloud": "Google", "bond investors": "Credit markets",
         "convertible investors": "Credit markets"}
deals["from"] = deals["from"].replace(ALIAS); deals["to"] = deals["to"].replace(ALIAS)
deals["quantified"] = deals.amount_usd_bn.notna()
deals["amount_usd_bn"] = deals.amount_usd_bn.fillna(0.0)

EDGE_COLOR = {"equity_investment": C["MSFT"], "purchase_commitment": C["GOOGL"], "cloud_contract": C["GOOGL"],
              "capacity_backstop": C["neg"], "debt_financing": C["META"], "warrant": C["AMZN"]}
EDGE_LABEL = {"equity_investment": "equity / investment", "purchase_commitment": "chip or cloud purchase",
              "cloud_contract": "chip or cloud purchase", "capacity_backstop": "capacity backstop",
              "debt_financing": "debt financing", "warrant": "warrants"}

G = nx.DiGraph()
for _, r in deals.iterrows():
    if G.has_edge(r["from"], r["to"]):
        e = G[r["from"]][r["to"]]; e["w"] += r.amount_usd_bn; e["types"].add(r.type); e["q"] = e["q"] or r.quantified
    else:
        G.add_edge(r["from"], r["to"], w=r.amount_usd_bn, types={r.type}, status=r.status, q=bool(r.quantified))

# Cycle accounting: dollars that sit on a closed loop. For each simple cycle, the loop's binding size is its min edge.
cycles = list(nx.simple_cycles(G))
cyc_rows = []
for cyc in cycles:
    edges = [(cyc[i], cyc[(i + 1) % len(cyc)]) for i in range(len(cyc))]
    ws = [G[a][b]["w"] for a, b in edges]
    nq = sum(not G[a][b]["q"] for a, b in edges)
    cyc_rows.append(dict(cycle=" → ".join(cyc + [cyc[0]]), n_edges=len(cyc), unquantified_edges=nq,
                         min_quantified_edge_bn=min([w for (a, b), w in zip(edges, ws) if G[a][b]["q"]] or [0]),
                         sum_edges_bn=sum(ws)))
cyc_df = pd.DataFrame(cyc_rows).sort_values("sum_edges_bn", ascending=False) if cyc_rows else pd.DataFrame()
cyc_df.to_csv(F / "table_cycles.csv", index=False)
on_cycle_edges = {e for cyc in cycles for e in zip(cyc, cyc[1:] + cyc[:1])}
loop_dollars = sum(G[a][b]["w"] for a, b in on_cycle_edges)
total_dollars = sum(d["w"] for _, _, d in G.edges(data=True))
summary = dict(n_nodes=G.number_of_nodes(), n_edges=G.number_of_edges(), n_cycles=len(cycles),
               dollars_on_a_cycle_bn=round(loop_dollars, 1), total_edge_dollars_bn=round(total_dollars, 1),
               share_on_cycle=round(loop_dollars / total_dollars, 3) if total_dollars else np.nan)
pd.Series(summary).to_csv(F / "table_loop_summary.csv")
print(summary); print(cyc_df.head(10).to_string(index=False) if len(cyc_df) else "no cycles")

# ---- draw ----
# Pinned positions; any node not listed falls back to a seeded spring layout
PIN = {"Nvidia": (0.0, -0.2), "OpenAI": (-0.45, 0.45), "Microsoft": (0.6, -0.05), "Anthropic": (0.95, 0.55),
       "Amazon": (0.35, 0.9), "SoftBank": (-0.55, 1.0), "AMD": (-1.05, 0.6), "Meta": (-1.05, -0.85),
       "CoreWeave": (-0.2, -0.6), "Intel": (0.2, -0.5), "Credit markets": (0.3, -1.0), "Nebius": (0.7, -0.65),
       "Google": (1.3, 0.1)}
fixed = [n for n in G if n in PIN]
pos = nx.spring_layout(G, seed=7, pos={n: PIN[n] for n in fixed} or None, fixed=fixed or None)
pos = {k: np.asarray(v, dtype=float) for k, v in pos.items()}
fig, ax = plt.subplots(figsize=(12, 9)); ax.axis("off")
flow_in = {n: sum(d["w"] for _, _, d in G.in_edges(n, data=True)) for n in G}
flow_out = {n: sum(d["w"] for _, _, d in G.out_edges(n, data=True)) for n in G}
size = {n: 600 + 12 * (flow_in[n] + flow_out[n]) for n in G}
wmax = max(d["w"] for _, _, d in G.edges(data=True))
for a, b, d in G.edges(data=True):
    t = sorted(d["types"])[0]; on = (a, b) in on_cycle_edges
    lw = 0.8 + 6 * d["w"] / wmax
    rad = 0.18 if G.has_edge(b, a) else 0.08
    dashed = d["status"] == "LOI" or not d["q"]
    arr = FancyArrowPatch(pos[a], pos[b], connectionstyle=f"arc3,rad={rad}", arrowstyle="-|>", mutation_scale=14,
                          lw=lw, color=EDGE_COLOR.get(t, C["muted"]), alpha=0.95 if on else 0.45,
                          shrinkA=np.sqrt(size[a]) * 0.55, shrinkB=np.sqrt(size[b]) * 0.55, zorder=1,
                          linestyle=(0, (4, 2)) if dashed else "-")
    ax.add_patch(arr)
    dx, dy = pos[b] - pos[a]
    mid = (pos[a] + pos[b]) / 2 + 0.5 * rad * np.array([dy, -dx])  # arc3 control point is mid + rad*(dy,-dx); curve passes halfway
    ax.text(*mid, f"${d['w']:.0f}bn" if d["q"] else "n.q.", fontsize=8, color=C["ink2"], ha="center", va="center",
            bbox=dict(boxstyle="round,pad=0.15", fc="#fcfcfb", ec="none", alpha=0.85), zorder=3)
nx.draw_networkx_nodes(G, pos, node_size=[size[n] for n in G], node_color="#fcfcfb", edgecolors=C["ink"], linewidths=1.2, ax=ax)
nx.draw_networkx_labels(G, pos, font_size=9, font_color=C["ink"], ax=ax,
                        bbox=dict(boxstyle="round,pad=0.2", fc="#fcfcfb", ec="none", alpha=0.9))
ax.set_xlim(min(v[0] for v in pos.values()) - 0.2, max(v[0] for v in pos.values()) + 0.2)
ax.set_ylim(min(v[1] for v in pos.values()) - 0.3, max(v[1] for v in pos.values()) + 0.15)
from matplotlib.lines import Line2D
handles = [Line2D([0], [0], color=c, lw=3, label=EDGE_LABEL[t]) for t, c in EDGE_COLOR.items()
           if t in {tt for _, _, d in G.edges(data=True) for tt in d["types"]} and t != "cloud_contract"]
handles.append(Line2D([0], [0], color=C["muted"], lw=2, ls=(0, (4, 2)), label="letter of intent, or no public dollar figure (n.q.)"))
ax.legend(handles=handles, frameon=False, fontsize=9, loc="lower right")
fig.text(0.01, 0.975, "The AI money loop: who is financing whom", fontweight="bold", fontsize=14, color=C["ink"])
fig.text(0.01, 0.945, f"{summary['n_edges']} announced commitments between {summary['n_nodes']} entities; "
         f"\\${summary['dollars_on_a_cycle_bn']:.0f}bn of \\${summary['total_edge_dollars_bn']:.0f}bn sits on a closed loop. "
         "Edge width = dollars; bright = on a cycle.", color=C["ink2"], fontsize=10)
fig.text(0.01, 0.01, "Source: data/deals.csv (one URL and quote per row: SEC filings, company press releases, Reuters/CNBC). Amounts are announced headline sizes, not cash transferred.",
         color=C["muted"], fontsize=8)
fig.savefig(F / "fig2_money_loop.png", dpi=180, bbox_inches="tight"); plt.close()
print("fig2 written")
