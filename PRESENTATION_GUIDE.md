# B787 Belt Health Dashboard: Presentation Guide

A plain-English walkthrough of every page and chart in the dashboard, with what to say when presenting it.

Live app: https://gal-belt-dashboard.streamlit.app

---

## 1. The story in one minute

> We looked at 10,000 past belt screenings on the B787 fleet and built a model that predicts whether a screening will find a belt defect.
> We then used that model on 2,000 newer screenings (May to August 2025) where the answer is not known yet.
>
> The main finding: **belts go wrong when the tension tool has gone too long without calibration.** An uncalibrated tool sets the belt tension wrong, and wrong tension, plus summer heat, is what goes with defects.
>
> Right now, **Tool-03 is 179 days past calibration**, and the aircraft it worked on are the ones the model flags most. Our recommendation: **pull Tool-03 for calibration and inspect the 9 High Risk aircraft first.**

If you only remember one sentence: *"Overdue tool → wrong belt tension → more defects. Tool-03 is the one to fix now."*

---

## 2. Background you need first

### What is the data?
- Each row is one **screening**: a technician checks a belt on one engine of one aircraft.
- For each screening we know the measurements (tension, temperature, vibration, slip), the tool used, the station, the belt supplier, and how hard the engine has been working in the last 30 days.
- **Training data:** 10,000 screenings, Jan 2024 to May 2025. Here we know the real answer: was a defect found, yes or no? About **2.7%** of these found a defect, so defects are rare.
- **Test data:** 2,000 screenings, late May to Aug 2025. Here we **don't** know the answer. Everything you see for this period is a **model prediction**, not a fact.
- The dashboard covers **100 aircraft**, each with a left (L) and right (R) engine, such as ENG-022-L.

### Words used on the dashboard

| Word | Plain meaning |
|---|---|
| **Tension difference** | How far the measured belt tension is from the target tension, in %. +10% means the belt is 10% tighter than it should be. Zero is perfect. |
| **Calibration** | Checking and resetting the tension tool against a trusted reference so it reads correctly. |
| **Days since calibration** | How long since the tool was last calibrated. |
| **Uses since calibration** | How many jobs the tool has done since it was last calibrated. |
| **Calibration load** | Days since calibration × uses since calibration ÷ 1,000. One number for how worn out the tool's calibration is. **Above 90 = overdue.** |
| **Defect risk** | The model's estimate (0–100%) that this screening will find a defect. |
| **Normal range** | The range that 99% of defect-free training screenings stayed inside. Tension difference ≤ 9.7%, belt temperature ≤ 88.2 °C, vibration ≤ 5.1 mm/s. Outside this range is "abnormal". |
| **Test period (predicted)** | The shaded orange area on charts. Everything inside it comes from the model, not from real inspection results. |

### Belt Status: the three colours

| Status | Rule | Meaning |
|---|---|---|
| 🔴 **High Risk** | The model predicts a defect (risk above about 51%, the "Yes threshold") | Inspect first |
| 🟠 **Medium** | Risk is 20% or more, **or** at least one measurement is outside the normal range | Keep an eye on it, inspect soon |
| 🟢 **Normal** | Neither of the above | No action |

---

## 3. The left sidebar: Settings

- **Aircraft status based on:** controls which screening decides each aircraft's colour.
  - **Latest screening** (default): the aircraft's most recent check. Answers "how is it *now*?"
  - **Riskiest screening, last 30 days:** the worst check in the last month. This is a more cautious view, so more aircraft show as risky.
- The grey notes remind the audience that training numbers are real outcomes, test numbers are predictions, and that **association is not proof of cause**.

**What to say:** "You can switch between 'how is each aircraft right now' and 'what was the worst we saw this month'."

---

## 4. Tab 1: Fleet alert (the main page)

This is the page for a maintenance manager: what is wrong, and what to do today.

### The red alert box
- **"19 B787 aircraft have abnormal belt measurements."** Of the 100 aircraft, 19 are High Risk or Medium (9 High Risk + 10 Medium). The other 81 are Normal.
- **"9 are high risk and need inspection first."**
- **The likely contributing factor:** defects are more common when **Tool-03** is used.
  - It is **179 days past calibration**.
  - Belts it tensioned read **+6.4%** above target on average. The other tools are close to 0%.
  - **33%** of its latest jobs are predicted defects, against **5%** for the other tools.
- **Recommendation:** pull Tool-03 for calibration, and inspect the High Risk aircraft first.
- The small grey line says *"Association, not proven cause."* Say this out loud. The data shows the two things happen together; a physical check of the tool confirms it.

### The aircraft table
One row per aircraft, worst first. By default it shows only the flagged aircraft; turn on **"Show all 100 aircraft"** to see the rest.

| Column | What it means |
|---|---|
| Aircraft | Tail ID, such as B787-022 |
| Belt Status | High Risk / Medium / Normal |
| Tension Difference | How far off target the belt tension was at that screening |
| Tool | Which tension tool was used |
| Engine | Which engine, L or R |
| Screening | Date of the screening the status is based on |
| Defect risk | The model's probability of a defect |
| Why flagged | Plain reasons: which measurement was out of range, or which tool was overdue |

**Example to point at: B787-022.** Tension is +14.4% (the normal limit is 9.7%), the belt is hot at 90.8 °C (limit 88.2 °C), and it was set with Tool-03, 175 days overdue. Defect risk is 100%. Every warning sign is present at once.

**A pattern to point out:** 7 of the 9 High Risk aircraft used **Tool-03**. That is why the alert names it.

**What to say:** "This page answers two questions: *which aircraft do we look at first*, and *what is probably causing it*. The table gives the reasons in plain words, so an engineer can act without reading a model."

---

## 5. Tab 2: Trends

This tab answers: is the problem getting better or worse, and when does it happen?

### Chart 1: Monthly defect rate (line chart)
- **What it shows:** the % of screenings each month that found (or are predicted to find) a defect.
- **Blue line, "Actual":** real defect rates from training data, Jan 2024 to May 2025.
- **Orange dashed line, "Predicted":** the model's predicted defect rate for the test months, inside the shaded area.
- **How to read it:**
  - There are **two peaks every year**: one in **late spring / early summer** (around May to June) and one in **autumn** (around Oct to Nov).
  - After **December** the rate drops close to 0%. Tools are recalibrated in December, so they read correctly again.
  - **Each peak is higher than the last.** Apr–May defect rate went from **4.6% in 2024 to 5.9% in 2025.** The problem is growing.
  - The predicted line jumps to about **10%** at the start of the test period (hot season), dips in mid-summer, then climbs back to about **8%** by August as tools go overdue again.

**What to say:** "Defects come in two waves a year. The spring wave follows the heat; the autumn wave follows tools going overdue. A reset in December brings it back down. Each year the waves get bigger."

### Chart 2: Average ambient temperature
- **What it shows:** average outside temperature per month at screening time.
- It's a smooth wave: about **40 °C in summer**, about **22 °C in winter**.
- **Why it's here:** compare it with the defect chart. The spring defect peak lines up with the hottest months, and heat stresses belts.

### Chart 3: Screenings done with an overdue tool (bar chart)
- **What it shows:** each month, the % of screenings where the tool was overdue for calibration (calibration load above 90).
- Bars are **zero from Jan to Jul 2024**, then appear **Aug to Nov 2024** (up to about 21%), disappear after December's recalibration, and come back in **Apr to Aug 2025**, reaching about **22% in August 2025**, the highest yet.
- **Why it's here:** the autumn defect peaks line up with these bars. And August 2025 has the most overdue-tool work we have ever seen, which is why the model expects defects to rise again.

**What to say:** "Two drivers, two charts. Heat explains the spring wave. Overdue tools explain the autumn wave. Right now, in August 2025, we have both at once."

---

## 6. Tab 3: Factors

This tab uses **training data only** (real outcomes). It answers: what is different about screenings that found a defect?

### Chart 1: Defect rate by tension difference
Screenings are grouped by how far off target the tension was:

| Tension difference | Defect rate | Screenings |
|---|---|---|
| 0–2% | 0.4% | 3,978 |
| 2–4% | 0.7% | 2,944 |
| 4–6% | 2.5% | 1,661 |
| 6–8% | 7.3% | 695 |
| 8–10% | 20.9% | 258 |
| over 10% | **50.3%** | 153 |

**What to say:** "This is the clearest chart in the dashboard. Get the tension right and defects almost never happen. Once it's more than 10% off, **half** of those belts have a defect."

### Chart 2: Measurements outside the normal range
For each measurement, two bars: defect rate when the reading was **outside** the normal range (orange) and when it was **inside** (blue).

| Measurement | Defect rate if abnormal | Defect rate if normal | How much more likely |
|---|---|---|---|
| Tension difference | 48% | 1.8% | **about 26×** |
| Belt temperature | 34% | 2.2% | about 15× |
| Vibration | 32% | 2.3% | about 14× |
| Belt slip | 14% | 2.6% | about 5× |

**What to say:** "Any abnormal reading is a warning, but a bad tension reading is the strongest one: 26 times more likely to be a defect."

### Charts 3–5: Defect rate by tool, by station, by belt supplier

| Group | Highest | Others |
|---|---|---|
| **Tool** | Tool-05: 6.6% | Tool-01: 3.1%; the rest 1.2–1.7% |
| **Station** | Station C: 3.8% | Station A: 2.5%, Station B: 2.1% |
| **Supplier** | Supplier B: 3.5% | Supplier A: 1.8% |

**Important point:** these overlap. Tool-05 was the tool most often overdue in late 2024, and where a tool is used is linked to station. So don't present "Station C is bad" or "Supplier B is bad" as separate proven causes. They are **associations**.

**Why Tool-03 looks fine here but is the alert today:** in training (up to May 2025), Tool-03 had a low defect rate of 1.4%. It only went badly overdue *after* that, in the test period. Use this to make the point that **the tool itself isn't bad; any tool goes bad when it isn't calibrated.**

---

## 7. Tab 4: Tools & calibration

This tab answers: which tool is the problem right now, and how do we know calibration matters?

### Tool status table
One row per tool, worst first.

| Column | Meaning |
|---|---|
| Defects (training) | Real defect rate for that tool, Jan 2024 to May 2025 |
| Predicted (test) | Predicted defect rate, May to Aug 2025 |
| Predicted (latest month) | Predicted defect rate in August 2025 only |
| Days since cal. | Days since that tool was last calibrated |
| Uses since cal. | Jobs done since last calibration |
| Avg tension diff. | Average tension error of belts it set in the test period |
| Overdue (test) | % of its test-period jobs done while overdue |

**Tool-03 stands out on every column:**
- 179 days and 1,117 uses since calibration, both the highest.
- Average tension **+6.4%**, while most tools are near 0%.
- **32.9%** predicted defect rate in August, against 0.8–8.1% for the others.
- Overdue for **59%** of its test jobs.

**Tool-05** is second (138 days, +3.7%, 8.1%), so it is worth calibrating soon too.

### Chart: Defect rate by calibration load (training data)

| Calibration load | Defect rate |
|---|---|
| under 30 | 1.6% |
| 30–60 | 1.7% |
| 60–90 | 3.9% |
| **over 90 (overdue)** | **18.9%** |

**What to say:** "This is the proof from real outcomes. A freshly calibrated tool has about a 1.6% defect rate. An overdue tool has nearly 19%, roughly **12 times higher**."

### Tool over time (pick a tool from the dropdown; Tool-03 shown)
Two small line charts for the chosen tool, month by month:
- **Days since calibration:** goes up and down in a saw-tooth through 2024 (it's calibrated regularly, so it never passes about 75 days), then in 2025 it **keeps climbing past 150 days**. Nobody recalibrated it.
- **Avg tension difference:** flat near 0–1% the whole time, then **shoots up to about 6–7%** in the test period, at exactly the time the calibration ran out.

**What to say:** "Watch the two lines rise together. As soon as Tool-03 stopped being calibrated, the belts it set started reading high. That's the mechanism."

### Pattern box
The same thing happened three times: **Tool-05 in late 2024, Tool-01 in spring 2025, and Tool-03 now.** Each time, a tool goes too long without calibration, its belts read high, and defects follow. Choose those tools in the dropdown to show the same shape.

---

## 8. Tab 5: Inspection list

This tab is the working list for engineers.

### Screenings to inspect
- **344** test-period screenings are High Risk or Medium, sorted by highest defect risk first.
- **Filters:** Status (High Risk / Medium), Tool, Station. For example, pick Tool-03 to see every job it touched.
- **Columns:** Record ID, aircraft, engine, date, status, defect risk (shown as a bar), tension difference, tool, station, and why it was flagged.
- **Download inspection list (CSV)** exports the filtered list for planning or hand-over.

Note the difference from Tab 1: Tab 1 shows **one row per aircraft** (its current state). This tab shows **every risky screening** in the period, so one aircraft can appear more than once (B787-048 appears twice).

### Aircraft drill-down
- Choose an aircraft to see **every screening it had in the test period** as dots on a timeline.
- **Height** = predicted defect risk. **Colour** = status.
- The **dashed line ("Yes threshold")** at about 51% is where the model switches to predicting a defect. Dots above it are High Risk.

**Example: B787-022.** All through June and July the dots sit near 0% (green, healthy). Then in **late August** two red dots jump to about **88% and 100%**. Something changed recently: that's when Tool-03 was used on it, far out of calibration.

**What to say:** "This lets an engineer see whether an aircraft has always been a problem or has just turned bad. B787-022 was fine all summer and turned bad in the last two weeks, which matches the tool going overdue."

---

## 9. Tab 6: Model

This tab answers: how good is the prediction, and can we trust it?

### What the model is
An **average of three models**: LightGBM, CatBoost (both are "decision tree" models, good at finding patterns like "if tension is high *and* the tool is overdue…") and logistic regression (a simpler, steadier model). Averaging three different models gives steadier predictions than any one alone.

**Inputs:** the screening's measurements, the tool's calibration state, the engine's last-30-days workload, station, tool, belt supplier and batch. **Technician and month were left out** because adding them made the results worse.

### The scores, explained simply

| Score | Value | Plain meaning |
|---|---|---|
| **Precision** | 0.745 | When the model says "defect", it is right about **3 times out of 4**. |
| **Recall** | 0.758 | Of all real defects, the model catches about **3 out of 4**. |
| **F1** | **0.751** | One number that balances precision and recall (0 = useless, 1 = perfect). |
| **Yes threshold** | 0.509 | Risk above about 51% is called a predicted defect. |

**Why F1 and not accuracy?** Only 2.7% of screenings are defects. A model that always says "no defect" would be 97% accurate and completely useless. F1 only rewards finding the defects.

### How we tested it
- **Cross-validation (F1 0.751):** split the 10,000 rows into 5 parts, trained on 4, tested on the 5th, rotated, and repeated 3 times. Every score comes from data the model didn't see while training.
- **Time check (F1 0.702):** trained on the **oldest 8,000** screenings and predicted the **newest 2,000**. This is the honest test, because in real life we always predict the future from the past. The score drops a little, as expected, but stays solid.

### Why the threshold is set slightly low
The defect rate is rising year on year, so we lean towards **catching more defects** (recall) and accept a few more false alarms. Missing a bad belt costs more than an extra inspection.

### Test-period prediction
The model flags **106 of 2,000** test screenings as defects (**5.3%**), about double the training rate of 2.7%. This is expected, not an error: the test period is the **hot season** plus a **build-up of overdue tools**, the two biggest drivers.

### Limits: say these honestly
- The data is synthetic (made for the case study).
- The dashboard shows **associations, not proven causes**. Confirm with physical inspection and a tool check.
- It is a decision-support tool, **not a certified maintenance system**.

The **Download case_3_predictions.csv** button gives the submission file.

---

## 10. Suggested presentation flow (about 8–10 minutes)

1. **Problem (30 s):** belt defects are rare but costly; can we predict and prevent them?
2. **Fleet alert (2 min):** 19 flagged, 9 High Risk, Tool-03 is the likely cause. Point at B787-022.
3. **Trends (1.5 min):** two waves a year (heat and overdue tools), and each wave is bigger.
4. **Factors (1.5 min):** the tension chart (50% defects above 10% off target) and the "26× more likely" number.
5. **Tools & calibration (2 min):** overdue tools give 19% defects against 1.6%; show Tool-03's two lines rising together; the same thing happened with Tool-05 and Tool-01.
6. **Inspection list (1 min):** the working list, filters, CSV, and the B787-022 drill-down.
7. **Model (1 min):** catches 3 in 4 defects, right 3 in 4 times; tested on future data.
8. **Recommendations (30 s):**
   - Calibrate **Tool-03 now**, and **Tool-05** soon.
   - Inspect the **9 High Risk aircraft** first, then the 10 Medium.
   - **Prevent the next wave:** set a hard calibration limit (for example, load must stay under 60, well before 90) instead of waiting for the December reset.
   - Take extra care with tension in the **hot season**.

---

## 11. Questions you might get, and simple answers

**"Is Tool-03 definitely the cause?"**
No. The data shows a strong association. It has also happened the same way with two other tools, which makes it convincing. The next step is to check Tool-03 against a calibrated reference.

**"Why does Tool-03 look fine in the Factors tab?"**
That tab only covers training data, up to May 2025, when Tool-03 was still calibrated. It went overdue after that. The tool isn't bad; any tool goes bad when it isn't calibrated.

**"Why does the model predict twice as many defects as usual?"**
The test period is the hottest part of the year, and more tools are overdue than ever before. Both push defects up. The rising trend in the real data supports it.

**"What does 100% defect risk mean?"**
The model is very confident, not certain. Every warning sign is present at once (big tension error, hot belt, overdue tool). Treat it as "inspect first".

**"Why not just use accuracy?"**
Defects are only 2.7% of screenings. Always saying "no defect" would score 97% accuracy and catch nothing. F1 measures how well we find the rare defects.

**"How far can we trust 0.75?"**
On a true "predict the future" test it scored 0.70. For a rare-event problem that's strong, but it's a tool to prioritise inspections, not to replace them.

**"Why were technician and month left out?"**
Adding them made the validation score worse. Month is already covered by temperature and calibration, and technician added noise.

**"What is the difference between Medium and High Risk?"**
High Risk means the model predicts a defect. Medium means the risk is 20% or more, or a reading is outside the normal range: not predicted as a defect, but worth checking.
