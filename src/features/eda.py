"""Exploratory Data Analysis (EDA) and pattern analysis using Apache Spark."""

from pathlib import Path
from typing import Any, Dict, List
import logging
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("FraudGuard.EDA")

try:
    from pyspark.sql import DataFrame
    from pyspark.sql import functions as F
    PYSPARK_AVAILABLE = True
except ImportError:
    DataFrame = None  # type: ignore
    PYSPARK_AVAILABLE = False


def compute_missingness_profile(df: DataFrame, top_n: int = 20) -> pd.DataFrame:
    """Analyze missing/null value percentage per column using Spark aggregations."""
    total_count = df.count()
    if total_count == 0:
        return pd.DataFrame(columns=["column_name", "null_count", "missing_percentage"])

    # Create null count expressions for each column
    null_exprs = [
        F.count(
            F.when(
                F.col(c).isNull() | (F.isnan(c) if "double" in str(df.schema[c].dataType) or "float" in str(df.schema[c].dataType) else F.lit(False)),
                c,
            )
        ).alias(c)
        for c in df.columns
    ]

    null_row = df.select(null_exprs).collect()[0]

    records = []
    for c in df.columns:
        n_null = int(null_row[c])
        pct = round((n_null / total_count) * 100, 2)
        records.append({"column_name": c, "null_count": n_null, "missing_percentage": pct})

    pdf = pd.DataFrame(records)
    pdf = pdf.sort_values(by="missing_percentage", ascending=False).reset_index(drop=True)
    return pdf.head(top_n)


def compute_fraud_by_categorical(
    df: DataFrame, cat_col: str, target_col: str = "isFraud"
) -> pd.DataFrame:
    """Calculate transaction volume, fraud count, and fraud rate grouped by categorical attribute."""
    if cat_col not in df.columns:
        logger.warning(f"Column '{cat_col}' not found in DataFrame.")
        return pd.DataFrame()

    agg_df = (
        df.groupBy(cat_col)
        .agg(
            F.count(target_col).alias("total_transactions"),
            F.sum(target_col).alias("fraud_transactions"),
        )
        .withColumn(
            "legitimate_transactions",
            F.col("total_transactions") - F.col("fraud_transactions"),
        )
        .withColumn(
            "fraud_rate_pct",
            F.round((F.col("fraud_transactions") / F.col("total_transactions")) * 100, 2),
        )
        .orderBy(F.desc("total_transactions"))
    )

    return agg_df.toPandas()


def compute_amount_distribution(
    df: DataFrame, amount_col: str = "TransactionAmt", target_col: str = "isFraud"
) -> pd.DataFrame:
    """Compute financial summary statistics comparing fraudulent vs legitimate transaction amounts."""
    stats = (
        df.groupBy(target_col)
        .agg(
            F.count(amount_col).alias("count"),
            F.round(F.min(amount_col), 2).alias("min_amount"),
            F.round(F.mean(amount_col), 2).alias("avg_amount"),
            F.round(F.stddev(amount_col), 2).alias("stddev_amount"),
            F.round(F.max(amount_col), 2).alias("max_amount"),
        )
        .withColumn(
            "class_label",
            F.when(F.col(target_col) == 1, "Fraudulent").otherwise("Legitimate"),
        )
        .orderBy(target_col)
    )
    return stats.toPandas()


def compute_hourly_fraud_pattern(
    df: DataFrame, time_col: str = "TransactionDT", target_col: str = "isFraud"
) -> pd.DataFrame:
    """Calculate hourly transaction volume and fraud prevalence across a 24-hour cycle."""
    if time_col not in df.columns or target_col not in df.columns:
        return pd.DataFrame()

    hourly_df = (
        df.withColumn("hour_of_day", (F.floor(F.col(time_col) / 3600.0) % 24).cast("int"))
        .groupBy("hour_of_day")
        .agg(
            F.count(target_col).alias("total_transactions"),
            F.sum(F.col(target_col).cast("long")).alias("fraud_transactions"),
        )
        .withColumn(
            "fraud_rate_pct",
            F.round((F.col("fraud_transactions") / F.col("total_transactions")) * 100, 4),
        )
        .orderBy("hour_of_day")
    )
    return hourly_df.toPandas()


def export_eda_reports(
    df: DataFrame,
    output_dir: Path,
    target_col: str = "isFraud",
    amount_col: str | None = None,
    time_col: str | None = None,
    dataset_name: str = "Dataset",
) -> Dict[str, Path]:
    """Generate and export all EDA summaries for Power BI Page 2 (Fraud Pattern Analysis)."""
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = {}

    logger.info("Computing missingness profile...")
    missing_df = compute_missingness_profile(df, top_n=30)
    missing_df["dataset_name"] = dataset_name
    p_missing = output_dir / "missingness_profile.csv"
    missing_df.to_csv(p_missing, index=False)
    paths["missingness"] = p_missing

    resolved_amt = amount_col or ("TransactionAmt" if "TransactionAmt" in df.columns else ("Amount" if "Amount" in df.columns else None))
    if resolved_amt and resolved_amt in df.columns:
        logger.info(f"Computing transaction amount statistics ({resolved_amt})...")
        amt_df = compute_amount_distribution(df, amount_col=resolved_amt, target_col=target_col)
        amt_df["dataset_name"] = dataset_name
        p_amt = output_dir / "amount_distribution.csv"
        amt_df.to_csv(p_amt, index=False)
        paths["amount_distribution"] = p_amt

    resolved_time = time_col or ("TransactionDT" if "TransactionDT" in df.columns else ("Time" if "Time" in df.columns else None))
    if resolved_time and resolved_time in df.columns:
        logger.info(f"Computing hourly fraud pattern ({resolved_time})...")
        hourly_df = compute_hourly_fraud_pattern(df, time_col=resolved_time, target_col=target_col)
        hourly_df["dataset_name"] = dataset_name
        p_hourly = output_dir / "hourly_fraud_pattern.csv"
        hourly_df.to_csv(p_hourly, index=False)
        paths["hourly_fraud_pattern"] = p_hourly

    if "ProductCD" in df.columns:
        logger.info("Computing fraud distribution by ProductCD...")
        prod_df = compute_fraud_by_categorical(df, "ProductCD", target_col=target_col)
        prod_df["dataset_name"] = dataset_name
        p_prod = output_dir / "fraud_by_product.csv"
        prod_df.to_csv(p_prod, index=False)
        paths["fraud_by_product"] = p_prod

    if "card4" in df.columns:
        logger.info("Computing fraud distribution by Card Brand (card4)...")
        card_df = compute_fraud_by_categorical(df, "card4", target_col=target_col)
        card_df["dataset_name"] = dataset_name
        p_card = output_dir / "fraud_by_card.csv"
        card_df.to_csv(p_card, index=False)
        paths["fraud_by_card"] = p_card

    logger.info(f"EDA export completed. {len(paths)} summary files saved to {output_dir}")
    return paths
