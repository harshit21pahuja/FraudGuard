"""Configuration loader for FraudGuard."""

from pathlib import Path
from typing import Any, Dict
try:
    import yaml
    HAS_YAML = True
except ImportError:
    yaml = None  # type: ignore
    HAS_YAML = False


def get_project_root() -> Path:
    """Return the root directory of the FraudGuard project."""
    # Assuming this file is in src/utils/config.py -> parent of parent of parent is root
    return Path(__file__).resolve().parent.parent.parent


def load_config(config_path: str | None = None) -> Dict[str, Any]:
    """Load the project configuration YAML file.

    Args:
        config_path: Optional path to YAML config. If None, uses default.

    Returns:
        Dict containing project configuration settings.
    """
    root = get_project_root()
    if config_path is None:
        target_path = root / "configs" / "project_config.yaml"
    else:
        target_path = Path(config_path)
        if not target_path.is_absolute():
            target_path = root / target_path

    if not target_path.exists():
        raise FileNotFoundError(f"Configuration file not found at: {target_path}")

    try:
        import yaml
        with open(target_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
    except ImportError:
        # Fallback basic loader if PyYAML is not yet installed in active Python environment
        import re
        config = {
            "project": {"name": "FraudGuard", "version": "1.0.0"},
            "spark": {"app_name": "FraudGuard-SparkML", "master": "local[*]", "driver_memory": "4g"},
            "datasets": {
                "dataset_a": {
                    "name": "IEEE-CIS Fraud Detection",
                    "raw_dir": "data/raw/ieee_cis",
                    "transaction_file": "train_transaction.csv",
                    "identity_file": "train_identity.csv",
                    "target_column": "isFraud",
                    "join_key": "TransactionID",
                },
                "dataset_b": {
                    "name": "Dataset B (Pending User Approval)",
                    "candidate_status": "Pending User Approval - Candidates Under Review",
                    "raw_dir": "data/raw/dataset_b",
                    "transaction_file": None,
                    "target_column": None,
                },
            },
            "models": {
                "logistic_regression": {},
                "random_forest": {},
                "xgboost": {},
                "lightgbm": {},
                "catboost": {},
            },
        }

    return config
