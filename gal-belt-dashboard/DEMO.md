# 5-minute demo script

**Setup:** the dashboard shows only computed results. Put the 5 Whys, fishbone, Bradford Hill, actions and limitations on slides, using PRESENTATION_NOTES.md. Run `streamlit run app.py` and start on the first tab. Use full-screen browser zoom. Each tab answers one question with one main visual.

---

### 0:00 to 0:30 · The problem
> "GAL asked why B787 engine belt defects are increasing. We had 30 maintenance records from January to March. Our goal was to find the cause, prove it as far as the data allows, and stop the next defect before it happens."

### 0:30 to 1:00 · The alert banner
Point at the red banner and the KPI row.
> "The dashboard computes this alert from the data: 11 of 30 jobs had a defect. Every one of them involved Tool-05, which is marked *needs calibration*. That's 11 of 11 jobs with that tool versus 0 of 19 with any other tool. Fisher's exact test puts the chance of this happening by luck at about 2 in 100 million."

Mention: "Nothing is hardcoded. If you upload a file where a different tool is the problem, the dashboard names that tool."

### 1:00 to 1:50 · Why are defects happening? (tab 1)
Read the answer line, then point at the tool bar chart and the heatmap.
> "Tool-05 has 11 of 11 jobs defective; every other tool has none. Station C looked worse at first, but the heatmap shows the defects sit in the Tool-05 row at every station. Within each tool, every station has the same defect rate, so the station effect disappears. What the data cannot do is separate the tool itself from its missed calibration, because they always occur together *(see PRESENTATION_NOTES.md §1 and §6)*."

### 1:50 to 2:20 · When do defects happen? (tab 2)
> "Defects did go up, from 3 to 4 a month, but so did use of Tool-05: 3, 4, 4. The trend test gives p = 0.64, and the p-chart shows no month out of control. So the fleet isn't wearing out. The increase follows how often that tool was used."

### 2:20 to 3:30 · Can we predict defects before the job? (tab 3)
Live demo:
1. Default: **Tool-05 / Needs Calibration**, which shows **High risk ⛔**, 11 of 11 past jobs defective, "swap to a calibrated tool".
2. Change the tool to **Tool-01** and the status to **Normal**, which shows **Low risk ✅**.

> "This uses only information available *before* the job starts. A model that uses belt temperature and vibration also scores perfectly, but those readings come from the same inspection that finds the defect, so it predicts the answer from the answer. We excluded them on purpose."

Honesty line: "With 11 defects these scores are unstable. A perfect score means the pattern is clean in this sample, not that the model will be perfect in service."

### 3:30 to 4:30 · What should maintenance do? (tab 4)
> "Eleven aircraft need inspection, and the list downloads as a CSV for planning. The root cause is a process gap: nothing blocks a tool that is overdue for calibration. A calibration gate in the work-order system would have prevented all 11 defects in this sample. Under placeholder costs (24 AOG hours at $10k per hour, 30% of defects becoming in-service failures), that is about $775k in avoided AOG cost over three months, against $16.5k of re-inspections *(cost figures: PRESENTATION_NOTES.md §6)*."

### 4:30 to 5:00 · Root cause, limitations and next steps (slides from PRESENTATION_NOTES.md)
> "This is 30 records over 3 months with categorical data only, so it is a strong signal, not proof. To confirm it: recalibrate Tool-05 and test it against a reference tool. To go further, add job dates, flight hours and measured belt tension, which would enable time-to-failure prediction."

**Close:** "One tool, one missing check, eleven defects, and a fix that costs almost nothing."
