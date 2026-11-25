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
- **Log Loss (Binary Cross-Entropy)**: $-\frac{1}{N}\sum_{i=1}^{N}\left[y_i \log(\hat{p}_i) + (1-y_i)\log(1-\hat{p}_i)\right]$ — Evaluates probability calibration across classifiers.

## 4. Final Machine Learning Model Suite
Following academic guidance and faculty review, FraudGuard implements a structured comparison across five distinct classification paradigms:

| Model | Role in FraudGuard | Academic & Technical Rationale |
| :--- | :--- | :--- |
| **Logistic Regression** | Baseline | Provides a simple, interpretable linear reference for comparison against non-linear architectures. |
| **Random Forest** | Ensemble baseline | Captures complex non-linear feature interactions through bagging of unpruned decision trees. |
| **XGBoost** | Advanced boosting | State-of-the-art extreme gradient boosting with regularized objectives, highly effective on structured transaction features. |
| **LightGBM** | Advanced boosting | High-performance gradient boosting using histogram-based algorithms and leaf-wise tree splitting. |
| **CatBoost** | Advanced boosting | Robust symmetric (oblivious) trees with native handling of categorical relationships and resistance to overfitting. |

*Obsolete Candidates*: Standalone Decision Tree, generic Spark GBTClassifier, and LinearSVC were retired from the final evaluation suite to emphasize modern gradient-boosting algorithms.

## 5. Decision Threshold & Operational Risk Analysis
Classifiers default to an arbitrary 0.5 probability decision threshold. In real-world fraud operations:
- Lowering the threshold (e.g., 0.15) increases Recall (catches more fraud) at the expense of Precision (more customer friction and review costs).
- Raising the threshold (e.g., 0.75) prioritizes Precision (fewer false alerts) at the expense of Recall (higher fraud write-offs).

FraudGuard explicitly scans decision thresholds in steps of 0.05 across calibrated probability models (Logistic Regression, Random Forest, XGBoost, LightGBM, CatBoost) using an asymmetric cost matrix ($C_{FP} = \$10$, $C_{FN} = \$500$) to identify the operational cost-minimizing operating point.

## 6. Cross-Dataset Comparison Boundaries
- Models trained on Dataset A cannot be directly evaluated on Dataset B without schema alignment, nor can metrics be merged naively.
- Cross-dataset analysis is conducted at the **methodological level**: comparing how tree-based vs. linear classifiers perform across differing degrees of class imbalance, feature granularity, and data representations once Dataset B is finalized.
