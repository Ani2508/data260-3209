# Reproducible Run Instructions — HW1

Prereqs: Python 3.12, Ollama running with qwen3:8b, `pip install langchain-core langchain-ollama`.

1. Web app (Docker):
   cd code
   docker build -t clinical-trial-app -f Dockerfile .
   docker run -d -p 8509:8509 clinical-trial-app
   Open http://localhost:8509

2. Agents (Part 2):
   cd code
   py -3.12 agents_demo.py --title "..." --content "..." --strict

3. Non-determinism (Part 3): cd code && py -3.12 run_nondeterminism.py
4. Token client (Part 4): cd code && py -3.12 hw1_client.py
5. Self-check: py -3.12 verify_hw01.py  (writes reports/hw01/verification.json)
