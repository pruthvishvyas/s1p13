# SaaS Revenue-Retention Pipeline (saas_subscription_co)

Question: which active accounts will churn in the next 90 days, how much ARR is at risk, and what do we do this week?

## Run
1. Put the data at `data/raw/saas_customers.csv` (UTF-8 CSV, one row per account).
2. `python generate_notebook.py` then run `saas_subscription_co_pipeline.ipynb` top to bottom (or `python project/main.py`).
3. Outputs: `reports/` (charts, Excel, dashboard.html, deck), `models/`, `data/processed/`, `output/` (frontend JSON), `config/goals.json`.

## Headline (last run)
- Active ARR 5,086,076; ARR at risk 184,184; P1 accounts 0; scoring source: model.

## Method notes
- Leakage columns (Status, Churn_Date, Churn_Reason, Months_Active, lifetime metrics, tenure) are never used by the classifier.
- Health_Score / Churn_Risk are tested for leakage and excluded when they look derived from the outcome.
- Active accounts are scored with out-of-fold calibrated probabilities (never by a model that saw them).
- Probabilities rank relative risk; the 90-day horizon is an assumption because the data is a snapshot.
- GRR/NRR are snapshot approximations, not annualized.
- Thresholds live in CONFIG['THRESHOLDS'] and `data/processed/validation_report.json`; goals in `config/goals.json`.
- BigQuery: fill CONFIG['BIGQUERY'] and upload `data/processed/account_master.csv`; `export_for_frontend.py` falls back to CSV on any error.
