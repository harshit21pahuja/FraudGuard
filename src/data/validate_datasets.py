"""Dataset discovery and presence validation for FraudGuard."""

import os
from pathlib import Path
from typing import Any, Dict
from src.utils.config import get_project_root, load_config


def validate_dataset_presence(config: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """Validate whether required raw dataset files are present in the workspace.

    Returns:
        Dictionary detailing existence, paths, and byte sizes of expected files.
    """
    if config is None:
        config = load_config()

    root = get_project_root()
    report: Dict[str, Any] = {"dataset_a": {}, "dataset_b": {}}

    # Dataset A (IEEE-CIS)
    cfg_a = config.get("datasets", {}).get("dataset_a", {})
    raw_dir_a = root / cfg_a.get("raw_dir", "data/raw/ieee_cis")
    trans_file = raw_dir_a / cfg_a.get("transaction_file", "train_transaction.csv")
    ident_file = raw_dir_a / cfg_a.get("identity_file", "train_identity.csv")

    report["dataset_a"] = {
        "name": cfg_a.get("name", "IEEE-CIS"),
        "transaction_file_path": str(trans_file),
        "transaction_file_exists": trans_file.exists(),
        "transaction_file_size_mb": round(trans_file.stat().st_size / (1024 * 1024), 2)
        if trans_file.exists()
        else 0.0,
        "identity_file_path": str(ident_file),
        "identity_file_exists": ident_file.exists(),
        "identity_file_size_mb": round(ident_file.stat().st_size / (1024 * 1024), 2)
        if ident_file.exists()
        else 0.0,
        "ready": trans_file.exists() and ident_file.exists(),
    }

    # Dataset B
    cfg_b = config.get("datasets", {}).get("dataset_b", {})
    raw_dir_b = root / cfg_b.get("raw_dir", "data/raw/creditcard")
    data_file_b = raw_dir_b / cfg_b.get("transaction_file", "creditcard.csv")

    report["dataset_b"] = {
        "name": cfg_b.get("name", "Dataset B"),
        "candidate_status": cfg_b.get("candidate_status", "Pending Confirmation"),
        "file_path": str(data_file_b),
        "file_exists": data_file_b.exists(),
        "file_size_mb": round(data_file_b.stat().st_size / (1024 * 1024), 2)
        if data_file_b.exists()
        else 0.0,
        "ready": data_file_b.exists(),
    }

    return report


if __name__ == "__main__":
    status = validate_dataset_presence()
    print("--- FraudGuard Dataset Validation Report ---")
    for ds_key, details in status.items():
        print(f"\n[{ds_key.upper()}] {details.get('name')}")
        for k, v in details.items():
            if k != "name":
                print(f"  - {k}: {v}")
