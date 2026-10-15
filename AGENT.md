# AGENT.md - Project and Agent Instructions (s3209)

## Project description
- This repository (data260-3209) is a clinical trial listing system for DATA 260, extended every homework.
- The FastAPI backend runs on PORT_BASE 8509; MySQL holds s3209_rel and MongoDB holds s3209_doc.
- The assistant (TrialMate) helps a trial coordinator; it must never invent trial IDs, dates or counts.

## Technology stack
- Python 3.12, FastAPI, Pydantic v2, SQLAlchemy (MySQL) and PyMongo (MongoDB).
- Every model call goes through `complete()` / `ModelClient` in `src/model_client.py` (local Ollama).

## Coding conventions
- Functions use snake_case names, full type hints on every parameter and the return value.
- Every function has a one-line docstring that states what it returns.
- Library code does not use `print()`; it returns values or raises `ValueError` with a clear message.
- Validate inputs at the top of a function and fail fast on bad input.
- Use only the Python standard library unless a dependency is already in `requirements.txt`.

## Testing approach
- Each new function ships with at least three plain `assert` tests, including one edge case.
- Tests must run offline: no network, no database and no model calls.
- Smoke checks for a homework live in `code/verify_hwNN.py` and write `reports/hwNN/verification.json`.

## Prohibited actions
- Never hard-code passwords, API keys or connection secrets; read them from `.env`.
- Never call Ollama or another model API directly; use the adapter in `src/model_client.py`.
- Never delete or overwrite database records or memory files without an explicit user command.
- Never store patient identifiers (names, MRNs, dates of birth) in memory or logs.

## Code review mode
- When asked to review code, respond only in bullet points, each starting with "- ".
- One specific observation per bullet: correctness, readability, error handling, security.
- No intro, closing sentence, headings or code fences in a review.
