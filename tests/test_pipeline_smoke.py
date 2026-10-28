"""Integration smoke tests for the end-to-end Spark ML pipeline."""

import unittest
from src.utils.config import load_config
from src.utils.spark_utils import PYSPARK_AVAILABLE, get_spark_session


@unittest.skipUnless(PYSPARK_AVAILABLE, "PySpark not installed in this Python environment")
class TestSparkMLPipelineSmoke(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = load_config()
        # Set minimal Spark config for testing
        cls.config["spark"]["master"] = "local[1]"
        cls.config["spark"]["driver_memory"] = "1g"
        cls.spark = get_spark_session(cls.config)

    @classmethod
    def tearDownClass(cls):
        if cls.spark:
            cls.spark.stop()

    def test_end_to_end_pipeline_flow(self):
        from src.data.mock_generator import generate_mock_ieee_cis_data
        from src.data.loader import time_aware_split, validate_target_distribution
        from src.features.engineering import (
            identify_column_types,
            build_spark_ml_feature_pipeline,
        )
        from src.models.trainer import train_model
        from src.evaluation.metrics import evaluate_predictions
        from src.risk.thresholds import scan_decision_thresholds
        from pyspark.sql import functions as F

        # 1. Generate realistic sample data
        df = generate_mock_ieee_cis_data(self.spark, num_records=120, fraud_rate=0.15, seed=42)
        self.assertEqual(df.count(), 120)

        # 2. Target validation
        target_stats = validate_target_distribution(df, target_col="isFraud")
        self.assertEqual(target_stats["total_records"], 120)
        self.assertGreater(target_stats["fraud_count"], 0)

        # 3. Time-aware split
        train_df, val_df, test_df = time_aware_split(
            df, time_col="TransactionDT", train_ratio=0.70, val_ratio=0.15, test_ratio=0.15
        )
        self.assertEqual(train_df.count() + val_df.count() + test_df.count(), 120)

        # 4. Feature identification & pipeline fitting
        num_cols, cat_cols, _ = identify_column_types(train_df, target_col="isFraud")
        self.assertTrue(len(num_cols) > 0)
        self.assertTrue(len(cat_cols) > 0)

        pipeline = build_spark_ml_feature_pipeline(num_cols, cat_cols, apply_scaling=False)
        # Fit strictly on train_df (no data leakage)
        fitted_pipeline = pipeline.fit(train_df)

        train_trans = fitted_pipeline.transform(train_df).withColumnRenamed("isFraud", "label")
        test_trans = fitted_pipeline.transform(test_df).withColumnRenamed("isFraud", "label")
        self.assertIn("features", train_trans.columns)

        # 5. Model training (All 5 classifiers: LR, RF, XGB, LGB, CB)
        model, train_time = train_model("logistic_regression", train_trans, {"max_iter": 10})
        self.assertGreater(train_time, 0.0)

        rf_model, rf_time = train_model("random_forest", train_trans, {"num_trees": 5, "max_depth": 3})
        self.assertGreater(rf_time, 0.0)

        xgb_model, xgb_time = train_model("xgboost", train_trans, {"n_estimators": 5, "max_depth": 3})
        self.assertGreater(xgb_time, 0.0)
        xgb_preds = xgb_model.transform(test_trans)
        self.assertIn("prediction", xgb_preds.columns)
        self.assertIn("probability", xgb_preds.columns)

        lgb_model, lgb_time = train_model("lightgbm", train_trans, {"n_estimators": 5, "max_depth": 3})
        self.assertGreater(lgb_time, 0.0)
        lgb_preds = lgb_model.transform(test_trans)
        self.assertIn("prediction", lgb_preds.columns)

        cb_model, cb_time = train_model("catboost", train_trans, {"iterations": 5, "depth": 3})
        self.assertGreater(cb_time, 0.0)
        cb_preds = cb_model.transform(test_trans)
        self.assertIn("prediction", cb_preds.columns)

        # 6. Evaluation on held-out test data
        predictions = model.transform(test_trans)
        metrics = evaluate_predictions(predictions, model_name="Logistic Regression")
        self.assertIn("precision", metrics)
        self.assertIn("recall", metrics)
        self.assertIn("f1_score", metrics)
        self.assertIn("true_positives", metrics)

        # 7. Threshold risk analysis
        threshold_records = scan_decision_thresholds(
            predictions, min_thresh=0.1, max_thresh=0.9, step=0.2
        )
        self.assertTrue(len(threshold_records) > 0)
        self.assertIn("threshold", threshold_records[0])
        self.assertIn("total_operational_cost", threshold_records[0])


if __name__ == "__main__":
    unittest.main()
