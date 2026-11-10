# B787 Engine Belt Defect Investigation

MoIAT x GAL "AI for Smart Maintenance" hackathon, Case 3. A Streamlit dashboard that finds what drives B787 engine belt defects, tests whether a station or month effect survives stratification, scores defect risk before a job starts, and lists the aircraft to inspect.

The dashboard shows only results computed from the loaded file. Background, root-cause narrative, the Bradford Hill checklist, recommended actions and limitations are in [PRESENTATION_NOTES.md](PRESENTATION_NOTES.md). The demo script is in [DEMO.md](DEMO.md).

> Prototype only. Not for operational aircraft use.

## Run it

Python 3.10 or newer is required.

```bash
cd gal-belt-dashboard
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py               # http://localhost:8501
pytest -q                          # statistics, model and full-app tests
```

The bundled file `data/gal_belt_data.csv` is the GAL Case 3 data. Upload another CSV or XLSX file with the same columns from the sidebar. Headers and labels are normalised: `Y`/`True` count as a defect, `Due`/`Overdue` count as *Needs Calibration*, and dates or month numbers become month names. If required columns are missing, the app lists them.

**Deploy:** on [share.streamlit.io](https://share.streamlit.io), set the main file path to `gal-belt-dashboard/app.py` and the Python version to 3.12.

## Real GAL data (release v2)

Upload either v2 file from the sidebar and the app switches to v2 mode automatically:

| File | What the dashboard shows |
|---|---|
| `case_3_test_inputs.csv` (2,000 unlabelled episodes) | Model risk for every episode and aircraft, the aircraft board with tension difference and readings, predicted defect rate by tool, batch and month, an inspection list, and a **Submission CSV** download (`case_3_predictions.csv`, format-checked on the page) |
| `Case_3_Train_Participants.xlsx` (10,000 labelled episodes) | The same, plus actual defect rates next to the predictions and the model's score on the file (optimistic, because the model was trained on it) |

The model is trained offline in `Backend/` (`python -m case3.train`, about 6 minutes) and saved to
`Backend/output/model.joblib`; the dashboard only loads it, so scoring takes under a second. The file format is
detected from its columns; the 30-row sample keeps the original view.

To open a file by default when running locally (useful for a demo), set `BELT_DATA`:

```bash
BELT_DATA=../Backend/data/case_3_test_inputs.csv streamlit run app.py
```

## Layout of the dashboard

A header with the computed alert banner and four KPIs (total jobs, defects, defect rate with the suspect tool, defect rate with other tools), then one tab per question. Each tab has a one-line computed answer above a single main visual.

| Tab | Answer line | Main visual |
|---|---|---|
| Why are defects happening? | Suspect factor, its share of defects, Fisher p | Defect rate by tool, plus a tool × station heatmap with a computed "is it the station?" line |
| When do defects happen? | Whether any month is outside the p-chart limits, and the trend-test p-value | Monthly defects vs suspect-tool jobs |
| Can we predict defects before the job? | Pre-job risk checker (Low/Medium/High, rate with 90% range, recommendation) | Learned decision-tree rule, leave-one-out recall and precision, leakage check (one line each) |
| What should maintenance do? | Calibration gate: defects that occurred → with calibrated tools only → % reduction | Aircraft to inspect, with readings and a CSV download |

The sidebar has only the file upload and the risk thresholds. Detailed statistics (factor ranking, Cramér's V, Bayesian intervals, p-chart, CMH, model coefficients, cost model) are in PRESENTATION_NOTES.md under "Supporting statistics".

## Methods summary

- **Association:** Fisher's exact test per level with Benjamini-Hochberg correction; χ² and Cramér's V per factor, with an exact test when expected counts are below 5; Beta(1,1) posterior rates with 90% intervals.
- **Time:** p-chart with ±3σ limits; two-sided Cochran-Armitage trend test.
- **Causation:** stratified rates and Cochran-Mantel-Haenszel; exact-overlap (confounding) detection between pre-job factors.
- **Prediction:** pre-job features only (tool, tool status, station, month); depth-2 decision tree, L2 logistic regression and Firth logistic regression; leave-one-out cross-validation with automatic small-sample and separation warnings.
- **Impact:** calibration gate (block tools not in *Normal* status) applied to past jobs; affected-aircraft list with priorities.

Nothing is hardcoded. The suspect factor is the pre-job level with the lowest BH q-value. `tests/test_app.py` reruns the whole app on a file where Tool-02 is the faulty tool and fails if any visible text still names Tool-05.

## Layout

```
app.py            Streamlit UI (computed content only)
src/data.py       load, validate, normalise
src/stats.py      statistical tests and generated conclusions
src/model.py      models, validation, risk checker
src/impact.py     calibration gate, inspection list, fleet status
src/charts.py     Plotly figures
tests/            pytest + Streamlit AppTest
```
