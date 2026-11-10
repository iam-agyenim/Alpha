# 5-minute demo script

**Setup:** run `streamlit run app.py`, switch on **Presentation mode** in the sidebar, and start on the Overview tab. Use full-screen browser zoom.

---

### 0:00 to 0:30 · The problem
> "GAL asked why B787 engine belt defects are increasing. We had 30 maintenance records from January to March. Our goal was to find the cause, prove it as far as the data allows, and stop the next defect before it happens."

### 0:30 to 1:00 · The alert banner
Point at the red banner and the KPI row.
> "The dashboard computes this alert from the data: 11 of 30 jobs had a defect. Every one of them involved Tool-05, which is marked *needs calibration*. That's 11 of 11 jobs with that tool versus 0 of 19 with any other tool. Fisher's exact test puts the chance of this happening by luck at about 2 in 100 million."

Mention: "Nothing is hardcoded. If you upload a file where a different tool is the problem, the dashboard names that tool."

### 1:00 to 1:40 · Why (Why tab)
Show the Bayesian chart.
> "Each dot is a group's estimated defect rate, and the line shows our uncertainty. Only Tool-05 and *needs calibration* sit clearly above the fleet average. The heatmap shows the defects sit in the Tool-05 row at every station."

### 1:40 to 2:10 · When (When tab)
> "Defects did go up, from 3 to 4 a month, but so did use of Tool-05: 3, 4, 4. The trend test gives p = 0.64, and the p-chart shows no month out of control. So the fleet isn't wearing out. The increase follows how often that tool was used."

### 2:10 to 2:50 · Causation (Causation tab)
> "Station C looked worse at first. But within each tool, every station has exactly the same defect rate, so the station effect disappears. Most Bradford Hill criteria are met. What the data cannot do is separate the tool itself from its missed calibration, because they always occur together. That's why our first action is a recalibration test against a reference tool."

### 2:50 to 3:40 · Pre-job risk checker (Prediction tab)
Live demo:
1. Default: **Tool-05 / Needs Calibration**, which shows **High risk ⛔ ~89%**, "swap to a calibrated tool".
2. Change the tool to **Tool-01** and the status to **Normal**, which shows **Low risk ✅**.

> "This uses only information available *before* the job starts. A model that uses belt temperature and vibration also scores perfectly, but those readings come from the same inspection that finds the defect, so it predicts the answer from the answer. We excluded them on purpose."

Honesty line: "With 11 defects these scores are unstable. A perfect score means the pattern is clean in this sample, not that the model will be perfect in service."

### 3:40 to 4:30 · Action plan and impact (Action plan tab)
> "Eleven aircraft need inspection, and the list downloads as a CSV for planning. The root cause is a process gap: nothing blocks a tool that is overdue for calibration. A calibration gate in the work-order system would have prevented all 11 defects in this sample. Under placeholder costs (24 AOG hours at $10k per hour, 30% of defects becoming in-service failures), that is about $775k in avoided AOG cost over three months, against $16.5k of re-inspections. GAL can enter its own figures in the sidebar."

### 4:30 to 5:00 · Limitations and next steps (Data & methods tab)
> "This is 30 records over 3 months with categorical data only, so it is a strong signal, not proof. To confirm it: recalibrate Tool-05 and test it against a reference tool. To go further, add job dates, flight hours and measured belt tension, which would enable time-to-failure prediction."

**Close:** "One tool, one missing check, eleven defects, and a fix that costs almost nothing."
