# FraudGuard Methodology & Academic Foundations

## 1. Problem Framing
Financial fraud detection is an extreme class imbalance problem with non-stationary distributions, asymmetric error costs, and temporal dependency.
- **Cost of False Negatives (FN)**: Undetected fraud leading to direct financial loss and regulatory liability.
- **Cost of False Positives (FP)**: Legitimate transactions blocked, causing customer friction, lost interchange fees, and manual review overhead.

## 2. Train / Validation / Test Splitting Strategy
- **Temporal Split vs. Random Split**:
  - For Dataset A (IEEE-CIS), `TransactionDT` represents a continuous time delta (seconds). A temporal split (e.g., first 70% of time for training, middle 15% for validation, last 15% for testing) prevents temporal data leakage and mimics real-world forward testing.
  - For Dataset B (e.g. ULB Credit Card), if `Time` is available across a 48-hour window, stratified random splitting or time-ordered splitting can be compared.
- **Natural Test Distribution**: Resampling (e.g., undersampling or class weights) is applied strictly to the training split. Validation and test sets preserve the natural ground-truth fraud prevalence (e.g., ~3.5% for IEEE-CIS, ~0.17% for ULB) to ensure unbiased evaluation.

## 3. Evaluation Metrics in Imbalanced Classification
In extreme imbalance (e.g. 99.8% non-fraud), standard accuracy is a misleading metric (a naive classifier predicting all 0s achieves 99.8% accuracy but 0.0 recall).
- **Precision**: $\frac{TP}{TP + FP}$ — Proportion of flagged transactions that were genuine fraud.
- **Recall (Sensitivity)**: $\frac{TP}{TP + FN}$ — Proportion of total fraud caught by the model.
- **F1-Score**: Harmonic mean of Precision and Recall.
- **ROC-AUC**: Evaluates ranking capability across all possible thresholds; insensitive to class skew.
- **PR-AUC (Precision-Recall AUC)**: Highly sensitive to the positive (minority) class; critical for fraud benchmark comparisons.

## 4. Decision Threshold Analysis
Spark ML classifiers output raw predictions based on a default 0.5 probability threshold. In fraud operations:
- Lowering the threshold (e.g., 0.2) increases Recall (catches more fraud) at the expense of Precision (more False Positives).
- Raising the threshold (e.g., 0.8) prioritizes Precision (fewer false alerts) at the expense of Recall.
FraudGuard explicitly scans thresholds in steps of 0.05 across valid probability-producing models (Logistic Regression, Decision Tree, Random Forest, GBT) to map operational trade-off frontiers.
*Note on LinearSVC*: Spark's `LinearSVC` outputs raw margins ($w^T x + b$) rather than calibrated probabilities; threshold analysis on LinearSVC is based on margin shifts or Platt scaling where appropriate.

## 5. Cross-Dataset Comparison Boundaries
- Models trained on Dataset A cannot be directly evaluated on Dataset B without schema alignment, nor can metrics be merged naively.
- Cross-dataset analysis is conducted at the **methodological level**: comparing how tree-based vs. linear classifiers perform across differing degrees of class imbalance, feature granularity, and data representations.
