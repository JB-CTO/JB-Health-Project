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
