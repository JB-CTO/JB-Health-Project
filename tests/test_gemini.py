import pytest
from src.database import init_db
from src.parsers.mock_generator import generate_all_samples
from src.parsers.apple_health import AppleHealthParser
from src.parsers.quest_diagnostics import QuestDiagnosticsParser
from src.analytics.recovery import compute_daily_recovery
from src.analytics.training_load import compute_training_load
from src.ai.context_builder import build_health_context
from src.ai.gemini_assistant import GeminiHealthAssistant, AVAILABLE_MODELS


def test_context_builder_and_deidentification(tmp_path):
    db_file = str(tmp_path / "test_gemini.db")
    init_db(db_file)

    # Ingest sample data
    AppleHealthParser("data/samples/sample_apple_health.xml").parse_and_store(db_file)
    QuestDiagnosticsParser("data/samples/sample_quest_lab.csv").parse_and_store(db_file)
    compute_daily_recovery(db_file)
    compute_training_load(db_file)

    targets = {
        "sleep_hours_target": 8.0,
        "daily_active_calories": 600,
        "daily_protein_g_target": 160.0
    }

    context = build_health_context(db_file, days=30, targets=targets)
    assert len(context) > 500
    assert "DE-IDENTIFIED PERSONAL HEALTH & PERFORMANCE SNAPSHOT" in context
    assert "Autonomic Readiness" in context
    assert "Sleep Architecture" in context
    assert "Training Load" in context
    assert "Clinical Biomarkers" in context

    # Test de-identification: no patient names or SSNs
    assert "John Doe" not in context
    assert "SSN" not in context


def test_gemini_assistant_initialization_and_fallbacks():
    # Test without API key
    asst = GeminiHealthAssistant(api_key=None)
    assert not asst.is_available()

    briefing = asst.generate_executive_briefing("test context")
    assert "Gemini API Key Required" in briefing

    chat_resp = asst.chat_turn("Hello", [], "test context")
    assert "Gemini API Key Required" in chat_resp

    # Test model selection
    assert "gemini-3.7-flash" in AVAILABLE_MODELS
    assert "gemini-2.5-pro" in AVAILABLE_MODELS
    assert "gemini-3.5-flash-lite" in AVAILABLE_MODELS

    asst_custom = GeminiHealthAssistant(api_key="test_dummy_key", model_name="gemini-2.5-pro")
    assert asst_custom.model_name == "gemini-2.5-pro"