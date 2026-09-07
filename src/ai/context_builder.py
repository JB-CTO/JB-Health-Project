"""
Health Data Context Builder for Gemini API.
Extracts, summarizes, and formats de-identified health metrics across sleep,
autonomic recovery, training load, nutrition, and clinical biomarkers into a
structured, token-efficient Markdown prompt payload.
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import re
import pandas as pd
import numpy as np

from src.database import (
    load_table_df, get_session,
    DailySummaryRecord, BiomarkerRecord, WorkoutRecord
)
from src.analytics.training_load import get_training_stress_category
from src.analytics.correlations import get_integrated_daily_df, compute_pairwise_correlation


def build_health_context(db_path: Optional[str] = None, days: int = 30, targets: Optional[Dict[str, Any]] = None) -> str:
    """
    Assembles a comprehensive, de-identified Markdown context payload
    synthesizing the user's recent health data for Gemini prompts.
    """
    df_master = get_integrated_daily_df(db_path)
    df_bio = load_table_df("biomarker_records", db_path)
    df_workouts = load_table_df("workout_records", db_path)

    sections = []
    sections.append("# DE-IDENTIFIED PERSONAL HEALTH & PERFORMANCE SNAPSHOT")
    sections.append(f"Generated on: {datetime.today().strftime('%Y-%m-%d %H:%M')}")
    sections.append(f"Analysis Window: Last {days} Days\n")

    # Target goals
    if targets:
        sleep_t = targets.get("sleep_hours_target", 8.0)
        cals_t = targets.get("daily_active_calories", 600)
        prot_t = targets.get("daily_protein_g_target", 160.0)
        sections.append("## Personal Targets")
        sections.append(f"- Target Sleep: {sleep_t} hrs/night (Deep >= 15%, REM >= 20%)")
        sections.append(f"- Daily Active Calories Target: {cals_t} kcal")
        sections.append(f"- Daily Protein Target: {prot_t} g\n")

    if df_master.empty:
        sections.append("*(No daily summary health records found in database)*")
        return "\n".join(sections)

    # Filter by timeframe
    cutoff = datetime.today() - timedelta(days=days)
    df_win = df_master[df_master["date"] >= cutoff].sort_values("date")
    if df_win.empty:
        df_win = df_master.tail(days)

    latest = df_win.iloc[-1]
    latest_date = latest["date"].strftime("%Y-%m-%d") if isinstance(latest["date"], (datetime, pd.Timestamp)) else str(latest["date"])

    # 1. Latest Readiness & Recovery
    sections.append("## 1. Latest Autonomic Readiness & Physiological Recovery")
    sections.append(f"- Latest Date Tracked: {latest_date}")
    sections.append(f"- Readiness / Recovery Score: {latest.get('recovery_score', 'N/A')} / 100")
    
    hrv = latest.get("hrv_sdnn", np.nan)
    hrv_base = latest.get("hrv_7d_baseline", np.nan)
    hrv_delta = (hrv - hrv_base) if pd.notna(hrv) and pd.notna(hrv_base) else 0.0
    if pd.notna(hrv):
        sections.append(f"- Heart Rate Variability (SDNN): {hrv:.1f} ms (14-day rolling baseline: {hrv_base:.1f} ms, Delta: {hrv_delta:+.1f} ms)")
    else:
        sections.append("- HRV: N/A")

    rhr = latest.get("resting_hr", np.nan)
    rhr_base = latest.get("resting_hr_7d_baseline", np.nan)
    rhr_delta = (rhr - rhr_base) if pd.notna(rhr) and pd.notna(rhr_base) else 0.0
    if pd.notna(rhr):
        sections.append(f"- Resting Heart Rate: {rhr:.1f} bpm (14-day rolling baseline: {rhr_base:.1f} bpm, Delta: {rhr_delta:+.1f} bpm)")
    else:
        sections.append("- Resting HR: N/A")

    sections.append(f"- Cumulative Sleep Debt: {latest.get('sleep_debt_hours', 0.0):.1f} hours behind target\n")

    # 2. Sleep Architecture
    sections.append("## 2. Sleep Architecture & Quality")
    valid_sleep = df_win[df_win["total_sleep_hours"] > 0.5] if "total_sleep_hours" in df_win.columns else pd.DataFrame()
    if not valid_sleep.empty:
        avg_sleep = valid_sleep["total_sleep_hours"].mean()
        avg_deep = valid_sleep["deep_sleep_hours"].mean()
        avg_rem = valid_sleep["rem_sleep_hours"].mean()
        avg_score = valid_sleep["sleep_score"].mean()
        deep_pct = (avg_deep / avg_sleep * 100) if avg_sleep > 0 else 0
        rem_pct = (avg_rem / avg_sleep * 100) if avg_sleep > 0 else 0
        core_pct = max(0.0, 100.0 - (deep_pct + rem_pct))

        sections.append(f"- Average Nightly Sleep: {avg_sleep:.2f} hrs (Last Night: {latest.get('total_sleep_hours', 0):.2f} hrs)")
        sections.append(f"- Sleep Stages Distribution: Deep: {deep_pct:.1f}% ({avg_deep:.2f}h), REM: {rem_pct:.1f}% ({avg_rem:.2f}h), Core/Light: {core_pct:.1f}%")
        sections.append(f"- Average Sleep Score: {avg_score:.1f} / 100 (Last Night: {latest.get('sleep_score', 'N/A')})")
        
        # Recent 7 nights summary
        recent_sleep = valid_sleep.tail(7)
        sections.append("\nRecent 7 Nights:")
        sections.append("| Date | Sleep (hrs) | Deep (hrs) | REM (hrs) | Score |")
        sections.append("|---|---|---|---|---|")
        for _, row in recent_sleep.iterrows():
            d_str = row["date"].strftime("%Y-%m-%d") if isinstance(row["date"], (datetime, pd.Timestamp)) else str(row["date"])
            sections.append(f"| {d_str} | {row.get('total_sleep_hours', 0):.2f}h | {row.get('deep_sleep_hours', 0):.2f}h | {row.get('rem_sleep_hours', 0):.2f}h | {row.get('sleep_score', 0):.0f} |")
    else:
        sections.append("- No sleep records recorded in this window.")
    sections.append("")

    # 3. Athletic Performance & Training Load
    sections.append("## 3. Athletic Performance & Training Load (ATL / CTL / TSB)")
    if "training_stress_balance" in df_win.columns and pd.notna(latest.get("training_stress_balance")):
        tsb = latest["training_stress_balance"]
        atl = latest.get("training_load_atl", 0.0)
        ctl = latest.get("training_load_ctl", 0.0)
        cat = get_training_stress_category(tsb)
        acwr = (atl / ctl) if ctl > 0 else 1.0

        sections.append(f"- Training Stress Balance (TSB / Freshness): {tsb:+.1f} pts ({cat['zone']} - {cat['status']})")
        sections.append(f"- Acute Training Load (ATL / 7-Day Fatigue): {atl:.1f} pts")
        sections.append(f"- Chronic Training Load (CTL / 28-Day Fitness Base): {ctl:.1f} pts")
        sections.append(f"- Acute:Chronic Workload Ratio (ACWR): {acwr:.2f} (Sweet spot: 0.80 - 1.30)")
        sections.append(f"- Prescription: {cat['message']}")
    
    # Recent workouts
    if not df_workouts.empty:
        w_cutoff = datetime.today() - timedelta(days=14)
        df_w_recent = df_workouts[pd.to_datetime(df_workouts["date"]) >= w_cutoff].sort_values("start_time", ascending=False)
        if not df_w_recent.empty:
            sections.append(f"\nWorkouts Logged (Last 14 Days: {len(df_w_recent)} sessions):")
            for _, w in df_w_recent.head(8).iterrows():
                dist_str = f", {w['distance_km']} km" if pd.notna(w.get("distance_km")) and w["distance_km"] > 0 else ""
                sections.append(f"- {w['date']}: {w['activity_type']} - {w['duration_minutes']} min, {w['calories_burned']} kcal{dist_str}")
    sections.append("")

    # 4. Quest Diagnostics Biomarkers
    sections.append("## 4. Clinical Biomarkers & Quest Blood Work")
    if not df_bio.empty:
        df_bio_sorted = df_bio.sort_values(["date", "category", "test_name"], ascending=[False, True, True])
        latest_draw_date = df_bio_sorted["date"].iloc[0]
        sections.append(f"Most Recent Lab Draw Date: {latest_draw_date}")
        
        # Abnormal Flags
        abnormal = df_bio_sorted[df_bio_sorted["flag"].isin(["HIGH", "LOW", "CRITICAL"])]
        if not abnormal.empty:
            sections.append("\n⚠️ Flagged Out-of-Range Biomarkers:")
            for _, b in abnormal.iterrows():
                ref_str = f" [Ref: {b['ref_low']} - {b['ref_high']}]" if pd.notna(b.get("ref_low")) and pd.notna(b.get("ref_high")) else ""
                sections.append(f"- **{b['test_name']}** ({b['category']}): **{b['value']} {b['unit']}** - **{b['flag']}**{ref_str} (Draw: {b['date']})")
        else:
            sections.append("\n✅ All tested biomarkers currently within standard laboratory reference ranges.")

        # Key Longevity & Metabolic Markers
        key_markers = ["ApoB", "Cholesterol, Total", "HDL-C", "LDL-C", "Triglycerides", "hs-CRP", "Hemoglobin A1c", "Glucose", "Vitamin D", "Testosterone", "Ferritin", "eGFR"]
        pattern = "|".join([re.escape(k) for k in key_markers])
        key_df = df_bio_sorted[df_bio_sorted["test_name"].str.contains(pattern, case=False, na=False)]
        if not key_df.empty:
            sections.append("\nKey Cardiovascular & Longevity Panel Snapshot:")
            for _, b in key_df.drop_duplicates(subset=["test_name"]).head(12).iterrows():
                ref_str = f" (Ref: {b['ref_low']}-{b['ref_high']} {b['unit']})" if pd.notna(b.get("ref_low")) else f" {b['unit']}"
                sections.append(f"- {b['test_name']}: {b['value']}{ref_str} [{b['flag']}]")
    else:
        sections.append("- No laboratory blood work records loaded in database.")
    sections.append("")

    # 5. Nutrition & Fueling
    sections.append("## 5. Nutrition & Fueling Averages")
    valid_nut = df_win[df_win["calories_consumed"] > 200] if "calories_consumed" in df_win.columns else pd.DataFrame()
    if not valid_nut.empty:
        avg_cal = valid_nut["calories_consumed"].mean()
        avg_prot = valid_nut["protein_consumed"].mean()
        avg_carb = valid_nut["carbs_consumed"].mean() if "carbs_consumed" in valid_nut.columns else 0.0
        avg_fat = valid_nut["fat_consumed"].mean() if "fat_consumed" in valid_nut.columns else 0.0
        sections.append(f"- Average Daily Calories: {avg_cal:.0f} kcal")
        sections.append(f"- Average Protein: {avg_prot:.1f} g/day")
        sections.append(f"- Average Carbs: {avg_carb:.1f} g/day")
        sections.append(f"- Average Fat: {avg_fat:.1f} g/day")
    else:
        sections.append("- No nutrition records logged in this timeframe.")
    sections.append("")

    # 6. Discovered Lifestyle Correlations
    sections.append("## 6. Discovered Lifestyle Correlations")
    corr_findings = []
    if "protein_consumed" in df_win.columns and "recovery_score" in df_win.columns:
        c1 = compute_pairwise_correlation(df_win["protein_consumed"], df_win["recovery_score"])
        if c1["n"] >= 10 and abs(c1["r"]) >= 0.2:
            corr_findings.append(f"- Protein Intake vs Recovery Score: r = {c1['r']:+.2f} ({c1['strength']}, p = {c1['p_val']:.3f})")

    if "active_calories" in df_win.columns and "deep_sleep_hours" in df_win.columns:
        c2 = compute_pairwise_correlation(df_win["active_calories"], df_win["deep_sleep_hours"])
        if c2["n"] >= 10 and abs(c2["r"]) >= 0.2:
            corr_findings.append(f"- Active Calories Burned vs Deep Sleep: r = {c2['r']:+.2f} ({c2['strength']}, p = {c2['p_val']:.3f})")

    if corr_findings:
        sections.extend(corr_findings)
    else:
        sections.append("- Baselines currently building as more historical data is aggregated.")

    return "\n".join(sections)