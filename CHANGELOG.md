# 📋 Changelog

All notable changes to the **JB-Health-Project** are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html):
- **MAJOR** version when you make incompatible changes.
- **MINOR** version when you add functionality in a backward compatible manner.
- **PATCH** version when you make backward compatible bug fixes.

---

## [1.3.0] - 2026-09-07

### Added
- Add Google Gemini AI Health & Longevity Coach: 1-click executive briefings, biomarker interpretation, and interactive chat

---

## [1.2.2] - 2026-09-07

### Changed
- Fix sleep duration calculation: resolve multi-device overlapping intervals and deduplicate database records

---

## [1.2.0] - 2026-09-07

### Added
- **Multi-File Batch Quest PDF Uploader**: Support for selecting and processing multiple Quest Diagnostics PDF lab reports simultaneously in the browser, with real-time progress tracking.
- **Local Batch Ingestion**: Auto-detection of multiple Quest PDFs or Apple Health exports placed in `data/raw/` for 1-click local disk import.
- **2GB Upload Limit**: Raised Streamlit server maximum upload size to 2,048 MB (2 GB) in `.streamlit/config.toml` to support large multi-year Apple Health exports.
- **Step-by-Step Data Source Guides**: Built-in export instructions for Apple Health, MyFitnessPal, and Quest Diagnostics directly in the Data Import page.
- **Continuous Sleep Ribbon (`render_sleep_ribbon`)**: Horizontal distribution ribbon displaying proportional nightly stages (Deep, REM, Core, Awake).
- **Biomarker Range Pin Visualizer (`render_biomarker_range_bar`)**: Visual indicator mapping lab test values against clinical reference range boundaries.
- **Version Tracking System**: Added `src/__version__.py`, `CHANGELOG.md`, and automated `tools/bump_version.py` helper.

### Changed
- **Unified Design System**: Standardized glassmorphism stat cards (`render_stat_card`) across all 8 dashboard tabs.
- **Plotly Chart Styling**: Replaced box borders with faint dotted gridlines (`apply_dark_layout`), smooth spline curves, and glowing gradient area fills.
- **Theme Configuration**: Configured native dark theme in `.streamlit/config.toml` (Obsidian Navy `#080c16`, Slate Surface `#111827`, Cyan Accent `#06b6d4`).

---

## [1.1.0] - 2026-09-06

### Added
- **Performance & Training Load Engine (`src/analytics/training_load.py`)**: Banister impulse-response model computing Acute Training Load (ATL / 7-day fatigue), Chronic Training Load (CTL / 28-day fitness), Training Stress Balance (TSB), and Acute:Chronic Workload Ratio (ACWR).
- **Performance Coaching Prescriptions**: Automated fitness state classification (Peak, Optimal Building, Maintenance, High Fatigue).
- **Statsmodels Dependency**: Added `statsmodels>=0.14.0` for OLS trendlines with fallback error handling in scatter plots.

### Fixed
- **UTF-8 BOM Elimination**: Removed Windows PowerShell UTF-8 Byte Order Marks from configuration and source files.
- **Defensive Config Loading**: Configured `yaml.safe_load` with `encoding="utf-8-sig"` to prevent `yaml.parser.ParserError`.
- **Component Imports**: Fixed `apply_dark_layout` import in `app.py`.

---

## [1.0.0] - 2026-09-06

### Added
- **Initial Open-Source Release**: Full personal health, recovery, and sleep intelligence platform.
- **Apple Health Parser (`src/parsers/apple_health.py`)**: Memory-efficient streaming XML parser (`lxml.etree.iterparse`) for Sleep Analysis, HRV, Resting Heart Rate, Active Calories, Steps, VO2 Max, and workouts.
- **MyFitnessPal Parser (`src/parsers/myfitnesspal.py`)**: CSV parser for daily and meal-by-meal nutrition and macronutrients.
- **Quest Diagnostics Parser (`src/parsers/quest_diagnostics.py`)**: PDF and CSV lab report extractor with reference ranges and abnormal flags (`HIGH`, `LOW`).
- **Synthetic Mock Generator (`src/parsers/mock_generator.py`)**: 90-day realistic synthetic health datasets for 1-click demo preview.
- **Recovery Analytics Engine (`src/analytics/recovery.py`)**: Daily 0–100% readiness scores using 14-day rolling HRV z-scores and sleep architecture.
- **Multivariate Correlation Engine (`src/analytics/correlations.py`)**: Pearson correlation matrix and pairwise scatter plots.
- **Interactive Streamlit Dashboard (`app.py`)**: 8-tab interface with Plotly charts.
- **Privacy & Security Scanner (`tools/verify_clean_repo.py`)**: Pre-commit security scanner verifying zero PHI, personal health records, or secrets.
- **Strict `.gitignore`**: Blocks all `.db`, `.sqlite`, raw exports, and credentials from Git.
- **Documentation**: MIT License and comprehensive `README.md`.
