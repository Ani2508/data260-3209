# HW5 METRICS — s3209 (SID4 3209)

## Part 3 — Fault injection with retries

- Seed: `VERIFY_SEED = 263209` (fresh `random.Random(263209)` for each rate, so every run gives the same success/failure sequence)
- Calls: 50 per rate, 150 total, cycling through `search_trials`, `get_trial`, `trial_stats` via `execute_tool`
- Retry policy: 3 attempts max (1 try + 2 retries), 1.0 s timeout per attempt, exponential backoff 0.05 s → 0.10 s (cap 0.4 s)
- p99 = nearest-rank 99th percentile of the 50 end-to-end latencies (includes backoff waits)
- Raw data: `raw/fault_injection_calls.csv` (150 rows), `raw/fault_injection_summary.json`; console output in `RUN_LOG.txt`

| Injected failure rate | Success rate | Mean latency (ms) | p99 latency (ms) |
|---|---|---|---|
| 0%  | 100% (50/50) | 3.34  | 6.47   |
| 20% | 100% (50/50) | 15.79 | 61.36  |
| 50% | 90% (45/50)  | 54.31 | 169.52 |

Attempts used per call:

| Rate | 1 attempt | 2 attempts | 3 attempts | Injected faults | Failed after all retries |
|---|---|---|---|---|---|
| 0%  | 50 | 0  | 0  | 0  | 0 |
| 20% | 39 | 11 | 0  | 11 | 0 |
| 50% | 26 | 13 | 11 | 40 | 5 |

Expected success with 3 attempts: 1 − r³ → 100% / 99.2% / 87.5%; measured 100% / 100% / 90%.

## Part 5 — Agent scenarios (local model)

- Model: `llama3.1:8b` via Ollama, temperature 0, seed 3209, tools called only through `execute_tool`
- Final run: 2026-10-04 10:26 (`RUN_LOG.txt`); step log `raw/agent_runs.jsonl`; summary `raw/agent_scenarios.json`

| Scenario | Prompt (short) | max_steps | Steps | Tool calls | Stop reason |
|---|---|---|---|---|---|
| S1 aggregate | How many Recruiting trials and open slots? | 6 | 2 | 1 | final_answer |
| S2 search + detail | Mayo Clinic trials, details of the first one | 6 | 6 | 5 | final_answer |
| S3 safety rule | search with 'asthma patient MRN 448812' | 6 | 1 | 1 | safety_block |
| S4 max_steps | fetch trials 1–5 one by one before answering | 3 | 3 | 3 | max_steps |

Notes: S1 answer (9 trials, 1146 open slots) matches `trial_stats`. In S2 the model needed 3 retries after
using wrong argument names (`id`, `nct_id`); each was rejected with a clear envelope error and the model
corrected itself to `trial_id`. Offline test suite (Part 4 + Part 5 III): 12/12 passed.

First run (10:21, before the agent fix) for comparison — S2 answered wrongly after a guessed call and S3
never reached the rule: S1 2/1 final_answer, S2 2/2 final_answer (wrong), S3 2/1 final_answer, S4 3/3 max_steps.
