"""Utility to automate or guide dataset downloads for FraudGuard."""

import argparse
import logging
import zipfile
from pathlib import Path

from src.utils.config import get_project_root

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("FraudGuard.Downloader")


def check_kaggle_credentials() -> bool:
    """Check if Kaggle credentials file kaggle.json exists in user's home directory."""
    kaggle_json = Path.home() / ".kaggle" / "kaggle.json"
    return kaggle_json.exists()


def _extract_if_zipped(dest: Path, filename: str) -> None:
    """Extract a Kaggle-downloaded .zip archive if present and remove the zip."""
    zip_path = dest / f"{filename}.zip"
    if zip_path.exists():
        logger.info(f"Extracting {zip_path.name}...")
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(dest)
        zip_path.unlink()


def download_ieee_cis_dataset(target_dir: Path | None = None) -> bool:
    """Download IEEE-CIS dataset using Kaggle API if credentials are present."""
    root = get_project_root()
    dest = target_dir or (root / "data" / "raw" / "ieee_cis")
    dest.mkdir(parents=True, exist_ok=True)

    trans_csv = dest / "train_transaction.csv"
    ident_csv = dest / "train_identity.csv"
    if trans_csv.exists() and ident_csv.exists():
        logger.info(f"IEEE-CIS files already present in {dest}")
        return True

    if not check_kaggle_credentials():
        logger.warning(
            "Kaggle credentials not detected at ~/.kaggle/kaggle.json\n"
            "To download automatically:\n"
            "  1. Go to https://www.kaggle.com/settings -> 'Create New Token' -> downloads kaggle.json\n"
            "  2. Place kaggle.json in ~/.kaggle/ (or C:\\Users\\<User>\\.kaggle\\kaggle.json)\n"
            "  3. Accept competition rules at https://www.kaggle.com/competitions/ieee-fraud-detection/rules\n"
            "Alternatively, manually download train_transaction.csv & train_identity.csv into:\n"
            f"  {dest}"
        )
        return False

    try:
        import kaggle

        logger.info(f"Downloading IEEE-CIS dataset to {dest}...")
        for fname in ("train_transaction.csv", "train_identity.csv"):
            kaggle.api.competition_download_file("ieee-fraud-detection", fname, path=str(dest))
            _extract_if_zipped(dest, fname)
        logger.info("IEEE-CIS download completed successfully.")
        return trans_csv.exists() and ident_csv.exists()
    except Exception as e:
        logger.error(f"Failed to download IEEE-CIS via Kaggle API: {e}")
        return False


def download_ulb_creditcard_dataset(target_dir: Path | None = None) -> Path:
    """Download ULB European Cardholders Credit Card Fraud dataset (OpenML ID 1597, ODbL)."""
    root = get_project_root()
    dest = target_dir or (root / "data" / "raw" / "dataset_b")
    dest.mkdir(parents=True, exist_ok=True)
    out_csv = dest / "creditcard.csv"

    if out_csv.exists() and out_csv.stat().st_size > 1_000_000:
        logger.info(f"Dataset B already present at {out_csv} ({out_csv.stat().st_size / (1024*1024):.2f} MB)")
        return out_csv

    from sklearn.datasets import fetch_openml

    logger.info("Fetching ULB Credit Card Fraud dataset from OpenML (data_id=1597, ODbL license)...")
    bunch = fetch_openml(data_id=1597, as_frame=True, parser="auto")
    df = bunch.frame.copy()
    if "Class" in df.columns:
        df["Class"] = df["Class"].astype(str).str.strip("'\"").astype(int)

    logger.info(f"Saving {len(df):,} rows and {len(df.columns)} columns to {out_csv}...")
    df.to_csv(out_csv, index=False)
    logger.info(f"Dataset B saved successfully ({out_csv.stat().st_size / (1024*1024):.2f} MB).")
    return out_csv


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Download FraudGuard datasets")
    parser.add_argument("--dataset", choices=["a", "b", "all"], default="all")
    args = parser.parse_args()

    if args.dataset in ("a", "all"):
        download_ieee_cis_dataset()
    if args.dataset in ("b", "all"):
        download_ulb_creditcard_dataset()
