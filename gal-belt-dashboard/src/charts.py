"""Plotly figure builders. One colour system: red = defect/high risk, amber = needs calibration/medium,
green = normal/low, navy = neutral emphasis, grey = context. Every coloured mark also carries a text label."""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# Palette taken from the GAL x MoIAT briefing deck (Case 3 "Expected Dashboard" slide). app.py's CSS uses the
# same values, so charts, the fleet alert card and the status board read as one system.
RED = "#C0392B"      # High Risk / defect
AMBER = "#D97706"    # Medium / needs calibration
GREEN = "#2E8B57"    # Normal
NAVY = "#265AA4"     # deck accent1: neutral emphasis
GOLD = "#AF8C45"     # deck accent2: labels and reference lines
GREY = "#8D9091"     # deck accent3: context
INK = "#404042"      # deck dk1: text
MUTED = "#5F6264"    # deck accent4: secondary text
GRID = "#E3E5E8"     # deck accent6: gridlines
FONT = "Cairo, Helvetica, Arial, sans-serif"

SEQ_RED = [[0, "#FBEAE8"], [0.5, "#E08A80"], [1, RED]]
SEQ_NAVY = [[0, "#EAF0F8"], [0.5, "#8BA6CF"], [1, NAVY]]


def style(fig: go.Figure, title: str, x: str | None = None, y: str | None = None, big: bool = False,
          height: int | None = None) -> go.Figure:
    base = 18 if big else 15
    fig.update_layout(
        title=dict(text=f"<b>{title}</b>", font=dict(size=base + 4, color=INK, family=FONT), x=0, xanchor="left"),
        font=dict(size=base, color=INK, family=FONT),
        plot_bgcolor="white", paper_bgcolor="white",
        margin=dict(l=80, r=30, t=70, b=80), height=height or (520 if big else 400),
        # Legend under the plot: it can never collide with a long title, whatever the screen width.
        legend=dict(orientation="h", yanchor="top", y=-0.22, xanchor="left", x=0, font=dict(size=base)),
        hoverlabel=dict(font_size=base),
        uniformtext=dict(minsize=base - 2, mode="show"),
    )
    fig.update_traces(textfont_size=base, selector=dict(type="bar"))
    fig.update_xaxes(title_text=x, automargin=True, title_standoff=12, showgrid=False, linecolor=GRID, tickfont=dict(size=base), title_font=dict(size=base))
    fig.update_yaxes(title_text=y, automargin=True, title_standoff=12, gridcolor=GRID, zeroline=False, tickfont=dict(size=base), title_font=dict(size=base))
    return fig


def _pct(v):
    return "n/a" if pd.isna(v) else f"{v:.0%}"


def rate_bar(rates: pd.DataFrame, title: str, axis: str, highlight: str | None = None, big=False) -> go.Figure:
    colours = [RED if lvl == highlight else NAVY for lvl in rates["level"]]
    text = [f"{d}/{n} ({_pct(r)})" for d, n, r in zip(rates["defects"], rates["jobs"], rates["rate"])]
    fig = go.Figure(go.Bar(x=rates["level"], y=rates["rate"] * 100, marker_color=colours, text=text,
                           textposition="outside", cliponaxis=False,
                           hovertemplate="%{x}<br>%{text} of jobs had a defect<extra></extra>"))
    fig.update_yaxes(range=[0, 115], ticksuffix="%")
    return style(fig, title, axis, "Defect rate (% of jobs)", big)


def pareto_chart(p: pd.DataFrame, title: str, big=False) -> go.Figure:
    """Single-axis Pareto: bars = defects, labels carry the cumulative share."""
    colours = [RED if d > 0 and i == 0 else (NAVY if d > 0 else GREY) for i, d in enumerate(p["defects"])]
    text = [f"{d} defects · cum. {c:.0f}%" if d else "0" for d, c in zip(p["defects"], p["cum_pct"])]
    fig = go.Figure(go.Bar(x=p["level"], y=p["defects"], marker_color=colours, text=text, textposition="outside",
                           cliponaxis=False, hovertemplate="%{x}: %{text}<extra></extra>"))
    fig.update_yaxes(range=[0, max(1, p["defects"].max()) * 1.2])
    return style(fig, title, "Tool", "Number of defects", big)


def bayes_chart(b: pd.DataFrame, overall: dict, title: str, big=False) -> go.Figure:
    b = b.copy()
    b["label"] = b["factor_label"] + ": " + b["level"].astype(str)
    b = b.iloc[::-1]
    colours = [RED if lo > overall["post_mean"] else GREEN if hi < overall["post_mean"] else NAVY
               for lo, hi in zip(b["ci_low"], b["ci_high"])]
    fig = go.Figure(go.Scatter(
        x=b["post_mean"] * 100, y=b["label"], mode="markers",
        marker=dict(size=12, color=colours, line=dict(color="white", width=2)),
        error_x=dict(type="data", symmetric=False, array=(b["ci_high"] - b["post_mean"]) * 100,
                     arrayminus=(b["post_mean"] - b["ci_low"]) * 100, color=MUTED, thickness=2, width=0),
        customdata=np.stack([b["defects"], b["jobs"], b["ci_low"] * 100, b["ci_high"] * 100], axis=1),
        hovertemplate="%{y}<br>Estimated rate %{x:.0f}% (90% interval %{customdata[2]:.0f}–%{customdata[3]:.0f}%)"
                      "<br>%{customdata[0]} defects in %{customdata[1]} jobs<extra></extra>"))
    fig.add_vline(x=overall["post_mean"] * 100, line_dash="dash", line_color=MUTED,
                  annotation_text=f"Fleet average {overall['post_mean']:.0%}", annotation_position="top")
    fig.update_xaxes(range=[0, 100], ticksuffix="%", showgrid=True, gridcolor=GRID)
    fig.update_yaxes(showgrid=False)
    return style(fig, title, "Estimated defect rate with 90% credible interval", None, big,
                 height=max(380, 34 * len(b) + 120))


def heatmap(table: pd.DataFrame, title: str, x: str, y: str, scale, fmt="{:.0f}", big=False,
            text: pd.DataFrame | None = None) -> go.Figure:
    labels = text if text is not None else table.map(lambda v: "" if pd.isna(v) else fmt.format(v))
    fig = go.Figure(go.Heatmap(z=table.to_numpy(dtype=float), x=table.columns.astype(str), y=table.index.astype(str),
                               colorscale=scale, text=labels.to_numpy(), texttemplate="%{text}",
                               textfont=dict(size=18 if big else 15), showscale=False, xgap=2, ygap=2,
                               hovertemplate=f"{y}: %{{y}}<br>{x}: %{{x}}<br>%{{text}}<extra></extra>"))
    fig.update_yaxes(autorange="reversed")
    return style(fig, title, x, y, big, height=max(300, 70 * len(table) + 120))


def monthly_chart(m: pd.DataFrame, suspect: str, title: str, big=False) -> go.Figure:
    fig = go.Figure()
    for col, name, colour in [("jobs", "All jobs", GREY), ("suspect_jobs", f"Jobs with {suspect}", AMBER),
                              ("defects", "Defects", RED)]:
        fig.add_bar(x=m["month"], y=m[col], name=name, marker_color=colour, text=m[col], textposition="outside",
                    cliponaxis=False, hovertemplate=f"%{{x}}: %{{y}} {name.lower()}<extra></extra>")
    fig.update_layout(barmode="group", bargap=0.25, bargroupgap=0.08)
    fig.update_yaxes(range=[0, m["jobs"].max() * 1.2])
    return style(fig, title, "Month", "Number of jobs", big)


def p_chart_fig(pc: dict, title: str, big=False) -> go.Figure:
    t = pc["table"]
    fig = go.Figure()
    fig.add_scatter(x=t["month"], y=t["ucl"] * 100, name="Upper control limit", mode="lines",
                    line=dict(color=MUTED, dash="dash", width=2, shape="hv"))
    fig.add_scatter(x=t["month"], y=t["lcl"] * 100, name="Lower control limit", mode="lines",
                    line=dict(color=MUTED, dash="dot", width=2, shape="hv"))
    fig.add_scatter(x=t["month"], y=[pc["centre"] * 100] * len(t), name=f"Centre line ({pc['centre']:.1%})",
                    mode="lines", line=dict(color=NAVY, width=2))
    colours = [RED if o else NAVY for o in t["out_of_control"]]
    fig.add_scatter(x=t["month"], y=t["rate"] * 100, name="Monthly defect rate", mode="lines+markers+text",
                    line=dict(color=INK, width=2), marker=dict(size=12, color=colours, line=dict(color="white", width=2)),
                    text=[f"{r:.0%}" for r in t["rate"]], textposition="top center",
                    customdata=np.stack([t["defects"], t["jobs"]], axis=1),
                    hovertemplate="%{x}: %{y:.0f}% (%{customdata[0]} of %{customdata[1]} jobs)<extra></extra>")
    fig.update_yaxes(range=[0, 105], ticksuffix="%")
    return style(fig, title, "Month", "Defect rate (% of jobs)", big)


def small_multiples(table: pd.DataFrame, factor: str, by: str, title: str, factor_label: str, by_label: str,
                    big=False) -> go.Figure:
    t = table.copy()
    t["pct"] = t["rate"] * 100
    t["label"] = [f"{d}/{n}" for d, n in zip(t["defects"], t["jobs"])]
    t["colour"] = np.where(t["rate"] >= 0.5, "High (≥50%)", np.where(t["rate"] > 0, "Some", "None"))
    fig = px.bar(t, x=factor, y="pct", facet_col=by, text="label", color="colour",
                 color_discrete_map={"High (≥50%)": RED, "Some": AMBER, "None": GREEN},
                 category_orders={"colour": ["High (≥50%)", "Some", "None"]},
                 labels={"pct": "Defect rate (%)", factor: factor_label, by: by_label, "colour": "Defect rate"})
    fig.for_each_annotation(lambda a: a.update(text=f"{by_label}: {a.text.split('=')[-1]}"))
    fig.update_traces(textposition="outside", cliponaxis=False)
    fig.update_yaxes(range=[0, 118], ticksuffix="%")
    style(fig, title, None, None, big)
    fig.update_layout(legend=dict(orientation="h", yanchor="top", y=-0.28, xanchor="left", x=0),
                      margin=dict(b=120))
    fig.update_yaxes(title_text="Defect rate (% of jobs)", col=1)
    fig.update_xaxes(title_text=factor_label)
    return fig


def confusion_fig(cm, title: str, big=False) -> go.Figure:
    labels = pd.DataFrame(cm, index=["Actual: no defect", "Actual: defect"],
                          columns=["Predicted: no defect", "Predicted: defect"])
    return heatmap(labels.astype(float), title, "Prediction", "Actual", SEQ_NAVY, big=big,
                   text=labels.map(lambda v: f"{int(v)} jobs"))


def gate_chart(g: dict, big=False) -> go.Figure:
    fig = go.Figure(go.Bar(
        x=["Defects that occurred", "Defects left if the gate blocked<br>tools not in Normal status"],
        y=[g["defects_total"], g["defects_remaining"]], marker_color=[RED, GREEN],
        text=[f"{g['defects_total']} defects", f"{g['defects_remaining']} defects"], textposition="outside",
        cliponaxis=False))
    fig.update_yaxes(range=[0, max(1, g["defects_total"]) * 1.25])
    return style(fig, f"Calibration gate: {g['defects_avoided']} of {g['defects_total']} defects prevented",
                 None, "Number of defects", big)


def risk_probs_chart(fitted: pd.DataFrame, high: float, medium: float, big=False) -> go.Figure:
    f = fitted.sort_values("risk")
    colours = [RED if r >= high else AMBER if r >= medium else GREEN for r in f["risk"]]
    fig = go.Figure(go.Bar(x=f["risk"] * 100, y=f["Record_ID"] + " · " + f["Tool_ID"], orientation="h",
                           marker_color=colours,
                           text=[f"{r:.0%} {'(defect)' if d else ''}" for r, d in zip(f["risk"], f["defect"])],
                           textposition="outside", cliponaxis=False,
                           hovertemplate="%{y}: %{x:.0f}% predicted risk<extra></extra>"))
    fig.add_vline(x=high * 100, line_dash="dash", line_color=RED, annotation_text="High", annotation_position="top")
    fig.add_vline(x=medium * 100, line_dash="dot", line_color=AMBER, annotation_text="Medium", annotation_position="top")
    fig.update_xaxes(range=[0, 115], ticksuffix="%")
    return style(fig, "Pre-job model: predicted risk for every past job", "Predicted defect risk", None, big,
                 height=max(420, (34 if big else 24) * len(f) + 140))
