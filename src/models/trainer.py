"""Model definition and training routines for the 5 Spark ML binary classifiers."""

import time
from typing import Any, Dict, Tuple
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("FraudGuard.Models")

try:
    from pyspark.ml.classification import (
        DecisionTreeClassifier,
        GBTClassifier,
        LinearSVC,
        LogisticRegression,
        RandomForestClassifier,
    )
    from pyspark.sql import DataFrame
    PYSPARK_AVAILABLE = True
except ImportError:
    PYSPARK_AVAILABLE = False
    DataFrame = None  # type: ignore


def get_classifier(model_name: str, model_config: Dict[str, Any] | None = None) -> Any:
    """Instantiate a Spark ML binary classifier based on model name and configuration.

    Supported models:
      - 'logistic_regression'
      - 'decision_tree'
      - 'random_forest'
      - 'gbt'
      - 'linear_svc'
    """
    if not PYSPARK_AVAILABLE:
        raise ImportError("PySpark ML is not available in the current environment.")

    cfg = model_config or {}
    name = model_name.lower().replace(" ", "_")

    if name in ("logistic_regression", "lr"):
        return LogisticRegression(
            featuresCol="features",
            labelCol="label",
            maxIter=cfg.get("max_iter", 100),
            regParam=cfg.get("reg_param", 0.01),
            elasticNetParam=cfg.get("elastic_net_param", 0.0),
        )

    elif name in ("decision_tree", "dt"):
        return DecisionTreeClassifier(
            featuresCol="features",
            labelCol="label",
            maxDepth=cfg.get("max_depth", 6),
            maxBins=cfg.get("max_bins", 32),
            seed=cfg.get("seed", 42),
        )

    elif name in ("random_forest", "rf"):
        return RandomForestClassifier(
            featuresCol="features",
            labelCol="label",
            numTrees=cfg.get("num_trees", 50),
            maxDepth=cfg.get("max_depth", 8),
            maxBins=cfg.get("max_bins", 32),
            seed=cfg.get("seed", 42),
        )

    elif name in ("gbt", "gradient_boosted_trees"):
        return GBTClassifier(
            featuresCol="features",
            labelCol="label",
            maxIter=cfg.get("max_iter", 40),
            maxDepth=cfg.get("max_depth", 5),
            stepSize=cfg.get("step_size", 0.1),
            seed=cfg.get("seed", 42),
        )

    elif name in ("linear_svc", "svm"):
        return LinearSVC(
            featuresCol="features",
            labelCol="label",
            maxIter=cfg.get("max_iter", 100),
            regParam=cfg.get("reg_param", 0.01),
        )

    else:
        raise ValueError(
            f"Unsupported model name: '{model_name}'. "
            f"Supported models: logistic_regression, decision_tree, random_forest, gbt, linear_svc."
        )


def train_model(
    model_name: str,
    train_df: DataFrame,
    model_config: Dict[str, Any] | None = None,
) -> Tuple[Any, float]:
    """Train a Spark ML classifier on the training split and record genuine training runtime.

    Returns:
        Tuple of (fitted_model, training_time_seconds)
    """
    classifier = get_classifier(model_name, model_config)
    logger.info(f"Initiating training for model: '{model_name}' on {train_df.count()} records...")

    start_time = time.time()
    fitted_model = classifier.fit(train_df)
    training_time = round(time.time() - start_time, 2)

    logger.info(f"Model '{model_name}' trained successfully in {training_time} seconds.")
    return fitted_model, training_time
