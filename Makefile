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

hw06-consolidate:
	cp reports/hw06/memory_test/MEMORY_original.md reports/hw06/memory_test/MEMORY_consolidated.md
	python3 code/hw6_memory_cli.py --memory reports/hw06/memory_test/MEMORY_consolidated.md \
		--cmd "/memory" \
		--cmd "Who is the site PI for our trial?" \
		--cmd "What port does the backend run on?" \
		--cmd "/compact" \
		--cmd "/memory"

hw06-dream:
	python3 code/hw6_memory_cli.py --cmd "/help" \
		--cmd "Our trial NCT05512874 has 61 of 240 participants enrolled." \
		--cmd "The IRB continuing review is due on 2027-03-14 and the main site is Sacramento." \
		--cmd "/dream" --cmd "/memory"

hw06-agent-check:
	python3 code/hw6_agent_check.py

verify-hw06:
	python3 code/verify_hw06.py
