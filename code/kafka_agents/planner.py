"""HW8 Part 2 Planner: s3209_inbox (question) -> s3209_tasks (plan)."""
from common import INBOX, TASKS, ask_json, log, model, now, run_agent

SYSTEM = ("You are the Planner for a clinical trial listings help desk. Break the user's "
          "question into exactly 3 short steps a writer should follow to answer it. "
          'Reply only with JSON: {"plan": ["step 1", "step 2", "step 3"]}')
llm = model()


def handle(msg: dict) -> dict:
    plan = ask_json(llm, SYSTEM, msg["question"], "plan")["plan"][:3]
    log("PLANNER", f"PLAN     {plan}")
    return {"correlation_id": msg["correlation_id"], "question": msg["question"],
            "plan": plan, "planned_at": now()}


if __name__ == "__main__":
    run_agent("PLANNER", INBOX, TASKS, handle)
