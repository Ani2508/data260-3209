"""HW6 Part 4 - chat client with file-based memory (AGENT.md + MEMORY.md).

Commands: /memory  /compact  /dream  /help  /exit
Interactive:  python3 code/hw6_memory_cli.py
Scripted:     python3 code/hw6_memory_cli.py --cmd "/memory" --cmd "/compact"
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "code" / "web_application"))

import file_memory as fm  # noqa: E402
from model_client import ModelClient  # noqa: E402

RUNNER = "Ani Taraiya"
MODEL = __import__("os").environ.get("OLLAMA_MODEL", "llama3.1:8b")
BASE_PROMPT = "You are TrialMate, a concise assistant for the s3209 clinical-trial project."

HELP = """Commands
  /memory   show MEMORY.md (content lines, last consolidation, whether consolidation is due)
  /compact  consolidate MEMORY.md (merge duplicates, resolve contradictions) and compact the
            chat history into one summary message; prints before/after counts
  /dream    extract durable facts from the recent conversation and append them to MEMORY.md
  /help     show this help
  /exit     quit
Anything else is sent to the model with AGENT.md + MEMORY.md in the system prompt."""

DREAM_PROMPT = (
    "From the conversation below, list durable facts worth remembering across sessions "
    "(project settings, names, IDs, numbers, dates, decisions). Skip questions and small talk. "
    'Return JSON only: {"facts": [{"key": "<area.name, snake_case>", "value": "<short value>"}]}'
)
COMPACT_PROMPT = "Summarize this conversation in at most 5 bullets ('- ' prefix), keeping concrete facts."


class MemoryChat:
    def __init__(self, memory_path: Path, agent_path: Path):
        self.memory_path, self.agent_path = memory_path, agent_path
        self.history = []
        self.text_llm = ModelClient(model=MODEL, force_json=False, temperature=0.0, seed=3209,
                                    num_ctx=8192, num_predict=300)
        self.json_llm = ModelClient(model=MODEL, force_json=True, temperature=0.0, seed=3209,
                                    num_ctx=8192, num_predict=400)

    # -- helpers
    def files(self):
        return fm.load_memory_files(self.agent_path, self.memory_path)

    def system_prompt(self):
        return fm.build_system_prompt(self.files(), BASE_PROMPT)

    # -- commands
    def cmd_memory(self):
        text = self.files()["memory"]
        due, reasons = fm.needs_consolidation(text)
        print(text.rstrip())
        print("-" * 60)
        print(f"file: {self.memory_path.name}")
        print(f"content lines: {len(fm.content_lines(text))}  facts: {len(fm.parse_facts(text))}")
        print(f"last consolidated: {fm.read_last_consolidated(text)}")
        print(f"consolidation due: {due}  {'; '.join(reasons)}")

    def cmd_compact(self):
        text = self.files()["memory"]
        new_text, rep = fm.consolidate(text)
        self.memory_path.write_text(new_text, encoding="utf-8")
        msgs_before = len(self.history)
        if self.history:
            convo = "\n".join(f"{m['role']}: {m['content']}" for m in self.history)
            res = self.text_llm.complete([{"role": "system", "content": COMPACT_PROMPT},
                                          {"role": "user", "content": convo}])
            self.history = [{"role": "assistant", "content": "Summary of earlier conversation:\n" + res.text}]
        print("/compact report")
        print(f"  MEMORY.md content lines : {rep['lines_before']} -> {rep['lines_after']}")
        print(f"  MEMORY.md facts         : {rep['facts_before']} -> {rep['facts_after']}")
        print(f"  duplicates merged       : {rep['duplicates_merged']}")
        print(f"  contradictions resolved : {rep['contradictions_resolved']}")
        for r in rep["resolutions"]:
            print(f"    {r['key']}: kept '{r['kept']}' over '{r['dropped']}' ({r['rule']})")
        for s in rep["suspect_resolutions"]:
            print(f"  SUSPECT  {s['key']}: kept '{s['kept']}' (x{s['kept_count']}) but dropped "
                  f"'{s['dropped']}' had x{s['dropped_count']} confirmations - review manually")
        print(f"  chat messages           : {msgs_before} -> {len(self.history)}")
        return rep

    def cmd_dream(self, extra_messages=None):
        recent = (extra_messages or []) + self.history[-20:]
        if not recent:
            print("/dream: no recent conversation to learn from")
            return []
        convo = "\n".join(f"{m['role']}: {m['content']}" for m in recent)
        res = self.json_llm.complete([{"role": "system", "content": DREAM_PROMPT},
                                      {"role": "user", "content": convo}])
        try:
            facts = json.loads(res.text).get("facts", [])
        except (json.JSONDecodeError, AttributeError):
            facts = []
        text, added = fm.append_facts(self.files()["memory"], facts)
        self.memory_path.write_text(text, encoding="utf-8")
        print(f"/dream: {len(facts)} candidate facts, {len(added)} new lines added to MEMORY.md")
        for a in added:
            print("  + " + a)
        return added

    def chat(self, message):
        msgs = [{"role": "system", "content": self.system_prompt()}] + self.history + \
               [{"role": "user", "content": message}]
        res = self.text_llm.complete(msgs)
        self.history += [{"role": "user", "content": message}, {"role": "assistant", "content": res.text}]
        print(f"assistant> {res.text}")
        print(f"   [tokens in={res.input_tokens} out={res.output_tokens}]")

    def handle(self, line, echo=False):
        line = line.strip()
        if not line:
            return True
        if echo:
            print(f"you> {line}")
        if line in ("/exit", "/quit"):
            return False
        if line == "/help":
            print(HELP)
        elif line == "/memory":
            self.cmd_memory()
        elif line == "/compact":
            self.cmd_compact()
        elif line == "/dream":
            self.cmd_dream()
        elif line.startswith("/"):
            print(f"unknown command {line}; type /help")
        else:
            self.chat(line)
        return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--memory", default=str(fm.MEMORY_PATH))
    ap.add_argument("--agent", default=str(fm.AGENT_PATH))
    ap.add_argument("--cmd", action="append", help="run these lines then exit")
    args = ap.parse_args()
    mc = MemoryChat(Path(args.memory).resolve(), Path(args.agent).resolve())

    text = mc.files()["memory"]
    due, reasons = fm.needs_consolidation(text)
    print(f"File-memory chat | run by {RUNNER} | model {MODEL}")
    print(f"AGENT.md: {len(fm.content_lines(mc.files()['agent']))} lines | "
          f"MEMORY.md: {len(fm.content_lines(text))} lines | consolidation due: {due} {reasons}")
    if args.cmd:
        for line in args.cmd:
            if not mc.handle(line, echo=True):
                break
        return
    print("type /help for commands")
    while True:
        try:
            line = input("you> ")
        except (EOFError, KeyboardInterrupt):
            break
        if not mc.handle(line):
            break


if __name__ == "__main__":
    main()
