"""
Training Load & Workout Performance Analytics Engine.
Calculates Acute Training Load (ATL / Fatigue), Chronic Training Load (CTL / Fitness),
Training Stress Balance (TSB / Freshness), ACWR (Acute:Chronic Workload Ratio),
and workout category breakdowns.
"""

from typing import Dict, List, Optional
import numpy as np
import pandas as pd

from src.database import WorkoutRecord, ActivityRecord, DailySummaryRecord, get_session


def compute_training_load(db_path: Optional[str] = None):
    """
    Computes daily ATL (7-day EMA), CTL (28-day EMA), TSB (CTL - ATL),
    and ACWR from daily active load and workouts.
    """
    session = get_session(db_path)()
    try:
        # Load activity records
        df_act = pd.read_sql_query(
            "SELECT date, active_calories, step_count, exercise_minutes, vo2_max FROM activity_records ORDER BY date ASC",
            session.bind
        )
        
        # Load workout counts
        df_wk = pd.read_sql_query(
            "SELECT date, COUNT(id) as workout_count, SUM(calories_burned) as wk_calories, SUM(duration_minutes) as wk_duration FROM workout_records GROUP BY date",
            session.bind
        )

        if df_act.empty:
            return

        df = pd.merge(df_act, df_wk, on="date", how="left").fillna(0)
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date").reset_index(drop=True)

        # Calculate daily Training Load score (arbitrary training impulse units)
        # Combination of active calories and exercise minutes
        # E.g. 500 active cals + 45 min exercise = 50 + 45 = 95 load units
        df["daily_load"] = (df["active_calories"] / 10.0) + (df["exercise_minutes"] * 0.8)

        # Exponential Moving Averages:
        # ATL (Fatigue): 7-day span
        # CTL (Fitness): 28-day span
        df["atl"] = df["daily_load"].ewm(span=7, adjust=False).mean()
        df["ctl"] = df["daily_load"].ewm(span=28, adjust=False).mean()
        df["tsb"] = df["ctl"] - df["atl"]
        df["acwr"] = np.where(df["ctl"] > 0, df["atl"] / df["ctl"], 1.0)

        # Update daily_summary table
        for _, row in df.iterrows():
            date_str = row["date"].strftime("%Y-%m-%d")
            existing = session.query(DailySummaryRecord).filter_by(date=date_str).first()
            if not existing:
                existing = DailySummaryRecord(date=date_str)
                session.add(existing)

            existing.active_calories = float(row["active_calories"])
            existing.steps = int(row["step_count"])
            existing.exercise_minutes = float(row["exercise_minutes"])
            existing.workout_count = int(row["workout_count"])
            existing.training_load_atl = round(float(row["atl"]), 1)
            existing.training_load_ctl = round(float(row["ctl"]), 1)
            existing.training_stress_balance = round(float(row["tsb"]), 1)

        session.commit()
    finally:
        session.close()


def get_training_stress_category(tsb: float) -> Dict[str, str]:
    """Interprets TSB value into a coaching status and recommendation."""
    if tsb > 15:
        return {
            "status": "Very Fresh / Tapering",
            "zone": "Fresh",
            "color": "#3b82f6",
            "message": "High freshness. Great for a race or max-effort test, but extended periods lead to detraining."
        }
    elif 5 <= tsb <= 15:
        return {
            "status": "Optimal Freshness (Peak)",
            "zone": "Peak",
            "color": "#10b981",
            "message": "Prime readiness! Ideal state for personal records and high-intensity performance."
        }
    elif -10 <= tsb < 5:
        return {
            "status": "Neutral / Productive Load",
            "zone": "Maintenance",
            "color": "#06b6d4",
            "message": "Balanced fitness building and fatigue. Sustainable long-term training."
        }
    elif -30 <= tsb < -10:
        return {
            "status": "Optimal Building Phase",
            "zone": "Building",
            "color": "#f59e0b",
            "message": "High productive fatigue. Fitness is increasing, prioritize sleep and nutrition for recovery."
        }
    else:
        return {
            "status": "Overreaching / High Fatigue",
            "zone": "Overreaching",
            "color": "#ef4444",
            "message": "Critical fatigue accumulation. High risk of overtraining or injury. Plan an active recovery day."
        }
