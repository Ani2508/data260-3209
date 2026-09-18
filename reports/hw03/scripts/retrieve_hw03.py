import json
import time
from pathlib import Path
from datetime import datetime, timezone

import numpy as np
import yaml

from llama_index.core import (
    Document,
    VectorStoreIndex,
    StorageContext,
)
from llama_index.core.vector_stores import SimpleVectorStore
from llama_index.core.node_parser import (
    TokenTextSplitter,
    SentenceWindowNodeParser,
    SemanticSplitterNodeParser,
)
from llama_index.embeddings.huggingface import HuggingFaceEmbedding


PROJECT_ROOT = Path(__file__).resolve().parents[3]
CORPUS_DIR = PROJECT_ROOT / "corpus"
QUESTIONS_FILE = PROJECT_ROOT / "reports" / "hw03" / "questions.yaml"
RAW_DIR = PROJECT_ROOT / "reports" / "hw03" / "raw"
RUN_LOG_FILE = PROJECT_ROOT / "reports" / "hw03" / "RUN_LOG.txt"
EMBEDDING_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"


def extract_study_text(study):
    """Pull only the readable narrative fields from a study record."""
    protocol = study.get("protocolSection", {})
    identification = protocol.get("identificationModule", {})
    status_module = protocol.get("statusModule", {})
    description = protocol.get("descriptionModule", {})
    conditions_module = protocol.get("conditionsModule", {})
    eligibility = protocol.get("eligibilityModule", {})

    parts = [
        "Study ID: " + identification.get("nctId", ""),
        "Overall status: " + status_module.get("overallStatus", ""),
        identification.get("officialTitle")
        or identification.get("briefTitle", ""),
        description.get("briefSummary", ""),
        description.get("detailedDescription", ""),
        "Conditions: " + ", ".join(
            conditions_module.get("conditions", [])
        ),
        eligibility.get("eligibilityCriteria", ""),
    ]

    return "\n\n".join(p for p in parts if p)


def load_corpus_documents(limit=None):
    documents = []

    for file_path in sorted(CORPUS_DIR.glob("*.json")):
        data = json.loads(file_path.read_text(encoding="utf-8"))

        for study in data.get("studies", []):

            if limit is not None and len(documents) >= limit:
                return documents

            study_text = extract_study_text(study)

            if not study_text.strip():
                continue

            documents.append(
                Document(
                    text=study_text,
                    metadata={
                        "source": f"corpus/{file_path.name}",
                        "nct_id": study.get("protocolSection", {})
                                       .get("identificationModule", {})
                                       .get("nctId", "unknown"),
                    },
                )
            )

    return documents


def build_token_nodes(documents):
    splitter = TokenTextSplitter(
        chunk_size=256,
        chunk_overlap=40,
    )
    return splitter.get_nodes_from_documents(documents)


def build_sentence_window_nodes(documents):
    splitter = SentenceWindowNodeParser.from_defaults(
        window_size=3,
        window_metadata_key="window",
        original_text_metadata_key="original_text",
    )
    return splitter.get_nodes_from_documents(documents)


def build_semantic_nodes(documents, embed_model):
    splitter = SemanticSplitterNodeParser(
        buffer_size=1,
        breakpoint_percentile_threshold=95,
        embed_model=embed_model,
    )
    return splitter.get_nodes_from_documents(documents)


def build_in_memory_index(nodes, embed_model):
    vector_store = SimpleVectorStore()
    storage_context = StorageContext.from_defaults(
        vector_store=vector_store
    )

    return VectorStoreIndex(
        nodes=nodes,
        storage_context=storage_context,
        embed_model=embed_model,
        show_progress=False,
    )


def cosine_similarity(vector_a, vector_b):
    vector_a = np.asarray(vector_a, dtype=float)
    vector_b = np.asarray(vector_b, dtype=float)

    denominator = np.linalg.norm(vector_a) * np.linalg.norm(vector_b)

    if denominator == 0:
        return 0.0

    return float(np.dot(vector_a, vector_b) / denominator)


def retrieve_and_report(
    index,
    technique,
    query_id,
    query,
    embed_model,
    k=3,
):
    query_embedding = np.asarray(
        embed_model.get_query_embedding(query),
        dtype=float,
    )

    retriever = index.as_retriever(similarity_top_k=k)

    start_time = time.perf_counter()
    retrieved_nodes = retriever.retrieve(query)
    latency_ms = (time.perf_counter() - start_time) * 1000

    document_vectors = []
    result_rows = []

    for rank, result in enumerate(retrieved_nodes, start=1):
        chunk_text = result.node.get_content()

        document_embedding = np.asarray(
            embed_model.get_text_embedding(chunk_text),
            dtype=float,
        )

        document_vectors.append(document_embedding)

        result_rows.append(
            {
                "rank": rank,
                "store_score": (
                    float(result.score)
                    if result.score is not None
                    else None
                ),
                "cosine_sim": cosine_similarity(
                    query_embedding,
                    document_embedding,
                ),
                "chunk_len": len(chunk_text),
                "preview": chunk_text[:160].replace("\n", " "),
                "source": result.node.metadata.get("source"),
            }
        )

    document_matrix = (
        np.vstack(document_vectors)
        if document_vectors
        else np.empty((0, len(query_embedding)))
    )

    print(f"\n=== {technique} | {query_id} ===")
    print("Query:", query)
    print("Query embedding dimension:", len(query_embedding))
    print("First eight query values:", query_embedding[:8].tolist())
    print("Query vector shape:", query_embedding.shape)
    print("Document vector shape:", document_matrix.shape)
    print(f"Retrieval latency: {latency_ms:.2f} ms")
    print("rank | store_score | cosine_sim | chunk_len | preview")

    for row in result_rows:
        print(
            row["rank"],
            "|",
            row["store_score"],
            "|",
            f'{row["cosine_sim"]:.6f}',
            "|",
            row["chunk_len"],
            "|",
            row["preview"],
        )

    return {
        "technique": technique,
        "query_id": query_id,
        "query": query,
        "query_embedding_dimension": len(query_embedding),
        "query_embedding_first_8": query_embedding[:8].tolist(),
        "query_vector_shape": list(query_embedding.shape),
        "document_vector_shape": list(document_matrix.shape),
        "retrieval_latency_ms": latency_ms,
        "results": result_rows,
    }


if __name__ == "__main__":
    run_started = datetime.now(timezone.utc)

    documents = load_corpus_documents()

    embed_model = HuggingFaceEmbedding(model_name=EMBEDDING_MODEL_NAME)

    token_nodes = build_token_nodes(documents)
    sentence_window_nodes = build_sentence_window_nodes(documents)
    print("Building semantic chunks (this is the slow one)...")
    semantic_nodes = build_semantic_nodes(documents, embed_model)

    print("\nDocuments loaded:", len(documents))
    print("Token chunks created:", len(token_nodes))
    print("Sentence-window chunks created:", len(sentence_window_nodes))
    print("Semantic chunks created:", len(semantic_nodes))

    print("\nBuilding vector indexes...")
    token_index = build_in_memory_index(token_nodes, embed_model)
    print("  Token index built")
    sentence_window_index = build_in_memory_index(sentence_window_nodes, embed_model)
    print("  Sentence-window index built")
    semantic_index = build_in_memory_index(semantic_nodes, embed_model)
    print("  Semantic index built")

    print("\nAll three indexes ready.")

    # --- Run all 5 questions x 3 techniques, save 15 JSON files ---
    questions = yaml.safe_load(
        QUESTIONS_FILE.read_text(encoding="utf-8")
    )

    RAW_DIR.mkdir(parents=True, exist_ok=True)

    technique_indexes = [
        ("Token", token_index),
        ("Semantic", semantic_index),
        ("Sentence-window", sentence_window_index),
    ]

    for technique_name, index in technique_indexes:
        for question in questions:
            result = retrieve_and_report(
                index=index,
                technique=technique_name,
                query_id=question["id"],
                query=question["question"],
                embed_model=embed_model,
                k=3,
            )

            result["expected_answer"] = question["expected_answer"]
            result["expected_source"] = question["expected_source"]

            safe_name = technique_name.lower().replace("-", "_")
            output_path = RAW_DIR / (
                f"{safe_name}_{question['id']}.json"
            )

            output_path.write_text(
                json.dumps(result, indent=2),
                encoding="utf-8",
            )

            print("Saved:", output_path)

    # --- Write the run log ---
    run_finished = datetime.now(timezone.utc)

    log_lines = [
        "DATA-260 Homework 3 - Part 2 retrieval run",
        f"Run started (UTC):  {run_started.isoformat()}",
        f"Run finished (UTC): {run_finished.isoformat()}",
        f"Duration seconds:   {(run_finished - run_started).total_seconds():.1f}",
        f"Embedding model:    {EMBEDDING_MODEL_NAME}",
        f"Documents loaded:   {len(documents)}",
        f"Token chunks:       {len(token_nodes)}",
        f"Sentence-window:    {len(sentence_window_nodes)}",
        f"Semantic chunks:    {len(semantic_nodes)}",
        f"Questions:          {len(questions)}",
        f"Results saved:      {len(questions) * len(technique_indexes)}",
    ]

    RUN_LOG_FILE.write_text("\n".join(log_lines), encoding="utf-8")
    print("\nRun log saved:", RUN_LOG_FILE)
    print("\n".join(log_lines))