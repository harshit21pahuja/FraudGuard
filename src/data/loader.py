"""Dataset Ingestion, Join Validation, and Splitting Module."""

import logging
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("FraudGuard.Loader")

try:
    from pyspark.sql import DataFrame, SparkSession, Window
    from pyspark.sql import functions as F
    from pyspark.sql.types import IntegerType
    PYSPARK_AVAILABLE = True
except ImportError:
    DataFrame = Any  # type: ignore
    SparkSession = Any  # type: ignore
    Window = Any  # type: ignore
    PYSPARK_AVAILABLE = False


def validate_raw_files_exist(trans_path: Path, ident_path: Optional[Path] = None) -> None:
    """Verify that required raw CSV files exist."""
    missing = []
    if not trans_path.exists():
        missing.append(str(trans_path))
    if ident_path is not None and not ident_path.exists():
        missing.append(str(ident_path))

    if missing:
        raise FileNotFoundError(
            "Required raw dataset files are missing:\n"
            + "\n".join(f"  - {f}" for f in missing)
        )


def inspect_and_validate_join(
    trans_df: DataFrame, ident_df: DataFrame, join_key: str = "TransactionID"
) -> Dict[str, Any]:
    """Validate join-key uniqueness and unmatched records prior to join.

    Ensures:
      1. No duplicate TransactionIDs in transaction DataFrame.
      2. No duplicate TransactionIDs in identity DataFrame.
      3. Calculates matching rate to document how many transactions have telemetry.
    """
    logger.info("Validating join-key uniqueness and identity match statistics...")

    trans_count = trans_df.count()
    trans_distinct = trans_df.select(join_key).distinct().count()
    if trans_count != trans_distinct:
        raise ValueError(
            f"Integrity Error: Duplicate {join_key} found in transaction data! "
            f"Total rows: {trans_count}, Distinct: {trans_distinct}"
        )

    ident_count = ident_df.count()
    ident_distinct = ident_df.select(join_key).distinct().count()
    if ident_count != ident_distinct:
        raise ValueError(
            f"Integrity Error: Duplicate {join_key} found in identity data! "
            f"Total rows: {ident_count}, Distinct: {ident_distinct}"
        )

    matched_count = trans_df.join(
        ident_df.select(join_key), on=join_key, how="inner"
    ).count()
    match_pct = round((matched_count / trans_count) * 100, 2) if trans_count > 0 else 0.0

    stats = {
        "transaction_rows": trans_count,
        "identity_rows": ident_count,
        "matched_rows": matched_count,
        "identity_coverage_pct": match_pct,
        "unmatched_transaction_rows": trans_count - matched_count,
    }
    logger.info(
        f"Join validation passed: {matched_count}/{trans_count} ({match_pct}%) "
        f"transactions matched an identity record."
    )
    return stats


def perform_ieee_cis_join(
    trans_df: DataFrame, ident_df: DataFrame, join_key: str = "TransactionID"
) -> DataFrame:
    """Perform a left outer join from transactions to identity data.

    Left join is mandatory because identity information is only available for
    a subset (~24%) of transactions. An inner join would discard 75% of data.
    """
    initial_count = trans_df.count()
    joined_df = trans_df.join(ident_df, on=join_key, how="left")
    joined_count = joined_df.count()

    if joined_count != initial_count:
        raise ValueError(
            f"Join anomaly detected: Row count changed from {initial_count} to {joined_count}."
        )

    logger.info(f"Left join completed successfully. Preserved exact count: {joined_count} rows.")
    return joined_df


def validate_target_distribution(
    df: DataFrame, target_col: str = "isFraud"
) -> Dict[str, Any]:
    """Inspect and validate the binary target label distribution."""
    if target_col not in df.columns:
        raise ValueError(f"Target column '{target_col}' not found in DataFrame.")

    null_count = df.filter(F.col(target_col).isNull()).count()
    if null_count > 0:
        raise ValueError(f"Found {null_count} null values in target column '{target_col}'.")

    dist_rows = (
        df.groupBy(F.col(target_col).cast(IntegerType()).alias("_target"))
        .count()
        .orderBy("_target")
        .collect()
    )

    dist_map = {int(row["_target"]): int(row["count"]) for row in dist_rows}
    total = sum(dist_map.values())
    fraud_count = dist_map.get(1, 0)
    legit_count = dist_map.get(0, 0)
    prevalence = round((fraud_count / total) * 100, 4) if total > 0 else 0.0

    logger.info(
        f"Target Distribution [{target_col}]: Total={total}, Legit(0)={legit_count}, "
        f"Fraud(1)={fraud_count}, Fraud Prevalence={prevalence}%"
    )

    return {
        "total_records": total,
        "legitimate_count": legit_count,
        "fraud_count": fraud_count,
        "fraud_prevalence_pct": prevalence,
    }


def time_aware_split(
    df: DataFrame,
    time_col: str = "TransactionDT",
    train_ratio: float = 0.70,
    val_ratio: float = 0.15,
    test_ratio: float = 0.15,
) -> Tuple[DataFrame, DataFrame, DataFrame]:
    """Perform a strictly forward time-aware train/val/test split.

    Uses time_col (seconds elapsed) to split the dataset temporally:
      - Train: [min_time, cutoff_train]
      - Validation: (cutoff_train, cutoff_val]
      - Test: (cutoff_val, max_time]
    This eliminates temporal data leakage into the evaluation sets.
    """
    if abs(train_ratio + val_ratio + test_ratio - 1.0) > 1e-5:
        raise ValueError("train_ratio, val_ratio, and test_ratio must sum to 1.0")

    probabilities = [train_ratio, train_ratio + val_ratio]
    cutoffs = df.approxQuantile(time_col, probabilities, 0.001)
    train_cutoff = cutoffs[0]
    val_cutoff = cutoffs[1]

    logger.info(
        f"Time-aware split boundaries for '{time_col}': "
        f"Train cutoff = {train_cutoff:.1f}, Val cutoff = {val_cutoff:.1f}"
    )

    train_df = df.filter(F.col(time_col) <= train_cutoff)
    val_df = df.filter((F.col(time_col) > train_cutoff) & (F.col(time_col) <= val_cutoff))
    test_df = df.filter(F.col(time_col) > val_cutoff)

    logger.info(
        f"Split sizes: Train={train_df.count()}, Val={val_df.count()}, Test={test_df.count()}"
    )
    return train_df, val_df, test_df


def stratified_split(
    df: DataFrame,
    target_col: str = "Class",
    train_ratio: float = 0.70,
    val_ratio: float = 0.15,
    test_ratio: float = 0.15,
    seed: int = 42,
) -> Tuple[DataFrame, DataFrame, DataFrame]:
    """Perform an exact deterministic stratified train/val/test split preserving class ratio."""
    if abs(train_ratio + val_ratio + test_ratio - 1.0) > 1e-5:
        raise ValueError("train_ratio, val_ratio, and test_ratio must sum to 1.0")

    # Deterministic per-class ranking ensures exact class prevalence across all three partitions
    win = Window.partitionBy(target_col).orderBy(F.rand(seed))
    ranked = df.withColumn("_pct_rank", F.percent_rank().over(win))

    val_cutoff = train_ratio + val_ratio
    train_df = ranked.filter(F.col("_pct_rank") < train_ratio).drop("_pct_rank")
    val_df = ranked.filter(
        (F.col("_pct_rank") >= train_ratio) & (F.col("_pct_rank") < val_cutoff)
    ).drop("_pct_rank")
    test_df = ranked.filter(F.col("_pct_rank") >= val_cutoff).drop("_pct_rank")

    logger.info(
        f"Stratified split ({target_col}): Train={train_df.count()}, "
        f"Val={val_df.count()}, Test={test_df.count()}"
    )
    return train_df, val_df, test_df


def group_aware_stratified_split(
    df: DataFrame,
    target_col: str = "Class",
    train_ratio: float = 0.70,
    val_ratio: float = 0.15,
    test_ratio: float = 0.15,
    seed: int = 42,
) -> Tuple[DataFrame, DataFrame, DataFrame]:
    """Perform a deterministic row-weighted group-aware stratified train/val/test split.

    Assigns every identical feature group to a single partition while keeping
    original row proportions and class counts close to target split ratios.
    Detects conflicting target labels within duplicate feature groups prior to
    partition assignment.
    """
    if abs(train_ratio + val_ratio + test_ratio - 1.0) > 1e-5:
        raise ValueError("train_ratio, val_ratio, and test_ratio must sum to 1.0")
    if target_col not in df.columns:
        raise ValueError(f"Target column '{target_col}' not found in DataFrame.")

    feature_cols = sorted([c for c in df.columns if c != target_col])
    if not feature_cols:
        raise ValueError("No feature columns available for group construction.")

    df_gid = df.withColumn(
        "_group_id",
        F.sha2(
            F.to_json(F.struct(*[F.col(c) for c in feature_cols]), {"ignoreNullFields": "false"}),
            256,
        ),
    )

    conflict_count = (
        df_gid.groupBy("_group_id")
        .agg(F.countDistinct(target_col).alias("_n_labels"))
        .filter(F.col("_n_labels") > 1)
        .count()
    )
    if conflict_count > 0:
        raise ValueError(
            f"Conflicting target labels detected in {conflict_count} duplicate feature group(s) "
            f"for target '{target_col}'."
        )

    groups = df_gid.groupBy("_group_id", target_col).agg(
        F.count("*").cast("long").alias("_group_size")
    )

    class_window = Window.partitionBy(target_col)
    cum_window = (
        Window.partitionBy(target_col)
        .orderBy(F.sha2(F.concat_ws(":", F.col("_group_id"), F.lit(str(seed))), 256))
        .rowsBetween(Window.unboundedPreceding, Window.currentRow)
    )

    val_cutoff = train_ratio + val_ratio
    groups_assigned = (
        groups.withColumn("_class_total", F.sum("_group_size").over(class_window))
        .withColumn("_cum_rows", F.sum("_group_size").over(cum_window))
        .withColumn("_cum_frac", F.col("_cum_rows") / F.col("_class_total"))
        .withColumn(
            "_partition",
            F.when(F.col("_cum_frac") <= train_ratio, F.lit("train"))
            .when(F.col("_cum_frac") <= val_cutoff, F.lit("val"))
            .otherwise(F.lit("test")),
        )
    )

    joined = df_gid.join(
        groups_assigned.select("_group_id", "_partition"),
        on="_group_id",
        how="inner",
    )

    train_df = joined.filter(F.col("_partition") == "train").drop("_group_id", "_partition")
    val_df = joined.filter(F.col("_partition") == "val").drop("_group_id", "_partition")
    test_df = joined.filter(F.col("_partition") == "test").drop("_group_id", "_partition")

    logger.info(
        f"Group-aware stratified split ({target_col}): Train={train_df.count()}, "
        f"Val={val_df.count()}, Test={test_df.count()}"
    )
    return train_df, val_df, test_df
