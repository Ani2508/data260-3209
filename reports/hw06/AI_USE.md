# HW6 AI_USE - s3209

## 1. What I used an AI assistant for, and what I did myself

I used an AI assistant to learn and understand the concepts in this homework: the MongoDB document API,
the memory chat logic (short-term window, summaries, episodic facts), the Part 3 experiment and scoring,
the file-based memory commands, and the verification script. It also helped write the code for these
parts and helped arrange the report layout and check grammar.

I did the setup and running myself. I installed MongoDB and Compass on my Mac, ran the backend, Ollama
and every experiment and command on my machine, took all the screenshots, checked the outputs against
the requirements and decided what to change when results looked wrong.

## 2. One AI-produced output that was wrong

The first version of the episodic memory extraction stored facts the user never said. In my Part 2
run, the episodes collection held 20 facts, including "You requested a JSON output", "You asked me to
summarize your trial", and general advice the model made up, such as "Submit report within 24 hours of
occurrence". These are not user facts and they pushed the real facts out of the top-3 retrieval.

## 3. How I detected the problem

I read the JSON from GET /api/memory/ani_demo and the episodes collection in Compass after the
12-message run. Many facts did not match anything I typed, and the facts retrieved for the warfarin
and IRB messages were screening-visit advice instead of the details I had just given.

## 4. What I changed and why it works now

The extraction prompt now asks only for facts the user states, copied exactly, with one positive
and one negative example. Messages that end with "?" are skipped, and facts starting with "You asked" /
"The user mentioned" are filtered out. Embeddings use separate query and document prefixes for
nomic-embed-text. After rerunning Part 2, the session stored 9 facts, all taken from my messages
(trial ID, phase, drug, 240 target, 61 enrolled, Sacramento, Dr. Helen Okafor, warfarin/INR, IRB date),
and the site/PI question retrieved the correct two facts.
