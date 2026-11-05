"""HW8 Part 2 Planner: s3209_inbox (question) -> s3209_tasks (plan)."""
from common import INBOX, TASKS, ask_json, log, model, now, run_agent

SYSTEM = ("You are the Planner for a clinical trial listings help desk. Break the user's "
          "question into exactly 3 short steps a writer should follow to answer it. "
          'Reply only with JSON: {"plan": ["step 1", "step 2", "step 3"]}')
llm = model()


def handle(msg: dict) -> dict:
    facts = msg.get("facts", "")  # HW9: trial records from s3209_rel (may be empty)
    user = msg["question"] + (f"\nTrial records:\n{facts}" if facts else "")
    plan = ask_json(llm, SYSTEM, user, "plan")["plan"][:3]
    log("PLANNER", f"PLAN     {plan}")
    return {"correlation_id": msg["correlation_id"], "question": msg["question"],
            "facts": facts, "plan": plan, "planned_at": now()}


if __name__ == "__main__":
    run_agent("PLANNER", INBOX, TASKS, handle)
