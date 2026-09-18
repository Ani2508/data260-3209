# DATA 260 HW3 Reproducible Run Instructions

## Environment

Operating system: Windows 11

Check Python version:

    py -3.12 --version

## Install dependencies

    py -3.12 -m pip install llama-index llama-index-embeddings-huggingface sentence-transformers faiss-cpu numpy pandas pyyaml fastapi uvicorn jinja2 itsdangerous

The project uses the public embedding model `sentence-transformers/all-MiniLM-L6-v2`, which is downloaded automatically from Hugging Face during the first run.

## Start the FastAPI application

Open a terminal in the web application folder:

    cd D:\data260-3209\code\web_application
    py -3.12 -m uvicorn main:app --host 127.0.0.1 --port 8509

Keep this terminal running. The application is available at http://127.0.0.1:8509/

## Build chunk statistics

Open a second terminal:

    cd D:\data260-3209
    py -3.12 reports\hw03\scripts\chunk_stats.py

This creates `reports/hw03/chunk_stats.json`

## Run the three retrieval pipelines

    py -3.12 reports\hw03\scripts\retrieve_hw03.py

This runs TokenTextSplitter, SemanticSplitterNodeParser, and SentenceWindowNodeParser, and creates 15 raw JSON files in `reports/hw03/raw/`

## Create the metrics summary

    py -3.12 reports\hw03\scripts\summarize_results.py

This creates `reports/hw03/METRICS.md`

## Run the verification script

Make sure the FastAPI server is still running, then execute:

    py -3.12 reports\hw03\scripts\verify_hw03.py

This creates `reports/hw03/verification.json` and should end with `"overall_pass": true`

## Reproducibility note

The retrieval comparison uses the same corpus and the same embedding model for all three chunking techniques. The vector indexes are built in memory and are not stored as permanent databases.