"""
Multivariate Correlation & Lifestyle Insights Engine.
Computes correlations between lifestyle inputs (nutrition, workouts, activity)
and physiological outputs (sleep stages, HRV, resting heart rate, recovery).
Includes lag-based correlations (e.g. today's dinner/strain vs tonight's sleep and tomorrow's HRV).
"""

from typing import Dict, List, Optional, Tuple, Any
import pandas as pd
import numpy as np
from scipy import stats

from src.database import get_session


def get_integrated_daily_df(db_path: Optional[str] = None) -> pd.DataFrame:
    """
    Joins daily summary, nutrition, activity, and workouts into a single master analysis DataFrame.
    """
    session = get_session(db_path)()
    try:
        query = """
        SELECT 
            d.date,
            d.recovery_score,
            d.sleep_score,
            d.hrv_sdnn,
            d.resting_hr,
            d.total_sleep_hours,
            d.deep_sleep_hours,
            d.rem_sleep_hours,
            d.sleep_debt_hours,
            d.active_calories,
            d.steps,
            d.exercise_minutes,
            d.workout_count,
            d.training_load_atl,
            d.training_load_ctl,
            d.training_stress_balance,
            n.calories as calories_consumed,
            n.protein_g as protein_consumed,
            n.carbs_g as carbs_consumed,
            n.fat_g as fat_consumed,
            n.fiber_g as fiber_consumed,
            n.sodium_mg as sodium_consumed
        FROM daily_summary d
        LEFT JOIN (
            SELECT date, 
                   SUM(calories) as calories, 
                   SUM(protein_g) as protein_g,
                   SUM(carbs_g) as carbs_g,
                   SUM(fat_g) as fat_g,
                   SUM(fiber_g) as fiber_g,
                   SUM(sodium_mg) as sodium_mg
            FROM nutrition_records
            GROUP BY date
        ) n ON d.date = n.date
        ORDER BY d.date ASC
        """
        df = pd.read_sql_query(query, session.bind)
        if not df.empty:
            df["date"] = pd.to_datetime(df["date"])
            # Create next-day lag columns (e.g. how today's active calories impact tomorrow's recovery)
            df["next_day_hrv"] = df["hrv_sdnn"].shift(-1)
            df["next_day_recovery"] = df["recovery_score"].shift(-1)
            df["next_day_rhr"] = df["resting_hr"].shift(-1)
        return df
    finally:
        session.close()


def compute_correlation_matrix(df: pd.DataFrame, selected_cols: Optional[List[str]] = None) -> pd.DataFrame:
    """Computes correlation matrix for numeric columns."""
    if df.empty:
        return pd.DataFrame()
    num_cols = selected_cols if selected_cols else df.select_dtypes(include=[np.number]).columns.tolist()
    valid_cols = [c for c in num_cols if c in df.columns and df[c].notna().sum() >= 5]
    if len(valid_cols) < 2:
        return pd.DataFrame()
    return df[valid_cols].corr()


def compute_pairwise_correlation(x_series: pd.Series, y_series: pd.Series) -> Dict[str, Any]:
    """Computes Pearson correlation coefficient and p-value between two series."""
    valid = pd.DataFrame({"x": x_series, "y": y_series}).dropna()
    if len(valid) < 5:
        return {"r": 0.0, "p_value": 1.0, "n": len(valid), "description": "Insufficient data"}

    r, p = stats.pearsonr(valid["x"], valid["y"])
    
    # Interpretation
    abs_r = abs(r)
    strength = "Very Strong" if abs_r >= 0.7 else ("Moderate" if abs_r >= 0.4 else ("Weak" if abs_r >= 0.2 else "Negligible"))
    direction = "Positive" if r > 0 else "Negative"

    return {
        "r": round(float(r), 3),
        "p_value": round(float(p), 4),
        "n": int(len(valid)),
        "strength": strength,
        "direction": direction,
        "is_significant": bool(p < 0.05),
        "description": f"{strength} {direction} correlation (r = {r:.2f}, p = {p:.3f})"
    }
