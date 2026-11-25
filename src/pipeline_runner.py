"""FraudGuard Master Pipeline Runner.

Orchestrates cross-dataset ingestion, validation, Spark ML feature engineering,
validation tuning, held-out evaluation of 5 classifiers (LR, RF, XGBoost,
LightGBM, CatBoost), threshold risk optimization, publication figures, and
Power BI analytical CSV exports.
"""

import argparse
import inspect
import logging
import time
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd

from src.data.loader import (
    group_aware_stratified_split,
    inspect_and_validate_join,
    perform_ieee_cis_join,
    time_aware_split,
    validate_target_distribution,
)
from src.data.mock_generator import (
    generate_mock_creditcard_data,
    generate_mock_ieee_cis_data,
)
from src.evaluation.metrics import evaluate_predictions, extract_roc_pr_arrays
from src.evaluation.visualizations import (
    plot_confusion_matrices_grid,
    plot_cross_dataset_comparison,
    plot_eda_overview,
    plot_model_comparison,
    plot_roc_and_pr_curves,
    plot_threshold_curves,
)
from src.features.eda import export_eda_reports
from src.features.engineering import (
    build_spark_ml_feature_pipeline,
    identify_column_types,
)
from src.models.trainer import (
    extract_numpy_features,
    train_model,
    tune_classifier_on_validation,
)
from src.risk.thresholds import scan_decision_thresholds
from src.utils.config import get_project_root, load_config
from src.utils.spark_utils import get_spark_session

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("FraudGuard.MasterPipeline")

CLASSIFIERS = [
    "logistic_regression",
    "random_forest",
    "xgboost",
    "lightgbm",
    "catboost",
]


def _load_dataset_frame(
    spark: Any,
    root: Path,
    dataset_key: str,
    ds_cfg: Dict[str, Any],
    seed: int,
    force_mock: bool = False,
    mock_samples: int = 500,
    sample_fraction: float | None = None,
):
    """Ingest raw CSVs for dataset_a or dataset_b (or generate mock data if forced)."""
    raw_dir = root / ds_cfg.get("raw_dir", f"data/raw/{dataset_key}")
    trans_fname = ds_cfg.get("transaction_file")
    ident_fname = ds_cfg.get("identity_file")
    join_key = ds_cfg.get("join_key")
    target_col = ds_cfg.get("target_column")

    trans_file = (raw_dir / trans_fname) if trans_fname else None
    ident_file = (raw_dir / ident_fname) if ident_fname else None

    if force_mock:
        logger.info(f"[{dataset_key}] Using synthetic mock generator ({mock_samples} rows)...")
        if dataset_key == "dataset_b":
            return generate_mock_creditcard_data(spark, num_records=mock_samples, fraud_rate=0.05, seed=seed), True
        return generate_mock_ieee_cis_data(spark, num_records=mock_samples, fraud_rate=0.04, seed=seed), True

    if trans_file is None or not trans_file.exists():
        raise FileNotFoundError(
            f"[{dataset_key}] Raw dataset file missing at: {trans_file}\n"
            f"Run downloader or place raw CSV files in {raw_dir}, or pass --force-mock for smoke testing."
        )

    logger.info(f"[{dataset_key}] Ingesting real dataset from {trans_file}...")
    trans_df = spark.read.csv(str(trans_file), header=True, inferSchema=True)

    if sample_fraction is not None and 0 < sample_fraction < 1.0:
        logger.info(f"[{dataset_key}] Sampling {sample_fraction*100:.1f}% of rows for dev mode...")
        trans_df = trans_df.sample(withReplacement=False, fraction=sample_fraction, seed=seed)

    if ident_file is not None and ident_file.exists() and join_key:
        logger.info(f"[{dataset_key}] Ingesting identity table from {ident_file}...")
        ident_df = spark.read.csv(str(ident_file), header=True, inferSchema=True)
        join_stats = inspect_and_validate_join(trans_df, ident_df, join_key=join_key)
        logger.info(f"[{dataset_key}] Join integrity stats: {join_stats}")
        full_df = perform_ieee_cis_join(trans_df, ident_df, join_key=join_key)
    else:
        full_df = trans_df

    # Ensure integer target label
    from pyspark.sql import functions as F
    from pyspark.sql.types import IntegerType

    full_df = full_df.withColumn(target_col, F.col(target_col).cast(IntegerType()))
    return full_df, False


def _select_and_scan_thresholds(
    val_results_df: pd.DataFrame,
    val_predictions: Dict[str, Any],
    config: Dict[str, Any],
    dataset_key: str,
    ds_name: str,
):
    """Select the operational model via validation PR-AUC and scan thresholds on validation."""
    best_model_row = val_results_df.sort_values(by="pr_auc", ascending=False).iloc[0]
    best_model_name = str(best_model_row["model_name"])
    best_val_pr_auc = float(best_model_row["pr_auc"])
    logger.info(
        f"[{dataset_key}] Selected operational model via validation PR-AUC "
        f"({best_val_pr_auc:.4f}): {best_model_name}"
    )

    risk_cfg = config.get("risk_analysis", {})
    thresh_params = inspect.signature(scan_decision_thresholds).parameters
    min_thresh = float(risk_cfg.get("threshold_min", thresh_params["min_thresh"].default))
    max_thresh = float(risk_cfg.get("threshold_max", thresh_params["max_thresh"].default))
    step = float(risk_cfg.get("threshold_step", thresh_params["step"].default))
    cost_fp = float(risk_cfg.get("cost_fp", thresh_params["cost_fp"].default))
    cost_fn = float(risk_cfg.get("cost_fn", thresh_params["cost_fn"].default))

    threshold_records = scan_decision_thresholds(
        val_predictions[best_model_name],
        min_thresh=min_thresh,
        max_thresh=max_thresh,
        step=step,
        cost_fp=cost_fp,
        cost_fn=cost_fn,
    )
    for r in threshold_records:
        r["dataset_key"] = dataset_key
        r["dataset_name"] = ds_name
        r["model_name"] = best_model_name
    threshold_df = pd.DataFrame(threshold_records)

    frozen_row = threshold_df.loc[threshold_df["total_operational_cost"].idxmin()]
    frozen_threshold = float(frozen_row["threshold"])
    frozen_val_cost = float(frozen_row["total_operational_cost"])
    logger.info(
        f"[{dataset_key}] Frozen validation threshold for {best_model_name}: "
        f"{frozen_threshold:.2f} (val_cost={frozen_val_cost})"
    )
    return best_model_name, best_val_pr_auc, threshold_df, frozen_threshold, frozen_val_cost, cost_fp, cost_fn


def _evaluate_frozen_threshold_on_test(
    test_preds: Any,
    best_model_name: str,
    best_val_pr_auc: float,
    frozen_threshold: float,
    frozen_val_cost: float,
    cost_fp: float,
    cost_fn: float,
    dataset_key: str,
    ds_name: str,
) -> pd.DataFrame:
    """Evaluate held-out test predictions once at the validation-frozen threshold."""
    y_true_test, y_prob_test = extract_roc_pr_arrays(test_preds)
    total_test_records = int(len(y_true_test))
    y_pred_frozen = (y_prob_test >= frozen_threshold).astype(int)

    tp = int(((y_true_test == 1) & (y_pred_frozen == 1)).sum())
    tn = int(((y_true_test == 0) & (y_pred_frozen == 0)).sum())
    fp = int(((y_true_test == 0) & (y_pred_frozen == 1)).sum())
    fn = int(((y_true_test == 1) & (y_pred_frozen == 0)).sum())

    precision = round(tp / (tp + fp), 4) if (tp + fp) > 0 else 0.0
    recall = round(tp / (tp + fn), 4) if (tp + fn) > 0 else 0.0
    f1 = (
        round(2 * (precision * recall) / (precision + recall), 4)
        if (precision + recall) > 0
        else 0.0
    )
    flagged_volume = tp + fp
    alert_rate_pct = round((flagged_volume / total_test_records) * 100, 2) if total_test_records > 0 else 0.0
    total_operational_cost = round((fp * cost_fp) + (fn * cost_fn), 2)

    return pd.DataFrame(
        [
            {
                "dataset_key": dataset_key,
                "dataset_name": ds_name,
                "model_name": best_model_name,
                "selection_metric": "val_pr_auc",
                "val_pr_auc": round(best_val_pr_auc, 4),
                "frozen_threshold": frozen_threshold,
                "val_operational_cost": frozen_val_cost,
                "total_test_samples": total_test_records,
                "precision": precision,
                "recall": recall,
                "f1_score": f1,
                "true_positives": tp,
                "false_positives": fp,
                "true_negatives": tn,
                "false_negatives": fn,
                "flagged_volume": flagged_volume,
                "alert_rate_pct": alert_rate_pct,
                "total_operational_cost": total_operational_cost,
            }
        ]
    )


def run_single_dataset(
    spark: Any,
    config: Dict[str, Any],
    dataset_key: str,
    force_mock: bool = False,
    mock_samples: int = 500,
    dev_sample: bool = False,
    tune_hyperparams: bool = True,
    export_eda: bool = True,
    export_model_comparison: bool = True,
    export_threshold_outputs: bool = True,
    export_dataset_summary: bool = True,
    export_model_figures: bool = True,
) -> Dict[str, Any]:
    """Run the full ingestion, feature engineering, training, tuning, evaluation, and export for one dataset."""
    start_ts = time.time()
    root = get_project_root()
    seed = config.get("project", {}).get("random_seed", 42)
    ds_cfg = config.get("datasets", {}).get(dataset_key, {})
    ds_name = ds_cfg.get("name", dataset_key)
    target_col = ds_cfg.get("target_column", "isFraud")
    id_col = ds_cfg.get("join_key")
    time_col = ds_cfg.get("time_column")
    split_strategy = ds_cfg.get("split_strategy", "stratified_random")

    logger.info("=" * 70)
    logger.info(f"FRAUDGUARD PIPELINE — {dataset_key.upper()}: {ds_name}")
    logger.info("=" * 70)

    sample_frac = config.get("dev_mode", {}).get("sample_fraction", 0.05) if dev_sample else None
    full_df, is_mock = _load_dataset_frame(
        spark,
        root,
        dataset_key,
        ds_cfg,
        seed=seed,
        force_mock=force_mock,
        mock_samples=mock_samples,
        sample_fraction=sample_frac,
    )

    # Persist clean interim Parquet when Hadoop/Spark FS is available; otherwise cache in memory
    import os
    interim_rel = ds_cfg.get("interim_path")
    if interim_rel and not is_mock and (os.name != "nt" or os.environ.get("HADOOP_HOME")):
        interim_path = root / interim_rel
        interim_path.parent.mkdir(parents=True, exist_ok=True)
        logger.info(f"[{dataset_key}] Saving interim Parquet to {interim_path}...")
        full_df.write.mode("overwrite").parquet(str(interim_path))
        full_df = spark.read.parquet(str(interim_path))
    else:
        full_df.cache()

    # Prepare output directories
    out_cfg = config.get("outputs", {})
    metrics_dir = root / out_cfg.get("metrics_dir", "outputs/metrics")
    summaries_dir = root / out_cfg.get("summaries_dir", "outputs/summaries")
    figures_dir = root / out_cfg.get("figures_dir", "outputs/figures") / dataset_key
    for d in (metrics_dir, summaries_dir, figures_dir):
        d.mkdir(parents=True, exist_ok=True)

    # Target validation & Spark EDA while full_df is cached (then release full_df memory)
    target_stats = validate_target_distribution(full_df, target_col=target_col)
    eda_paths: Dict[str, Path] = {}
    if export_eda:
        eda_dir = summaries_dir / dataset_key
        eda_paths = export_eda_reports(
            full_df,
            eda_dir,
            target_col=target_col,
            time_col=time_col,
            dataset_name=ds_name,
        )
        amt_df = pd.read_csv(eda_paths["amount_distribution"]) if "amount_distribution" in eda_paths else pd.DataFrame()
        hourly_df = pd.read_csv(eda_paths["hourly_fraud_pattern"]) if "hourly_fraud_pattern" in eda_paths else None
        cat_df = pd.read_csv(eda_paths["fraud_by_product"]) if "fraud_by_product" in eda_paths else None
        plot_eda_overview(ds_name, target_stats, amt_df, figures_dir / "eda_overview.png", hourly_df=hourly_df, cat_df=cat_df)

    # Leakage-free Train / Validation / Test split
    train_ratio = ds_cfg.get("train_ratio", 0.70)
    val_ratio = ds_cfg.get("val_ratio", 0.15)
    test_ratio = ds_cfg.get("test_ratio", 0.15)

    if split_strategy == "time_aware" and time_col and time_col in full_df.columns:
        train_df, val_df, test_df = time_aware_split(
            full_df, time_col=time_col, train_ratio=train_ratio, val_ratio=val_ratio, test_ratio=test_ratio
        )
    else:
        train_df, val_df, test_df = group_aware_stratified_split(
            full_df, target_col=target_col, train_ratio=train_ratio, val_ratio=val_ratio, test_ratio=test_ratio, seed=seed
        )

    train_df = train_df.coalesce(8).cache()
    val_df = val_df.coalesce(8).cache()
    test_df = test_df.coalesce(8).cache()

    train_count = train_df.count()
    val_count = val_df.count()
    test_count = test_df.count()
    full_df.unpersist()

    # Feature identification & Spark ML Pipeline (fitted strictly on train_df)
    num_cols, cat_cols, dropped_cols = identify_column_types(
        train_df, target_col=target_col, id_col=id_col, time_col=time_col
    )
    feature_pipeline = build_spark_ml_feature_pipeline(num_cols, cat_cols, apply_scaling=True)
    logger.info(f"[{dataset_key}] Fitting Spark ML feature pipeline on train_df ({train_count:,} rows)...")
    pipeline_model = feature_pipeline.fit(train_df)

    train_prep = pipeline_model.transform(train_df).select(
        "features", target_col
    ).withColumnRenamed(target_col, "label").cache()
    val_prep = pipeline_model.transform(val_df).select(
        "features", target_col
    ).withColumnRenamed(target_col, "label").cache()
    test_prep = pipeline_model.transform(test_df).select(
        "features", target_col
    ).withColumnRenamed(target_col, "label").cache()

    # Pre-extract NumPy arrays once for the 3 boosted models
    train_xy = extract_numpy_features(train_prep)
    val_xy = extract_numpy_features(val_prep)

    model_configs = config.get("models", {})
    metrics_records: List[Dict[str, Any]] = []
    val_metrics_records: List[Dict[str, Any]] = []
    tuning_records: List[Dict[str, Any]] = []
    curve_data: Dict[str, Any] = {}
    trained_models: Dict[str, Any] = {}
    val_predictions: Dict[str, Any] = {}
    test_predictions: Dict[str, Any] = {}

    for m_name in CLASSIFIERS:
        cfg = model_configs.get(m_name, {})
        if tune_hyperparams:
            fitted_model, train_duration, best_cfg, m_tuning = tune_classifier_on_validation(
                m_name,
                train_prep,
                val_prep,
                base_config=cfg,
                precomputed_train_xy=train_xy,
                precomputed_val_xy=val_xy,
            )
            for t_rec in m_tuning:
                t_rec["dataset_key"] = dataset_key
                t_rec["dataset_name"] = ds_name
            tuning_records.extend(m_tuning)
            logger.info(f"[{dataset_key}] Selected {m_name} config via validation PR-AUC: {best_cfg}")
        else:
            fitted_model, train_duration = train_model(
                m_name, train_prep, model_config=cfg, precomputed_xy=train_xy
            )

        trained_models[m_name] = fitted_model

        val_preds = fitted_model.transform(val_prep).cache()
        val_predictions[m_name] = val_preds
        val_metrics = evaluate_predictions(val_preds, model_name=m_name)
        val_metrics["training_time_sec"] = train_duration
        val_metrics["dataset_key"] = dataset_key
        val_metrics["dataset_name"] = ds_name
        val_metrics_records.append(val_metrics)

        preds = fitted_model.transform(test_prep).cache()
        test_predictions[m_name] = preds
        eval_metrics = evaluate_predictions(preds, model_name=m_name)
        eval_metrics["training_time_sec"] = train_duration
        eval_metrics["dataset_key"] = dataset_key
        eval_metrics["dataset_name"] = ds_name
        metrics_records.append(eval_metrics)
        curve_data[m_name] = extract_roc_pr_arrays(preds)

    val_results_df = pd.DataFrame(val_metrics_records)
    results_df = pd.DataFrame(metrics_records)
    print(f"\n--- [{ds_name}] Held-Out Test Evaluation ---")
    print(
        results_df[
            ["model_name", "precision", "recall", "f1_score", "roc_auc", "pr_auc", "log_loss", "training_time_sec"]
        ].to_string(index=False)
    )

    # Select operational model and scan decision thresholds strictly on validation data
    (
        best_model_name,
        best_val_pr_auc,
        threshold_df,
        frozen_threshold,
        frozen_val_cost,
        cost_fp,
        cost_fn,
    ) = _select_and_scan_thresholds(
        val_results_df, val_predictions, config, dataset_key, ds_name
    )
    frozen_threshold_test_df = _evaluate_frozen_threshold_on_test(
        test_predictions[best_model_name],
        best_model_name=best_model_name,
        best_val_pr_auc=best_val_pr_auc,
        frozen_threshold=frozen_threshold,
        frozen_val_cost=frozen_val_cost,
        cost_fp=cost_fp,
        cost_fn=cost_fn,
        dataset_key=dataset_key,
        ds_name=ds_name,
    )

    # Export per-dataset tables & figures
    if export_model_comparison:
        results_df.to_csv(metrics_dir / f"{dataset_key}_model_comparison.csv", index=False)
    if export_threshold_outputs:
        threshold_df.to_csv(summaries_dir / f"{dataset_key}_threshold_analysis.csv", index=False)
        frozen_threshold_test_df.to_csv(summaries_dir / f"{dataset_key}_frozen_threshold_test.csv", index=False)
    tuning_df = pd.DataFrame(tuning_records)
    if not tuning_df.empty:
        tuning_df.to_csv(summaries_dir / f"{dataset_key}_hyperparameter_tuning.csv", index=False)

    overview_df = pd.DataFrame(
        [
            {
                "dataset_key": dataset_key,
                "dataset_name": ds_name,
                "total_records": target_stats["total_records"],
                "legitimate_records": target_stats["legitimate_count"],
                "fraud_records": target_stats["fraud_count"],
                "fraud_prevalence_pct": target_stats["fraud_prevalence_pct"],
                "train_records": train_count,
                "val_records": val_count,
                "test_records": test_count,
                "numerical_features": len(num_cols),
                "categorical_features": len(cat_cols),
                "dropped_high_null_features": len(dropped_cols),
            }
        ]
    )
    if export_dataset_summary:
        overview_df.to_csv(summaries_dir / f"{dataset_key}_dataset_summary.csv", index=False)

    if export_model_figures:
        plot_model_comparison(results_df, figures_dir / "model_comparison_bar_chart.png")
    if export_threshold_outputs:
        plot_threshold_curves(threshold_df, figures_dir / "threshold_tradeoffs.png")
    if export_model_figures:
        plot_confusion_matrices_grid(results_df, figures_dir / "confusion_matrices_grid.png")
        plot_roc_and_pr_curves(
            curve_data,
            figures_dir / "roc_curves.png",
            figures_dir / "pr_curves.png",
            dataset_label=ds_name,
        )

    # Unpersist caches cleanly
    for p_df in val_predictions.values():
        p_df.unpersist()
    for p_df in test_predictions.values():
        p_df.unpersist()
    train_df.unpersist()
    val_df.unpersist()
    test_df.unpersist()
    train_prep.unpersist()
    val_prep.unpersist()
    test_prep.unpersist()

    elapsed = round(time.time() - start_ts, 2)
    logger.info(f"[{dataset_key}] Completed in {elapsed}s.")
    return {
        "dataset_key": dataset_key,
        "dataset_name": ds_name,
        "is_mock": is_mock,
        "runtime_seconds": elapsed,
        "results_df": results_df,
        "val_results_df": val_results_df,
        "threshold_df": threshold_df,
        "frozen_threshold_test_df": frozen_threshold_test_df,
        "overview_df": overview_df,
        "tuning_df": tuning_df,
        "eda_paths": eda_paths,
    }


def consolidate_cross_dataset_exports(
    config: Dict[str, Any],
    run_outputs: List[Dict[str, Any]],
    export_tables: set[str] | None = None,
    export_top_figures: set[str] | None = None,
    export_cross_comparison_figure: bool = True,
) -> None:
    """Merge per-dataset results into master outputs/ and powerbi/data/ tables."""
    root = get_project_root()
    out_cfg = config.get("outputs", {})
    metrics_dir = root / out_cfg.get("metrics_dir", "outputs/metrics")
    summaries_dir = root / out_cfg.get("summaries_dir", "outputs/summaries")
    figures_dir = root / out_cfg.get("figures_dir", "outputs/figures")
    powerbi_dir = root / out_cfg.get("powerbi_dir", "powerbi/data")
    powerbi_dir.mkdir(parents=True, exist_ok=True)

    # Combine whatever datasets exist on disk (supports running A and B separately or together)
    comp_frames, thresh_frames, over_frames, tune_frames = [], [], [], []
    miss_frames, amt_frames, hourly_frames, prod_frames, card_frames = [], [], [], [], []

    for ds_key in ("dataset_a", "dataset_b"):
        p_comp = metrics_dir / f"{ds_key}_model_comparison.csv"
        p_thr = summaries_dir / f"{ds_key}_threshold_analysis.csv"
        p_ovr = summaries_dir / f"{ds_key}_dataset_summary.csv"
        p_tun = summaries_dir / f"{ds_key}_hyperparameter_tuning.csv"

        if p_comp.exists():
            comp_frames.append(pd.read_csv(p_comp))
        if p_thr.exists():
            thresh_frames.append(pd.read_csv(p_thr))
        if p_ovr.exists():
            over_frames.append(pd.read_csv(p_ovr))
        if p_tun.exists():
            tune_frames.append(pd.read_csv(p_tun))

        eda_sub = summaries_dir / ds_key
        for lst, fname in (
            (miss_frames, "missingness_profile.csv"),
            (amt_frames, "amount_distribution.csv"),
            (hourly_frames, "hourly_fraud_pattern.csv"),
            (prod_frames, "fraud_by_product.csv"),
            (card_frames, "fraud_by_card.csv"),
        ):
            fp = eda_sub / fname
            if fp.exists():
                lst.append(pd.read_csv(fp))

    def _export_both(frames: List[pd.DataFrame], rel_dir: Path, filename: str) -> pd.DataFrame:
        if export_tables is not None and filename not in export_tables:
            return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
        if not frames:
            for d in (rel_dir, powerbi_dir):
                stale = d / filename
                if stale.exists():
                    stale.unlink()
            return pd.DataFrame()
        df_merged = pd.concat(frames, ignore_index=True)
        df_merged.to_csv(rel_dir / filename, index=False)
        df_merged.to_csv(powerbi_dir / filename, index=False)
        return df_merged

    combined_comp = _export_both(comp_frames, metrics_dir, "model_comparison.csv")
    _export_both(thresh_frames, summaries_dir, "threshold_analysis.csv")
    _export_both(over_frames, summaries_dir, "dataset_summary.csv")
    _export_both(tune_frames, summaries_dir, "hyperparameter_tuning.csv")
    _export_both(miss_frames, summaries_dir, "missingness_profile.csv")
    _export_both(amt_frames, summaries_dir, "amount_distribution.csv")
    _export_both(hourly_frames, summaries_dir, "hourly_fraud_pattern.csv")
    _export_both(prod_frames, summaries_dir, "fraud_by_product.csv")
    _export_both(card_frames, summaries_dir, "fraud_by_card.csv")

    # Copy primary dataset figures to top-level outputs/figures/ for backwards compatibility
    if run_outputs:
        primary_key = run_outputs[0]["dataset_key"]
        src_fig_dir = figures_dir / primary_key
        for fig_name in (
            "model_comparison_bar_chart.png",
            "threshold_tradeoffs.png",
            "confusion_matrices_grid.png",
            "roc_curves.png",
            "pr_curves.png",
            "eda_overview.png",
        ):
            if export_top_figures is not None and fig_name not in export_top_figures:
                continue
            src_p = src_fig_dir / fig_name
            if src_p.exists():
                (figures_dir / fig_name).write_bytes(src_p.read_bytes())

    if export_cross_comparison_figure and not combined_comp.empty and combined_comp["dataset_name"].nunique() >= 2:
        plot_cross_dataset_comparison(combined_comp, figures_dir / "cross_dataset_comparison.png")


def run_pipeline(
    dataset_key: str = "all",
    force_mock: bool = False,
    mock_samples: int = 500,
    dev_sample: bool = False,
    tune_hyperparams: bool = True,
) -> Dict[str, Any]:
    """Execute the end-to-end FraudGuard Big Data & ML pipeline."""
    total_start = time.time()
    config = load_config()
    spark = get_spark_session(config)
    logger.info(f"Apache Spark Session active: Version {spark.version}")

    keys = ["dataset_a", "dataset_b"] if dataset_key == "all" else [dataset_key]
    run_outputs: List[Dict[str, Any]] = []
    skipped: Dict[str, str] = {}

    for key in keys:
        try:
            res = run_single_dataset(
                spark,
                config,
                dataset_key=key,
                force_mock=force_mock,
                mock_samples=mock_samples,
                dev_sample=dev_sample,
                tune_hyperparams=tune_hyperparams,
            )
            run_outputs.append(res)
        except FileNotFoundError as exc:
            logger.warning(str(exc))
            skipped[key] = str(exc)
            if dataset_key != "all":
                raise

    consolidate_cross_dataset_exports(config, run_outputs)

    total_time = round(time.time() - total_start, 2)
    logger.info(f"FRAUDGUARD MASTER PIPELINE COMPLETED IN {total_time}s")
    return {
        "status": "SUCCESS" if run_outputs else "SKIPPED",
        "runtime_seconds": total_time,
        "datasets_completed": [r["dataset_key"] for r in run_outputs],
        "datasets_skipped": skipped,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run FraudGuard Cross-Dataset Master Pipeline")
    parser.add_argument(
        "--dataset",
        choices=["dataset_a", "dataset_b", "all"],
        default="all",
        help="Which dataset(s) to run",
    )
    parser.add_argument("--force-mock", action="store_true", help="Force synthetic sample generation")
    parser.add_argument("--samples", type=int, default=500, help="Mock sample size")
    parser.add_argument("--dev", action="store_true", help="Use dev_mode sample_fraction on real data")
    parser.add_argument("--no-tune", action="store_true", help="Skip validation hyperparameter grid")
    args = parser.parse_args()

    run_pipeline(
        dataset_key=args.dataset,
        force_mock=args.force_mock,
        mock_samples=args.samples,
        dev_sample=args.dev,
        tune_hyperparams=not args.no_tune,
    )