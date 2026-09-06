"""
Apple Health Export Parser (Streaming XML).
Parses Apple Health exports (export.xml or export.zip) efficiently without memory overload.
Extracts sleep stages, HRV, resting heart rate, active calories, workouts, and nutrition sync.
"""

from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Generator, List, Optional, Tuple, Any
import zipfile
import re

from lxml import etree
import pandas as pd
from sqlalchemy.orm import Session

from src.database import (
    SleepRecord, HeartRecord, ActivityRecord, WorkoutRecord, NutritionRecord, get_session
)

# Mapping Apple Health Sleep Values
SLEEP_STAGE_MAP = {
    "HKCategoryValueSleepAnalysisInBed": "InBed",
    "HKCategoryValueSleepAnalysisAsleepUnspecified": "Core",
    "HKCategoryValueSleepAnalysisAsleepCore": "Core",
    "HKCategoryValueSleepAnalysisAsleepDeep": "Deep",
    "HKCategoryValueSleepAnalysisAsleepREM": "REM",
    "HKCategoryValueSleepAnalysisAwake": "Awake",
}

# Mapping Apple Workout Types
def clean_workout_type(raw_type: str) -> str:
    """Cleans HKWorkoutActivityTypeTraditionalStrengthTraining to Strength Training."""
    cleaned = raw_type.replace("HKWorkoutActivityType", "")
    # Add spacing between camel case
    cleaned = re.sub(r"([a-z])([A-Z])", r"\1 \2", cleaned)
    return cleaned.strip()


def parse_apple_date(date_str: str) -> datetime:
    """Parses Apple Health datetime string: '2024-03-01 07:15:00 -0500'."""
    # Strip timezone offset for local naive representation
    cleaned = date_str[:19]
    return datetime.strptime(cleaned, "%Y-%m-%d %H:%M:%S")


def get_sleep_canonical_date(start_dt: datetime) -> str:
    """
    Groups sleep that happens overnight into a single date.
    If sleep starts before noon (e.g. 2:00 AM on March 2nd), it belongs to March 1st night.
    If sleep starts after 18:00 (e.g. 10:30 PM on March 1st), it belongs to March 1st night.
    """
    if start_dt.hour < 12:
        canonical = start_dt.date() - timedelta(days=1)
    else:
        canonical = start_dt.date()
    return canonical.strftime("%Y-%m-%d")


class AppleHealthParser:
    def __init__(self, file_path: str):
        self.file_path = Path(file_path)
        if not self.file_path.exists():
            raise FileNotFoundError(f"File not found: {self.file_path}")

    def get_xml_file_handle(self):
        """Yields open file handle for export.xml whether given a .zip or .xml file."""
        if self.file_path.suffix.lower() == ".zip":
            zf = zipfile.ZipFile(self.file_path, "r")
            # Look for export.xml inside the zip
            xml_names = [name for name in zf.namelist() if name.endswith("export.xml")]
            if not xml_names:
                raise ValueError("No export.xml found inside the zip file.")
            return zf.open(xml_names[0])
        else:
            return open(self.file_path, "rb")

    def parse_and_store(self, db_path: Optional[str] = None, batch_size: int = 2000) -> Dict[str, int]:
        """
        Streams through Apple Health XML and stores parsed records directly into SQLite.
        Returns summary count of imported records.
        """
        session = get_session(db_path)()
        counts = {
            "sleep": 0,
            "hrv": 0,
            "resting_hr": 0,
            "heart_rate": 0,
            "activity_days": 0,
            "workouts": 0,
            "nutrition": 0,
        }

        # Daily accumulators for activity and nutrition
        daily_activity: Dict[str, Dict[str, float]] = {}
        daily_nutrition: Dict[str, Dict[str, float]] = {}

        file_obj = self.get_xml_file_handle()
        try:
            # iterparse allows streaming huge XMLs with near-zero RAM
            context = etree.iterparse(file_obj, events=("end",), tag=("Record", "Workout"))
            
            pending_records = []

            for event, elem in context:
                tag = elem.tag
                attrib = elem.attrib

                if tag == "Record":
                    rec_type = attrib.get("type", "")

                    # 1. Sleep Analysis
                    if rec_type == "HKCategoryTypeIdentifierSleepAnalysis":
                        val = attrib.get("value", "")
                        stage = SLEEP_STAGE_MAP.get(val, "Core")
                        try:
                            start_dt = parse_apple_date(attrib["startDate"])
                            end_dt = parse_apple_date(attrib["endDate"])
                            duration_min = (end_dt - start_dt).total_seconds() / 60.0
                            if duration_min > 0:
                                sleep_rec = SleepRecord(
                                    date=get_sleep_canonical_date(start_dt),
                                    start_time=start_dt,
                                    end_time=end_dt,
                                    stage=stage,
                                    duration_minutes=duration_min,
                                    source="AppleHealth"
                                )
                                pending_records.append(sleep_rec)
                                counts["sleep"] += 1
                        except Exception:
                            pass

                    # 2. Heart Rate Variability (SDNN)
                    elif rec_type == "HKQuantityTypeIdentifierHeartRateVariabilitySDNN":
                        try:
                            start_dt = parse_apple_date(attrib["startDate"])
                            val = float(attrib.get("value", 0))
                            unit = attrib.get("unit", "ms")
                            pending_records.append(HeartRecord(
                                timestamp=start_dt,
                                date=start_dt.strftime("%Y-%m-%d"),
                                metric="hrv_sdnn",
                                value=val,
                                unit=unit,
                                source="AppleHealth"
                            ))
                            counts["hrv"] += 1
                        except Exception:
                            pass

                    # 3. Resting Heart Rate
                    elif rec_type == "HKQuantityTypeIdentifierRestingHeartRate":
                        try:
                            start_dt = parse_apple_date(attrib["startDate"])
                            val = float(attrib.get("value", 0))
                            pending_records.append(HeartRecord(
                                timestamp=start_dt,
                                date=start_dt.strftime("%Y-%m-%d"),
                                metric="resting_hr",
                                value=val,
                                unit="bpm",
                                source="AppleHealth"
                            ))
                            counts["resting_hr"] += 1
                        except Exception:
                            pass

                    # 4. Activity Totals (Active Energy, Basal, Steps, Exercise Minutes, VO2 Max)
                    elif rec_type in (
                        "HKQuantityTypeIdentifierActiveEnergyBurned",
                        "HKQuantityTypeIdentifierBasalEnergyBurned",
                        "HKQuantityTypeIdentifierStepCount",
                        "HKQuantityTypeIdentifierAppleExerciseTime",
                        "HKQuantityTypeIdentifierVO2Max"
                    ):
                        try:
                            start_dt = parse_apple_date(attrib["startDate"])
                            date_str = start_dt.strftime("%Y-%m-%d")
                            val = float(attrib.get("value", 0))

                            if date_str not in daily_activity:
                                daily_activity[date_str] = {
                                    "active_calories": 0.0,
                                    "basal_calories": 0.0,
                                    "steps": 0,
                                    "exercise_min": 0.0,
                                    "vo2_max": None
                                }
                            
                            if rec_type == "HKQuantityTypeIdentifierActiveEnergyBurned":
                                daily_activity[date_str]["active_calories"] += val
                            elif rec_type == "HKQuantityTypeIdentifierBasalEnergyBurned":
                                daily_activity[date_str]["basal_calories"] += val
                            elif rec_type == "HKQuantityTypeIdentifierStepCount":
                                daily_activity[date_str]["steps"] += int(val)
                            elif rec_type == "HKQuantityTypeIdentifierAppleExerciseTime":
                                daily_activity[date_str]["exercise_min"] += val
                            elif rec_type == "HKQuantityTypeIdentifierVO2Max":
                                daily_activity[date_str]["vo2_max"] = val
                        except Exception:
                            pass

                    # 5. Nutrition (Apple Health sync from MyFitnessPal)
                    elif rec_type.startswith("HKQuantityTypeIdentifierDietary"):
                        try:
                            start_dt = parse_apple_date(attrib["startDate"])
                            date_str = start_dt.strftime("%Y-%m-%d")
                            val = float(attrib.get("value", 0))

                            if date_str not in daily_nutrition:
                                daily_nutrition[date_str] = {
                                    "calories": 0.0,
                                    "protein_g": 0.0,
                                    "carbs_g": 0.0,
                                    "fat_g": 0.0,
                                    "fiber_g": 0.0,
                                    "sugar_g": 0.0,
                                    "sodium_mg": 0.0,
                                    "water_ml": 0.0,
                                }
                            
                            if rec_type == "HKQuantityTypeIdentifierDietaryEnergyConsumed":
                                daily_nutrition[date_str]["calories"] += val
                            elif rec_type == "HKQuantityTypeIdentifierDietaryProtein":
                                daily_nutrition[date_str]["protein_g"] += val
                            elif rec_type == "HKQuantityTypeIdentifierDietaryCarbohydrates":
                                daily_nutrition[date_str]["carbs_g"] += val
                            elif rec_type == "HKQuantityTypeIdentifierDietaryFatTotal":
                                daily_nutrition[date_str]["fat_g"] += val
                            elif rec_type == "HKQuantityTypeIdentifierDietaryFiber":
                                daily_nutrition[date_str]["fiber_g"] += val
                            elif rec_type == "HKQuantityTypeIdentifierDietarySugar":
                                daily_nutrition[date_str]["sugar_g"] += val
                            elif rec_type == "HKQuantityTypeIdentifierDietarySodium":
                                daily_nutrition[date_str]["sodium_mg"] += val
                            elif rec_type == "HKQuantityTypeIdentifierDietaryWater":
                                daily_nutrition[date_str]["water_ml"] += val
                        except Exception:
                            pass

                elif tag == "Workout":
                    # Workouts
                    try:
                        start_dt = parse_apple_date(attrib["startDate"])
                        end_dt = parse_apple_date(attrib["endDate"])
                        duration = float(attrib.get("duration", 0))
                        # Some versions duration is in minutes, some in seconds. If duration > 3600 and difference is smaller:
                        if duration > (end_dt - start_dt).total_seconds() * 1.5 or duration > 1000:
                            duration = (end_dt - start_dt).total_seconds() / 60.0
                        
                        raw_act = attrib.get("workoutActivityType", "Other")
                        act_type = clean_workout_type(raw_act)
                        cals = float(attrib.get("totalEnergyBurned", 0.0))
                        dist = float(attrib.get("totalDistance", 0.0))

                        pending_records.append(WorkoutRecord(
                            date=start_dt.strftime("%Y-%m-%d"),
                            start_time=start_dt,
                            end_time=end_dt,
                            activity_type=act_type,
                            duration_minutes=round(duration, 1),
                            calories_burned=round(cals, 1),
                            distance_km=round(dist, 2),
                            source="AppleHealth"
                        ))
                        counts["workouts"] += 1
                    except Exception:
                        pass

                # Batch flush to avoid memory pressure
                if len(pending_records) >= batch_size:
                    session.bulk_save_objects(pending_records)
                    session.commit()
                    pending_records = []

                # Clear element from memory
                elem.clear()
                while elem.getprevious() is not None:
                    del elem.getparent()[0]

            # Save remaining pending
            if pending_records:
                session.bulk_save_objects(pending_records)
                session.commit()

            # Insert aggregated daily activity
            for date_str, act in daily_activity.items():
                existing = session.query(ActivityRecord).filter_by(date=date_str).first()
                if existing:
                    existing.active_calories = round(act["active_calories"], 1)
                    existing.basal_calories = round(act["basal_calories"], 1)
                    existing.step_count = act["steps"]
                    existing.exercise_minutes = round(act["exercise_min"], 1)
                    if act["vo2_max"] is not None:
                        existing.vo2_max = round(act["vo2_max"], 1)
                else:
                    session.add(ActivityRecord(
                        date=date_str,
                        active_calories=round(act["active_calories"], 1),
                        basal_calories=round(act["basal_calories"], 1),
                        step_count=act["steps"],
                        exercise_minutes=round(act["exercise_min"], 1),
                        vo2_max=round(act["vo2_max"], 1) if act["vo2_max"] else None
                    ))
                counts["activity_days"] += 1

            # Insert aggregated daily nutrition
            for date_str, nut in daily_nutrition.items():
                existing = session.query(NutritionRecord).filter_by(date=date_str, meal_type="DailySummary").first()
                if existing:
                    existing.calories = round(nut["calories"], 1)
                    existing.protein_g = round(nut["protein_g"], 1)
                    existing.carbs_g = round(nut["carbs_g"], 1)
                    existing.fat_g = round(nut["fat_g"], 1)
                    existing.fiber_g = round(nut["fiber_g"], 1)
                    existing.sugar_g = round(nut["sugar_g"], 1)
                    existing.sodium_mg = round(nut["sodium_mg"], 1)
                    existing.water_ml = round(nut["water_ml"], 1)
                else:
                    session.add(NutritionRecord(
                        date=date_str,
                        meal_type="DailySummary",
                        calories=round(nut["calories"], 1),
                        protein_g=round(nut["protein_g"], 1),
                        carbs_g=round(nut["carbs_g"], 1),
                        fat_g=round(nut["fat_g"], 1),
                        fiber_g=round(nut["fiber_g"], 1),
                        sugar_g=round(nut["sugar_g"], 1),
                        sodium_mg=round(nut["sodium_mg"], 1),
                        water_ml=round(nut["water_ml"], 1),
                        source="AppleHealth"
                    ))
                counts["nutrition"] += 1

            session.commit()

        finally:
            file_obj.close()
            session.close()

        return counts
