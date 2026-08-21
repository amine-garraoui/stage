"""Shared Plotly chart components."""

from __future__ import annotations
from typing import Optional
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

PRIMARY = "#003366"
ACCENT = "#0066CC"
SUCCESS = "#006633"
WARNING = "#FF8800"
DANGER = "#CC3300"
TEMPLATE = "plotly_white"


def line_chart_with_forecast(df: pd.DataFrame, title: str, y_label: str) -> go.Figure:
    hist = df[df["is_historical"] == True]  # noqa: E712
    future = df[df["is_historical"] == False]  # noqa: E712
    fig = go.Figure()
    if not future.empty:
        fig.add_trace(go.Scatter(
            x=list(future["period"]) + list(future["period"].iloc[::-1]),
            y=list(future["upper"]) + list(future["lower"].iloc[::-1]),
            fill="toself", fillcolor="rgba(0,102,204,0.15)",
            line=dict(color="rgba(0,0,0,0)"), name="IC 95%", showlegend=True,
        ))
    if not hist.empty:
        fig.add_trace(go.Scatter(x=hist["period"], y=hist["value"], mode="lines+markers",
                                  name="Historique", line=dict(color=PRIMARY, width=2)))
    if not future.empty:
        fig.add_trace(go.Scatter(x=future["period"], y=future["value"], mode="lines+markers",
                                  name="Prévision", line=dict(color=ACCENT, width=2, dash="dash"),
                                  marker=dict(symbol="diamond")))
    fig.update_layout(title=title, xaxis_title="Période", yaxis_title=y_label,
                      template=TEMPLATE, hovermode="x unified")
    return fig


def bar_chart_breakdown(data: dict, title: str, max_items: int = 15, color: str = ACCENT) -> go.Figure:
    items = sorted(data.items(), key=lambda x: x[1], reverse=True)[:max_items]
    fig = go.Figure(go.Bar(
        y=[i[0] for i in items], x=[i[1] for i in items],
        orientation="h", marker_color=color,
        text=[i[1] for i in items], textposition="outside",
    ))
    fig.update_layout(title=title, xaxis_title="Tickets", template=TEMPLATE,
                      yaxis=dict(autorange="reversed"),
                      height=max(300, len(items) * 30))
    return fig


def satisfaction_gauge(score: float) -> go.Figure:
    fig = go.Figure(go.Indicator(
        mode="gauge+number+delta", value=score,
        delta={"reference": 3.5},
        title={"text": "Satisfaction Moyenne"},
        gauge={"axis": {"range": [0, 5]}, "bar": {"color": ACCENT},
               "steps": [{"range": [0,2], "color": "#FFE0E0"},
                         {"range": [2,3.5], "color": "#FFF3CD"},
                         {"range": [3.5,5], "color": "#D4EDDA"}]},
    ))
    fig.update_layout(height=250, margin=dict(t=30, b=0, l=20, r=20))
    return fig


def performance_gauge(score: float) -> go.Figure:
    c = SUCCESS if score >= 70 else (WARNING if score >= 50 else DANGER)
    fig = go.Figure(go.Indicator(
        mode="gauge+number", value=score,
        title={"text": "Indice de Performance RSI"},
        gauge={"axis": {"range": [0,100]}, "bar": {"color": c},
               "steps": [{"range":[0,50],"color":"#FFE0E0"},
                         {"range":[50,70],"color":"#FFF3CD"},
                         {"range":[70,100],"color":"#D4EDDA"}]},
    ))
    fig.update_layout(height=250, margin=dict(t=30, b=0, l=20, r=20))
    return fig


def anomaly_pie(counts: dict) -> go.Figure:
    clrs = {"CRITICAL": DANGER, "HIGH": WARNING, "MEDIUM": "#FFD700", "LOW": "#90EE90"}
    labels = list(counts.keys()); values = list(counts.values())
    fig = go.Figure(go.Pie(labels=labels, values=values,
                            marker_colors=[clrs.get(l, ACCENT) for l in labels], hole=0.4))
    fig.update_layout(title="Anomalies par Sévérité", height=300)
    return fig
