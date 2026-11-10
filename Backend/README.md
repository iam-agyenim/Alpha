# Case 3 (release v2): belt-defect prediction

Trains on the 10,000 labelled screening episodes and writes `output/case_3_predictions.csv` for the 2,000 test
episodes, in the exact format the organisers require. Ranking metric: F1 on `Defect_Found = Yes`.

## Run it

Python 3.12.

```bash
cd Backend
python3.12 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m case3.train \
  --train    <path>/Case_3_Train_Participants.xlsx \
  --test     <path>/case_3_test_inputs.csv \
  --template <path>/submission_guidelines/case_3_predictions_template.csv \
  --out output
.venv/bin/python -m case3.submission output/case_3_predictions.csv <path>/case_3_test_inputs.csv
.venv/bin/pytest -q tests
```

A full run takes about 6 minutes on a laptop. Competition data is not committed (`data/` is ignored); pass the paths.

## Outputs (`output/`)

| File | What it is |
|---|---|
| `case_3_predictions.csv` | **The submission.** 2,000 rows + header, `Record_ID,Defect_Found`, Yes/No, template order |
| `test_scores.csv` | Same IDs with the model's defect probability (for the dashboard; never submit this) |
| `report.json` | Threshold, validation scores, test prediction summary, format-check result |
| `threshold_curve.csv` | F1 at every threshold for each validation view |
| `feature_importance.csv` | CatBoost importance, averaged over seeds |

## Method

1. **Cleaning** (`case3/features.py`). The raw files mix case and stray spaces (`Tool-05`, `tool-05 `,
   `" STATION A"`); all are mapped to one spelling. About 3% of values are missing in 13 columns; they stay
   missing and the tree models handle them natively (no invented values). No values fall outside the data
   dictionary ranges and there are no duplicate rows or IDs.
2. **Features.** All 23 raw inputs plus row-level features: tension difference from target (N, %, absolute %),
   belt temperature above ambient, high-load share, tool uses per day since calibration, hours per cycle,
   vibration × temperature, slip × absolute tension difference, count of missing values. Identifiers and the
   absolute date are not inputs: the brief says repeated tags do not form a shared history, and the date would
   only teach the training calendar. Every feature uses only its own row (tested).
3. **Model.** CatBoost (5 seeds) blended 70/30 with LightGBM (5 seeds). CatBoost alone was the best single
   model; the blend was more stable on unseen periods.
4. **Threshold.** Defects are 2.7% of training rows, so the Yes/No cut-off matters as much as the model. The
   threshold maximises the average F1 over three views: repeated 5-fold cross-validation, an unseen summer
   (train without May-Aug 2024, predict it), and an unseen later period (train on 2024, predict Jan-May 2025).
   The test set is a later summer (May-Aug 2025), so a threshold tuned only on shuffled folds is too strict.

## Results

Every score comes from a model that never saw the rows it is scored on.

| Validation view | Rows | Defects | F1 | Precision | Recall | Best F1 at any threshold |
|---|---|---|---|---|---|---|
| Repeated 5-fold CV (all rows) | 10,000 | 269 | **0.728** | 0.67 | 0.80 | 0.732 |
| Unseen summer (May-Aug 2024) | 2,460 | 79 | **0.690** | 0.64 | 0.75 | 0.690 |
| Unseen later period (Jan-May 2025) | 2,680 | 67 | **0.699** | 0.66 | 0.75 | 0.707 |

Threshold **0.16**. Expect a test score around **F1 0.69-0.73** (×100 = 69-73 points); with ~100 defects in the
test set, chance alone moves F1 by a few points either way.

Model comparison (repeated 5-fold CV, best threshold): logistic regression 0.66, XGBoost 0.64, LightGBM 0.69,
CatBoost 0.73-0.74. Tuning depth, learning rate and regularisation, and adding hinge features at the visible
thresholds, all landed within ±0.01 of CatBoost's default, which is inside the noise for 269 defects.

**Why the "best-threshold" approach was not used:** on the two unseen periods, a threshold picked only from
cross-validation gave F1 0.52-0.66, because it moved between 0.12 and 0.35 depending on the split. The
multi-view threshold scored within 0.01 of the best possible on both.

## Test predictions

129 of 2,000 test episodes predicted Yes (6.5%), against 2.7% defects in training. That is expected: the test
period is summer (ambient 37 °C vs 31 °C, more hot-operation days), and the higher-risk belt batches B-04,
B-07 and B-09 make up 37% of test rows against 23% in training.

Predicted-Yes episodes have the same profile as real defects in training: median belt temperature 84.5 °C vs
76 °C, vibration 4.2 vs 3.2 mm/s, tension 7.2% off target vs 2.5%, belt age 4,480 h vs 2,490 h, 83 days since
tool calibration vs 55.

**Finding for the presentation: Tool-03 is drifting out of calibration in the test period.** In training it was
always recent (median 46 days since calibration, never above 120). In the test period its median is 135 days,
61% of its jobs are past 120 days, and it rises every month (84 → 108 → 132 → 163 days, May to August). The
model gives Yes to 19% of Tool-03 jobs, against 2-7% for other tools, and it does so from the calibration
readings, not the tool name. Recommendation: recalibrate Tool-03 now.

## What drives defects (training data, association, not proof of cause)

| Factor | Defect rate |
|---|---|
| Days since tool calibration | ~1.5% up to 90 days → 13% at 120-180 → 35% above 180 |
| Tool uses since calibration | ~1.5% up to 600 → 20% at 800-1,200 → 38% above 1,200 |
| Belt age | ~1% below 3,000 h → 7% at 4,000-5,000 h → 11% above 5,000 h |
| Tension vs target | 0.6% within ±5% → 8% at +5-10% → 52% at +10-20%; 35% below -10% |
| Belt temperature | 0% below 60 °C → 15% at 85-90 °C → 41% at 90-100 °C |
| Vibration | 0.1% below 2 mm/s → 25% at 5-6 mm/s → 60% above 6 mm/s |
| Season | Defects concentrate in hot months (5-9% per month) and nearly vanish in winter (0.2-0.5%) |
| Belt batch | B-07 6.2%, B-09 6.1%, B-04 4.6%, against 0.8-3.2% for others |
| Tool | Tool-05 6.7% against 1.2-3.1% (Tool-05 is also the most overdue tool in training) |

These are associations in synthetic screening data. Temperature, vibration and slip are measured at screening,
before the confirmatory inspection, so they are legitimate inputs here (the data dictionary sets
`Maintenance_Date` as the cutoff), unlike the original 30-row sample.
