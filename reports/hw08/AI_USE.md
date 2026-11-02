# HW8 AI_USE - s3209

## 1. What I used an AI assistant for, and what I did myself

I used an AI assistant to understand the concepts in this homework (request/response over Kafka
with a correlation_id, consumer groups and partitions, when to commit offsets, idempotency,
dead-letter topics and message keys) and to help me write the code for each part, the
failure-test and verification scripts and the report layout. I did not trust it blindly: I asked
questions until I understood each concept and what each script was doing.

I did the setup and running myself. I ran the Docker stack (Kafka, worker, FastAPI), Ollama, the
three agents in separate terminals, and every demo, failure test and verification run on my Mac.
I took the screenshots and checked each output against the assignment before it went into the
report.

## 2. One AI-produced output that was wrong

The first version of the Part 3 failure tests assumed the test's Writer was the only member of
the `s3209_writer` consumer group. The Part 2 Writer was still running in another terminal, so
the two Writers split the `s3209_tasks` partitions. The duplicate "after fix" run crashed with
`TypeError: unsupported operand type(s) for +: 'NoneType' and 'int'` because the message went
to the other Writer, and the duplicate, crash and poison runs mixed output from both Writers.

## 3. How I detected the problem

In `RUN_LOG.txt` the test Writer logged `ASSIGNED partitions=[1]` instead of `[0, 1]`, and
there were `WRITER` lines without the test's indent, which meant a second Writer was consuming.
The poison "before fix" run also printed a traceback from the old Part 2 code path.

## 4. What I changed and why it works now

The test now checks that its Writer owns both partitions before sending anything, and stops
with a clear message if another Writer is in the group. The `None` case in the wait was fixed.
I stopped the Part 2 Writer and re-ran the six tests (15:19-15:27): every run logged
`ASSIGNED partitions=[0, 1]`, the results match the expected before/after behaviour, and
`make verify-hw08` passed 14 / 14 checks.
