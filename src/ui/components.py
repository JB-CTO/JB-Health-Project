"""
Reusable UI components, Plotly chart builders, and style helpers for JB-Health-Project.
"""

from typing import Dict, List, Optional
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import numpy as np


# Dark theme palette
COLORS = {
    "background": "#0e1117",
    "surface": "#1e293b",
    "primary": "#0f766e",
    "primary_light": "#14b8a6",
    "success": "#10b981",
    "warning": "#f59e0b",
    "danger": "#ef4444",
    "info": "#3b82f6",
    "purple": "#8b5cf6",
    "deep_sleep": "#3b82f6",
    "rem_sleep": "#8b5cf6",
    "core_sleep": "#06b6d4",
    "awake": "#f43f5e",
    "text": "#f8fafc",
    "text_muted": "#94a3b8",
}


def apply_dark_layout(fig: go.Figure, title: str = "", height: int = 400) -> go.Figure:
    """Applies a clean, modern dark aesthetic to any Plotly figure."""
    fig.update_layout(
        title=dict(text=title, font=dict(size=16, color=COLORS["text"], family="Inter, sans-serif")),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(30,41,59,0.5)",
        height=height,
        margin=dict(l=40, r=30, t=50, b=40),
        font=dict(color=COLORS["text"], family="Inter, sans-serif"),
        hoverlabel=dict(bgcolor="#1e293b", font_size=12, font_family="Inter, sans-serif"),
        xaxis=dict(
            gridcolor="rgba(148,163,184,0.1)",
            zerolinecolor="rgba(148,163,184,0.2)",
            showline=True,
            linecolor="rgba(148,163,184,0.2)"
        ),
        yaxis=dict(
            gridcolor="rgba(148,163,184,0.1)",
            zerolinecolor="rgba(148,163,184,0.2)",
            showline=True,
            linecolor="rgba(148,163,184,0.2)"
        ),
        legend=dict(
            bgcolor="rgba(15,23,42,0.6)",
            bordercolor="rgba(148,163,184,0.2)",
            borderwidth=1,
            font=dict(size=11)
        )
    )
    return fig


def plot_recovery_gauge(score: float) -> go.Figure:
    """Renders a circular gauge for today's recovery score."""
    if score >= 67:
        bar_color = COLORS["success"]
    elif score >= 34:
        bar_color = COLORS["warning"]
    else:
        bar_color = COLORS["danger"]

    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=score,
        title=dict(text="<b>Readiness & Recovery Score</b>", font=dict(size=16, color=COLORS["text"])),
        number=dict(suffix="%", font=dict(size=36, color=bar_color)),
        gauge=dict(
            axis=dict(range=[0, 100], tickwidth=1, tickcolor=COLORS["text_muted"]),
            bar=dict(color=bar_color, thickness=0.3),
            bgcolor="rgba(255,255,255,0.05)",
            borderwidth=2,
            bordercolor="rgba(148,163,184,0.2)",
            steps=[
                dict(range=[0, 33], color="rgba(239,68,68,0.2)"),
                dict(range=[33, 66], color="rgba(245,158,11,0.2)"),
                dict(range=[66, 100], color="rgba(16,185,129,0.2)")
            ]
        )
    ))
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        height=240,
        margin=dict(l=30, r=30, t=40, b=20)
    )
    return fig


def plot_hrv_trend(df: pd.DataFrame) -> go.Figure:
    """Plots daily HRV with 7-day rolling baseline."""
    fig = go.Figure()
    if df.empty or "hrv_sdnn" not in df.columns:
        return fig

    # HRV daily points
    fig.add_trace(go.Scatter(
        x=df["date"], y=df["hrv_sdnn"],
        mode="markers+lines",
        name="Daily HRV (ms)",
        line=dict(color=COLORS["primary_light"], width=1.5),
        marker=dict(size=6, color=COLORS["primary_light"])
    ))

    # Baseline line
    if "hrv_7d_baseline" in df.columns and df["hrv_7d_baseline"].notna().any():
        fig.add_trace(go.Scatter(
            x=df["date"], y=df["hrv_7d_baseline"],
            mode="lines",
            name="14-Day Baseline",
            line=dict(color="#38bdf8", width=2.5, dash="dash")
        ))

    apply_dark_layout(fig, title="Heart Rate Variability (SDNN) & Rolling Baseline", height=350)
    fig.update_yaxes(title="HRV (ms)")
    return fig


def plot_sleep_stages_timeline(df: pd.DataFrame) -> go.Figure:
    """Stacked bar chart showing Deep, REM, Core, and Awake hours per night."""
    fig = go.Figure()
    if df.empty or "total_sleep_hours" not in df.columns:
        return fig

    # Calculate Core sleep if not present
    core_series = df["total_sleep_hours"] - (df["deep_sleep_hours"].fillna(0) + df["rem_sleep_hours"].fillna(0))
    core_series = core_series.clip(lower=0)

    fig.add_trace(go.Bar(
        x=df["date"], y=df["deep_sleep_hours"],
        name="Deep Sleep",
        marker_color=COLORS["deep_sleep"]
    ))
    fig.add_trace(go.Bar(
        x=df["date"], y=df["rem_sleep_hours"],
        name="REM Sleep",
        marker_color=COLORS["rem_sleep"]
    ))
    fig.add_trace(go.Bar(
        x=df["date"], y=core_series,
        name="Core / Light Sleep",
        marker_color=COLORS["core_sleep"]
    ))

    # Add Target line
    fig.add_hline(y=8.0, line_dash="dot", line_color="#f59e0b", annotation_text="8h Target", annotation_position="top right")

    fig.update_layout(barmode="stack")
    apply_dark_layout(fig, title="Nightly Sleep Architecture Breakdown", height=380)
    fig.update_yaxes(title="Sleep Duration (Hours)")
    return fig


def plot_training_load_tsb(df: pd.DataFrame) -> go.Figure:
    """Plots Acute Training Load (ATL), Chronic Training Load (CTL), and Freshness (TSB)."""
    fig = go.Figure()
    if df.empty or "training_stress_balance" not in df.columns:
        return fig

    # TSB area fill
    colors_tsb = ["rgba(16,185,129,0.7)" if v >= 0 else "rgba(239,68,68,0.7)" for v in df["training_stress_balance"]]
    fig.add_trace(go.Bar(
        x=df["date"], y=df["training_stress_balance"],
        name="Training Stress Balance (TSB)",
        marker_color=colors_tsb,
        opacity=0.65
    ))

    # ATL line (Fatigue)
    fig.add_trace(go.Scatter(
        x=df["date"], y=df["training_load_atl"],
        mode="lines",
        name="Acute Load / Fatigue (7d)",
        line=dict(color="#f43f5e", width=2)
    ))

    # CTL line (Fitness)
    fig.add_trace(go.Scatter(
        x=df["date"], y=df["training_load_ctl"],
        mode="lines",
        name="Chronic Load / Fitness (28d)",
        line=dict(color="#3b82f6", width=2.5)
    ))

    # Reference threshold lines for optimal training
    fig.add_hline(y=15, line_dash="dash", line_color="rgba(148,163,184,0.3)", annotation_text="Fresh / Peaking")
    fig.add_hline(y=-10, line_dash="dash", line_color="rgba(148,163,184,0.3)", annotation_text="Optimal Building")
    fig.add_hline(y=-30, line_dash="dash", line_color="rgba(239,68,68,0.5)", annotation_text="Overreaching Danger")

    apply_dark_layout(fig, title="Performance & Training Load (ATL, CTL, TSB)", height=420)
    fig.update_yaxes(title="Load Units / TSB")
    return fig


def plot_biomarker_trends(df_bio: pd.DataFrame, test_name: str) -> go.Figure:
    """Plots a biomarker over time with normal reference range shading."""
    fig = go.Figure()
    sub = df_bio[df_bio["test_name"] == test_name].sort_values("date")
    if sub.empty:
        return fig

    ref_low = sub["ref_low"].iloc[-1] if pd.notna(sub["ref_low"].iloc[-1]) else None
    ref_high = sub["ref_high"].iloc[-1] if pd.notna(sub["ref_high"].iloc[-1]) else None
    unit = sub["unit"].iloc[-1] or ""

    # Shaded Reference Range
    if ref_low is not None and ref_high is not None:
        fig.add_hrect(
            y0=ref_low, y1=ref_high,
            fillcolor="rgba(16,185,129,0.15)",
            line_width=0,
            annotation_text=f"Normal ({ref_low}-{ref_high} {unit})",
            annotation_position="top left"
        )
    elif ref_high is not None:
        fig.add_hrect(
            y0=0, y1=ref_high,
            fillcolor="rgba(16,185,129,0.15)",
            line_width=0,
            annotation_text=f"Normal (<{ref_high} {unit})",
            annotation_position="top left"
        )
    elif ref_low is not None:
        fig.add_hline(
            y=ref_low, line_dash="dash", line_color="rgba(16,185,129,0.5)",
            annotation_text=f"Target (>{ref_low} {unit})"
        )

    # Actual measurements
    marker_colors = [COLORS["danger"] if f in ("HIGH", "LOW", "CRITICAL") else COLORS["primary_light"] for f in sub["flag"]]
    fig.add_trace(go.Scatter(
        x=sub["date"], y=sub["value"],
        mode="markers+lines+text",
        text=[f"{v} {unit}" for v in sub["value"]],
        textposition="top center",
        name=test_name,
        line=dict(color=COLORS["primary_light"], width=2.5),
        marker=dict(size=10, color=marker_colors)
    ))

    apply_dark_layout(fig, title=f"{test_name} Historical Trend", height=350)
    fig.update_yaxes(title=f"{test_name} ({unit})")
    return fig


def plot_correlation_scatter(df: pd.DataFrame, x_col: str, y_col: str, title: str = "") -> go.Figure:
    """Scatter plot with trendline between any two health metrics."""
    valid = df[[x_col, y_col]].dropna()
    if valid.empty:
        return go.Figure()

    try:
        fig = px.scatter(
            valid, x=x_col, y=y_col,
            trendline="ols",
            color_discrete_sequence=[COLORS["primary_light"]]
        )
    except Exception:
        fig = px.scatter(
            valid, x=x_col, y=y_col,
            color_discrete_sequence=[COLORS["primary_light"]]
        )
    apply_dark_layout(fig, title=title or f"{x_col} vs {y_col}", height=380)
    return fig
