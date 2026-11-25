"""Tests verifying fixes for threshold/model-selection leakage and Dataset B group splitting."""

import inspect
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd
from pyspark.ml.linalg import Vectors
from pyspark.sql import functions as F
from pyspark.sql.types import DoubleType, IntegerType, StructField, StructType

from src.data.loader import group_aware_stratified_split, time_aware_split
from src.data.mock_generator import generate_mock_ieee_cis_data
from src.pipeline_runner import (
    _evaluate_frozen_threshold_on_test,
    _select_and_scan_thresholds,
    run_single_dataset,
)
from src.risk.thresholds import scan_decision_thresholds
from src.utils.config import load_config
from src.utils.spark_utils import PYSPARK_AVAILABLE, get_spark_session


def _make_pred_df(spark, rows):
    """Build a Spark DataFrame matching Spark ML / BoostedSparkModelWrapper prediction schema."""
    from pyspark.ml.linalg import VectorUDT

    schema = StructType(
        [
            StructField("label", IntegerType(), False),
            StructField("rawPrediction", VectorUDT(), False),
            StructField("probability", VectorUDT(), False),
            StructField("prediction", DoubleType(), False),
        ]
    )
    formatted = []
    for y, p1 in rows:
        p0 = 1.0 - p1
        pred = 1.0 if p1 >= 0.5 else 0.0
        formatted.append((int(y), Vectors.dense([p0 - p1, p1 - p0]), Vectors.dense([p0, p1]), pred))
    return spark.createDataFrame(formatted, schema=schema)


@unittest.skipUnless(PYSPARK_AVAILABLE, "PySpark not installed")
class TestThresholdAndSplitFixes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = load_config()
        cls.config["spark"]["master"] = "local[2]"
        cls.config["spark"]["driver_memory"] = "1g"
        cls.config["spark"]["sql_shuffle_partitions"] = 4
        cls.spark = get_spark_session(cls.config)

    @classmethod
    def tearDownClass(cls):
        if cls.spark:
            cls.spark.stop()

    # ------------------------------------------------------------------
    # Fix 1: Threshold & Operational Model Selection Tests (6 tests)
    # ------------------------------------------------------------------

    def test_best_model_selected_by_validation_pr_auc_not_test(self):
        # xgboost leads validation PR-AUC (0.91 vs 0.65), even though catboost has higher test PR-AUC
        val_results_df = pd.DataFrame(
            [
                {"model_name": "catboost", "pr_auc": 0.65},
                {"model_name": "xgboost", "pr_auc": 0.91},
            ]
        )
        val_predictions = {
            "xgboost": _make_pred_df(self.spark, [(1, 0.9), (1, 0.8), (0, 0.1), (0, 0.2), (0, 0.15)]),
            "catboost": _make_pred_df(self.spark, [(1, 0.55), (1, 0.4), (0, 0.45), (0, 0.35), (0, 0.2)]),
        }
        best_model, best_val_pr, _, _, _, _, _ = _select_and_scan_thresholds(
            val_results_df, val_predictions, self.config, "dataset_b", "Dataset B"
        )
        self.assertEqual(best_model, "xgboost")
        self.assertAlmostEqual(best_val_pr, 0.91, places=4)

    def test_threshold_scan_uses_validation_predictions_only(self):
        # Validation has 6 rows; test has 11 rows. Threshold scan sums must equal 6, not 11.
        val_results_df = pd.DataFrame([{"model_name": "lightgbm", "pr_auc": 0.88}])
        val_df = _make_pred_df(
            self.spark,
            [(1, 0.9), (1, 0.85), (0, 0.1), (0, 0.2), (0, 0.15), (0, 0.05)],
        )
        val_predictions = {"lightgbm": val_df}

        _, _, threshold_df, _, _, _, _ = _select_and_scan_thresholds(
            val_results_df, val_predictions, self.config, "dataset_a", "Dataset A"
        )
        self.assertGreater(len(threshold_df), 0)
        for _, row in threshold_df.iterrows():
            total_scanned = row["true_positives"] + row["false_positives"] + row["true_negatives"] + row["false_negatives"]
            self.assertEqual(total_scanned, 6)

    def test_per_model_validation_predictions_not_overwritten(self):
        # First model wins validation PR-AUC; last model in dict has terrible probabilities.
        val_results_df = pd.DataFrame(
            [
                {"model_name": "logistic_regression", "pr_auc": 0.95},
                {"model_name": "catboost", "pr_auc": 0.40},
            ]
        )
        # At threshold 0.50: logistic_regression has zero FP and zero FN (cost=0.0)
        val_predictions = {
            "logistic_regression": _make_pred_df(
                self.spark, [(1, 0.92), (1, 0.88), (0, 0.08), (0, 0.12)]
            ),
            # Catboost misses all positives even at low thresholds (high cost)
            "catboost": _make_pred_df(
                self.spark, [(1, 0.01), (1, 0.02), (0, 0.99), (0, 0.98)]
            ),
        }
        best_model, _, threshold_df, _, val_cost, _, _ = _select_and_scan_thresholds(
            val_results_df, val_predictions, self.config, "dataset_b", "Dataset B"
        )
        self.assertEqual(best_model, "logistic_regression")
        self.assertEqual(val_cost, 0.0)
        self.assertEqual(threshold_df["model_name"].unique().tolist(), ["logistic_regression"])

    def test_frozen_threshold_reused_for_single_heldout_test_eval(self):
        # Validation minimum cost occurs at t=0.85 -> test must be evaluated strictly at 0.85
        test_df = _make_pred_df(
            self.spark,
            [
                (1, 0.90),  # TP at 0.85
                (1, 0.60),  # FN at 0.85 (would be TP at 0.50!)
                (0, 0.88),  # FP at 0.85
                (0, 0.20),  # TN at 0.85
            ],
        )
        frozen_df = _evaluate_frozen_threshold_on_test(
            test_df,
            best_model_name="xgboost",
            best_val_pr_auc=0.82,
            frozen_threshold=0.85,
            frozen_val_cost=100.0,
            cost_fp=10.0,
            cost_fn=500.0,
            dataset_key="dataset_b",
            ds_name="Dataset B",
        )
        row = frozen_df.iloc[0]
        self.assertEqual(row["frozen_threshold"], 0.85)
        self.assertEqual(row["true_positives"], 1)
        self.assertEqual(row["false_negatives"], 1)
        self.assertEqual(row["false_positives"], 1)
        self.assertEqual(row["true_negatives"], 1)
        self.assertEqual(row["total_operational_cost"], 510.0)

    def test_single_source_cost_weights_reused(self):
        thresh_sig = inspect.signature(scan_decision_thresholds).parameters
        expected_fp = float(thresh_sig["cost_fp"].default)
        expected_fn = float(thresh_sig["cost_fn"].default)
        self.assertEqual(expected_fp, 10.0)
        self.assertEqual(expected_fn, 500.0)

        val_results_df = pd.DataFrame([{"model_name": "random_forest", "pr_auc": 0.80}])
        val_predictions = {
            "random_forest": _make_pred_df(self.spark, [(1, 0.20), (0, 0.90), (0, 0.10)]),
        }
        _, _, threshold_df, frozen_t, _, c_fp, c_fn = _select_and_scan_thresholds(
            val_results_df, val_predictions, self.config, "dataset_b", "Dataset B"
        )
        self.assertEqual(c_fp, expected_fp)
        self.assertEqual(c_fn, expected_fn)
        row_05 = threshold_df[threshold_df["threshold"] == 0.5].iloc[0]
        self.assertEqual(
            row_05["total_operational_cost"],
            round(row_05["false_positives"] * expected_fp + row_05["false_negatives"] * expected_fn, 2),
        )
        test_df = _make_pred_df(self.spark, [(1, 0.10), (0, 0.99)])
        frozen_df = _evaluate_frozen_threshold_on_test(
            test_df, "random_forest", 0.80, frozen_t, 0.0, c_fp, c_fn, "dataset_b", "Dataset B"
        )
        frow = frozen_df.iloc[0]
        self.assertEqual(
            frow["total_operational_cost"],
            round(frow["false_positives"] * expected_fp + frow["false_negatives"] * expected_fn, 2),
        )

    def test_end_to_end_pipeline_mock_no_tune_exports_frozen_threshold(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_cfg = {**self.config}
            tmp_cfg["outputs"] = {
                "metrics_dir": str(Path(tmpdir) / "metrics"),
                "figures_dir": str(Path(tmpdir) / "figures"),
                "summaries_dir": str(Path(tmpdir) / "summaries"),
                "logs_dir": str(Path(tmpdir) / "logs"),
                "powerbi_dir": str(Path(tmpdir) / "powerbi"),
            }
            # Minimal fast configs so all 5 models train quickly on 200 mock rows
            tmp_cfg["models"] = {
                "logistic_regression": {"max_iter": 10, "reg_param": 0.01},
                "random_forest": {"num_trees": 5, "max_depth": 3},
                "xgboost": {"n_estimators": 5, "max_depth": 3, "learning_rate": 0.1},
                "lightgbm": {"n_estimators": 5, "max_depth": 3, "learning_rate": 0.1, "verbose": -1},
                "catboost": {"iterations": 5, "depth": 3, "learning_rate": 0.1, "verbose": 0},
            }
            res = run_single_dataset(
                self.spark,
                tmp_cfg,
                dataset_key="dataset_b",
                force_mock=True,
                mock_samples=200,
                tune_hyperparams=False,
            )
            self.assertEqual(len(res["results_df"]), 5)
            self.assertEqual(len(res["val_results_df"]), 5)
            frozen_path = Path(tmpdir) / "summaries" / "dataset_b_frozen_threshold_test.csv"
            self.assertTrue(frozen_path.exists())
            frozen_csv = pd.read_csv(frozen_path)
            self.assertEqual(frozen_csv.loc[0, "selection_metric"], "val_pr_auc")
            expected_best = (
                res["val_results_df"].sort_values(by="pr_auc", ascending=False).iloc[0]["model_name"]
            )
            self.assertEqual(frozen_csv.loc[0, "model_name"], expected_best)

    # ------------------------------------------------------------------
    # Fix 2: Row-Weighted Group-Aware Split Tests (6 tests)
    # ------------------------------------------------------------------

    def _build_synthetic_grouped_df(self):
        """Construct synthetic dataset with multi-row duplicates, nulls, and realistic sizes."""
        rows = []
        # 500 legitimate rows across unique + duplicate groups (max legit group size = 10)
        idx = 0
        for g in range(10):  # 10 groups of size 10 = 100 rows
            for _ in range(10):
                rows.append((float(g), None if g % 2 == 0 else float(g * 2), 10.0 + g, 0))
            idx += 1
        for g in range(10, 410):  # 400 unique rows
            rows.append((float(g), 0.0 if g % 2 == 0 else float(g * 2), 25.0, 0))

        # 50 fraud rows across fraud groups (max fraud group size = 3)
        # 5 groups of size 3 = 15 rows, 35 groups of size 1 = 35 rows -> 40 groups total
        for fg in range(5):
            for _ in range(3):
                rows.append((9000.0 + fg, -1.0, 99.0 + fg, 1))
        for fg in range(5, 40):
            rows.append((9000.0 + fg, -2.0, 150.0, 1))

        schema = StructType(
            [
                StructField("V1", DoubleType(), True),
                StructField("V2", DoubleType(), True),
                StructField("Amount", DoubleType(), True),
                StructField("Class", IntegerType(), False),
            ]
        )
        return self.spark.createDataFrame(rows, schema=schema)

    def test_group_aware_split_preserves_all_rows(self):
        df = self._build_synthetic_grouped_df()
        total = df.count()
        tr, va, te = group_aware_stratified_split(df, target_col="Class", seed=42)
        self.assertEqual(tr.count() + va.count() + te.count(), total)

    def test_group_aware_split_zero_cross_partition_groups_and_null_safe(self):
        df = self._build_synthetic_grouped_df()
        tr, va, te = group_aware_stratified_split(df, target_col="Class", seed=42)

        feature_cols = sorted(["V1", "V2", "Amount"])
        gid_expr = F.sha2(
            F.to_json(F.struct(*[F.col(c) for c in feature_cols]), {"ignoreNullFields": "false"}),
            256,
        )
        combined = (
            tr.withColumn("_p", F.lit("train"))
            .unionByName(va.withColumn("_p", F.lit("val")))
            .unionByName(te.withColumn("_p", F.lit("test")))
            .withColumn("_gid", gid_expr)
        )
        cross_count = (
            combined.groupBy("_gid")
            .agg(F.countDistinct("_p").alias("n_p"))
            .filter(F.col("n_p") > 1)
            .count()
        )
        self.assertEqual(cross_count, 0)

        # Explicitly verify V2=None vs V2=0.0 at V1=10.0 produces distinct JSON group IDs
        null_vs_zero = self.spark.createDataFrame(
            [(10.0, None, 25.0, 0), (10.0, 0.0, 25.0, 0)],
            schema=df.schema,
        ).withColumn("_gid", gid_expr).collect()
        self.assertNotEqual(null_vs_zero[0]["_gid"], null_vs_zero[1]["_gid"])

    def test_group_aware_split_reproducible_seed_42(self):
        df = self._build_synthetic_grouped_df()
        tr1, va1, te1 = group_aware_stratified_split(df, target_col="Class", seed=42)
        tr2, va2, te2 = group_aware_stratified_split(df, target_col="Class", seed=42)

        self.assertEqual((tr1.count(), va1.count(), te1.count()), (tr2.count(), va2.count(), te2.count()))
        for a, b in ((tr1, tr2), (va1, va2), (te1, te2)):
            rows_a = sorted((r["V1"], r["V2"], r["Amount"], r["Class"]) for r in a.collect())
            rows_b = sorted((r["V1"], r["V2"], r["Amount"], r["Class"]) for r in b.collect())
            self.assertEqual(rows_a, rows_b)

    def test_group_aware_split_row_and_fraud_distribution_within_group_bounds(self):
        df = self._build_synthetic_grouped_df()
        total_rows = 550
        total_fraud = 50
        max_legit_group = 10
        max_fraud_group = 3

        tr, va, te = group_aware_stratified_split(df, target_col="Class", seed=42)
        ratios = {"train": 0.70, "val": 0.15, "test": 0.15}
        parts = {"train": tr, "val": va, "test": te}

        row_sum = 0
        fraud_sum = 0
        for name, pdf in parts.items():
            cnt = pdf.count()
            f_cnt = pdf.filter(F.col("Class") == 1).count()
            row_sum += cnt
            fraud_sum += f_cnt

            # Strict non-zero fraud requirement in every partition
            self.assertGreater(f_cnt, 0, f"Partition {name} must contain > 0 fraud rows")

            boundaries = 2 if name == "val" else 1
            max_fraud_dev = boundaries * max_fraud_group
            max_row_dev = boundaries * (max_fraud_group + max_legit_group)

            expected_fraud = ratios[name] * total_fraud
            expected_rows = ratios[name] * total_rows
            self.assertLessEqual(abs(f_cnt - expected_fraud), max_fraud_dev)
            self.assertLessEqual(abs(cnt - expected_rows), max_row_dev)

        self.assertEqual(row_sum, total_rows)
        self.assertEqual(fraud_sum, total_fraud)

    def test_group_aware_split_detects_conflicting_labels(self):
        schema = StructType(
            [
                StructField("V1", DoubleType(), True),
                StructField("Amount", DoubleType(), True),
                StructField("Class", IntegerType(), False),
            ]
        )
        bad_df = self.spark.createDataFrame(
            [(1.5, 42.0, 0), (1.5, 42.0, 1), (2.5, 10.0, 0)],
            schema=schema,
        )
        with self.assertRaises(ValueError):
            group_aware_stratified_split(bad_df, target_col="Class", seed=42)

    def test_dataset_a_time_aware_split_unaffected(self):
        df = generate_mock_ieee_cis_data(self.spark, num_records=120, fraud_rate=0.10, seed=42)
        tr, va, te = time_aware_split(df, time_col="TransactionDT")
        self.assertEqual(tr.count() + va.count() + te.count(), 120)
        max_tr = tr.agg(F.max("TransactionDT")).first()[0]
        min_va = va.agg(F.min("TransactionDT")).first()[0]
        max_va = va.agg(F.max("TransactionDT")).first()[0]
        min_te = te.agg(F.min("TransactionDT")).first()[0]
        self.assertLessEqual(max_tr, min_va)
        self.assertLessEqual(max_va, min_te)


if __name__ == "__main__":
    unittest.main()
