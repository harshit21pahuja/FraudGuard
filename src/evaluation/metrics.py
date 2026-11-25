"""Evaluation metrics, loss functions, and confusion matrix calculations."""

import logging
from typing import Any, Dict, Tuple

import numpy as np

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("FraudGuard.Evaluation")

try:
    from pyspark.ml.evaluation import BinaryClassificationEvaluator
    from pyspark.ml.functions import vector_to_array
    from pyspark.sql import DataFrame
    from pyspark.sql import functions as F
    PYSPARK_AVAILABLE = True
except ImportError:
    DataFrame = None  # type: ignore
    BinaryClassificationEvaluator = None  # type: ignore
    PYSPARK_AVAILABLE = False


def calculate_confusion_matrix(
    predictions: DataFrame,
    label_col: str = "label",
    prediction_col: str = "prediction",
) -> Dict[str, int]:
    """Calculate exact Confusion Matrix (TP, TN, FP, FN) from genuine predictions."""
    counts = (
        predictions.groupBy(label_col, prediction_col)
        .count()
        .collect()
    )

    matrix = {"tp": 0, "tn": 0, "fp": 0, "fn": 0}
    for row in counts:
        lbl = int(row[label_col])
        pred = int(row[prediction_col])
        cnt = int(row["count"])

        if lbl == 1 and pred == 1:
            matrix["tp"] = cnt
        elif lbl == 0 and pred == 0:
            matrix["tn"] = cnt
        elif lbl == 0 and pred == 1:
            matrix["fp"] = cnt
        elif lbl == 1 and pred == 0:
            matrix["fn"] = cnt

    return matrix


def extract_roc_pr_arrays(
    predictions: DataFrame,
    label_col: str = "label",
    prob_col: str = "probability",
) -> Tuple[np.ndarray, np.ndarray]:
    """Collect ground-truth binary labels and positive-class probabilities as NumPy arrays."""
    rows = predictions.select(
        F.col(label_col).cast("int").alias("y"),
        vector_to_array(F.col(prob_col))[1].alias("p"),
    ).collect()
    y_true = np.array([int(r["y"]) for r in rows], dtype=np.int32)
    y_prob = np.array([float(r["p"]) for r in rows], dtype=np.float64)
    return y_true, y_prob


def compute_binary_log_loss(y_true: np.ndarray, y_prob: np.ndarray) -> float:
    """Compute binary cross-entropy loss (Log Loss) from probability predictions."""
    if len(y_true) == 0:
        return 0.0
    p = np.clip(y_prob, 1e-15, 1.0 - 1e-15)
    loss = -np.mean(y_true * np.log(p) + (1.0 - y_true) * np.log(1.0 - p))
    return round(float(loss), 5)


def evaluate_predictions(
    predictions: DataFrame,
    model_name: str,
    label_col: str = "label",
    prediction_col: str = "prediction",
    has_raw_predictions: bool = True,
) -> Dict[str, Any]:
    """Calculate comprehensive evaluation metrics for imbalanced financial fraud detection.

    Returns:
      - Precision, Recall, F1-Score
      - ROC-AUC, PR-AUC (Precision-Recall Area Under Curve)
      - Log Loss (Binary Cross-Entropy Loss Function)
      - Accuracy (Supplementary)
      - Confusion Matrix: TP, TN, FP, FN
    """
    matrix = calculate_confusion_matrix(predictions, label_col, prediction_col)
    tp = matrix["tp"]
    tn = matrix["tn"]
    fp = matrix["fp"]
    fn = matrix["fn"]
    total = tp + tn + fp + fn

    precision = round(tp / (tp + fp), 4) if (tp + fp) > 0 else 0.0
    recall = round(tp / (tp + fn), 4) if (tp + fn) > 0 else 0.0
    f1 = (
        round(2 * (precision * recall) / (precision + recall), 4)
        if (precision + recall) > 0
        else 0.0
    )
    accuracy = round((tp + tn) / total, 4) if total > 0 else 0.0

    roc_auc = 0.0
    pr_auc = 0.0
    log_loss = 0.0

    if has_raw_predictions and "rawPrediction" in predictions.columns:
        evaluator_roc = BinaryClassificationEvaluator(
            rawPredictionCol="rawPrediction",
            labelCol=label_col,
            metricName="areaUnderROC",
        )
        evaluator_pr = BinaryClassificationEvaluator(
            rawPredictionCol="rawPrediction",
            labelCol=label_col,
            metricName="areaUnderPR",
        )
        try:
            roc_auc = round(float(evaluator_roc.evaluate(predictions)), 4)
            pr_auc = round(float(evaluator_pr.evaluate(predictions)), 4)
        except Exception as e:
            logger.warning(f"Could not compute AUC metrics for {model_name}: {e}")

    if "probability" in predictions.columns:
        try:
            y_true, y_prob = extract_roc_pr_arrays(predictions, label_col=label_col)
            log_loss = compute_binary_log_loss(y_true, y_prob)
        except Exception as e:
            logger.warning(f"Could not compute log_loss for {model_name}: {e}")

    logger.info(
        f"Evaluation [{model_name}]: Precision={precision}, Recall={recall}, "
        f"F1={f1}, ROC-AUC={roc_auc}, PR-AUC={pr_auc}, LogLoss={log_loss}, "
        f"TP={tp}, FP={fp}, FN={fn}"
    )

    return {
        "model_name": model_name,
        "total_test_samples": total,
        "true_positives": tp,
        "true_negatives": tn,
        "false_positives": fp,
        "false_negatives": fn,
        "precision": precision,
        "recall": recall,
        "f1_score": f1,
        "roc_auc": roc_auc,
        "pr_auc": pr_auc,
        "log_loss": log_loss,
        "accuracy": accuracy,
    }
