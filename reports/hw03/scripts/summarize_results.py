import json
from pathlib import Path
from statistics import mean


PROJECT_ROOT = Path(__file__).resolve().parents[3]

RAW_DIR = PROJECT_ROOT / "reports" / "hw03" / "raw"
CHUNK_STATS_FILE = PROJECT_ROOT / "reports" / "hw03" / "chunk_stats.json"
METRICS_FILE = PROJECT_ROOT / "reports" / "hw03" / "METRICS.md"


def load_results():
    return [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(RAW_DIR.glob("*.json"))
    ]


def calculate_question_metrics(result):
    rows = result["results"]
    cosine_values = [row["cosine_sim"] for row in rows]

    expected_source = result["expected_source"]

    recall = any(
        row.get("source") == expected_source
        for row in rows
    )

    return {
        "technique": result["technique"],
        "query_id": result["query_id"],
        "top1_cosine": max(cosine_values),
        "mean_at_k_cosine": mean(cosine_values),
        "recall_at_k": recall,
        "latency_ms": result["retrieval_latency_ms"],
    }


def write_metrics_report(question_metrics, chunk_stats):
    lines = [
        "# HW3 Retrieval Metrics",
        "",
        "## Full-corpus chunk statistics",
        "",
        "| Technique | Chunks | Average chunk length (characters) | Minimum length | Maximum length |",
        "|---|---:|---:|---:|---:|",
    ]

    for technique in ["Token", "Semantic", "Sentence-window"]:
        stats = chunk_stats["techniques"][technique]

        lines.append(
            f"| {technique} "
            f"| {stats['chunks']} "
            f"| {stats['average_chunk_length_chars']:.2f} "
            f"| {stats['minimum_chunk_length_chars']} "
            f"| {stats['maximum_chunk_length_chars']} |"
        )

    lines.extend(
        [
            "",
            "## Per-question retrieval results",
            "",
            "| Question | Technique | Top-1 cosine | Mean@k cosine | Recall@k | Latency (ms) |",
            "|---|---|---:|---:|---:|---:|",
        ]
    )

    for item in question_metrics:
        lines.append(
            f"| {item['query_id']} "
            f"| {item['technique']} "
            f"| {item['top1_cosine']:.4f} "
            f"| {item['mean_at_k_cosine']:.4f} "
            f"| {str(item['recall_at_k'])} "
            f"| {item['latency_ms']:.2f} |"
        )

    summary = {}

    lines.extend(
        [
            "",
            "## Technique summary",
            "",
            "| Technique | Chunks | Average chunk length | Mean top-1 cosine | Mean@k cosine | Recall@k | Mean latency (ms) |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
    )

    for technique in ["Token", "Semantic", "Sentence-window"]:
        items = [
            item
            for item in question_metrics
            if item["technique"] == technique
        ]

        stats = chunk_stats["techniques"][technique]

        summary[technique] = {
            "mean_top1": mean(
                item["top1_cosine"] for item in items
            ),
            "mean_at_k": mean(
                item["mean_at_k_cosine"] for item in items
            ),
            "recall": mean(
                item["recall_at_k"] for item in items
            ),
            "latency": mean(
                item["latency_ms"] for item in items
            ),
        }

        lines.append(
            f"| {technique} "
            f"| {stats['chunks']} "
            f"| {stats['average_chunk_length_chars']:.2f} "
            f"| {summary[technique]['mean_top1']:.4f} "
            f"| {summary[technique]['mean_at_k']:.4f} "
            f"| {summary[technique]['recall']:.4f} "
            f"| {summary[technique]['latency']:.2f} |"
        )

    lines.extend(
        [
            "",
            "## High-score incorrect retrieval analysis",
            "",
            "For q4, the expected answer was Dapagliflozin from study NCT03704818.",
            "The Token method ranked a different diabetes study, NCT00488527, first.",
            "The incorrect result had a store score of 0.6117 and cosine similarity of 0.6215.",
            "Its preview referred to Lantus therapy and did not contain Dapagliflozin.",
            "The embedding likely considered it similar because both studies contain related",
            "diabetes, medication, and hypoglycemia language. This demonstrates that",
            "embedding similarity measures semantic relatedness, not exact answer correctness.",
            "",
            "## Observations",
            "",
            "Sentence-window chunking performed best overall for this corpus. It achieved",
            "the highest mean top-1 cosine and mean@k cosine because its sentence-level",
            "chunks preserve nearby context. However, it created many more chunks and had",
            "higher retrieval latency than Token and Semantic chunking.",
            "",
            "Token chunking provided a useful speed-quality balance. Semantic chunking",
            "created the fewest chunks and had the lowest average latency, but its average",
            "similarity scores were lower. Performance varied by question, showing that",
            "no single technique was best for every individual query.",
            "",
            "## Conclusion",
            "",
            "Sentence-window was the best overall technique for this clinical-trial corpus.",
            "It achieved the highest average top-1 cosine and mean@k cosine while all three",
            "techniques achieved perfect source-level Recall@k. Its main disadvantage was",
            "higher computational cost because it created 7,863 chunks and required more",
            "retrieval time. Token chunking was a practical faster alternative, while",
            "Semantic chunking was the most compact and fastest approach.",
        ]
    )

    METRICS_FILE.write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    raw_results = load_results()

    if len(raw_results) != 15:
        raise ValueError(
            f"Expected 15 raw result files, found {len(raw_results)}"
        )

    chunk_stats = json.loads(
        CHUNK_STATS_FILE.read_text(encoding="utf-8")
    )

    metrics = [
        calculate_question_metrics(result)
        for result in raw_results
    ]

    write_metrics_report(metrics, chunk_stats)

    print("Raw result files:", len(raw_results))
    print("Full-corpus chunk statistics loaded")
    print("Error analysis added")
    print("Observations added")
    print("Conclusion added")
    print("Metrics written to:", METRICS_FILE)