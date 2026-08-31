# METRICS.md — HW1 Results

## Part 2 — Agents (single run)

**Command:**
`py -3.12 agents_demo.py --title "Diabetes Drug Trial" --content "A six month randomized trial testing a new oral medication for type 2 diabetes in adults."`

- **Q1 — Final 3 tags:** type 2 diabetes treatment; randomized clinical trial; oral medication trial
- **Q2 — Final summary (<=25 words):** A six-month trial tests a new oral medication for type 2 diabetes management.
- **Q3 — Did the Reviewer change anything?** Yes. The Reviewer reworded two of the Planner's tags (e.g. "oral medication for diabetes" -> "oral medication trials"; "randomized clinical trial" -> "randomized controlled trials") and tightened the summary, though it reported no formal issues. The Finalizer settled on a blend.

---

## Part 3 — Non-determinism (40 runs)

Fixed input: `cases/nondeterminism_input.json`
("Phase II Study of Drug X in Type 2 Diabetes" + trial content)

| Metric | Temp 0.0 | Temp 0.7 |
|--------|----------|----------|
| Distinct tag sets | 3 | 14 |
| Tags in all 20 runs | oral medication, type 2 diabetes | (none) |
| Tags in exactly 1 run | (none) | 10 tags (e.g. oral antidiabetic therapy, study phase, phase ii clinical trials) |

| Latency | Temp 0.0 | Temp 0.7 |
|---------|----------|----------|
| p50 (ms) | 724,452 | 898,426 |
| p95 (ms) | 928,249 | 1,448,281 |
| p99 (ms) | 932,289 | 1,456,572 |

**Interpretation:** At temperature 0.0 the output is highly repeatable — only 3 distinct
tag sets across 20 runs, with "oral medication" and "type 2 diabetes" in every run. At
temperature 0.7 the same input produced 14 distinct tag sets and 10 tags that appeared
only once, so two users sending identical input would often see different tags. Variation
is acceptable when variety is the goal (e.g. brainstorming alternative tags); it is not
acceptable when the same input must always yield the same categorization (e.g. an
auditable or reproducible listing pipeline), where temperature 0.0 should be used.

*(Note: latencies are high because inference is CPU-only on a Surface Laptop 3; each run
is a full Planner->Reviewer->Finalizer pass.)*

---

## Part 4 — Token accounting (5-turn conversation)

Per-turn input tokens: 191 -> 282 -> 384 -> 587 -> 801 (grows as history is resent).

| Turn | Input | Output | Total |
|------|-------|--------|-------|
| 1 | 191 | 1057 | 1248 |
| 2 | 282 | 430 | 712 |
| 3 | 384 | 520 | 904 |
| 4 | 587 | 665 | 1252 |
| 5 | 801 | 588 | 1389 |

**/stats after turn 3:** turns=3, cum input=857, cum output=2007, cum total=2864, history=2721 chars
**/stats after turn 5:** turns=5, cum input=2245, cum output=3260, cum total=5505, history=4251 chars
**Session summary:** turns=5, cum input=2245, cum output=3260, cum total=5505

**AGENT.md verification:** all code-review turns returned strict bullet-only output; the
model correctly flagged the SQL-injection bug in the get_user() example.
