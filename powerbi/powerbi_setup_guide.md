# FraudGuard Power BI Implementation & Architecture Guide

## 1. Data Architecture & Star Schema (`powerbi/data/`)

The PySpark master pipeline exports consolidated CSV data marts into `powerbi/data/`, modeled as a single-direction star schema anchored by `dataset_summary[dataset_name]`:

1. `dataset_summary.csv` *(Dimension / Fact Header)* — `dataset_key`, `dataset_name`, `total_records`, `legitimate_records`, `fraud_records`, `fraud_prevalence_pct`, `train_records`, `val_records`, `test_records`, `numerical_features`, `categorical_features`, `dropped_high_null_features`.
2. `model_comparison.csv` — `model_name`, `total_test_samples`, `true_positives`, `true_negatives`, `false_positives`, `false_negatives`, `precision`, `recall`, `f1_score`, `roc_auc`, `pr_auc`, `log_loss`, `accuracy`, `training_time_sec`, `dataset_key`, `dataset_name`.
3. `threshold_analysis.csv` — Threshold curve (`0.05` to `0.95` step `0.05`) on the top PR-AUC model (`precision`, `recall`, `f1_score`, `flagged_volume`, `alert_rate_pct`, `total_operational_cost`, `dataset_key`, `dataset_name`, `model_name`).
4. `hyperparameter_tuning.csv` — Candidate validation configurations ranked by `val_pr_auc`, `val_roc_auc`, `val_log_loss`, and `selected` flag.
5. `amount_distribution.csv` — Class-level `count`, `min_amount`, `avg_amount`, `stddev_amount`, `max_amount`, `class_label`, `dataset_name`.
6. `missingness_profile.csv` — Column-level `null_count`, `missing_percentage`, `dataset_name`.
7. *Optional Dataset A (IEEE-CIS) marts when ingested*: `hourly_fraud_pattern.csv`, `fraud_by_product.csv`, `fraud_by_card.csv`.

---

## 2. Core DAX Measures (Embedded in `FraudGuard_Dashboard.SemanticModel`)

```dax
Total Transactions = SUM(dataset_summary[total_records])
Total Fraud Cases = SUM(dataset_summary[fraud_records])
Total Legitimate Transactions = SUM(dataset_summary[legitimate_records])
Fraud Prevalence Pct = DIVIDE(SUM(dataset_summary[fraud_records]), SUM(dataset_summary[total_records]), 0) * 100

Best PR-AUC = MAX(model_comparison[pr_auc])
Best F1 Score = MAX(model_comparison[f1_score])
Lowest Log Loss = MIN(model_comparison[log_loss])
Top Performing Model = CONCATENATEX(TOPN(1, model_comparison, model_comparison[pr_auc], DESC), model_comparison[model_name], ", ")

Minimum Operational Loss = MIN(threshold_analysis[total_operational_cost])
Optimal Threshold = MAXX(TOPN(1, threshold_analysis, threshold_analysis[total_operational_cost], ASC), threshold_analysis[threshold])
```

---

## 3. Dashboard Page Design (`FraudGuard_Dashboard.pbip`)

1. **Page 1: Fraud Overview** — Dataset slicer, KPI cards (`Total Transactions`, `Legitimate`, `Fraud Cases`, `Fraud Prevalence (%)`), partition distribution bars (`Train / Val / Test`), and `dataset_summary` schema grid.
2. **Page 2: Fraud Pattern Analysis** — Mean & StdDev Amount by Class, Maximum Amount by Class, Transaction Amount table, and Data Quality Missingness audit table.
3. **Page 3: Model Performance Comparison** — Dataset & Classifier slicers, KPI cards (`Top PR-AUC Classifier`, `Best PR-AUC`, `Lowest Log Loss`), clustered bar comparisons across Precision/Recall/F1/ROC-AUC/PR-AUC, Binary Log Loss chart, and full evaluation scorecard.
4. **Page 4: Risk & Decision Threshold Analysis** — Cost-optimal KPI cards (`Minimum Operational Loss`, `Optimal Threshold`), dual line charts (Precision/Recall/F1 frontier & Financial Loss Curve under `$10 FP / $500 FN`), and full threshold sensitivity table.
5. **Page 5: Cross-Dataset Comparison** — Cross-dataset PR-AUC and F1-Score comparisons grouped by `dataset_name` and validation hyperparameter tuning table.
