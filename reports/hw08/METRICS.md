# HW8 METRICS - s3209 (SID4 3209)

- SID4 3209 | PORT_BASE 8509 | PREFIX s3209 | SEED 3209 | VERIFY_SEED 263209 | DOMAIN_ID 1 (Clinical trial listings)
- Hardware: Apple MacBook Pro, Apple M5 Pro chip, 48 GB RAM, macOS
- Kafka: apache/kafka 3.8.0 (KRaft, single node) in Docker; Python client kafka-python
- Model (Part 2 agents): llama3.1:8b (Ollama, via `src/model_client.py`), temperature 0, seed 3209
- Console output with timestamps: `RUN_LOG.txt`; raw data: `raw/`; self-check: `verification.json`

## Part 1 - Trial service over Kafka

Topics: `s3209_trial_requests` (client/FastAPI -> worker), `s3209_trial_responses` (worker -> client/FastAPI).
Containers: `s3209_kafka`, `s3209_trial_worker`, `s3209_trial_api` (127.0.0.1:8509).

| Request | Result | correlation_id kept |
|---|---|---|
| CREATE_TRIAL (valid data) | success, uuid4 trial_id, "Trial created" | yes |
| GET_TRIAL (that trial_id) | success, same 6 fields | yes |
| GET_TRIAL (unknown id) | success false, "Trial not found" | yes |
| DELETE_TRIAL (unknown op) | success false, "Unknown operation" | yes |
| CREATE_TRIAL (bad email, short content) | success false, "Validation failed: ..." | yes |
| POST / GET through FastAPI (X-Correlation-ID) | success | yes |

Round trip (client log, `make hw08-demo` 14:10:56): CREATE 8 ms, GET 5 ms.

## Part 2 - Three-agent pipeline (`raw/part2_final.json`)

Topics: `s3209_inbox` (1 partition), `s3209_tasks` (2), `s3209_drafts` (1), `s3209_final` (1).
One consumer group per agent; offset committed after the outgoing message is acked.

| Stage (run 14:45:01) | Time |
|---|---|
| Planner (inbox -> tasks) | 1.73 s |
| Writer (tasks -> drafts) | 1.73 s |
| Reviewer (drafts -> final) | 0.80 s |
| Inbox to final | 4.25 s |

Final message: status `approved`, 74-word answer, correlation_id unchanged through all four topics.

## Part 3 - Failure behavior (`raw/part3_*`)

Reported runs: `make hw08-<test>-before/-after` at 15:19-15:27 (ordering at 15:12-15:13).
An earlier attempt at 15:00-15:10 is also in `RUN_LOG.txt`; it shared the `s3209_writer`
group with the Part 2 Writer that was still running, so it is not used for the results.

| Failure scenario | Before fix | After fix |
|---|---|---|
| Duplicate delivery | 2 deliveries -> 2 drafts, 2 final messages | 2nd delivery skipped (DUPLICATE) -> 1 draft, 1 final |
| Consumer killed mid-work | commit before work: committed p1=13, message at 12 -> lost, 0 drafts | commit after success: committed p1=13, message at 13 -> redelivered, 1 draft, committed 14 |
| Poison message | Writer crashed twice on p0@44; offset stayed 44; good message 0 drafts | 3 tries -> `s3209_dead_letter`; good message drafted |
| Two partitions / two consumers | no key: p0=12, p1=8; 2 of 3 trials out of order | key = trial id: one partition per trial; 3 of 3 in order |

Ordering detail (VERIFY_SEED 263209, 20 messages, 3 trials, 2 Writers in `s3209_writer`):

| Trial | Before: order processed | After: order processed |
|---|---|---|
| NCT05512874 | 2, 1, 4, 3, 6, 8, 5, 7 (p0+p1) | 1-7 (p0) |
| NCT04811023 | 1-7 (p0+p1) | 1-8 (p0) |
| NCT06120458 | 1, 3, 2, 5, 4 (p0+p1) | 1-5 (p0) |

All three trial keys hashed to p0, so WRITER-2 processed all 20 messages in the after run.

Notes:
- After `kill -9`, the restarted Writer waited about 44 s for its partitions (the dead member's
  session had to expire). In `part3_crash_after.json` the `completed` flag is false because the
  script waited 45 s for the log line; the draft count (1) and committed offset (14) show the
  message did complete.
- Poison after-fix run also cleared the poison left by the before-fix run (p0@44 -> dead letter)
  and drafted the good message behind it (p0@45).

## Verification (`verification.json`)

`make verify-hw08` on commit e5f85ee: 14 / 14 checks passed (Part 1: 6, Part 2: 3, Part 3: 5).
