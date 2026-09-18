import json
from pathlib import Path
from statistics import mean

from llama_index.embeddings.huggingface import HuggingFaceEmbedding

from retrieve_hw03 import (
    EMBEDDING_MODEL_NAME,
    build_semantic_nodes,
    build_sentence_window_nodes,
    build_token_nodes,
    load_corpus_documents,
)


PROJECT_ROOT = Path(__file__).resolve().parents[3]
OUTPUT_FILE = PROJECT_ROOT / "reports" / "hw03" / "chunk_stats.json"


def calculate_stats(nodes):
    lengths = [
        len(node.get_content())
        for node in nodes
    ]

    return {
        "chunks": len(nodes),
        "average_chunk_length_chars": mean(lengths),
        "minimum_chunk_length_chars": min(lengths),
        "maximum_chunk_length_chars": max(lengths),
    }


if __name__ == "__main__":
    documents = load_corpus_documents()

    print("Documents loaded:", len(documents))

    embed_model = HuggingFaceEmbedding(
        model_name=EMBEDDING_MODEL_NAME
    )

    print("Building Token chunks...")
    token_nodes = build_token_nodes(documents)

    print("Building Semantic chunks...")
    semantic_nodes = build_semantic_nodes(
        documents,
        embed_model,
    )

    print("Building Sentence-window chunks...")
    sentence_window_nodes = build_sentence_window_nodes(documents)

    stats = {
        "documents": len(documents),
        "techniques": {
            "Token": calculate_stats(token_nodes),
            "Semantic": calculate_stats(semantic_nodes),
            "Sentence-window": calculate_stats(
                sentence_window_nodes
            ),
        },
    }

    OUTPUT_FILE.write_text(
        json.dumps(stats, indent=2),
        encoding="utf-8",
    )

    print(json.dumps(stats, indent=2))
    print("Chunk statistics saved to:", OUTPUT_FILE)