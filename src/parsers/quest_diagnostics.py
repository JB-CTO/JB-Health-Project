"""
Quest Diagnostics Lab Report Parser (PDF & CSV).
Extracts biomarkers, values, reference ranges, and flags from Quest Diagnostics PDF reports.
Categorizes biomarkers (Lipids, Metabolic, Hormones, Inflammation, CBC, Vitamins).
"""

from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import re

import pdfplumber
from pypdf import PdfReader
import pandas as pd

from src.database import BiomarkerRecord, get_session

# Categorization mapping for standard lab tests
BIOMARKER_CATEGORIES = {
    # Lipids
    "CHOLESTEROL, TOTAL": "Lipids",
    "HDL CHOLESTEROL": "Lipids",
    "LDL CHOLESTEROL": "Lipids",
    "TRIGLYCERIDES": "Lipids",
    "VLDL CHOLESTEROL": "Lipids",
    "NON-HDL CHOLESTEROL": "Lipids",
    "CHOLESTEROL/HDL RATIO": "Lipids",
    "APOLIPOPROTEIN B": "Lipids",
    "LIPOPROTEIN (A)": "Lipids",
    # Metabolic & CMP
    "GLUCOSE": "Metabolic",
    "HEMOGLOBIN A1c": "Metabolic",
    "INSULIN": "Metabolic",
    "UREA NITROGEN (BUN)": "Metabolic",
    "CREATININE": "Metabolic",
    "eGFR": "Metabolic",
    "BUN/CREATININE RATIO": "Metabolic",
    "SODIUM": "Metabolic",
    "POTASSIUM": "Metabolic",
    "CHLORIDE": "Metabolic",
    "CARBON DIOXIDE": "Metabolic",
    "CALCIUM": "Metabolic",
    "PROTEIN, TOTAL": "Metabolic",
    "ALBUMIN": "Metabolic",
    "GLOBULIN": "Metabolic",
    "ALBUMIN/GLOBULIN RATIO": "Metabolic",
    "BILIRUBIN, TOTAL": "Metabolic",
    "ALKALINE PHOSPHATASE": "Metabolic",
    "AST": "Metabolic",
    "ALT": "Metabolic",
    # Hormones & Endocrine
    "TESTOSTERONE, TOTAL": "Hormones",
    "TESTOSTERONE, FREE": "Hormones",
    "ESTRADIOL": "Hormones",
    "DHEA-SULFATE": "Hormones",
    "CORTISOL": "Hormones",
    "TSH": "Hormones",
    "T4, FREE": "Hormones",
    "T3, FREE": "Hormones",
    "SHBG": "Hormones",
    "IGF-1": "Hormones",
    # Inflammation & Cardiovascular Recovery
    "C-REACTIVE PROTEIN, CARDIAC (hs-CRP)": "Inflammation",
    "hs-CRP": "Inflammation",
    "FERRITIN": "Inflammation",
    "HOMOCYSTEINE": "Inflammation",
    # Vitamins & Micronutrients
    "VITAMIN D, 25-HYDROXY": "Vitamins",
    "VITAMIN B12": "Vitamins",
    "FOLATE": "Vitamins",
    "MAGNESIUM": "Vitamins",
    "ZINC": "Vitamins",
    # CBC
    "WHITE BLOOD COUNT": "CBC",
    "RED BLOOD COUNT": "CBC",
    "HEMOGLOBIN": "CBC",
    "HEMATOCRIT": "CBC",
    "PLATELET COUNT": "CBC",
    "MCV": "CBC",
}


def classify_category(test_name: str) -> str:
    """Classifies a biomarker into a standard clinical panel."""
    upper = test_name.upper().strip()
    for known_test, cat in BIOMARKER_CATEGORIES.items():
        if known_test in upper or upper in known_test:
            return cat
    
    if any(term in upper for term in ["LIPID", "CHOL", "TRIG"]):
        return "Lipids"
    if any(term in upper for term in ["GLUCOSE", "A1C", "METABOLIC", "CREAT", "eGFR", "LIVER", "ALT", "AST"]):
        return "Metabolic"
    if any(term in upper for term in ["TESTOSTERONE", "ESTROGEN", "THYROID", "TSH", "CORTISOL", "DHEA"]):
        return "Hormones"
    if any(term in upper for term in ["CRP", "FERRITIN", "INFLAMM", "SED"]):
        return "Inflammation"
    if any(term in upper for term in ["VITAMIN", "MINERAL", "MAGNESIUM", "ZINC", "B12", "FOLATE"]):
        return "Vitamins"
    if any(term in upper for term in ["WBC", "RBC", "PLATELET", "HEMOGLOBIN", "HEMATOCRIT"]):
        return "CBC"
    return "Other Biomarkers"


def parse_reference_range(range_str: str) -> Tuple[Optional[float], Optional[float]]:
    """Extracts numeric low and high limits from strings like '65-99', '<200', '>=40'."""
    if not range_str:
        return None, None
    s = range_str.strip().replace(",", "")

    # Format: > 40 or >= 40
    if ">" in s or "≥" in s:
        m = re.search(r"[>≥]\s*=?\s*(\d*\.?\d+)", s)
        if m:
            try:
                return float(m.group(1)), None
            except ValueError:
                pass

    # Format: < 200 or <= 200
    if "<" in s or "≤" in s:
        m = re.search(r"[<≤]\s*=?\s*(\d*\.?\d+)", s)
        if m:
            try:
                return 0.0, float(m.group(1))
            except ValueError:
                pass

    # Format: low - high (e.g. 65-99, 0.60 - 1.35)
    dash_match = re.search(r"(\d*\.?\d+)\s*(?:-|–|—|\bto\b)\s*(\d*\.?\d+)", s)
    if dash_match:
        try:
            low = float(dash_match.group(1))
            high = float(dash_match.group(2))
            return low, high
        except ValueError:
            pass

    return None, None


class QuestDiagnosticsParser:
    def __init__(self, file_path: str):
        self.file_path = Path(file_path)
        if not self.file_path.exists():
            raise FileNotFoundError(f"File not found: {self.file_path}")

    def extract_collection_date(self, text: str) -> str:
        """Finds specimen collection date in Quest PDF header."""
        date_patterns = [
            r"Collected:\s*(\d{1,2}/\d{1,2}/\d{2,4})",
            r"Date Collected:\s*(\d{1,2}/\d{1,2}/\d{2,4})",
            r"Collection Date:\s*(\d{1,2}/\d{1,2}/\d{2,4})",
            r"Report Date:\s*(\d{1,2}/\d{1,2}/\d{2,4})",
            r"Date of Service:\s*(\d{1,2}/\d{1,2}/\d{2,4})",
            r"DOB:.*?(\d{1,2}/\d{1,2}/\d{4})",
        ]
        for pat in date_patterns:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                raw_d = m.group(1)
                try:
                    d = pd.to_datetime(raw_d).date()
                    return d.strftime("%Y-%m-%d")
                except Exception:
                    pass
        # Default to today if not found
        return datetime.today().strftime("%Y-%m-%d")

    def parse_pdf(self) -> List[Dict[str, Any]]:
        """Parses a Quest Diagnostics PDF report and extracts biomarker records."""
        extracted_records = []
        all_text = ""

        with pdfplumber.open(self.file_path) as pdf:
            for page in pdf.pages:
                txt = page.extract_text() or ""
                all_text += "\n" + txt

        collection_date = self.extract_collection_date(all_text)

        # Iterate page tables and lines
        with pdfplumber.open(self.file_path) as pdf:
            for page in pdf.pages:
                tables = page.extract_tables()
                for table in tables:
                    for row in table:
                        if not row or len(row) < 3:
                            continue
                        clean_row = [str(cell).strip() if cell else "" for cell in row]
                        # Look for test name, in-range or out-of-range value, reference range
                        row_text = " ".join(clean_row)
                        # Skip header lines
                        if any(h in row_text.lower() for h in ["test name", "in range", "out of range", "reference range"]):
                            continue
                        
                        # Check if first item is test name and has numbers
                        name_candidate = clean_row[0]
                        if len(name_candidate) < 2 or name_candidate.isdigit():
                            continue

                        # Find numeric value and flags
                        val_num = None
                        unit = ""
                        ref_str = ""
                        flag = "NORMAL"

                        for cell in clean_row[1:]:
                            if not cell:
                                continue
                            # Check for Flag
                            if cell.upper() in ("H", "HIGH"):
                                flag = "HIGH"
                            elif cell.upper() in ("L", "LOW"):
                                flag = "LOW"
                            elif cell.upper() in ("CRITICAL", "C"):
                                flag = "CRITICAL"
                            # Check for Reference range (e.g. 65-99, <200)
                            elif ("-" in cell or "<" in cell or ">" in cell) and any(c.isdigit() for c in cell):
                                ref_str = cell
                            # Check for Value (numeric)
                            elif val_num is None:
                                num_match = re.search(r"[-+]?\d*\.?\d+", cell)
                                if num_match:
                                    try:
                                        val_num = float(num_match.group(0))
                                    except ValueError:
                                        pass
                            # Units
                            elif any(u in cell.lower() for u in ["mg/dl", "u/l", "iu/l", "pg/ml", "ng/dl", "g/dl", "%", "mmol/l", "mcg/dl"]):
                                unit = cell

                        if val_num is not None and len(name_candidate) > 2:
                            ref_low, ref_high = parse_reference_range(ref_str)
                            # If flag wasn't explicitly marked, derive from ref range
                            if flag == "NORMAL":
                                if ref_low is not None and val_num < ref_low:
                                    flag = "LOW"
                                elif ref_high is not None and val_num > ref_high:
                                    flag = "HIGH"

                            extracted_records.append({
                                "date": collection_date,
                                "category": classify_category(name_candidate),
                                "test_name": name_candidate,
                                "value": val_num,
                                "unit": unit,
                                "ref_low": ref_low,
                                "ref_high": ref_high,
                                "flag": flag,
                                "source": "Quest Diagnostics"
                            })

        # Regex fallback for lines not captured in tables
        if not extracted_records:
            # Pattern: Test Name ... Value (Flag) ... Ref Range ... Units
            pattern = re.compile(
                r"^([A-Z0-9\s,\-\(\)\/\.]+?)\s+([<>]?\s*\d+\.?\d*)\s*(H|L|HIGH|LOW)?\s+([<>=]?\s*\d+[\.\d]*\s*[-–]\s*\d+[\.\d]*|[<>=]\s*\d+[\.\d]*)\s*([a-zA-Z\/%]+)?",
                re.MULTILINE
            )
            for match in pattern.finditer(all_text):
                test_name = match.group(1).strip()
                if len(test_name) < 3 or "TEST" in test_name or "PATIENT" in test_name:
                    continue
                raw_val = match.group(2).replace("<", "").replace(">", "").strip()
                try:
                    val_num = float(raw_val)
                except ValueError:
                    continue
                raw_flag = match.group(3) or ""
                flag = "HIGH" if "H" in raw_flag.upper() else ("LOW" if "L" in raw_flag.upper() else "NORMAL")
                ref_str = match.group(4)
                unit = match.group(5) or ""
                ref_low, ref_high = parse_reference_range(ref_str)

                extracted_records.append({
                    "date": collection_date,
                    "category": classify_category(test_name),
                    "test_name": test_name,
                    "value": val_num,
                    "unit": unit,
                    "ref_low": ref_low,
                    "ref_high": ref_high,
                    "flag": flag,
                    "source": "Quest Diagnostics"
                })

        return extracted_records

    def parse_csv(self) -> List[Dict[str, Any]]:
        """Parses a standardized CSV of lab results."""
        df = pd.read_csv(self.file_path)
        extracted = []
        for _, row in df.iterrows():
            test = str(row.get("test_name", row.get("Test", ""))).strip()
            if not test:
                continue
            date_str = str(row.get("date", row.get("Date", datetime.today().strftime("%Y-%m-%d")))).strip()
            val = float(row.get("value", row.get("Value", 0.0)))
            unit = str(row.get("unit", row.get("Unit", ""))).strip()
            ref_low = float(row["ref_low"]) if "ref_low" in row and pd.notna(row["ref_low"]) else None
            ref_high = float(row["ref_high"]) if "ref_high" in row and pd.notna(row["ref_high"]) else None
            flag = str(row.get("flag", row.get("Flag", "NORMAL"))).upper().strip()
            if flag not in ("NORMAL", "HIGH", "LOW", "CRITICAL"):
                if ref_low is not None and val < ref_low:
                    flag = "LOW"
                elif ref_high is not None and val > ref_high:
                    flag = "HIGH"
                else:
                    flag = "NORMAL"

            extracted.append({
                "date": date_str,
                "category": classify_category(test),
                "test_name": test,
                "value": val,
                "unit": unit,
                "ref_low": ref_low,
                "ref_high": ref_high,
                "flag": flag,
                "source": "Quest Diagnostics"
            })
        return extracted

    def parse_and_store(self, db_path: Optional[str] = None) -> int:
        """Parses file (PDF or CSV) and stores records into SQLite."""
        if self.file_path.suffix.lower() == ".pdf":
            records = self.parse_pdf()
        elif self.file_path.suffix.lower() == ".csv":
            records = self.parse_csv()
        else:
            raise ValueError(f"Unsupported file extension: {self.file_path.suffix}. Expected .pdf or .csv.")

        session = get_session(db_path)()
        saved_count = 0
        try:
            for r in records:
                # Deduplicate by date and test_name
                existing = session.query(BiomarkerRecord).filter_by(
                    date=r["date"], test_name=r["test_name"]
                ).first()
                if existing:
                    existing.value = r["value"]
                    existing.unit = r["unit"]
                    existing.ref_low = r["ref_low"]
                    existing.ref_high = r["ref_high"]
                    existing.flag = r["flag"]
                    existing.category = r["category"]
                else:
                    rec = BiomarkerRecord(**r)
                    session.add(rec)
                saved_count += 1
            session.commit()
        finally:
            session.close()

        return saved_count
