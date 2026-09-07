"""
Reusable UI components, Plotly chart builders, and style helpers for JB-Health-Project.
Delivers a consistent, modern dark aesthetic across all health dashboards.
"""

from typing import Dict, List, Optional, Tuple
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import numpy as np

# Premium Modern Health Palette
COLORS = {
    "background": "#080c16",
    "surface": "#111827",
    "surface_card": "rgba(17, 24, 39, 0.75)",
    "border": "rgba(255, 255, 255, 0.07)",
    "primary": "#06b6d4",        # Cyan
    "primary_light": "#22d3ee",  # Bright Cyan
    "primary_dark": "#0891b2",
    "success": "#10b981",        # Emerald
    "success_light": "#34d399",
    "warning": "#f59e0b",        # Amber
    "warning_light": "#fbbf24",
    "danger": "#f43f5e",         # Rose Red
    "danger_light": "#fb7185",
    "info": "#3b82f6",           # Blue
    "purple": "#8b5cf6",         # Violet
    "deep_sleep": "#3b82f6",     # Deep Royal Blue
    "rem_sleep": "#8b5cf6",      # Vivid Purple
    "core_sleep": "#06b6d4",     # Bright Cyan
    "awake": "#fb7185",          # Coral Rose
    "text": "#f8fafc",           # Near White
    "text_muted": "#94a3b8",     # Slate Gray
}


def apply_dark_layout(fig: go.Figure, title: str = "", height: int = 380) -> go.Figure:
    """Applies a clean, modern dark aesthetic with subtle gridlines and crisp typography."""
    fig.update_layout(
        title=dict(
            text=f"<b>{title}</b>" if title else "",
            font=dict(size=15, color=COLORS["text"], family="Inter, -apple-system, sans-serif"),
            x=0.01,
            y=0.96
        ),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(15, 23, 42, 0.4)",
        height=height,
        margin=dict(l=35, r=25, t=45 if title else 25, b=35),
        font=dict(color=COLORS["text_muted"], family="Inter, -apple-system, sans-serif", size=11),
        hoverlabel=dict(
            bgcolor="#111827",
            bordercolor="rgba(255, 255, 255, 0.15)",
            font_size=12,
            font_family="Inter, sans-serif",
            font_color=COLORS["text"]
        ),
        xaxis=dict(
            showgrid=False,
            zeroline=False,
            showline=True,
            linecolor="rgba(255, 255, 255, 0.1)",
            tickfont=dict(color=COLORS["text_muted"], size=10)
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor="rgba(255, 255, 255, 0.05)",
            griddash="dot",
            zeroline=False,
            showline=False,
            tickfont=dict(color=COLORS["text_muted"], size=10)
        ),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            bgcolor="rgba(0,0,0,0)",
            font=dict(size=11, color=COLORS["text_muted"])
        )
    )
    return fig


def render_stat_card(
    title: str,
    value: str,
    unit: str = "",
    delta: str = "",
    delta_type: str = "neutral",
    subtitle: str = "",
    icon: str = "⚡"
) -> str:
    """Generates modern glassmorphic KPI card HTML with consistent typography and delta badges."""
    badge_html = ""
    if delta:
        if delta_type == "good":
            badge_class = "delta-good"
            arrow = "↑" if not delta.startswith(("-", "+")) else ""
        elif delta_type == "bad":
            badge_class = "delta-bad"
            arrow = "↓" if not delta.startswith(("-", "+")) else ""
        elif delta_type == "warn":
            badge_class = "delta-warn"
            arrow = "•"
        else:
            badge_class = "delta-neutral"
            arrow = "•"
        badge_html = f'<span class="delta-pill {badge_class}">{arrow} {delta}</span>'

    unit_html = f'<span class="stat-unit">{unit}</span>' if unit else ""
    subtitle_html = f'<div class="stat-sub">{subtitle}</div>' if subtitle else ""

    return f"""
    <div class="stat-card">
        <div class="stat-header">
            <span class="stat-title">{title}</span>
            <span class="stat-icon">{icon}</span>
        </div>
        <div class="stat-row">
            <div class="stat-value">{value}{unit_html}</div>
            {badge_html}
        </div>
        {subtitle_html}
    </div>
    """


def plot_recovery_gauge(score: float) -> go.Figure:
    """Renders a sleek circular recovery gauge with status badge."""
    if score >= 67:
        bar_color = COLORS["success"]
        status_text = "OPTIMAL READINESS"
        status_color = COLORS["success_light"]
    elif score >= 34:
        bar_color = COLORS["warning"]
        status_text = "MODERATE RECOVERY"
        status_color = COLORS["warning_light"]
    else:
        bar_color = COLORS["danger"]
        status_text = "FATIGUE / REST NEEDED"
        status_color = COLORS["danger_light"]

    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=score,
        number=dict(suffix="%", font=dict(size=38, color=COLORS["text"], family="Inter, sans-serif")),
        gauge=dict(
            axis=dict(range=[0, 100], tickwidth=1, tickcolor="rgba(255,255,255,0.15)", ticklen=6),
            bar=dict(color=bar_color, thickness=0.28),
            bgcolor="rgba(255, 255, 255, 0.04)",
            borderwidth=1,
            bordercolor="rgba(255, 255, 255, 0.08)",
            steps=[
                dict(range=[0, 33], color="rgba(244, 63, 94, 0.12)"),
                dict(range=[33, 66], color="rgba(245, 158, 11, 0.12)"),
                dict(range=[66, 100], color="rgba(16, 185, 129, 0.12)")
            ]
        )
    ))

    fig.add_annotation(
        text=f"<span style='color:{status_color};font-weight:700;letter-spacing:1px;font-size:11px'>{status_text}</span>",
        x=0.5, y=0.15,
        showarrow=False
    )

    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        height=220,
        margin=dict(l=20, r=20, t=25, b=10)
    )
    return fig


def plot_hrv_trend(df: pd.DataFrame) -> go.Figure:
    """Plots daily HRV with 14-day rolling baseline and confidence corridor."""
    fig = go.Figure()
    if df.empty or "hrv_sdnn" not in df.columns:
        return fig

    # Baseline line with confidence tunnel
    if "hrv_7d_baseline" in df.columns and df["hrv_7d_baseline"].notna().any():
        # Shaded normal band (+- 10% around baseline)
        upper_band = df["hrv_7d_baseline"] * 1.15
        lower_band = df["hrv_7d_baseline"] * 0.85
        fig.add_trace(go.Scatter(
            x=df["date"], y=upper_band,
            mode="lines",
            line=dict(width=0),
            showlegend=False,
            hoverinfo="skip"
        ))
        fig.add_trace(go.Scatter(
            x=df["date"], y=lower_band,
            mode="lines",
            line=dict(width=0),
            fill="tonexty",
            fillcolor="rgba(6, 182, 212, 0.08)",
            name="Normal HRV Zone",
            hoverinfo="skip"
        ))
        fig.add_trace(go.Scatter(
            x=df["date"], y=df["hrv_7d_baseline"],
            mode="lines",
            name="14d Baseline",
            line=dict(color="rgba(6, 182, 212, 0.8)", width=2, dash="dash")
        ))

    # Daily HRV points & smooth spline
    fig.add_trace(go.Scatter(
        x=df["date"], y=df["hrv_sdnn"],
        mode="lines+markers",
        name="Daily HRV",
        line=dict(color=COLORS["primary_light"], width=2.2, shape="spline"),
        marker=dict(size=6, color=COLORS["primary_light"], line=dict(width=1, color="#ffffff"))
    ))

    apply_dark_layout(fig, title="Heart Rate Variability (SDNN) & Rolling Baseline", height=340)
    fig.update_yaxes(title="HRV (ms)")
    return fig


def plot_sleep_stages_timeline(df: pd.DataFrame) -> go.Figure:
    """Stacked sleep architecture bars with custom modern palette."""
    fig = go.Figure()
    if df.empty or "total_sleep_hours" not in df.columns:
        return fig

    core_series = df["total_sleep_hours"] - (df["deep_sleep_hours"].fillna(0) + df["rem_sleep_hours"].fillna(0))
    core_series = core_series.clip(lower=0)

    fig.add_trace(go.Bar(
        x=df["date"], y=df["deep_sleep_hours"],
        name="Deep Sleep",
        marker_color=COLORS["deep_sleep"],
        opacity=0.9
    ))
    fig.add_trace(go.Bar(
        x=df["date"], y=df["rem_sleep_hours"],
        name="REM Sleep",
        marker_color=COLORS["rem_sleep"],
        opacity=0.9
    ))
    fig.add_trace(go.Bar(
        x=df["date"], y=core_series,
        name="Core / Light",
        marker_color=COLORS["core_sleep"],
        opacity=0.85
    ))

    fig.add_hline(
        y=8.0, line_dash="dot",
        line_color=COLORS["warning"],
        annotation_text="8.0h Target",
        annotation_position="top right",
        annotation_font=dict(size=10, color=COLORS["warning"])
    )

    fig.update_layout(barmode="stack")
    apply_dark_layout(fig, title="Nightly Sleep Architecture Breakdown", height=350)
    max_y = max(12.0, float(df["total_sleep_hours"].dropna().max() + 1.0)) if "total_sleep_hours" in df.columns and not df["total_sleep_hours"].dropna().empty else 12.0
    fig.update_yaxes(title="Duration (Hours)", range=[0, min(24.0, max_y)])
    return fig


def render_sleep_ribbon(deep_pct: float, rem_pct: float, core_pct: float, awake_pct: float = 0.0) -> str:
    """Renders a modern horizontal sleep distribution ribbon bar."""
    awake_bar = f'<div style="width:{awake_pct:.1f}%; background:{COLORS["awake"]};" title="Awake: {awake_pct:.1f}%"></div>' if awake_pct > 0 else ""
    awake_legend = f'<span><i style="background:{COLORS["awake"]}"></i> Awake: <b>{awake_pct:.1f}%</b></span>' if awake_pct > 0 else ""
    return f"""
    <div class="sleep-ribbon-container">
        <div class="sleep-ribbon-bar">
            <div style="width:{deep_pct:.1f}%; background:{COLORS['deep_sleep']};" title="Deep: {deep_pct:.1f}%"></div>
            <div style="width:{rem_pct:.1f}%; background:{COLORS['rem_sleep']};" title="REM: {rem_pct:.1f}%"></div>
            <div style="width:{core_pct:.1f}%; background:{COLORS['core_sleep']};" title="Core: {core_pct:.1f}%"></div>
            {awake_bar}
        </div>
        <div class="sleep-ribbon-legend">
            <span><i style="background:{COLORS['deep_sleep']}"></i> Deep: <b>{deep_pct:.1f}%</b></span>
            <span><i style="background:{COLORS['rem_sleep']}"></i> REM: <b>{rem_pct:.1f}%</b></span>
            <span><i style="background:{COLORS['core_sleep']}"></i> Core: <b>{core_pct:.1f}%</b></span>
            {awake_legend}
        </div>
    </div>
    """


def plot_training_load_tsb(df: pd.DataFrame) -> go.Figure:
    """Plots Acute Training Load (ATL), Chronic Training Load (CTL), and Freshness (TSB)."""
    fig = go.Figure()
    if df.empty or "training_stress_balance" not in df.columns:
        return fig

    # TSB area fill
    colors_tsb = [
        "rgba(16,185,129,0.75)" if v >= 0 else "rgba(244,63,94,0.75)"
        for v in df["training_stress_balance"]
    ]
    fig.add_trace(go.Bar(
        x=df["date"], y=df["training_stress_balance"],
        name="TSB (Freshness)",
        marker_color=colors_tsb
    ))

    # ATL spline (Fatigue)
    fig.add_trace(go.Scatter(
        x=df["date"], y=df["training_load_atl"],
        mode="lines",
        name="ATL (Fatigue - 7d)",
        line=dict(color=COLORS["danger_light"], width=2.2, shape="spline")
    ))

    # CTL spline (Fitness)
    fig.add_trace(go.Scatter(
        x=df["date"], y=df["training_load_ctl"],
        mode="lines",
        name="CTL (Fitness - 28d)",
        line=dict(color=COLORS["primary_light"], width=2.5, shape="spline")
    ))

    # Coaching threshold lines
    fig.add_hline(y=15, line_dash="dash", line_color="rgba(16,185,129,0.3)", annotation_text="Peak / Race Ready", annotation_position="bottom right")
    fig.add_hline(y=-10, line_dash="dash", line_color="rgba(6,182,212,0.3)", annotation_text="Optimal Building", annotation_position="bottom right")
    fig.add_hline(y=-30, line_dash="dash", line_color="rgba(244,63,94,0.4)", annotation_text="Overreaching Danger", annotation_position="bottom right")

    apply_dark_layout(fig, title="Performance & Training Stress Balance (ATL vs CTL vs TSB)", height=380)
    fig.update_yaxes(title="Load Units / TSB")
    return fig


def plot_biomarker_trends(df_bio: pd.DataFrame, test_name: str) -> go.Figure:
    """Plots a biomarker over time with shaded normal reference range."""
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
            fillcolor="rgba(16, 185, 129, 0.12)",
            line_width=0,
            annotation_text=f"Normal Zone ({ref_low} - {ref_high} {unit})",
            annotation_position="top left",
            annotation_font=dict(size=10, color=COLORS["success_light"])
        )
    elif ref_high is not None:
        fig.add_hrect(
            y0=0, y1=ref_high,
            fillcolor="rgba(16, 185, 129, 0.12)",
            line_width=0,
            annotation_text=f"Normal Zone (< {ref_high} {unit})",
            annotation_position="top left",
            annotation_font=dict(size=10, color=COLORS["success_light"])
        )
    elif ref_low is not None:
        fig.add_hline(
            y=ref_low, line_dash="dash", line_color="rgba(16,185,129,0.5)",
            annotation_text=f"Target (>{ref_low} {unit})",
            annotation_position="bottom right",
            annotation_font=dict(size=10, color=COLORS["success_light"])
        )

    # Actual measurements
    marker_colors = [
        COLORS["danger"] if f in ("HIGH", "LOW", "CRITICAL") else COLORS["primary_light"]
        for f in sub["flag"]
    ]
    fig.add_trace(go.Scatter(
        x=sub["date"], y=sub["value"],
        mode="markers+lines+text",
        text=[f"{v}" for v in sub["value"]],
        textposition="top center",
        textfont=dict(color=COLORS["text"], size=11),
        name=test_name,
        line=dict(color=COLORS["primary_light"], width=2.5, shape="spline"),
        marker=dict(size=10, color=marker_colors, line=dict(color="#ffffff", width=1.5))
    ))

    apply_dark_layout(fig, title=f"{test_name} Trajectory", height=330)
    fig.update_yaxes(title=f"{test_name} ({unit})")
    return fig


def render_biomarker_range_bar(val: float, ref_low: Optional[float], ref_high: Optional[float], unit: str, flag: str) -> str:
    """Renders a visual horizontal range indicator bar showing where the biomarker lands."""
    if ref_low is not None and ref_high is not None and ref_high > ref_low:
        span = ref_high - ref_low
        # Calculate percentage position on a scale from (ref_low - 0.5*span) to (ref_high + 0.5*span)
        scale_min = max(0.0, ref_low - 0.4 * span)
        scale_max = ref_high + 0.4 * span
        pct = max(2.0, min(98.0, ((val - scale_min) / (scale_max - scale_min)) * 100.0))
        normal_start = ((ref_low - scale_min) / (scale_max - scale_min)) * 100.0
        normal_width = ((ref_high - ref_low) / (scale_max - scale_min)) * 100.0
    else:
        pct = 50.0
        normal_start = 25.0
        normal_width = 50.0

    flag_color = COLORS["success"] if flag == "NORMAL" else COLORS["danger"]

    return f"""
    <div class="range-bar-container">
        <div class="range-bar-track">
            <div class="range-bar-normal" style="left:{normal_start:.1f}%; width:{normal_width:.1f}%;"></div>
            <div class="range-bar-pin" style="left:{pct:.1f}%; background:{flag_color};"></div>
        </div>
        <div class="range-bar-labels">
            <span>Low: {ref_low if ref_low is not None else '--'}</span>
            <span style="color:{flag_color}; font-weight:700;">Current: {val} {unit} ({flag})</span>
            <span>High: {ref_high if ref_high is not None else '--'}</span>
        </div>
    </div>
    """


def plot_correlation_scatter(df: pd.DataFrame, x_col: str, y_col: str, title: str = "") -> go.Figure:
    """Scatter plot with trendline between any two health metrics with error fallback."""
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

    fig.update_traces(marker=dict(size=8, opacity=0.8, line=dict(width=1, color="rgba(255,255,255,0.2)")))
    apply_dark_layout(fig, title=title or f"{x_col} vs {y_col}", height=360)
    return fig
