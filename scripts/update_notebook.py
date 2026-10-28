import json
from pathlib import Path

nb_path = Path("notebooks/01_ieee_cis_pipeline.ipynb")

with open(nb_path, "r", encoding="utf-8") as f:
    nb = json.load(f)

# Check cells
cells = nb.get("cells", [])

# Let's inspect step 6 export paths
for cell in cells:
    if cell.get("cell_type") == "code":
        src = "".join(cell.get("source", []))
        if "model_comparison_ieee_cis.csv" in src:
            new_src = []
            for line in cell["source"]:
                if "model_comparison_ieee_cis.csv" in line:
                    new_src.append("results_df.to_csv(\"outputs/metrics/model_comparison.csv\", index=False)\n")
                else:
                    new_src.append(line)
            cell["source"] = new_src
        if "threshold_analysis_ieee_cis.csv" in src:
            new_src = []
            for line in cell["source"]:
                if "threshold_analysis_ieee_cis.csv" in line:
                    new_src.append("threshold_df.to_csv(\"outputs/summaries/threshold_analysis.csv\", index=False)\n")
                else:
                    new_src.append(line)
            cell["source"] = new_src

# Add Step 8 if not already present
has_step_8 = any("Step 8" in "".join(c.get("source", [])) for c in cells)
if not has_step_8:
    step8_md = {
        "cell_type": "markdown",
        "metadata": {},
        "source": [
            "### Step 8: Academic Visualizations & Executive Dashboard Plots\n",
            "Generate publication-quality figures:\n",
            "1. Multi-metric grouped bar chart comparing all 5 classifiers.\n",
            "2. Precision-Recall trade-off & financial cost curve across decision thresholds.\n",
            "3. 5-model test-set confusion matrix grid."
        ]
    }
    step8_code = {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": [
            "from pathlib import Path\n",
            "from IPython.display import Image, display\n",
            "from src.evaluation.visualizations import (\n",
            "    plot_model_comparison,\n",
            "    plot_threshold_curves,\n",
            "    plot_confusion_matrices_grid,\n",
            ")\n",
            "\n",
            "fig_dir = Path(\"outputs/figures\")\n",
            "fig_dir.mkdir(parents=True, exist_ok=True)\n",
            "\n",
            "# 1. Held-Out Classifier Comparison\n",
            "comp_path = fig_dir / \"model_comparison_bar_chart.png\"\n",
            "plot_model_comparison(results_df, comp_path)\n",
            "display(Image(filename=str(comp_path)))\n",
            "\n",
            "# 2. Decision Threshold & Financial Cost Optimization\n",
            "thresh_path = fig_dir / \"threshold_tradeoffs.png\"\n",
            "plot_threshold_curves(threshold_df, thresh_path)\n",
            "display(Image(filename=str(thresh_path)))\n",
            "\n",
            "# 3. Comprehensive Confusion Matrices Grid\n",
            "cm_path = fig_dir / \"confusion_matrices_grid.png\"\n",
            "plot_confusion_matrices_grid(results_df, cm_path)\n",
            "display(Image(filename=str(cm_path)))\n",
            "\n",
            "print(\"Publication-quality visualizations generated and displayed successfully.\")"
        ]
    }
    summary_md = {
        "cell_type": "markdown",
        "metadata": {},
        "source": [
            "### Summary of Deliverables & Project Artifacts\n",
            "- **Model Evaluation Metrics**: `outputs/metrics/model_comparison.csv`\n",
            "- **Threshold Analysis**: `outputs/summaries/threshold_analysis.csv`\n",
            "- **Exploratory Data Analysis Summaries**: `outputs/summaries/*.csv`\n",
            "- **Publication Figures**: `outputs/figures/model_comparison_bar_chart.png`, `threshold_tradeoffs.png`, `confusion_matrices_grid.png`\n",
            "- **Live Power BI Data Sources**: `powerbi/data/*.csv`\n",
            "- **Interactive Power BI Dashboard**: `powerbi/FraudGuard_Dashboard.pbix`"
        ]
    }
    cells.extend([step8_md, step8_code, summary_md])
    nb["cells"] = cells

with open(nb_path, "w", encoding="utf-8") as f:
    json.dump(nb, f, indent=1)

print("Notebook updated successfully.")
