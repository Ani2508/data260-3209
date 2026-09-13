\# DATA-260 Homework 2 Part 4 Metrics



\## Frozen input



All normal experiments used the exact same frozen input:



`reports/hw02/cases/schema\_input.json`



Model:



`qwen3:4b-instruct-2507-q4\_K\_M`



Hardware:



Microsoft Surface Laptop 3, AMD Ryzen 5, 16 GB RAM, CPU-only.



Forced test environment variables were cleared during all normal experiments.



\## Thirty-run schema-validation experiment



| Category | Count |

|---|---:|

| Valid first attempt | 30 |

| Valid after one retry | 0 |

| Valid after two or more retries | 0 |

| Abandoned at the ceiling | 0 |

| Total runs | 30 |



Completion rate: 30/30 = 100%



Mean latency: 35,579.15 ms, approximately 35.58 seconds.



Minimum latency: 31,863.69 ms.



Maximum latency: 73,436.91 ms.



The Planner produced valid output on the first attempt in all 30 normal runs.



\## Turn-ceiling comparison



| Turn ceiling | Runs | Completed reviewed runs | Completion rate | Mean latency |

|---:|---:|---:|---:|---:|

| 2 | 20 | 0 | 0% | 19,103.69 ms |

| 10 | 20 | 20 | 100% | 34,894.50 ms |



Ceiling 2 was faster, but it stopped before the Reviewer ran. Its Planner output was valid, but the final state had empty reviewer feedback.



Ceiling 10 allowed the full Supervisor-Planner-Reviewer workflow to complete in all 20 runs.



Deployment choice: turn ceiling 10.



Reason: The assignment requires the full validation and review workflow. Ceiling 10 achieved a 100% completion rate, while ceiling 2 achieved 0% full reviewed completion.



\## Adversarial-input experiment



The adversarial input was saved as:



`reports/hw02/cases/adversarial\_input.json`



| Run | Turn count | Reached ceiling |

|---:|---:|---|

| 1 | 4 | No |

| 2 | 4 | No |

| 3 | 4 | No |

| 4 | 4 | No |

| 5 | 4 | No |



Runs reaching the ceiling: 0/5.



Observed ceiling rate: 0%.



Mean latency: 53,047.53 ms, approximately 53.05 seconds.



The conflicting instructions in the input did not cause the graph to reach its turn ceiling. The Planner and Reviewer still completed successfully in all five observed runs.

