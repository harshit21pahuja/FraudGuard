"""Model definition and training routines for the 5 selected FraudGuard classifiers.

Final Model Selection:
  1. Logistic Regression (Baseline - Simple linear reference)
  2. Random Forest (Ensemble baseline - Captures nonlinear interactions via bagging)
  3. XGBoost (Advanced boosting - High-efficiency extreme gradient boosting)
  4. LightGBM (Advanced boosting - Leaf-wise fast gradient boosting)
  5. CatBoost (Advanced boosting - Robust categorical & numerical gradient boosting)
"""

import time
from typing import Any, Dict, List, Tuple
import logging
import numpy as np

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("FraudGuard.Models")

try:
    from pyspark.ml.classification import (
        LogisticRegression,
        RandomForestClassifier,
    )
    from pyspark.ml.linalg import Vectors, VectorUDT
    from pyspark.sql import DataFrame, Row
    from pyspark.sql.types import DoubleType, IntegerType, StructField, StructType
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
        """Run inference on Spark DataFrame features and return explicit-schema DataFrame."""
        rows = df.select("label", "features").collect()
        if not rows:
            return df

        n_rows = len(rows)
        dim = len(rows[0]["features"])
        X = np.empty((n_rows, dim), dtype=np.float32)
        labels = np.empty((n_rows,), dtype=np.int32)
        for i, r in enumerate(rows):
            X[i] = r["features"].toArray()
            labels[i] = int(r["label"])
        del rows

        probs = self.model.predict_proba(X)
        preds = self.model.predict(X).astype(float)
        del X

        enriched_rows = []
        for i in range(n_rows):
            p0 = float(probs[i][0])
            p1 = float(probs[i][1])
            p1_clamped = max(min(p1, 1.0 - 1e-7), 1e-7)
            raw = float(np.log(p1_clamped / (1.0 - p1_clamped)))
            enriched_rows.append(
                (
                    int(labels[i]),
                    Vectors.dense([-raw, raw]),
                    Vectors.dense([p0, p1]),
                    float(preds[i]),
                )
            )

        schema = StructType(
            [
                StructField("label", IntegerType(), False),
                StructField("rawPrediction", VectorUDT(), False),
                StructField("probability", VectorUDT(), False),
                StructField("prediction", DoubleType(), False),
            ]
        )
        return df.sparkSession.createDataFrame(enriched_rows, schema=schema)


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
            min_child_samples=cfg.get("min_child_samples", 20),
            reg_lambda=cfg.get("reg_lambda", 0.0),
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


def extract_numpy_features(df: DataFrame) -> Tuple[np.ndarray, np.ndarray]:
    """Collect Spark ML feature vectors and labels into pre-allocated NumPy arrays."""
    rows = df.select("features", "label").collect()
    if not rows:
        return np.empty((0, 0), dtype=np.float32), np.empty((0,), dtype=np.int32)
    dim = len(rows[0]["features"])
    X = np.empty((len(rows), dim), dtype=np.float32)
    y = np.empty((len(rows),), dtype=np.int32)
    for idx, r in enumerate(rows):
        X[idx] = r["features"].toArray()
        y[idx] = int(r["label"])
    del rows
    return X, y


def train_model(
    model_name: str,
    train_df: DataFrame,
    model_config: Dict[str, Any] | None = None,
    precomputed_xy: Tuple[np.ndarray, np.ndarray] | None = None,
) -> Tuple[Any, float]:
    """Train a classifier on the training split and record genuine training runtime.

    Returns:
        Tuple of (fitted_model, training_time_seconds)
    """
    classifier = get_classifier(model_name, model_config)
    record_count = len(precomputed_xy[1]) if precomputed_xy is not None else train_df.count()
    logger.info(f"Initiating training for model: '{model_name}' on {record_count} records...")

    start_time = time.time()
    name = model_name.lower().replace(" ", "_").replace("-", "_")

    if name in ("logistic_regression", "lr", "random_forest", "rf"):
        fitted_model = classifier.fit(train_df)
    else:
        X, y = precomputed_xy if precomputed_xy is not None else extract_numpy_features(train_df)
        classifier.fit(X, y)
        fitted_model = BoostedSparkModelWrapper(classifier, model_name=model_name)

    training_time = round(time.time() - start_time, 2)
    logger.info(f"Model '{model_name}' trained successfully in {training_time} seconds.")
    return fitted_model, training_time


def tune_classifier_on_validation(
    model_name: str,
    train_df: DataFrame,
    val_df: DataFrame,
    base_config: Dict[str, Any] | None = None,
    precomputed_train_xy: Tuple[np.ndarray, np.ndarray] | None = None,
    precomputed_val_xy: Tuple[np.ndarray, np.ndarray] | None = None,
) -> Tuple[Any, float, Dict[str, Any], List[Dict[str, Any]]]:
    """Evaluate candidate hyperparameter settings on the validation split and pick best by PR-AUC."""
    from src.evaluation.metrics import evaluate_predictions

    base_cfg = dict(base_config or {})
    name = model_name.lower().replace(" ", "_").replace("-", "_")

    if name in ("logistic_regression", "lr"):
        candidates = [
            {**base_cfg, "reg_param": 0.001},
            {**base_cfg, "reg_param": 0.01},
            {**base_cfg, "reg_param": 0.1},
        ]
    elif name in ("random_forest", "rf"):
        candidates = [
            {**base_cfg, "max_depth": 5},
            {**base_cfg, "max_depth": 8},
        ]
    elif name in ("xgboost", "xgb"):
        candidates = [
            {**base_cfg, "max_depth": 4, "learning_rate": 0.1},
            {**base_cfg, "max_depth": 6, "learning_rate": 0.1},
            {**base_cfg, "max_depth": 6, "learning_rate": 0.05},
        ]
    elif name in ("lightgbm", "lgb"):
        candidates = [
            {**base_cfg, "max_depth": 5, "num_leaves": 15, "learning_rate": 0.03, "min_child_samples": 50, "reg_lambda": 5.0},
            {**base_cfg, "max_depth": 6, "num_leaves": 31, "learning_rate": 0.05, "min_child_samples": 30, "reg_lambda": 1.0},
            {**base_cfg, "max_depth": 6, "num_leaves": 31, "learning_rate": 0.1, "min_child_samples": 20, "reg_lambda": 0.0},
        ]
    else:  # catboost
        candidates = [
            {**base_cfg, "depth": 4, "learning_rate": 0.1},
            {**base_cfg, "depth": 6, "learning_rate": 0.1},
            {**base_cfg, "depth": 6, "learning_rate": 0.05},
        ]

    best_model = None
    best_time = 0.0
    best_cfg = base_cfg
    best_score = -1.0
    tuning_records: List[Dict[str, Any]] = []

    for cand_cfg in candidates:
        if name in ("logistic_regression", "lr", "random_forest", "rf"):
            fitted, train_sec = train_model(model_name, train_df, cand_cfg)
            val_preds = fitted.transform(val_df)
            val_metrics = evaluate_predictions(val_preds, model_name=model_name)
        else:
            # Fast vectorized validation evaluation for boosted candidates
            from sklearn.metrics import average_precision_score, roc_auc_score
            from src.evaluation.metrics import compute_binary_log_loss

            X_tr, y_tr = precomputed_train_xy or extract_numpy_features(train_df)
            X_va, y_va = precomputed_val_xy or extract_numpy_features(val_df)
            clf = get_classifier(model_name, cand_cfg)
            t0 = time.time()
            clf.fit(X_tr, y_tr)
            train_sec = round(time.time() - t0, 2)
            probs = clf.predict_proba(X_va)[:, 1]
            val_metrics = {
                "pr_auc": round(float(average_precision_score(y_va, probs)), 4) if len(np.unique(y_va)) > 1 else 0.0,
                "roc_auc": round(float(roc_auc_score(y_va, probs)), 4) if len(np.unique(y_va)) > 1 else 0.0,
                "log_loss": compute_binary_log_loss(y_va, probs),
            }
            fitted = BoostedSparkModelWrapper(clf, model_name=model_name)

        param_summary = {
            k: v
            for k, v in cand_cfg.items()
            if k in ("reg_param", "max_depth", "depth", "num_leaves", "learning_rate", "min_child_samples", "reg_lambda", "num_trees", "n_estimators", "iterations")
        }
        rec = {
            "model_name": model_name,
            "hyperparameters": str(param_summary),
            "val_pr_auc": val_metrics["pr_auc"],
            "val_roc_auc": val_metrics["roc_auc"],
            "val_log_loss": val_metrics["log_loss"],
            "train_time_sec": train_sec,
            "selected": False,
        }
        tuning_records.append(rec)
        if val_metrics["pr_auc"] > best_score:
            best_score = val_metrics["pr_auc"]
            best_model = fitted
            best_time = train_sec
            best_cfg = cand_cfg

    for rec in tuning_records:
        if rec["val_pr_auc"] == best_score and best_score >= 0:
            rec["selected"] = True
            break

    return best_model, best_time, best_cfg, tuning_records
