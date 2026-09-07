import pytest
from src.database import init_db
from src.parsers.apple_health import AppleHealthParser
from src.analytics.recovery import compute_daily_recovery
from src.analytics.training_load import compute_training_load, get_training_stress_category
from src.analytics.correlations import get_integrated_daily_df, compute_pairwise_correlation

def test_analytics_and_training_load(tmp_path):
    db_file = str(tmp_path / "test_analytics.db")
    init_db(db_file)
    AppleHealthParser("data/samples/sample_apple_health.xml").parse_and_store(db_file)
    
    compute_daily_recovery(db_file)
    compute_training_load(db_file)

    df = get_integrated_daily_df(db_file)
    assert not df.empty
    assert "recovery_score" in df.columns
    assert "training_stress_balance" in df.columns

    # Test TSB coaching category
    cat_fresh = get_training_stress_category(10.0)
    assert cat_fresh["zone"] == "Peak"
    cat_tired = get_training_stress_category(-35.0)
    assert cat_tired["zone"] == "Overreaching"

    # Test correlation
    corr = compute_pairwise_correlation(df["total_sleep_hours"], df["recovery_score"])
    assert "r" in corr


def test_sleep_interval_merging_and_deduplication(tmp_path):
    """Tests that overlapping multi-device sleep intervals do not inflate sleep > 24 hours."""
    from datetime import datetime, timedelta
    from src.database import get_session, SleepRecord
    from src.analytics.recovery import calculate_sleep_metrics, merge_time_intervals

    db_file = str(tmp_path / "test_sleep_dedup.db")
    init_db(db_file)
    session = get_session(db_file)()

    date_str = "2026-09-01"
    base_t = datetime(2026, 9, 1, 22, 0) # 10:00 PM

    # Scenario 1: iPhone records a macro block from 10:00 PM to 6:00 AM (8 hours) as Core
    session.add(SleepRecord(
        date=date_str,
        start_time=base_t,
        end_time=base_t + timedelta(hours=8),
        stage="Core",
        duration_minutes=480.0,
        source="iPhone"
    ))

    # Scenario 2: Apple Watch concurrently records micro-stages inside that exact 8-hour window
    # 10:00 PM - 11:30 PM: Deep (1.5h)
    # 11:30 PM - 1:30 AM: REM (2.0h)
    # 1:30 AM - 5:30 AM: Core (4.0h)
    # 5:30 AM - 6:00 AM: Awake (0.5h)
    session.add(SleepRecord(
        date=date_str,
        start_time=base_t,
        end_time=base_t + timedelta(hours=1.5),
        stage="Deep",
        duration_minutes=90.0,
        source="Apple Watch"
    ))
    session.add(SleepRecord(
        date=date_str,
        start_time=base_t + timedelta(hours=1.5),
        end_time=base_t + timedelta(hours=3.5),
        stage="REM",
        duration_minutes=120.0,
        source="Apple Watch"
    ))
    session.add(SleepRecord(
        date=date_str,
        start_time=base_t + timedelta(hours=3.5),
        end_time=base_t + timedelta(hours=7.5),
        stage="Core",
        duration_minutes=240.0,
        source="Apple Watch"
    ))
    session.add(SleepRecord(
        date=date_str,
        start_time=base_t + timedelta(hours=7.5),
        end_time=base_t + timedelta(hours=8.0),
        stage="Awake",
        duration_minutes=30.0,
        source="Apple Watch"
    ))

    # Scenario 3: Exact duplicate records inserted again (re-import)
    session.add(SleepRecord(
        date=date_str,
        start_time=base_t,
        end_time=base_t + timedelta(hours=1.5),
        stage="Deep",
        duration_minutes=90.0,
        source="Apple Watch"
    ))
    session.commit()

    # Calculate metrics
    m = calculate_sleep_metrics(date_str, session)
    session.close()

    # Even with iPhone (8h) + Apple Watch (7.5h) + duplicate Deep (1.5h) = 17 hours raw sum,
    # The true merged asleep union must be 8.0 hours!
    assert m["total_sleep_hours"] == 8.0
    assert m["deep_sleep_hours"] == 1.5
    assert m["rem_sleep_hours"] == 2.0
    assert m["core_sleep_hours"] == 4.5
    # Sum of parts must equal total
    assert round(m["deep_sleep_hours"] + m["rem_sleep_hours"] + m["core_sleep_hours"], 2) == m["total_sleep_hours"]
    assert m["total_sleep_hours"] <= 24.0
    assert m["awake_hours"] == 0.5

