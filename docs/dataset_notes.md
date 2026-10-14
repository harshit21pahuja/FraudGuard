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

## Dataset B Candidates Assessment (Second Dataset)

### Candidate 1 (Recommended): Credit Card Fraud Detection (European Cardholders — ULB)
- **Source**: Université Libre de Bruxelles (ULB) Machine Learning Group / Kaggle (`https://www.kaggle.com/datasets/mlg-ulb/creditcardfraud`)
- **Nature**: **100% Real-world**. Real credit card transactions made by European cardholders in September 2013 over a two-day period.
- **Structure**:
  - Rows: 284,807 transactions.
  - Features: 30 numerical input features: `Time`, `Amount`, and 28 principal components (`V1` to `V28`) obtained via PCA for confidentiality.
  - Target Column: `Class` (0 = legitimate, 1 = fraudulent).
- **Class Balance**: 492 fraud cases out of 284,807 transactions (0.172% fraud prevalence — extreme imbalance).
- **Licensing**: Open Database License (ODbL). Free for academic and research use.
- **Why It Is Ideal**:
  - **Academic Rigor**: It is the gold-standard benchmark in financial fraud literature (cited in >2,000 papers).
  - **Complementary Contrast**: Perfectly contrasts with Dataset A (dense numerical PCA features vs. high-dimensional heterogeneous e-commerce metadata with categorical variables and missing values).
  - **Spark Fit**: Clean, highly reproducible, runs smoothly on PySpark without massive disk overhead.

### Candidate 2: Bank Account Fraud (BAF) Suite (NeurIPS 2022)
- **Source**: Feedzai Research / NeurIPS 2022 (`https://github.com/feedzai/bank-account-fraud`)
- **Nature**: Semi-synthetic realistic benchmark designed to study fraud detection with realistic fairness and temporal drift.
- **Structure**: 1,000,000 bank account opening applications, 32 tabular features.
- **Target**: `fraud_bool` (~1.1% fraud rate).
- **Assessment**: Excellent dataset, but semi-synthetic rather than purely observed real transactions.

### Candidate 3: PaySim (Mobile Money Simulation)
- **Source**: Kaggle (`https://www.kaggle.com/datasets/ealaxi/paysim1`)
- **Nature**: **100% Synthetic simulation** based on an agent-based simulator (PaySim) scaled from a sample of real financial logs.
- **Structure**: 6,362,620 rows, 11 columns.
- **Assessment**: Frequently used in undergraduate projects, but faculty explicitly requested prioritizing real-world data. If chosen, it must be labeled explicitly as synthetic.

**Recommendation**: Dataset B Candidate 1 (ULB European Cardholders) is the superior academic choice.
