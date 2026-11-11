"""Paths, column groups and shared settings."""
from pathlib import Path

# --- Paths ---
PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw"
OUTPUT_DIR = PROJECT_ROOT / "outputs"
PREDICTIONS_DIR = OUTPUT_DIR / "predictions"
METRICS_DIR = OUTPUT_DIR / "metrics"
EXPERIMENTS_DIR = OUTPUT_DIR / "experiments"

TRAIN_PATH = RAW_DATA_DIR / "Case_3_Train_Participants.xlsx"
TRAIN_SHEET = "Train Data"
TEST_INPUTS_PATH = RAW_DATA_DIR / "case_3_test_inputs.csv"
SUBMISSION_TEMPLATE_PATH = RAW_DATA_DIR / "case_3_predictions_template.csv"
SUBMISSION_PATH = PREDICTIONS_DIR / "case_3_predictions.csv"

# --- Columns ---
ID_COLUMN = "Record_ID"
DATE_COLUMN = "Maintenance_Date"
TARGET_COLUMN = "Defect_Found"   # raw "Yes"/"No" label
LABEL_COLUMN = "is_defect"       # cleaned 0/1 label

CATEGORICAL_COLUMNS = ["Maintenance_Station", "Tool_ID", "Belt_Supplier", "Belt_Batch_ID", "Technician_ID"]
NUMERIC_COLUMNS = [
    "High_Load_Hours_Last_30_Days", "Hot_Operation_Days_Last_30_Days", "Peak_Operating_Temperature_C",
    "Days_Since_Tool_Calibration", "Tool_Uses_Since_Calibration", "Belt_Age_Hours",
    "Cycles_Since_Belt_Install", "Belt_Target_Tension_N", "Belt_Measured_Tension_N",
    "Ambient_Temperature_C", "Relative_Humidity_Pct", "Engine_Load_Ratio", "Alignment_Offset_mm",
    "Contamination_Index", "Operating_Hours_Last_30_Days", "Belt_Temperature_C",
    "Belt_Vibration_mm_s", "Belt_Slip_Pct",
]
# Columns that get an explicit "was missing" flag
MISSING_FLAG_COLUMNS = [
    "Belt_Measured_Tension_N", "Belt_Temperature_C", "Belt_Vibration_mm_s",
    "Days_Since_Tool_Calibration", "Tool_Uses_Since_Calibration", "Belt_Age_Hours", "Belt_Slip_Pct",
]
# Both lowered validation F1, so the models never see them
EXCLUDED_FEATURES = ["Technician_ID", "Month"]

# --- Validation ---
N_FOLDS = 5
FINAL_MODEL_SEEDS = (0, 1, 2)       # CV repeats and seed averaging for the final model
EXPERIMENT_SEEDS = (0, 1)           # CV repeats for model comparisons
TEMPORAL_TRAIN_FRACTION = 0.8       # time check: train on first 80% by date, score on last 20%
F1_TOLERANCE = 0.01                 # pick lowest threshold within this F1 of the best
