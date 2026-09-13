# AI Use Statement

## (1) What did you use an AI assistant for, and what did you do yourself?

I used an AI assistant to understand the overall flow of DATA-260 Homework 2 and to confirm whether my approach matched the assignment requirements. The assistant helped me understand concepts that were unfamiliar to me, including FastAPI endpoints, stateful LangGraph workflows, Pydantic validation, retry loops, turn ceilings, frozen-input experiments, latency measurement, and adversarial testing.

The AI assistant also helped with project setup, Windows commands, Python script organization, troubleshooting, experiment planning, and report organization.

I did not follow the AI suggestions blindly. I asked follow-up questions, compared different approaches, checked the assignment requirements, and selected solutions based on best practices. I edited and saved the files myself, ran the commands on my computer, executed the experiments, reviewed the raw outputs, captured screenshots, and verified the final results.

## (2) One AI-produced output that was wrong or unsuitable, or one thing I independently verified

The first turn-ceiling comparison script incorrectly counted a run as completed whenever it found the `Final Graph State` message. This caused the first comparison to report that all 20 runs with turn ceiling 2 were completed.

That result was unsuitable because turn ceiling 2 stopped before the Reviewer completed. The final state showed empty reviewer feedback:

`"reviewer_feedback": {}`

Therefore, the run had a Planner result but did not complete the full Planner-Reviewer workflow.

## (3) How did you detect the problem or verify the result?

I independently inspected a raw output file from the first ceiling-2 comparison:

`reports/hw02/raw/ceiling_2_run_001.txt`

The output showed that the graph stopped at turn 2 and never reached the Reviewer node. This showed that the original completion check was too weak.

I corrected the completion check so that a run was counted as complete only when the Reviewer finished successfully and returned:

`"issues": []`

I then reran the comparison using the same frozen input and model settings. The corrected results were:

- Turn ceiling 2: 0 out of 20 completed reviewed runs.
- Turn ceiling 10: 20 out of 20 completed reviewed runs.

This verification showed that the corrected comparison was more accurate than the original result.

## (4) What did you change and why does it work now?

I changed the experiment completion check to require successful Reviewer validation instead of checking only for the existence of a final graph state.

This works because a graph can stop with a Planner proposal even when the Reviewer has not run. Requiring `"issues": []` confirms that the Reviewer completed and found no problems.

I also used a frozen input file, removed the forced test environment variables during normal experiments, recorded raw console output and latency, and used separate scripts for the 30-run experiment, turn-ceiling comparison, and adversarial experiment.

The final experiments were performed using the local Ollama model:

`qwen3:4b-instruct-2507-q4_K_M`

