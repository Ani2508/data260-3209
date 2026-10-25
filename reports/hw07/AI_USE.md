# HW7 AI_USE - s3209

## 1. What I used an AI assistant for, and what I did myself

I used an AI assistant to understand the concepts in this homework (JWT and role checks, the agent
loop and repair path, Reflexion, the ReAct/MRKL tools, prompt injection and the bash safety gate)
and to help write the code for each part, the verification script and the report layout.

I did the setup and running myself. I ran the MySQL migration, the backend, Ollama and every demo,
experiment and commit on my Mac, ran both bike-share scenarios through the UI, reviewed every output
and screenshot against the assignment, and decided what to change when results looked wrong.

## 2. One AI-produced output that was wrong

The first version of the Part 4 bike-share agent gave a wrong pay-per-use total for scenario A. The
SQL it was told to write charged each ride $4.99 plus the classic-bike overage, but left out the
e-bike per-minute price ($0.41/min). Almost half of the scenario A rides are e-bike rides
(3,498.9 e-bike minutes), so the total was about $1,434.55 too low, and the model still reported it
as the final answer with citations. Earlier versions also quoted prices from the wrong pricing-page
passage and cited passages that were never retrieved.

## 3. How I detected the problem

I checked the agent's numbers against a separate calculation over the same CSV and the prices on the
saved pricing-page snapshot: 520 x $4.99 + 396.5 classic minutes over 30 x $0.41 + 3,498.9 e-bike
minutes x $0.41 = $4,191.92. The agent's total was lower than this by the e-bike charge.

## 4. What I changed and why it works now

The cost formula is now one fixed SQL template (single ride + classic overage + e-bike minutes) used
for both the total and the weekly table, and the final answer goes through a validated schema. The
answer is sent back to the model if the weekly spend does not add up to the pay-per-use total, the
membership total is not fees + residual, the fees do not equal riders x months x $19.92, the
break-even is not monthly price / single-ride price, the decision contradicts the totals, or a cited
passage id was never retrieved. Retrieval returns at least 3 passages with ids. After these changes
scenario A gives $4,191.92 vs $1,155.77 (Buy Monthly Membership) and scenario B $2,594.80 vs
$5,179.20 (Pay Per Ride/Minute), both matching my own calculation, and `make verify-hw07` replays the
recorded scenario B run through the same answer check (16/16 checks passed).
