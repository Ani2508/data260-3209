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

# ---------------- HW7 ----------------
LOG7 = reports/hw07/RUN_LOG.txt
STAMP7 = mkdir -p reports/hw07/raw; echo "[$$(date '+%Y-%m-%d %H:%M:%S')] ======================================================================" >> $(LOG7); echo "[$$(date '+%Y-%m-%d %H:%M:%S')] RUN: $(1)   run by: Ani Taraiya" >> $(LOG7)

hw07-migrate:
	@$(call STAMP7,make hw07-migrate (HW7 Part 1 users table + role users))
	cd code/web_application && python3 -u migrate_hw07.py 2>&1 | python3 ../tslog.py ../../$(LOG7)

hw07-part1:
	@$(call STAMP7,make hw07-part1 S=$(S) (HW7 Part 1 JWT + RBAC demo))
	bash code/hw07_part1_demo.sh $(S) 2>&1 | python3 code/tslog.py $(LOG7)

hw07-part2-test:
	@$(call STAMP7,make hw07-part2-test (HW7 Part 2 offline tests))
	cd code/mcp_servers && python3 -u test_agent_loop.py 2>&1 | python3 ../tslog.py ../../$(LOG7)

hw07-part2:
	@$(call STAMP7,make hw07-part2 T=$(T) (HW7 Part 2 tasks A B C + nonexistent id))
	python3 -u code/run_hw07_part2.py demo $(if $(T),--task $(T)) 2>&1 | python3 code/tslog.py $(LOG7)

hw07-part2-rel:
	@$(call STAMP7,make hw07-part2-rel (HW7 Part 2 reliability, 21 attempts))
	python3 -u code/run_hw07_part2.py reliability -n 21 2>&1 | python3 code/tslog.py $(LOG7)

hw07-part3-test:
	@$(call STAMP7,make hw07-part3-test (HW7 Part 3 offline tests))
	cd code/mcp_servers && python3 -u test_reflexion.py 2>&1 | python3 ../tslog.py ../../$(LOG7)

hw07-part3:
	@$(call STAMP7,make hw07-part3 (HW7 Part 3 original vs Reflexion))
	python3 -u code/run_hw07_part3.py compare -n 5 2>&1 | python3 code/tslog.py $(LOG7)

hw07-part3-show:
	@$(call STAMP7,make hw07-part3-show (HW7 Part 3 stored reflection))
	python3 -u code/run_hw07_part3.py show 2>&1 | python3 code/tslog.py $(LOG7)

hw07-part4-data:
	@$(call STAMP7,make hw07-part4-data (HW7 Part 4 scenario CSVs from Citi Bike data))
	cd code && python3 -u -m bikeshare.prepare_scenarios 2>&1 | python3 tslog.py ../$(LOG7)

hw07-part4:
	@$(call STAMP7,make hw07-part4 S=$(S) (HW7 Part 4 bike-share agent))
	python3 -u code/run_hw07_part4.py $(S) 2>&1 | python3 code/tslog.py $(LOG7)
