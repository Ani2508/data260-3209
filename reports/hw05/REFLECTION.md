# Reflection — HW5 Part 5

I picked run **548a7b47** (scenario S2) from `raw/agent_runs.jsonl`: *"Find trials sponsored by Mayo Clinic, then give me the full details of the first trial in the results."* The local model was llama3.1:8b with max_steps = 6.

**Step 1.** The model asked for two tool calls at once: a search and a guessed `get_trial`. The harness logged a note and ran only the first call, `search_trials {"query": "Mayo Clinic", "limit": 10}`, through `execute_tool`. The safety rule found no patient data, the call succeeded, and the envelope listed Mayo Clinic trials, with trial 6 first.

**Steps 2–4.** The model tried to open trial 6 but used the wrong argument names: `{"id": "6"}`, then `{"nct_id": "NCT55837001"}`, then `{"id": "6"}` again. Each time `execute_tool` did not crash. It returned `{"ok": false, "error": "unknown field(s): id"}`, the harness logged the step and passed the error back as a tool message, and the turn counter went up.

**Step 5.** The error text was clear enough for the model to fix its call to `get_trial {"trial_id": 6}`. This returned `ok: true` with the full record.

**Step 6.** The model replied with plain text and no tool call: trial 6 is "Phase I Study of Drug G-6 in Asthma" (NCT55837001), Terminated, 0 open slots. That matches the database.

**Why it stopped:** normal completion (`stop_reason = final_answer`) at step 6, exactly at the max_steps ceiling. One more bad call and the harness would have stopped with `max_steps`. The run shows why the envelope matters: rejected calls became feedback instead of exceptions. It also shows that a small local model wastes steps on argument names, so tool schemas and error messages need to name the correct field.
