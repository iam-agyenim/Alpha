# Business Case: Cutting Belt-Defect Cost on the B787 Fleet

*What our model and data tell an aerospace business: the problems, the fixes, the money, and how the AI agents make it happen every day.*

---

## 1. The situation

We are the reliability engineering team for an operator (or MRO) running **100 B787 aircraft** (200 engines). Every engine's belt is screened regularly, about **7,300 screenings a year**. Some screenings find a **belt defect**. Each defect costs money:

- **Found on the ground:** a belt replacement, labour, and the aircraft held for repair.
- **Missed until it fails in service:** an AOG (aircraft on ground), flight delays or cancellations, passenger compensation, and a rushed repair away from base. This is far more expensive.

**Business goal:** fewer defects, catch the rest early, and spend inspection and maintenance money only where it matters.

**What we have:** 10,000 past screenings with known outcomes (Jan 2024 to May 2025), 2,000 recent screenings scored by our ML model (May to Aug 2025), and a model that predicts defects with **F1 0.75** (0.70 on a strict "predict the future" test).

---

## 2. What the data found: six business problems

### Problem 1: Uncalibrated tools cause about 4 in 10 defects
- **106 of 269 defects (39%)** happened when the tension tool was **overdue for calibration**.
- Overdue tool: **18.9%** defect rate. Freshly calibrated tool: **1.6%**. That is **about 12 times higher**.
- The same thing happened three times: **Tool-05 (late 2024), Tool-01 (spring 2025), Tool-03 (now)**. Every time, calibration lapsed, tension drifted, and defects followed.
- **Today:** Tool-03 is **179 days** past calibration, belts it sets read **+6.4%** over target, and it is linked to **7 of the 9 High Risk aircraft**. **40 of the 106** predicted defects in the latest period involve overdue tools.

> **Root cause:** a process gap. Calibration is allowed to slip for months, and nothing warns anyone.

### Problem 2: Wrong belt tension is how the damage happens
- Belts more than **6% off target** are only **11% of screenings**, but they hold **68% of all defects**.
- More than 10% off target: **1 in 2** belts has a defect.
- An overdue tool **plus** tension more than 6% off: **42%** defect rate. A calibrated tool with good tension: **0.9%**.

> **Meaning:** the defect is mostly "built in" at the moment the belt is tensioned with a bad tool. It's preventable at the point of work.

### Problem 3: Inspection effort isn't targeted
Our model ranks every screening by risk. On data it never saw while training:

| Detailed inspection of… | Screenings | Defects caught |
|---|---|---|
| Top **2%** by model risk | 200 | **61%** |
| Top **3%** | 300 | **78%** |
| Top **5%** | 500 | **89%** |
| Top 10% | 1,000 | 97% |

> **Meaning:** we can find almost 9 in 10 defects by inspecting 1 in 20 screenings. Today, effort is spread evenly or decided by gut feeling.

### Problem 4: Defects come in predictable waves, and they're growing
- **Hot weather doubles the defect rate:** 4.2% when ambient is above 35 °C, against 1.9% otherwise.
- **Two waves a year:** late spring (heat) and autumn (tools going overdue before the December recalibration).
- **Rising:** the April–May defect rate went from **4.6% (2024) to 5.9% (2025)**. The model predicts **5.3%** for summer 2025, double the 2.7% training average.

> **Meaning:** workload, spare belts and staff can be planned months ahead instead of reacting.

### Problem 5: The supplier problem is really a tool problem
- Supplier B looks worse: 3.5% defect rate against 1.8% for Supplier A.
- **But with a calibrated tool, both suppliers are the same: 1.8% vs 1.7%.** Supplier B's belts only fail more when the tool is overdue (**25%** against 5% for Supplier A).

> **Meaning:** don't pay to switch suppliers. Fix calibration. Supplier B's belts are simply less forgiving of wrong tension, which is useful when negotiating tolerances with the supplier.

### Problem 6: No early-warning system
Each of these signals existed in the data before the defects rose, but nobody was watching them together. **The information was there; the process to act on it wasn't.**

---

## 3. The fixes and what they're worth

> **Illustrative unit costs: replace them with your company's real figures. The formulas stay the same.**
>
> | Item | Assumed cost |
> |---|---|
> | Average cost of a belt defect (replacement, labour, downtime, share of in-service failures) | **$5,000** |
> | Detailed belt inspection | **$300** |
> | One tool calibration | **$150** |
> | Re-tensioning a belt | **$100** |
>
> Volumes come from our data: about **7,300 screenings** and about **197 defects** a year.

### Fix 1: Calibrate by condition, not by calendar (the biggest win)
**Action:** trigger calibration when a tool's calibration load (days × uses ÷ 1,000) reaches **60**, well before the "overdue" level of 90, instead of waiting for a fixed date or the December reset. Pull **Tool-03 today** and **Tool-05 next**.

| | Per year |
|---|---|
| Defects avoided (excess defects above the fresh-tool rate, measured in the data) | **about 77** |
| Value at $5,000 each | **about $385,000** |
| Extra calibrations (about 40 a year at $150) | about $6,000 |
| **Net benefit** | **about $379,000** |

**Tighter option, load 45:** at 1,000 aircraft it avoids about 25 more defects a year (about $90k more net) but needs about 6× more calibrations (about 278 against 44 extra a year). Start at 60, and pilot 45 where calibration capacity allows.

**KPI:** % of screenings done with a tool above the trigger. **Target: 0%.**

### Fix 2: "First time right" tension check
**Action:** if a measured tension is more than **6% off target**, re-check and re-tension straight away with a recently calibrated tool before the aircraft is released.

| | Per year |
|---|---|
| Belts affected (11% of screenings) | about 800 |
| Cost at $100 each | about $80,000 |
| Covers | **68% of defect risk** |

The value overlaps with Fix 1 (most bad tension comes from bad tools), so we don't count it twice. Think of it as the **safety net** when a tool drifts between calibrations.
**KPI:** % of belts released within ±6% of target. **Target: >98%.**

### Fix 3: Risk-based inspection
**Action:** do the detailed inspection on the **top 5%** of screenings by model risk (the High Risk and Medium list), instead of a blanket or ad-hoc approach.

| Option | Inspections a year | Cost | Defects caught |
|---|---|---|---|
| Inspect everything in detail | 7,300 | $2,190,000 | ~100% |
| **Model top 5%** | **365** | **$110,000** | **89%** |
| Model top 3% | 220 | $66,000 | 78% |

**Saves about $2.1 million a year compared with blanket inspection**, while still catching about 9 in 10 defects. The remaining ones are still covered by routine screening and the Medium watch list.
**KPI:** defects found per 100 detailed inspections (yield). **Target:** about 50, against about 3 for random inspection.

### Fix 4: Season-ready planning
**Action:** in **March** (before the heat) and **August** (before the autumn wave):
- calibrate every tool in a sweep
- increase belt spares and line staff for the predicted defect rate
- schedule belt work into planned checks instead of unplanned AOG

**Value:** fewer expedited parts and less overtime, and a reduced risk of AOG during peak flying season, when every grounded aircraft costs the most. Spare-belt stock can be sized from the model's monthly forecast instead of guesswork.
**KPI:** unplanned belt removals in May–June and Oct–Nov. **Target:** down year on year.

### Fix 5: Smart procurement, not supplier switching
**Action:** keep both suppliers. Share the finding with Supplier B (their belts are less tolerant of tension error) and negotiate a wider tolerance, or a warranty tied to correct tensioning.
**Value:** avoids re-qualifying a new supplier (expensive and slow in aerospace), and gives a data-backed negotiating position.

### Fix 6: Immediate action this week
- **Pull Tool-03** for calibration: $150.
- **Inspect the 9 High Risk aircraft** first, then the 10 Medium: about 19 × $300 = **$5,700**.
- Against that: **40 predicted defects** linked to overdue tools in the latest period, about **$200,000** of defect cost at risk.

---

## 4. Financial summary (illustrative)

| Fix | Annual value | Annual cost | Effort |
|---|---|---|---|
| 1. Condition-based calibration | ~$385,000 | ~$6,000 | **Low:** a policy change plus a trigger |
| 2. First-time-right tension | safety net (overlaps Fix 1) | ~$80,000 | Low |
| 3. Risk-based inspection | ~$2.1M avoided vs blanket inspection | ~$110,000 | Medium: planning change |
| 4. Season-ready planning | fewer AOG, expedites, overtime | small | Low |
| 5. Smart procurement | avoids switching cost | none | Low |
| **Run cost of the system (enterprise, see section 6)** | | **about $0.7M–$1.5M a year all-in; AI tokens are only $17k–$175k of that** | |

**Bottom line:** the cheapest action, calibrating tools on time, is also the most valuable. The model told us *where* to look; the data told us *why*.

---

## 5. How the agentic AI makes this happen every day

The ML model produces risk scores, and the data holds the evidence. Findings like these are only valuable if someone acts on them **every day**. That is the agents' job: they turn model output into decisions, owners and follow-up, around the clock and across every base.

### From model output to business action

The agent team is live in the dashboard: click **✨ AI**, then **▶ Run briefing**.

| Business fix | Agent that drives it | What it does with the model's results | Who acts |
|---|---|---|---|
| **1. Condition-based calibration** | **Tool & calibration analyst** | Watches every tool's calibration age, uses and tension drift; flags overdue or drifting tools before they become a problem, with evidence (days, uses, tension error) | Tool crib / calibration |
| **2. First-time-right tension** | **Measurement analyst** | Finds belts outside the normal range, including cases where readings are bad but the model says low risk, so nothing slips through | Line maintenance |
| **3. Risk-based inspection** | **Risk analyst** | Ranks aircraft by model risk, explains each one in plain words, and builds the inspection list | Maintenance planning |
| **4. Season-ready planning** | **Trend analyst** | Compares this year with last year and spots the coming defect wave | Planning / stores |
| **All of the above** | **Lead planner** | Merges all findings, resolves conflicts, and issues **one ranked plan**: action, aircraft or tool IDs, owner, urgency (Today / This week / This month), and evidence | Maintenance manager |
| Ad-hoc questions | **Router + specialists** | "Why is B787-022 high risk?" "Which tool first?" Answered in seconds with checked numbers | Anyone |

**Getting findings to the people who act:** every specialist report has a **📤 Share** button. It emails the report (opening your own email app, with a suggested recipient such as the tool crib for the tool report), downloads a formatted **PDF**, or downloads plain text, so each finding reaches its owner in one click.

### Why agents instead of just a dashboard

| Without agents | With agents |
|---|---|
| An engineer has to open 6 tabs, read the charts and connect the dots | A **ranked action plan** arrives in a minute |
| Findings depend on who looks and when | **The same checks every time**, every day |
| Tool drift is noticed after defects appear | Drift is flagged **before** the defect wave |
| Insights stay in reliability engineering | Each action has an **owner** and an **urgency** |
| Questions wait for an analyst | **Instant answers** with evidence |

### What it costs and why it's safe
- **Unit cost (measured on our 100-aircraft fleet):** about $0.03–0.05 per full team briefing, about $0.001 per question. Section 6 scales this to the whole enterprise.
- **The facts come from the model and data, not the AI:** every number the agents write is checked against the model's output.
- **Read-only and human-approved:** agents recommend; engineers decide. Every run is logged for audit, which matters in a regulated industry.

### Next step: from advisor to co-pilot
| Stage | What the agents do | Status |
|---|---|---|
| 1. **Advisor** | Team briefing and Q&A in the AI panel, reports shared by email or PDF | **Built (live today)** |
| 2. **Watchdog** | Run automatically on every new screening; alert the tool crib when a tool crosses load 60 | Next: a scheduled run plus an email or Teams alert |
| 3. **Co-pilot** | Draft work orders in the maintenance system (for example, "calibrate Tool-03", "inspect B787-022 ENG-L") **for an engineer to approve** | Later: needs maintenance-system integration and approval workflow |
| 4. **Learning loop** | Compare predictions with actual inspection results each month; retrain the model when performance drops | Later: needs inspection outcomes fed back |

---

## 6. Running it at enterprise scale: the real cost

Our measured unit costs come from one 100-aircraft fleet. A large aerospace business runs at a very different scale, so here is the cost of running this across the whole company. **All figures are planning estimates; replace them with your own quotes.**

### The scale we planned for

| | Enterprise assumption |
|---|---|
| Aircraft | **1,000** (10 fleet groups of about 100) |
| Maintenance bases | **20**, running 3 shifts a day |
| Users (engineers, planners, tool crib, managers) | **1,500** |
| Belt screenings | about **73,000 a year** |

### AI token cost per month

| Workload | Volume per month | Standard models (gpt-6-luna specialists + gpt-6.1-terra lead) | Premium models (gpt-6.1-terra specialists + gpt-6-astra lead) |
|---|---|---|---|
| Fleet briefings, every hour, 10 fleet groups | 7,200 | $360 | $3,600 |
| Base briefings, every shift, 20 bases | 1,800 | $90 | $900 |
| Watchdog check on every new screening | about 6,100 | $3 | $30 |
| Questions (1,500 users × 15 a day × 22 days) | 495,000 | $495 | $4,950 |
| Monthly management and regulator reports | 40 | $20 | $200 |
| **Total per month** | | **about $1,000** | **about $9,700** |
| **Per year, with 50% headroom for growth and retries** | | **about $17,000** | **about $175,000** |

**Which tier?** Standard is enough for daily operations. Premium buys better reasoning for the lead planner and complex questions, and is worth it where a wrong call is expensive (fleet-level decisions, regulator reports).

### Total cost of ownership (what a big business actually pays)

| Cost item | Year 1 | Year 2 onwards | Notes |
|---|---|---|---|
| AI tokens | $17k–$175k | $17k–$175k | From the table above |
| Enterprise AI platform (Azure OpenAI or OpenAI Enterprise: data residency, zero data retention, SLAs, reserved capacity) | $50k–$250k | $50k–$250k | Needed for confidential fleet data and guaranteed uptime |
| Cloud hosting and MLOps (app servers, database, monitoring, model retraining) | $60k–$150k | $60k–$150k | Replaces the free Streamlit tier |
| Integration with the maintenance system (AMOS / TRAX / SAP) | $200k–$500k | $30k–$60k | One-off build, then upkeep |
| Security and compliance (penetration tests, ISO 27001 / SOC 2 controls, AI risk assessment, EASA / FAA documentation) | $100k–$250k | $80k–$150k | Non-negotiable in aviation |
| Team: ML engineer, data engineer, part-time reliability engineer, product owner (3–4 FTE) | $450k–$700k | $450k–$700k | The biggest cost |
| **Total** | **about $0.9M–$2.0M** | **about $0.7M–$1.5M** | |

> **Key message for management:** AI tokens are **less than 10%** of the total cost. The real cost is people, integration and compliance, as with any enterprise system. That is why the agent design (cheap model for specialists, summaries instead of raw data) matters less for the budget than getting the integration and the process change right.

### Return on investment at 1,000 aircraft

| | Per year |
|---|---|
| Fix 1 alone (condition-based calibration), 10× our fleet: about 770 defects avoided × $5,000 | **about $3.9M** |
| Fix 3 (risk-based inspection): inspection hours freed to redeploy | **thousands of technician hours** |
| Fix 4 (season-ready planning): fewer AOG events in peak season | Each avoided AOG is worth roughly **$100k+** in lost revenue, compensation and recovery (assumption) |
| **Total cost of ownership** | about $0.7M–$2.0M |
| **Payback** | **within the first year from Fix 1 alone**, about **2–5× return** in year 1 and more after |

### How we keep cost under control as it grows

| Lever | Saving |
|---|---|
| **Model routing:** cheap model for specialists, strong model only for the lead | About 85% of briefing cost is the lead, so only one call uses the expensive model |
| **Summaries, not raw data:** the ML model and Python shrink thousands of rows to a few hundred tokens | Cost doesn't grow with the number of screenings |
| **Event-driven runs:** brief when new screenings arrive, not blindly every hour | Cuts briefing volume 50–80% at quiet bases |
| **Prompt caching:** reuse the fixed instructions and tool definitions | Cached input is about 10× cheaper |
| **Batch API** for nightly and monthly reports | About 50% cheaper |
| **Answer cache:** common questions ("which tool first?") answered once per data refresh | Fewer repeated calls |
| **Budgets per base and per user**, plus a company daily cap (already built) | No surprise bills |

---

## 7. 30 / 60 / 90-day plan

| When | Do | Measure |
|---|---|---|
| **This week** | Pull Tool-03, calibrate Tool-05, inspect the 9 High Risk then the 10 Medium aircraft | High Risk aircraft cleared |
| **30 days** | Adopt the "calibrate at load 60" rule; introduce the >6% re-tension check; start the daily agent briefing | % screenings with a tool above load 60 → 0 |
| **60 days** | Switch detailed inspections to the model's risk list; set spare-belt levels from the forecast | Inspection yield; spares stock-outs |
| **90 days** | Pre-season tool sweep (August); review KPIs; feed real inspection outcomes back to retrain the model | Autumn defect rate compared with last year |

---

## 8. Honest limits
- The data is **synthetic** (case study). A real rollout needs the company's own data and a re-validation of the model.
- The money figures use **assumed unit costs**. The defect counts and rates are measured, but the dollar values must be replaced with real costs.
- The findings are **associations**, strongly supported (the same pattern repeated with three tools), but each should be confirmed with a physical tool check.
- The system is **decision support**, not a certified maintenance programme. It works alongside the approved maintenance programme and regulators' requirements.

---

## 9. One-slide summary

> **Problem:** about 4 in 10 belt defects happen because tension tools drift out of calibration; wrong tension builds the defect in, and it peaks in hot months and before the December recalibration.
>
> **Fix:** calibrate by condition (load ≤ 60), re-tension anything more than 6% off target, and inspect the model's top-5% risk list.
>
> **Value:** about 77 fewer defects a year (about $385k at an assumed $5k each) for about $6k of extra calibration, and about 89% of defects caught with 5% of the inspection effort.
>
> **How:** an ML model finds the risk; a team of AI agents turns it into a ranked action plan for every fleet and base, with owners, evidence and an audit trail.
>
> **Cost at enterprise scale (1,000 aircraft):** about $0.7M–$1.5M a year all-in (AI tokens under 10% of that), against about $3.9M a year from better calibration alone. It pays back in year 1.
