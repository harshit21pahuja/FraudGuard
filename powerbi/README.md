# Power BI Dashboard Specification — FraudGuard

## Overview
This directory stores documentation and verified pipeline export files intended for ingestion by Microsoft Power BI Desktop.

## Academic & Engineering Rules
1. **Zero Fabrication**: All tables imported into Power BI must be direct exports produced by the PySpark pipeline from real held-out model evaluations and data summaries.
2. **PBIX File Reality**: A `.pbix` file is not claimed until it is actually generated and placed in this repository.

## Proposed Dashboard Pages
1. **Page 1: Fraud Overview**
   - Total transaction volume, fraud count, genuine count, fraud prevalence rate (%).
   - Missing value indicators and join quality summary.
2. **Page 2: Fraud Pattern Analysis**
   - Fraud distribution by transaction amount, transaction time/hour, and high-risk categorical groupings (e.g., ProductCD, card types).
3. **Page 3: Model Performance Comparison**
   - Comparative metrics across all 5 Spark ML models: Precision, Recall, F1-Score, ROC-AUC, PR-AUC.
   - Interactive model slicer and confusion matrix visualizer.
4. **Page 4: Risk & Decision Threshold Analysis**
   - Threshold trade-off curve (Precision vs. Recall vs. Threshold).
   - False Positive vs. False Negative count simulation across decision thresholds (0.05 to 0.95).
   - Flagged alert volume vs. fraud detection capture rate.
5. **Page 5: Cross-Dataset Comparison & Academic Synthesis**
   - Side-by-side comparison of Dataset A (IEEE-CIS) and Dataset B.
   - Documentation of structural differences, collection contexts, and methodological boundaries.

## Export Schema Plan (CSV/Parquet)
The Spark pipeline will export:
- `powerbi/data/model_comparison.csv`: Final evaluation metrics per model and dataset.
- `powerbi/data/threshold_analysis.csv`: Threshold scan metrics (Precision, Recall, F1, FP, FN, Alert Rate).
- `powerbi/data/dataset_summary.csv`: Aggregated overview metrics (Total rows, Fraud %, Missingness).
- `powerbi/data/confusion_matrices.csv`: TP, FP, TN, FN breakdowns per classifier.
