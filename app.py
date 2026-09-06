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
    plot_training_load_tsb, plot_biomarker_trends, plot_correlation_scatter, COLORS
)

st.set_page_config(
    page_title="JB Health & Performance",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Load config
config_path = Path("config.yaml")
if config_path.exists():
    with open(config_path, "r") as f:
        cfg = yaml.safe_load(f)
else:
    cfg = {
        "targets": {
            "sleep_hours_target": 8.0,
            "daily_active_calories": 600,
            "daily_protein_g_target": 160.0
        }
    }

init_db()

st.markdown("""
<style>
    .metric-card {
        background: #1e293b;
        border-radius: 10px;
        padding: 16px 20px;
        border: 1px solid rgba(148, 163, 184, 0.15);
        margin-bottom: 15px;
    }
    .metric-title {
        color: #94a3b8;
        font-size: 0.85rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 4px;
    }
    .metric-value {
        color: #f8fafc;
        font-size: 1.8rem;
        font-weight: 700;
        line-height: 1.2;
    }
    .metric-subtitle {
        color: #14b8a6;
        font-size: 0.82rem;
        font-weight: 500;
        margin-top: 4px;
    }
    .metric-bad {
        color: #ef4444;
    }
    .metric-warn {
        color: #f59e0b;
    }
    .status-badge {
        display: inline-block;
        padding: 4px 10px;
        border-radius: 6px;
        font-weight: 600;
        font-size: 0.85rem;
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


with st.sidebar:
    st.title("⚡ JB-Health")
    st.caption("Personal Recovery & Health Intelligence")
    st.markdown("---")

    timeframe = st.selectbox(
        "Date Range View",
        ["Last 30 Days", "Last 90 Days", "Last 7 Days", "All History"],
        index=0
    )

    days_map = {"Last 7 Days": 7, "Last 30 Days": 30, "Last 90 Days": 90, "All History": 3650}
    max_days = days_map[timeframe]

    st.markdown("---")
    st.subheader("Data Management")
    if st.button("🚀 Load Demo / Sample Data", use_container_width=True):
        load_demo_data_action()

    if st.button("🔄 Recompute Analytics", use_container_width=True):
        with st.spinner("Recomputing baselines..."):
            compute_daily_recovery()
            compute_training_load()
        st.success("Updated!")
        st.rerun()

    if st.button("🗑️ Clear Local Database", use_container_width=True):
        reset_db()
        st.warning("Database cleared.")
        st.rerun()

    st.markdown("---")
    st.caption("🔒 **Privacy Guarantee**: All data stays strictly in local SQLite. Git repository blocks all raw health exports & PHI.")

df_master = get_integrated_daily_df()
df_bio = load_table_df("biomarker_records")
df_workouts = load_table_df("workout_records")

if not df_master.empty:
    cutoff = datetime.today() - timedelta(days=max_days)
    df_filtered = df_master[df_master["date"] >= cutoff].sort_values("date")
else:
    df_filtered = pd.DataFrame()

st.header("Personal Health & Recovery Dashboard")

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
    st.info("👋 Welcome! Your database is currently empty. Click **'🚀 Load Demo / Sample Data'** in the left sidebar to preview the dashboard with safe synthetic data, or go to the **'📁 Data Import'** tab to upload your own files.")
# -------------------------------------------------------------------------------------------------
# TAB 1: READINESS & RECOVERY
# -------------------------------------------------------------------------------------------------
with tab_recovery:
    if not df_filtered.empty:
        latest = df_filtered.iloc[-1]
        prev = df_filtered.iloc[-2] if len(df_filtered) > 1 else latest

        col_g, c1, c2, c3, c4 = st.columns([1.3, 1, 1, 1, 1])
        with col_g:
            st.plotly_chart(plot_recovery_gauge(latest.get("recovery_score", 70.0)), use_container_width=True)

        with c1:
            hrv_val = latest.get("hrv_sdnn", np.nan)
            hrv_base = latest.get("hrv_7d_baseline", np.nan)
            hrv_diff = (hrv_val - hrv_base) if pd.notna(hrv_val) and pd.notna(hrv_base) else 0
            diff_str = f"{hrv_diff:+.1f} ms vs baseline"
            sub_class = "metric-subtitle" if hrv_diff >= 0 else "metric-subtitle metric-bad"
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-title">Heart Rate Variability</div>
                <div class="metric-value">{hrv_val:.1f} <span style="font-size:1rem;color:#94a3b8">ms</span></div>
                <div class="{sub_class}">{diff_str}</div>
            </div>
            """, unsafe_allow_html=True)

        with c2:
            rhr_val = latest.get("resting_hr", np.nan)
            rhr_base = latest.get("resting_hr_7d_baseline", np.nan)
            rhr_diff = (rhr_val - rhr_base) if pd.notna(rhr_val) and pd.notna(rhr_base) else 0
            diff_str = f"{rhr_diff:+.1f} bpm vs baseline"
            sub_class = "metric-subtitle" if rhr_diff <= 0 else "metric-subtitle metric-bad"
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-title">Resting Heart Rate</div>
                <div class="metric-value">{rhr_val:.1f} <span style="font-size:1rem;color:#94a3b8">bpm</span></div>
                <div class="{sub_class}">{diff_str}</div>
            </div>
            """, unsafe_allow_html=True)

        with c3:
            sleep_hours = latest.get("total_sleep_hours", 0)
            sleep_target = cfg.get("targets", {}).get("sleep_hours_target", 8.0)
            s_diff = sleep_hours - sleep_target
            diff_str = f"{s_diff:+.1f}h vs {sleep_target}h target"
            sub_class = "metric-subtitle" if s_diff >= 0 else "metric-subtitle metric-warn"
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-title">Last Night Sleep</div>
                <div class="metric-value">{sleep_hours:.1f} <span style="font-size:1rem;color:#94a3b8">hrs</span></div>
                <div class="{sub_class}">{diff_str}</div>
            </div>
            """, unsafe_allow_html=True)

        with c4:
            debt = latest.get("sleep_debt_hours", 0)
            debt_color = "metric-subtitle" if debt < 1.0 else ("metric-subtitle metric-warn" if debt < 3.0 else "metric-subtitle metric-bad")
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-title">Cumulative Sleep Debt</div>
                <div class="metric-value">{debt:.1f} <span style="font-size:1rem;color:#94a3b8">hrs</span></div>
                <div class="{debt_color}">{'Optimal' if debt < 1.0 else 'Needs Recovery'}</div>
            </div>
            """, unsafe_allow_html=True)

        c_left, c_right = st.columns(2)
        with c_left:
            fig_rec = px.line(
                df_filtered, x="date", y="recovery_score",
                markers=True, line_shape="spline",
                color_discrete_sequence=[COLORS["primary_light"]]
            )
            fig_rec.add_hrect(y0=67, y1=100, fillcolor="rgba(16,185,129,0.1)", line_width=0, annotation_text="Optimal Recovery")
            fig_rec.add_hrect(y0=34, y1=66, fillcolor="rgba(245,158,11,0.1)", line_width=0, annotation_text="Moderate Recovery")
            fig_rec.add_hrect(y0=0, y1=33, fillcolor="rgba(239,68,68,0.1)", line_width=0, annotation_text="Low / Strain")
            fig_rec = apply_dark_layout(fig_rec, title="Daily Recovery Score Trend", height=350)
            fig_rec.update_yaxes(range=[0, 100], title="Recovery Score (%)")
            st.plotly_chart(fig_rec, use_container_width=True)

        with c_right:
            st.plotly_chart(plot_hrv_trend(df_filtered), use_container_width=True)

        fig_rhr = px.line(
            df_filtered, x="date", y="resting_hr",
            markers=True, line_shape="spline",
            color_discrete_sequence=["#f43f5e"]
        )
        if "resting_hr_7d_baseline" in df_filtered.columns:
            fig_rhr.add_scatter(
                x=df_filtered["date"], y=df_filtered["resting_hr_7d_baseline"],
                mode="lines", name="14d Baseline", line=dict(color="#fb7185", dash="dash")
            )
        fig_rhr = apply_dark_layout(fig_rhr, title="Resting Heart Rate & Baseline Trend", height=320)
        fig_rhr.update_yaxes(title="Resting HR (bpm)")
        st.plotly_chart(fig_rhr, use_container_width=True)
    else:
        st.write("No recovery data loaded yet.")

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

        with s_col1:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-title">Avg Sleep Duration</div>
                <div class="metric-value">{avg_sleep:.2f} <span style="font-size:1rem;color:#94a3b8">hrs</span></div>
                <div class="metric-subtitle">Target: {cfg.get('targets', {}).get('sleep_hours_target', 8.0)} hrs</div>
            </div>
            """, unsafe_allow_html=True)

        with s_col2:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-title">Deep Sleep %</div>
                <div class="metric-value">{deep_pct:.1f}%</div>
                <div class="metric-subtitle">Optimal: 15% - 25%</div>
            </div>
            """, unsafe_allow_html=True)

        with s_col3:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-title">REM Sleep %</div>
                <div class="metric-value">{rem_pct:.1f}%</div>
                <div class="metric-subtitle">Optimal: 20% - 25%</div>
            </div>
            """, unsafe_allow_html=True)

        with s_col4:
            avg_score = df_filtered["sleep_score"].mean()
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-title">Avg Sleep Quality Score</div>
                <div class="metric-value">{avg_score:.1f}</div>
                <div class="metric-subtitle">Quality & Architecture</div>
            </div>
            """, unsafe_allow_html=True)

        st.plotly_chart(plot_sleep_stages_timeline(df_filtered), use_container_width=True)

        fig_debt = px.area(
            df_filtered, x="date", y="sleep_debt_hours",
            color_discrete_sequence=["rgba(245,158,11,0.6)"]
        )
        fig_debt = apply_dark_layout(fig_debt, title="Cumulative Sleep Debt Over Time (Hours Behind Target)", height=300)
        fig_debt.update_yaxes(title="Sleep Debt (Hours)")
        st.plotly_chart(fig_debt, use_container_width=True)
    else:
        st.write("No sleep records available.")

# -------------------------------------------------------------------------------------------------
# TAB 3: PERFORMANCE & TRAINING LOAD
# -------------------------------------------------------------------------------------------------
with tab_perf:
    st.subheader("Workout Performance & Training Stress Balance (TSB)")
    st.caption("Track fitness adaptation, acute fatigue, and peak performance readiness.")

    if not df_filtered.empty and "training_stress_balance" in df_filtered.columns:
        latest_tsb = df_filtered["training_stress_balance"].iloc[-1]
        tsb_cat = get_training_stress_category(latest_tsb)
        latest_atl = df_filtered["training_load_atl"].iloc[-1]
        latest_ctl = df_filtered["training_load_ctl"].iloc[-1]

        p_col1, p_col2, p_col3, p_col4 = st.columns(4)
        with p_col1:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-title">Training Stress Balance (TSB)</div>
                <div class="metric-value" style="color:{tsb_cat['color']}">{latest_tsb:+.1f}</div>
                <div class="metric-subtitle">{tsb_cat['status']}</div>
            </div>
            """, unsafe_allow_html=True)

        with p_col2:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-title">Acute Load (Fatigue - 7d)</div>
                <div class="metric-value">{latest_atl:.1f}</div>
                <div class="metric-subtitle">Short-term training strain</div>
            </div>
            """, unsafe_allow_html=True)

        with p_col3:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-title">Chronic Load (Fitness - 28d)</div>
                <div class="metric-value">{latest_ctl:.1f}</div>
                <div class="metric-subtitle">Aerobic base & work capacity</div>
            </div>
            """, unsafe_allow_html=True)

        with p_col4:
            acwr = (latest_atl / latest_ctl) if latest_ctl > 0 else 1.0
            acwr_color = COLORS["success"] if 0.8 <= acwr <= 1.3 else (COLORS["warning"] if acwr < 1.5 else COLORS["danger"])
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-title">ACWR (Workload Ratio)</div>
                <div class="metric-value" style="color:{acwr_color}">{acwr:.2f}</div>
                <div class="metric-subtitle">Sweet Spot: 0.8 - 1.3</div>
            </div>
            """, unsafe_allow_html=True)

        st.info(f"💡 **Coach's Insight**: {tsb_cat['message']}")

        st.plotly_chart(plot_training_load_tsb(df_filtered), use_container_width=True)

        w_left, w_right = st.columns(2)
        with w_left:
            fig_act = px.bar(
                df_filtered, x="date", y="active_calories",
                color_discrete_sequence=[COLORS["primary_light"]]
            )
            fig_act.add_hline(y=cfg.get("targets", {}).get("daily_active_calories", 600), line_dash="dash", line_color="#f59e0b", annotation_text="Goal")
            fig_act = apply_dark_layout(fig_act, title="Daily Active Calories Burned", height=320)
            fig_act.update_yaxes(title="Active kcal")
            st.plotly_chart(fig_act, use_container_width=True)

        with w_right:
            if not df_workouts.empty:
                type_counts = df_workouts["activity_type"].value_counts().reset_index()
                type_counts.columns = ["Activity", "Count"]
                fig_pie = px.pie(
                    type_counts, names="Activity", values="Count",
                    hole=0.45,
                    color_discrete_sequence=px.colors.qualitative.Prism
                )
                fig_pie = apply_dark_layout(fig_pie, title="Workout Activity Distribution", height=320)
                st.plotly_chart(fig_pie, use_container_width=True)
            else:
                st.write("No individual workouts logged.")

        if not df_workouts.empty:
            st.subheader("Recent Workout Sessions")
            st.dataframe(
                df_workouts[["date", "activity_type", "duration_minutes", "calories_burned", "distance_km"]].tail(10).sort_values("date", ascending=False),
                use_container_width=True,
                hide_index=True
            )
    else:
        st.write("No performance or workout records loaded.")
# -------------------------------------------------------------------------------------------------
# TAB 4: QUEST DIAGNOSTICS BLOOD WORK & BIOMARKERS
# -------------------------------------------------------------------------------------------------
with tab_labs:
    st.subheader("Quest Diagnostics Blood Work & Biomarker Analytics")
    st.caption("Track metabolic health, hormone levels, lipid particles, and systemic recovery biomarkers over time.")

    if not df_bio.empty:
        out_of_range = df_bio[df_bio["flag"].isin(["HIGH", "LOW", "CRITICAL"])].sort_values("date", ascending=False)
        if not out_of_range.empty:
            latest_date = out_of_range["date"].max()
            recent_flags = out_of_range[out_of_range["date"] == latest_date]
            flag_items = [f"**{r['test_name']}**: {r['value']} {r['unit']} ({r['flag']})" for _, r in recent_flags.iterrows()]
            st.warning(f"⚠️ **Out of Range Biomarkers on {latest_date}**: " + " | ".join(flag_items))

        categories = ["All Categories"] + sorted(df_bio["category"].dropna().unique().tolist())
        sel_cat = st.selectbox("Filter by Clinical Panel", categories)

        sub_bio = df_bio if sel_cat == "All Categories" else df_bio[df_bio["category"] == sel_cat]
        available_tests = sorted(sub_bio["test_name"].dropna().unique().tolist())

        if available_tests:
            col_sel, col_stats = st.columns([1.5, 2.5])
            with col_sel:
                selected_test = st.selectbox("Select Biomarker to Inspect", available_tests)
            
            with col_stats:
                test_history = df_bio[df_bio["test_name"] == selected_test].sort_values("date")
                if not test_history.empty:
                    latest_val = test_history["value"].iloc[-1]
                    latest_flag = test_history["flag"].iloc[-1]
                    unit = test_history["unit"].iloc[-1]
                    ref_low = test_history["ref_low"].iloc[-1]
                    ref_high = test_history["ref_high"].iloc[-1]
                    ref_text = f"{ref_low} - {ref_high} {unit}" if pd.notna(ref_low) and pd.notna(ref_high) else ("Normal" if pd.isna(ref_high) else f"<{ref_high} {unit}")
                    
                    st.markdown(f"""
                    <div style="padding:10px 15px;background:#1e293b;border-radius:8px;border:1px solid rgba(148,163,184,0.15)">
                        <b>Most Recent ({test_history['date'].iloc[-1]}):</b> {latest_val} {unit} &nbsp;|&nbsp; 
                        <b>Reference Range:</b> {ref_text} &nbsp;|&nbsp; 
                        <b>Status:</b> <span class="status-badge" style="background:{'#10b981' if latest_flag == 'NORMAL' else '#ef4444'}">{latest_flag}</span>
                    </div>
                    """, unsafe_allow_html=True)

            st.plotly_chart(plot_biomarker_trends(df_bio, selected_test), use_container_width=True)

            st.markdown("#### Clinical Health Ratios")
            r_col1, r_col2, r_col3 = st.columns(3)
            with r_col1:
                trig = df_bio[df_bio["test_name"].str.contains("TRIGLYCERIDE", case=False, na=False)]["value"]
                hdl = df_bio[df_bio["test_name"].str.contains("HDL", case=False, na=False)]["value"]
                if not trig.empty and not hdl.empty:
                    ratio = trig.iloc[-1] / hdl.iloc[-1]
                    r_color = "metric-subtitle" if ratio < 2.0 else ("metric-subtitle metric-warn" if ratio < 3.5 else "metric-subtitle metric-bad")
                    st.markdown(f"""
                    <div class="metric-card">
                        <div class="metric-title">Triglyceride / HDL Ratio</div>
                        <div class="metric-value">{ratio:.2f}</div>
                        <div class="{r_color}">Optimal: &lt; 2.0 (Insulin Sensitivity)</div>
                    </div>
                    """, unsafe_allow_html=True)

            with r_col2:
                chol = df_bio[df_bio["test_name"].str.contains("CHOLESTEROL, TOTAL", case=False, na=False)]["value"]
                if not chol.empty and not hdl.empty:
                    ratio = chol.iloc[-1] / hdl.iloc[-1]
                    r_color = "metric-subtitle" if ratio < 3.5 else "metric-subtitle metric-warn"
                    st.markdown(f"""
                    <div class="metric-card">
                        <div class="metric-title">Cholesterol / HDL Ratio</div>
                        <div class="metric-value">{ratio:.2f}</div>
                        <div class="{r_color}">Optimal: &lt; 3.5 (Cardiovascular)</div>
                    </div>
                    """, unsafe_allow_html=True)

            with r_col3:
                crp = df_bio[df_bio["test_name"].str.contains("CRP", case=False, na=False)]["value"]
                if not crp.empty:
                    crp_val = crp.iloc[-1]
                    c_color = "metric-subtitle" if crp_val < 1.0 else ("metric-subtitle metric-warn" if crp_val < 3.0 else "metric-subtitle metric-bad")
                    st.markdown(f"""
                    <div class="metric-card">
                        <div class="metric-title">Systemic Inflammation (hs-CRP)</div>
                        <div class="metric-value">{crp_val:.2f} <span style="font-size:1rem;color:#94a3b8">mg/L</span></div>
                        <div class="{c_color}">Optimal: &lt; 1.0 mg/L</div>
                    </div>
                    """, unsafe_allow_html=True)

            st.markdown("#### Complete Lab History Table")
            st.dataframe(
                df_bio[["date", "category", "test_name", "value", "unit", "ref_low", "ref_high", "flag"]].sort_values(["date", "test_name"], ascending=[False, True]),
                use_container_width=True,
                hide_index=True
            )
        else:
            st.write("No tests found for this category.")
    else:
        st.write("No Quest Diagnostics lab results imported yet. Upload a Quest PDF report in the Data Import tab.")

# -------------------------------------------------------------------------------------------------
# TAB 5: NUTRITION & FUELING
# -------------------------------------------------------------------------------------------------
with tab_nutrition:
    st.subheader("Nutrition & Macronutrient Fueling")
    st.caption("Aggregated from Apple Health nutrition sync and MyFitnessPal exports.")

    if not df_filtered.empty and "calories_consumed" in df_filtered.columns:
        n_col1, n_col2, n_col3, n_col4 = st.columns(4)
        avg_cals = df_filtered["calories_consumed"].mean()
        avg_prot = df_filtered["protein_consumed"].mean()
        avg_carbs = df_filtered["carbs_consumed"].mean()
        avg_fat = df_filtered["fat_consumed"].mean()

        with n_col1:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-title">Avg Daily Calories</div>
                <div class="metric-value">{avg_cals:.0f} <span style="font-size:1rem;color:#94a3b8">kcal</span></div>
                <div class="metric-subtitle">Fuel Intake</div>
            </div>
            """, unsafe_allow_html=True)

        with n_col2:
            prot_target = cfg.get("targets", {}).get("daily_protein_g_target", 160.0)
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-title">Avg Daily Protein</div>
                <div class="metric-value">{avg_prot:.1f} <span style="font-size:1rem;color:#94a3b8">g</span></div>
                <div class="metric-subtitle">Target: {prot_target} g</div>
            </div>
            """, unsafe_allow_html=True)

        with n_col3:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-title">Avg Daily Carbs</div>
                <div class="metric-value">{avg_carbs:.1f} <span style="font-size:1rem;color:#94a3b8">g</span></div>
                <div class="metric-subtitle">Glycogen Replenishment</div>
            </div>
            """, unsafe_allow_html=True)

        with n_col4:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-title">Avg Daily Dietary Fat</div>
                <div class="metric-value">{avg_fat:.1f} <span style="font-size:1rem;color:#94a3b8">g</span></div>
                <div class="metric-subtitle">Hormonal Support</div>
            </div>
            """, unsafe_allow_html=True)

        fig_macros = go.Figure()
        fig_macros.add_trace(go.Bar(x=df_filtered["date"], y=df_filtered["protein_consumed"], name="Protein (g)", marker_color="#10b981"))
        fig_macros.add_trace(go.Bar(x=df_filtered["date"], y=df_filtered["carbs_consumed"], name="Carbohydrates (g)", marker_color="#3b82f6"))
        fig_macros.add_trace(go.Bar(x=df_filtered["date"], y=df_filtered["fat_consumed"], name="Fat (g)", marker_color="#f59e0b"))
        fig_macros.update_layout(barmode="stack")
        fig_macros = apply_dark_layout(fig_macros, title="Daily Macronutrient Breakdown (Grams)", height=360)
        fig_macros.update_yaxes(title="Grams")
        st.plotly_chart(fig_macros, use_container_width=True)

        if "active_calories" in df_filtered.columns:
            fig_eng = go.Figure()
            fig_eng.add_trace(go.Scatter(x=df_filtered["date"], y=df_filtered["calories_consumed"], mode="lines+markers", name="Intake (kcal)", line=dict(color="#10b981", width=2)))
            fig_eng.add_trace(go.Scatter(x=df_filtered["date"], y=df_filtered["active_calories"], mode="lines+markers", name="Active Burn (kcal)", line=dict(color="#f43f5e", width=2)))
            fig_eng = apply_dark_layout(fig_eng, title="Energy Intake vs Active Expenditure", height=320)
            fig_eng.update_yaxes(title="Calories (kcal)")
            st.plotly_chart(fig_eng, use_container_width=True)
    else:
        st.write("No nutrition records available.")

# -------------------------------------------------------------------------------------------------
# TAB 6: LIFESTYLE CORRELATIONS & INSIGHTS ENGINE
# -------------------------------------------------------------------------------------------------
with tab_correlations:
    st.subheader("Multivariate Lifestyle & Recovery Insights")
    st.caption("Discover statistical relationships between your habits, training, sleep, and physiological recovery.")

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
            fig_heat = apply_dark_layout(fig_heat, title="Correlation Matrix (Pearson r)", height=480)
            st.plotly_chart(fig_heat, use_container_width=True)

        st.markdown("#### Pairwise Deep-Dive with Trendline")
        col_x, col_y = st.columns(2)
        with col_x:
            x_var = st.selectbox("Independent Variable (X)", available_num_cols, index=0)
        with col_y:
            default_y_idx = available_num_cols.index("recovery_score") if "recovery_score" in available_num_cols else 1
            y_var = st.selectbox("Dependent Variable (Y)", available_num_cols, index=default_y_idx)

        if x_var != y_var:
            stats_res = compute_pairwise_correlation(df_filtered[x_var], df_filtered[y_var])
            sig_badge = "✅ Statistically Significant (p < 0.05)" if stats_res["is_significant"] else "ℹ️ Not Statistically Significant (p >= 0.05)"
            st.info(f"**Correlation Analysis**: {stats_res['description']} &nbsp;|&nbsp; {sig_badge}")
            st.plotly_chart(plot_correlation_scatter(df_filtered, x_var, y_var), use_container_width=True)
    else:
        st.write("Insufficient data for correlation calculations. Ingest at least 10 days of health records.")

# -------------------------------------------------------------------------------------------------
# TAB 7: CUSTOM DASHBOARD BUILDER
# -------------------------------------------------------------------------------------------------
with tab_builder:
    st.subheader("Custom Health Visualizer")
    st.caption("Build custom charts on the fly with any combination of health variables.")

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
            color_dim = st.selectbox("Color / Group By (Optional)", ["None"] + all_numeric)

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

        fig_custom = apply_dark_layout(fig_custom, title=f"Custom Visual: {y_axis} vs {x_axis}", height=420)
        st.plotly_chart(fig_custom, use_container_width=True)
    else:
        st.write("No data available to plot.")

# -------------------------------------------------------------------------------------------------
# TAB 8: DATA IMPORT & FILE MANAGEMENT
# -------------------------------------------------------------------------------------------------
with tab_import:
    st.subheader("Data Importer & File Management")
    st.caption("Upload your personal health data. All processing occurs locally on your machine.")

    u_col1, u_col2, u_col3 = st.columns(3)

    with u_col1:
        st.markdown("#### 1. Apple Health")
        st.caption("Upload `export.zip` or `export.xml` from your iPhone Health app.")
        ah_file = st.file_uploader("Upload Apple Health Export", type=["zip", "xml"], key="ah_up")
        if ah_file:
            if st.button("Process Apple Health Data"):
                with st.spinner("Processing Apple Health records (streaming)..."):
                    suffix = ".zip" if ah_file.name.endswith(".zip") else ".xml"
                    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                        tmp.write(ah_file.getvalue())
                        tmp_path = tmp.name
                    try:
                        counts = AppleHealthParser(tmp_path).parse_and_store()
                        compute_daily_recovery()
                        compute_training_load()
                        st.success(f"Parsed Apple Health: {counts['sleep']} sleep, {counts['hrv']} HRV, {counts['workouts']} workouts.")
                        st.rerun()
                    finally:
                        os.unlink(tmp_path)

    with u_col2:
        st.markdown("#### 2. MyFitnessPal")
        st.caption("Upload nutrition CSV exported from MyFitnessPal.")
        mfp_file = st.file_uploader("Upload MFP CSV", type=["csv"], key="mfp_up")
        if mfp_file:
            if st.button("Process MyFitnessPal CSV"):
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
        st.markdown("#### 3. Quest Diagnostics")
        st.caption("Upload lab report PDF or structured CSV.")
        quest_file = st.file_uploader("Upload Quest Lab Report", type=["pdf", "csv"], key="quest_up")
        if quest_file:
            if st.button("Process Quest Labs"):
                with st.spinner("Extracting biomarkers and reference ranges..."):
                    suffix = ".pdf" if quest_file.name.endswith(".pdf") else ".csv"
                    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                        tmp.write(quest_file.getvalue())
                        tmp_path = tmp.name
                    try:
                        cnt = QuestDiagnosticsParser(tmp_path).parse_and_store()
                        st.success(f"Successfully extracted {cnt} biomarkers from Quest report!")
                        st.rerun()
                    finally:
                        os.unlink(tmp_path)

    st.markdown("---")
    st.subheader("Database Overview & Record Counts")
    session = get_session()()
    try:
        db_stats = [
            {"Table": "Sleep Records", "Count": session.query(SleepRecord).count()},
            {"Table": "Heart Records (HRV, RHR)", "Count": session.query(HeartRecord).count()},
            {"Table": "Activity Days", "Count": session.query(ActivityRecord).count()},
            {"Table": "Workouts", "Count": session.query(WorkoutRecord).count()},
            {"Table": "Nutrition Days", "Count": session.query(NutritionRecord).count()},
            {"Table": "Biomarkers (Quest Labs)", "Count": session.query(BiomarkerRecord).count()},
            {"Table": "Daily Summary (Computed)", "Count": session.query(DailySummaryRecord).count()},
        ]
        st.dataframe(pd.DataFrame(db_stats), use_container_width=True, hide_index=True)
    finally:
        session.close()