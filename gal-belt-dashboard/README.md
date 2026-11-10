# B787 Engine Belt Defect Investigation

**MoIAT x GAL "AI for Smart Maintenance" hackathon, Case 3: Why are B787 engine belt defects increasing?**

A Streamlit dashboard that finds what is driving belt defects, checks whether the link is causal, flags the aircraft that need inspection, and scores the risk of a defect *before* a job starts.

> Prototype only. Not for operational aircraft use.

## Quick start

Python 3.10 or newer is required.

```bash
cd gal-belt-dashboard
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py               # opens http://localhost:8501
pytest -q                          # 32 tests: stats, model, and full-app smoke tests
```

Upload a different CSV or XLSX file from the sidebar. Column names and labels are normalised: `Y`/`True`/`1` all count as a defect, `Due`/`Overdue` count as *Needs Calibration*, and `2026-01-05`, `January` and `1` all become *Jan*. If a required column is missing, the app lists the missing columns instead of crashing.

## Findings on the GAL sample (30 jobs, Jan to Mar)

| Question | Answer | Evidence |
|---|---|---|
| Unusual trends? | Defects rose from 3 to 4 per month, **but only because Tool-05 was used more** (3, 4, 4 jobs). | Cochran-Armitage trend p = 0.64; p-chart: no month outside the limits |
| Which factor? | **Tool-05, the only tool marked *Needs Calibration***. 11 of 11 jobs with it had a defect, vs 0 of 19 with other tools. | Fisher p = 1.8 × 10⁻⁸ (BH q = 3.7 × 10⁻⁸) |
| Is the station to blame? | No. Station C looks worse at first (5 of 9 jobs) only because Tool-05 was used there more. Within each tool group, every station has the same defect rate. | Crude station χ² p = 0.37, V = 0.26 → no effect after stratification; CMH p = 2.4 × 10⁻⁷ for the tool |
| Is it causal? | Strong signal, but not proven. Strength, consistency, plausibility and specificity are met. Dose-response and experiment cannot be tested yet. | Bradford Hill checklist |
| Which aircraft need inspection? | 11 aircraft (all Tool-05 jobs). The list can be downloaded from the *Action plan* tab. | |
| What should change? | Quarantine and recalibrate Tool-05, test it against a reference tool, and add a **calibration gate** to the work-order system. | Gate would have avoided 11 of 11 defects (100%) |

**Root cause:** a maintenance process gap. Nothing stops a tool that is overdue for calibration from being used.

**Important caveat:** in this data, Tool-05 and *Needs Calibration* always occur together. The data cannot tell whether the problem is this specific tool or the missed calibration. Recalibrating the tool and testing it against a reference tool would settle the question.

## Dashboard tabs

1. **Overview:** KPIs, defect rate by tool, Pareto chart, and the full records table with filters and highlighting.
2. **Why:** factor ranking (rate, relative risk, Fisher p, BH q, Cramér's V), Bayesian rates with 90% intervals, and tool × station heatmaps.
3. **When:** monthly jobs vs defects, p-chart, Cochran-Armitage trend test, and a note on survival analysis.
4. **Causation:** stratification (station within tool and within tool status), CMH test, Bradford Hill checklist, causal chain, and confounding note.
5. **Prediction:** pre-job risk checker, decision-tree rule, logistic and Firth models, leave-one-out validation, and the leakage demo.
6. **Root cause:** 6M fishbone and 5 Whys, with each status computed from the results.
7. **Action plan:** inspection list (CSV download), actions with owners, calibration-gate impact, and the cost model.
8. **Data & methods:** data-quality log, methods, limitations, and the extra data that would unlock more analysis.

The sidebar has the file upload, a **Presentation mode** toggle (hides tables, enlarges charts), the risk thresholds, and the cost assumptions.

## Methods

Nothing is hardcoded. The top suspect factor is the pre-job factor level with the lowest Benjamini-Hochberg q-value (ties go to the higher relative risk). All titles, the alert, the fishbone and the action list are generated from it. `tests/test_app.py` runs the full app on a file where Tool-02 is the faulty tool and checks that the app names Tool-02.

| Area | Method | Code |
|---|---|---|
| Association | Defect rates per level; Fisher's exact test per level vs rest; BH correction; χ² + Cramér's V, switching to an exact test (Fisher, or a Fisher-Freeman-Halton permutation test) when expected counts are below 5 | `src/stats.py` |
| Uncertainty | Beta(1,1) posterior per group, 90% credible interval, P(group > rest) by Monte Carlo with a fixed seed | `bayes_rates` |
| Time | p-chart (p̄ ± 3·√(p̄(1−p̄)/n)); two-sided Cochran-Armitage trend test | `p_chart`, `cochran_armitage` |
| Causation | Stratified rates and within-stratum tests; Cochran-Mantel-Haenszel; Bradford Hill checklist marked from the computed results | `stratify`, `mantel_haenszel`, `bradford_hill` |
| Prediction | **Pre-job features only** (tool, tool status, station, month), one-hot encoded. Depth-2 decision tree for a readable rule; L2 logistic regression (`class_weight="balanced"`) for probabilities; Firth penalised logistic regression (written in numpy) as a cross-check | `src/model.py` |
| Validation | Leave-one-out cross-validation, plus stratified k-fold when there are at least 5 of each class; ROC-AUC, recall, precision, confusion matrix; automatic warnings for small samples and perfect separation | `validate` |
| Leakage demo | The same model trained on belt condition, temperature and vibration. It also scores perfectly, but it predicts the answer from the answer. | `leakage_demo` |
| Impact | Calibration gate (block any tool not in *Normal* status) applied to past jobs; cost model with editable placeholder assumptions | `src/impact.py` |

**Why not use the symptoms to predict?** Belt condition, temperature and vibration are recorded at the same inspection that finds the defect, so they are part of the outcome. A model that uses them gives no warning before the job.

**Why penalised regression?** Tool status perfectly separates defects from non-defects in this data. Ordinary logistic regression then pushes its coefficients toward infinity and never converges. The L2 penalty, or Firth's correction, keeps the estimates finite.

## Limitations

- **30 records, 11 defects, 3 months.** A few new records could change any result, and the perfect validation scores reflect a clean sample, not a perfect model.
- **Categorical data only.** There are no tension measurements and no days overdue for calibration, so dose-response cannot be tested.
- **Confounding.** Tool-05 and *Needs Calibration* cannot be separated in this data.
- **No causal proof without an intervention.** The recalibration test is the next step.
- **One record per aircraft and no dates.** Survival analysis (time to failure) and repeat-defect analysis are not possible.
- **Cost figures are placeholders.** Replace them with GAL's figures in the sidebar.

## Data that would unlock more

- Job dates and flight hours or cycles → time-to-failure curves (Kaplan-Meier / Weibull) and seasonality
- Measured belt tension before and after each job → direct test of the mechanism
- Tool calibration dates → days overdue as a continuous risk factor
- Technician ID, engine ID, belt part and batch number → tests for the remaining fishbone branches

## Project layout

```
app.py            Streamlit UI only
src/data.py       load, validate, normalise
src/stats.py      statistical tests
src/model.py      prediction models, validation, risk checker
src/rca.py        fishbone, 5 Whys, causal chain
src/impact.py     calibration gate, cost model, inspection list
src/charts.py     Plotly figure builders
tests/            pytest: stats, model, app smoke tests (AppTest)
DEMO.md           5-minute demo script
```
