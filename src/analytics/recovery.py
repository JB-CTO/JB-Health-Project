"""
Recovery and Sleep Scoring Engine.
Computes daily physiological readiness scores, HRV baseline z-scores,
resting heart rate deviations, and cumulative sleep debt.
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional
import numpy as np
import pandas as pd
from sqlalchemy import func

from src.database import SleepRecord, HeartRecord, DailySummaryRecord, get_session


def calculate_sleep_metrics(date_str: str, session) -> Dict[str, float]:
    """Calculates sleep architecture metrics for a given canonical night date."""
    records = session.query(SleepRecord).filter_by(date=date_str).all()
    if not records:
        return {
            "total_sleep_hours": 0.0,
            "deep_sleep_hours": 0.0,
            "rem_sleep_hours": 0.0,
            "core_sleep_hours": 0.0,
            "awake_hours": 0.0,
            "sleep_score": 0.0
        }

    durations = {"Deep": 0.0, "REM": 0.0, "Core": 0.0, "Awake": 0.0, "InBed": 0.0}
    for r in records:
        st = r.stage if r.stage in durations else "Core"
        durations[st] += r.duration_minutes

    total_sleep_min = durations["Deep"] + durations["REM"] + durations["Core"]
    total_hours = total_sleep_min / 60.0
    deep_hours = durations["Deep"] / 60.0
    rem_hours = durations["REM"] / 60.0
    core_hours = durations["Core"] / 60.0
    awake_hours = durations["Awake"] / 60.0

    # Calculate sleep score (0-100)
    # Target: 8.0h total, ~18% deep, ~22% rem
    duration_factor = min(100.0, (total_hours / 8.0) * 100.0)
    deep_pct = (durations["Deep"] / total_sleep_min * 100.0) if total_sleep_min > 0 else 0
    rem_pct = (durations["REM"] / total_sleep_min * 100.0) if total_sleep_min > 0 else 0

    deep_score = min(100.0, (deep_pct / 18.0) * 100.0)
    rem_score = min(100.0, (rem_pct / 22.0) * 100.0)
    sleep_score = (0.50 * duration_factor) + (0.25 * deep_score) + (0.25 * rem_score)

    return {
        "total_sleep_hours": round(total_hours, 2),
        "deep_sleep_hours": round(deep_hours, 2),
        "rem_sleep_hours": round(rem_hours, 2),
        "core_sleep_hours": round(core_hours, 2),
        "awake_hours": round(awake_hours, 2),
        "sleep_score": round(max(0.0, min(100.0, sleep_score)), 1)
    }


def compute_daily_recovery(db_path: Optional[str] = None, target_sleep_hours: float = 8.0):
    """
    Processes all dates in the database and updates the daily_summary table
    with readiness scores, rolling HRV/RHR baselines, and sleep debt.
    """
    session = get_session(db_path)()
    try:
        # Get all unique dates from heart, sleep, and activity
        heart_dates = [r[0] for r in session.query(HeartRecord.date).distinct().all()]
        sleep_dates = [r[0] for r in session.query(SleepRecord.date).distinct().all()]
        all_dates = sorted(list(set(heart_dates + sleep_dates)))

        if not all_dates:
            return

        # Fetch daily average HRV and Resting HR into DataFrame for rolling calculations
        query = """
        SELECT date, metric, AVG(value) as val
        FROM heart_records
        WHERE metric IN ('hrv_sdnn', 'resting_hr')
        GROUP BY date, metric
        """
        df_heart = pd.read_sql_query(query, session.bind)
        df_piv = df_heart.pivot(index="date", columns="metric", values="val") if not df_heart.empty else pd.DataFrame()

        # Rolling 14-day baselines
        hrv_series = df_piv["hrv_sdnn"] if "hrv_sdnn" in df_piv.columns else pd.Series(dtype=float)
        rhr_series = df_piv["resting_hr"] if "resting_hr" in df_piv.columns else pd.Series(dtype=float)

        hrv_baseline = hrv_series.rolling(window=14, min_periods=1).mean()
        hrv_std = hrv_series.rolling(window=14, min_periods=1).std().fillna(5.0)
        rhr_baseline = rhr_series.rolling(window=14, min_periods=1).mean()

        sleep_debt_acc = 0.0

        for cur_date in all_dates:
            sleep_m = calculate_sleep_metrics(cur_date, session)
            
            # Cumulative sleep debt (clamped between 0 and 15 hours)
            deficit = target_sleep_hours - sleep_m["total_sleep_hours"]
            sleep_debt_acc = max(0.0, min(15.0, sleep_debt_acc + deficit))

            curr_hrv = float(hrv_series.get(cur_date, np.nan))
            base_hrv = float(hrv_baseline.get(cur_date, np.nan))
            curr_rhr = float(rhr_series.get(cur_date, np.nan))
            base_rhr = float(rhr_baseline.get(cur_date, np.nan))

            # Recovery score components (0-100 scale)
            # 1. HRV component: z-score vs rolling baseline
            if not np.isnan(curr_hrv) and not np.isnan(base_hrv) and base_hrv > 0:
                s = float(hrv_std.get(cur_date, 5.0))
                if s <= 0: s = 5.0
                z_hrv = (curr_hrv - base_hrv) / s
                # Map z-score [-2.0, +2.0] to [20, 100]
                hrv_subscore = max(10.0, min(100.0, 60.0 + (z_hrv * 20.0)))
            else:
                hrv_subscore = 65.0

            # 2. RHR component: deviation from baseline (lower is better)
            if not np.isnan(curr_rhr) and not np.isnan(base_rhr) and base_rhr > 0:
                diff_rhr = base_rhr - curr_rhr # positive = rested, negative = elevated HR
                rhr_subscore = max(10.0, min(100.0, 60.0 + (diff_rhr * 8.0)))
            else:
                rhr_subscore = 65.0

            # 3. Sleep component
            sleep_subscore = sleep_m["sleep_score"]

            # Combined weighted Readiness/Recovery score
            recovery_score = (0.45 * hrv_subscore) + (0.30 * rhr_subscore) + (0.25 * sleep_subscore)
            recovery_score = round(max(5.0, min(99.0, recovery_score)), 1)

            # Upsert into daily_summary
            existing = session.query(DailySummaryRecord).filter_by(date=cur_date).first()
            if not existing:
                existing = DailySummaryRecord(date=cur_date)
                session.add(existing)

            existing.recovery_score = recovery_score
            existing.sleep_score = sleep_m["sleep_score"]
            existing.hrv_sdnn = round(curr_hrv, 1) if not np.isnan(curr_hrv) else None
            existing.hrv_7d_baseline = round(base_hrv, 1) if not np.isnan(base_hrv) else None
            existing.resting_hr = round(curr_rhr, 1) if not np.isnan(curr_rhr) else None
            existing.resting_hr_7d_baseline = round(base_rhr, 1) if not np.isnan(base_rhr) else None
            existing.total_sleep_hours = sleep_m["total_sleep_hours"]
            existing.deep_sleep_hours = sleep_m["deep_sleep_hours"]
            existing.rem_sleep_hours = sleep_m["rem_sleep_hours"]
            existing.sleep_debt_hours = round(sleep_debt_acc, 2)

        session.commit()
    finally:
        session.close()
