"""Utility to automate or guide dataset downloads from Kaggle."""

import os
from pathlib import Path
import logging
from src.utils.config import get_project_root

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("FraudGuard.Downloader")


def check_kaggle_credentials() -> bool:
    """Check if Kaggle credentials file kaggle.json exists in user's home directory."""
    kaggle_dir = Path.home() / ".kaggle"
    kaggle_json = kaggle_dir / "kaggle.json"
    return kaggle_json.exists()


def download_ieee_cis_dataset(target_dir: Path | None = None) -> None:
    """Download IEEE-CIS dataset using Kaggle CLI or API if credentials are present."""
    root = get_project_root()
    dest = target_dir or (root / "data" / "raw" / "ieee_cis")
    dest.mkdir(parents=True, exist_ok=True)

    if not check_kaggle_credentials():
        logger.warning(
            "Kaggle credentials not detected at ~/.kaggle/kaggle.json\n"
            "To download automatically:\n"
            "  1. Go to https://www.kaggle.com/settings -> 'Create New Token' -> downloads kaggle.json\n"
            "  2. Place kaggle.json in ~/.kaggle/ (or C:\\Users\\<User>\\.kaggle\\kaggle.json)\n"
            "Alternatively, manually download from:\n"
            "  https://www.kaggle.com/competitions/ieee-fraud-detection/data\n"
            f"  and place train_transaction.csv & train_identity.csv into: {dest}"
        )
        return

    try:
        import kaggle
        logger.info(f"Downloading IEEE-CIS dataset to {dest}...")
        kaggle.api.competition_download_file(
            "ieee-fraud-detection", "train_transaction.csv", path=str(dest)
        )
        kaggle.api.competition_download_file(
            "ieee-fraud-detection", "train_identity.csv", path=str(dest)
        )
        logger.info("Download completed successfully.")
    except Exception as e:
        logger.error(f"Failed to download via Kaggle API: {e}")


if __name__ == "__main__":
    download_ieee_cis_dataset()
