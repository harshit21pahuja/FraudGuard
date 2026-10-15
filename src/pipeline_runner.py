"""FraudGuard Master Pipeline Runner.

Orchestrates ingestion, feature engineering, training of 5 Spark ML models,
held-out evaluation, threshold risk analysis, figure generation, and Power BI exports.
"""

import argparse
import sys
import time
from pathlib import Path
from typing import Any, Dict, List
import logging

import pandas as pd

from src.utils.config import get_project_root, load_config
from src.utils.spark_utils import get_spark_session
from src.data.loader import (
    perform_ieee_cis_join,
    time_aware_split,
    validate_target_distribution,
)
from src.data.mock_generator import generate_mock_ieee_cis_data
from src.features.engineering import (
    build_spark_ml_feature_pipeline,
    identify_column_types,
)
from src.models.trainer import train_model
from src.evaluation.metrics import evaluate_predictions
from src.risk.thresholds import scan_decision_thresholds
from src.evaluation.visualizations import (
    plot_confusion_matrices_grid,
    plot_model_comparison,
    plot_threshold_curves,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("FraudGuard.MasterPipeline")


def run_pipeline(
    dataset_key: str = "dataset_a",
    force_mock: bool = False,
    mock_samples: int = 500,
) -> Dict[str, Any]:
    """Execute the full end-to-end Big Data & ML pipeline.

    Args:
        dataset_key: Key in configs/project_config.yaml (e.g., 'dataset_a').
        force_mock: If True, uses synthetic mock data even if raw files exist.
        mock_samples: Row count for synthetic sample generation.

    Returns:
        Dictionary containing data summaries, evaluation metrics, and export paths.
    """
    total_start = time.time()
    root = get_project_root()
    config = load_config()

    logger.info("=" * 70)
    logger.info("FRAUDGUARD: Cross-Dataset Financial Fraud Detection & Risk Analytics")
    logger.info("Initializing Master Pipeline Execution")
    logger.info("=" * 70)

    # 1. Initialize Apache Spark
    spark = get_spark_session(config)
    logger.info(f"Apache Spark Session active: Version {spark.version}")

    # 2. Data Ingestion
    cfg_a = config.get("datasets", {}).get(dataset_key, {})
    raw_dir = root / cfg_a.get("raw_dir", "data/raw/ieee_cis")
    trans_file = raw_dir / cfg_a.get("transaction_file", "train_transaction.csv")
    ident_file = raw_dir / cfg_a.get("identity_file", "train_identity.csv")
    target_col = cfg_a.get("target_column", "isFraud")
    time_col = cfg_a.get("time_column", "TransactionDT")

    if not force_mock and trans_file.exists():
        logger.info(f"Ingesting raw transactions from: {trans_file}")
        trans_df = spark.read.csv(str(trans_file), header=True, inferSchema=True)
        if ident_file.exists():
            logger.info(f"Ingesting raw identity data from: {ident_file}")
            ident_df = spark.read.csv(str(ident_file), header=True, inferSchema=True)
            full_df = perform_ieee_cis_join(trans_df, ident_df, join_key="TransactionID")
        else:
            full_df = trans_df
    else:
        logger.info(
            f"Raw dataset files not found at {raw_dir}. "
            f"Using realistic sample generator ({mock_samples} records, ~4% fraud rate)..."
        )
        full_df = generate_mock_ieee_cis_data(
            spark, num_records=mock_samples, fraud_rate=0.04, seed=config.get("project", {}).get("random_seed", 42)
        )

    # 3. Target Distribution Validation
    target_stats = validate_target_distribution(full_df, target_col=target_col)
    logger.info(f"Target Validation: {target_stats}")

    # 4. Leakage-Free Time-Aware Split
    train_ratio = cfg_a.get("train_ratio", 0.70)
    val_ratio = cfg_a.get("val_ratio", 0.15)
    test_ratio = cfg_a.get("test_ratio", 0.15)

    train_df, val_df, test_df = time_aware_split(
        full_df,
        time_col=time_col,
        train_ratio=train_ratio,
        val_ratio=val_ratio,
        test_ratio=test_ratio,
    )

    # Cache split DataFrames for optimal performance
    train_df.cache()
    val_df.cache()
    test_df.cache()

    # 5. Feature Engineering Pipeline
    num_cols, cat_cols, dropped_cols = identify_column_types(
        train_df, target_col=target_col, id_col="TransactionID", time_col=time_col
    )
    feature_pipeline = build_spark_ml_feature_pipeline(num_cols, cat_cols, apply_scaling=True)

    logger.info("Fitting Spark ML Pipeline strictly on training split (train_df)...")
    pipeline_fit_start = time.time()
    pipeline_model = feature_pipeline.fit(train_df)
    logger.info(f"Feature Pipeline fitted in {round(time.time() - pipeline_fit_start, 2)}s.")

    # Transform all three splits
    train_prep = pipeline_model.transform(train_df).withColumnRenamed(target_col, "label")
    val_prep = pipeline_model.transform(val_df).withColumnRenamed(target_col, "label")
    test_prep = pipeline_model.transform(test_df).withColumnRenamed(target_col, "label")

    train_prep.cache()
    test_prep.cache()

    # 6. Model Training & Held-Out Evaluation (5 Classifiers)
    classifiers = [
        "logistic_regression",
        "decision_tree",
        "random_forest",
        "gbt",
        "linear_svc",
    ]
    model_configs = config.get("models", {})
    metrics_records: List[Dict[str, Any]] = []
    trained_models: Dict[str, Any] = {}

    logger.info("=" * 70)
    logger.info("TRAINING & EVALUATION OF 5 SPARK ML CLASSIFIERS")
    logger.info("=" * 70)

    for m_name in classifiers:
        cfg = model_configs.get(m_name, {})
        fitted_model, train_duration = train_model(m_name, train_prep, model_config=cfg)
        trained_models[m_name] = fitted_model

        # Evaluate on held-out test split
        preds = fitted_model.transform(test_prep)
        eval_metrics = evaluate_predictions(preds, model_name=m_name)
        eval_metrics["training_time_sec"] = train_duration
        metrics_records.append(eval_metrics)

    results_df = pd.DataFrame(metrics_records)
    print("\n--- Held-Out Test Evaluation Summary ---")
    print(results_df[["model_name", "precision", "recall", "f1_score", "roc_auc", "pr_auc", "training_time_sec"]].to_string(index=False))

    # 7. Decision Threshold & Operational Risk Analysis
    # Use best probability-outputting model (e.g. Random Forest or GBT)
    logger.info("=" * 70)
    logger.info("OPERATIONAL RISK & DECISION THRESHOLD ANALYSIS")
    logger.info("=" * 70)

    risk_cfg = config.get("risk_analysis", {})
    prob_model_name = "random_forest"
    rf_preds = trained_models[prob_model_name].transform(test_prep)

    threshold_records = scan_decision_thresholds(
        rf_preds,
        min_thresh=risk_cfg.get("threshold_min", 0.05),
        max_thresh=risk_cfg.get("threshold_max", 0.95),
        step=risk_cfg.get("threshold_step", 0.05),
        cost_fp=10.0,
        cost_fn=500.0,
    )
    threshold_df = pd.DataFrame(threshold_records)
    print("\n--- Decision Threshold Scan (First 5 Points) ---")
    print(threshold_df[["threshold", "precision", "recall", "f1_score", "false_positives", "false_negatives", "total_operational_cost"]].head(5).to_string(index=False))

    # 8. Export Verified CSVs for Power BI & University Report
    logger.info("Exporting verified analytical summaries for Power BI Desktop...")
    out_cfg = config.get("outputs", {})
    metrics_dir = root / out_cfg.get("metrics_dir", "outputs/metrics")
    summaries_dir = root / out_cfg.get("summaries_dir", "outputs/summaries")
    figures_dir = root / out_cfg.get("figures_dir", "outputs/figures")
    powerbi_dir = root / out_cfg.get("powerbi_dir", "powerbi/data")

    for d in (metrics_dir, summaries_dir, figures_dir, powerbi_dir):
        d.mkdir(parents=True, exist_ok=True)

    # Save metrics tables
    results_df.to_csv(metrics_dir / "model_comparison.csv", index=False)
    results_df.to_csv(powerbi_dir / "model_comparison.csv", index=False)

    threshold_df.to_csv(summaries_dir / "threshold_analysis.csv", index=False)
    threshold_df.to_csv(powerbi_dir / "threshold_analysis.csv", index=False)

    # Save dataset overview summary
    overview_df = pd.DataFrame([
        {
            "dataset_name": cfg_a.get("name", "IEEE-CIS Fraud Detection"),
            "total_records": target_stats["total_records"],
            "legitimate_records": target_stats["legitimate_count"],
            "fraud_records": target_stats["fraud_count"],
            "fraud_prevalence_pct": target_stats["fraud_prevalence_pct"],
            "train_records": train_df.count(),
            "val_records": val_df.count(),
            "test_records": test_df.count(),
            "numerical_features": len(num_cols),
            "categorical_features": len(cat_cols),
        }
    ])
    overview_df.to_csv(summaries_dir / "dataset_summary.csv", index=False)
    overview_df.to_csv(powerbi_dir / "dataset_summary.csv", index=False)

    # 9. Generate Publication-Quality Visualizations
    logger.info("Generating academic report figures in outputs/figures/...")
    plot_model_comparison(results_df, figures_dir / "model_comparison_bar_chart.png")
    plot_threshold_curves(threshold_df, figures_dir / "threshold_tradeoffs.png")
    plot_confusion_matrices_grid(results_df, figures_dir / "confusion_matrices_grid.png")

    total_time = round(time.time() - total_start, 2)
    logger.info("=" * 70)
    logger.info(f"FRAUDGUARD MASTER PIPELINE COMPLETED IN {total_time} SECONDS")
    logger.info("All metrics, threshold scans, figures, and Power BI tables successfully exported.")
    logger.info("=" * 70)

    return {
        "status": "SUCCESS",
        "runtime_seconds": total_time,
        "models_evaluated": len(classifiers),
        "results": results_df.to_dict(orient="records"),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run FraudGuard Master Pipeline")
    parser.add_argument("--force-mock", action="store_true", help="Force synthetic sample generation")
    parser.add_argument("--samples", type=int, default=500, help="Mock sample size")
    args = parser.parse_args()

    run_pipeline(force_mock=args.force_mock, mock_samples=args.samples)
