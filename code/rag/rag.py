import json
import re
from pathlib import Path

import faiss
import numpy as np
import ollama
from sentence_transformers import SentenceTransformer

LLM_MODEL = "qwen3:4b-instruct-2507-q4_K_M"
CORPUS_DIR = Path(__file__).resolve().parent / "corpus"
CHUNK_SIZE = 500
CHUNK_OVERLAP = 50
EMBED_MODEL_NAME = "all-MiniLM-L6-v2"
REPORTS_DIR = Path(__file__).resolve().parents[2] / "reports" / "hw04" / "raw"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

_embed_model = None


def get_embedder():
    global _embed_model
    if _embed_model is None:
        _embed_model = SentenceTransformer(EMBED_MODEL_NAME)
    return _embed_model


def load_corpus():
    """Read every .md file in corpus/ as (source_name, full_text)."""
    docs = []
    for path in sorted(CORPUS_DIR.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        docs.append((path.name, text))
    return docs


def chunk_text(text, chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
    """Character-based chunking with overlap, as required by the assignment."""
    text = re.sub(r"\s+", " ", text).strip()
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        chunks.append(chunk)
        if end >= len(text):
            break
        start = end - overlap
    return chunks


def build_index():
    """Chunk every document, embed the chunks, and build a FAISS index."""
    docs = load_corpus()
    embedder = get_embedder()

    chunk_records = []  # each: {chunk_id, source, text}
    chunk_id = 0
    for source_name, text in docs:
        pieces = chunk_text(text)
        for piece in pieces:
            chunk_records.append({
                "chunk_id": chunk_id,
                "source": source_name,
                "text": piece,
            })
            chunk_id += 1

    texts = [c["text"] for c in chunk_records]
    embeddings = embedder.encode(texts, convert_to_numpy=True, normalize_embeddings=True)

    dim = embeddings.shape[1]
    index = faiss.IndexFlatIP(dim)  # inner product on normalized vectors = cosine similarity
    index.add(embeddings.astype(np.float32))

    return index, chunk_records


def retrieve(query, index, chunk_records, top_k=3):
    """Return the top_k chunks most similar to the query, with their score."""
    embedder = get_embedder()
    q_emb = embedder.encode([query], convert_to_numpy=True, normalize_embeddings=True)
    scores, indices = index.search(q_emb.astype(np.float32), top_k)

    results = []
    for score, idx in zip(scores[0], indices[0]):
        if idx == -1:
            continue
        record = chunk_records[idx]
        results.append({
            "chunk_id": record["chunk_id"],
            "source": record["source"],
            "text": record["text"],
            "score": float(score),
        })
    return results


def print_retrieval(query, results):
    print(f"\nQuery: {query}")
    print(f"Retrieved {len(results)} chunks:")
    for r in results:
        preview = r["text"][:100].replace("\n", " ")
        print(f"  [chunk {r['chunk_id']:3d}] source={r['source']:30s} "
              f"score={r['score']:.3f}  \"{preview}...\"")


def call_llm(prompt):
    response = ollama.chat(
        model=LLM_MODEL,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.message.content


def config_a_no_rag(question):
    """Baseline: question straight to the LLM, no context at all."""
    prompt = f"Answer this question as best you can:\n\n{question}"
    return call_llm(prompt)


def config_b_basic_rag(question, index, chunk_records, top_k=3):
    """Basic RAG: top-k raw chunks pasted into the prompt, no cleanup."""
    results = retrieve(question, index, chunk_records, top_k=top_k)
    context = "\n\n".join(r["text"] for r in results)
    prompt = f"""Use the following context to answer the question.

Context:
{context}

Question: {question}"""
    return call_llm(prompt), results


def config_c_context_engineered(question, index, chunk_records, top_k=3):
    """Context-engineered RAG: dedup, label sources, add grounding rules."""
    results = retrieve(question, index, chunk_records, top_k=top_k)

    # Drop exact-duplicate chunk text (de-duplication)
    seen_text = set()
    deduped = []
    for r in results:
        if r["text"] not in seen_text:
            seen_text.add(r["text"])
            deduped.append(r)

    # Order and label survivors with their source, numbered for citation
    labeled_context = "\n\n".join(
        f"[Source {i+1}: {r['source']}]\n{r['text']}"
        for i, r in enumerate(deduped)
    )

    prompt = f"""Answer the question using ONLY the numbered sources below.
Cite the source number(s) you used, like [Source 1].
If the sources do not contain enough information to answer, respond exactly with:
"I cannot answer this question from the provided documents"

Sources:
{labeled_context}

Question: {question}"""
    return call_llm(prompt), deduped


if __name__ == "__main__":
    print("Building index from corpus...")
    index, chunk_records = build_index()
    print(f"Indexed {len(chunk_records)} chunks from {len(load_corpus())} documents.\n")

    test_q = "What happens during a Phase I clinical trial?"

    print("=" * 60)
    print("CONFIG A: No-RAG")
    print("=" * 60)
    print(config_a_no_rag(test_q))

    print("\n" + "=" * 60)
    print("CONFIG B: Basic-RAG")
    print("=" * 60)
    answer_b, chunks_b = config_b_basic_rag(test_q, index, chunk_records)
    print_retrieval(test_q, chunks_b)
    print("\nAnswer:", answer_b)

    print("\n" + "=" * 60)
    print("CONFIG C: Context-Engineered RAG")
    print("=" * 60)
    answer_c, chunks_c = config_c_context_engineered(test_q, index, chunk_records)
    print_retrieval(test_q, chunks_c)
    print("\nAnswer:", answer_c)

    QUESTIONS = {
    "Q1": "What is a Phase I clinical trial?",
    "Q2": "What must be included when a clinical trial is registered, and what happens if a trial is stopped early?",
    "Q3": "What is a clinical trial phase?",
    "Q4": "Why might a trial stop?",
    "Q5": "What is the average cost of running a Phase III clinical trial?",
    "Q6": "What is the capital of France?",
}


def run_all_configs(question, index, chunk_records, top_k=3):
    """Run one question through all 3 configs. Returns a dict of results."""
    answer_a = config_a_no_rag(question)
    answer_b, chunks_b = config_b_basic_rag(question, index, chunk_records, top_k)
    answer_c, chunks_c = config_c_context_engineered(question, index, chunk_records, top_k)

    return {
        "question": question,
        "config_a_answer": answer_a,
        "config_b_answer": answer_b,
        "config_b_chunks": chunks_b,
        "config_c_answer": answer_c,
        "config_c_chunks": chunks_c,
    }


def run_test_set():
    index, chunk_records = build_index()
    all_results = {}
    output_lines = []

    def log(line=""):
        print(line)
        output_lines.append(line)

    for qid, question in QUESTIONS.items():
        log("\n" + "#" * 70)
        log(f"{qid}: {question}")
        log("#" * 70)

        result = run_all_configs(question, index, chunk_records)
        all_results[qid] = result

        log("\n--- Config A (No-RAG) ---")
        log(result["config_a_answer"])

        log("\n--- Config B (Basic-RAG) ---")
        for r in result["config_b_chunks"]:
            log(f"  [chunk {r['chunk_id']:3d}] source={r['source']:30s} score={r['score']:.3f}")
        log("Answer: " + result["config_b_answer"])

        log("\n--- Config C (Context-RAG) ---")
        for r in result["config_c_chunks"]:
            log(f"  [chunk {r['chunk_id']:3d}] source={r['source']:30s} score={r['score']:.3f}")
        log("Answer: " + result["config_c_answer"])

    out_path = REPORTS_DIR / "rag_six_questions.txt"
    out_path.write_text("\n".join(output_lines), encoding="utf-8")
    print(f"\nSaved six-question results to {out_path}")

    return all_results

def run_k_sweep(question, index, chunk_records, k_values=(1, 3, 5)):
    """Run one question at different top_k values to see how context size affects the answer."""
    sweep_results = {}
    output_lines = [f"Question: {question}\n"]

    def log(line=""):
        print(line)
        output_lines.append(line)

    for k in k_values:
        log("\n" + "-" * 60)
        log(f"top_k = {k}")
        log("-" * 60)
        answer, chunks = config_c_context_engineered(question, index, chunk_records, top_k=k)
        for r in chunks:
            log(f"  [chunk {r['chunk_id']:3d}] source={r['source']:30s} score={r['score']:.3f}")
        log("Answer: " + answer)
        sweep_results[k] = {"answer": answer, "chunks": chunks}

    out_path = REPORTS_DIR / "rag_k_sweep.txt"
    out_path.write_text("\n".join(output_lines), encoding="utf-8")
    print(f"\nSaved k-sweep results to {out_path}")

    return sweep_results

def save_evaluation_table():
    """Save the manually-assessed evaluation table (Step 6) as a CSV."""
    import csv

    rows = [
        {"question": "Q1", "config": "A (No-RAG)", "correct_retrieval": "N/A", "correct_answer": "Yes", "grounded": "No", "refused_when_needed": "N/A"},
        {"question": "Q1", "config": "B (Basic-RAG)", "correct_retrieval": "Yes", "correct_answer": "Yes", "grounded": "Yes", "refused_when_needed": "N/A"},
        {"question": "Q1", "config": "C (Context-RAG)", "correct_retrieval": "Yes", "correct_answer": "Yes", "grounded": "Yes", "refused_when_needed": "N/A"},
        {"question": "Q2", "config": "A (No-RAG)", "correct_retrieval": "N/A", "correct_answer": "Partial", "grounded": "No", "refused_when_needed": "N/A"},
        {"question": "Q2", "config": "B (Basic-RAG)", "correct_retrieval": "Yes", "correct_answer": "Yes", "grounded": "Yes", "refused_when_needed": "N/A"},
        {"question": "Q2", "config": "C (Context-RAG)", "correct_retrieval": "Yes", "correct_answer": "Yes", "grounded": "Yes", "refused_when_needed": "N/A"},
        {"question": "Q3", "config": "A (No-RAG)", "correct_retrieval": "N/A", "correct_answer": "Yes", "grounded": "No", "refused_when_needed": "N/A"},
        {"question": "Q3", "config": "B (Basic-RAG)", "correct_retrieval": "Yes", "correct_answer": "Yes", "grounded": "Yes", "refused_when_needed": "N/A"},
        {"question": "Q3", "config": "C (Context-RAG)", "correct_retrieval": "Yes", "correct_answer": "Yes", "grounded": "Yes", "refused_when_needed": "N/A"},
        {"question": "Q4", "config": "A (No-RAG)", "correct_retrieval": "N/A", "correct_answer": "Partial", "grounded": "No", "refused_when_needed": "N/A"},
        {"question": "Q4", "config": "B (Basic-RAG)", "correct_retrieval": "Yes", "correct_answer": "Yes", "grounded": "Yes", "refused_when_needed": "N/A"},
        {"question": "Q4", "config": "C (Context-RAG)", "correct_retrieval": "Yes", "correct_answer": "Yes", "grounded": "Yes", "refused_when_needed": "N/A"},
        {"question": "Q5", "config": "A (No-RAG)", "correct_retrieval": "N/A", "correct_answer": "No", "grounded": "No", "refused_when_needed": "No"},
        {"question": "Q5", "config": "B (Basic-RAG)", "correct_retrieval": "Yes", "correct_answer": "Yes", "grounded": "Yes", "refused_when_needed": "Partial"},
        {"question": "Q5", "config": "C (Context-RAG)", "correct_retrieval": "Yes", "correct_answer": "Yes", "grounded": "Yes", "refused_when_needed": "Yes"},
        {"question": "Q6", "config": "A (No-RAG)", "correct_retrieval": "N/A", "correct_answer": "Yes", "grounded": "No", "refused_when_needed": "No"},
        {"question": "Q6", "config": "B (Basic-RAG)", "correct_retrieval": "Yes", "correct_answer": "No", "grounded": "No", "refused_when_needed": "No"},
        {"question": "Q6", "config": "C (Context-RAG)", "correct_retrieval": "Yes", "correct_answer": "Yes", "grounded": "Yes", "refused_when_needed": "Yes"},
    ]

    out_path = REPORTS_DIR / "rag_evaluation_table.csv"
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    print(f"Saved evaluation table to {out_path}")


if __name__ == "__main__":
    print("Building index from corpus...")
    index, chunk_records = build_index()

    print("\n" + "=" * 70)
    print("SIX-QUESTION TEST SET (all 3 configs)")
    print("=" * 70)
    results = run_test_set()

    print("\n\n" + "=" * 70)
    print("TOP_K SWEEP (Config C) on Q2")
    print("=" * 70)
    sweep_q = QUESTIONS["Q2"]
    sweep_results = run_k_sweep(sweep_q, index, chunk_records, k_values=(1, 3, 5))

    print("\n\n" + "=" * 70)
    print("EVALUATION TABLE")
    print("=" * 70)
    save_evaluation_table()

    print("\nAll Part 4 outputs saved to reports/hw04/raw/")

