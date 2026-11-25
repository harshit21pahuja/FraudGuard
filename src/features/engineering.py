"""Feature Engineering and Spark ML Pipeline Definition for IEEE-CIS."""

from typing import List, Tuple
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("FraudGuard.Features")

try:
    from pyspark.ml import Pipeline
    from pyspark.ml.feature import (
        Imputer,
        OneHotEncoder,
        StandardScaler,
        StringIndexer,
        VectorAssembler,
    )
    from pyspark.sql import DataFrame
    from pyspark.sql import functions as F
    PYSPARK_AVAILABLE = True
except ImportError:
    Pipeline = Any = None  # type: ignore
    DataFrame = None  # type: ignore
    PYSPARK_AVAILABLE = False


def identify_column_types(
    df: DataFrame,
    target_col: str = "isFraud",
    id_col: str | None = "TransactionID",
    time_col: str | None = "TransactionDT",
    missing_threshold: float = 0.80,
    max_cat_cardinality: int = 100,
) -> Tuple[List[str], List[str], List[str]]:
    """Classify DataFrame columns into categorical and numerical features.

    Computes missingness across all columns in a single Spark aggregation pass,
    filters out columns with excessive missingness (> missing_threshold) or
    ultra-high categorical cardinality (> max_cat_cardinality), and excludes
    identifiers, time, and target columns to prevent data leakage.
    """
    total_rows = df.count()
    exclude_cols = {c for c in (target_col, id_col, time_col) if c}

    candidate_fields = [f for f in df.schema.fields if f.name not in exclude_cols]
    if not candidate_fields or total_rows == 0:
        return [], [], []

    # Single-pass Spark aggregation for all candidate column null/NaN counts
    null_exprs = []
    for field in candidate_fields:
        col_name = field.name
        data_type = field.dataType.simpleString()
        is_float = any(t in data_type for t in ("double", "float"))
        cond = (
            (F.col(col_name).isNull() | F.isnan(col_name))
            if is_float
            else F.col(col_name).isNull()
        )
        null_exprs.append(F.count(F.when(cond, 1)).alias(col_name))

    null_counts_row = df.select(null_exprs).collect()[0]

    raw_cat_cols: List[str] = []
    numerical_cols: List[str] = []
    dropped_cols: List[str] = []

    for field in candidate_fields:
        col_name = field.name
        data_type = field.dataType.simpleString()
        null_count = int(null_counts_row[col_name])
        missing_rate = null_count / total_rows

        if missing_rate > missing_threshold:
            dropped_cols.append(col_name)
            continue

        if data_type in ("string", "boolean"):
            raw_cat_cols.append(col_name)
        elif any(t in data_type for t in ("int", "bigint", "double", "float", "smallint", "long", "decimal")):
            numerical_cols.append(col_name)

    # Guard OneHotEncoder against ultra-high cardinality string columns (e.g. DeviceInfo)
    categorical_cols: List[str] = []
    if raw_cat_cols and max_cat_cardinality > 0:
        card_exprs = [F.approx_count_distinct(F.col(c)).alias(c) for c in raw_cat_cols]
        card_row = df.select(card_exprs).collect()[0]
        for c in raw_cat_cols:
            if int(card_row[c]) <= max_cat_cardinality:
                categorical_cols.append(c)
            else:
                dropped_cols.append(c)
                logger.info(f"Dropping high-cardinality categorical '{c}' (~{int(card_row[c])} distinct values > {max_cat_cardinality}).")
    else:
        categorical_cols = raw_cat_cols

    logger.info(
        f"Feature selection: {len(numerical_cols)} numerical features, "
        f"{len(categorical_cols)} categorical features, "
        f"{len(dropped_cols)} dropped due to >{missing_threshold*100}% nulls or high cardinality."
    )
    return numerical_cols, categorical_cols, dropped_cols


def build_spark_ml_feature_pipeline(
    numerical_cols: List[str],
    categorical_cols: List[str],
    apply_scaling: bool = False,
) -> Pipeline:
    """Construct an end-to-end Spark ML Pipeline for feature transformation.

    Stages:
      1. StringIndexer on categoricals (with handleInvalid='keep')
      2. OneHotEncoder on indexed categoricals
      3. Imputer on numerical features (median strategy)
      4. VectorAssembler to combine all transformed features into 'features' vector
      5. (Optional) StandardScaler for algorithms sensitive to scale (e.g. LinearSVC / Logistic Regression)
    """
    stages = []

    # 1. Categorical String Indexing
    indexed_cat_cols = []
    encoded_cat_cols = []
    if categorical_cols:
        for cat_col in categorical_cols:
            idx_col = f"{cat_col}_idx"
            indexer = StringIndexer(
                inputCol=cat_col, outputCol=idx_col, handleInvalid="keep"
            )
            stages.append(indexer)
            indexed_cat_cols.append(idx_col)
            encoded_cat_cols.append(f"{cat_col}_vec")

        # 2. One-Hot Encoding
        ohe = OneHotEncoder(
            inputCols=indexed_cat_cols,
            outputCols=encoded_cat_cols,
            handleInvalid="keep",
        )
        stages.append(ohe)

    # 3. Numerical Imputation
    imputed_num_cols = []
    if numerical_cols:
        imputed_num_cols = [f"{col}_imp" for col in numerical_cols]
        imputer = Imputer(
            inputCols=numerical_cols,
            outputCols=imputed_num_cols,
            strategy="median",
        )
        stages.append(imputer)

    # 4. Vector Assembly
    assembler_inputs = imputed_num_cols + encoded_cat_cols
    assembler = VectorAssembler(
        inputCols=assembler_inputs,
        outputCol="raw_features" if apply_scaling else "features",
        handleInvalid="keep",
    )
    stages.append(assembler)

    # 5. Optional Standard Scaling
    if apply_scaling:
        scaler = StandardScaler(
            inputCol="raw_features",
            outputCol="features",
            withStd=True,
            withMean=False,  # Keep sparse matrices efficient
        )
        stages.append(scaler)

    pipeline = Pipeline(stages=stages)
    logger.info(f"Spark ML Pipeline constructed with {len(stages)} stages.")
    return pipeline
