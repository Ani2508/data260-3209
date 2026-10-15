verify-hw01:
	python3 verify_hw01.py

run-agents:
	cd code && python3 agents_demo.py --title "Phase II Study of Drug X in Type 2 Diabetes" --content "This randomized trial enrolls adult patients with type 2 diabetes over six months to test blood glucose control with a new oral medication." --strict

run-client:
	cd code && python3 hw1_client.py

run-nondeterminism:
	cd code && python3 run_nondeterminism.py

docker-build:
	cd code && docker build -t clinical-trial-app -f Dockerfile .

docker-run:
	docker run -d -p 8509:8509 clinical-trial-app

verify-hw05:
	cd code && python3 verify_hw05.py

# ---------------- HW6 ----------------
run-api:
	cd code/web_application && python3 -m uvicorn main:app --port 8509

hw06-part1:
	python3 code/run_hw06_part1.py

hw06-part2:
	python3 code/run_hw06_part2.py

hw06-part3:
	python3 code/run_hw06_memory_cost.py

LOG6 = reports/hw06/RUN_LOG.txt
STAMP = echo "[$$(date '+%Y-%m-%d %H:%M:%S')] ======================================================================" >> $(LOG6); echo "[$$(date '+%Y-%m-%d %H:%M:%S')] RUN: $(1)   run by: Ani Taraiya" >> $(LOG6)

hw06-consolidate:
	cp reports/hw06/memory_test/MEMORY_original.md reports/hw06/memory_test/MEMORY_consolidated.md
	@$(call STAMP,make hw06-consolidate (HW6 Part 4 consolidation test))
	python3 -u code/hw6_memory_cli.py --memory reports/hw06/memory_test/MEMORY_consolidated.md \
		--cmd "/memory" \
		--cmd "Who is the site PI for our trial?" \
		--cmd "What port does the backend run on?" \
		--cmd "/compact" \
		--cmd "/memory" 2>&1 | python3 code/tslog.py $(LOG6)

hw06-dream:
	@$(call STAMP,make hw06-dream (HW6 Part 4 /help /dream /memory))
	python3 -u code/hw6_memory_cli.py --cmd "/help" \
		--cmd "Our trial NCT05512874 has 61 of 240 participants enrolled." \
		--cmd "The IRB continuing review is due on 2027-03-14 and the main site is Sacramento." \
		--cmd "/dream" --cmd "/memory" 2>&1 | python3 code/tslog.py $(LOG6)

hw06-agent-check:
	@$(call STAMP,make hw06-agent-check (HW6 Part 4 AGENT.md verification))
	python3 -u code/hw6_agent_check.py 2>&1 | python3 code/tslog.py $(LOG6)

verify-hw06:
	@$(call STAMP,make verify-hw06 (HW6 smoke test))
	python3 -u code/verify_hw06.py 2>&1 | python3 code/tslog.py $(LOG6)
