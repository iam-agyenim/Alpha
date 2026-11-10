# Presentation notes: GAL Case 3, B787 engine belt defects

Background, reasoning and narrative for the pitch. **None of this is shown in the dashboard**, which shows only results computed from the loaded data. The figures below come from the GAL sample (30 jobs, Jan to Mar). If GAL gives you a different file, check them against the dashboard first.

---

## 1. Root cause analysis

### 5 Whys
1. **Why are B787 engine belt defects being found?**
   → The belts show abnormal condition at inspection. 100% of defective belts ran hot and vibrated.
2. **Why are the belts running hot and vibrating?**
   → Most likely the belt tension was set incorrectly during maintenance. This is inferred, because tension is not recorded.
3. **Why was the tension set incorrectly?**
   → The jobs used Tool-05, which needed calibration. 11 of 11 of those jobs produced a defect.
4. **Why was that tool used?**
   → It was issued and used even though its status showed it needed calibration.
5. **Why was a tool overdue for calibration allowed on the job?**
   → A maintenance process gap. Station is ruled out by stratification. Crew was not tested, because there is no technician data.

### Fishbone (6M)

| Category | Status | Evidence |
|---|---|---|
| Machine / tool | **Confirmed** | 11 of 11 jobs with Tool-05 had a defect, vs 0 of 19 with other tools (Fisher p = 1.8 × 10⁻⁸) |
| Measurement / calibration | **Confirmed but confounded** | Every Tool-05 job also had a tool needing calibration, so the data cannot separate the two |
| Method / station | **Ruled out by stratification** | Within each tool, every station has the same defect rate (crude station p = 0.41 exact, 0.37 χ²) |
| Man / technician | Not in data | No technician ID, so training and shift effects cannot be tested |
| Material / belt batch | Not in data | No belt part or batch number |
| Environment | Not testable | No temperature, humidity or route data; month shows no trend (p = 0.64) |

### Causal chain
```
Tool-05 needs calibration ──► Belt tension set wrongly ──► High temperature + vibration ──► Belt defect
      [in data]                 [INFERRED, not in data]        [symptoms, in data]          [outcome, in data]
```
The middle link is the hypothesis. Measuring belt tension before and after each job would confirm or reject it.

### Confounding
Tool-05 and *Needs Calibration* occur in exactly the same 11 jobs. The data cannot tell whether the problem is this specific tool (a faulty unit) or the missed calibration (a process lapse). Both lead to the same first action: take the tool out of service and recalibrate it, then test it against a reference tool. If defects stop after recalibration, calibration was the cause.

---

## 2. Bradford Hill checklist

| Criterion | Status | Evidence |
|---|---|---|
| Strength | ✅ Met | Relative risk ∞ (no defects without Tool-05); BH q = 3.7 × 10⁻⁸ |
| Consistency | ✅ Met | Defect rate with Tool-05 is higher in 3 of 3 stations and 3 of 3 months |
| Temporality | 🟡 Partially | Tool status is known before the job and the defect is found after it, but there are no timestamps |
| Plausibility | ✅ Met | A tension tool out of calibration sets tension wrongly, which causes heat and vibration; 100% of defects show that pattern |
| Specificity | ✅ Met | All defects involve Tool-05, and there are no defects without it |
| Dose-response | ⚪ Not testable | Needs days overdue or measured tension error; the data only has a yes/no status |
| Experiment | ⚪ Not testable | No intervention yet. The recalibration test is the experiment |

---

## 3. Recommended actions

| # | Action | Why | Owner |
|---|---|---|---|
| 1 | Quarantine Tool-05 and recalibrate it | Linked to 11 of 11 defective jobs | Tool store |
| 2 | Test Tool-05 against a reference tool | Separates a faulty unit from a calibration lapse (confounded in the data) | Quality |
| 3 | Trace other aircraft serviced with Tool-05 | Exposure outside this dataset is unknown | Planning |
| 4 | Re-inspect the 11 affected aircraft after rework | Confirm each belt is within limits once tension is reset | Line maintenance |
| 5 | Add a calibration gate to the work-order system | Block job sign-off when the selected tool is out of calibration; would have avoided 11 of 11 defects | MRO IT / Quality |

---

## 4. Methods

| Question | Method | Why this method |
|---|---|---|
| Which groups have more defects? | Defect rate per level; Fisher's exact test (level vs rest); Benjamini-Hochberg correction | Exact for small counts; controls false discoveries across 18 tests |
| How strong is a factor overall? | χ² test + Cramér's V; exact permutation test when expected counts < 5 | Effect size on a 0–1 scale; valid p-values for small cells |
| How sure are we of each rate? | Bayesian Beta(1,1) posterior, 90% credible interval, P(rate > rest) by Monte Carlo | Honest uncertainty with only 6–19 jobs per group |
| Is it getting worse over time? | p-chart (p̄ ± 3σ per month); Cochran-Armitage trend test | Standard SPC; trend test for ordered months |
| Is the station a cause or a stand-in? | Stratification (station within tool and within status); Cochran-Mantel-Haenszel | Removes confounding by a measured factor |
| Can we warn before the job? | Depth-2 decision tree; L2 logistic regression (balanced); Firth logistic as a cross-check | Readable rule; penalties handle perfect separation |
| Is the model honest? | Leave-one-out cross-validation; stratified k-fold when there are ≥ 5 of each class | Every prediction comes from a model that never saw that job |
| What about the symptoms? | Leakage comparison: the same model trained on condition, temperature and vibration | Those are recorded at the same inspection as the defect, so they predict the answer from the answer |

**Why only pre-job features?** Tool, tool status, station and month are known before the job starts. Belt condition, temperature and vibration are measured at the same inspection that finds the defect, so a model using them gives no advance warning.

**Why penalised regression?** Tool status perfectly separates defects from non-defects in this data. Ordinary logistic regression then pushes coefficients toward infinity and never converges. The L2 penalty or Firth's correction keeps the estimates finite. Because Tool-05 and *Needs Calibration* are identical columns, the L2 model splits the weight evenly between them.

**Survival analysis** (Kaplan-Meier / Weibull) would answer how long a belt lasts before it fails. It needs install dates or flight hours, which this data does not have.

---

## 5. Limitations

- **Small sample:** 30 jobs, 11 defects, 3 months. A few new records could change any result. The perfect validation scores reflect a clean sample, not a perfect model.
- **Categorical data only:** no tension measurements and no days overdue, so dose-response cannot be tested.
- **Confounding:** Tool-05 and *Needs Calibration* cannot be separated in this data.
- **No causal proof without an intervention:** the recalibration test is the next step.
- **One record per aircraft and no dates:** no survival or repeat-defect analysis.
- **Cost figures are placeholders** (see section 6). The cost model was removed from the dashboard; replace the assumptions with GAL's figures before quoting a number.
- **Prototype only:** not for operational aircraft use.

**Data that would unlock more:** job dates and flight hours (survival analysis), measured belt tension (the mechanism), tool calibration dates (days overdue as a risk score), and technician, engine and belt-batch IDs (the remaining fishbone branches).

---

## 6. Supporting statistics

Removed from the dashboard to keep it to four questions. Quote these if judges ask. All values are from the GAL sample (30 jobs, 11 defects, Jan to Mar) and were produced by the functions in `src/`, which are unchanged and still tested.

### Factor ranking (Fisher's exact test, level vs rest, Benjamini-Hochberg correction)

| Factor | Level | Defects / jobs | Rate | Rate elsewhere | Relative risk | Fisher p | BH q | Cramér's V |
|---|---|---|---|---|---|---|---|---|
| Tool | Tool-05 | 11 / 11 | 100% | 0% | ∞ | 1.8 × 10⁻⁸ | 3.7 × 10⁻⁸ | 1.00 |
| Tool status | Needs Calibration | 11 / 11 | 100% | 0% | ∞ | 1.8 × 10⁻⁸ | 3.7 × 10⁻⁸ | 1.00 |
| Tool | Tool-02 | 0 / 7 | 0% | 48% | 0 | 0.029 | 0.053 | 1.00 |
| Tool | Tool-01 / Tool-03 | 0 / 6 each | 0% | 46% | 0 | 0.061 | 0.092 | 1.00 |
| Station | Station C | 5 / 9 | 56% | 29% | 1.9× | 0.23 | 0.31 | 0.26 |
| Station | Station A | 3 / 11 | 27% | 42% | 0.6× | 0.47 | 0.60 | 0.26 |
| Station | Station B | 3 / 10 | 30% | 40% | 0.75× | 0.70 | 0.79 | 0.26 |
| Month | Jan | 3 / 10 | 30% | 40% | 0.75× | 0.70 | 0.79 | 0.10 |
| Month | Feb / Mar | 4 / 10 each | 40% | 35% | 1.1× | 1.00 | 1.00 | 0.10 |

Belt condition, temperature and vibration give the same 1.8 × 10⁻⁸ but are symptoms recorded with the defect, not causes.

### Whole-factor association (χ², with an exact test when expected counts are below 5)

| Factor | Groups | χ² p | Exact p | Cramér's V | Exact method |
|---|---|---|---|---|---|
| Tool | 4 | 1.4 × 10⁻⁶ | 5.0 × 10⁻⁵ | 1.00 | Fisher-Freeman-Halton permutation (20,000 shuffles) |
| Tool status | 2 | 4.3 × 10⁻⁸ | 1.8 × 10⁻⁸ | 1.00 | Fisher's exact |
| Station | 3 | 0.37 | 0.41 | 0.26 | Fisher-Freeman-Halton permutation |
| Month | 3 | 0.87 | 1.00 | 0.10 | Fisher-Freeman-Halton permutation |

### Bayesian defect rates (Beta(1,1) prior, 90% credible interval)

Fleet average 38% (90% interval 24–52%).

| Group | Jobs | Defects | Estimated rate | 90% interval | P(rate above rest) |
|---|---|---|---|---|---|
| Tool-05 / Needs Calibration | 11 | 11 | 92% | 78–100% | 100% |
| Tool-01 / Tool-03 | 6 | 0 | 13% | 1–35% | 2% |
| Tool-02 | 7 | 0 | 11% | 1–31% | 1% |
| Normal tool status | 19 | 0 | 5% | 0–14% | 0% |
| Station A | 11 | 3 | 31% | 12–53% | 23% |
| Station B | 10 | 3 | 33% | 14–56% | 32% |
| Station C | 9 | 5 | 55% | 30–78% | 92% |
| Jan | 10 | 3 | 33% | 14–56% | 32% |
| Feb / Mar | 10 | 4 | 42% | 20–65% | 62% |

Only Tool-05 / Needs Calibration has an interval entirely above the fleet average. Station C's interval overlaps it.

### Time

- **p-chart:** centre line 36.7%, upper control limit 82%, lower 0% (n = 10 jobs per month). Jan 30%, Feb 40%, Mar 40%: all inside the limits.
- **Cochran-Armitage trend test:** z = 0.46, p = 0.64. The rise from 3 to 4 defects per month is within chance; it follows Tool-05 use (3, 4, 4 jobs).

### Causation

- **Stratification:** within each tool, and within each tool status, every station has exactly the same defect rate (spread 0 percentage points, within-group p = 1.0). Crude station p = 0.41 (exact).
- **Cochran-Mantel-Haenszel** (Tool-05 vs other jobs, stratified by station): χ² = 26.7, p = 2.4 × 10⁻⁷. The tool effect holds after accounting for station.
- **Confounding:** Tool-05 and Needs Calibration occur in exactly the same 11 jobs.

### Prediction models

- **Decision tree rule:** IF tool status is Needs Calibration THEN defect (11 of 11); otherwise no defect (0 of 19).
- **L2 logistic regression (balanced):** Tool-05 and Needs Calibration each ×3.9 odds (coefficient 1.36, weight split evenly because the columns are identical); Normal status ×0.26; Station C ×1.2.
- **Firth logistic (converged):** Tool-05 ×77 odds; every other term between ×0.83 and ×1.21.
- **Validation:** leave-one-out and stratified 5-fold both give ROC-AUC 1.00, recall 100% (11 of 11), precision 100% (0 false alarms), for both the logistic model and the tree. With only 11 defects and perfect separation, this shows a clean sample, not a perfect model.
- **Leakage demo:** a model on belt condition, temperature and vibration also scores AUC 1.00 and recall 100%, because those readings are taken at the same inspection that finds the defect.

### Cost model (placeholder assumptions)

Assumptions: $10,000 per AOG hour, 24 AOG hours per in-service belt failure, 30% of defects would become in-service failures, $1,500 per aircraft re-inspection.

With the calibration gate avoiding 11 defects and 11 aircraft re-inspected: 3.3 in-service failures avoided, 79 AOG hours avoided, $792,000 AOG cost avoided, $16,500 re-inspection cost, **net benefit about $775,500 over three months**. Replace the assumptions with GAL's figures before quoting this.

