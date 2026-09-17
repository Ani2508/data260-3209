# Clinical Trial Corpus Sources

Access date: 2026-09-17

The corpus consists of public clinical-trial study records downloaded from the official ClinicalTrials.gov Data API.

| Local file | Source URL | Topic |
|---|---|---|
| corpus/clinicaltrials_diabetes.json | https://clinicaltrials.gov/api/v2/studies?query.cond=diabetes&pageSize=100&format=json | Diabetes clinical trials |
| corpus/clinicaltrials_breast_cancer.json | https://clinicaltrials.gov/api/v2/studies?query.cond=breast%20cancer&pageSize=100&format=json | Breast cancer clinical trials |
| corpus/clinicaltrials_covid19.json | https://clinicaltrials.gov/api/v2/studies?query.cond=covid-19&pageSize=100&format=json | COVID-19 clinical trials |

The files are local snapshots of public clinical-trial records and are used as the shared corpus for all three chunking techniques.