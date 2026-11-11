"""Load and clean the raw train / test files."""
import re

import pandas as pd

from .config import CATEGORICAL_COLUMNS, DATE_COLUMN, LABEL_COLUMN, NUMERIC_COLUMNS, TARGET_COLUMN, TRAIN_SHEET

# Canonical label patterns: "Station A", "Tool-05", "Supplier B", "A-01", "TECH-21"
_STATION = re.compile(r"(?i)station\s*([a-z])$")
_TOOL = re.compile(r"(?i)tool[-\s]*0*(\d+)$")
_SUPPLIER = re.compile(r"(?i)supplier\s*([a-z])$")
_BATCH = re.compile(r"(?i)([ab])-?0*(\d+)$")
_TECHNICIAN = re.compile(r"(?i)tech[-\s]*0*(\d+)$")


def _canonical_label(value: str) -> str:
    """Map one messy category label to its canonical spelling."""
    if value.lower() in ("nan", "none", ""):
        return "Missing"
    if m := _STATION.match(value):
        return f"Station {m.group(1).upper()}"
    if m := _TOOL.match(value):
        return f"Tool-{int(m.group(1)):02d}"
    if m := _SUPPLIER.match(value):
        return f"Supplier {m.group(1).upper()}"
    if m := _BATCH.match(value):
        return f"{m.group(1).upper()}-{int(m.group(2)):02d}"
    if m := _TECHNICIAN.match(value):
        return f"TECH-{int(m.group(1)):02d}"
    return value


def normalize_category_labels(series: pd.Series) -> pd.Series:
    """Trim, collapse whitespace and standardize category spellings."""
    collapsed = series.astype(str).str.strip().str.replace(r"\s+", " ", regex=True)
    return collapsed.map(_canonical_label)


def clean_raw_data(raw: pd.DataFrame) -> pd.DataFrame:
    """Fix category spellings, coerce numeric/date types and add the 0/1 label (train only)."""
    df = raw.copy()
    for col in CATEGORICAL_COLUMNS:
        if col in df:
            df[col] = normalize_category_labels(df[col])
    for col in NUMERIC_COLUMNS:
        df[col] = pd.to_numeric(df[col], errors="coerce")  # bad entries -> NaN
    df[DATE_COLUMN] = pd.to_datetime(df[DATE_COLUMN], errors="coerce")
    if TARGET_COLUMN in df:
        df[LABEL_COLUMN] = (df[TARGET_COLUMN].astype(str).str.strip().str.lower() == "yes").astype(int)
    return df


def load_test_inputs(path) -> pd.DataFrame:
    """Read raw (uncleaned) test inputs from CSV or Excel."""
    return pd.read_csv(path) if str(path).endswith(".csv") else pd.read_excel(path)


def load_training_data(path, sort_by_date: bool = False) -> pd.DataFrame:
    """Load and clean training data; sort by date for temporal validation."""
    df = clean_raw_data(pd.read_excel(path, TRAIN_SHEET))
    if sort_by_date:
        df = df.sort_values(DATE_COLUMN).reset_index(drop=True)
    return df
