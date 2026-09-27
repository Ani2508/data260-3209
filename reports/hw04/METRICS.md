# HW4 Metrics

## Section 0 — Personal Configuration

| Value | Result |
|---|---|
| SID4 | 3209 |
| PORT_BASE | 8509 |
| PREFIX | s3209 |
| SEED | 3209 |
| VERIFY_SEED | 263209 |
| DOMAIN_ID | 1 (Clinical Trial Listings) |

## Part 3 — N+1 Measurement Results

| Page size | Version | SQL stmts/req | p50 (ms) | p95 (ms) | p99 (ms) |
|---|---|---|---|---|---|
| 10 | naive | 13 | 22.30 | 31.21 | 37.71 |
| 10 | fixed | 4 | 35.07 | 62.96 | 71.54 |
| 50 | naive | 53 | 62.69 | 67.80 | 70.82 |
| 50 | fixed | 4 | 32.53 | 53.07 | 78.00 |
| 200 | naive | 203 | 524.23 | 1060.91 | 1293.84 |
| 200 | fixed | 4 | 43.26 | 51.34 | 97.81 |

## Speed-up (naive p50 / fixed p50)

| Page size | Speed-up |
|---|---|
| 10 | 0.64x (fixed slower) |
| 50 | 1.93x faster |
| 200 | 12.12x faster |

## Part 3 — Index (EXPLAIN before/after)

Before adding an index on `trials.sponsor`:
- type: ALL, key: NULL, rows: 4980 (full table scan)

After adding `idx_trials_sponsor`:
- type: ref, key: idx_trials_sponsor, rows: 631 (index lookup)

## Part 4 — RAG Evaluation Summary

| Config | Accuracy | Faithfulness | Format Compliance | Robustness (Q5/Q6) |
|---|---|---|---|---|
| A - No-RAG | 4/6 correct (2 hallucinated) | 0/6 grounded | N/A | 0/2 refused |
| B - Basic-RAG | 5/6 correct | 5/6 grounded | No citations used | 1/2 refused |
| C - Context-RAG | 6/6 correct | 6/6 grounded | 6/6 followed format | 2/2 refused |

Full per-question evaluation table: see `reports/hw04/raw/rag_evaluation_table.csv`
