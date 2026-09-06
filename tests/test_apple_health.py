import pytest
from pathlib import Path
from src.database import init_db, get_session, SleepRecord, HeartRecord, WorkoutRecord
from src.parsers.apple_health import AppleHealthParser, clean_workout_type, get_sleep_canonical_date
from datetime import datetime

def test_clean_workout_type():
    assert clean_workout_type("HKWorkoutActivityTypeRunning") == "Running"
    assert clean_workout_type("HKWorkoutActivityTypeTraditionalStrengthTraining") == "Traditional Strength Training"

def test_sleep_canonical_date():
    # 2 AM on March 2 belongs to March 1 night
    dt_early = datetime(2024, 3, 2, 2, 30)
    assert get_sleep_canonical_date(dt_early) == "2024-03-01"
    # 11 PM on March 1 belongs to March 1 night
    dt_late = datetime(2024, 3, 1, 23, 0)
    assert get_sleep_canonical_date(dt_late) == "2024-03-01"

def test_apple_health_parsing(tmp_path):
    db_file = str(tmp_path / "test_ah.db")
    init_db(db_file)
    parser = AppleHealthParser("data/samples/sample_apple_health.xml")
    counts = parser.parse_and_store(db_file)
    assert counts["sleep"] > 0
    assert counts["hrv"] > 0
    assert counts["resting_hr"] > 0
    assert counts["workouts"] > 0
