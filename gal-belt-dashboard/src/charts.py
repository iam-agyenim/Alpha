"""Plotly figure builders. One colour system: red = defect/high risk, amber = needs calibration/medium,
green = normal/low, navy = neutral emphasis, grey = context. Every coloured mark also carries a text label."""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

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
    text = [f"{d} of {n} ({_pct(r)})" for d, n, r in zip(rates["defects"], rates["jobs"], rates["rate"])]
    fig = go.Figure(go.Bar(x=rates["level"], y=rates["rate"] * 100, marker_color=colours, text=text,
                           textposition="outside", cliponaxis=False,
                           hovertemplate="%{x}<br>%{text} of jobs had a defect<extra></extra>"))
    fig.update_yaxes(range=[0, 115], ticksuffix="%")
    return style(fig, title, axis, "Defect rate (% of jobs)", big)


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


