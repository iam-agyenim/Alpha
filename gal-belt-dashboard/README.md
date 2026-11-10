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

## Tabs

| Tab | Shows |
|---|---|
| Overview | Alert, KPIs, defect rate by tool, Pareto chart, filterable records |
| Why | Factor ranking (rate, relative risk, Fisher p, BH q, Cramér's V), Bayesian intervals, tool × station heatmaps |
| When | Monthly jobs vs defects, p-chart, Cochran-Armitage trend test |
| Causation | Station rates within each tool and tool status, CMH test, confounding check |
| Prediction | Pre-job risk checker, learned decision-tree rule, logistic and Firth models, leave-one-out validation, leakage comparison |
| Action plan | Aircraft to inspect (CSV download), calibration-gate impact, cost estimate from sidebar assumptions |
| Data quality | Normalisation log, column profile |

## Methods summary

- **Association:** Fisher's exact test per level with Benjamini-Hochberg correction; χ² and Cramér's V per factor, with an exact test when expected counts are below 5; Beta(1,1) posterior rates with 90% intervals.
- **Time:** p-chart with ±3σ limits; two-sided Cochran-Armitage trend test.
- **Causation:** stratified rates and Cochran-Mantel-Haenszel; exact-overlap (confounding) detection between pre-job factors.
- **Prediction:** pre-job features only (tool, tool status, station, month); depth-2 decision tree, L2 logistic regression and Firth logistic regression; leave-one-out cross-validation with automatic small-sample and separation warnings.
- **Impact:** calibration gate (block tools not in *Normal* status) applied to past jobs; cost model driven by sidebar inputs.

Nothing is hardcoded. The suspect factor is the pre-job level with the lowest BH q-value. `tests/test_app.py` reruns the whole app on a file where Tool-02 is the faulty tool and fails if any visible text still names Tool-05.

## Layout

```
app.py            Streamlit UI (computed content only)
src/data.py       load, validate, normalise
src/stats.py      statistical tests and generated conclusions
src/model.py      models, validation, risk checker
src/impact.py     calibration gate, cost model, inspection list
src/charts.py     Plotly figures
tests/            pytest + Streamlit AppTest
```
