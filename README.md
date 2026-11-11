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

## AI assistant (multi-agent layer)

`belt_defect/agents/` adds a team of OpenAI agents on top of the trained model. Click **✨ AI** (top right) to open the
assistant panel: **▶ Run briefing** runs four specialists (risk, measurements, tools & calibration, trends) in
parallel with read-only tools over the model's predictions; a lead planner merges their findings into one
prioritised action plan, shown in the chat. Ask follow-up questions in the same chat; a router picks the specialist.
Each report has a **📤 Share** menu: email (opens your mail app), PDF or text download.

| File | Role |
|---|---|
| `agents/tools.py` | 10 read-only tools (model output + statistics), sanitised JSON |
| `agents/agent.py` | Capped tool-calling loop (OpenAI Responses API), number grounding check |
| `agents/team.py` | Specialists, peer cross-checks, lead planner, chat router, audit log |
| `agents/guard.py` | Prompt-injection screening, output allowlist, grounding |
| `agents/cost.py`, `agents/settings.py` | Token/cost meter, prices, models, spend limits |
| `dashboard/ai_panel.py` | Slide-out AI chat panel (briefing, questions, Share menus) |
| `dashboard/report_share.py` | PDF, text and email-link builders for the Share menu |

The dashboard pages (Fleet alert, Trends, Factors, Tools & calibration, Inspection list, Model) are in the left sidebar.

**API key:** put `OPENAI_API_KEY=...` in `.env` (git-ignored) locally, or in Streamlit Cloud **Settings → Secrets**.
Measured cost: about $0.03–0.05 per briefing, about $0.001 per question. Tests: `.venv/bin/python -m pytest tests`.
See `PRESENTATION_GUIDE.md` sections 12–15 and `BUSINESS_CASE.md`.
