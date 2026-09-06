import pytest
from src.database import init_db, get_session, NutritionRecord
from src.parsers.myfitnesspal import MyFitnessPalParser

def test_mfp_parsing(tmp_path):
    db_file = str(tmp_path / "test_mfp.db")
    init_db(db_file)
    parser = MyFitnessPalParser("data/samples/sample_myfitnesspal.csv")
    count = parser.parse_and_store(db_file)
    assert count > 0

    session = get_session(db_file)()
    try:
        sample = session.query(NutritionRecord).first()
        assert sample is not None
        assert sample.calories > 0
        assert sample.protein_g > 0
    finally:
        session.close()
