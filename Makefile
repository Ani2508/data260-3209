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

hw07-part5:
	@$(call STAMP7,make hw07-part5 (HW7 Part 5 prompt-injection attacks before/after defenses))
	python3 -u code/run_hw07_part5.py 2>&1 | python3 code/tslog.py $(LOG7)

hw07-part6:
	@$(call STAMP7,make hw07-part6 (HW7 Part 6 file tools + safety gate))
	cd code && python3 -u -m devtools.test_devtools 2>&1 | python3 tslog.py ../$(LOG7)
	python3 -u code/run_hw07_part6.py 2>&1 | python3 code/tslog.py $(LOG7)

verify-hw07:
	@$(call STAMP7,make verify-hw07 (HW7 smoke test))
	python3 -u code/verify_hw07.py 2>&1 | python3 code/tslog.py $(LOG7)

# ---------------- HW8 ----------------
LOG8 = reports/hw08/RUN_LOG.txt
COMPOSE8 = docker compose -f code/kafka_service/docker-compose.yml
STAMP8 = mkdir -p reports/hw08/raw; echo "[$$(date '+%Y-%m-%d %H:%M:%S')] ======================================================================" >> $(LOG8); echo "[$$(date '+%Y-%m-%d %H:%M:%S')] RUN: $(1)   run by: Ani Taraiya" >> $(LOG8)

hw08-up:
	$(COMPOSE8) up -d --build

hw08-down:
	$(COMPOSE8) down

hw08-ps:
	@$(call STAMP8,make hw08-ps (HW8 Part 1 containers))
	@(echo "Run by: Ani Taraiya (s3209)   $$(date '+%Y-%m-%d %H:%M:%S')"; \
	  docker ps --filter name=s3209_ --format "table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}") 2>&1 | python3 code/tslog.py $(LOG8)

hw08-logs:
	@$(call STAMP8,make hw08-logs (HW8 Part 1 worker and API startup logs))
	@for i in $$(seq 30); do docker logs s3209_trial_worker 2>&1 | grep -q "Consumer is ready" && break; sleep 1; done
	@(echo "Run by: Ani Taraiya (s3209)"; echo "---- docker logs s3209_trial_worker ----"; \
	  docker logs s3209_trial_worker 2>&1 | grep -E "Run by|Consumer is ready"; \
	  echo "---- docker logs s3209_trial_api ----"; \
	  docker logs s3209_trial_api 2>&1 | grep -E "Run by|Server started|Uvicorn running") 2>&1 | python3 code/tslog.py $(LOG8)

hw08-demo:
	@$(call STAMP8,make hw08-demo (HW8 Part 1 CREATE_TRIAL -> GET_TRIAL over Kafka))
	python3 -u code/homework_demo.py 2>&1 | python3 code/tslog.py $(LOG8)

hw08-errors:
	@$(call STAMP8,make hw08-errors (HW8 Part 1 error responses over Kafka))
	python3 -u code/homework_demo.py --errors 2>&1 | python3 code/tslog.py $(LOG8)

hw08-api:
	@$(call STAMP8,make hw08-api (HW8 Part 1 FastAPI wrapper over Kafka))
	@bash code/kafka_service/api_demo.sh 2>&1 | python3 code/tslog.py $(LOG8)

# HW8 Part 2: four topics created with the Kafka CLI, then one agent per terminal
KT = docker exec s3209_kafka /opt/kafka/bin/kafka-topics.sh --bootstrap-server localhost:9092

hw08-topics:
	@$(call STAMP8,make hw08-topics (HW8 Part 2 create s3209_inbox/tasks/drafts/final))
	@(echo "Run by: Ani Taraiya (s3209)"; \
	  for tp in inbox:1 tasks:2 drafts:1 final:1; do t=s3209_$${tp%%:*}; n=$${tp##*:}; \
	    echo "$$ kafka-topics.sh --create --if-not-exists --topic $$t --partitions $$n --replication-factor 1"; \
	    $(KT) --create --if-not-exists --topic $$t --partitions $$n --replication-factor 1 2>&1 | grep -v "WARNING: Due to"; \
	  done; echo; echo "$$ kafka-topics.sh --describe"; \
	  for t in inbox tasks drafts final; do \
	    $(KT) --describe --topic s3209_$$t | grep PartitionCount | awk '{print $$1, $$2, $$5, $$6, $$7, $$8}'; done) 2>&1 | python3 code/tslog.py $(LOG8)

hw08-topics-delete:
	@for t in inbox tasks drafts final; do $(KT) --delete --if-exists --topic s3209_$$t; done; echo "deleted s3209_inbox/tasks/drafts/final"

hw08-planner:
	@$(call STAMP8,make hw08-planner (HW8 Part 2 Planner))
	cd code/kafka_agents && python3 -u planner.py 2>&1 | python3 ../tslog.py ../../$(LOG8)

hw08-writer:
	@$(call STAMP8,make hw08-writer (HW8 Part 2 Writer))
	cd code/kafka_agents && python3 -u writer.py 2>&1 | python3 ../tslog.py ../../$(LOG8)

hw08-reviewer:
	@$(call STAMP8,make hw08-reviewer (HW8 Part 2 Reviewer))
	cd code/kafka_agents && python3 -u reviewer.py 2>&1 | python3 ../tslog.py ../../$(LOG8)

hw08-ask:
	@$(call STAMP8,make hw08-ask (HW8 Part 2 send one question))
	cd code/kafka_agents && python3 -u send_question.py 2>&1 | python3 ../tslog.py ../../$(LOG8)

# HW8 Part 3: failure tests (stop the Part 2 Writer first; each test starts its own Writer)
hw08-topic-dlq:
	@$(call STAMP8,make hw08-topic-dlq (HW8 Part 3 create s3209_dead_letter))
	@(echo "Run by: Ani Taraiya (s3209)"; \
	  echo "$$ kafka-topics.sh --create --if-not-exists --topic s3209_dead_letter --partitions 1 --replication-factor 1"; \
	  $(KT) --create --if-not-exists --topic s3209_dead_letter --partitions 1 --replication-factor 1 2>&1 | grep -v "WARNING: Due to"; \
	  $(KT) --describe --topic s3209_dead_letter | grep PartitionCount | awk '{print $$1, $$2, $$5, $$6, $$7, $$8}') 2>&1 | python3 code/tslog.py $(LOG8)

P3_TESTS = dup crash poison order
$(foreach t,$(P3_TESTS),hw08-$(t)-before) $(foreach t,$(P3_TESTS),hw08-$(t)-after):
	@$(call STAMP8,make $@ (HW8 Part 3 $(word 2,$(subst -, ,$@)) $(word 3,$(subst -, ,$@)) fix))
	cd code/kafka_agents && python3 -u failure_tests.py $(word 2,$(subst -, ,$@)) $(if $(filter before,$(word 3,$(subst -, ,$@))),--before) 2>&1 | python3 ../tslog.py ../../$(LOG8)

verify-hw08:
	@$(call STAMP8,make verify-hw08 (HW8 smoke test))
	python3 -u code/verify_hw08.py 2>&1 | python3 code/tslog.py $(LOG8)

# ---------------- HW9 ----------------
LOG9 = reports/hw09/RUN_LOG.txt
COMPOSE9 = docker compose -f code/cache/docker-compose.yml
STAMP9 = mkdir -p reports/hw09/raw; echo "[$$(date '+%Y-%m-%d %H:%M:%S')] ======================================================================" >> $(LOG9); echo "[$$(date '+%Y-%m-%d %H:%M:%S')] RUN: $(1)   run by: Ani Taraiya" >> $(LOG9)

hw09-redis-up:
	$(COMPOSE9) up -d

hw09-redis-down:
	$(COMPOSE9) down

hw09-redis-ps:
	@$(call STAMP9,make hw09-redis-ps (HW9 Redis container))
	@(echo "Run by: Ani Taraiya (s3209)   $$(date '+%Y-%m-%d %H:%M:%S')"; \
	  docker ps --filter name=s3209_redis --format "table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}"; \
	  echo "$$ redis-cli PING"; docker exec s3209_redis redis-cli PING) 2>&1 | python3 code/tslog.py $(LOG9)

hw09-migrate:
	@$(call STAMP9,make hw09-migrate (HW9 Part 1 trials.view_count column))
	cd code/web_application && python3 -u migrate_hw09.py 2>&1 | python3 ../tslog.py ../../$(LOG9)

hw09-part1-test:
	@$(call STAMP9,make hw09-part1-test (HW9 Part 1 offline tests))
	python3 -u code/cache/test_trial_cache.py 2>&1 | python3 code/tslog.py $(LOG9)

hw09-part1:
	@$(call STAMP9,make hw09-part1 (HW9 Part 1 Redis view counter, 25 accesses))
	python3 -u code/run_hw09_part1.py $(if $(T),--trial-id $(T)) 2>&1 | python3 code/tslog.py $(LOG9)

hw09-part1-check:
	@$(call STAMP9,make hw09-part1-check (HW9 Part 1 Redis key vs MySQL row))
	@(echo "Run by: Ani Taraiya (s3209)"; \
	  echo "$$ redis-cli --scan --pattern 's3209:views:*'"; docker exec s3209_redis redis-cli --scan --pattern 's3209:views:*'; \
	  for k in $$(docker exec s3209_redis redis-cli --scan --pattern 's3209:views:*'); do \
	    echo "$$ redis-cli GET $$k"; docker exec s3209_redis redis-cli GET $$k; done; \
	  echo "$$ SELECT id, nct_id, view_count FROM trials WHERE view_count > 0"; \
	  cd code/web_application && python3 -c "from database import engine; from sqlalchemy import text; \
	  [print(' ', *r) for r in engine.connect().execute(text('SELECT id, nct_id, view_count FROM trials WHERE view_count > 0'))]") \
	  2>&1 | python3 code/tslog.py $(LOG9)

# HW9 Part 2: semantic cache in front of the HW8 agents (one agent per terminal)
hw09-planner:
	@$(call STAMP9,make hw09-planner (HW9 Part 2 HW8 Planner))
	cd code/kafka_agents && python3 -u planner.py 2>&1 | python3 ../tslog.py ../../$(LOG9)

hw09-writer:
	@$(call STAMP9,make hw09-writer (HW9 Part 2 HW8 Writer))
	cd code/kafka_agents && python3 -u writer.py 2>&1 | python3 ../tslog.py ../../$(LOG9)

hw09-reviewer:
	@$(call STAMP9,make hw09-reviewer (HW9 Part 2 HW8 Reviewer))
	cd code/kafka_agents && python3 -u reviewer.py 2>&1 | python3 ../tslog.py ../../$(LOG9)

hw09-part2-test:
	@$(call STAMP9,make hw09-part2-test (HW9 Part 2 offline tests))
	python3 -u code/semantic_cache/test_semantic_cache.py 2>&1 | python3 code/tslog.py $(LOG9)

hw09-part2:
	@$(call STAMP9,make hw09-part2 (HW9 Part 2 semantic cache, 12 queries, threshold $(or $(TH),0.85)))
	python3 -u code/run_hw09_part2.py --threshold $(or $(TH),0.85) 2>&1 | python3 code/tslog.py $(LOG9)

hw09-part2-redis:
	@$(call STAMP9,make hw09-part2-redis (HW9 Part 2 cache entries in Redis))
	@(echo "Run by: Ani Taraiya (s3209)"; \
	  echo "$$ redis-cli FT.INFO s3209_semcache_idx (num_docs)"; \
	  docker exec s3209_redis redis-cli FT.INFO s3209_semcache_idx | grep -A1 -E "^num_docs$$"; \
	  for k in $$(docker exec s3209_redis redis-cli --scan --pattern 's3209:semcache:*' | head -3); do \
	    echo "$$ redis-cli HMGET $$k query data_version review created_at"; \
	    docker exec s3209_redis redis-cli HMGET $$k query data_version review created_at; done) \
	  2>&1 | python3 code/tslog.py $(LOG9)
