"""HW8 Part 3 failure tests. Each test starts its own Writer process(es) and runs once with
the fix switched off (--before) and once with it on.

  python failure_tests.py dup|crash|poison|order [--before]

Stop the Writer from Part 2 first (it is in the same consumer group).
Raw results: reports/hw08/raw/part3_<test>_<before|after>.json (+ .csv for order)
"""
import argparse
import csv
import json
import os
import random
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path

from kafka import KafkaConsumer, TopicPartition

from common import BOOTSTRAP, DRAFTS, FINAL, PREFIX, ROOT, RUN_BY, SID4, TASKS, log, now, producer
from reliable import DEAD_LETTER

VERIFY_SEED = 260000 + SID4
HERE = Path(__file__).resolve().parent
RAW = ROOT / "reports/hw08/raw"
QUESTION = "What should a patient check before joining a recruiting Phase II diabetes trial?"
PLAN = ["List the eligibility criteria", "Explain risks and visit schedule",
        "Advise talking to their doctor"]


class Writer:
    """One writer.py process; its output is shown and kept for wait_for()."""

    def __init__(self, name="WRITER", flags=(), sim=False, quiet=False):
        self.quiet = quiet  # order test: show only start-up and assignment lines
        env = {**os.environ, **({"WRITER_SIM": "1"} if sim else {})}
        self.proc = subprocess.Popen([sys.executable, "-u", "writer.py", "--name", name, *flags],
                                     cwd=HERE, env=env, text=True,
                                     stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        self.lines: list[str] = []
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self):
        in_traceback = False
        for line in self.proc.stdout:
            if line.startswith("Traceback"):
                in_traceback = True  # keep the screen short: show only the error line
                continue
            if in_traceback and line.startswith(" "):
                continue
            in_traceback = False
            if not self.quiet or any(w in line for w in ("Run by", "MODE", "ASSIGNED")):
                print("    " + line, end="", flush=True)
            self.lines.append(line)

    def wait_for(self, *words, timeout=90, start=0):
        end = time.time() + timeout
        while time.time() < end:
            for i in range(start, len(self.lines)):
                if all(w in self.lines[i] for w in words):
                    return i
            if self.proc.poll() is not None:
                time.sleep(0.5)  # let the reader thread catch the last lines
                if not any(all(w in ln for w in words) for ln in self.lines[start:]):
                    return None
            time.sleep(0.2)
        return None

    def ready(self, single=False, timeout=60):
        """Wait for the assignment: one partition (order test) or both (other tests)."""
        end = time.time() + timeout
        while time.time() < end:
            got = [ln for ln in self.lines if "ASSIGNED" in ln]
            if got and ("[0]" in got[-1] or "[1]" in got[-1] if single
                        else "[0, 1]" in got[-1]):
                return True
            time.sleep(0.3)
        if not single:
            log("TEST", "STOP     another Writer is still in group s3209_writer - "
                        "press Ctrl+C in that terminal and run again")
            self.stop()
            sys.exit(1)
        return False

    def stop(self):
        if self.proc.poll() is None:
            self.proc.terminate()
            self.proc.wait(timeout=10)


def offsets_now(topic):
    c = KafkaConsumer(bootstrap_servers=BOOTSTRAP, group_id=None)
    tps = [TopicPartition(topic, p) for p in c.partitions_for_topic(topic)]
    ends = c.end_offsets(tps)
    c.close()
    return ends


def read_since(topic, start, idle=3):
    c = KafkaConsumer(bootstrap_servers=BOOTSTRAP, group_id=None, enable_auto_commit=False,
                      consumer_timeout_ms=idle * 1000)
    c.assign(list(start))
    for tp, off in start.items():
        c.seek(tp, off)
    msgs = [json.loads(r.value) for r in c]
    c.close()
    return msgs


def committed(partition):
    c = KafkaConsumer(bootstrap_servers=BOOTSTRAP, group_id=f"{PREFIX}_writer",
                      enable_auto_commit=False)
    off = c.committed(TopicPartition(TASKS, partition))
    c.close()
    return off


_producer = None


def send(msg, key=None, partition=None, quiet=False):
    global _producer
    _producer = _producer or producer()
    meta = _producer.send(TASKS, key=key or msg["correlation_id"], value=msg,
                          partition=partition).get(timeout=10)
    if not quiet:
        log("TEST", f"SENT     to {TASKS} [p{meta.partition}@{meta.offset}] "
                    f"cid={msg['correlation_id']}")
    return meta


def task(**extra):
    return {"correlation_id": str(uuid.uuid4()), "question": QUESTION, "plan": PLAN,
            "planned_at": now(), **extra}


def save(name, data):
    RAW.mkdir(parents=True, exist_ok=True)
    (RAW / f"{name}.json").write_text(json.dumps(data, indent=2) + "\n")
    log("TEST", f"saved reports/hw08/raw/{name}.json")


# ---------------- I. duplicate delivery ----------------
def test_dup(before):
    w = Writer(flags=["--no-idempotency"] if before else [])
    w.ready()
    drafts0, finals0 = offsets_now(DRAFTS), offsets_now(FINAL)
    msg = task()
    cid = msg["correlation_id"]
    send(msg)
    i = w.wait_for("SENT", cid)
    log("TEST", f"REPLAY   same message again, same cid={cid}")
    send(msg)
    w.wait_for(cid, "SENT" if before else "DUPLICATE", start=(i or 0) + 1)
    time.sleep(8)  # give the Reviewer time to react to any extra draft
    drafts = [m for m in read_since(DRAFTS, drafts0) if m.get("correlation_id") == cid]
    finals = [m for m in read_since(FINAL, finals0) if m.get("correlation_id") == cid]
    log("TEST", f"RESULT   2 deliveries -> drafts written={len(drafts)}, "
                f"final messages={len(finals)} (expected 1 each)")
    w.stop()
    save(f"part3_dup_{'before' if before else 'after'}",
         {"cid": cid, "deliveries": 2, "drafts": len(drafts), "finals": len(finals)})


# ---------------- II. consumer death ----------------
def test_crash(before):
    flags = ["--commit-first"] if before else []
    w = Writer(flags=flags)
    w.ready()
    drafts0 = offsets_now(DRAFTS)
    msg = task()
    cid = msg["correlation_id"]
    meta = send(msg)
    w.wait_for("RECEIVED", cid)
    time.sleep(0.3)
    log("TEST", f"KILL -9  writer pid={w.proc.pid} while it is drafting cid={cid}")
    w.proc.kill()
    w.proc.wait()
    off = committed(meta.partition)
    log("TEST", f"OFFSET   committed p{meta.partition} = {off}  (message offset "
                f"{meta.offset}) -> {'already past it' if off > meta.offset else 'not past it'}")
    log("TEST", "RESTART  writer")
    w2 = Writer(flags=flags)
    done = w2.wait_for("SENT", cid, timeout=45)
    drafts = [m for m in read_since(DRAFTS, drafts0) if m.get("correlation_id") == cid]
    after = committed(meta.partition)
    outcome = "redelivered and completed" if drafts else "LOST (never redelivered)"
    log("TEST", f"RESULT   {outcome}; drafts={len(drafts)}; committed p{meta.partition} = "
                f"{after}")
    w2.stop()
    save(f"part3_crash_{'before' if before else 'after'}",
         {"cid": cid, "offset": meta.offset, "committed_after_kill": off,
          "committed_end": after, "drafts": len(drafts), "completed": done is not None})


# ---------------- III. poison message ----------------
def test_poison(before):
    flags = ["--no-dead-letter"] if before else []
    w = Writer(flags=flags)
    w.ready()
    drafts0, dead0 = offsets_now(DRAFTS), offsets_now(DEAD_LETTER)
    bad = task(plan=None)  # plan missing -> the Writer cannot build a draft
    good = task()
    log("TEST", "poison and a good message go to the same partition (p0)")
    meta = send(bad, partition=0)
    send(good, partition=0)
    if before:
        crashes = 0
        for attempt in range(2):
            w.proc.wait(timeout=90)
            crashes += 1
            log("TEST", f"CRASHED  writer exit={w.proc.returncode} (crash {crashes})")
            if attempt == 0:
                log("TEST", "RESTART  writer")
                w = Writer(flags=flags)
        log("TEST", f"OFFSET   committed p0 = {committed(0)} (poison offset {meta.offset})")
    else:
        w.wait_for("SENT", good["correlation_id"])
        w.stop()
    drafts = [m for m in read_since(DRAFTS, drafts0) if m.get("correlation_id") ==
              good["correlation_id"]]
    dead = [m for m in read_since(DEAD_LETTER, dead0) if m.get("correlation_id") ==
            bad["correlation_id"]]
    log("TEST", f"RESULT   good message drafted={len(drafts)}  "
                f"poison in {DEAD_LETTER}={len(dead)}")
    if dead:
        print(json.dumps({k: dead[0][k] for k in ("correlation_id", "error", "attempts",
                                                  "source")}, indent=2))
    save(f"part3_poison_{'before' if before else 'after'}",
         {"poison_cid": bad["correlation_id"], "good_cid": good["correlation_id"],
          "good_drafted": len(drafts), "dead_letter": len(dead)})


# ---------------- IV. ordering ----------------
def test_order(before):
    label = "before" if before else "after"
    rng = random.Random(VERIFY_SEED)
    writers = [Writer(f"WRITER-{n}", sim=True, quiet=True) for n in (1, 2)]
    for w in writers:
        w.ready(single=True)
    time.sleep(2)
    drafts0 = offsets_now(DRAFTS)
    entities = ["NCT05512874", "NCT04811023", "NCT06120458"]
    seq = dict.fromkeys(entities, 0)
    sent = []
    log("TEST", f"VERIFY_SEED={VERIFY_SEED}  20 messages  key="
                f"{'none (seeded random partition)' if before else 'entity (trial id)'}")
    for _ in range(20):
        entity = rng.choice(entities)
        seq[entity] += 1
        msg = task(entity=entity, seq=seq[entity], work_ms=rng.randint(100, 600), run=label)
        if before:
            meta = send(msg, partition=rng.choice([0, 1]), quiet=True)
        else:
            meta = send(msg, key=entity, quiet=True)
        sent.append((msg["correlation_id"], meta.partition))
    log("TEST", f"sent 20 messages to {TASKS}: p0={sum(p == 0 for _, p in sent)} "
                f"p1={sum(p == 1 for _, p in sent)}")
    cids = {c for c, _ in sent}
    end = time.time() + 90
    done = []
    while time.time() < end and len(done) < 20:
        done = [m for m in read_since(DRAFTS, drafts0, idle=2) if m["correlation_id"] in cids]
    for w in writers:
        w.stop()

    print(f"\n  order processed ({label})")
    print("   #  entity        seq  partition  writer")
    rows = []
    for n, m in enumerate(done, 1):
        rows.append({"order": n, "entity": m["entity"], "seq": m["seq"],
                     "partition": m["source_partition"], "writer": m["processed_by"]})
        print(f"  {n:>2}  {m['entity']}  {m['seq']:>3}  p{m['source_partition']}"
              f"         {m['processed_by']}")
    summary = {}
    for e in entities:
        seqs = [r["seq"] for r in rows if r["entity"] == e]
        parts = sorted({r["partition"] for r in rows if r["entity"] == e})
        ok = seqs == sorted(seqs)
        summary[e] = {"seq_order": seqs, "partitions": parts, "in_order": ok}
        log("TEST", f"{e}  partitions={parts}  order={seqs}  "
                    f"{'IN ORDER' if ok else 'OUT OF ORDER'}")
    RAW.mkdir(parents=True, exist_ok=True)
    with open(RAW / f"part3_order_{label}.csv", "w", newline="") as f:
        out = csv.DictWriter(f, fieldnames=["order", "entity", "seq", "partition", "writer"])
        out.writeheader()
        out.writerows(rows)
    save(f"part3_order_{label}", {"verify_seed": VERIFY_SEED, "processed": len(rows),
                                  "entities": summary})


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("test", choices=["dup", "crash", "poison", "order"])
    p.add_argument("--before", action="store_true", help="run with the fix switched off")
    a = p.parse_args()
    log("TEST", f"Run by: {RUN_BY} ({PREFIX})   test={a.test}   "
                f"{'BEFORE fix' if a.before else 'AFTER fix'}")
    {"dup": test_dup, "crash": test_crash, "poison": test_poison, "order": test_order}[a.test](
        a.before)
