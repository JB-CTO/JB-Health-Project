import pytest
from src.database import init_db, get_session, BiomarkerRecord
from src.parsers.quest_diagnostics import QuestDiagnosticsParser, parse_reference_range, classify_category

def test_parse_reference_range():
    assert parse_reference_range("65-99") == (65.0, 99.0)
    assert parse_reference_range("<200") == (0.0, 200.0)
    assert parse_reference_range(">=40") == (40.0, None)
    assert parse_reference_range("30.0-100.0") == (30.0, 100.0)

def test_classify_category():
    assert classify_category("CHOLESTEROL, TOTAL") == "Lipids"
    assert classify_category("TRIGLYCERIDES") == "Lipids"
    assert classify_category("GLUCOSE") == "Metabolic"
    assert classify_category("TESTOSTERONE, TOTAL") == "Hormones"
    assert classify_category("C-REACTIVE PROTEIN, CARDIAC (hs-CRP)") == "Inflammation"
    assert classify_category("VITAMIN D, 25-HYDROXY") == "Vitamins"

def test_quest_pdf_parsing(tmp_path):
    db_file = str(tmp_path / "test_quest.db")
    init_db(db_file)
    parser = QuestDiagnosticsParser("data/samples/sample_quest_lab.pdf")
    count = parser.parse_and_store(db_file)
    assert count >= 15

    session = get_session(db_file)()
    try:
        rec = session.query(BiomarkerRecord).filter_by(test_name="GLUCOSE").first()
        assert rec is not None
        assert rec.value > 0
    finally:
        session.close()

def test_quest_csv_parsing(tmp_path):
    db_file = str(tmp_path / "test_quest_csv.db")
    init_db(db_file)
    parser = QuestDiagnosticsParser("data/samples/sample_quest_lab.csv")
    count = parser.parse_and_store(db_file)
    assert count > 0
