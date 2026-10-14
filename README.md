# FraudGuard: Cross-Dataset Financial Fraud Detection and Risk Analytics Using Apache Spark and Machine Learning

**Course**: CSET371 — Big Data Analytics and Business Intelligence  
**Institution**: Bennett University, Greater Noida  
**Domain**: FinTech, Financial Fraud Detection, Big Data Analytics, Machine Learning, Business Intelligence  

---

## 1. Project Team
| Name | Enrollment No. | Proposed Responsibilities |
| :--- | :--- | :--- |
| **Harshit Pahuja** | S24CSEU0736 | Project Coordination, PySpark Pipeline, Preprocessing, Feature Engineering, Integration |
| **Rachit Nain** | S24CSEU2646 | Dataset Validation, Exploratory Data Analysis, Visualization, Fraud Pattern Analysis |
| **Man Mohan Gaur** | S24CSEU2012 | Spark ML Model Implementation, Training, Evaluation, Model Comparison |
| **Kunal Sehrawat** | S24CSEU2638 | Risk & Threshold Analysis, Error Analysis, Power BI Dashboard |
| **Bhumi Jindal** | S24CSEU0884 | Literature Review, Existing-System Analysis, Research Gap, Report & Presentation |

---

## 2. Project Overview & Scope
FraudGuard is an offline, big data decision-support system designed to detect fraudulent financial transactions across heterogeneous datasets. Built on **Apache Spark (PySpark)** and **Spark ML**, the system processes high-volume transaction records, trains 5 machine learning classifiers, rigorously evaluates performance on imbalanced data, models operational risk trade-offs (False Positives vs. False Negatives), and exports verified analytical summaries for an interactive **Microsoft Power BI** dashboard.

> **Academic Notice**: FraudGuard is an academic decision-support prototype. It does not claim real-time streaming detection or live banking production deployment.

---

## 3. Technology Stack
- **Language**: Python 3.10+ / 3.11+
- **Big Data Processing**: Apache Spark / PySpark (Spark DataFrames)
- **Machine Learning**: Spark ML (`pyspark.ml`)
- **Visual Analytics**: Matplotlib, Seaborn
- **Business Intelligence**: Microsoft Power BI Desktop
- **Configuration & Reproducibility**: YAML, PyTest, Git / GitHub

---

## 4. Required Machine Learning Classifiers
All models are implemented using native Spark ML APIs (`pyspark.ml`):
1. **Logistic Regression** (`pyspark.ml.classification.LogisticRegression`)
2. **Decision Tree Classifier** (`pyspark.ml.classification.DecisionTreeClassifier`)
3. **Random Forest Classifier** (`pyspark.ml.classification.RandomForestClassifier`)
4. **Gradient-Boosted Trees** (`pyspark.ml.classification.GBTClassifier`)
5. **Linear Support Vector Machine** (`pyspark.ml.classification.LinearSVC`)

---

## 5. Repository Structure
```
FraudGuard/
├── README.md                           # Master Project Documentation
├── requirements.txt                    # Python Dependencies
├── .gitignore                          # Git Ignore (data, logs, venv, secrets)
├── configs/
│   └── project_config.yaml             # Central Project Configuration
├── data/
│   ├── raw/                            # Raw CSV files (IEEE-CIS, Dataset B)
│   ├── interim/                        # Cleaned joins & intermediate Parquet files
│   └── processed/                      # Preprocessed feature vectors for training
├── notebooks/                          # Interactive analysis & Colab-compatible notebooks
├── src/                                # Modular PySpark Source Code
│   ├── data/                           # Data ingestion & schema validation
│   ├── features/                       # Spark ML feature pipelines & encoders
│   ├── models/                         # Model training routines (5 classifiers)
│   ├── evaluation/                     # Metrics (Precision, Recall, F1, ROC/PR-AUC)
│   ├── risk/                           # Threshold scanning & cost analysis
│   └── utils/                          # Spark session builder & logging
├── tests/                              # PyTest unit and integration tests
├── outputs/
│   ├── metrics/                        # Raw metric JSON/CSV exports
│   ├── figures/                        # High-resolution evaluation plots
│   ├── summaries/                      # Aggregate tables
│   └── logs/                           # Spark and run logs
├── powerbi/
│   ├── README.md                       # Power BI Dashboard Specification & Visual Plan
│   └── data/                           # Exported clean CSVs for Power BI import
└── docs/
    ├── architecture.md                 # System Architecture & Spark DAG
    ├── methodology.md                  # Academic Evaluation & Metric Foundations
    └── dataset_notes.md                # Dataset A & B Assessment and Provenance
```

---

## 6. Development Workflow & Implementation Phases
- **Phase 1: Workspace Audit & Planning** *(Completed)*
- **Phase 2: Environment & Dataset Validation** *(In Progress)*
- **Phase 3: Data Ingestion & Preprocessing Pipeline**
- **Phase 4: Spark ML Model Training & Threshold Risk Analysis**
- **Phase 5: Power BI Export & Dashboard Generation**
- **Phase 6: Testing, Academic Report & Viva Defense Preparation**
