"""Decision-threshold scanning, operational risk trade-offs, and cost curves."""

from typing import Any, Dict, List
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("FraudGuard.Risk")

try:
    from pyspark.ml.functions import vector_to_array
    from pyspark.sql import DataFrame
    from pyspark.sql import functions as F
    PYSPARK_AVAILABLE = True
except ImportError:
    DataFrame = None  # type: ignore
    PYSPARK_AVAILABLE = False


def scan_decision_thresholds(
    predictions: DataFrame,
    prob_col: str = "probability",
    label_col: str = "label",
    min_thresh: float = 0.05,
    max_thresh: float = 0.95,
    step: float = 0.05,
    cost_fp: float = 10.0,
    cost_fn: float = 500.0,
) -> List[Dict[str, Any]]:
    """Scan classification decision thresholds from min_thresh to max_thresh.

    Evaluates the trade-off between False Positives (customer friction) and
    False Negatives (financial losses) for models providing calibrated probabilities.

    Args:
        predictions: DataFrame containing probability vector and true label.
        prob_col: Vector column containing class probabilities [P(0), P(1)].
        label_col: Ground-truth label column.
        min_thresh: Lowest threshold to scan.
        max_thresh: Highest threshold to scan.
        step: Increment step.
        cost_fp: Nominal operational cost of one false positive alert (e.g., $10 manual review).
        cost_fn: Direct loss associated with one missed fraud transaction (e.g., $500).

    Returns:
        List of dicts representing threshold performance records.
    """
    if prob_col not in predictions.columns:
        raise ValueError(
            f"Probability column '{prob_col}' not found. "
            "Ensure the model supports calibrated probability outputs."
        )

    # Extract probability of positive class (fraud = index 1)
    df_prob = predictions.withColumn("fraud_prob", vector_to_array(F.col(prob_col))[1])
    total_records = df_prob.count()

    results: List[Dict[str, Any]] = []
    current_thresh = min_thresh

    logger.info(
        f"Scanning decision thresholds from {min_thresh} to {max_thresh} (step={step})..."
    )

    while current_thresh <= (max_thresh + 1e-6):
        t = round(current_thresh, 2)
        # Classify with threshold t
        pred_df = df_prob.withColumn(
            "threshold_pred",
            F.when(F.col("fraud_prob") >= t, 1).otherwise(0),
        )

        counts = (
            pred_df.groupBy(label_col, "threshold_pred")
            .count()
            .collect()
        )

        tp = tn = fp = fn = 0
        for row in counts:
            lbl = int(row[label_col])
            pred = int(row["threshold_pred"])
            cnt = int(row["count"])
            if lbl == 1 and pred == 1:
                tp = cnt
            elif lbl == 0 and pred == 0:
                tn = cnt
            elif lbl == 0 and pred == 1:
                fp = cnt
            elif lbl == 1 and pred == 0:
                fn = cnt

        precision = round(tp / (tp + fp), 4) if (tp + fp) > 0 else 0.0
        recall = round(tp / (tp + fn), 4) if (tp + fn) > 0 else 0.0
        f1 = (
            round(2 * (precision * recall) / (precision + recall), 4)
            if (precision + recall) > 0
            else 0.0
        )
        flagged_volume = tp + fp
        alert_rate = round((flagged_volume / total_records) * 100, 2) if total_records > 0 else 0.0
        total_operational_cost = round((fp * cost_fp) + (fn * cost_fn), 2)

        results.append(
            {
                "threshold": t,
                "precision": precision,
                "recall": recall,
                "f1_score": f1,
                "true_positives": tp,
                "false_positives": fp,
                "true_negatives": tn,
                "false_negatives": fn,
                "flagged_volume": flagged_volume,
                "alert_rate_pct": alert_rate,
                "total_operational_cost": total_operational_cost,
            }
        )

        current_thresh += step

    logger.info(f"Threshold scan completed for {len(results)} decision points.")
    return results
