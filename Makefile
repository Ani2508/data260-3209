verify-hw01:
	py -3.12 verify_hw01.py

run-agents:
	cd code && py -3.12 agents_demo.py --title "Phase II Study of Drug X in Type 2 Diabetes" --content "This randomized trial enrolls adult patients with type 2 diabetes over six months to test blood glucose control with a new oral medication." --strict

run-client:
	cd code && py -3.12 hw1_client.py

run-nondeterminism:
	cd code && py -3.12 run_nondeterminism.py

docker-build:
	cd code && docker build -t clinical-trial-app -f Dockerfile .

docker-run:
	docker run -d -p 8509:8509 clinical-trial-app
