import pytest
from pathlib import Path
from src.database import init_db, get_session, SleepRecord, HeartRecord, ActivityRecord, WorkoutRecord, BiomarkerRecord

@pytest.fixture
def temp_db(tmp_path):
    db_file = tmp_path / "test.db"
    init_db(str(db_file))
    return str(db_file)

def test_database_init_and_tables(temp_db):
    session = get_session(temp_db)()
    try:
        assert session.query(SleepRecord).count() == 0
        assert session.query(HeartRecord).count() == 0
        assert session.query(ActivityRecord).count() == 0
        assert session.query(WorkoutRecord).count() == 0
        assert session.query(BiomarkerRecord).count() == 0
    finally:
        session.close()
