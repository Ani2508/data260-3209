# data260-3209 — DATA 260 (shared semester repository)

**Student:** Ani Taraiya  |  **SID4:** 3209  |  **Domain (DOMAIN_ID 1):** Clinical trial listings

**Collaborators added:** Sbnikitha, supriyaselvanganesan

## Personal configuration

| Value | Result |
|-------|--------|
| SID4 | 3209 |
| PORT_BASE | 8509 |
| PREFIX | s3209 |
| SEED | 3209 |
| VERIFY_SEED | 263209 |
| DOMAIN_ID | 1 (Clinical trial listings) |

**Hardware:** Microsoft Surface Laptop 3 — AMD Ryzen 5 (4 cores), 16 GB RAM,
integrated AMD Radeon (no GPU). Windows 11 Home 64-bit.
**Local model:** qwen3:8b via Ollama 0.33.0, CPU-only, 4096-token context.

## Repository layout (shared across the semester)

```
data260-3209/
├── code/                      # shared application code (extended each homework)
│   ├── web_application/        # Part 1 web app (HTML/JS/CSS + nginx.conf)
│   ├── agents_demo.py          # Part 2 agents
│   ├── hw1_client.py           # Part 4 token client
│   ├── run_nondeterminism.py   # Part 3 experiment
│   └── Dockerfile
├── src/
│   └── model_client.py         # shared model adapter (all calls go through this)
├── reports/
│   └── hw01/                   # HW1 deliverables
│       ├── raw/                # nondeterminism_runs.csv, token_counts.json
│       ├── cases/nondeterminism_input.json
│       ├── RUN_LOG.txt
│       ├── METRICS.md
│       ├── AI_USE.md
│       ├── report.pdf
│       └── verification.json
├── AGENT.md
├── DOMAIN_SCHEMA.md
├── verify_hw01.py
└── README.md
```

## How to run (Python 3.12; Ollama running with qwen3:8b)

Install deps: `pip install langchain-core langchain-ollama`

**Part 1 — web app (Docker):**
```
cd code
docker build -t clinical-trial-app -f Dockerfile .
docker run -d -p 8509:8509 clinical-trial-app
# open http://localhost:8509
```

**Part 2 — agents:**
```
cd code
py -3.12 agents_demo.py --title "Phase II Study of Drug X in Type 2 Diabetes" --content "This randomized trial enrolls adult patients with type 2 diabetes over six months to test blood glucose control with a new oral medication." --strict
```

**Part 3 — non-determinism (40 runs):**
```
cd code
py -3.12 run_nondeterminism.py
```

**Part 4 — token client:**
```
cd code
py -3.12 hw1_client.py
```

**Self-check:**
```
py -3.12 verify_hw01.py
```

## Notes
- All model calls route through `src/model_client.py` (`complete(messages, tools=None)`).
- qwen3:8b runs CPU-only here, so inference is slow; reasoning is disabled via `/no_think`.
