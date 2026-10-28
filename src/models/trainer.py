"""Model definition and training routines for the 5 selected FraudGuard classifiers.

Final Model Selection:
  1. Logistic Regression (Baseline - Simple linear reference)
  2. Random Forest (Ensemble baseline - Captures nonlinear interactions via bagging)
  3. XGBoost (Advanced boosting - High-efficiency extreme gradient boosting)
  4. LightGBM (Advanced boosting - Leaf-wise fast gradient boosting)
  5. CatBoost (Advanced boosting - Robust categorical & numerical gradient boosting)
"""

import time
from typing import Any, Dict, Tuple
import logging
import numpy as np

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("FraudGuard.Models")

try:
    from pyspark.ml.classification import (
        LogisticRegression,
        RandomForestClassifier,
    )
    from pyspark.ml.linalg import Vectors
    from pyspark.sql import DataFrame, Row
    PYSPARK_AVAILABLE = True
except ImportError:
    PYSPARK_AVAILABLE = False
    DataFrame = None  # type: ignore

try:
    import xgboost as xgb
    XGB_AVAILABLE = True
except ImportError:
    XGB_AVAILABLE = False

try:
    import lightgbm as lgb
    LGB_AVAILABLE = True
except ImportError:
    LGB_AVAILABLE = False

try:
    import catboost as cb
    CATBOOST_AVAILABLE = True
except ImportError:
    CATBOOST_AVAILABLE = False


class BoostedSparkModelWrapper:
    """Wrapper for scikit-learn compatible gradient boosted models (XGBoost, LightGBM, CatBoost)
    to seamlessly interact with Spark ML evaluation and threshold risk pipelines.
    
    Produces identical output schema as native Spark ML classifiers:
      - 'rawPrediction': Vector [margin_0, margin_1]
      - 'probability': Vector [P(0), P(1)]
      - 'prediction': float (0.0 or 1.0)
    """

    def __init__(self, model: Any, model_name: str):
        self.model = model
        self.model_name = model_name

    def transform(self, df: DataFrame) -> DataFrame:
        """Run inference on the Spark DataFrame features and return enriched DataFrame."""
        rows = df.collect()
        if not rows:
            return df

        X = np.array([r["features"].toArray() for r in rows], dtype=np.float32)
        probs = self.model.predict_proba(X)
        preds = self.model.predict(X).astype(float)

        enriched_rows = []
        for i, r in enumerate(rows):
            d = r.asDict()
            p0 = float(probs[i][0])
            p1 = float(probs[i][1])
            # Calibrated log-odds for rawPrediction
            p1_clamped = max(min(p1, 1.0 - 1e-7), 1e-7)
            raw = float(np.log(p1_clamped / (1.0 - p1_clamped)))
            d["rawPrediction"] = Vectors.dense([-raw, raw])
            d["probability"] = Vectors.dense([p0, p1])
            d["prediction"] = float(preds[i])
            enriched_rows.append(Row(**d))

        spark = df.sparkSession
        return spark.createDataFrame(enriched_rows)


def get_classifier(model_name: str, model_config: Dict[str, Any] | None = None) -> Any:
    """Instantiate a Spark ML or Boosted classifier based on model name and configuration.

    Supported models:
      - 'logistic_regression' (Spark ML Baseline)
      - 'random_forest' (Spark ML Ensemble Baseline)
      - 'xgboost' (Advanced Boosting Model)
      - 'lightgbm' (Advanced Boosting Model)
      - 'catboost' (Advanced Boosting Model)
    """
    cfg = model_config or {}
    name = model_name.lower().replace(" ", "_").replace("-", "_")

    if name in ("logistic_regression", "lr"):
        if not PYSPARK_AVAILABLE:
            raise ImportError("PySpark ML is not available.")
        return LogisticRegression(
            featuresCol="features",
            labelCol="label",
            maxIter=cfg.get("max_iter", 100),
            regParam=cfg.get("reg_param", 0.01),
            elasticNetParam=cfg.get("elastic_net_param", 0.0),
        )

    elif name in ("random_forest", "rf"):
        if not PYSPARK_AVAILABLE:
            raise ImportError("PySpark ML is not available.")
        return RandomForestClassifier(
            featuresCol="features",
            labelCol="label",
            numTrees=cfg.get("num_trees", 50),
            maxDepth=cfg.get("max_depth", 8),
            maxBins=cfg.get("max_bins", 32),
            seed=cfg.get("seed", 42),
        )

    elif name in ("xgboost", "xgb"):
        if not XGB_AVAILABLE:
            raise ImportError("xgboost is not installed. Please install via pip install xgboost.")
        return xgb.XGBClassifier(
            n_estimators=cfg.get("n_estimators", 50),
            max_depth=cfg.get("max_depth", 6),
            learning_rate=cfg.get("learning_rate", 0.1),
            subsample=cfg.get("subsample", 0.8),
            colsample_bytree=cfg.get("colsample_bytree", 0.8),
            eval_metric=cfg.get("eval_metric", "logloss"),
            random_state=cfg.get("seed", 42),
            n_jobs=cfg.get("n_jobs", -1),
        )

    elif name in ("lightgbm", "lgb"):
        if not LGB_AVAILABLE:
            raise ImportError("lightgbm is not installed. Please install via pip install lightgbm.")
        return lgb.LGBMClassifier(
            n_estimators=cfg.get("n_estimators", 50),
            max_depth=cfg.get("max_depth", 6),
            learning_rate=cfg.get("learning_rate", 0.1),
            num_leaves=cfg.get("num_leaves", 31),
            random_state=cfg.get("seed", 42),
            verbose=cfg.get("verbose", -1),
            n_jobs=cfg.get("n_jobs", -1),
        )

    elif name in ("catboost", "cb"):
        if not CATBOOST_AVAILABLE:
            raise ImportError("catboost is not installed. Please install via pip install catboost.")
        return cb.CatBoostClassifier(
            iterations=cfg.get("iterations", 50),
            depth=cfg.get("depth", 6),
            learning_rate=cfg.get("learning_rate", 0.1),
            random_seed=cfg.get("seed", 42),
            verbose=cfg.get("verbose", 0),
            thread_count=cfg.get("thread_count", -1),
        )

    else:
        raise ValueError(
            f"Unsupported model name: '{model_name}'. "
            f"Supported models: logistic_regression, random_forest, xgboost, lightgbm, catboost."
        )


def train_model(
    model_name: str,
    train_df: DataFrame,
    model_config: Dict[str, Any] | None = None,
) -> Tuple[Any, float]:
    """Train a classifier on the training split and record genuine training runtime.

    Returns:
        Tuple of (fitted_model, training_time_seconds)
    """
    classifier = get_classifier(model_name, model_config)
    record_count = train_df.count()
    logger.info(f"Initiating training for model: '{model_name}' on {record_count} records...")

    start_time = time.time()
    name = model_name.lower().replace(" ", "_").replace("-", "_")

    if name in ("logistic_regression", "lr", "random_forest", "rf"):
        # Native Spark ML classifier
        fitted_model = classifier.fit(train_df)
    else:
        # Boosted model (XGBoost, LightGBM, CatBoost)
        rows = train_df.select("features", "label").collect()
        X = np.array([r["features"].toArray() for r in rows], dtype=np.float32)
        y = np.array([r["label"] for r in rows], dtype=np.float32)

        classifier.fit(X, y)
        fitted_model = BoostedSparkModelWrapper(classifier, model_name=model_name)

    training_time = round(time.time() - start_time, 2)
    logger.info(f"Model '{model_name}' trained successfully in {training_time} seconds.")
    return fitted_model, training_time
