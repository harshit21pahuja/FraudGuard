"""Academic-grade visualization generator for FraudGuard evaluation and reports."""

from pathlib import Path
from typing import Any, Dict, List, Tuple
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

    ax.set_xlabel("Binary Classifier", fontweight="bold")
    ax.set_ylabel("Score (0.0 – 1.0)", fontweight="bold")
    ax.set_title("FraudGuard: Held-Out Model Performance Comparison", fontweight="bold", pad=26)
    ax.set_xticks(x)
    ax.set_xticklabels(models, rotation=15, ha="right")
    ax.set_ylim(0, 1.12)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, 1.08), ncol=4, frameon=True)
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


def plot_roc_and_pr_curves(
    curve_data: Dict[str, Tuple["np.ndarray", "np.ndarray"]],
    roc_output_path: Path,
    pr_output_path: Path,
    dataset_label: str = "",
) -> None:
    """Plot overlaid ROC curves and Precision-Recall curves across all 5 classifiers."""
    if not VIS_AVAILABLE or not curve_data:
        return

    from sklearn.metrics import auc, average_precision_score, precision_recall_curve, roc_curve

    setup_plot_style()
    roc_output_path.parent.mkdir(parents=True, exist_ok=True)
    pr_output_path.parent.mkdir(parents=True, exist_ok=True)
    palette = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd"]
    title_suffix = f"\n({dataset_label})" if dataset_label else ""

    # 1. ROC Curves
    fig, ax = plt.subplots(figsize=(8, 6))
    for idx, (m_name, (y_true, y_prob)) in enumerate(curve_data.items()):
        if len(np.unique(y_true)) < 2:
            continue
        fpr, tpr, _ = roc_curve(y_true, y_prob)
        roc_val = auc(fpr, tpr)
        ax.plot(fpr, tpr, lw=2.0, color=palette[idx % len(palette)], label=f"{m_name} (AUC = {roc_val:.4f})")
    ax.plot([0, 1], [0, 1], "k--", lw=1.2, alpha=0.6, label="Random Baseline (AUC = 0.5000)")
    ax.set_xlabel("False Positive Rate (1 - Specificity)", fontweight="bold")
    ax.set_ylabel("True Positive Rate (Recall)", fontweight="bold")
    ax.set_title(f"ROC-AUC Curves Across 5 Classifiers{title_suffix}", fontweight="bold", fontsize=12)
    ax.legend(loc="lower right", frameon=True, fontsize=9)
    ax.grid(True, linestyle="--", alpha=0.5)
    plt.tight_layout()
    plt.savefig(roc_output_path, dpi=300)
    plt.close()
    logger.info(f"ROC curves saved to: {roc_output_path}")

    # 2. Precision-Recall Curves
    fig, ax = plt.subplots(figsize=(8, 6))
    prevalence = 0.0
    for idx, (m_name, (y_true, y_prob)) in enumerate(curve_data.items()):
        if len(np.unique(y_true)) < 2:
            continue
        prevalence = float(np.mean(y_true))
        prec, rec, _ = precision_recall_curve(y_true, y_prob)
        ap_val = average_precision_score(y_true, y_prob)
        ax.plot(rec, prec, lw=2.0, color=palette[idx % len(palette)], label=f"{m_name} (AP = {ap_val:.4f})")
    ax.axhline(prevalence, color="gray", linestyle="--", lw=1.2, label=f"No-Skill Baseline (AP = {prevalence:.4f})")
    ax.set_xlabel("Recall (Sensitivity)", fontweight="bold")
    ax.set_ylabel("Precision", fontweight="bold")
    ax.set_title(f"Precision-Recall Curves Across 5 Classifiers{title_suffix}", fontweight="bold", fontsize=12)
    ax.set_ylim(-0.02, 1.05)
    ax.legend(loc="lower left", frameon=True, fontsize=9)
    ax.grid(True, linestyle="--", alpha=0.5)
    plt.tight_layout()
    plt.savefig(pr_output_path, dpi=300)
    plt.close()
    logger.info(f"Precision-Recall curves saved to: {pr_output_path}")


def plot_cross_dataset_comparison(combined_df: "pd.DataFrame", output_path: Path) -> None:
    """Plot side-by-side comparison of PR-AUC, ROC-AUC, F1-Score, and Log Loss across datasets."""
    if not VIS_AVAILABLE or combined_df.empty:
        return

    setup_plot_style()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    datasets = combined_df["dataset_name"].unique().tolist()
    if len(datasets) < 2:
        return

    fig, axes = plt.subplots(1, 3, figsize=(16, 5.4))
    metrics_to_plot = [
        ("f1_score", "F1-Score (Held-Out Test)"),
        ("roc_auc", "ROC-AUC (Held-Out Test)"),
        ("pr_auc", "PR-AUC (Imbalanced Precision-Recall)"),
    ]
    handles, labels = None, None
    for ax, (col, title) in zip(axes, metrics_to_plot):
        pivot = combined_df.pivot(index="model_name", columns="dataset_name", values=col)
        pivot.plot(kind="bar", ax=ax, width=0.72, alpha=0.88, legend=False)
        ax.set_title(title, fontweight="bold", fontsize=11)
        ax.set_xlabel("")
        ax.set_ylabel("Score")
        ax.set_ylim(0, 1.12)
        ax.tick_params(axis="x", rotation=25)
        ax.grid(axis="y", linestyle="--", alpha=0.5)
        if handles is None:
            handles, labels = ax.get_legend_handles_labels()

    if handles and labels:
        fig.legend(handles, labels, loc="upper center", bbox_to_anchor=(0.5, 0.93), ncol=len(labels), frameon=True, fontsize=9)
    plt.suptitle("FraudGuard Cross-Dataset Performance Comparison", fontsize=14, fontweight="bold", y=0.99)
    plt.tight_layout(rect=[0, 0, 1, 0.88])
    plt.savefig(output_path, dpi=300)
    plt.close()
    logger.info(f"Cross-dataset comparison chart saved to: {output_path}")


def plot_eda_overview(
    dataset_name: str,
    target_stats: Dict[str, Any],
    amount_df: "pd.DataFrame",
    output_path: Path,
    hourly_df: "pd.DataFrame | None" = None,
    cat_df: "pd.DataFrame | None" = None,
) -> None:
    """Generate a 3-panel EDA overview chart (class imbalance, amount stats, and temporal/category fraud rate)."""
    if not VIS_AVAILABLE:
        return

    setup_plot_style()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(1, 3, figsize=(16, 4.8))

    # Panel 1: Class Imbalance (Log Scale)
    counts = [target_stats["legitimate_count"], target_stats["fraud_count"]]
    labels = ["Legitimate (0)", "Fraudulent (1)"]
    bars = axes[0].bar(labels, counts, color=["#2ca02c", "#d62728"], alpha=0.88)
    axes[0].set_yscale("log")
    axes[0].set_ylim(top=max(1, max(counts)) * 2.5)
    axes[0].set_title("Class Imbalance (Log Scale)", fontweight="bold", fontsize=11)
    axes[0].set_ylabel("Transaction Count (log)")
    for b, c in zip(bars, counts):
        axes[0].text(b.get_x() + b.get_width() / 2, c * 1.18, f"{c:,}", ha="center", va="bottom", fontsize=9, fontweight="bold")
    axes[0].grid(axis="y", linestyle="--", alpha=0.5)

    # Panel 2: Mean vs Max Transaction Amount by Class
    if not amount_df.empty:
        x = np.arange(len(amount_df))
        axes[1].bar(x - 0.18, amount_df["avg_amount"], width=0.35, label="Mean Amount", color="#1f77b4")
        axes[1].bar(x + 0.18, amount_df["stddev_amount"].fillna(0), width=0.35, label="Std Dev Amount", color="#ff7f0e")
        max_amt = float(max(amount_df["avg_amount"].max(), amount_df["stddev_amount"].fillna(0).max(), 1.0))
        axes[1].set_ylim(0, max_amt * 1.25)
        axes[1].set_xticks(x)
        axes[1].set_xticklabels(amount_df["class_label"])
        axes[1].set_title("Transaction Amount Statistics", fontweight="bold", fontsize=11)
        axes[1].set_ylabel("Amount ($)")
        axes[1].legend(loc="upper left", fontsize=8)
        axes[1].grid(axis="y", linestyle="--", alpha=0.5)

    # Panel 3: Categorical Fraud Rate OR Hourly Fraud Rate
    if cat_df is not None and not cat_df.empty:
        col_name = cat_df.columns[0]
        axes[2].bar(cat_df[col_name].astype(str), cat_df["fraud_rate_pct"], color="#9467bd", alpha=0.88)
        axes[2].set_ylim(0, max(1.0, float(cat_df["fraud_rate_pct"].max()) * 1.15))
        axes[2].set_title(f"Fraud Rate (%) by {col_name}", fontweight="bold", fontsize=11)
        axes[2].set_ylabel("Fraud Rate (%)")
        axes[2].grid(axis="y", linestyle="--", alpha=0.5)
    elif hourly_df is not None and not hourly_df.empty:
        axes[2].plot(hourly_df["hour_of_day"], hourly_df["fraud_rate_pct"], marker="o", color="#d62728", lw=2)
        axes[2].set_title("Hourly Fraud Rate (%)", fontweight="bold", fontsize=11)
        axes[2].set_xlabel("Hour of Day")
        axes[2].set_ylabel("Fraud Rate (%)")
        axes[2].grid(True, linestyle="--", alpha=0.5)
    else:
        ratio = int(round(target_stats["legitimate_count"] / max(1, target_stats["fraud_count"])))
        summary_lines = [
            f"Total Transactions: {target_stats['total_records']:,}",
            f"Legitimate (0): {target_stats['legitimate_count']:,}",
            f"Fraudulent (1): {target_stats['fraud_count']:,}",
            f"Fraud Prevalence: {target_stats['fraud_prevalence_pct']}%",
            f"Imbalance Ratio: {ratio:,} : 1",
        ]
        if not amount_df.empty and "max_amount" in amount_df.columns:
            max_vals = dict(zip(amount_df["class_label"], amount_df["max_amount"]))
            if "Legitimate" in max_vals and "Fraudulent" in max_vals:
                summary_lines.append(f"Max Amount (Legit / Fraud): USD {max_vals['Legitimate']:,.0f} / USD {max_vals['Fraudulent']:,.0f}")
        axes[2].set_title("Dataset Imbalance Profile", fontweight="bold", fontsize=11)
        axes[2].text(
            0.5,
            0.5,
            "\n\n".join(summary_lines),
            ha="center",
            va="center",
            fontsize=11,
            bbox={"boxstyle": "round,pad=0.8", "facecolor": "#f4f7fa", "edgecolor": "#1f4e79", "linewidth": 1.2},
        )
        axes[2].axis("off")

    plt.suptitle(f"Exploratory Data Analysis — {dataset_name}", fontsize=13, fontweight="bold")
    plt.tight_layout(rect=[0, 0, 1, 0.94])
    plt.savefig(output_path, dpi=300)
    plt.close()
    logger.info(f"EDA overview figure saved to: {output_path}")
