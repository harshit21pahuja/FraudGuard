"""Synthetic mock sample generator for IEEE-CIS pipeline smoke testing."""

import random
from typing import Any, List
from pathlib import Path

try:
    from pyspark.sql import DataFrame, SparkSession
    from pyspark.sql.types import (
        DoubleType,
        IntegerType,
        LongType,
        StringType,
        StructField,
        StructType,
    )
    PYSPARK_AVAILABLE = True
except ImportError:
    PYSPARK_AVAILABLE = False
    DataFrame = None  # type: ignore


def generate_mock_ieee_cis_data(
    spark: Any, num_records: int = 150, fraud_rate: float = 0.05, seed: int = 42
) -> DataFrame:
    """Generate a realistic mock Spark DataFrame mirroring IEEE-CIS schema for testing.

    Includes:
      - TransactionID, isFraud, TransactionDT, TransactionAmt
      - Categoricals: ProductCD, card4, card6, P_emaildomain, DeviceType
      - Numericals: card1, card2, C1, C2, D1, V1, V2, V3
    """
    random.seed(seed)
    product_codes = ["W", "H", "C", "S", "R"]
    card_types = ["visa", "mastercard", "discover"]
    card_tiers = ["debit", "credit"]
    domains = ["gmail.com", "yahoo.com", "hotmail.com", "anonymous.com", None]
    devices = ["mobile", "desktop", None]

    rows = []
    base_time = 86400  # Day 1 in seconds

    for i in range(num_records):
        trans_id = 3000000 + i
        # Simulate time progression
        trans_dt = base_time + (i * 300) + random.randint(0, 100)
        # 5% fraud probability
        is_fraud = 1 if random.random() < fraud_rate else 0
        amt = round(random.expovariate(1 / 100.0) + 5.0, 2)

        prod = random.choice(product_codes)
        c4 = random.choice(card_types)
        c6 = random.choice(card_tiers)
        p_email = random.choice(domains)
        dev = random.choice(devices)

        c1 = random.randint(1, 10)
        c2 = random.randint(1, 10)
        d1 = float(random.randint(0, 100)) if random.random() > 0.1 else None
        v1 = float(random.choice([0, 1, 2])) if random.random() > 0.05 else None
        v2 = float(random.choice([0, 1, 2])) if random.random() > 0.05 else None

        rows.append(
            (
                trans_id,
                is_fraud,
                trans_dt,
                amt,
                prod,
                c4,
                c6,
                p_email,
                dev,
                float(random.randint(1000, 9999)),  # card1
                float(random.randint(100, 999)),   # card2
                float(c1),
                float(c2),
                d1,
                v1,
                v2,
            )
        )

    schema = StructType(
        [
            StructField("TransactionID", LongType(), False),
            StructField("isFraud", IntegerType(), False),
            StructField("TransactionDT", LongType(), False),
            StructField("TransactionAmt", DoubleType(), False),
            StructField("ProductCD", StringType(), True),
            StructField("card4", StringType(), True),
            StructField("card6", StringType(), True),
            StructField("P_emaildomain", StringType(), True),
            StructField("DeviceType", StringType(), True),
            StructField("card1", DoubleType(), True),
            StructField("card2", DoubleType(), True),
            StructField("C1", DoubleType(), True),
            StructField("C2", DoubleType(), True),
            StructField("D1", DoubleType(), True),
            StructField("V1", DoubleType(), True),
            StructField("V2", DoubleType(), True),
        ]
    )

    return spark.createDataFrame(rows, schema=schema)
