# HW3 Retrieval Metrics

## Full-corpus chunk statistics

| Technique | Chunks | Average chunk length (characters) | Minimum length | Maximum length |
|---|---:|---:|---:|---:|
| Token | 1494 | 975.78 | 147 | 1427 |
| Semantic | 820 | 1515.05 | 3 | 12408 |
| Sentence-window | 7863 | 158.00 | 2 | 5351 |

## Per-question retrieval results

| Question | Technique | Top-1 cosine | Mean@k cosine | Recall@k | Latency (ms) |
|---|---|---:|---:|---:|---:|
| q1 | Semantic | 0.7207 | 0.6108 | True | 109.70 |
| q2 | Semantic | 0.6934 | 0.5072 | True | 74.91 |
| q3 | Semantic | 0.7440 | 0.6465 | True | 69.26 |
| q4 | Semantic | 0.5899 | 0.5041 | True | 74.41 |
| q5 | Semantic | 0.7105 | 0.6351 | True | 82.35 |
| q1 | Sentence-window | 0.7784 | 0.5816 | True | 334.37 |
| q2 | Sentence-window | 0.7894 | 0.6605 | True | 355.07 |
| q3 | Sentence-window | 0.8488 | 0.6462 | True | 337.76 |
| q4 | Sentence-window | 0.6231 | 0.5442 | True | 344.53 |
| q5 | Sentence-window | 0.6707 | 0.6564 | True | 361.81 |
| q1 | Token | 0.7296 | 0.6385 | True | 85.79 |
| q2 | Token | 0.6997 | 0.6284 | True | 89.25 |
| q3 | Token | 0.6992 | 0.6108 | True | 91.99 |
| q4 | Token | 0.6215 | 0.5141 | True | 86.72 |
| q5 | Token | 0.7195 | 0.6733 | True | 162.74 |

## Technique summary

| Technique | Chunks | Average chunk length | Mean top-1 cosine | Mean@k cosine | Recall@k | Mean latency (ms) |
|---|---:|---:|---:|---:|---:|---:|
| Token | 1494 | 975.78 | 0.6939 | 0.6130 | 1.0000 | 103.30 |
| Semantic | 820 | 1515.05 | 0.6917 | 0.5808 | 1.0000 | 82.12 |
| Sentence-window | 7863 | 158.00 | 0.7421 | 0.6177 | 1.0000 | 346.71 |

## High-score incorrect retrieval analysis

For q4, the expected answer was Dapagliflozin from study NCT03704818.
The Token method ranked a different diabetes study, NCT00488527, first.
The incorrect result had a store score of 0.6117 and cosine similarity of 0.6215.
Its preview referred to Lantus therapy and did not contain Dapagliflozin.
The embedding likely considered it similar because both studies contain related
diabetes, medication, and hypoglycemia language. This demonstrates that
embedding similarity measures semantic relatedness, not exact answer correctness.

## Observations

Sentence-window chunking performed best overall for this corpus. It achieved
the highest mean top-1 cosine and mean@k cosine because its sentence-level
chunks preserve nearby context. However, it created many more chunks and had
higher retrieval latency than Token and Semantic chunking.

Token chunking provided a useful speed-quality balance. Semantic chunking
created the fewest chunks and had the lowest average latency, but its average
similarity scores were lower. Performance varied by question, showing that
no single technique was best for every individual query.

## Conclusion

Sentence-window was the best overall technique for this clinical-trial corpus.
It achieved the highest average top-1 cosine and mean@k cosine while all three
techniques achieved perfect source-level Recall@k. Its main disadvantage was
higher computational cost because it created 7,863 chunks and required more
retrieval time. Token chunking was a practical faster alternative, while
Semantic chunking was the most compact and fastest approach.

## AI Use and Verification

### 1. How AI assistance was used

I used an AI assistant as a programming guide while completing HW3. It helped me understand the assignment requirements and provided code suggestions for creating auth.py, updating main.py, adding login and logout routes, managing sessions, protecting the dashboard, and applying Bootstrap styling to the HTML pages. For Part 2, it also suggested code for loading the clinical-trial documents, creating the three LlamaIndex chunking pipelines, generating embeddings, retrieving results, calculating cosine similarity, creating metrics, and running verification checks.
I did not use the assistant to submit pre-generated results. I entered and modified the suggested code in VS Code, installed the required packages, ran the programs locally, checked errors, tested the application, captured screenshots, reviewed the retrieval outputs, and created the final report. I also made the final decisions about which results and evidence to include


### 2. Incorrect or unsuitable AI-produced output

The first retrieval implementation chunked the complete JSON records directly. This caused chunks to contain JSON syntax such as braces, field names, and quoted values instead of clear clinical-trial text. The first retrieval results were also not useful for the question about the study status of NCT00741390.

### 3. How the problem was detected

I inspected the printed chunk previews and retrieval results. The previews contained fragmented JSON content, and the top results for the status question did not clearly contain the expected study status. I compared the results with the expected answers in `questions.yaml`.

### 4. What was changed and why

I changed the corpus loader to extract readable fields from each study, including the study title, summary, detailed description, conditions, eligibility criteria, study ID, and overall status. This created more meaningful chunks for embedding and retrieval. I then reran the three chunking techniques and regenerated the raw results and metrics. The final pipeline produced meaningful text previews and complete comparison results for all 15 question-technique combinations.
