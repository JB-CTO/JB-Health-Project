# ⚡ JB-Health-Project

> **An open-source, privacy-first personal health, recovery, and performance intelligence platform.**  
> Unify data from **Apple Health**, **MyFitnessPal**, and **Quest Diagnostics (Blood Work)** into interactive, actionable dashboards to optimize sleep, physiological recovery, and athletic training load.

[![Version: v1.2.0](https://img.shields.io/badge/Version-v1.2.0-cyan.svg)](CHANGELOG.md)
[![License: MIT](https://img.shields.io/badge/License-MIT-teal.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.35%2B-red.svg)](https://streamlit.io/)
[![Privacy First](https://img.shields.io/badge/Privacy-Zero--PHI--Guaranteed-green.svg)](#-privacy-and-open-source-safety)

---

## 🌟 Key Features

### 1. ⚡ Physiological Recovery & Readiness Command Center
- **Readiness Score (0–100%)**: Multi-factorial recovery model combining HRV deviation from your personal 14-day rolling baseline, resting heart rate deviation, and sleep architecture.
- **Heart Rate Variability (HRV - SDNN)**: High-resolution tracking with rolling baseline bands and z-score analysis.
- **Resting Heart Rate (RHR)**: Cardiovascular recovery trends and strain indicators.

### 2. 🌙 Sleep Architecture & Optimization
- **Sleep Stage Breakdown**: Tracks **Deep Sleep**, **REM Sleep**, **Core/Light Sleep**, and **Awake time**.
- **Sleep Quality Score**: Evaluates total sleep duration against optimal targets and percentage of restorative sleep (Deep % + REM %).
- **Cumulative Sleep Debt**: Quantifies cumulative sleep deficits over rolling 7-day windows.

### 3. 🏋️ Workout Performance & Training Load (ATL / CTL / TSB)
- **Impulse-Response Training Model**:
  - **Acute Training Load (ATL / 7-Day EMA)**: Quantifies short-term fatigue.
  - **Chronic Training Load (CTL / 28-Day EMA)**: Quantifies long-term aerobic fitness base.
  - **Training Stress Balance (TSB = CTL - ATL)**: Determines your readiness state (**Fresh / Peaking**, **Optimal Building**, **Maintenance**, or **High Overreaching Risk**).
  - **Acute:Chronic Workload Ratio (ACWR)**: Monitors injury risk threshold (0.8–1.3 sweet spot).
- **Workout Breakdown**: Visualizes sessions by activity type (Running, Strength Training, Cycling, HIIT), active calories burned, duration, and VO2 Max progression.

### 4. 🧪 Quest Diagnostics Blood Work & Biomarker Tracker
- **Native PDF & CSV Parsing**: Automatically extracts biomarker values, reference ranges, and abnormal flags directly from Quest Diagnostics lab report PDFs.
- **Categorized Panels**: Lipids, Comprehensive Metabolic Panel (CMP), Hormones & Endocrine, Systemic Inflammation, and Vitamins.
- **Interactive Time Series**: Visualizes multi-year lab draws with shaded **Normal Reference Range Bands** (green zones) and out-of-range alert flags.
- **Clinical Health Ratios**: Calculates Triglyceride-to-HDL ratio, Cholesterol/HDL ratio, and hs-CRP inflammation markers.

### 5. 🥗 Nutrition & Fueling Analytics
- Ingests dietary logs from **MyFitnessPal** (or Apple Health nutrition sync).
- Tracks daily macronutrient splits (Protein, Carbohydrates, Dietary Fat).
- Energy Balance: Compares daily caloric intake vs active energy expenditure.
- Protein-to-bodyweight optimization and hydration tracking.

### 6. 🔍 Multivariate Correlation & Insights Engine
- Computes **Pearson correlation matrices** and p-values between lifestyle habits and recovery outputs.
- Discover actionable answers:
  - *How does late dinner or high carbohydrate intake impact your next-day HRV and deep sleep?*
  - *Does high training strain increase resting heart rate or sleep latency?*
  - *How does cardiorespiratory fitness (VO2 Max) correlate with resting metabolic biomarkers?*

### 7. 📊 Custom Visualizer & Ad-Hoc Dashboard Builder
- Create custom charts on the fly by selecting any X-axis, Y-axis, chart type (Line, Bar, Scatter with OLS trendline, Box plot), and date ranges.

---

## 🔒 Privacy and Open-Source Safety

This repository is designed from the ground up to be safe for open-source sharing:
1. **100% Local Storage**: All your personal data is stored in a local SQLite database (`data/health.db`) on your computer. Nothing is sent to external servers or cloud APIs.
2. **Strict `.gitignore`**: Automatically ignores all databases, raw exports (`*.xml`, `*.zip`, `*.pdf`, `*.csv` outside samples), and logs.
3. **Turnkey Demo Dataset**: Comes with 90 days of realistic, anonymized synthetic mock data so anyone cloning your repo can test the application immediately without uploading private data.
4. **Pre-Push PHI Scanner**: Includes `tools/verify_clean_repo.py`, an automated security scanner that verifies zero personal health information or credentials are in the git staging area before pushing.

---

## 🚀 Quickstart Guide

### Prerequisites
- Python 3.10, 3.11, or 3.12
- Git

### 1. Clone the Repository
```bash
git clone https://github.com/JB-CTO/JB-Health-Project.git
cd JB-Health-Project
```

### 2. Create Virtual Environment & Install Dependencies
```bash
# On Windows:
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt

# On macOS / Linux:
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Launch the Dashboard
```bash
streamlit run app.py
```
Open your browser to `http://localhost:8501`.

> **Tip**: Click **"🚀 Load Demo / Sample Data"** in the sidebar to preview the dashboard with 90 days of synthetic data in 5 seconds!

---

## 📥 How to Export Your Personal Data

### 1. Apple Health (iPhone)
1. Open the **Health** app on your iPhone.
2. Tap your profile picture in the top-right corner.
3. Scroll down and tap **Export All Health Data**.
4. Tap **Export** (this creates an `export.zip` file containing `export.xml`).
5. Transfer `export.zip` to your computer (AirDrop, iCloud Drive, or cable).
6. Go to the **📁 Data Import** tab in the dashboard and drag-and-drop `export.zip`.

### 2. MyFitnessPal
- **Option A (Automatic via Apple Health - Recommended)**: If MyFitnessPal is connected to Apple Health on your iPhone, all dietary calories, protein, carbs, and fat are automatically included in your Apple Health export!
- **Option B (CSV Export)**: On the MyFitnessPal website (or app under Reports), export your **Nutrition Summary CSV** and upload it in the **📁 Data Import** tab.

### 3. Quest Diagnostics (Blood Work)
1. Log in to your **MyQuest** patient portal (`myquest.questdiagnostics.com`).
2. Navigate to **Results** and select your lab report.
3. Click **Download PDF Report**.
4. In the dashboard's **📁 Data Import** tab, upload the PDF directly. The parser automatically extracts all biomarker panels, values, and reference ranges.

---

## ⚙️ Configuration (`config.yaml`)

Customize targets and baseline parameters to match your physiology:

```yaml
targets:
  sleep_hours_target: 8.0          # Target nightly sleep
  daily_active_calories: 600       # Target active calories
  daily_protein_g_target: 160.0    # Target daily protein intake (g)

recovery_model:
  hrv_baseline_days: 14            # Rolling baseline window for HRV
  rhr_baseline_days: 14            # Rolling baseline window for RHR

training_load:
  acute_days: 7                    # Short-term fatigue (ATL)
  chronic_days: 28                 # Long-term fitness (CTL)
```

---

## 🧪 Testing & Verification

Run the automated test suite:
```bash
pytest -v
```

Run the privacy & PHI security scanner:
```bash
python tools/verify_clean_repo.py
```

---

## 🏷️ Version Tracking & Documenting Changes

This project adheres to [Semantic Versioning](https://semver.org/) (`MAJOR.MINOR.PATCH`). All notable releases and code changes are documented in [`CHANGELOG.md`](CHANGELOG.md).

### How to document changes & bump versions
Whenever you make updates to the codebase and want to document them in GitHub, use the automated version tracking helper:

```bash
# For bug fixes, UI tweaks, or minor updates (e.g. v1.2.0 -> v1.2.1):
python tools/bump_version.py patch "Fixed X, polished Y"

# For new features, parsers, or dashboards (e.g. v1.2.0 -> v1.3.0):
python tools/bump_version.py minor "Added feature Z"

# For breaking architectural changes (e.g. v1.2.0 -> v2.0.0):
python tools/bump_version.py major "Overhauled data pipeline"
```

The script automatically:
1. Increments `__version__` in `src/__version__.py`.
2. Prepends a formatted release entry with today's date in `CHANGELOG.md`.
3. Prompts the Git commands to commit, tag (`git tag vX.Y.Z`), and push tags (`git push --follow-tags`) to GitHub!

---

## 📄 License

Distributed under the [MIT License](LICENSE).
