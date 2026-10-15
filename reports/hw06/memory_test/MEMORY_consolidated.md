# MEMORY.md - durable facts (s3209)
<!-- last_consolidated: 2026-10-15T13:07:58 -->
<!-- format: - [YYYY-MM-DD] key: value {src=protocol|team|chat} -->

## Facts
- [2026-09-01] project.name: data260-3209 clinical trial listing system {src=team}
- [2026-09-26] project.port: FastAPI backend runs on PORT_BASE 8509 {src=protocol} <!-- merged x2 -->
- [2026-09-08] project.prefix: s3209 {src=team} <!-- merged x2 -->
- [2026-09-20] model.local: llama3.1:8b via Ollama {src=team}
- [2026-09-02] db.relational: MySQL database s3209_rel {src=team}
- [2026-09-15] db.document: MongoDB database s3209_doc {src=team} <!-- merged x2 -->
- [2026-10-01] user.role: trial coordinator at a university hospital {src=chat} <!-- merged x2 -->
- [2026-09-16] trial.nct_id: NCT05512874 {src=protocol} <!-- merged x2 -->
- [2026-09-27] trial.drug: oral GLP-1 agonist {src=protocol} <!-- merged x2 -->
- [2026-09-04] trial.condition: type 2 diabetes in adults {src=protocol}
- [2026-10-10] site.pi: Dr. Helen Okafur {src=chat}
- [2026-09-17] site.city: Sacramento {src=chat} <!-- merged x2 -->
- [2026-09-19] trial.target: 240 participants across all sites {src=protocol} <!-- merged x2 -->
- [2026-09-29] user.preference: short answers with bullet points {src=chat} <!-- merged x2 -->
- [2026-09-18] safety.warfarin: extra INR checks for participants on warfarin {src=protocol} <!-- merged x2 -->
- [2026-09-10] irb.review_due: 2027-03-14 {src=team}
- [2026-09-23] irb.packet_ready: 2027-03-01 {src=team} <!-- merged x2 -->
- [2026-09-22] trial.phase: Phase II {src=protocol} <!-- merged x2 -->
- [2026-09-12] trial.randomization: 1:1 drug versus placebo {src=protocol}
- [2026-09-13] trial.blinding: double-blind {src=protocol}
- [2026-10-05] ae.review: adverse events reviewed weekly {src=team} <!-- merged x2 -->
- [2026-10-08] trial.enrolled: 61 participants {src=chat}
- [2026-09-24] embed.model: nomic-embed-text {src=team} <!-- merged x2 -->
- [2026-09-28] memory.short_term_n: 12 messages {src=team} <!-- merged x2 -->
- [2026-10-06] analysis.primary: intention-to-treat {src=protocol} <!-- merged x2 -->
- [2026-10-09] project.repo: github.com/Ani2508/data260-3209 {src=team} <!-- merged x2 -->

## Resolved contradictions
- project.port: kept "FastAPI backend runs on PORT_BASE 8509" (protocol, 2026-09-26) over "backend runs on port 8000" (chat, 2026-10-02) - higher source
- model.local: kept "llama3.1:8b via Ollama" (team, 2026-09-20) over "qwen3:8b via Ollama" (chat, 2026-09-01) - higher source
- site.pi: kept "Dr. Helen Okafur" (chat, 2026-10-10) over "Dr. Helen Okafor" (chat, 2026-09-30) - newer date SUSPECT: dropped value had more confirmations
- irb.review_due: kept "2027-03-14" (team, 2026-09-10) over "2027-03-04" (chat, 2026-10-11) - higher source
- trial.enrolled: kept "61 participants" (chat, 2026-10-08) over "52 participants" (chat, 2026-09-15) - newer date
