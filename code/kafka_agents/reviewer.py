"""HW8 Part 2 Reviewer: s3209_drafts (draft) -> s3209_final (status + answer)."""
from common import DRAFTS, FINAL, ask_json, log, model, now, run_agent

SYSTEM = ("You are the Reviewer for a clinical trial listings help desk. Approve the draft "
          "only if it answers the question, follows the plan and is clear. "
          'Reply only with JSON: {"approved": true or false, "notes": "one sentence"}')
llm = model()


def handle(msg: dict) -> dict:
    words = len(msg["draft"].split())
    review = ask_json(llm, SYSTEM, f"Question: {msg['question']}\nPlan: {msg['plan']}\n"
                                   f"Draft: {msg['draft']}", "notes")
    checks_ok = 30 <= words <= 180
    status = "approved" if review.get("approved") is True and checks_ok else "rejected"
    log("REVIEWER", f"REVIEW   status={status} words={words} notes={review['notes']}")
    return {"correlation_id": msg["correlation_id"], "status": status, "answer": msg["draft"],
            "review_notes": review["notes"], "question": msg["question"], "plan": msg["plan"],
            "planned_at": msg["planned_at"], "written_at": msg["written_at"],
            "reviewed_at": now()}


if __name__ == "__main__":
    run_agent("REVIEWER", DRAFTS, FINAL, handle)
