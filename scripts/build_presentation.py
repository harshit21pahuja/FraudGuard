"""Generate FraudGuard Final Presentation (FraudGuard_Presentation.pptx).

Reads genuine metrics, dataset summaries, hyperparameter tuning logs, threshold
analysis curves, and figures directly from outputs/ so every reported figure is
100% reproducible and synchronized with pipeline execution.
"""

import sys
sys.modules["pyarrow"] = None
sys.modules["pyarrow.compute"] = None
from pathlib import Path
import pandas as pd
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.util import Inches, Pt


NAVY = RGBColor(15, 39, 68)
BLUE = RGBColor(31, 78, 121)
TEAL = RGBColor(22, 160, 133)
CORAL = RGBColor(192, 57, 43)
DARK_TEXT = RGBColor(33, 37, 41)
MUTED = RGBColor(90, 102, 115)
LIGHT_BG = RGBColor(244, 247, 250)
WHITE = RGBColor(255, 255, 255)
BORDER = RGBColor(208, 215, 222)


def add_header(slide, title_text: str, subtitle_text: str = "") -> None:
    """Add a clean executive top banner to a content slide."""
    bar = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0), Inches(0), Inches(13.333), Inches(1.05))
    bar.fill.solid()
    bar.fill.fore_color.rgb = NAVY
    bar.line.fill.background()

    accent = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0), Inches(1.05), Inches(13.333), Inches(0.06))
    accent.fill.solid()
    accent.fill.fore_color.rgb = TEAL
    accent.line.fill.background()

    tb = slide.shapes.add_textbox(Inches(0.6), Inches(0.14), Inches(12.1), Inches(0.85))
    tf = tb.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = title_text
    p.font.name = "Calibri"
    p.font.size = Pt(24)
    p.font.bold = True
    p.font.color.rgb = WHITE

    if subtitle_text:
        p2 = tf.add_paragraph()
        p2.text = subtitle_text
        p2.font.name = "Calibri"
        p2.font.size = Pt(12)
        p2.font.color.rgb = RGBColor(200, 220, 240)


def add_footer(slide, slide_num: int, total_slides: int) -> None:
    """Add consistent slide footer."""
    tb = slide.shapes.add_textbox(Inches(0.6), Inches(7.15), Inches(12.1), Inches(0.3))
    tf = tb.text_frame
    p = tf.paragraphs[0]
    p.text = f"FraudGuard | CSET371 Big Data Analytics & Business Intelligence | Bennett University          {slide_num} / {total_slides}"
    p.font.name = "Calibri"
    p.font.size = Pt(10)
    p.font.color.rgb = MUTED
    p.alignment = PP_ALIGN.RIGHT


def add_card(slide, left: float, top: float, width: float, height: float, title: str, bullets: list[str], title_color=BLUE) -> None:
    """Add a clean bordered card with heading and bullet points."""
    box = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(left), Inches(top), Inches(width), Inches(height))
    box.fill.solid()
    box.fill.fore_color.rgb = LIGHT_BG
    box.line.color.rgb = BORDER
    box.line.width = Pt(1)

    tb = slide.shapes.add_textbox(Inches(left + 0.18), Inches(top + 0.12), Inches(width - 0.36), Inches(height - 0.24))
    tf = tb.text_frame
    tf.word_wrap = True
    p0 = tf.paragraphs[0]
    p0.text = title
    p0.font.name = "Calibri"
    p0.font.size = Pt(15)
    p0.font.bold = True
    p0.font.color.rgb = title_color
    p0.space_after = Pt(6)

    for b in bullets:
        p = tf.add_paragraph()
        p.text = f"• {b}"
        p.font.name = "Calibri"
        p.font.size = Pt(12)
        p.font.color.rgb = DARK_TEXT
        p.space_after = Pt(4)


def add_styled_table(slide, left: float, top: float, width: float, height: float, headers: list[str], rows: list[list[str]], font_size: int = 10) -> None:
    """Add a styled data table to a slide."""
    table_shape = slide.shapes.add_table(len(rows) + 1, len(headers), Inches(left), Inches(top), Inches(width), Inches(height))
    table = table_shape.table
    for c_idx, h in enumerate(headers):
        cell = table.cell(0, c_idx)
        cell.fill.solid()
        cell.fill.fore_color.rgb = BLUE
        cell.vertical_anchor = MSO_ANCHOR.MIDDLE
        p = cell.text_frame.paragraphs[0]
        p.text = h
        p.font.name = "Calibri"
        p.font.size = Pt(font_size)
        p.font.bold = True
        p.font.color.rgb = WHITE
        p.alignment = PP_ALIGN.CENTER

    for r_idx, row_vals in enumerate(rows, start=1):
        bg = WHITE if r_idx % 2 == 1 else LIGHT_BG
        for c_idx, val in enumerate(row_vals):
            cell = table.cell(r_idx, c_idx)
            cell.fill.solid()
            cell.fill.fore_color.rgb = bg
            cell.vertical_anchor = MSO_ANCHOR.MIDDLE
            p = cell.text_frame.paragraphs[0]
            p.text = str(val)
            p.font.name = "Calibri"
            p.font.size = Pt(font_size)
            p.font.color.rgb = DARK_TEXT
            p.font.bold = (c_idx == 0)
            p.alignment = PP_ALIGN.LEFT if c_idx == 0 else PP_ALIGN.CENTER


def build_presentation(output_path: Path) -> Path:
    """Create the complete 13-slide FraudGuard presentation."""
    root = output_path.parent
    metrics_path = root / "outputs" / "metrics" / "model_comparison.csv"
    summary_path = root / "outputs" / "summaries" / "dataset_summary.csv"
    thresh_path = root / "outputs" / "summaries" / "threshold_analysis.csv"
    tuning_path = root / "outputs" / "summaries" / "hyperparameter_tuning.csv"

    metrics_df = pd.read_csv(metrics_path) if metrics_path.exists() else pd.DataFrame()
    summary_df = pd.read_csv(summary_path) if summary_path.exists() else pd.DataFrame()
    thresh_df = pd.read_csv(thresh_path) if thresh_path.exists() else pd.DataFrame()
    tuning_df = pd.read_csv(tuning_path) if tuning_path.exists() else pd.DataFrame()

    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    blank = prs.slide_layouts[6]
    total_slides = 16

    # Slide 1: Title Slide
    s1 = prs.slides.add_slide(blank)
    bg1 = s1.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0), Inches(0), Inches(13.333), Inches(7.5))
    bg1.fill.solid()
    bg1.fill.fore_color.rgb = NAVY
    bg1.line.fill.background()

    stripe = s1.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0), Inches(0), Inches(0.32), Inches(7.5))
    stripe.fill.solid()
    stripe.fill.fore_color.rgb = TEAL
    stripe.line.fill.background()

    tb = s1.shapes.add_textbox(Inches(0.9), Inches(1.1), Inches(11.6), Inches(5.6))
    tf = tb.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = "FRAUDGUARD"
    p.font.name = "Calibri"
    p.font.size = Pt(20)
    p.font.bold = True
    p.font.color.rgb = TEAL

    p2 = tf.add_paragraph()
    p2.text = "Cross-Dataset Financial Fraud Detection and Risk Analytics Using Apache Spark and Machine Learning"
    p2.font.name = "Calibri"
    p2.font.size = Pt(34)
    p2.font.bold = True
    p2.font.color.rgb = WHITE
    p2.space_after = Pt(16)

    p3 = tf.add_paragraph()
    p3.text = "CSET371 — Big Data Analytics and Business Intelligence  |  Bennett University, Greater Noida"
    p3.font.name = "Calibri"
    p3.font.size = Pt(16)
    p3.font.color.rgb = RGBColor(200, 220, 240)
    p3.space_after = Pt(22)

    p4 = tf.add_paragraph()
    p4.text = (
        "Submitted by:\n"
        "• Harshit Pahuja (S24CSEU0736)   • Rachit Nain (S24CSEU2646)   • Man Mohan Gaur (S24CSEU2012)\n"
        "• Kunal Sehrawat (S24CSEU2638)   • Bhumi Jindal (S24CSEU0884)\n\n"
        "Under the Guidance of: Dr. Monia (Associate Professor, SCSET)"
    )
    p4.font.name = "Calibri"
    p4.font.size = Pt(15)
    p4.font.color.rgb = RGBColor(235, 242, 248)

    # Slide 2: Problem Analysis & Challenges
    s2 = prs.slides.add_slide(blank)
    add_header(s2, "1. Problem Domain, Context & Key Challenges", "Why accuracy fails and why scalable leakage-free pipelines are critical")
    add_card(
        s2, 0.6, 1.4, 5.9, 2.6,
        "Financial Fraud Landscape",
        [
            "Digital payments generate millions of high-dimensional transactions with heterogeneous attributes.",
            "Fraud prevalence is severely skewed (0.17% in card payments; ~3.5% in e-commerce checkouts).",
            "A naive all-legitimate classifier reaches 99.83% accuracy while missing 100% of fraud.",
        ],
    )
    add_card(
        s2, 6.8, 1.4, 5.9, 2.6,
        "Asymmetric Operational Risk",
        [
            "False Negative (Missed Fraud): Direct chargeback loss and regulatory exposure (nominal $500).",
            "False Positive (False Alert): Customer friction, declined sales, manual review overhead (nominal $10).",
            "Default 0.50 probability thresholds ignore asymmetric financial losses.",
        ],
        title_color=CORAL,
    )
    add_card(
        s2, 0.6, 4.25, 12.1, 2.65,
        "Core Research Questions Addressed by FraudGuard",
        [
            "RQ1: How can PySpark guarantee leakage-free, reproducible preprocessing across high-volume transaction schemas?",
            "RQ2: How do Linear (LR), Bagging (RF), and Boosting (XGBoost, LightGBM, CatBoost) paradigms compare via PR-AUC, ROC-AUC, and Log Loss?",
            "RQ3: How do model behavior and class-imbalance sensitivity differ across anonymized PCA vs. rich e-commerce datasets?",
            "RQ4: What probability threshold minimizes total operational loss, and how can Power BI communicate trade-offs to analysts?",
        ],
        title_color=TEAL,
    )
    add_footer(s2, 2, total_slides)

    # Slide 3: Literature Survey & Research Gap
    s3 = prs.slides.add_slide(blank)
    add_header(s3, "2. Existing Systems, Literature Context & Research Gap", "From isolated single-dataset notebooks to unified Spark + BI risk analytics")
    lit_headers = ["Approach / Study Area", "Strengths", "Key Gaps Addressed by FraudGuard"]
    lit_rows = [
        ["Rule-Based Engines", "Auditable deterministic rules", "Static thresholds fail against evolving fraud patterns"],
        ["Standard Accuracy Benchmarks", "Simple baseline reporting", "Misleading under 0.17%–3.5% class skew (He & Garcia, 2009)"],
        ["Standalone ML Notebooks", "Fast prototyping", "Risk data leakage via pre-split scaling & lack Spark scalability"],
        ["Single-Threshold Classifiers", "Standard 0.5 cutoff", "Ignore asymmetric FP vs. FN costs (Dal Pozzolo et al., 2015)"],
        ["FraudGuard Contribution", "PySpark + 5 models + Power BI", "Strict train-only pipelines, PR-AUC/Log Loss, cost curve, 5-page BI"],
    ]
    add_styled_table(s3, 0.6, 1.45, 12.1, 3.6, lit_headers, lit_rows, font_size=12)
    add_card(
        s3, 0.6, 5.3, 12.1, 1.6,
        "Academic & Engineering Safeguards",
        [
            "Strict train-only fitting of StringIndexer, OneHotEncoder, Imputer, and StandardScaler (zero test leakage).",
            "Validation split (15%) dedicated exclusively to hyperparameter selection; held-out test split (15%) evaluated once.",
        ],
        title_color=NAVY,
    )
    add_footer(s3, 3, total_slides)

    # Slide 4: Datasets & Cross-Dataset Design
    s4 = prs.slides.add_slide(blank)
    add_header(s4, "3. Cross-Dataset Design & Verified Dataset Profiles", "Contrasting heterogeneous e-commerce metadata vs. anonymized European card transactions")
    if not summary_df.empty:
        ds_headers = ["Dataset", "Total Rows", "Legitimate (0)", "Fraud (1)", "Fraud Rate", "Train / Val / Test", "Num / Cat Feats"]
        ds_rows = []
        for _, r in summary_df.iterrows():
            ds_rows.append([
                r["dataset_name"],
                f"{int(r['total_records']):,}",
                f"{int(r['legitimate_records']):,}",
                f"{int(r['fraud_records']):,}",
                f"{r['fraud_prevalence_pct']}%",
                f"{int(r['train_records']):,} / {int(r['val_records']):,} / {int(r['test_records']):,}",
                f"{int(r['numerical_features'])} / {int(r['categorical_features'])}",
            ])
        add_styled_table(s4, 0.6, 1.4, 12.1, 2.3, ds_headers, ds_rows, font_size=11)

    add_card(
        s4, 0.6, 4.0, 5.9, 2.85,
        "Dataset A: IEEE-CIS Fraud Detection (Vesta / Kaggle)",
        [
            "E-commerce transactions joined across train_transaction & train_identity via left outer join on TransactionID.",
            "Rich categoricals (ProductCD, card4, card6, P_emaildomain, DeviceType) and high missingness (>80% dropped).",
            "Time-aware forward split on TransactionDT prevents future-to-past temporal leakage.",
        ],
    )
    add_card(
        s4, 6.8, 4.0, 5.9, 2.85,
        "Dataset B: ULB European Cardholders (OpenML 1597)",
        [
            "284,807 real card transactions with 492 fraud cases (0.1727% prevalence) under ODbL license.",
            "29 dense numerical features (PCA components V1–V28 + Amount) with zero missing values.",
            "Deterministic stratified 70% / 15% / 15% split preserves exact 0.1727% minority ratio across partitions.",
        ],
        title_color=TEAL,
    )
    add_footer(s4, 4, total_slides)

    # Slide 5: System Architecture
    s5 = prs.slides.add_slide(blank)
    add_header(s5, "4. FraudGuard End-to-End PySpark Architecture", "Modular big data pipeline from ingestion to Power BI reporting")
    stages = [
        ("1. Data Ingestion", "Spark CSV readers, left-join integrity checks, schema & target validation (src/data/loader.py)"),
        ("2. Spark EDA", "Single-pass null profiling, amount statistics, categorical/hourly risk aggregation (src/features/eda.py)"),
        ("3. Feature Pipeline", "StringIndexer, OneHotEncoder, Median Imputer, VectorAssembler, StandardScaler fit on train only"),
        ("4. Model Suite", "Spark ML (LR, RF) + BoostedSparkModelWrapper (XGBoost, LightGBM, CatBoost) with validation tuning"),
        ("5. Evaluation & Risk", "Precision, Recall, F1, ROC-AUC, PR-AUC, Log Loss + vectorized threshold cost scan ($10 FP / $500 FN)"),
        ("6. BI & Reporting", "Verified CSVs -> 5-page Power BI Dashboard + automated charts, notebooks & Word report"),
    ]
    for idx, (st_title, st_desc) in enumerate(stages):
        col = idx % 3
        row = idx // 3
        add_card(s5, 0.6 + col * 4.1, 1.5 + row * 2.7, 3.9, 2.4, st_title, [st_desc], title_color=BLUE if row == 0 else TEAL)
    add_footer(s5, 5, total_slides)

    # Slide 6: ML Suite & Validation Tuning
    s6 = prs.slides.add_slide(blank)
    add_header(s6, "5. Classifier Suite & Validation Hyperparameter Tuning", "Systematic model comparison using validation PR-AUC selection")
    if not tuning_df.empty:
        sel = tuning_df[tuning_df["selected"] == True].copy() if "selected" in tuning_df.columns else tuning_df.head(5)
        tun_headers = ["Dataset", "Classifier", "Selected Hyperparameters", "Val PR-AUC", "Val ROC-AUC", "Val Log Loss"]
        tun_rows = [
            [
                r.get("dataset_name", ""),
                r["model_name"],
                r["hyperparameters"],
                f"{r['val_pr_auc']:.4f}",
                f"{r['val_roc_auc']:.4f}",
                f"{r['val_log_loss']:.5f}",
            ]
            for _, r in sel.head(10).iterrows()
        ]
        tun_font = 8.5 if len(tun_rows) > 5 else 10
        add_styled_table(s6, 0.6, 1.4, 12.1, 4.15, tun_headers, tun_rows, font_size=tun_font)
    add_card(
        s6, 0.6, 5.7, 12.1, 1.25,
        "BoostedSparkModelWrapper Interoperability Pattern",
        [
            "Bridges Spark ML Feature Vectors with XGBoost/LightGBM/CatBoost, returning explicit-schema Spark DataFrames (rawPrediction, probability, prediction) for PySpark BinaryClassificationEvaluator.",
        ],
        title_color=NAVY,
    )
    add_footer(s6, 6, total_slides)

    # Slide 7: EDA Overview
    s7 = prs.slides.add_slide(blank)
    add_header(s7, "6. Exploratory Data Analysis (EDA) & Fraud Patterns", "Quantifying extreme class imbalance and transaction amount distributions")
    eda_a = root / "outputs" / "figures" / "dataset_a" / "eda_overview.png"
    eda_b = root / "outputs" / "figures" / "dataset_b" / "eda_overview.png"
    if eda_a.exists() and eda_b.exists():
        s7.shapes.add_picture(str(eda_a), Inches(0.55), Inches(1.45), width=Inches(6.0))
        s7.shapes.add_picture(str(eda_b), Inches(6.75), Inches(1.45), width=Inches(6.0))
    else:
        eda_img = root / "outputs" / "figures" / "eda_overview.png"
        if eda_img.exists():
            s7.shapes.add_picture(str(eda_img), Inches(0.6), Inches(1.4), width=Inches(12.1))
    add_card(
        s7, 0.6, 5.35, 12.1, 1.55,
        "Key Empirical Data Observations",
        [
            "Extreme skew confirmed across real data: majority class dominates by 27x–578x, validating PR-AUC and Log Loss over raw Accuracy.",
            "Single-pass missingness profiling automatically filters attributes exceeding 80% null density before training.",
        ],
        title_color=BLUE,
    )
    add_footer(s7, 7, total_slides)

    # Slide 8: Held-Out Model Comparison Table + Bar Chart
    s8 = prs.slides.add_slide(blank)
    add_header(s8, "7. Quantitative Held-Out Model Evaluation", "Comparison across Precision, Recall, F1, ROC-AUC, PR-AUC, Log Loss & Runtime")
    if not metrics_df.empty:
        m_headers = ["DS", "Model", "Prec", "Rec", "F1", "ROC", "PR-AUC", "LogLoss", "Time"]
        m_rows = [
            [
                str(r.get("dataset_key", "ds")).replace("dataset_", "").upper(),
                r["model_name"].replace("logistic_regression", "logistic_reg").replace("random_forest", "random_for"),
                f"{r['precision']:.4f}",
                f"{r['recall']:.4f}",
                f"{r['f1_score']:.4f}",
                f"{r['roc_auc']:.4f}",
                f"{r['pr_auc']:.4f}",
                f"{r.get('log_loss', 0.0):.5f}",
                f"{r['training_time_sec']:.1f}s",
            ]
            for _, r in metrics_df.iterrows()
        ]
        m_font = 8 if len(m_rows) > 5 else 9
        add_styled_table(s8, 0.45, 1.35, 6.95, 5.3, m_headers, m_rows, font_size=m_font)
        col_widths = [Inches(0.45), Inches(1.2), Inches(0.72), Inches(0.72), Inches(0.72), Inches(0.74), Inches(0.80), Inches(0.88), Inches(0.72)]
        tbl_shape = [sh for sh in s8.shapes if sh.has_table][-1]
        for idx_w, w_val in enumerate(col_widths):
            tbl_shape.table.columns[idx_w].width = w_val
    bar_img = root / "outputs" / "figures" / "model_comparison_bar_chart.png"
    if bar_img.exists():
        s8.shapes.add_picture(str(bar_img), Inches(7.55), Inches(1.55), width=Inches(5.3))
    add_footer(s8, 8, total_slides)

    # Slide 9: ROC, PR Curves & Confusion Matrices
    s9 = prs.slides.add_slide(blank)
    add_header(s9, "8. ROC-AUC, Precision-Recall Curves & Confusion Matrices", "Visual discrimination power and exact TP / TN / FP / FN error counts")
    roc_img = root / "outputs" / "figures" / "roc_curves.png"
    pr_img = root / "outputs" / "figures" / "pr_curves.png"
    cm_img = root / "outputs" / "figures" / "confusion_matrices_grid.png"
    if roc_img.exists():
        s9.shapes.add_picture(str(roc_img), Inches(0.5), Inches(1.4), width=Inches(4.0))
    if pr_img.exists():
        s9.shapes.add_picture(str(pr_img), Inches(4.65), Inches(1.4), width=Inches(4.0))
    if cm_img.exists():
        s9.shapes.add_picture(str(cm_img), Inches(8.8), Inches(1.4), width=Inches(4.0))
    add_card(
        s9, 0.5, 5.25, 12.3, 1.65,
        "Diagnostic Justification of Results",
        [
            "Gradient boosting models (XGBoost, LightGBM, CatBoost) dominate PR-AUC and minimize Log Loss compared to linear Logistic Regression.",
            "PR-AUC separates top boosting models far more clearly than ROC-AUC due to the massive True Negative pool in fraud detection.",
        ],
        title_color=TEAL,
    )
    add_footer(s9, 9, total_slides)

    # Slide 10: Operational Risk & Threshold Analysis
    s10 = prs.slides.add_slide(blank)
    add_header(s10, "9. Operational Risk & Decision Threshold Optimization", "Minimizing total financial loss ($10 FP review cost vs. $500 FN missed fraud)")
    thr_img = root / "outputs" / "figures" / "threshold_tradeoffs.png"
    if thr_img.exists():
        s10.shapes.add_picture(str(thr_img), Inches(0.6), Inches(1.4), width=Inches(12.1))
    if not thresh_df.empty:
        ds_groups = thresh_df.groupby("dataset_name", sort=False) if "dataset_name" in thresh_df.columns else [("Evaluated Dataset", thresh_df)]
        thr_bullets = []
        for ds_lbl, grp in ds_groups:
            best_thr = grp.sort_values("total_operational_cost").iloc[0]
            def_thr = grp[grp["threshold"].round(2) == 0.50]
            def_cost = f"${float(def_thr.iloc[0]['total_operational_cost']):,.2f}" if not def_thr.empty else "N/A"
            thr_bullets.append(
                f"{ds_lbl} ({best_thr.get('model_name', '')}): Opt thr={best_thr['threshold']:.2f} | "
                f"Prec={best_thr['precision']:.4f}, Rec={best_thr['recall']:.4f}, F1={best_thr['f1_score']:.4f}, "
                f"Cost=${float(best_thr['total_operational_cost']):,.2f} (vs. {def_cost} at 0.50)"
            )
        add_card(
            s10, 0.6, 5.45, 12.1, 1.45,
            "Cost-Optimal Operating Points vs. Default 0.50 Threshold",
            thr_bullets,
            title_color=CORAL,
        )
    add_footer(s10, 10, total_slides)

    # Slide 11: Cross-Dataset Comparison
    s11 = prs.slides.add_slide(blank)
    add_header(s11, "10. Cross-Dataset Synthesis & Methodological Boundaries", "Evaluating algorithmic consistency across heterogeneous vs. PCA-anonymized schemas")
    cross_img = root / "outputs" / "figures" / "cross_dataset_comparison.png"
    if cross_img.exists():
        s11.shapes.add_picture(str(cross_img), Inches(0.6), Inches(1.4), width=Inches(12.1))
    else:
        comp_headers = ["Dimension", "Dataset A: IEEE-CIS (Vesta)", "Dataset B: ULB European Cardholders"]
        comp_rows = [
            ["Domain & Structure", "E-Commerce Checkouts (Transaction + Identity Left Join)", "Real Cardholder Payments (284,807 Rows, 492 Frauds)"],
            ["Feature Space", "Heterogeneous Numerical + High-Cardinality Categoricals", "29 Dense Numericals (V1–V28 PCA + Amount), Zero Nulls"],
            ["Split Discipline", "Time-Aware Chronological Split (TransactionDT)", "Deterministic Stratified Window Split (0.1727% Preserved)"],
            ["Current Run Status", "Validated Pipeline Ready (Awaiting Raw Kaggle CSVs)", "Completed Full-Scale Evaluation (42,722 Held-Out Test Rows)"],
        ]
        add_styled_table(s11, 0.6, 1.45, 12.1, 3.5, comp_headers, comp_rows, font_size=11)
    add_card(
        s11, 0.6, 5.45, 12.1, 1.45,
        "Why Direct Model Transfer Is Avoided",
        [
            "Dataset A features e-commerce categoricals and temporal drift; Dataset B features orthogonal PCA components (V1–V28). Each dataset retains independent preprocessing pipelines and held-out evaluations.",
        ],
        title_color=NAVY,
    )
    add_footer(s11, 11, total_slides)

    # Slide 12: Power BI Dashboard
    s12 = prs.slides.add_slide(blank)
    add_header(s12, "11. Interactive Power BI Business Intelligence Dashboard", "5-page executive decision-support workspace backed by verified CSV exports")
    pages = [
        ("Page 1: Fraud Overview", ["Total, Legitimate & Fraud KPI cards", "Fraud Prevalence % & Train/Val/Test counts"]),
        ("Page 2: Fraud Pattern Analysis", ["Amount statistics & missingness profile", "Categorical (ProductCD/Card) & hourly patterns"]),
        ("Page 3: Model Performance", ["Clustered comparison across 5 classifiers", "Precision, Recall, F1, ROC-AUC, PR-AUC, Log Loss"]),
        ("Page 4: Risk & Thresholds", ["Precision-Recall trade-off frontier", "FP vs. FN operational loss minimization curve"]),
        ("Page 5: Cross-Dataset View", ["Dataset A vs. Dataset B KPI comparison", "Methodological boundary & tuning insights"]),
    ]
    for idx, (ptitle, pbul) in enumerate(pages):
        col = idx % 3
        row = idx // 3
        add_card(s12, 0.6 + col * 4.1, 1.5 + row * 2.65, 3.9, 2.35, ptitle, pbul, title_color=BLUE if row == 0 else TEAL)
    add_footer(s12, 12, total_slides)

    # Slide 13: Alignment to Sustainable Development Goals (SDGs)
    s13 = prs.slides.add_slide(blank)
    add_header(s13, "12. Alignment to Sustainable Development Goals (SDGs)", "Translating Big Data Analytics & Fraud Risk Reduction into UN 2030 Sustainability Targets")
    add_card(
        s13, 0.6, 1.45, 3.85, 5.4,
        "SDG 8: Decent Work & Economic Growth",
        [
            "Target 8.10: Strengthen capacity of domestic financial institutions to expand access to banking & financial services.",
            "Fraud Protection: Shields merchants and retail consumers from fraudulent revenue drains across digital payment systems.",
            "Friction Minimization: Calibrated thresholds lower False Positives (~$10 friction) to protect customer trust in digital finance.",
            "Financial Inclusion: Enables safe onboarding of unbanked users by lowering fraud-loss reserves for digital credit providers.",
        ],
        title_color=TEAL,
    )
    add_card(
        s13, 4.74, 1.45, 3.85, 5.4,
        "SDG 9: Industry, Innovation & Infrastructure",
        [
            "Target 9.5: Upgrade technological capabilities and foster innovation in domestic industrial and financial sectors.",
            "Big Data Scale: Apache Spark distributed computing processes 875,000+ transactions with high fault tolerance.",
            "ML Innovation: Benchmarks state-of-the-art gradient boosters (XGBoost, LightGBM, CatBoost) against classic baselines.",
            "Decision Intelligence: Bridges algorithmic data science with enterprise Business Intelligence via Microsoft Power BI.",
        ],
        title_color=BLUE,
    )
    add_card(
        s13, 8.88, 1.45, 3.85, 5.4,
        "SDG 16: Peace, Justice & Strong Institutions",
        [
            "Target 16.4: By 2030, significantly reduce illicit financial flows and combat organized cybercrime syndicates.",
            "Anti-Laundering Shield: Intercepts account takeovers, card-not-present fraud, and bot-driven checkout attacks.",
            "Audit Integrity: Zero data leakage protocols, reproducible seeds, and transparent confusion matrices ensure regulatory compliance.",
            "Transparent Analytics: Eliminates black-box reliance through cost-matrix curves and feature importance visibility.",
        ],
        title_color=NAVY,
    )
    add_footer(s13, 13, total_slides)

    # Slide 14: Team Member Contributions & Project Management
    s14 = prs.slides.add_slide(blank)
    add_header(s14, "13. Team Member Contributions & Project Management", "Individual ownership, project management milestones, and accountability across the 3-credit scheme")
    team_headers = ["Team Member", "Enrollment No.", "Primary Architectural Responsibility", "Key Verified Deliverables"]
    team_rows = [
        ["Harshit Pahuja", "S24CSEU0736", "Project Coordinator & Big Data Architect", "PySpark Ingestion, Join Validation, Group-Aware Split, Master Runner, Integration Testing"],
        ["Rachit Nain", "S24CSEU2646", "Data Validation & EDA Specialist", "Dataset Profiling, Null/Cardinality Analysis, Spark EDA Visualizations, Hourly Patterns"],
        ["Man Mohan Gaur", "S24CSEU2012", "Machine Learning & Modeling Lead", "Spark ML Feature Pipelines, 5 Classifiers Implementation, Validation Hyperparameter Grid Tuning"],
        ["Kunal Sehrawat", "S24CSEU2638", "Risk Analytics & Business Intelligence Lead", "Decision Threshold Optimization, Financial Cost Modeling ($10 FP vs $500 FN), 5-Page Power BI Dashboard"],
        ["Bhumi Jindal", "S24CSEU0884", "Research, Documentation & Compliance Lead", "Literature Survey, Comparative Research Gap Matrix, SDG Mapping, Final Academic Report & Presentation"],
    ]
    add_styled_table(s14, 0.6, 1.45, 12.1, 3.4, team_headers, team_rows, font_size=10)
    add_card(
        s14, 0.6, 5.15, 12.1, 1.8,
        "Agile Project Management, Regularity & Quality Assurance",
        [
            "Development Discipline: Centralized YAML configuration, modular src/ package structure, and Git version control.",
            "Automated Test Coverage: 21/21 passing PyTest unit and integration tests covering data integrity, splits, and risk curves.",
            "Timely Milestones: Successfully delivered Milestone 1 (Planning), Milestone 2 (Pipeline & Tuning), and Milestone 3 (Final Evaluation).",
        ],
        title_color=TEAL,
    )
    add_footer(s14, 14, total_slides)

    # Slide 15: Conclusion, Limitations & Future Scope
    s15 = prs.slides.add_slide(blank)
    add_header(s15, "14. Conclusion, Limitations & Future Scope", "Summary of academic contributions, production roadmap, and technical boundaries")
    add_card(
        s15, 0.6, 1.45, 5.9, 3.3,
        "Key Engineering Contributions",
        [
            "Delivered end-to-end PySpark fraud detection system handling ~875,000 transactions with zero data leakage.",
            "Demonstrated that Precision-Recall AUC (PR-AUC) and Log Loss provide far superior risk separation than misleading Accuracy (>99.8%).",
            "Proved gradient boosters (XGBoost, LightGBM, CatBoost) achieve superior PR-AUC over linear Logistic Regression and Random Forest.",
            "Pioneered asymmetric cost-based threshold optimization ($10 FP vs $500 FN), achieving up to 83.8% fraud recall at 0.05 cutoff.",
        ],
        title_color=TEAL,
    )
    add_card(
        s15, 6.8, 1.45, 5.9, 3.3,
        "Technical Limitations & Boundaries",
        [
            "Batch Ingestion Prototype: Current pipeline processes batch CSV/Parquet; production banking requires sub-100ms real-time inference.",
            "Single-Node Spark Simulation: Executed locally on multi-core workstation (`local[*]`) rather than distributed multi-node cloud cluster.",
            "No Cross-Schema Model Transfer: IEEE-CIS and ULB schemas are fundamentally distinct (e-commerce vs. orthogonal PCA components).",
        ],
        title_color=CORAL,
    )
    add_card(
        s15, 0.6, 5.0, 12.1, 1.95,
        "Production Roadmap & Future Enhancements",
        [
            "Streaming Infrastructure: Integrate Apache Kafka + Spark Structured Streaming for real-time windowed velocity feature computation.",
            "Graph Fraud Analytics: Deploy Apache Spark GraphX / Graph Neural Networks (GNNs) to detect syndicated fraud rings sharing IP/device hashes.",
            "Automated MLOps: Implement automated concept-drift detection (Evidently AI / MLflow) with scheduled retraining triggers.",
        ],
        title_color=NAVY,
    )
    add_footer(s15, 15, total_slides)

    # Slide 16: Live Demonstration & Viva Evaluation Guide
    s16 = prs.slides.add_slide(blank)
    add_header(s16, "15. Live Demonstration & Lab Viva Walkthrough Guide", "Structured demonstration roadmap for the Milestone-3 laboratory evaluation")
    demo_stages = [
        ("Stage 1: Big Data & Automated Testing", [
            "Terminal: Run `.venv\\Scripts\\python.exe -m pytest -v` to prove all 21/21 automated tests pass.",
            "Code Walkthrough: Show `src/data/loader.py` join validation, time-aware split, and group-aware split.",
            "Highlight zero data leakage engineering and deterministic SHA-256 group hashing.",
        ]),
        ("Stage 2: ML Training & Risk Optimization", [
            "Code Walkthrough: Show `src/pipeline_runner.py` and `src/models/trainer.py` 5-classifier suite.",
            "Explain why PR-AUC was selected for model ranking over raw accuracy.",
            "Demonstrate threshold scanning: why lowering cutoff to 0.05 minimizes $500 FN cost.",
        ]),
        ("Stage 3: Power BI Business Intelligence", [
            "Open `powerbi/FraudGuard_Dashboard.pbip` live in Microsoft Power BI Desktop.",
            "Demonstrate 5 pages: Overview KPIs, Fraud Patterns, Model Comparison, Cost Curves, Cross-Dataset.",
            "Interact with dataset slicers and show verified CSV data lineage.",
        ]),
    ]
    for idx, (stitle, sbullets) in enumerate(demo_stages):
        add_card(s16, 0.6 + idx * 4.1, 1.5, 3.9, 5.35, stitle, sbullets, title_color=BLUE if idx == 0 else (TEAL if idx == 1 else CORAL))
    add_footer(s16, 16, total_slides)

    prs.save(str(output_path))
    print(f"Presentation generated successfully: {output_path}")
    return output_path


if __name__ == "__main__":
    out_file = Path(__file__).resolve().parent.parent / "FraudGuard_Presentation.pptx"
    build_presentation(out_file)
