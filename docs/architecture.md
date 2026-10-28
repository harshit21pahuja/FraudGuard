# FraudGuard System Architecture

## 1. System Overview
FraudGuard is an offline big data analytics and machine learning decision-support system designed to ingest, clean, transform, and evaluate financial transactions for fraud detection using **Apache Spark / PySpark**.

```
+-------------------------------------------------------------+
|                     Data Ingestion Layer                    |
|  - IEEE-CIS (Transaction & Identity CSVs)                   |
|  - Dataset B (e.g. ULB European Cardholders CSV)             |
+-------------------------------------------------------------+
                              |
                              v
+-------------------------------------------------------------+
|              Spark Validation & Cleaning Layer              |
|  - Schema enforcement, null analysis, join-key integrity    |
|  - Duplicate checks & target validation                     |
+-------------------------------------------------------------+
                              |
                              v
+-------------------------------------------------------------+
|         Spark ML Feature Engineering & Pipeline Layer       |
|  - StringIndexer, OneHotEncoderEstimator                    |
|  - VectorAssembler, Imputer, StandardScaler                 |
|  - Leakage-free fit on Training split only                  |
+-------------------------------------------------------------+
                              |
                              v
+-------------------------------------------------------------+
|              Model Training & Optimization Layer            |
|  - Logistic Regression (Spark ML Baseline)                  |
|  - Random Forest Classifier (Spark ML Ensemble Baseline)     |
|  - XGBoost Classifier (Advanced Gradient Boosting)          |
|  - LightGBM Classifier (Advanced Gradient Boosting)         |
|  - CatBoost Classifier (Advanced Gradient Boosting)         |
+-------------------------------------------------------------+
                              |
                              v
+-------------------------------------------------------------+
|          Evaluation, Verification & Risk Analysis           |
|  - Precision, Recall, F1, ROC-AUC, PR-AUC, Confusion Matrix |
|  - Threshold simulation (FP vs FN cost trade-offs)          |
|  - Verified metrics exported to CSV/Parquet                 |
+-------------------------------------------------------------+
                              |
                              v
+-------------------------------------------------------------+
|                 Business Intelligence Layer                 |
|  - Microsoft Power BI Desktop (Interactive Dashboards)      |
|  - Academic Report Figures & Tables                         |
+-------------------------------------------------------------+
```

## 2. Spark Pipeline Design Principles
- **Lazy Evaluation & Partitioning**: Spark DataFrames utilize catalyst optimization and shuffle partitioning configured to resource capacity (`local[*]` or cluster nodes).
- **Strict Leakage Prevention**: Preprocessing transformers (imputers, scalers, indexers) are fitted strictly on `train_df`. Validation and test splits are transformed using the fitted pipeline models.
- **Hybrid Boosting Integration**: To execute XGBoost, LightGBM, and CatBoost on Windows without JVM/Maven worker deadlocks, a normalized `BoostedSparkModelWrapper` converts Spark vector features into predictions and returns Spark DataFrames with standard schema (`rawPrediction`, `probability`, `prediction`), maintaining seamless interoperability with PySpark's `BinaryClassificationEvaluator`.
- **Memory Management**: Intermediate clean joins are persisted as Parquet files to eliminate redundant CSV re-parsing and re-computation.
