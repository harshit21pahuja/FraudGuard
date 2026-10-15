"""Unit tests for Exploratory Data Analysis module."""

import unittest
from pathlib import Path
from src.utils.config import load_config
from src.utils.spark_utils import PYSPARK_AVAILABLE, get_spark_session
from src.data.mock_generator import generate_mock_ieee_cis_data
from src.features.eda import (
    compute_amount_distribution,
    compute_fraud_by_categorical,
    compute_missingness_profile,
    export_eda_reports,
)


@unittest.skipUnless(PYSPARK_AVAILABLE, "PySpark not installed")
class TestEDAModule(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        config = load_config()
        config["spark"]["master"] = "local[1]"
        cls.spark = get_spark_session(config)
        cls.df = generate_mock_ieee_cis_data(cls.spark, num_records=80, fraud_rate=0.10, seed=42)

    @classmethod
    def tearDownClass(cls):
        if cls.spark:
            cls.spark.stop()

    def test_missingness_profile(self):
        missing_df = compute_missingness_profile(self.df, top_n=10)
        self.assertFalse(missing_df.empty)
        self.assertIn("column_name", missing_df.columns)
        self.assertIn("missing_percentage", missing_df.columns)

    def test_fraud_by_categorical(self):
        cat_df = compute_fraud_by_categorical(self.df, cat_col="ProductCD")
        self.assertFalse(cat_df.empty)
        self.assertIn("total_transactions", cat_df.columns)
        self.assertIn("fraud_transactions", cat_df.columns)
        self.assertIn("fraud_rate_pct", cat_df.columns)

    def test_amount_distribution(self):
        amt_df = compute_amount_distribution(self.df)
        self.assertFalse(amt_df.empty)
        self.assertIn("avg_amount", amt_df.columns)
        self.assertIn("class_label", amt_df.columns)

    def test_export_eda_reports(self):
        test_out = Path("outputs/test_eda")
        paths = export_eda_reports(self.df, output_dir=test_out)
        self.assertIn("missingness", paths)
        self.assertTrue(paths["missingness"].exists())
        # Clean up test output
        for p in paths.values():
            if p.exists():
                p.unlink()
        if test_out.exists():
            test_out.rmdir()


if __name__ == "__main__":
    unittest.main()
