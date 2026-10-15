"""Academic-grade visualization generator for FraudGuard evaluation and reports."""

from pathlib import Path
from typing import List, Dict, Any
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("FraudGuard.Visualizations")

try:
    import matplotlib.pyplot as plt
    import seaborn as sns
    import pandas as pd
    import numpy as np
    VIS_AVAILABLE = True
except ImportError:
    VIS_AVAILABLE = False


def setup_plot_style() -> None:
    """Set academic standard styling for Matplotlib and Seaborn."""
    if not VIS_AVAILABLE:
        return
    plt.style.use("seaborn-v0_8-whitegrid" if "seaborn-v0_8-whitegrid" in plt.style.available else "default")
    plt.rcParams.update({
        "font.family": "sans-serif",
        "font.size": 11,
        "axes.labelsize": 12,
        "axes.titlesize": 13,
        "xtick.labelsize": 10,
        "ytick.labelsize": 10,
        "figure.titlesize": 14,
        "figure.dpi": 300,
    })


def plot_model_comparison(results_df: "pd.DataFrame", output_path: Path) -> None:
    """Generate a grouped bar chart comparing Precision, Recall, F1, and ROC-AUC for all 5 classifiers."""
    if not VIS_AVAILABLE:
        logger.warning("Matplotlib/Seaborn not installed. Skipping plot generation.")
        return

    setup_plot_style()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    metrics = ["precision", "recall", "f1_score", "roc_auc"]
    metric_labels = ["Precision", "Recall", "F1-Score", "ROC-AUC"]
    models = results_df["model_name"].tolist()

    x = np.arange(len(models))
    width = 0.2

    fig, ax = plt.subplots(figsize=(10, 6))
    colors = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728"]

    for i, (m, label, color) in enumerate(zip(metrics, metric_labels, colors)):
        vals = results_df[m].tolist()
        rects = ax.bar(x + (i - 1.5) * width, vals, width, label=label, color=color, alpha=0.85)
        # Value labels above bars
        for rect in rects:
            height = rect.get_height()
            if height > 0:
                ax.annotate(
                    f"{height:.2f}",
                    xy=(rect.get_x() + rect.get_width() / 2, height),
                    xytext=(0, 3),
                    textcoords="offset points",
                    ha="center",
                    va="bottom",
                    fontsize=8,
                )

    ax.set_xlabel("Spark ML Classifier", fontweight="bold")
    ax.set_ylabel("Score (0.0 – 1.0)", fontweight="bold")
    ax.set_title("FraudGuard: Held-Out Model Performance Comparison", fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels(models, rotation=15, ha="right")
    ax.set_ylim(0, 1.15)
    ax.legend(loc="upper right", frameon=True)
    ax.grid(axis="y", linestyle="--", alpha=0.6)

    plt.tight_layout()
    plt.savefig(output_path, dpi=300)
    plt.close()
    logger.info(f"Model comparison figure saved to: {output_path}")


def plot_threshold_curves(threshold_df: "pd.DataFrame", output_path: Path) -> None:
    """Generate Precision-Recall Trade-off and Cost Curves across decision thresholds."""
    if not VIS_AVAILABLE:
        return

    setup_plot_style()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))

    # 1. Precision vs Recall Curve
    ax1.plot(
        threshold_df["threshold"], threshold_df["precision"],
        marker="o", label="Precision", color="#1f77b4", linewidth=2
    )
    ax1.plot(
        threshold_df["threshold"], threshold_df["recall"],
        marker="s", label="Recall", color="#d62728", linewidth=2
    )
    ax1.plot(
        threshold_df["threshold"], threshold_df["f1_score"],
        marker="^", label="F1-Score", color="#2ca02c", linestyle="--", linewidth=1.8
    )
    ax1.set_xlabel("Decision Threshold (0.05 to 0.95)", fontweight="bold")
    ax1.set_ylabel("Score", fontweight="bold")
    ax1.set_title("Operational Trade-off: Precision vs. Recall", fontweight="bold")
    ax1.set_ylim(-0.05, 1.05)
    ax1.legend(loc="best", frameon=True)
    ax1.grid(True, linestyle="--", alpha=0.5)

    # 2. Total Operational Cost Curve
    ax2.plot(
        threshold_df["threshold"], threshold_df["total_operational_cost"],
        marker="D", color="#8c564b", linewidth=2.2, label="Total Cost ($)"
    )
    # Highlight minimum cost threshold
    min_idx = threshold_df["total_operational_cost"].idxmin()
    min_thresh = threshold_df.loc[min_idx, "threshold"]
    min_cost = threshold_df.loc[min_idx, "total_operational_cost"]

    ax2.scatter([min_thresh], [min_cost], color="red", s=120, zorder=5, label=f"Optimal ({min_thresh:.2f}, ${min_cost:,.0f})")
    ax2.set_xlabel("Decision Threshold", fontweight="bold")
    ax2.set_ylabel("Operational Cost ($)", fontweight="bold")
    ax2.set_title("Financial Cost Minimization Curve", fontweight="bold")
    ax2.legend(loc="upper right", frameon=True)
    ax2.grid(True, linestyle="--", alpha=0.5)

    plt.tight_layout()
    plt.savefig(output_path, dpi=300)
    plt.close()
    logger.info(f"Threshold trade-off figure saved to: {output_path}")


def plot_confusion_matrices_grid(results_df: "pd.DataFrame", output_path: Path) -> None:
    """Generate a grid of 2x2 confusion matrices for all evaluated classifiers."""
    if not VIS_AVAILABLE:
        return

    setup_plot_style()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    n_models = len(results_df)
    cols = 3
    rows = (n_models + cols - 1) // cols

    fig, axes = plt.subplots(rows, cols, figsize=(4.5 * cols, 3.8 * rows))
    axes = np.array(axes).reshape(-1)

    for i, (_, row) in enumerate(results_df.iterrows()):
        ax = axes[i]
        matrix = np.array([
            [row["true_negatives"], row["false_positives"]],
            [row["false_negatives"], row["true_positives"]],
        ])
        sns.heatmap(
            matrix, annot=True, fmt=",d", cmap="Blues", cbar=False, ax=ax,
            xticklabels=["Legit (0)", "Fraud (1)"],
            yticklabels=["Legit (0)", "Fraud (1)"],
            annot_kws={"size": 11, "weight": "bold"},
        )
        ax.set_title(f"{row['model_name']}", fontweight="bold", fontsize=11)
        ax.set_xlabel("Predicted Label")
        ax.set_ylabel("True Label")

    # Hide extra subplots
    for j in range(i + 1, len(axes)):
        fig.delaxes(axes[j])

    plt.suptitle("Confusion Matrices (Test Set Evaluation)", fontsize=14, fontweight="bold", y=0.99)
    plt.tight_layout()
    plt.savefig(output_path, dpi=300)
    plt.close()
    logger.info(f"Confusion matrix grid saved to: {output_path}")
