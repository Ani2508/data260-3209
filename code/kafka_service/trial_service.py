"""HW8 Part 1 domain logic: validate and process CREATE_TRIAL / GET_TRIAL.

Pure functions (no Kafka) so the worker and the tests share the same rules.
Trials live in a plain dict inside the worker process.
"""
import re
import uuid

STATUSES = {"Recruiting", "Active - Not Recruiting", "Completed", "Terminated"}
FIELDS = ("trialTitle", "sponsor", "email", "content", "status", "terms")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$")


def validate_trial(data) -> list[str]:
    """Return a list of field errors (empty list = valid)."""
    if not isinstance(data, dict):
        return ["data must be a JSON object"]
    errors = [f"unknown field '{k}'" for k in data if k not in FIELDS]
    for key in ("trialTitle", "sponsor", "email", "content", "status"):
        value = data.get(key)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"'{key}' is required")
    if errors:
        return errors
    if not 5 <= len(data["trialTitle"].strip()) <= 200:
        errors.append("'trialTitle' must be 5-200 characters")
    if len(data["sponsor"].strip()) > 200:
        errors.append("'sponsor' must be at most 200 characters")
    if not EMAIL_RE.match(data["email"].strip()):
        errors.append("'email' must be a valid email address")
    if len(data["content"].strip()) <= 25:
        errors.append("'content' must be more than 25 characters")
    if data["status"] not in STATUSES:
        errors.append(f"'status' must be one of {sorted(STATUSES)}")
    if data.get("terms") is not True:
        errors.append("'terms' must be true")
    return errors


def handle_request(store: dict, request) -> dict:
    """Process one request message and return the response (always echoes correlation_id)."""
    cid = request.get("correlation_id") if isinstance(request, dict) else None
    op = request.get("operation") if isinstance(request, dict) else None

    def fail(error: str) -> dict:
        return {"correlation_id": cid, "operation": op, "success": False, "error": error}

    if not isinstance(cid, str) or not cid:
        return fail("Missing correlation_id")
    data = request.get("data")

    if op == "CREATE_TRIAL":
        errors = validate_trial(data)
        if errors:
            return fail("Validation failed: " + "; ".join(errors))
        trial_id = str(uuid.uuid4())
        store[trial_id] = {"trial_id": trial_id, **{k: data[k] for k in FIELDS}}
        return {"correlation_id": cid, "operation": op, "success": True,
                "trial_id": trial_id, "message": "Trial created"}

    if op == "GET_TRIAL":
        trial_id = data.get("trial_id") if isinstance(data, dict) else None
        if not isinstance(trial_id, str) or not trial_id.strip():
            return fail("'trial_id' is required")
        if trial_id not in store:
            return fail("Trial not found")
        return {"correlation_id": cid, "operation": op, "success": True,
                "trial": store[trial_id]}

    return fail("Unknown operation")
