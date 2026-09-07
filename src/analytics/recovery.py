"""
Recovery and Sleep Scoring Engine.
Computes daily physiological readiness scores, HRV baseline z-scores,
resting heart rate deviations, and cumulative sleep debt.
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import numpy as np
import pandas as pd
from sqlalchemy import func

from src.database import SleepRecord, HeartRecord, DailySummaryRecord, get_session


def merge_time_intervals(intervals: List[Tuple[datetime, datetime]]) -> float:
    """
    Merges overlapping or adjacent [start, end] time intervals and returns total minutes.
    Prevents artificial inflation of sleep duration from multiple devices (e.g. Apple Watch
    and iPhone recording simultaneously) or duplicate segment imports.
    """
    if not intervals:
        return 0.0
    valid = [(s, e) for s, e in intervals if e > s]
    if not valid:
        return 0.0
    sorted_int = sorted(valid, key=lambda x: x[0])
    merged = [sorted_int[0]]
    for cur_s, cur_e in sorted_int[1:]:
        last_s, last_e = merged[-1]
        if cur_s <= last_e:  # Overlapping or contiguous interval
            merged[-1] = (last_s, max(last_e, cur_e))
        else:
            merged.append((cur_s, cur_e))
    return sum((end - start).total_seconds() / 60.0 for start, end in merged)


def calculate_sleep_metrics(date_str: str, session) -> Dict[str, float]:
    """
    Calculates physically accurate sleep architecture metrics for a given canonical night.
    Resolves multi-device overlapping records and enforces physical day limits (max 24h).
    """
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

    # Extract parsed interval tuples
    valid_records = []
    for r in records:
        if r.start_time and r.end_time and r.end_time > r.start_time:
            valid_records.append(r)

    if not valid_records:
        return {
            "total_sleep_hours": 0.0,
            "deep_sleep_hours": 0.0,
            "rem_sleep_hours": 0.0,
            "core_sleep_hours": 0.0,
            "awake_hours": 0.0,
            "sleep_score": 0.0
        }

    # Asleep stages (Deep, REM, Core, Asleep) - excludes InBed and Awake
    asleep_stages = {"Deep", "REM", "Core", "Asleep", "Unspecified"}
    asleep_intervals = [(r.start_time, r.end_time) for r in valid_records if r.stage in asleep_stages]

    # Compute union of all time asleep (solves multi-device double counting)
    total_asleep_mins = merge_time_intervals(asleep_intervals)
    total_hours = min(24.0, total_asleep_mins / 60.0)

    # Compute stage-specific merged durations
    deep_mins = merge_time_intervals([(r.start_time, r.end_time) for r in valid_records if r.stage == "Deep"])
    rem_mins = merge_time_intervals([(r.start_time, r.end_time) for r in valid_records if r.stage == "REM"])
    awake_mins = merge_time_intervals([(r.start_time, r.end_time) for r in valid_records if r.stage == "Awake"])

    # Allocate stages ensuring deep + rem + core == total_sleep_hours
    deep_hours = min(total_hours, deep_mins / 60.0)
    rem_hours = min(total_hours - deep_hours, rem_mins / 60.0)
    core_hours = max(0.0, total_hours - (deep_hours + rem_hours))
    awake_hours = awake_mins / 60.0

    # Calculate sleep score (0-100)
    # Target: 8.0h total, ~18% deep, ~22% rem
    duration_factor = min(100.0, (total_hours / 8.0) * 100.0)
    deep_pct = (deep_hours / total_hours * 100.0) if total_hours > 0 else 0.0
    rem_pct = (rem_hours / total_hours * 100.0) if total_hours > 0 else 0.0

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
