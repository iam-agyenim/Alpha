# B787 Belt Health: Presentation Guide

A plain-English walkthrough of the app (the **Dashboard** with our findings and the **Workflow** where AI agents act on them), with what to say when presenting.

Live app: https://gal-belt-dashboard.streamlit.app

---

## 1. The story in one minute

> We looked at 10,000 past belt screenings on the B787 fleet and built an ML model that predicts whether a screening will find a belt defect. We then used it on 2,000 newer screenings (May to August 2025).
>
> **The finding:** belts go wrong when the tension tool has gone too long without calibration. An uncalibrated tool sets the tension wrong, and wrong tension (plus summer heat) is what goes with defects. Right now **Tool-03 is 179 days past calibration** and is linked to **7 of the 9 High Risk aircraft**.
>
> **What we built on top:** an automated workflow. New screenings pass a security agent, get scored by the model, and then a **Quality & Safety agent**, a **Logistics agent** and a **Commercial agent** pass results to each other: which aircraft to inspect, which belts and calibration slots are needed, what flights and money are at stake. A security check verifies every number, and a manager approves before any work order is issued.

If you remember one sentence: *"Overdue tool → wrong belt tension → more defects. The model finds it; the agents turn it into an approved plan."*

---

## 2. Background you need first

### The data
- Each row is one **screening**: a technician checks a belt on one engine of one aircraft.
- For each screening we know the measurements (tension, temperature, vibration, slip), the tool, station, belt supplier, and how hard the engine worked in the last 30 days.
- **Training data:** 10,000 screenings, Jan 2024 to May 2025, with the real answer (defect found yes/no). About **2.7%** found a defect, so defects are rare.
- **Latest period:** 2,000 screenings, late May to Aug 2025, with **no answer yet**. Everything shown for this period is a **model prediction**.
- **100 aircraft**, each with a left (L) and right (R) engine (e.g. ENG-022-L).

### Words used in the app

| Word | Plain meaning |
|---|---|
| **Tension difference** | How far the measured belt tension is from the target, in %. +10% = 10% too tight. 0 is perfect. |
| **Calibration** | Checking and resetting the tension tool against a trusted reference so it reads correctly. |
| **Calibration load** | Days since calibration × uses since calibration ÷ 1,000. One number for how worn out the tool's calibration is. **Above 90 = overdue.** |
| **Defect risk** | The model's estimate (0–100%) that this screening will find a defect. |
| **Normal range** | The range 99% of defect-free training screenings stayed inside: tension difference ≤ 9.7%, belt temperature ≤ 88.2 °C, vibration ≤ 5.1 mm/s. |
| **Agent** | An AI worker with one job and a fixed set of read-only tools; it receives a hand-off and sends results to the next step. |

### Belt status (three colours: white, green, black)

| Badge | Rule | Meaning |
|---|---|---|
| **Black badge: High Risk** | Model predicts a defect (risk above about 51%) | Inspect first |
| **Green outline: Medium** | Risk ≥ 20% **or** a reading outside the normal range | Inspect soon |
| **Light green: Normal** | Neither | No action |

---

## 3. The app at a glance

- **Left sidebar:** two pages, **📊 Dashboard** (our findings) and **🔀 Workflow** (the AI agents acting on them).
- **Theme:** white background, one green for "good / done / data", black for buttons, warnings and High Risk.
- **Footer notes in the sidebar:** training data is real outcomes, the latest period is predictions, and associations are not proof of cause.

---

## 4. The Dashboard page

The dashboard is deliberately minimal: four numbers, one alert, one table, three charts and the reports.

### The four numbers (KPI cards)

| Card | Value | What to say |
|---|---|---|
| **Aircraft flagged** | 19 / 100 | High Risk or Medium at their latest screening |
| **High Risk** (green card) | 9 | The model predicts a defect: these are inspected first |
| **Predicted defects** | 106 / 2,000 | 5.3% of the latest screenings, double the 2.7% history: hot season plus overdue tools |
| **Model F1** | 0.75 | 0.70 on a strict "predict the future" test (see section 6) |

### The fleet alert (black box)
*"19 B787 aircraft have abnormal belt measurements. 9 are high risk and need inspection first."* The likely contributing factor is **Tool-03**: 179 days past calibration, belts it tensioned read **+6.4%** over target, and **33%** of its latest jobs are predicted defects against **5%** for other tools. **Recommended:** pull Tool-03 for calibration and inspect High Risk aircraft first. Say out loud: *association, not proven cause*. A physical tool check confirms it.

### Aircraft needing attention (table)
One row per flagged aircraft, worst first: aircraft, status badge, tension difference, tool, defect risk, and **why it was flagged** in plain words. Toggle **Show all 100 aircraft** to see every aircraft.

**Example: B787-022.** Tension +14.4% (normal ≤ 9.7%), belt 90.8 °C (normal ≤ 88.2 °C), tensioned with Tool-03 (175 days overdue). Risk 100%. Every warning sign at once.

### Chart 1: Defect rate by month
- **Green line:** real defect rates (Jan 2024 to May 2025). **Black dashed line:** predicted rates for the latest period.
- **Two waves a year:** late spring (heat) and autumn (tools going overdue before the December recalibration), then near 0% after the reset.
- **Rising:** April–May went from **4.6% (2024) to 5.9% (2025)**; the prediction climbs back to about **8%** by August.

*"Defects come in two waves a year, and each wave is bigger. Right now we have heat and overdue tools at the same time."*

### Chart 2: Defect rate by tool calibration load

| Calibration load | Defect rate |
|---|---|
| under 30 | 1.6% |
| 30–60 | 1.7% |
| 60–90 | 3.9% |
| **over 90 (overdue, black bar)** | **18.9%** |

*"A freshly calibrated tool: 1.6% defects. An overdue tool: nearly 19%, about 12 times higher."*

### Chart 3: Defect rate by tension error

| Tension off target | Defect rate |
|---|---|
| 0–2% | 0.4% |
| 2–4% | 0.7% |
| 4–6% | 2.5% |
| 6–8% | 7.3% |
| 8–10% | 20.9% |
| **over 10% (black bar)** | **50.3%** |

*"Get the tension right and defects almost never happen. More than 10% off target, and half the belts have a defect."*

### Reports
- **⬇ Inspection list (CSV):** every High Risk or Medium screening in the latest period, with reasons.
- **⬇ Model predictions (CSV):** the submission file.
- A one-line model summary (F1, precision, recall).

---

## 5. Extra facts for questions

These aren't on the minimal dashboard but are good answers to questions.

**Abnormal readings and defect odds (training data):**

| Measurement outside normal range | Defect rate | vs normal | How much more likely |
|---|---|---|---|
| Tension difference | 48% | 1.8% | about 26× |
| Belt temperature | 34% | 2.2% | about 15× |
| Vibration | 32% | 2.3% | about 14× |
| Belt slip | 14% | 2.6% | about 5× |

**The same pattern, three times:** Tool-05 (late 2024), Tool-01 (spring 2025), Tool-03 (now). Calibration lapses, tension drifts, defects follow.

**Supplier B is not the problem:** Supplier B looks worse overall (3.5% vs 1.8%), but **with a calibrated tool both are the same (1.8% vs 1.7%)**. Supplier B's belts only fail more when the tool is overdue (25% vs 5%). Fix the tools; don't switch suppliers.

**Heat:** the defect rate doubles when ambient is above 35 °C (4.2% vs 1.9%).

---

## 6. The model

**What it is:** an average of three models: LightGBM, CatBoost (decision-tree models that find patterns like "high tension *and* overdue tool") and logistic regression (simpler and steadier). Technician and month were left out because they made results worse.

| Score | Value | Plain meaning |
|---|---|---|
| **Precision** | 0.745 | When it says "defect", it's right about **3 times in 4** |
| **Recall** | 0.758 | It catches about **3 in 4** real defects |
| **F1** | **0.751** | One number balancing both (0 = useless, 1 = perfect) |

- **Why not accuracy?** Only 2.7% are defects; always saying "no defect" is 97% accurate and useless.
- **Cross-validation (F1 0.751):** split into 5 parts, train on 4, test on the 5th, rotate, repeat 3 times.
- **Time check (F1 0.702):** train on the oldest 8,000, predict the newest 2,000. This is the honest test, because in real life we predict the future from the past.
- **Threshold set slightly low** to catch more defects, because missing a bad belt costs more than an extra inspection.
- **Limits:** synthetic data; associations, not proven causes; decision support, not a certified maintenance system.

---

## 7. The Workflow page (applied AI)

### What it is, in one sentence
**An automated maintenance workflow where the ML model and four AI agents pass data and results to each other, ending in a human-approved plan and work orders**, shown as a live, animated diagram with a timestamped log.

### Why we still need the ML model

| Job | Done by | Why |
|---|---|---|
| Predicting defects from thousands of rows of numbers | **ML model** (F1 0.75) | AI language models are poor at precise maths over large tables |
| Counting belts, staff hours, costs | **Calculators in code** | Must be exact and repeatable, so the AI never does arithmetic |
| Deciding, planning, explaining, writing hand-offs | **AI agents** | This is what language models are good at |

### The pipeline

```
Incoming data → Security agent → ML model → Orchestrator
                                               ↓
   Security check ← Commercial ← Logistics ← Quality & Safety
         ↓
   Human approval → Outputs (work orders, PDF report, email)
```

| Step | Type | Receives | Sends |
|---|---|---|---|
| **Incoming data** | code | The chosen batch of screenings (latest month, last 14 days, or whole period) | Raw batch → Security |
| **Security agent** | rules in code | Raw batch | Clean batch: checks columns, ID formats, value ranges, duplicates; **quarantines rows with instruction-like text** |
| **ML model** | the trained model | Clean batch | Risk score per screening, High Risk / Medium aircraft, tool most linked to risk |
| **Orchestrator** | code | Model results | Routing plan; sends the risk results to Quality & Safety |
| **Quality & Safety agent** | AI (gpt-6-luna) | Model results | Inspections with priority (**P1 today, P2 within 48h, P3 next check**), tool actions, safety notes → Logistics |
| **Logistics agent** | AI (gpt-6-luna) | Safety orders | Belts per station (stock vs order), calibration slot and loan tool per tool, technician capacity → Commercial |
| **Commercial agent** | AI (gpt-6.1-terra) | Safety orders + logistics plan | Flights at risk in the next 24h, plan cost vs defect cost at risk, customer note, recommendation → Security check |
| **Security check** | code | All agent outputs | Verifies **every number** the agents wrote against the model, data and calculators |
| **Human approval** | person | Verified plan | Approve or reject (name, time and comment logged) |
| **Outputs** | code | Approved plan | Work orders, PDF report, CSV, email |

### What you see on the page
1. **Controls:** batch picker, **▶ Run workflow** (black: runs the real agents, about a minute, about 2¢) and **↺ Replay** (replays the animation free).
2. **While running:** a live progress list streams each step and agent action as it happens.
3. **The animated diagram:**
   - each step is a card that **pulses black while running** and turns **green when done**
   - **green data packets travel along the arrows** when one step hands results to the next
   - each card shows its latest action ("Called tools_at_risk()") and stats (tool calls, seconds, cost)
   - **Human approval** ends on a dashed green "Your turn" card
   - a top bar shows run ID, batch, run time, tokens and cost and status, with **Pause, 1× / 2× / 4× speed and Replay**
4. **Event log:** every event with **timestamp, time since start, agent, type** (start, receive, think, tool, check, send, done, decision) and message.
5. **Step details:** click any card to see what it received and sent: model numbers, inspections, belt plan, costs, number-check result.
6. **Your decision:** a green box with the Commercial agent's recommendation and key facts (inspections, tool actions, belts to order, plan cost). Type your name and a comment, then **✓ Approve** or **✕ Reject**. Approving animates the last hand-off and issues the work orders.
7. **Outputs:** work-order table, **⬇ Report (PDF)**, **⬇ Work orders (CSV)**, and **✉️ Email plan** (opens your mail app with the plan filled in).
8. **Expanders:** structured agent outputs, the full event log (download as JSON), and the security controls.

### Example: a real run (the recorded sample, latest month)
- **Intake:** 622 screenings from 100 aircraft (29 Jul – 29 Aug 2025).
- **Security agent:** 622 valid, 0 quarantined, 51 with missing readings (kept and flagged).
- **ML model:** 48 predicted defects, **9 High Risk**, 10 Medium; tool most linked to risk **Tool-03**.
- **Quality & Safety:** **19 inspections** (4 P1, 9 P2, 6 P3), and **Tool-03 and Tool-05: remove from service and calibrate**.
- **Logistics:** belts to order: Station A 1, Station B 5, Station C 4. Tool-03 gets the **Today 14:00** slot (loan Tool-01) and Tool-05 **Today 16:00** (loan Tool-02). All inspections fit in one shift.
- **Commercial:** the aircraft have about **49 estimated flights in the next 24h**. The plan costs **$6,000** against **$240,000** of predicted defect cost at risk (2.5%). Recommendation: support the plan and have an engineer review the abnormal low-risk readings.
- **Security check:** 3/3 agents passed number verification.
- **Cost:** about **21,000 tokens, $0.015**, about 1 minute. After approval: **21 work orders**.

**What to say:** *"The model finds the risk. The agents turn it into a plan the business can act on: who inspects what, which parts and slots, what's at stake. Every number is checked, and nothing happens until a person approves."*

**Demo tip:** open the Workflow page early. The recorded sample replays instantly (no internet or API key needed). If you have time, press **▶ Run workflow** for a live run, then **Approve** to show the outputs.

**Honest note:** belt stock, calibration slots, technician numbers, flight estimates and unit costs are **planning assumptions**, because the dataset doesn't have them. The agents, the log and the PDF all label them as assumptions. In a real deployment they'd come from the stores, scheduling and finance systems.

---

## 8. Security: a critical look

| Threat | How it could happen | Our defence |
|---|---|---|
| **Prompt injection in the data** | A data field contains "ignore your instructions…" | The **Security agent quarantines** rows with instruction-like text before the model or any agent sees them; every string a tool returns also passes an allowlist |
| **Prompt injection between agents** | One agent's output tries to steer the next | Hand-offs are wrapped as "data, not instructions"; every agent's rules say never to obey text found in data |
| **Made-up numbers** | An agent writes "risk 85%" when the model said 40% | The **Security check** verifies every number against the model, data and calculators; a mismatch is flagged in the log and report |
| **Too much power** | An agent issues work orders or changes data | Agents have **read-only tools and calculators only** (allowlist per agent). Work orders are created by code **only after human approval** |
| **Bad input data** | Wrong IDs, impossible values, duplicates | Rule checks on schema, ID formats, value ranges and duplicates; bad rows are quarantined and counted in the log |
| **Runaway cost** | A loop or repeated runs | Max 6 tool rounds per agent, capped output, **5 runs per session**, daily token cap |
| **Key leak** | API key in code or GitHub | Key only in Streamlit Secrets or a git-ignored `.env`; never in prompts, logs or code |
| **Over-trust** | AI output treated as an order | **Human approval gate**; approver name, time and comment logged; every run audit-logged |

**What to say:** *"We assumed the AI could be attacked and could be wrong. So bad data is quarantined at the door, agents can only read, every number is checked, and a person signs off."*

**Honest limit:** pattern-based screening can be fooled by clever wording. That's why it's one layer of several: the real protection is that agents can't act, and their numbers are verified.

---

## 9. Cost and the business case

### Measured cost (real runs, OpenAI Standard prices, Nov 2026)

| Model | Used for | Price per 1M tokens (in / out) |
|---|---|---|
| gpt-6-luna | Quality & Safety, Logistics | $0.10 / $0.50 |
| gpt-6.1-terra | Commercial | $1.00 / $5.00 |

| Action | Tokens | Cost | Time |
|---|---|---|---|
| **One full workflow run** | about 20,000–28,000 | **about $0.015–0.02** | about 1 minute |
| **Replay** | 0 | free | instant |

### At enterprise scale (1,000 aircraft, 20 bases, 1,500 users)
AI tokens: about **$17k–$175k a year** depending on model tier. The **total cost of ownership** (team, maintenance-system integration, enterprise AI platform, hosting, security and compliance) is about **$0.7M–$1.5M a year**, and tokens are under 10% of that. Against about **$3.9M a year** from better calibration alone, it **pays back in year 1**. Full breakdown: `BUSINESS_CASE.md`, section 6.

### The value story
- One prevented AOG (aircraft on ground) event can be worth $100k+ (assumption), far more than years of AI cost.
- Every morning, an approved plan: which aircraft, which tool, which belts, who, by when, and what's at stake.
- Results can be reproduced (validated model), explained (agents show evidence), checked (number verification) and audited (timestamped log, approval record), which is what aviation regulators expect.

---

## 10. Suggested presentation flow (about 8–10 minutes)

1. **Problem (30 s):** belt defects are rare but costly. Can we predict and prevent them?
2. **Dashboard (3 min):** the KPI cards, the alert (Tool-03), B787-022 in the table, then the three charts: two waves a year, overdue tools at 19% vs 1.6%, tension more than 10% off at 50%.
3. **Model (1 min):** catches 3 in 4 defects, right 3 in 4 times, tested on future data.
4. **Workflow (3–4 min):** replay the run while explaining each agent. Click Quality & Safety, then Logistics, to show what was passed. Point at the log timestamps. Approve and show the work orders and PDF.
5. **Security and cost (1 min):** quarantine, read-only agents, number check, human gate; about 2¢ per run.
6. **Recommendations (30 s):** calibrate Tool-03 now (Tool-05 next), inspect the 9 High Risk aircraft, calibrate by condition (load ≤ 60) instead of by calendar, and take extra care with tension in the hot season.

---

## 11. Questions you might get

**"Is Tool-03 definitely the cause?"**
No. It's a strong association, and the same pattern happened with two other tools. Confirm with a physical tool check.

**"Why does the model predict twice as many defects as usual?"**
The latest period is the hottest part of the year, and more tools are overdue than ever. Both push defects up.

**"What does 100% risk mean?"**
Very confident, not certain: every warning sign is present at once. Treat it as "inspect first".

**"If you have AI agents, why build an ML model?"**
The model does the precise prediction over thousands of rows (F1 0.75); the agents do the planning and communication. Agents alone would guess and cost tokens per row.

**"Are the logistics and commercial numbers real?"**
The counts come from our data (which aircraft, which station). Stock levels, slots, flight estimates and unit costs are planning assumptions, clearly labelled. In production they'd come from the stores, scheduling and finance systems.

**"What stops someone hacking it?"**
Bad data is quarantined before the model, agents can only read, hand-offs are treated as data, every number is checked, and a person approves. The API key is never in a prompt.

**"What if an agent makes a mistake?"**
The security check flags any number that doesn't match the model or data, the manager sees the plan before approving, and everything is in the timestamped log.

**"What does it cost to run?"**
About 1.5–2¢ per run, measured. At enterprise scale the tokens are a small part; people, integration and compliance are most of the cost.

**"Can it run without internet?"**
The dashboard, model and replay work offline. Only a live workflow run needs the AI API.
