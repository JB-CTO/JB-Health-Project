"""
Database models and connection management for JB-Health-Project.
Stores health data from Apple Health, MyFitnessPal, and Quest Diagnostics.
"""

from datetime import datetime
from pathlib import Path
from typing import Optional
import os

from sqlalchemy import (
    create_engine, Column, Integer, Float, String, DateTime, Date, ForeignKey, Index, Text, UniqueConstraint
)
from sqlalchemy.orm import declarative_base, sessionmaker, scoped_session
import pandas as pd

Base = declarative_base()

class SleepRecord(Base):
    __tablename__ = "sleep_records"
    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(String(10), index=True, nullable=False) # YYYY-MM-DD (Night of sleep)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)
    stage = Column(String(30), nullable=False) # Deep, REM, Core, Awake, InBed, Unspecified
    duration_minutes = Column(Float, nullable=False)
    source = Column(String(50), default="AppleHealth")

    __table_args__ = (
        Index("idx_sleep_date_stage", "date", "stage"),
    )

class HeartRecord(Base):
    __tablename__ = "heart_records"
    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, nullable=False, index=True)
    date = Column(String(10), index=True, nullable=False) # YYYY-MM-DD
    metric = Column(String(30), nullable=False) # resting_hr, hrv_sdnn, walking_hr, heart_rate
    value = Column(Float, nullable=False)
    unit = Column(String(20), default="bpm")
    source = Column(String(50), default="AppleHealth")

    __table_args__ = (
        Index("idx_heart_date_metric", "date", "metric"),
    )

class ActivityRecord(Base):
    __tablename__ = "activity_records"
    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(String(10), unique=True, index=True, nullable=False) # YYYY-MM-DD
    active_calories = Column(Float, default=0.0)
    basal_calories = Column(Float, default=0.0)
    step_count = Column(Integer, default=0)
    exercise_minutes = Column(Float, default=0.0)
    vo2_max = Column(Float, nullable=True)

class WorkoutRecord(Base):
    __tablename__ = "workout_records"
    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(String(10), index=True, nullable=False) # YYYY-MM-DD
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)
    activity_type = Column(String(60), nullable=False) # Running, Strength, Cycling, etc.
    duration_minutes = Column(Float, nullable=False)
    calories_burned = Column(Float, default=0.0)
    distance_km = Column(Float, default=0.0)
    avg_heart_rate = Column(Float, nullable=True)
    max_heart_rate = Column(Float, nullable=True)
    source = Column(String(50), default="AppleHealth")

class NutritionRecord(Base):
    __tablename__ = "nutrition_records"
    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(String(10), index=True, nullable=False) # YYYY-MM-DD
    meal_type = Column(String(30), default="DailySummary") # Breakfast, Lunch, Dinner, Snacks, DailySummary
    calories = Column(Float, default=0.0)
    protein_g = Column(Float, default=0.0)
    carbs_g = Column(Float, default=0.0)
    fat_g = Column(Float, default=0.0)
    fiber_g = Column(Float, default=0.0)
    sugar_g = Column(Float, default=0.0)
    sodium_mg = Column(Float, default=0.0)
    water_ml = Column(Float, default=0.0)
    source = Column(String(50), default="AppleHealth")

class BiomarkerRecord(Base):
    __tablename__ = "biomarker_records"
    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(String(10), index=True, nullable=False) # YYYY-MM-DD
    category = Column(String(50), nullable=False) # Lipids, Metabolic, Hormones, Inflammation, CBC, Vitamins
    test_name = Column(String(100), nullable=False)
    value = Column(Float, nullable=False)
    unit = Column(String(30), default="")
    ref_low = Column(Float, nullable=True)
    ref_high = Column(Float, nullable=True)
    flag = Column(String(20), default="NORMAL") # NORMAL, HIGH, LOW, CRITICAL
    source = Column(String(50), default="Quest Diagnostics")

    __table_args__ = (
        Index("idx_biomarker_date_test", "date", "test_name"),
    )

class DailySummaryRecord(Base):
    __tablename__ = "daily_summary"
    date = Column(String(10), primary_key=True) # YYYY-MM-DD
    recovery_score = Column(Float, nullable=True) # 0-100
    sleep_score = Column(Float, nullable=True) # 0-100
    hrv_sdnn = Column(Float, nullable=True)
    hrv_7d_baseline = Column(Float, nullable=True)
    resting_hr = Column(Float, nullable=True)
    resting_hr_7d_baseline = Column(Float, nullable=True)
    total_sleep_hours = Column(Float, nullable=True)
    deep_sleep_hours = Column(Float, nullable=True)
    rem_sleep_hours = Column(Float, nullable=True)
    sleep_debt_hours = Column(Float, nullable=True)
    active_calories = Column(Float, nullable=True)
    steps = Column(Integer, nullable=True)
    exercise_minutes = Column(Float, nullable=True)
    workout_count = Column(Integer, default=0)
    training_load_atl = Column(Float, nullable=True)
    training_load_ctl = Column(Float, nullable=True)
    training_stress_balance = Column(Float, nullable=True)
    calories_consumed = Column(Float, nullable=True)
    protein_consumed = Column(Float, nullable=True)


def get_db_path(custom_path: Optional[str] = None) -> Path:
    """Returns absolute path to SQLite database."""
    if custom_path:
        p = Path(custom_path)
    else:
        root = Path(__file__).resolve().parent.parent
        p = root / "data" / "health.db"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def get_engine(db_path: Optional[str] = None):
    path = get_db_path(db_path)
    engine = create_engine(f"sqlite:///{path.as_posix()}", echo=False)
    return engine


def init_db(db_path: Optional[str] = None):
    """Initializes all tables in the database."""
    engine = get_engine(db_path)
    Base.metadata.create_all(engine)
    return engine


def get_session(db_path: Optional[str] = None):
    """Returns a new SQLAlchemy session."""
    engine = get_engine(db_path)
    session_factory = sessionmaker(bind=engine)
    return scoped_session(session_factory)


def reset_db(db_path: Optional[str] = None):
    """Clears and re-creates all tables."""
    engine = get_engine(db_path)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)


def load_table_df(table_name: str, db_path: Optional[str] = None) -> pd.DataFrame:
    """Loads a table into a pandas DataFrame."""
    engine = get_engine(db_path)
    query = f"SELECT * FROM {table_name}"
    try:
        return pd.read_sql_query(query, engine)
    except Exception:
        return pd.DataFrame()
