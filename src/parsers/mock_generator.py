"""
Synthetic Health Data Generator for JB-Health-Project.
Generates 100% anonymous, realistic synthetic health data for:
- Apple Health export.xml (Sleep, HRV, Resting HR, Workouts, Activity)
- MyFitnessPal nutrition.csv
- Quest Diagnostics lab reports (PDF & CSV)
Enables immediate testing and open-source demonstration with ZERO personal health information exposed.
"""

from datetime import datetime, timedelta
from pathlib import Path
import random
from typing import Optional
import os

from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors


def generate_mock_apple_health_xml(output_path: Path, days: int = 90):
    """Generates realistic Apple Health XML export file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    end_date = datetime.today()
    start_date = end_date - timedelta(days=days)

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<!DOCTYPE HealthData [',
        '<!ELEMENT HealthData (ExportDate, Me, (Record|Workout|ActivitySummary)*)>',
        '<!ATTLIST HealthData locale CDATA #REQUIRED>',
        ']>',
        '<HealthData locale="en_US">',
        f'  <ExportDate value="{end_date.strftime("%Y-%m-%d %H:%M:%S -0500")}"/>',
        '  <Me HKCharacteristicTypeIdentifierDateOfBirth="1988-05-15" HKCharacteristicTypeIdentifierBiologicalSex="HKBiologicalSexMale"/>'
    ]

    current_dt = start_date
    while current_dt <= end_date:
        d_str = current_dt.strftime("%Y-%m-%d")
        
        # 1. Sleep: Bedtime ~ 23:00, wake ~ 07:00 (7.5 - 8.5 hrs)
        bed_hour = random.choice([22, 23, 0])
        bed_min = random.randint(0, 50)
        if bed_hour == 0:
            sleep_start = datetime(current_dt.year, current_dt.month, current_dt.day, 0, bed_min)
        else:
            prev = current_dt - timedelta(days=1)
            sleep_start = datetime(prev.year, prev.month, prev.day, bed_hour, bed_min)
        
        wake_time = sleep_start + timedelta(hours=random.uniform(7.0, 8.5))

        # Sleep stages breakdown
        t = sleep_start
        while t < wake_time:
            # Pick a stage: Awake (5%), Deep (20%), REM (25%), Core (50%)
            stage_choice = random.choices(
                ["Awake", "Deep", "REM", "Core"],
                weights=[0.08, 0.20, 0.25, 0.47]
            )[0]
            stage_map = {
                "Awake": "HKCategoryValueSleepAnalysisAwake",
                "Deep": "HKCategoryValueSleepAnalysisAsleepDeep",
                "REM": "HKCategoryValueSleepAnalysisAsleepREM",
                "Core": "HKCategoryValueSleepAnalysisAsleepCore",
            }
            duration_min = random.randint(15, 60)
            next_t = min(wake_time, t + timedelta(minutes=duration_min))
            lines.append(
                f'  <Record type="HKCategoryTypeIdentifierSleepAnalysis" '
                f'sourceName="Apple Watch" unit="count" '
                f'startDate="{t.strftime("%Y-%m-%d %H:%M:%S -0500")}" '
                f'endDate="{next_t.strftime("%Y-%m-%d %H:%M:%S -0500")}" '
                f'value="{stage_map[stage_choice]}"/>'
            )
            t = next_t

        # 2. Resting Heart Rate (around 52-62 bpm)
        rhr = round(random.gauss(56, 3), 1)
        rhr_dt = datetime(current_dt.year, current_dt.month, current_dt.day, 7, 30)
        lines.append(
            f'  <Record type="HKQuantityTypeIdentifierRestingHeartRate" '
            f'sourceName="Apple Watch" unit="count/min" '
            f'startDate="{rhr_dt.strftime("%Y-%m-%d %H:%M:%S -0500")}" '
            f'endDate="{rhr_dt.strftime("%Y-%m-%d %H:%M:%S -0500")}" '
            f'value="{rhr}"/>'
        )

        # 3. Heart Rate Variability (SDNN) (around 45-75 ms)
        hrv = round(max(25.0, random.gauss(60, 12)), 1)
        hrv_dt = datetime(current_dt.year, current_dt.month, current_dt.day, 6, 45)
        lines.append(
            f'  <Record type="HKQuantityTypeIdentifierHeartRateVariabilitySDNN" '
            f'sourceName="Apple Watch" unit="ms" '
            f'startDate="{hrv_dt.strftime("%Y-%m-%d %H:%M:%S -0500")}" '
            f'endDate="{hrv_dt.strftime("%Y-%m-%d %H:%M:%S -0500")}" '
            f'value="{hrv}"/>'
        )

        # 4. Activity (Active Calories, Steps, Exercise Minutes)
        act_cals = round(random.gauss(650, 180), 1)
        steps = int(random.gauss(10500, 2500))
        ex_min = round(max(15.0, random.gauss(50, 20)), 1)
        midday = datetime(current_dt.year, current_dt.month, current_dt.day, 12, 0)
        lines.append(
            f'  <Record type="HKQuantityTypeIdentifierActiveEnergyBurned" '
            f'sourceName="Apple Watch" unit="kcal" '
            f'startDate="{midday.strftime("%Y-%m-%d %H:%M:%S -0500")}" '
            f'endDate="{midday.strftime("%Y-%m-%d %H:%M:%S -0500")}" '
            f'value="{act_cals}"/>'
        )
        lines.append(
            f'  <Record type="HKQuantityTypeIdentifierStepCount" '
            f'sourceName="iPhone" unit="count" '
            f'startDate="{midday.strftime("%Y-%m-%d %H:%M:%S -0500")}" '
            f'endDate="{midday.strftime("%Y-%m-%d %H:%M:%S -0500")}" '
            f'value="{steps}"/>'
        )
        lines.append(
            f'  <Record type="HKQuantityTypeIdentifierAppleExerciseTime" '
            f'sourceName="Apple Watch" unit="min" '
            f'startDate="{midday.strftime("%Y-%m-%d %H:%M:%S -0500")}" '
            f'endDate="{midday.strftime("%Y-%m-%d %H:%M:%S -0500")}" '
            f'value="{ex_min}"/>'
        )

        # 5. VO2 Max (once per week)
        if current_dt.weekday() == 0:
            vo2 = round(random.gauss(47.5, 1.2), 1)
            lines.append(
                f'  <Record type="HKQuantityTypeIdentifierVO2Max" '
                f'sourceName="Apple Watch" unit="mL/min·kg" '
                f'startDate="{midday.strftime("%Y-%m-%d %H:%M:%S -0500")}" '
                f'endDate="{midday.strftime("%Y-%m-%d %H:%M:%S -0500")}" '
                f'value="{vo2}"/>'
            )

        # 6. Workouts (5 days a week)
        if random.random() < 0.75:
            wk_types = [
                ("HKWorkoutActivityTypeRunning", 35, 400, 5.2),
                ("HKWorkoutActivityTypeTraditionalStrengthTraining", 55, 320, 0.0),
                ("HKWorkoutActivityTypeCycling", 45, 450, 15.0),
                ("HKWorkoutActivityTypeHighIntensityIntervalTraining", 30, 350, 0.0),
            ]
            w_type, dur, w_cals, dist = random.choice(wk_types)
            wk_start = datetime(current_dt.year, current_dt.month, current_dt.day, random.choice([7, 17]), 0)
            wk_end = wk_start + timedelta(minutes=dur)
            lines.append(
                f'  <Workout workoutActivityType="{w_type}" '
                f'duration="{dur}" durationUnit="min" '
                f'totalEnergyBurned="{w_cals}" totalEnergyBurnedUnit="kcal" '
                f'totalDistance="{dist}" totalDistanceUnit="km" '
                f'sourceName="Apple Watch" '
                f'startDate="{wk_start.strftime("%Y-%m-%d %H:%M:%S -0500")}" '
                f'endDate="{wk_end.strftime("%Y-%m-%d %H:%M:%S -0500")}"/>'
            )

        # 7. Dietary Sync (Apple Health synced with MyFitnessPal)
        prot = round(random.gauss(165, 25), 1)
        carbs = round(random.gauss(240, 45), 1)
        fat = round(random.gauss(70, 15), 1)
        cals = round((prot * 4) + (carbs * 4) + (fat * 9))
        lines.append(
            f'  <Record type="HKQuantityTypeIdentifierDietaryEnergyConsumed" '
            f'sourceName="MyFitnessPal" unit="kcal" '
            f'startDate="{midday.strftime("%Y-%m-%d %H:%M:%S -0500")}" '
            f'endDate="{midday.strftime("%Y-%m-%d %H:%M:%S -0500")}" '
            f'value="{cals}"/>'
        )
        lines.append(
            f'  <Record type="HKQuantityTypeIdentifierDietaryProtein" '
            f'sourceName="MyFitnessPal" unit="g" '
            f'startDate="{midday.strftime("%Y-%m-%d %H:%M:%S -0500")}" '
            f'endDate="{midday.strftime("%Y-%m-%d %H:%M:%S -0500")}" '
            f'value="{prot}"/>'
        )
        lines.append(
            f'  <Record type="HKQuantityTypeIdentifierDietaryCarbohydrates" '
            f'sourceName="MyFitnessPal" unit="g" '
            f'startDate="{midday.strftime("%Y-%m-%d %H:%M:%S -0500")}" '
            f'endDate="{midday.strftime("%Y-%m-%d %H:%M:%S -0500")}" '
            f'value="{carbs}"/>'
        )
        lines.append(
            f'  <Record type="HKQuantityTypeIdentifierDietaryFatTotal" '
            f'sourceName="MyFitnessPal" unit="g" '
            f'startDate="{midday.strftime("%Y-%m-%d %H:%M:%S -0500")}" '
            f'endDate="{midday.strftime("%Y-%m-%d %H:%M:%S -0500")}" '
            f'value="{fat}"/>'
        )

        current_dt += timedelta(days=1)

    lines.append('</HealthData>')

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def generate_mock_mfp_csv(output_path: Path, days: int = 90):
    """Generates realistic MyFitnessPal CSV export."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    end_date = datetime.today()
    start_date = end_date - timedelta(days=days)

    rows = ["Date,Meal,Calories,Fat (g),Carbohydrates (g),Fiber (g),Sugar (g),Protein (g),Sodium (mg),Water (ml)"]
    current_dt = start_date
    while current_dt <= end_date:
        d_str = current_dt.strftime("%Y-%m-%d")
        prot = round(random.gauss(165, 20), 1)
        carbs = round(random.gauss(230, 35), 1)
        fat = round(random.gauss(68, 12), 1)
        fiber = round(random.gauss(32, 6), 1)
        sugar = round(random.gauss(45, 15), 1)
        sodium = round(random.gauss(2400, 400), 0)
        water = round(random.gauss(3200, 500), 0)
        cals = round((prot * 4) + (carbs * 4) + (fat * 9))

        rows.append(f"{d_str},DailySummary,{cals},{fat},{carbs},{fiber},{sugar},{prot},{sodium},{water}")
        current_dt += timedelta(days=1)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(rows))


def generate_mock_quest_pdf(output_path: Path, collection_date: Optional[str] = None):
    """Generates an authentic looking Quest Diagnostics PDF lab report."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if not collection_date:
        collection_date = (datetime.today() - timedelta(days=14)).strftime("%m/%d/%Y")

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=letter,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("TitleStyle", parent=styles["Heading1"], fontSize=18, textColor=colors.HexColor("#0f766e"))
    header_style = ParagraphStyle("HeaderStyle", parent=styles["Normal"], fontSize=9, leading=12)
    sec_style = ParagraphStyle("SecStyle", parent=styles["Heading2"], fontSize=12, textColor=colors.HexColor("#1e293b"))

    elements = []

    # Title & Header
    elements.append(Paragraph("Quest Diagnostics - Laboratory Report", title_style))
    elements.append(Spacer(1, 10))

    header_text = f"""
    <b>PATIENT:</b> DOE, JOHN (SYNTHETIC MOCK)<br/>
    <b>DOB:</b> 01/01/1988 &nbsp;&nbsp;|&nbsp;&nbsp; <b>AGE:</b> 38 &nbsp;&nbsp;|&nbsp;&nbsp; <b>GENDER:</b> M<br/>
    <b>Date Collected:</b> {collection_date} &nbsp;&nbsp;|&nbsp;&nbsp; <b>Report Date:</b> {collection_date}<br/>
    <b>ORDERING PHYSICIAN:</b> DR. HEALTH CONSULTANT, MD<br/>
    <b>STATUS:</b> FINAL REPORT
    """
    elements.append(Paragraph(header_text, header_style))
    elements.append(Spacer(1, 15))

    # Test Results Data Table
    data = [
        ["Test Name", "In Range", "Out Of Range", "Reference Range", "Units"]
    ]

    tests = [
        # Lipids
        ("CHOLESTEROL, TOTAL", "182", "", "<200", "mg/dL"),
        ("HDL CHOLESTEROL", "58", "", ">=40", "mg/dL"),
        ("TRIGLYCERIDES", "92", "", "<150", "mg/dL"),
        ("LDL CHOLESTEROL", "106", "H", "<100", "mg/dL"),
        ("CHOLESTEROL/HDL RATIO", "3.1", "", "<5.0", "ratio"),
        # Metabolic (CMP)
        ("GLUCOSE", "88", "", "65-99", "mg/dL"),
        ("HEMOGLOBIN A1c", "5.2", "", "<5.7", "%"),
        ("UREA NITROGEN (BUN)", "16", "", "7-25", "mg/dL"),
        ("CREATININE", "0.98", "", "0.60-1.35", "mg/dL"),
        ("eGFR", "96", "", ">=60", "mL/min/1.73m2"),
        ("SODIUM", "140", "", "135-146", "mmol/L"),
        ("POTASSIUM", "4.4", "", "3.5-5.3", "mmol/L"),
        ("CALCIUM", "9.4", "", "8.6-10.3", "mg/dL"),
        ("PROTEIN, TOTAL", "7.1", "", "6.1-8.1", "g/dL"),
        ("ALBUMIN", "4.6", "", "3.6-5.1", "g/dL"),
        ("AST", "22", "", "10-40", "U/L"),
        ("ALT", "24", "", "9-46", "U/L"),
        # Hormones & Recovery
        ("TESTOSTERONE, TOTAL", "685", "", "264-916", "ng/dL"),
        ("TESTOSTERONE, FREE", "14.8", "", "9.3-26.5", "pg/mL"),
        ("TSH", "1.75", "", "0.40-4.50", "mIU/L"),
        ("CORTISOL", "12.4", "", "4.0-22.0", "ug/dL"),
        # Inflammation & Vitamins
        ("C-REACTIVE PROTEIN, CARDIAC (hs-CRP)", "0.65", "", "<1.00", "mg/L"),
        ("VITAMIN D, 25-HYDROXY", "54.2", "", "30.0-100.0", "ng/mL"),
        ("FERRITIN", "145", "", "38-380", "ng/mL"),
        ("VITAMIN B12", "620", "", "200-1100", "pg/mL")
    ]

    for name, in_rng, out_rng, ref, unit in tests:
        data.append([name, in_rng, out_rng, ref, unit])

    t = Table(data, colWidths=[200, 75, 75, 110, 80])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0f766e')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 5),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('TEXTCOLOR', (2, 1), (2, -1), colors.HexColor('#dc2626')), # Red for out of range
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')])
    ]))

    elements.append(t)
    doc.build(elements)


def generate_mock_quest_csv(output_path: Path):
    """Generates quarterly historical Quest Diagnostics CSV records."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    today = datetime.today()
    q3_date = (today - timedelta(days=180)).strftime("%Y-%m-%d")
    q2_date = (today - timedelta(days=90)).strftime("%Y-%m-%d")
    q1_date = (today - timedelta(days=14)).strftime("%Y-%m-%d")

    quarterly_data = [
        # Quarter 3 (6 months ago)
        (q3_date, "CHOLESTEROL, TOTAL", 210, "mg/dL", 0, 200, "HIGH"),
        (q3_date, "HDL CHOLESTEROL", 48, "mg/dL", 40, None, "NORMAL"),
        (q3_date, "LDL CHOLESTEROL", 132, "mg/dL", 0, 100, "HIGH"),
        (q3_date, "TRIGLYCERIDES", 145, "mg/dL", 0, 150, "NORMAL"),
        (q3_date, "GLUCOSE", 94, "mg/dL", 65, 99, "NORMAL"),
        (q3_date, "HEMOGLOBIN A1c", 5.4, "%", 0, 5.7, "NORMAL"),
        (q3_date, "TESTOSTERONE, TOTAL", 580, "ng/dL", 264, 916, "NORMAL"),
        (q3_date, "C-REACTIVE PROTEIN, CARDIAC (hs-CRP)", 1.45, "mg/L", 0, 1.0, "HIGH"),
        (q3_date, "VITAMIN D, 25-HYDROXY", 32.0, "ng/mL", 30.0, 100.0, "NORMAL"),

        # Quarter 2 (3 months ago)
        (q2_date, "CHOLESTEROL, TOTAL", 195, "mg/dL", 0, 200, "NORMAL"),
        (q2_date, "HDL CHOLESTEROL", 53, "mg/dL", 40, None, "NORMAL"),
        (q2_date, "LDL CHOLESTEROL", 118, "mg/dL", 0, 100, "HIGH"),
        (q2_date, "TRIGLYCERIDES", 110, "mg/dL", 0, 150, "NORMAL"),
        (q2_date, "GLUCOSE", 90, "mg/dL", 65, 99, "NORMAL"),
        (q2_date, "HEMOGLOBIN A1c", 5.3, "%", 0, 5.7, "NORMAL"),
        (q2_date, "TESTOSTERONE, TOTAL", 640, "ng/dL", 264, 916, "NORMAL"),
        (q2_date, "C-REACTIVE PROTEIN, CARDIAC (hs-CRP)", 0.85, "mg/L", 0, 1.0, "NORMAL"),
        (q2_date, "VITAMIN D, 25-HYDROXY", 46.0, "ng/mL", 30.0, 100.0, "NORMAL"),

        # Quarter 1 (Recent)
        (q1_date, "CHOLESTEROL, TOTAL", 182, "mg/dL", 0, 200, "NORMAL"),
        (q1_date, "HDL CHOLESTEROL", 58, "mg/dL", 40, None, "NORMAL"),
        (q1_date, "LDL CHOLESTEROL", 106, "mg/dL", 0, 100, "HIGH"),
        (q1_date, "TRIGLYCERIDES", 92, "mg/dL", 0, 150, "NORMAL"),
        (q1_date, "GLUCOSE", 88, "mg/dL", 65, 99, "NORMAL"),
        (q1_date, "HEMOGLOBIN A1c", 5.2, "%", 0, 5.7, "NORMAL"),
        (q1_date, "TESTOSTERONE, TOTAL", 685, "ng/dL", 264, 916, "NORMAL"),
        (q1_date, "C-REACTIVE PROTEIN, CARDIAC (hs-CRP)", 0.65, "mg/L", 0, 1.0, "NORMAL"),
        (q1_date, "VITAMIN D, 25-HYDROXY", 54.2, "ng/mL", 30.0, 100.0, "NORMAL"),
    ]

    import csv
    headers = ["date", "test_name", "value", "unit", "ref_low", "ref_high", "flag"]
    formatted_data = []
    for d, t_name, val, unit, r_low, r_high, flag in quarterly_data:
        low_str = str(r_low) if r_low is not None else ""
        high_str = str(r_high) if r_high is not None else ""
        formatted_data.append([d, t_name, val, unit, low_str, high_str, flag])

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(formatted_data)


def generate_all_samples(base_dir: Path):
    """Generates all sample files into data/samples/."""
    samples_dir = base_dir / "data" / "samples"
    samples_dir.mkdir(parents=True, exist_ok=True)
    
    xml_path = samples_dir / "sample_apple_health.xml"
    mfp_path = samples_dir / "sample_myfitnesspal.csv"
    pdf_path = samples_dir / "sample_quest_lab.pdf"
    csv_path = samples_dir / "sample_quest_lab.csv"

    print("Generating synthetic Apple Health XML...")
    generate_mock_apple_health_xml(xml_path, days=90)
    print("Generating synthetic MyFitnessPal CSV...")
    generate_mock_mfp_csv(mfp_path, days=90)
    print("Generating synthetic Quest Diagnostics PDF...")
    generate_mock_quest_pdf(pdf_path)
    print("Generating synthetic Quest Diagnostics CSV...")
    generate_mock_quest_csv(csv_path)
    print("All mock sample files generated successfully!")


if __name__ == "__main__":
    root = Path(__file__).resolve().parent.parent.parent
    generate_all_samples(root)
