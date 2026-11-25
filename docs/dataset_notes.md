# Dataset Documentation & Assessment Notes

## Dataset A: IEEE-CIS Fraud Detection (Primary)
- **Source**: Kaggle / Vesta Corporation (`https://www.kaggle.com/competitions/ieee-fraud-detection/data`)
- **Nature**: Genuine real-world e-commerce transaction data provided by Vesta Corp.
- **Files**:
  - `train_transaction.csv`: 590,540 rows, 394 columns. Contains transaction amount, product code, card information, purchaser/recipient email domains, and engineered risk attributes (`C1-C14`, `D1-D15`, `V1-V339`).
  - `train_identity.csv`: 144,233 rows, 41 columns. Contains device info, browser info, OS, and identity markers for a subset of transactions.
- **Target Column**: `isFraud` (Binary: 0 = legitimate, 1 = fraudulent). Label distribution in training data is ~3.5% fraud.
- **Join Key**: `TransactionID`.
  - Identity information is present for only ~24.4% of transactions (transactions without identity markers represent guest checkouts or devices without telemetry).
  - Validation rule: Must perform left outer join from transaction to identity; inner join would discard 75% of transaction data and bias the sample.
- **Licensing**: Competition terms permit academic and educational research use.
- **Security Rule**: Raw CSV files must remain in `.gitignore` and never committed to Git.

---

## Dataset B (Finalized): Credit Card Fraud Detection (European Cardholders — ULB)
- **Status**: **Approved & Finalized** (`data/raw/dataset_b/creditcard.csv`, 141.81 MB)
- **Source**: Université Libre de Bruxelles (ULB) Machine Learning Group / OpenML ID 1597 (`https://www.openml.org/d/1597`, mirror of `https://www.kaggle.com/datasets/mlg-ulb/creditcardfraud`)
- **Nature**: **100% Real-world**. Real credit card transactions made by European cardholders in September 2013 over a two-day period.
- **Structure**:
  - Rows: 284,807 transactions.
  - Features: 29 numerical input features in the OpenML 1597 export: `Amount` and 28 principal components (`V1` to `V28`) obtained via PCA for confidentiality (the raw `Time` index is omitted as an ignore-attribute in OpenML 1597).
  - Target Column: `Class` (0 = legitimate, 1 = fraudulent).
- **Class Balance**: 492 fraud cases out of 284,807 transactions (0.1727% fraud prevalence — extreme imbalance, 284,315 legitimate).
- **Licensing**: Open Database License (ODbL) / Public. Free for academic and research use.
- **Why It Is Ideal**:
  - **Academic Rigor**: Gold-standard benchmark in financial fraud literature (cited in >2,000 papers).
  - **Complementary Contrast**: Contrasts sharply with Dataset A (dense numerical PCA features with zero missing values and 0.1727% fraud vs. high-dimensional heterogeneous e-commerce metadata with categorical variables, missing values, and ~3.5% fraud).
  - **Spark Fit**: Clean, highly reproducible, runs smoothly on PySpark without massive disk overhead.

### Rejected Alternatives (Documented for Provenance)
- **Bank Account Fraud (BAF) Suite (NeurIPS 2022)**: Semi-synthetic tabular benchmark (~1.1% fraud rate); deferred in favor of 100% observed real transactions.
- **PaySim (Mobile Money Simulation)**: 100% synthetic simulation; excluded per faculty preference for real-world datasets.
