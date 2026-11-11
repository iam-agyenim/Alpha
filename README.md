# GAL Case 3: belt defect model

Predicts `Defect_Found` (Yes/No) for each belt maintenance record.

**Final model:** average of LightGBM + CatBoost + logistic regression probabilities.
**Features:** all numeric inputs + tension error (N, %, absolute), calibration load, hours per cycle,
belt temperature over ambient, high-load share, missing-value flags, station / tool / supplier / batch.
**Excluded:** `Technician_ID` and month (both lowered validation F1).
**Threshold:** lowest threshold whose out-of-fold F1 is within 0.01 of the best (leans to recall; the defect rate trends upward).

## Project layout

```
case3_model/
├── belt_defect/                 # reusable package
│   ├── config.py                # paths, column groups, seeds, validation settings
│   ├── preprocessing.py         # load data, fix category spellings, coerce types
│   ├── feature_engineering.py   # engineered features, feature selection, category alignment
│   ├── models.py                # model builders + final 3-model blend
│   ├── evaluation.py            # CV, temporal holdout, F1 threshold selection, scoring
│   └── fleet_analysis.py        # dashboard numbers: trends, abnormal measurements, tools, aircraft status
├── dashboard/app.py             # Streamlit fleet dashboard
├── scripts/
│   ├── train_and_predict.py              # final model -> submission file
│   ├── compare_model_families.py         # LogReg / RF / ExtraTrees / HistGB / LightGBM / XGBoost / CatBoost
│   ├── tune_lightgbm_and_ensembles.py    # LightGBM variants + ensembles (chose the final blend)
│   └── check_test_distribution_shift.py  # sanity check of test inputs vs recent training data
├── data/raw/                    # Case_3_Train_Participants.xlsx, case_3_test_inputs.csv, template
├── outputs/
│   ├── predictions/             # case_3_predictions.csv (submission), test_probabilities.csv
│   ├── metrics/                 # oof_metrics.json, oof_probabilities.npy
│   └── experiments/             # model_comparison.csv, lightgbm_ensemble_experiments.csv
└── requirements.txt
```

## Setup

```bash
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt
brew install libomp            # macOS only, needed by lightgbm
```

## Run

```bash
.venv/bin/python scripts/train_and_predict.py               # uses data/raw -> outputs/predictions
.venv/bin/python scripts/check_test_distribution_shift.py   # optional sanity check
```

Custom paths: `scripts/train_and_predict.py <train.xlsx> <test_inputs.csv> <template.csv> <predictions.csv>`

## Dashboard

```bash
.venv/bin/streamlit run dashboard/app.py    # needs train_and_predict.py outputs; opens http://localhost:8501
```

| Tab | Shows |
|---|---|
| Fleet alert (main) | Alert banner (aircraft flagged + likely contributing tool) and aircraft table: Aircraft, Belt Status, Tension Difference, Tool, plus engine, date, risk and reasons |
| Trends | Monthly defect rate (actual vs predicted), temperature and overdue-tool share |
| Factors | Defect rate by tension error, abnormal measurements, tool, station, supplier |
| Tools & calibration | Tool calibration status now, defect rate by calibration load, one tool's drift over time |
| Inspection list | Every High Risk / Medium screening with filters and CSV download; aircraft drill-down |
| Model | Validation scores, threshold, limits, submission download |

Belt Status: **High Risk** = model predicts a defect; **Medium** = defect risk ≥ 20% or a measurement outside the
normal range (99% of defect-free training screenings); **Normal** otherwise.

## Validation

| Scheme | F1 | Precision | Recall |
|---|---|---|---|
| All 10,000 rows, 5-fold x 3 repeats | 0.751 | 0.745 | 0.758 |
| Time-based: train first 8,000, predict last 2,000 | 0.702 | 0.687 | 0.719 |

Test prediction: 106 of 2,000 rows flagged (5.3%, vs 2.7% in training). The test period (late May to Aug 2025)
covers the hot-season peak and a build-up of overdue tool calibrations, both strong defect drivers;
see `scripts/check_test_distribution_shift.py`.

## Agentic maintenance workflow

The app has two pages (left sidebar): a minimal **Dashboard** of the findings and a **Workflow** page where the ML
model and AI agents pass data and results to each other, shown as an animated diagram with a timestamped log:

```
Incoming data → Security agent → ML model → Orchestrator → Quality & Safety → Logistics → Commercial
             → Security check → Human approval → Outputs (work orders, PDF, email)
```

| File | Role |
|---|---|
| `agents/workflow.py` | The pipeline: intake, security rules, model scoring, routing, 3 agents, output check, approval, work orders, event log |
| `agents/tools.py` | Read-only tools and calculators (batch risk, aircraft, tools, locations, parts and staff, flights, costs) |
| `agents/agent.py` | Capped tool-calling loop (OpenAI Responses API), number grounding check, event callbacks |
| `agents/guard.py` | Prompt-injection screening, output allowlist, grounding |
| `agents/cost.py`, `agents/settings.py` | Token/cost meter, prices, models, spend limits |
| `dashboard/workflow_view.py` | Animated workflow visual (HTML/SVG/JS) replaying the real timestamped events |
| `dashboard/report_share.py` | PDF report, work-order CSV and email link |
| `outputs/workflow_runs/sample_run.json` | A recorded real run, replayed when no API key is set |

Theme: white, green (`#0B6B3A`) and black. Logistics and commercial facts the dataset doesn't hold (belt stock,
calibration slots, flights, unit costs) are labelled planning assumptions (`OPS_ASSUMPTIONS` in `agents/tools.py`).

**API key:** put `OPENAI_API_KEY=...` in `.env` (git-ignored) locally, or in Streamlit Cloud **Settings → Secrets**.
Measured cost: about $0.015–0.02 per workflow run. Tests: `.venv/bin/python -m pytest tests`.
See `PRESENTATION_GUIDE.md` and `BUSINESS_CASE.md`.
