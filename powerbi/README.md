# FraudGuard Business Intelligence Module (`powerbi/`)

This module integrates batch PySpark fraud detection outputs into an interactive **5-page Microsoft Power BI Desktop** dashboard (`FraudGuard_Dashboard.pbip`).

## Directory Structure
```text
powerbi/
├── data/                            # Consolidated CSV data marts exported by pipeline_runner.py
│   ├── dataset_summary.csv          # Total, legitimate, fraud, split & feature counts per dataset
│   ├── model_comparison.csv         # Precision, Recall, F1, ROC-AUC, PR-AUC, Log Loss, CM & runtime
│   ├── threshold_analysis.csv       # 0.05–0.95 probability sweep with FP/FN financial loss ($)
│   ├── hyperparameter_tuning.csv    # Validation-split PR-AUC selection records
│   ├── amount_distribution.csv      # Class-wise transaction amount statistics
│   ├── missingness_profile.csv      # Column-level null profiling
│   └── *.csv (optional Dataset A)   # hourly_fraud_pattern.csv, fraud_by_product.csv, fraud_by_card.csv
├── FraudGuard_Dashboard.pbip        # 5-page Power BI Project (TMDL SemanticModel + PBIR 2.0.0 Report)
├── FraudGuard_Dashboard.SemanticModel/
├── FraudGuard_Dashboard.Report/
├── powerbi_setup_guide.md           # Full Semantic Model, DAX measures & 5-page layout specification
└── README.md
```

## Refreshing Data in Power BI Desktop
1. Execute the PySpark pipeline (`python -m src.pipeline_runner --dataset all`) to refresh all CSV tables in `powerbi/data/`.
2. Open `powerbi/FraudGuard_Dashboard.pbip` in **Microsoft Power BI Desktop (2.159+)**.
3. Click **Home -> Refresh** in Power BI Desktop to reload updated CSV marts into the star-schema semantic model and save `.pbix` if required for submission.
