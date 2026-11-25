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
        
        # Ensure fraud occurs periodically throughout the timeline so train, val, and test all receive fraud cases
        is_fraud = 1 if (i % int(1.0 / fraud_rate) == 0 or random.random() < (fraud_rate * 0.5)) else 0

        # Inject realistic fraud patterns (high amounts, suspicious domains, extreme velocity)
        if is_fraud == 1:
            amt = round(random.uniform(250.0, 1200.0), 2)
            p_email = random.choice(["anonymous.com", "mailinator.com", None])
            c1 = random.randint(15, 50)  # High transaction count/velocity
            c2 = random.randint(10, 40)
            v1 = float(random.choice([2, 3, 4]))
            v2 = float(random.choice([3, 4, 5]))
            prod = random.choice(["C", "R"])
        else:
            amt = round(random.expovariate(1 / 80.0) + 10.0, 2)
            p_email = random.choice(["gmail.com", "yahoo.com", "hotmail.com"])
            c1 = random.randint(1, 5)
            c2 = random.randint(1, 4)
            v1 = float(random.choice([0, 1]))
            v2 = float(random.choice([0, 1]))
            prod = random.choice(product_codes)

        c4 = random.choice(card_types)
        c6 = random.choice(card_tiers)
        dev = random.choice(devices)
        d1 = float(random.randint(0, 100)) if random.random() > 0.1 else None
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


def generate_mock_creditcard_data(
    spark: Any, num_records: int = 200, fraud_rate: float = 0.05, seed: int = 42
) -> DataFrame:
    """Generate a realistic mock Spark DataFrame mirroring ULB Credit Card Fraud schema."""
    random.seed(seed)
    feature_cols = ["Time"] + [f"V{idx}" for idx in range(1, 29)] + ["Amount"]
    rows = []
    for i in range(num_records):
        is_fraud = 1 if (i % max(1, int(1.0 / fraud_rate)) == 0) else 0
        t_val = float(i * 600 + random.randint(0, 300))
        if is_fraud == 1:
            v_vals = [round(random.gauss(-2.0 if k in (1, 3, 4, 10, 14) else 0.5, 1.2), 4) for k in range(1, 29)]
            amt = round(random.uniform(120.0, 900.0), 2)
        else:
            v_vals = [round(random.gauss(0.2 if k in (1, 3, 14) else 0.0, 0.8), 4) for k in range(1, 29)]
            amt = round(random.expovariate(1 / 60.0) + 1.0, 2)
        rows.append((t_val, *v_vals, amt, is_fraud))

    schema = StructType(
        [StructField(c, DoubleType(), False) for c in feature_cols]
        + [StructField("Class", IntegerType(), False)]
    )
    return spark.createDataFrame(rows, schema=schema)
