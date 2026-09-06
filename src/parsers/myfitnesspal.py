"""
MyFitnessPal CSV Parser.
Supports nutrition and exercise CSV exports directly from MyFitnessPal.
Handles both meal-by-meal and daily aggregate export formats.
"""

from datetime import datetime
from pathlib import Path
from typing import Dict, Optional
import pandas as pd

from src.database import NutritionRecord, get_session


class MyFitnessPalParser:
    def __init__(self, file_path: str):
        self.file_path = Path(file_path)
        if not self.file_path.exists():
            raise FileNotFoundError(f"File not found: {self.file_path}")

    def parse_and_store(self, db_path: Optional[str] = None) -> int:
        """
        Parses MFP CSV and inserts records into SQLite.
        Returns total number of nutrition records saved.
        """
        df = pd.read_csv(self.file_path)
        
        # Standardize column headers
        col_map = {}
        for c in df.columns:
            low = c.strip().lower()
            if "date" in low:
                col_map[c] = "date"
            elif "meal" in low:
                col_map[c] = "meal"
            elif "calorie" in low or "energy" in low:
                col_map[c] = "calories"
            elif "protein" in low:
                col_map[c] = "protein"
            elif "carb" in low:
                col_map[c] = "carbs"
            elif "fat" in low and "sat" not in low:
                col_map[c] = "fat"
            elif "fiber" in low or "fibre" in low:
                col_map[c] = "fiber"
            elif "sugar" in low:
                col_map[c] = "sugar"
            elif "sodium" in low:
                col_map[c] = "sodium"
            elif "water" in low:
                col_map[c] = "water"

        df = df.rename(columns=col_map)
        if "date" not in df.columns:
            raise ValueError("Invalid MFP export: No 'date' column found.")

        session = get_session(db_path)()
        count = 0
        try:
            for _, row in df.iterrows():
                try:
                    # Parse date string (e.g. 2024-01-15 or 1/15/2024)
                    raw_d = str(row["date"]).strip()
                    try:
                        d_obj = pd.to_datetime(raw_d).date()
                        date_str = d_obj.strftime("%Y-%m-%d")
                    except Exception:
                        continue

                    meal_type = str(row.get("meal", "DailySummary")).strip()
                    cals = float(row.get("calories", 0) or 0)
                    prot = float(row.get("protein", 0) or 0)
                    carbs = float(row.get("carbs", 0) or 0)
                    fat = float(row.get("fat", 0) or 0)
                    fiber = float(row.get("fiber", 0) or 0)
                    sugar = float(row.get("sugar", 0) or 0)
                    sodium = float(row.get("sodium", 0) or 0)
                    water = float(row.get("water", 0) or 0)

                    # Update or insert
                    existing = session.query(NutritionRecord).filter_by(
                        date=date_str, meal_type=meal_type
                    ).first()

                    if existing:
                        existing.calories = cals
                        existing.protein_g = prot
                        existing.carbs_g = carbs
                        existing.fat_g = fat
                        existing.fiber_g = fiber
                        existing.sugar_g = sugar
                        existing.sodium_mg = sodium
                        existing.water_ml = water
                        existing.source = "MyFitnessPal"
                    else:
                        rec = NutritionRecord(
                            date=date_str,
                            meal_type=meal_type,
                            calories=cals,
                            protein_g=prot,
                            carbs_g=carbs,
                            fat_g=fat,
                            fiber_g=fiber,
                            sugar_g=sugar,
                            sodium_mg=sodium,
                            water_ml=water,
                            source="MyFitnessPal"
                        )
                        session.add(rec)
                    count += 1
                except Exception:
                    continue

            session.commit()
        finally:
            session.close()

        return count
