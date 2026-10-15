# HW6 METRICS - s3209 (SID4 3209)

- Hardware: Apple MacBook Pro, Apple M5 Pro chip, 48 GB RAM, macOS
- Model: llama3.1:8b (Ollama, temperature 0, seed 3209); embeddings nomic-embed-text (768 dims)
- Backend: FastAPI on PORT_BASE 8509, MongoDB database s3209_doc
- Console output with timestamps: `RUN_LOG.txt`; raw data: `raw/`

## Part 1 - MongoDB document API (`raw/part1_crud.json`)

| Operation | Endpoint | Status |
|---|---|---|
| Create | POST /api/doc/trials | 201 |
| Retrieve all | GET /api/doc/trials | 200 |
| Get one | GET /api/doc/trials/{id} | 200 |
| Update | PUT /api/doc/trials/{id} | 200 |
| Delete | DELETE /api/doc/trials/{id} | 204 |
| Deleted / unknown id | GET /api/doc/trials/{id} | 404 |
| Invalid id format | GET /api/doc/trials/not-an-id | 400 |
| Missing title / bad enum / bad date / title > 100 chars | POST /api/doc/trials | 422 (x4) |

## Part 2 - Memory chat (`raw/part2_*.json`)

| Item | Result |
|---|---|
| Messages in session ani-demo-s1 | 12 scripted + 2 from chat page |
| Short-term window | grows 0, 2, 4 ... then fixed at 12 (SHORT_TERM_N) |
| Session summaries | created at user messages 5 and 10 |
| Lifetime summary | created at message 10 (session_id null) |
| Episodic facts stored | 9 (from 12 messages; questions add none) |
| Recall check | "Which site and PI did I mention earlier?" -> Sacramento, Dr. Helen Okafor |

## Part 3 - What memory costs

Same 30-message conversation (`cases/conversation_30.yaml`) in a fresh session per setting, then 5 probes
(`memory_probes.yaml`). Raw data: `raw/part3_turns.csv`, `raw/part3_probe_scores.json`, `raw/part3_summary.json`,
`raw/chat_requests.jsonl`.

| Setting | Mean prompt tokens/turn | Mean latency (ms) | Probe quality (1-5) |
|---|---|---|---|
| SHORT_TERM_N=4 | 484.4 | 2256.1 | 5.00 |
| SHORT_TERM_N=12 | 628.7 | 2106.6 | 5.00 |
| SHORT_TERM_N=30 | 941.3 | 2266.9 | 5.00 |
| Compression policy (N=30 + compress) | 740.2 | 1988.5 | 5.00 |

Mean prompt tokens by section (per turn):

| Setting | Short-term | Long-term | Episodic | Model latency (ms) |
|---|---|---|---|---|
| SHORT_TERM_N=4 | 118.4 | 285.0 | 47.6 | 877.8 |
| SHORT_TERM_N=12 | 328.2 | 211.8 | 47.6 | 996.0 |
| SHORT_TERM_N=30 | 612.4 | 249.2 | 47.6 | 1136.4 |
| Compression policy | 394.5 | 219.0 | 47.6 | 901.9 |

Compression policy vs N=30 baseline (`raw/part3_compression_comparison.json`):

| Metric | N=30 | N=30 + compress | Change |
|---|---|---|---|
| Mean prompt tokens/turn | 941.3 | 740.2 | -21.4% |
| Short-term tokens/turn | 612.4 | 394.5 | -35.6% |
| Probe quality | 5.00 | 5.00 | no change |
| Mean latency (ms) | 2266.9 | 1988.5 | -12.3% |

Cost of 10,000 x 30-turn conversations ($1/M input, $5/M output):

| Setting | Input tokens / conv. | Output tokens / conv. | Reply only | All calls |
|---|---|---|---|---|
| SHORT_TERM_N=4 (best) | 21,223 | 2,982 | $199.68 | $361.33 |
| SHORT_TERM_N=12 | 24,751 | 2,586 | $241.41 | $376.81 |
| SHORT_TERM_N=30 (worst) | 34,346 | 2,497 | $328.69 | $468.31 |
| Compression policy | 27,783 | 2,182 | $258.67 | $386.93 |

Best = cheapest setting at the top probe quality (all tied at 5.00); worst = most expensive with no recall gain.

## Part 4 - File-based memory

| Item | Result |
|---|---|
| AGENT.md | 20 instructions in 6 sections (5 required categories covered) |
| MEMORY_original.md | 55 lines, 50 facts |
| After /compact | 52 -> 34 content lines (38 lines total), 50 -> 26 facts |
| Duplicates merged | 19 |
| Contradictions resolved | 5 (all listed in the file) |
| Resolved incorrectly | 1 - site.pi kept typo "Okafur" over "Okafor" (x3); flagged SUSPECT |
| /dream | 5 facts extracted, 5 lines added to MEMORY.md |
| AGENT.md check (generated function) | attempt 1: 7/10 rules, attempt 2 after feedback: 6/10 |

## Verification

`make verify-hw06` -> `verification.json`: 12/12 checks passed.
