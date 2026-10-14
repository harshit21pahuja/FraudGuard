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
    id_col: str = "TransactionID",
    time_col: str = "TransactionDT",
    missing_threshold: float = 0.80,
) -> Tuple[List[str], List[str], List[str]]:
    """Classify DataFrame columns into categorical and numerical features.

    Filters out columns with excessive missingness (> missing_threshold) and excludes
    identifiers, time, and target columns to prevent data leakage.
    """
    total_rows = df.count()
    exclude_cols = {target_col, id_col, time_col}

    categorical_cols: List[str] = []
    numerical_cols: List[str] = []
    dropped_cols: List[str] = []

    # Check null ratios per column
    schema = df.schema
    for field in schema.fields:
        col_name = field.name
        if col_name in exclude_cols:
            continue

        data_type = field.dataType.simpleString()
        # Count nulls
        null_count = df.filter(F.col(col_name).isNull() | F.isnan(col_name) if "double" in data_type or "float" in data_type else F.col(col_name).isNull()).count()
        missing_rate = null_count / total_rows if total_rows > 0 else 0.0

        if missing_rate > missing_threshold:
            dropped_cols.append(col_name)
            continue

        if data_type in ("string", "boolean"):
            categorical_cols.append(col_name)
        elif data_type in ("int", "bigint", "double", "float", "smallint", "long"):
            numerical_cols.append(col_name)

    logger.info(
        f"Feature selection: {len(numerical_cols)} numerical features, "
        f"{len(categorical_cols)} categorical features, "
        f"{len(dropped_cols)} dropped due to >{missing_threshold*100}% nulls."
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
