"""
JB-Health-Project: Personal Health, Recovery & Performance Intelligence Platform.
Aggregates Apple Health, MyFitnessPal, and Quest Diagnostics blood work.
"""

from datetime import datetime, timedelta
from pathlib import Path
import os
import shutil
import tempfile

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import yaml

from src.database import (
    init_db, reset_db, load_table_df, get_session,
    SleepRecord, HeartRecord, ActivityRecord, WorkoutRecord, NutritionRecord, BiomarkerRecord, DailySummaryRecord
)
from src.parsers.apple_health import AppleHealthParser
from src.parsers.myfitnesspal import MyFitnessPalParser
from src.parsers.quest_diagnostics import QuestDiagnosticsParser
from src.parsers.mock_generator import generate_all_samples
from src.analytics.recovery import compute_daily_recovery
from src.analytics.training_load import compute_training_load, get_training_stress_category
from src.analytics.correlations import get_integrated_daily_df, compute_pairwise_correlation, compute_correlation_matrix
from src.ui.components import (
    plot_recovery_gauge, plot_hrv_trend, plot_sleep_stages_timeline,
    plot_training_load_tsb, plot_biomarker_trends, plot_correlation_scatter,
    render_stat_card, render_sleep_ribbon, render_biomarker_range_bar,
    apply_dark_layout, COLORS
)

# Set page configuration
st.set_page_config(
    page_title="JB Health & Performance",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Load configuration defensively
config_path = Path("config.yaml")
if config_path.exists():
    with open(config_path, "r", encoding="utf-8-sig") as f:
        cfg = yaml.safe_load(f) or {}
else:
    cfg = {}

targets = cfg.get("targets", {
    "sleep_hours_target": 8.0,
    "daily_active_calories": 600,
    "daily_protein_g_target": 160.0
})

init_db()

# Premium CSS Design System
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

    html, body, [class*="css"] {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }

    /* Background & Container */
    .stApp {
        background: #080c16;
    }

    /* Top Hero Header */
    .hero-banner {
        background: linear-gradient(135deg, rgba(17, 24, 39, 0.9) 0%, rgba(15, 23, 42, 0.7) 100%);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 16px;
        padding: 20px 24px;
        margin-bottom: 22px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        box-shadow: 0 10px 30px -10px rgba(0, 0, 0, 0.5);
    }
    .hero-title {
        font-size: 1.5rem;
        font-weight: 800;
        color: #f8fafc;
        letter-spacing: -0.02em;
        margin: 0;
        display: flex;
        align-items: center;
        gap: 10px;
    }
    .hero-subtitle {
        font-size: 0.85rem;
        color: #94a3b8;
        margin-top: 4px;
    }
    .hero-badge {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        background: rgba(6, 182, 212, 0.12);
        border: 1px solid rgba(6, 182, 212, 0.3);
        color: #22d3ee;
        padding: 6px 14px;
        border-radius: 9999px;
        font-size: 0.8rem;
        font-weight: 600;
        letter-spacing: 0.03em;
    }
    .pulse-dot {
        width: 8px;
        height: 8px;
        border-radius: 50%;
        background: #10b981;
        box-shadow: 0 0 10px #10b981;
    }

    /* Unified Glassmorphism Stat Cards */
    .stat-card {
        background: linear-gradient(135deg, rgba(17, 24, 39, 0.85) 0%, rgba(15, 23, 42, 0.65) 100%);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 14px;
        padding: 16px 18px;
        margin-bottom: 16px;
        box-shadow: 0 4px 20px -2px rgba(0, 0, 0, 0.3);
        transition: transform 0.2s ease, border-color 0.2s ease;
    }
    .stat-card:hover {
        border-color: rgba(6, 182, 212, 0.3);
        transform: translateY(-2px);
    }
    .stat-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 8px;
    }
    .stat-title {
        font-size: 0.75rem;
        font-weight: 600;
        color: #94a3b8;
        text-transform: uppercase;
        letter-spacing: 0.06em;
    }
    .stat-icon {
        font-size: 1.1rem;
        opacity: 0.85;
    }
    .stat-row {
        display: flex;
        justify-content: space-between;
        align-items: baseline;
    }
    .stat-value {
        font-size: 1.85rem;
        font-weight: 800;
        color: #f8fafc;
        line-height: 1.1;
    }
    .stat-unit {
        font-size: 0.95rem;
        font-weight: 500;
        color: #94a3b8;
        margin-left: 4px;
    }
    .stat-sub {
        font-size: 0.78rem;
        color: #64748b;
        margin-top: 6px;
        font-weight: 500;
    }

    /* Delta Pills */
    .delta-pill {
        display: inline-flex;
        align-items: center;
        padding: 2px 8px;
        border-radius: 9999px;
        font-size: 0.72rem;
        font-weight: 600;
        white-space: nowrap;
    }
    .delta-good {
        background: rgba(16, 185, 129, 0.12);
        color: #34d399;
        border: 1px solid rgba(16, 185, 129, 0.25);
    }
    .delta-bad {
        background: rgba(244, 63, 94, 0.12);
        color: #fb7185;
        border: 1px solid rgba(244, 63, 94, 0.25);
    }
    .delta-warn {
        background: rgba(245, 158, 11, 0.12);
        color: #fbbf24;
        border: 1px solid rgba(245, 158, 11, 0.25);
    }
    .delta-neutral {
        background: rgba(148, 163, 184, 0.12);
        color: #94a3b8;
        border: 1px solid rgba(148, 163, 184, 0.2);
    }

    /* Modern Tabs Styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 6px;
        background-color: rgba(17, 24, 39, 0.6);
        padding: 6px;
        border-radius: 12px;
        border: 1px solid rgba(255, 255, 255, 0.06);
        margin-bottom: 20px;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 8px;
        color: #94a3b8;
        font-size: 0.85rem;
        font-weight: 600;
        padding: 8px 16px;
        background: transparent;
        border: none;
        transition: all 0.2s ease;
    }
    .stTabs [aria-selected="true"] {
        background: #1e293b !important;
        color: #22d3ee !important;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
    }

    /* Sleep Ribbon */
    .sleep-ribbon-container {
        background: rgba(17, 24, 39, 0.7);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 12px;
        padding: 14px 18px;
        margin-bottom: 18px;
    }
    .sleep-ribbon-bar {
        display: flex;
        height: 14px;
        border-radius: 7px;
        overflow: hidden;
        margin-bottom: 10px;
    }
    .sleep-ribbon-legend {
        display: flex;
        gap: 18px;
        font-size: 0.8rem;
        color: #94a3b8;
    }
    .sleep-ribbon-legend span {
        display: flex;
        align-items: center;
        gap: 6px;
    }
    .sleep-ribbon-legend i {
        width: 10px;
        height: 10px;
        border-radius: 3px;
        display: inline-block;
    }

    /* Range Bar Component */
    .range-bar-container {
        background: rgba(17, 24, 39, 0.6);
        border: 1px solid rgba(255, 255, 255, 0.06);
        border-radius: 10px;
        padding: 12px 16px;
        margin-bottom: 16px;
    }
    .range-bar-track {
        position: relative;
        height: 8px;
        background: rgba(255, 255, 255, 0.06);
        border-radius: 4px;
        margin: 10px 0;
    }
    .range-bar-normal {
        position: absolute;
        top: 0;
        bottom: 0;
        background: rgba(16, 185, 129, 0.25);
        border: 1px solid rgba(16, 185, 129, 0.5);
        border-radius: 4px;
    }
    .range-bar-pin {
        position: absolute;
        top: -4px;
        width: 16px;
        height: 16px;
        border-radius: 50%;
        border: 2px solid #ffffff;
        transform: translateX(-50%);
        box-shadow: 0 0 8px rgba(0,0,0,0.6);
    }
    .range-bar-labels {
        display: flex;
        justify-content: space-between;
        font-size: 0.75rem;
        color: #94a3b8;
    }

    /* Section Cards */
    .content-box {
        background: rgba(17, 24, 39, 0.5);
        border: 1px solid rgba(255, 255, 255, 0.06);
        border-radius: 12px;
        padding: 18px;
        margin-bottom: 18px;
    }
</style>
""", unsafe_allow_html=True)


def load_demo_data_action():
    with st.spinner("Generating and ingesting 90-day synthetic dataset..."):
        generate_all_samples(Path("."))
        AppleHealthParser("data/samples/sample_apple_health.xml").parse_and_store()
        MyFitnessPalParser("data/samples/sample_myfitnesspal.csv").parse_and_store()
        QuestDiagnosticsParser("data/samples/sample_quest_lab.pdf").parse_and_store()
        QuestDiagnosticsParser("data/samples/sample_quest_lab.csv").parse_and_store()
        compute_daily_recovery()
        compute_training_load()
    st.sidebar.success("Demo dataset loaded successfully!")
    st.rerun()


# Sidebar Navigation
with st.sidebar:
    st.markdown("""
    <div style="display:flex; align-items:center; gap:10px; margin-bottom:12px;">
        <span style="font-size:1.8rem">⚡</span>
        <div>
            <div style="font-weight:800; font-size:1.15rem; color:#f8fafc; line-height:1.2;">JB-HEALTH</div>
            <div style="font-size:0.75rem; color:#06b6d4; font-weight:600;">INTELLIGENCE PLATFORM</div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    st.markdown("---")

    timeframe = st.selectbox(
        "Analysis Window",
        ["Last 30 Days", "Last 90 Days", "Last 7 Days", "All History"],
        index=0
    )
    days_map = {"Last 7 Days": 7, "Last 30 Days": 30, "Last 90 Days": 90, "All History": 3650}
    max_days = days_map[timeframe]

    st.markdown("---")
    st.markdown("##### Quick Actions")
    if st.button("🚀 Load Demo / Sample Data", use_container_width=True):
        load_demo_data_action()

    if st.button("🔄 Recompute Baselines", use_container_width=True):
        with st.spinner("Recomputing metrics..."):
            compute_daily_recovery()
            compute_training_load()
        st.success("Baselines updated!")
        st.rerun()

    if st.button("🗑️ Clear Local Database", use_container_width=True):
        reset_db()
        st.warning("Database cleared.")
        st.rerun()

    st.markdown("---")
    st.markdown("""
    <div style="font-size:0.75rem; color:#64748b; line-height:1.4;">
        🔒 <b>Zero PHI Exposure</b>: All data is processed and stored 100% locally in SQLite. Git blocks all personal files.
    </div>
    """, unsafe_allow_html=True)

# Master Data Loading
df_master = get_integrated_daily_df()
df_bio = load_table_df("biomarker_records")
df_workouts = load_table_df("workout_records")

if not df_master.empty:
    cutoff = datetime.today() - timedelta(days=max_days)
    df_filtered = df_master[df_master["date"] >= cutoff].sort_values("date")
else:
    df_filtered = pd.DataFrame()

# Hero Header
rec_count = len(df_filtered) if not df_filtered.empty else 0
st.markdown(f"""
<div class="hero-banner">
    <div>
        <h1 class="hero-title"><span>⚡</span> Health, Recovery & Performance Intelligence</h1>
        <div class="hero-subtitle">Unified Apple Health • MyFitnessPal Nutrition • Quest Diagnostics Biomarkers</div>
    </div>
    <div class="hero-badge">
        <div class="pulse-dot"></div>
        <span>{'Live Local Mode • ' + str(rec_count) + ' Days Active' if rec_count > 0 else 'Database Ready'}</span>
    </div>
</div>
""", unsafe_allow_html=True)

# Tabs
tab_recovery, tab_sleep, tab_perf, tab_labs, tab_nutrition, tab_correlations, tab_builder, tab_import = st.tabs([
    "⚡ Readiness & Recovery",
    "🌙 Sleep Architecture",
    "🏋️ Performance & Training Load",
    "🧪 Quest Blood Work & Labs",
    "🥗 Nutrition & Fueling",
    "🔍 Lifestyle Correlations",
    "📊 Custom Dashboard",
    "📁 Data Import"
])

if df_master.empty:
    st.info("👋 **Welcome to JB-Health-Project!** Click **'🚀 Load Demo / Sample Data'** in the left sidebar to preview the dashboard with realistic synthetic data, or visit the **'📁 Data Import'** tab to upload your own files.")


# -------------------------------------------------------------------------------------------------
# TAB 1: READINESS & RECOVERY
# -------------------------------------------------------------------------------------------------
with tab_recovery:
    if not df_filtered.empty:
        latest = df_filtered.iloc[-1]
        prev = df_filtered.iloc[-2] if len(df_filtered) > 1 else latest

        col_g, c1, c2, c3, c4 = st.columns([1.2, 1, 1, 1, 1])
        with col_g:
            st.plotly_chart(plot_recovery_gauge(latest.get("recovery_score", 70.0)), use_container_width=True)

        with c1:
            hrv_val = latest.get("hrv_sdnn", np.nan)
            hrv_base = latest.get("hrv_7d_baseline", np.nan)
            hrv_diff = (hrv_val - hrv_base) if pd.notna(hrv_val) and pd.notna(hrv_base) else 0
            diff_str = f"{hrv_diff:+.1f} ms" if pd.notna(hrv_val) else ""
            delta_t = "good" if hrv_diff >= 0 else "bad"
            card_html = render_stat_card(
                title="Heart Rate Variability",
                value=f"{hrv_val:.1f}" if pd.notna(hrv_val) else "--",
                unit="ms",
                delta=f"{diff_str} vs base",
                delta_type=delta_t,
                subtitle="Parasympathetic Autonomic Balance",
                icon="💓"
            )
            st.markdown(card_html, unsafe_allow_html=True)

        with c2:
            rhr_val = latest.get("resting_hr", np.nan)
            rhr_base = latest.get("resting_hr_7d_baseline", np.nan)
            rhr_diff = (rhr_val - rhr_base) if pd.notna(rhr_val) and pd.notna(rhr_base) else 0
            diff_str = f"{rhr_diff:+.1f} bpm" if pd.notna(rhr_val) else ""
            delta_t = "good" if rhr_diff <= 0 else "bad"
            card_html = render_stat_card(
                title="Resting Heart Rate",
                value=f"{rhr_val:.1f}" if pd.notna(rhr_val) else "--",
                unit="bpm",
                delta=f"{diff_str} vs base",
                delta_type=delta_t,
                subtitle="Cardiovascular Rest State",
                icon="❤️"
            )
            st.markdown(card_html, unsafe_allow_html=True)

        with c3:
            sleep_hours = latest.get("total_sleep_hours", 0)
            sleep_target = targets.get("sleep_hours_target", 8.0)
            s_diff = sleep_hours - sleep_target
            diff_str = f"{s_diff:+.1f}h"
            delta_t = "good" if s_diff >= 0 else "warn"
            card_html = render_stat_card(
                title="Last Night Sleep",
                value=f"{sleep_hours:.1f}",
                unit="hrs",
                delta=f"{diff_str} vs target",
                delta_type=delta_t,
                subtitle=f"Goal: {sleep_target} hrs",
                icon="🌙"
            )
            st.markdown(card_html, unsafe_allow_html=True)

        with c4:
            debt = latest.get("sleep_debt_hours", 0)
            debt_delta = "Optimal" if debt < 1.0 else ("Moderate" if debt < 3.0 else "High")
            delta_t = "good" if debt < 1.0 else ("warn" if debt < 3.0 else "bad")
            card_html = render_stat_card(
                title="Sleep Debt",
                value=f"{debt:.1f}",
                unit="hrs",
                delta=debt_delta,
                delta_type=delta_t,
                subtitle="Rolling 7-day deficit",
                icon="⏳"
            )
            st.markdown(card_html, unsafe_allow_html=True)

        # Synchronized Trend Visuals
        c_left, c_right = st.columns(2)
        with c_left:
            fig_rec = px.line(
                df_filtered, x="date", y="recovery_score",
                markers=True, line_shape="spline",
                color_discrete_sequence=[COLORS["primary_light"]]
            )
            fig_rec.add_hrect(y0=67, y1=100, fillcolor="rgba(16,185,129,0.08)", line_width=0, annotation_text="Optimal Readiness", annotation_position="top left", annotation_font=dict(size=9, color=COLORS["success_light"]))
            fig_rec.add_hrect(y0=34, y1=66, fillcolor="rgba(245,158,11,0.06)", line_width=0, annotation_text="Moderate Recovery", annotation_position="top left", annotation_font=dict(size=9, color=COLORS["warning_light"]))
            fig_rec.add_hrect(y0=0, y1=33, fillcolor="rgba(244,63,94,0.06)", line_width=0, annotation_text="High Fatigue", annotation_position="top left", annotation_font=dict(size=9, color=COLORS["danger_light"]))
            fig_rec = apply_dark_layout(fig_rec, title="Physiological Readiness Score (%)", height=340)
            fig_rec.update_yaxes(range=[0, 100], title="Recovery Score (%)")
            fig_rec.update_traces(line=dict(width=2.5), marker=dict(size=6, line=dict(color="#ffffff", width=1)))
            st.plotly_chart(fig_rec, use_container_width=True)

        with c_right:
            st.plotly_chart(plot_hrv_trend(df_filtered), use_container_width=True)

        # Full-width Resting Heart Rate
        fig_rhr = px.line(
            df_filtered, x="date", y="resting_hr",
            markers=True, line_shape="spline",
            color_discrete_sequence=[COLORS["danger_light"]]
        )
        if "resting_hr_7d_baseline" in df_filtered.columns:
            fig_rhr.add_scatter(
                x=df_filtered["date"], y=df_filtered["resting_hr_7d_baseline"],
                mode="lines", name="14d Baseline", line=dict(color="rgba(251, 113, 133, 0.7)", width=2, dash="dash")
            )
        fig_rhr = apply_dark_layout(fig_rhr, title="Resting Heart Rate & Baseline Progression", height=300)
        fig_rhr.update_yaxes(title="Resting HR (bpm)")
        fig_rhr.update_traces(line=dict(width=2.2), marker=dict(size=5))
        st.plotly_chart(fig_rhr, use_container_width=True)
    else:
        st.write("No recovery records loaded yet.")

# -------------------------------------------------------------------------------------------------
# TAB 2: SLEEP ARCHITECTURE
# -------------------------------------------------------------------------------------------------
with tab_sleep:
    if not df_filtered.empty and "total_sleep_hours" in df_filtered.columns:
        s_col1, s_col2, s_col3, s_col4 = st.columns(4)
        avg_sleep = df_filtered["total_sleep_hours"].mean()
        avg_deep = df_filtered["deep_sleep_hours"].mean()
        avg_rem = df_filtered["rem_sleep_hours"].mean()
        deep_pct = (avg_deep / avg_sleep * 100) if avg_sleep > 0 else 0
        rem_pct = (avg_rem / avg_sleep * 100) if avg_sleep > 0 else 0
        core_pct = max(0.0, 100.0 - (deep_pct + rem_pct + 7.0))
        awake_pct = 7.0

        with s_col1:
            diff_target = avg_sleep - targets.get("sleep_hours_target", 8.0)
            st.markdown(render_stat_card(
                title="Avg Sleep Duration",
                value=f"{avg_sleep:.2f}",
                unit="hrs",
                delta=f"{diff_target:+.2f}h vs goal",
                delta_type="good" if diff_target >= 0 else "warn",
                subtitle="Nightly average duration",
                icon="🌙"
            ), unsafe_allow_html=True)

        with s_col2:
            st.markdown(render_stat_card(
                title="Deep Sleep %",
                value=f"{deep_pct:.1f}",
                unit="%",
                delta="Optimal (15-25%)" if 15 <= deep_pct <= 25 else "Attention",
                delta_type="good" if 15 <= deep_pct <= 25 else "warn",
                subtitle="Physical recovery & cellular repair",
                icon="🧠"
            ), unsafe_allow_html=True)

        with s_col3:
            st.markdown(render_stat_card(
                title="REM Sleep %",
                value=f"{rem_pct:.1f}",
                unit="%",
                delta="Optimal (20-25%)" if 20 <= rem_pct <= 25 else "Attention",
                delta_type="good" if 20 <= rem_pct <= 25 else "warn",
                subtitle="Cognitive restoration & memory",
                icon="⚡"
            ), unsafe_allow_html=True)

        with s_col4:
            avg_score = df_filtered["sleep_score"].mean()
            st.markdown(render_stat_card(
                title="Sleep Quality Score",
                value=f"{avg_score:.1f}",
                unit="/100",
                delta="Balanced" if avg_score >= 75 else "Sub-optimal",
                delta_type="good" if avg_score >= 75 else "warn",
                subtitle="Architecture composite index",
                icon="⭐"
            ), unsafe_allow_html=True)

        # Continuous Stage Distribution Ribbon
        st.markdown(render_sleep_ribbon(deep_pct, rem_pct, core_pct, awake_pct), unsafe_allow_html=True)

        # Timeline
        st.plotly_chart(plot_sleep_stages_timeline(df_filtered), use_container_width=True)

        # Sleep Debt
        fig_debt = px.area(
            df_filtered, x="date", y="sleep_debt_hours",
            color_discrete_sequence=["rgba(245, 158, 11, 0.7)"]
        )
        fig_debt = apply_dark_layout(fig_debt, title="Cumulative Sleep Debt Accumulation (Hours Behind Target)", height=280)
        fig_debt.update_yaxes(title="Sleep Debt (Hours)")
        fig_debt.update_traces(line=dict(color=COLORS["warning"], width=2))
        st.plotly_chart(fig_debt, use_container_width=True)
    else:
        st.write("No sleep records available.")

# -------------------------------------------------------------------------------------------------
# TAB 3: PERFORMANCE & TRAINING LOAD
# -------------------------------------------------------------------------------------------------
with tab_perf:
    if not df_filtered.empty and "training_stress_balance" in df_filtered.columns:
        latest_tsb = df_filtered["training_stress_balance"].iloc[-1]
        tsb_cat = get_training_stress_category(latest_tsb)
        latest_atl = df_filtered["training_load_atl"].iloc[-1]
        latest_ctl = df_filtered["training_load_ctl"].iloc[-1]

        p_col1, p_col2, p_col3, p_col4 = st.columns(4)
        with p_col1:
            st.markdown(render_stat_card(
                title="Training Stress Balance",
                value=f"{latest_tsb:+.1f}",
                delta=tsb_cat['zone'],
                delta_type="good" if tsb_cat['zone'] in ('Peak', 'Fresh') else ("warn" if tsb_cat['zone'] == 'Building' else 'bad'),
                subtitle=tsb_cat['status'],
                icon="⚖️"
            ), unsafe_allow_html=True)

        with p_col2:
            st.markdown(render_stat_card(
                title="Acute Load (Fatigue)",
                value=f"{latest_atl:.1f}",
                unit="pts",
                delta="7-Day EMA",
                delta_type="neutral",
                subtitle="Short-term training fatigue",
                icon="🔥"
            ), unsafe_allow_html=True)

        with p_col3:
            st.markdown(render_stat_card(
                title="Chronic Load (Fitness)",
                value=f"{latest_ctl:.1f}",
                unit="pts",
                delta="28-Day EMA",
                delta_type="neutral",
                subtitle="Aerobic base work capacity",
                icon="🛡️"
            ), unsafe_allow_html=True)

        with p_col4:
            acwr = (latest_atl / latest_ctl) if latest_ctl > 0 else 1.0
            acwr_status = "Optimal" if 0.8 <= acwr <= 1.3 else ("Caution" if acwr < 1.5 else "High Risk")
            acwr_dt = "good" if 0.8 <= acwr <= 1.3 else ("warn" if acwr < 1.5 else "bad")
            st.markdown(render_stat_card(
                title="Workload Ratio (ACWR)",
                value=f"{acwr:.2f}",
                delta=acwr_status,
                delta_type=acwr_dt,
                subtitle="Sweet spot: 0.80 - 1.30",
                icon="📊"
            ), unsafe_allow_html=True)

        # Coaching recommendation banner
        st.markdown(f"""
        <div style="background:linear-gradient(90deg, rgba(6,182,212,0.1) 0%, rgba(17,24,39,0.8) 100%); border-left:4px solid {tsb_cat['color']}; padding:12px 18px; border-radius:8px; margin-bottom:18px;">
            <div style="font-weight:700; color:{tsb_cat['color']}; font-size:0.85rem; text-transform:uppercase; letter-spacing:0.05em;">Performance Prescription • {tsb_cat['status']}</div>
            <div style="color:#f8fafc; font-size:0.9rem; margin-top:3px;">{tsb_cat['message']}</div>
        </div>
        """, unsafe_allow_html=True)

        st.plotly_chart(plot_training_load_tsb(df_filtered), use_container_width=True)

        # Workouts breakdown
        w_left, w_right = st.columns(2)
        with w_left:
            fig_act = px.bar(
                df_filtered, x="date", y="active_calories",
                color_discrete_sequence=[COLORS["primary_light"]]
            )
            act_goal = targets.get("daily_active_calories", 600)
            fig_act.add_hline(y=act_goal, line_dash="dash", line_color=COLORS["warning"], annotation_text=f"Target: {act_goal} kcal", annotation_position="top right")
            fig_act = apply_dark_layout(fig_act, title="Daily Active Calories Burned (kcal)", height=320)
            fig_act.update_yaxes(title="Active kcal")
            st.plotly_chart(fig_act, use_container_width=True)

        with w_right:
            if not df_workouts.empty:
                type_counts = df_workouts["activity_type"].value_counts().reset_index()
                type_counts.columns = ["Activity", "Count"]
                fig_pie = px.pie(
                    type_counts, names="Activity", values="Count",
                    hole=0.55,
                    color_discrete_sequence=[COLORS["primary"], COLORS["purple"], COLORS["success"], COLORS["warning"], COLORS["danger"]]
                )
                fig_pie = apply_dark_layout(fig_pie, title="Workout Discipline Distribution", height=320)
                st.plotly_chart(fig_pie, use_container_width=True)
            else:
                st.write("No workouts logged.")

        if not df_workouts.empty:
            st.markdown("##### Recent Workout Sessions")
            st.dataframe(
                df_workouts[["date", "activity_type", "duration_minutes", "calories_burned", "distance_km"]].tail(10).sort_values("date", ascending=False),
                use_container_width=True,
                hide_index=True
            )
    else:
        st.write("No performance records loaded.")


# -------------------------------------------------------------------------------------------------
# TAB 4: QUEST DIAGNOSTICS BLOOD WORK & BIOMARKERS
# -------------------------------------------------------------------------------------------------
with tab_labs:
    if not df_bio.empty:
        # Out-of-range alert banner
        out_of_range = df_bio[df_bio["flag"].isin(["HIGH", "LOW", "CRITICAL"])].sort_values("date", ascending=False)
        if not out_of_range.empty:
            latest_date = out_of_range["date"].max()
            recent_flags = out_of_range[out_of_range["date"] == latest_date]
            flag_items = [f"<b>{r['test_name']}</b>: {r['value']} {r['unit']} (<span style='color:#fb7185;font-weight:700'>{r['flag']}</span>)" for _, r in recent_flags.iterrows()]
            st.markdown(f"""
            <div style="background:rgba(244,63,94,0.1); border:1px solid rgba(244,63,94,0.3); border-radius:12px; padding:12px 18px; margin-bottom:18px;">
                <div style="font-weight:700; color:#fb7185; font-size:0.85rem; text-transform:uppercase; letter-spacing:0.05em;">⚠️ Out of Range Biomarkers on {latest_date}</div>
                <div style="color:#f8fafc; font-size:0.88rem; margin-top:4px;">{' &nbsp;•&nbsp; '.join(flag_items)}</div>
            </div>
            """, unsafe_allow_html=True)

        categories = ["All Categories"] + sorted(df_bio["category"].dropna().unique().tolist())
        sel_cat = st.selectbox("Filter by Clinical Panel", categories)

        sub_bio = df_bio if sel_cat == "All Categories" else df_bio[df_bio["category"] == sel_cat]
        available_tests = sorted(sub_bio["test_name"].dropna().unique().tolist())

        if available_tests:
            col_sel, col_empty = st.columns([1.5, 2.5])
            with col_sel:
                selected_test = st.selectbox("Select Biomarker to Inspect", available_tests)

            test_history = df_bio[df_bio["test_name"] == selected_test].sort_values("date")
            if not test_history.empty:
                latest_val = test_history["value"].iloc[-1]
                latest_flag = test_history["flag"].iloc[-1]
                unit = test_history["unit"].iloc[-1] or ""
                ref_low = test_history["ref_low"].iloc[-1]
                ref_high = test_history["ref_high"].iloc[-1]
                
                # Visual Range Bar
                st.markdown(render_biomarker_range_bar(latest_val, ref_low, ref_high, unit, latest_flag), unsafe_allow_html=True)

            st.plotly_chart(plot_biomarker_trends(df_bio, selected_test), use_container_width=True)

            # Key Clinical Ratios
            st.markdown("##### Clinical Health Ratios")
            r_col1, r_col2, r_col3 = st.columns(3)
            with r_col1:
                trig = df_bio[df_bio["test_name"].str.contains("TRIGLYCERIDE", case=False, na=False)]["value"]
                hdl = df_bio[df_bio["test_name"].str.contains("HDL", case=False, na=False)]["value"]
                if not trig.empty and not hdl.empty:
                    ratio = trig.iloc[-1] / hdl.iloc[-1]
                    ratio_status = "Optimal (<2.0)" if ratio < 2.0 else ("Moderate" if ratio < 3.0 else "Elevated")
                    delta_t = "good" if ratio < 2.0 else ("warn" if ratio < 3.0 else "bad")
                    st.markdown(render_stat_card(
                        title="Triglyceride / HDL Ratio",
                        value=f"{ratio:.2f}",
                        delta=ratio_status,
                        delta_type=delta_t,
                        subtitle="Insulin sensitivity & metabolic flexibility",
                        icon="🧪"
                    ), unsafe_allow_html=True)

            with r_col2:
                chol = df_bio[df_bio["test_name"].str.contains("CHOLESTEROL, TOTAL", case=False, na=False)]["value"]
                if not chol.empty and not hdl.empty:
                    ratio = chol.iloc[-1] / hdl.iloc[-1]
                    ratio_status = "Optimal (<3.5)" if ratio < 3.5 else "Elevated"
                    delta_t = "good" if ratio < 3.5 else "warn"
                    st.markdown(render_stat_card(
                        title="Cholesterol / HDL Ratio",
                        value=f"{ratio:.2f}",
                        delta=ratio_status,
                        delta_type=delta_t,
                        subtitle="Cardiovascular lipid profile",
                        icon="🫀"
                    ), unsafe_allow_html=True)

            with r_col3:
                crp = df_bio[df_bio["test_name"].str.contains("CRP", case=False, na=False)]["value"]
                if not crp.empty:
                    crp_val = crp.iloc[-1]
                    crp_status = "Optimal (<1.0)" if crp_val < 1.0 else ("Elevated" if crp_val < 3.0 else "High")
                    delta_t = "good" if crp_val < 1.0 else ("warn" if crp_val < 3.0 else "bad")
                    st.markdown(render_stat_card(
                        title="Systemic hs-CRP",
                        value=f"{crp_val:.2f}",
                        unit="mg/L",
                        delta=crp_status,
                        delta_type=delta_t,
                        subtitle="Cardiovascular inflammation & recovery",
                        icon="🔥"
                    ), unsafe_allow_html=True)

            st.markdown("##### Complete Lab History")
            st.dataframe(
                df_bio[["date", "category", "test_name", "value", "unit", "ref_low", "ref_high", "flag"]].sort_values(["date", "test_name"], ascending=[False, True]),
                use_container_width=True,
                hide_index=True
            )
        else:
            st.write("No biomarker records for this category.")
    else:
        st.write("No Quest Diagnostics lab results imported yet. Upload a Quest PDF report in the Data Import tab.")

# -------------------------------------------------------------------------------------------------
# TAB 5: NUTRITION & FUELING
# -------------------------------------------------------------------------------------------------
with tab_nutrition:
    if not df_filtered.empty and "calories_consumed" in df_filtered.columns:
        n_col1, n_col2, n_col3, n_col4 = st.columns(4)
        avg_cals = df_filtered["calories_consumed"].mean()
        avg_prot = df_filtered["protein_consumed"].mean()
        avg_carbs = df_filtered["carbs_consumed"].mean()
        avg_fat = df_filtered["fat_consumed"].mean()

        with n_col1:
            st.markdown(render_stat_card(
                title="Avg Daily Calories",
                value=f"{avg_cals:.0f}",
                unit="kcal",
                delta="Daily Intake",
                delta_type="neutral",
                subtitle="Energy intake from dietary logs",
                icon="⚡"
            ), unsafe_allow_html=True)

        with n_col2:
            prot_target = targets.get("daily_protein_g_target", 160.0)
            prot_diff = avg_prot - prot_target
            st.markdown(render_stat_card(
                title="Avg Daily Protein",
                value=f"{avg_prot:.1f}",
                unit="g",
                delta=f"{prot_diff:+.1f}g vs target",
                delta_type="good" if prot_diff >= 0 else "warn",
                subtitle=f"Goal: {prot_target} g/day",
                icon="🥩"
            ), unsafe_allow_html=True)

        with n_col3:
            st.markdown(render_stat_card(
                title="Avg Daily Carbs",
                value=f"{avg_carbs:.1f}",
                unit="g",
                delta="Carbohydrate",
                delta_type="neutral",
                subtitle="Glycogen storage & energy",
                icon="🌾"
            ), unsafe_allow_html=True)

        with n_col4:
            st.markdown(render_stat_card(
                title="Avg Daily Fat",
                value=f"{avg_fat:.1f}",
                unit="g",
                delta="Dietary Lipids",
                delta_type="neutral",
                subtitle="Hormone & cellular health",
                icon="🥑"
            ), unsafe_allow_html=True)

        fig_macros = go.Figure()
        fig_macros.add_trace(go.Bar(x=df_filtered["date"], y=df_filtered["protein_consumed"], name="Protein (g)", marker_color=COLORS["success"]))
        fig_macros.add_trace(go.Bar(x=df_filtered["date"], y=df_filtered["carbs_consumed"], name="Carbohydrates (g)", marker_color=COLORS["info"]))
        fig_macros.add_trace(go.Bar(x=df_filtered["date"], y=df_filtered["fat_consumed"], name="Fat (g)", marker_color=COLORS["warning"]))
        fig_macros.update_layout(barmode="stack")
        fig_macros = apply_dark_layout(fig_macros, title="Daily Macronutrient Distribution (Grams)", height=340)
        fig_macros.update_yaxes(title="Grams")
        st.plotly_chart(fig_macros, use_container_width=True)

        if "active_calories" in df_filtered.columns:
            fig_eng = go.Figure()
            fig_eng.add_trace(go.Scatter(x=df_filtered["date"], y=df_filtered["calories_consumed"], mode="lines", name="Dietary Intake", line=dict(color=COLORS["success_light"], width=2.2, shape="spline")))
            fig_eng.add_trace(go.Scatter(x=df_filtered["date"], y=df_filtered["active_calories"], mode="lines", name="Active Expenditure", line=dict(color=COLORS["danger_light"], width=2.2, shape="spline")))
            fig_eng = apply_dark_layout(fig_eng, title="Energy Balance: Intake vs Active Burn (kcal)", height=320)
            fig_eng.update_yaxes(title="Calories (kcal)")
            st.plotly_chart(fig_eng, use_container_width=True)
    else:
        st.write("No nutrition records available.")

# -------------------------------------------------------------------------------------------------
# TAB 6: LIFESTYLE CORRELATIONS & INSIGHTS ENGINE
# -------------------------------------------------------------------------------------------------
with tab_correlations:
    if not df_filtered.empty and len(df_filtered) >= 10:
        candidate_cols = [
            "total_sleep_hours", "deep_sleep_hours", "rem_sleep_hours", "sleep_score",
            "active_calories", "steps", "exercise_minutes", "training_stress_balance",
            "calories_consumed", "protein_consumed", "hrv_sdnn", "resting_hr", "recovery_score"
        ]
        available_num_cols = [c for c in candidate_cols if c in df_filtered.columns and df_filtered[c].notna().sum() >= 10]

        corr_df = compute_correlation_matrix(df_filtered, available_num_cols)
        if not corr_df.empty:
            fig_heat = px.imshow(
                corr_df,
                text_auto=".2f",
                aspect="auto",
                color_continuous_scale="RdBu_r",
                zmin=-1, zmax=1
            )
            fig_heat = apply_dark_layout(fig_heat, title="Multivariate Pearson Correlation Matrix", height=460)
            st.plotly_chart(fig_heat, use_container_width=True)

        st.markdown("##### Pairwise Regression Deep-Dive")
        col_x, col_y = st.columns(2)
        with col_x:
            x_var = st.selectbox("Independent Input (X)", available_num_cols, index=0)
        with col_y:
            default_y_idx = available_num_cols.index("recovery_score") if "recovery_score" in available_num_cols else 1
            y_var = st.selectbox("Dependent Outcome (Y)", available_num_cols, index=default_y_idx)

        if x_var != y_var:
            stats_res = compute_pairwise_correlation(df_filtered[x_var], df_filtered[y_var])
            sig_badge = "✅ Statistically Significant (p < 0.05)" if stats_res["is_significant"] else "ℹ️ Exploratory Trend (p ≥ 0.05)"
            st.markdown(f"""
            <div style="background:rgba(6,182,212,0.08); border:1px solid rgba(6,182,212,0.25); border-radius:10px; padding:12px 16px; margin-bottom:14px;">
                <b>Insight</b>: {stats_res['description']} &nbsp;|&nbsp; {sig_badge}
            </div>
            """, unsafe_allow_html=True)
            st.plotly_chart(plot_correlation_scatter(df_filtered, x_var, y_var), use_container_width=True)
    else:
        st.write("Insufficient data for correlation calculations. Ingest at least 10 days of health records.")

# -------------------------------------------------------------------------------------------------
# TAB 7: CUSTOM DASHBOARD BUILDER
# -------------------------------------------------------------------------------------------------
with tab_builder:
    if not df_filtered.empty:
        all_numeric = df_filtered.select_dtypes(include=[np.number]).columns.tolist()
        b_c1, b_c2, b_c3, b_c4 = st.columns(4)
        with b_c1:
            chart_type = st.selectbox("Chart Type", ["Line Chart", "Bar Chart", "Scatter Plot", "Area Chart", "Box Plot"])
        with b_c2:
            x_axis = st.selectbox("X-Axis", ["date"] + all_numeric)
        with b_c3:
            y_axis = st.selectbox("Y-Axis", all_numeric, index=min(1, len(all_numeric) - 1))
        with b_c4:
            color_dim = st.selectbox("Color / Dimension (Optional)", ["None"] + all_numeric)

        color_arg = None if color_dim == "None" else color_dim

        if chart_type == "Line Chart":
            fig_custom = px.line(df_filtered, x=x_axis, y=y_axis, color=color_arg, markers=True)
        elif chart_type == "Bar Chart":
            fig_custom = px.bar(df_filtered, x=x_axis, y=y_axis, color=color_arg)
        elif chart_type == "Scatter Plot":
            fig_custom = px.scatter(df_filtered, x=x_axis, y=y_axis, color=color_arg, trendline="ols")
        elif chart_type == "Area Chart":
            fig_custom = px.area(df_filtered, x=x_axis, y=y_axis, color=color_arg)
        elif chart_type == "Box Plot":
            fig_custom = px.box(df_filtered, x=x_axis, y=y_axis, color=color_arg)

        fig_custom = apply_dark_layout(fig_custom, title=f"Custom Visualizer: {y_axis} vs {x_axis}", height=400)
        st.plotly_chart(fig_custom, use_container_width=True)
    else:
        st.write("No data available to plot.")

# -------------------------------------------------------------------------------------------------
# TAB 8: DATA IMPORT & FILE MANAGEMENT
# -------------------------------------------------------------------------------------------------
with tab_import:
    st.markdown("""
    <div style="margin-bottom:16px;">
        <div style="font-size:1.1rem; font-weight:700; color:#f8fafc;">Local Data Ingestion Engine</div>
        <div style="font-size:0.85rem; color:#94a3b8;">Drop in your personal exports. All data is processed completely on your local machine.</div>
    </div>
    """, unsafe_allow_html=True)

    u_col1, u_col2, u_col3 = st.columns(3)

    with u_col1:
        st.markdown("""
        <div style="background:rgba(17,24,39,0.7); border:1px solid rgba(255,255,255,0.08); border-radius:12px; padding:16px; min-height:220px;">
            <div style="font-weight:700; color:#f8fafc; font-size:0.95rem; margin-bottom:4px;">🍎 Apple Health</div>
            <div style="font-size:0.78rem; color:#94a3b8; margin-bottom:10px;">Upload <code>export.zip</code> or <code>export.xml</code> from iPhone.</div>
        </div>
        """, unsafe_allow_html=True)
        ah_file = st.file_uploader("Upload Apple Health", type=["zip", "xml"], key="ah_up", label_visibility="collapsed")
        if ah_file and st.button("Process Apple Health", use_container_width=True):
            with st.spinner("Streaming XML records..."):
                suffix = ".zip" if ah_file.name.endswith(".zip") else ".xml"
                with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                    tmp.write(ah_file.getvalue())
                    tmp_path = tmp.name
                try:
                    counts = AppleHealthParser(tmp_path).parse_and_store()
                    compute_daily_recovery()
                    compute_training_load()
                    st.success(f"Parsed: {counts['sleep']} sleep, {counts['hrv']} HRV, {counts['workouts']} workouts.")
                    st.rerun()
                finally:
                    os.unlink(tmp_path)

    with u_col2:
        st.markdown("""
        <div style="background:rgba(17,24,39,0.7); border:1px solid rgba(255,255,255,0.08); border-radius:12px; padding:16px; min-height:220px;">
            <div style="font-weight:700; color:#f8fafc; font-size:0.95rem; margin-bottom:4px;">🥗 MyFitnessPal</div>
            <div style="font-size:0.78rem; color:#94a3b8; margin-bottom:10px;">Upload nutrition summary <code>.csv</code> export.</div>
        </div>
        """, unsafe_allow_html=True)
        mfp_file = st.file_uploader("Upload MFP CSV", type=["csv"], key="mfp_up", label_visibility="collapsed")
        if mfp_file and st.button("Process MyFitnessPal", use_container_width=True):
            with st.spinner("Parsing nutrition records..."):
                with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as tmp:
                    tmp.write(mfp_file.getvalue())
                    tmp_path = tmp.name
                try:
                    cnt = MyFitnessPalParser(tmp_path).parse_and_store()
                    st.success(f"Parsed {cnt} MyFitnessPal records.")
                    st.rerun()
                finally:
                    os.unlink(tmp_path)

    with u_col3:
        st.markdown("""
        <div style="background:rgba(17,24,39,0.7); border:1px solid rgba(255,255,255,0.08); border-radius:12px; padding:16px; min-height:220px;">
            <div style="font-weight:700; color:#f8fafc; font-size:0.95rem; margin-bottom:4px;">🧪 Quest Diagnostics</div>
            <div style="font-size:0.78rem; color:#94a3b8; margin-bottom:10px;">Upload lab report <code>.pdf</code> or structured <code>.csv</code>.</div>
        </div>
        """, unsafe_allow_html=True)
        quest_file = st.file_uploader("Upload Quest Report", type=["pdf", "csv"], key="quest_up", label_visibility="collapsed")
        if quest_file and st.button("Process Quest Report", use_container_width=True):
            with st.spinner("Extracting biomarker records..."):
                suffix = ".pdf" if quest_file.name.endswith(".pdf") else ".csv"
                with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                    tmp.write(quest_file.getvalue())
                    tmp_path = tmp.name
                try:
                    cnt = QuestDiagnosticsParser(tmp_path).parse_and_store()
                    st.success(f"Extracted {cnt} biomarkers from Quest report!")
                    st.rerun()
                finally:
                    os.unlink(tmp_path)

    st.markdown("---")
    st.markdown("##### Local Database Inventory")
    session = get_session()()
    try:
        db_stats = [
            {"Data Domain": "Sleep Stages (Deep, REM, Core)", "Records": session.query(SleepRecord).count()},
            {"Data Domain": "Heart Records (HRV, RHR)", "Records": session.query(HeartRecord).count()},
            {"Data Domain": "Daily Activity Summaries", "Records": session.query(ActivityRecord).count()},
            {"Data Domain": "Workout Sessions (Apple Health)", "Records": session.query(WorkoutRecord).count()},
            {"Data Domain": "Nutrition Logs (Calories, Macros)", "Records": session.query(NutritionRecord).count()},
            {"Data Domain": "Quest Biomarkers (Blood Work)", "Records": session.query(BiomarkerRecord).count()},
            {"Data Domain": "Computed Daily Intelligence Rows", "Records": session.query(DailySummaryRecord).count()},
        ]
        st.dataframe(pd.DataFrame(db_stats), use_container_width=True, hide_index=True)
    finally:
        session.close()
