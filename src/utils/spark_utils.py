"""SparkSession management and Spark utility functions for FraudGuard."""

from typing import Any, Dict
from src.utils.config import load_config

try:
    from pyspark.sql import SparkSession
    PYSPARK_AVAILABLE = True
except ImportError:
    PYSPARK_AVAILABLE = False
    SparkSession = None  # type: ignore


def get_spark_session(config: Dict[str, Any] | None = None) -> Any:
    """Create or retrieve an active Apache Spark session configured for FraudGuard.

    Args:
        config: Optional project configuration dictionary.

    Returns:
        SparkSession instance.
    """
    if not PYSPARK_AVAILABLE:
        raise ImportError(
            "PySpark is not installed in the current environment. "
            "Please install requirements using 'pip install -r requirements.txt' "
            "or run inside a supported environment (e.g. Google Colab / Databricks)."
        )

    if config is None:
        config = load_config()

    spark_cfg = config.get("spark", {})
    app_name = spark_cfg.get("app_name", "FraudGuard-SparkML")
    master = spark_cfg.get("master", "local[*]")
    driver_mem = spark_cfg.get("driver_memory", "4g")
    sql_shuffle_partitions = spark_cfg.get("sql_shuffle_partitions", 8)
    log_level = spark_cfg.get("log_level", "WARN")

    import os
    import sys

    # Bind Python executable to the current active environment (.venv)
    os.environ["PYSPARK_PYTHON"] = sys.executable
    os.environ["PYSPARK_DRIVER_PYTHON"] = sys.executable

    builder = (
        SparkSession.builder.appName(app_name)
        .master(master)
        .config("spark.driver.memory", driver_mem)
        .config("spark.sql.shuffle.partitions", str(sql_shuffle_partitions))
        .config("spark.ui.enabled", "false")  # Avoid port conflicts in local dev
        .config("spark.driver.host", "127.0.0.1")  # Loopback avoids Windows firewall blocks
        .config("spark.driver.bindAddress", "127.0.0.1")
    )

    spark = builder.getOrCreate()
    spark.sparkContext.setLogLevel(log_level)
    return spark
