"""Generate the 5-page FraudGuard Power BI Project (.pbip + TMDL + PBIR 2.0.0).

Reads column schemas dynamically from powerbi/data/*.csv, constructs a
clean star-schema SemanticModel using TMDL with DAX measures and
QuoteStyle.Csv M partitions, and builds a 5-page PBIR 2.0.0 Report
matching powerbi/powerbi_setup_guide.md.
"""

from __future__ import annotations

import json
import shutil
import uuid
import zipfile
from pathlib import Path
from typing import Any, Dict, List


SCHEMA_PBIP = "https://developer.microsoft.com/json-schemas/fabric/pbip/pbipProperties/1.0.0/schema.json"
SCHEMA_PBIR = "https://developer.microsoft.com/json-schemas/fabric/item/report/definitionProperties/2.0.0/schema.json"
SCHEMA_PBISM = "https://developer.microsoft.com/json-schemas/fabric/item/semanticModel/definitionProperties/1.0.0/schema.json"
SCHEMA_REPORT_VER = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/versionMetadata/1.0.0/schema.json"
SCHEMA_REPORT = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/report/3.3.0/schema.json"
SCHEMA_PAGES = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/pagesMetadata/1.1.0/schema.json"
SCHEMA_PAGE = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/page/2.1.0/schema.json"
SCHEMA_VISUAL = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.13.0/schema.json"


def _uid(seed_str: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, f"fraudguard.powerbi.{seed_str}"))


def _short_id(seed_str: str) -> str:
    return _uid(seed_str).replace("-", "")[:20]


def _col_ref(entity: str, prop: str) -> Dict[str, Any]:
    return {
        "Column": {
            "Expression": {"SourceRef": {"Entity": entity}},
            "Property": prop,
        }
    }


def _meas_ref(entity: str, prop: str) -> Dict[str, Any]:
    return {
        "Measure": {
            "Expression": {"SourceRef": {"Entity": entity}},
            "Property": prop,
        }
    }


def _proj_col(entity: str, prop: str) -> Dict[str, Any]:
    return {
        "field": _col_ref(entity, prop),
        "queryRef": f"{entity}.{prop}",
        "nativeQueryRef": prop,
    }


def _proj_meas(entity: str, prop: str) -> Dict[str, Any]:
    return {
        "field": _meas_ref(entity, prop),
        "queryRef": f"{entity}.{prop}",
        "nativeQueryRef": prop,
    }


def _proj_agg(entity: str, prop: str, func: int = 0, label: str = "Sum") -> Dict[str, Any]:
    """Native PBIR Aggregation projection (func: 0=Sum, 1=Avg, 3=Min, 4=Max)."""
    return {
        "field": {"Aggregation": {"Expression": _col_ref(entity, prop), "Function": func}},
        "queryRef": f"{label}({entity}.{prop})",
        "nativeQueryRef": f"{label} of {prop}",
    }


def _visual_container(
    name: str,
    x: float,
    y: float,
    w: float,
    h: float,
    z: int,
    visual_type: str,
    query_state: Dict[str, Any],
    title: str | None = None,
) -> Dict[str, Any]:
    vis: Dict[str, Any] = {
        "visualType": visual_type,
        "query": {"queryState": query_state},
        "drillFilterOtherVisuals": True,
    }
    if title:
        vis["visualContainerObjects"] = {
            "title": [
                {
                    "properties": {
                        "show": {"expr": {"Literal": {"Value": "true"}}},
                        "text": {"expr": {"Literal": {"Value": f"'{title}'"}}},
                    }
                }
            ]
        }
    return {
        "$schema": SCHEMA_VISUAL,
        "name": name,
        "position": {"x": x, "y": y, "z": z, "height": h, "width": w, "tabOrder": z},
        "visual": vis,
    }


def _build_tmdl_table(
    table_name: str,
    csv_path: Path,
    columns: List[Dict[str, str]],
    measures: List[Dict[str, str]] | None = None,
    rename_first_col_to: str | None = None,
) -> str:
    lines: List[str] = [f"table {table_name}", f"\tlineageTag: {_uid(f'tbl.{table_name}')}", ""]

    for m in measures or []:
        m_orig = m["name"]
        m_name = f"'{m_orig}'" if (" " in m_orig or "%" in m_orig or "-" in m_orig) else m_orig
        lines.append(f"\tmeasure {m_name} = {m['expr']}")
        if m.get("format"):
            lines.append(f"\t\tformatString: {m['format']}")
        lines.append(f"\t\tlineageTag: {_uid(f'meas.{table_name}.{m_orig}')}")
        lines.append("")

    for col in columns:
        cname = col["name"]
        qname = f"'{cname}'" if " " in cname else cname
        lines.append(f"\tcolumn {qname}")
        lines.append(f"\t\tdataType: {col['dtype']}")
        if col.get("format"):
            lines.append(f"\t\tformatString: {col['format']}")
        lines.append(f"\t\tlineageTag: {_uid(f'col.{table_name}.{cname}')}")
        lines.append(f"\t\tsummarizeBy: {col.get('summarize', 'none')}")
        lines.append(f"\t\tsourceColumn: {cname}")
        lines.append("")

    # Build Power Query M script referencing Csv.Document with QuoteStyle.Csv
    csv_str = str(csv_path.resolve())
    type_pairs = ", ".join(f'{{"{c["name"]}", {c["mtype"]}}}' for c in columns)

    lines.append(f"\tpartition {table_name} = m")
    lines.append("\t\tmode: import")
    lines.append("\t\tsource =")
    lines.append("\t\t\tlet")
    lines.append(
        f'\t\t\t\tSource = Csv.Document(File.Contents("{csv_str}"), '
        "[Delimiter=\",\", Encoding=65001, QuoteStyle=QuoteStyle.Csv]),"
    )
    lines.append('\t\t\t\t#"Promoted Headers" = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),')
    if rename_first_col_to:
        lines.append(
            f'\t\t\t\t#"Normalized Target" = Table.RenameColumns(#"Promoted Headers", '
            f'{{{{Table.ColumnNames(#"Promoted Headers"){{0}}, "{rename_first_col_to}"}}}}),'
        )
        prev_step = '#"Normalized Target"'
    else:
        prev_step = '#"Promoted Headers"'
    lines.append(f'\t\t\t\t#"Changed Type" = Table.TransformColumnTypes({prev_step}, {{{type_pairs}}})')
    lines.append("\t\t\tin")
    lines.append('\t\t\t\t#"Changed Type"')
    lines.append("")
    return "\n".join(lines)


def build_powerbi_project(powerbi_dir: Path) -> Path:
    """Create FraudGuard_Dashboard.pbip + SemanticModel (TMDL) + Report (PBIR 2.0.0)."""
    data_dir = powerbi_dir / "data"
    pbip_path = powerbi_dir / "FraudGuard_Dashboard.pbip"
    sm_dir = powerbi_dir / "FraudGuard_Dashboard.SemanticModel"
    sm_def = sm_dir / "definition"
    sm_tables = sm_def / "tables"
    rep_dir = powerbi_dir / "FraudGuard_Dashboard.Report"
    rep_def = rep_dir / "definition"
    rep_pages = rep_def / "pages"
    rep_theme = rep_dir / "StaticResources" / "SharedResources" / "BaseThemes"

    for d in (sm_tables, rep_pages, rep_theme):
        d.mkdir(parents=True, exist_ok=True)
    for old_tmdl in sm_tables.glob("*.tmdl"):
        old_tmdl.unlink()
    for old_page in rep_pages.iterdir():
        if old_page.is_dir():
            shutil.rmtree(old_page)

    # Extract Fluent2 theme from existing .pbix if present
    pbix_path = powerbi_dir / "FraudGuard_Dashboard.pbix"
    theme_target = rep_theme / "Fluent2-CY26SU09.json"
    if pbix_path.exists() and not theme_target.exists():
        with zipfile.ZipFile(pbix_path, "r") as z:
            tname = "Report/StaticResources/SharedResources/BaseThemes/Fluent2-CY26SU09.json"
            if tname in z.namelist():
                theme_target.write_bytes(z.read(tname))

    # 1. Root .pbip & .pbir & .pbism metadata files
    pbip_path.write_text(
        json.dumps(
            {
                "$schema": SCHEMA_PBIP,
                "version": "1.0",
                "artifacts": [{"report": {"path": "FraudGuard_Dashboard.Report"}}],
                "settings": {"enableAutoRecovery": True},
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    platform_schema = "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json"
    for pdir, ptype in ((sm_dir, "SemanticModel"), (rep_dir, "Report")):
        (pdir / ".platform").write_text(
            json.dumps(
                {
                    "$schema": platform_schema,
                    "metadata": {"type": ptype, "displayName": "FraudGuard_Dashboard"},
                    "config": {"version": "2.0", "logicalId": _uid(f"platform.{ptype}")},
                },
                indent=2,
            ),
            encoding="utf-8",
        )

    (sm_dir / "definition.pbism").write_text(
        json.dumps({"$schema": SCHEMA_PBISM, "version": "4.2", "settings": {"qnaEnabled": True}}, indent=2),
        encoding="utf-8",
    )

    (rep_dir / "definition.pbir").write_text(
        json.dumps(
            {
                "$schema": SCHEMA_PBIR,
                "version": "4.0",
                "datasetReference": {"byPath": {"path": "../FraudGuard_Dashboard.SemanticModel"}},
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    # 2. SemanticModel TMDL definitions
    (sm_def / "database.tmdl").write_text(
        "database FraudGuard_Dashboard\n\tcompatibilityLevel: 1567\n",
        encoding="utf-8",
    )

    table_defs: List[Dict[str, Any]] = [
        {
            "name": "dataset_summary",
            "csv": data_dir / "dataset_summary.csv",
            "columns": [
                {"name": "dataset_key", "dtype": "string", "mtype": "type text"},
                {"name": "dataset_name", "dtype": "string", "mtype": "type text"},
                {"name": "total_records", "dtype": "int64", "mtype": "Int64.Type", "summarize": "sum", "format": "#,##0"},
                {"name": "legitimate_records", "dtype": "int64", "mtype": "Int64.Type", "summarize": "sum", "format": "#,##0"},
                {"name": "fraud_records", "dtype": "int64", "mtype": "Int64.Type", "summarize": "sum", "format": "#,##0"},
                {"name": "fraud_prevalence_pct", "dtype": "double", "mtype": "type number", "summarize": "average", "format": "0.0000"},
                {"name": "train_records", "dtype": "int64", "mtype": "Int64.Type", "summarize": "sum", "format": "#,##0"},
                {"name": "val_records", "dtype": "int64", "mtype": "Int64.Type", "summarize": "sum", "format": "#,##0"},
                {"name": "test_records", "dtype": "int64", "mtype": "Int64.Type", "summarize": "sum", "format": "#,##0"},
                {"name": "numerical_features", "dtype": "int64", "mtype": "Int64.Type", "summarize": "sum"},
                {"name": "categorical_features", "dtype": "int64", "mtype": "Int64.Type", "summarize": "sum"},
                {"name": "dropped_high_null_features", "dtype": "int64", "mtype": "Int64.Type", "summarize": "sum"},
            ],
            "measures": [
                {"name": "Total Transactions", "expr": "SUM(dataset_summary[total_records])", "format": "#,##0"},
                {"name": "Total Fraud Cases", "expr": "SUM(dataset_summary[fraud_records])", "format": "#,##0"},
                {"name": "Total Legitimate Transactions", "expr": "SUM(dataset_summary[legitimate_records])", "format": "#,##0"},
                {
                    "name": "Fraud Prevalence Pct",
                    "expr": "DIVIDE(SUM(dataset_summary[fraud_records]), SUM(dataset_summary[total_records]), 0) * 100",
                    "format": "0.0000",
                },
            ],
        },
        {
            "name": "model_comparison",
            "csv": data_dir / "model_comparison.csv",
            "columns": [
                {"name": "model_name", "dtype": "string", "mtype": "type text"},
                {"name": "total_test_samples", "dtype": "int64", "mtype": "Int64.Type", "summarize": "sum", "format": "#,##0"},
                {"name": "true_positives", "dtype": "int64", "mtype": "Int64.Type", "summarize": "sum", "format": "#,##0"},
                {"name": "true_negatives", "dtype": "int64", "mtype": "Int64.Type", "summarize": "sum", "format": "#,##0"},
                {"name": "false_positives", "dtype": "int64", "mtype": "Int64.Type", "summarize": "sum", "format": "#,##0"},
                {"name": "false_negatives", "dtype": "int64", "mtype": "Int64.Type", "summarize": "sum", "format": "#,##0"},
                {"name": "precision", "dtype": "double", "mtype": "type number", "summarize": "average", "format": "0.0000"},
                {"name": "recall", "dtype": "double", "mtype": "type number", "summarize": "average", "format": "0.0000"},
                {"name": "f1_score", "dtype": "double", "mtype": "type number", "summarize": "average", "format": "0.0000"},
                {"name": "roc_auc", "dtype": "double", "mtype": "type number", "summarize": "average", "format": "0.0000"},
                {"name": "pr_auc", "dtype": "double", "mtype": "type number", "summarize": "average", "format": "0.0000"},
                {"name": "log_loss", "dtype": "double", "mtype": "type number", "summarize": "average", "format": "0.00000"},
                {"name": "accuracy", "dtype": "double", "mtype": "type number", "summarize": "average", "format": "0.0000"},
                {"name": "training_time_sec", "dtype": "double", "mtype": "type number", "summarize": "sum", "format": "0.00"},
                {"name": "dataset_key", "dtype": "string", "mtype": "type text"},
                {"name": "dataset_name", "dtype": "string", "mtype": "type text"},
            ],
            "measures": [
                {"name": "Best F1 Score", "expr": "MAX(model_comparison[f1_score])", "format": "0.0000"},
                {"name": "Best PR-AUC", "expr": "MAX(model_comparison[pr_auc])", "format": "0.0000"},
                {"name": "Lowest Log Loss", "expr": "MIN(model_comparison[log_loss])", "format": "0.00000"},
                {
                    "name": "Top Performing Model",
                    "expr": 'CONCATENATEX(TOPN(1, model_comparison, model_comparison[pr_auc], DESC), model_comparison[model_name], ", ")',
                },
            ],
        },
        {
            "name": "threshold_analysis",
            "csv": data_dir / "threshold_analysis.csv",
            "columns": [
                {"name": "threshold", "dtype": "double", "mtype": "type number", "format": "0.00"},
                {"name": "precision", "dtype": "double", "mtype": "type number", "summarize": "average", "format": "0.0000"},
                {"name": "recall", "dtype": "double", "mtype": "type number", "summarize": "average", "format": "0.0000"},
                {"name": "f1_score", "dtype": "double", "mtype": "type number", "summarize": "average", "format": "0.0000"},
                {"name": "true_positives", "dtype": "int64", "mtype": "Int64.Type", "summarize": "sum", "format": "#,##0"},
                {"name": "false_positives", "dtype": "int64", "mtype": "Int64.Type", "summarize": "sum", "format": "#,##0"},
                {"name": "true_negatives", "dtype": "int64", "mtype": "Int64.Type", "summarize": "sum", "format": "#,##0"},
                {"name": "false_negatives", "dtype": "int64", "mtype": "Int64.Type", "summarize": "sum", "format": "#,##0"},
                {"name": "flagged_volume", "dtype": "int64", "mtype": "Int64.Type", "summarize": "sum", "format": "#,##0"},
                {"name": "alert_rate_pct", "dtype": "double", "mtype": "type number", "summarize": "average", "format": "0.00"},
                {"name": "total_operational_cost", "dtype": "double", "mtype": "type number", "summarize": "sum", "format": "$#,##0"},
                {"name": "dataset_key", "dtype": "string", "mtype": "type text"},
                {"name": "dataset_name", "dtype": "string", "mtype": "type text"},
                {"name": "model_name", "dtype": "string", "mtype": "type text"},
            ],
            "measures": [
                {"name": "Minimum Operational Loss", "expr": "MIN(threshold_analysis[total_operational_cost])", "format": "$#,##0"},
                {
                    "name": "Optimal Threshold",
                    "expr": "MAXX(TOPN(1, threshold_analysis, threshold_analysis[total_operational_cost], ASC), threshold_analysis[threshold])",
                    "format": "0.00",
                },
            ],
        },
        {
            "name": "hyperparameter_tuning",
            "csv": data_dir / "hyperparameter_tuning.csv",
            "columns": [
                {"name": "model_name", "dtype": "string", "mtype": "type text"},
                {"name": "hyperparameters", "dtype": "string", "mtype": "type text"},
                {"name": "val_pr_auc", "dtype": "double", "mtype": "type number", "summarize": "average", "format": "0.0000"},
                {"name": "val_roc_auc", "dtype": "double", "mtype": "type number", "summarize": "average", "format": "0.0000"},
                {"name": "val_log_loss", "dtype": "double", "mtype": "type number", "summarize": "average", "format": "0.00000"},
                {"name": "train_time_sec", "dtype": "double", "mtype": "type number", "summarize": "sum", "format": "0.00"},
                {"name": "selected", "dtype": "boolean", "mtype": "type logical"},
                {"name": "dataset_key", "dtype": "string", "mtype": "type text"},
                {"name": "dataset_name", "dtype": "string", "mtype": "type text"},
            ],
        },
        {
            "name": "amount_distribution",
            "csv": data_dir / "amount_distribution.csv",
            "rename_first_col_to": "target_value",
            "columns": [
                {"name": "target_value", "dtype": "int64", "mtype": "Int64.Type"},
                {"name": "count", "dtype": "int64", "mtype": "Int64.Type", "summarize": "sum", "format": "#,##0"},
                {"name": "min_amount", "dtype": "double", "mtype": "type number", "summarize": "min", "format": "$#,##0.00"},
                {"name": "avg_amount", "dtype": "double", "mtype": "type number", "summarize": "average", "format": "$#,##0.00"},
                {"name": "stddev_amount", "dtype": "double", "mtype": "type number", "summarize": "average", "format": "$#,##0.00"},
                {"name": "max_amount", "dtype": "double", "mtype": "type number", "summarize": "max", "format": "$#,##0.00"},
                {"name": "class_label", "dtype": "string", "mtype": "type text"},
                {"name": "dataset_name", "dtype": "string", "mtype": "type text"},
            ],
        },
        {
            "name": "missingness_profile",
            "csv": data_dir / "missingness_profile.csv",
            "columns": [
                {"name": "column_name", "dtype": "string", "mtype": "type text"},
                {"name": "null_count", "dtype": "int64", "mtype": "Int64.Type", "summarize": "sum", "format": "#,##0"},
                {"name": "missing_percentage", "dtype": "double", "mtype": "type number", "summarize": "average", "format": "0.00"},
                {"name": "dataset_name", "dtype": "string", "mtype": "type text"},
            ],
        },
    ]

    optional_tables: List[Dict[str, Any]] = [
        {
            "name": "hourly_fraud_pattern",
            "csv": data_dir / "hourly_fraud_pattern.csv",
            "columns": [
                {"name": "hour_of_day", "dtype": "int64", "mtype": "Int64.Type"},
                {"name": "total_transactions", "dtype": "int64", "mtype": "Int64.Type", "summarize": "sum", "format": "#,##0"},
                {"name": "fraud_transactions", "dtype": "int64", "mtype": "Int64.Type", "summarize": "sum", "format": "#,##0"},
                {"name": "fraud_rate_pct", "dtype": "double", "mtype": "type number", "summarize": "average", "format": "0.0000"},
                {"name": "dataset_name", "dtype": "string", "mtype": "type text"},
            ],
        },
        {
            "name": "fraud_by_product",
            "csv": data_dir / "fraud_by_product.csv",
            "columns": [
                {"name": "ProductCD", "dtype": "string", "mtype": "type text"},
                {"name": "total_transactions", "dtype": "int64", "mtype": "Int64.Type", "summarize": "sum", "format": "#,##0"},
                {"name": "fraud_transactions", "dtype": "int64", "mtype": "Int64.Type", "summarize": "sum", "format": "#,##0"},
                {"name": "legitimate_transactions", "dtype": "int64", "mtype": "Int64.Type", "summarize": "sum", "format": "#,##0"},
                {"name": "fraud_rate_pct", "dtype": "double", "mtype": "type number", "summarize": "average", "format": "0.00"},
                {"name": "dataset_name", "dtype": "string", "mtype": "type text"},
            ],
        },
        {
            "name": "fraud_by_card",
            "csv": data_dir / "fraud_by_card.csv",
            "columns": [
                {"name": "card4", "dtype": "string", "mtype": "type text"},
                {"name": "total_transactions", "dtype": "int64", "mtype": "Int64.Type", "summarize": "sum", "format": "#,##0"},
                {"name": "fraud_transactions", "dtype": "int64", "mtype": "Int64.Type", "summarize": "sum", "format": "#,##0"},
                {"name": "legitimate_transactions", "dtype": "int64", "mtype": "Int64.Type", "summarize": "sum", "format": "#,##0"},
                {"name": "fraud_rate_pct", "dtype": "double", "mtype": "type number", "summarize": "average", "format": "0.00"},
                {"name": "dataset_name", "dtype": "string", "mtype": "type text"},
            ],
        },
    ]
    for opt in optional_tables:
        if opt["csv"].exists():
            table_defs.append(opt)

    model_lines = [
        "model Model",
        "\tculture: en-US",
        "\tdefaultPowerBIDataSourceVersion: powerBI_V3",
        "\tsourceQueryCulture: en-US",
        "\tdataAccessOptions",
        "\t\tlegacyRedirects",
        "\t\treturnErrorValuesAsNull",
        "",
    ]
    rel_lines: List[str] = []

    for td in table_defs:
        tname = td["name"]
        model_lines.append(f"ref table {tname}")
        tmdl_text = _build_tmdl_table(
            tname,
            td["csv"],
            td["columns"],
            td.get("measures"),
            td.get("rename_first_col_to"),
        )
        (sm_tables / f"{tname}.tmdl").write_text(tmdl_text, encoding="utf-8")

        if tname != "dataset_summary":
            rel_lines.extend(
                [
                    f"relationship {_uid(f'rel.{tname}.dataset_summary')}",
                    f"\tfromColumn: {tname}.dataset_name",
                    "\ttoColumn: dataset_summary.dataset_name",
                    "",
                ]
            )

    (sm_def / "model.tmdl").write_text("\n".join(model_lines) + "\n", encoding="utf-8")
    (sm_def / "relationships.tmdl").write_text("\n".join(rel_lines), encoding="utf-8")

    # 3. PBIR 2.0.0 Report definition (5 pages)
    (rep_def / "version.json").write_text(
        json.dumps({"$schema": SCHEMA_REPORT_VER, "version": "2.0.0"}, indent=2),
        encoding="utf-8",
    )
    (rep_def / "report.json").write_text(
        json.dumps(
            {
                "$schema": SCHEMA_REPORT,
                "themeCollection": {
                    "baseTheme": {
                        "name": "Fluent2-CY26SU09",
                        "reportVersionAtImport": {"visual": "2.13.0", "report": "3.4.0", "page": "2.3.1"},
                        "type": "SharedResources",
                    }
                },
                "objects": {"section": [{"properties": {"verticalAlignment": {"expr": {"Literal": {"Value": "'Top'"}}}}}]},
                "resourcePackages": [
                    {
                        "name": "SharedResources",
                        "type": "SharedResources",
                        "items": [{"name": "Fluent2-CY26SU09", "path": "BaseThemes/Fluent2-CY26SU09.json", "type": "BaseTheme"}],
                    }
                ],
                "settings": {
                    "useStylableVisualContainerHeader": True,
                    "exportDataMode": "AllowSummarized",
                    "defaultDrillFilterOtherVisuals": True,
                    "allowChangeFilterTypes": True,
                    "useEnhancedTooltips": True,
                    "useDefaultAggregateDisplayName": True,
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    def _slicer_ds(page_tag: str, x: float = 30, y: float = 20, w: float = 420, h: float = 160, z: int = 0) -> Dict[str, Any]:
        return _visual_container(
            _short_id(f"{page_tag}.ds_slicer"),
            x, y, w, h, z,
            "slicer",
            {"Values": {"projections": [_proj_col("dataset_summary", "dataset_name")]}},
            title="Select Dataset",
        )

    p2_has_hourly = (data_dir / "hourly_fraud_pattern.csv").exists()
    p2_has_product = (data_dir / "fraud_by_product.csv").exists()
    p2_has_card = (data_dir / "fraud_by_card.csv").exists()

    p2_visuals: List[Dict[str, Any]] = [_slicer_ds("p2", 30, 20, 420, 160, 0)]
    if p2_has_hourly:
        p2_visuals.append(
            _visual_container(
                _short_id("p2.hourly"),
                480, 20, 1410, 240, 1,
                "lineChart",
                {
                    "Category": {"projections": [_proj_col("hourly_fraud_pattern", "hour_of_day")]},
                    "Series": {"projections": [_proj_col("hourly_fraud_pattern", "dataset_name")]},
                    "Y": {"projections": [_proj_agg("hourly_fraud_pattern", "fraud_rate_pct", func=1, label="Avg")]},
                },
                "Hourly Fraud Rate (%) Across 24-Hour Transaction Cycle",
            )
        )
    if p2_has_product and p2_has_card:
        p2_visuals.extend(
            [
                _visual_container(
                    _short_id("p2.amt_mean"),
                    30, 280, 600, 370, 2,
                    "clusteredColumnChart",
                    {
                        "Category": {"projections": [_proj_col("amount_distribution", "class_label")]},
                        "Y": {"projections": [_proj_agg("amount_distribution", "avg_amount", func=1, label="Avg"), _proj_agg("amount_distribution", "stddev_amount", func=1, label="Avg")]},
                    },
                    "Mean & StdDev Amount ($) by Class",
                ),
                _visual_container(
                    _short_id("p2.prod_bar"),
                    650, 280, 610, 370, 3,
                    "clusteredColumnChart",
                    {
                        "Category": {"projections": [_proj_col("fraud_by_product", "ProductCD")]},
                        "Y": {"projections": [_proj_agg("fraud_by_product", "fraud_rate_pct", func=1, label="Avg")]},
                    },
                    "IEEE-CIS Fraud Rate (%) by Product Code (ProductCD)",
                ),
                _visual_container(
                    _short_id("p2.card_bar"),
                    1280, 280, 610, 370, 4,
                    "clusteredColumnChart",
                    {
                        "Category": {"projections": [_proj_col("fraud_by_card", "card4")]},
                        "Y": {"projections": [_proj_agg("fraud_by_card", "fraud_rate_pct", func=1, label="Avg")]},
                    },
                    "IEEE-CIS Fraud Rate (%) by Card Network (card4)",
                ),
            ]
        )
    else:
        p2_visuals.extend(
            [
                _visual_container(
                    _short_id("p2.amt_mean"),
                    30, 280, 910, 370, 2,
                    "clusteredColumnChart",
                    {
                        "Category": {"projections": [_proj_col("amount_distribution", "class_label")]},
                        "Y": {"projections": [_proj_agg("amount_distribution", "avg_amount", func=1, label="Avg"), _proj_agg("amount_distribution", "stddev_amount", func=1, label="Avg")]},
                    },
                    "Mean & StdDev Transaction Amount ($) by Class",
                ),
                _visual_container(
                    _short_id("p2.amt_max"),
                    970, 280, 920, 370, 3,
                    "clusteredColumnChart",
                    {
                        "Category": {"projections": [_proj_col("amount_distribution", "class_label")]},
                        "Y": {"projections": [_proj_agg("amount_distribution", "max_amount", func=4, label="Max")]},
                    },
                    "Maximum Transaction Amount ($) by Class",
                ),
            ]
        )
    p2_visuals.extend(
        [
            _visual_container(
                _short_id("p2.amt_tbl"),
                30, 670, 910, 380, 5,
                "tableEx",
                {
                    "Values": {
                        "projections": [
                            _proj_col("amount_distribution", "dataset_name"),
                            _proj_col("amount_distribution", "class_label"),
                            _proj_col("amount_distribution", "count"),
                            _proj_col("amount_distribution", "min_amount"),
                            _proj_col("amount_distribution", "avg_amount"),
                            _proj_col("amount_distribution", "stddev_amount"),
                            _proj_col("amount_distribution", "max_amount"),
                        ]
                    }
                },
                "Transaction Amount Distribution Profile",
            ),
            _visual_container(
                _short_id("p2.null_tbl"),
                970, 670, 920, 380, 6,
                "tableEx",
                {
                    "Values": {
                        "projections": [
                            _proj_col("missingness_profile", "dataset_name"),
                            _proj_col("missingness_profile", "column_name"),
                            _proj_col("missingness_profile", "null_count"),
                            _proj_col("missingness_profile", "missing_percentage"),
                        ]
                    }
                },
                "Data Quality & Missingness Audit",
            ),
        ]
    )

    pages_spec: List[Dict[str, Any]] = [
        {
            "id": "p1overview0000000001",
            "title": "Fraud Overview",
            "visuals": [
                _slicer_ds("p1", 30, 20, 400, 180, 0),
                _visual_container(_short_id("p1.kpi1"), 460, 20, 340, 180, 1, "cardVisual", {"Data": {"projections": [_proj_meas("dataset_summary", "Total Transactions")]}}, "Total Transactions"),
                _visual_container(_short_id("p1.kpi2"), 820, 20, 340, 180, 2, "cardVisual", {"Data": {"projections": [_proj_meas("dataset_summary", "Total Legitimate Transactions")]}}, "Legitimate Transactions"),
                _visual_container(_short_id("p1.kpi3"), 1180, 20, 340, 180, 3, "cardVisual", {"Data": {"projections": [_proj_meas("dataset_summary", "Total Fraud Cases")]}}, "Fraud Cases"),
                _visual_container(_short_id("p1.kpi4"), 1540, 20, 350, 180, 4, "cardVisual", {"Data": {"projections": [_proj_meas("dataset_summary", "Fraud Prevalence Pct")]}}, "Fraud Prevalence (%)"),
                _visual_container(
                    _short_id("p1.split_bar"),
                    30, 230, 910, 430, 5,
                    "clusteredColumnChart",
                    {
                        "Category": {"projections": [_proj_col("dataset_summary", "dataset_name")]},
                        "Y": {
                            "projections": [
                                _proj_agg("dataset_summary", "train_records", 0, "Sum"),
                                _proj_agg("dataset_summary", "val_records", 0, "Sum"),
                                _proj_agg("dataset_summary", "test_records", 0, "Sum"),
                            ]
                        },
                    },
                    "Train / Validation / Test Partition Sizes",
                ),
                _visual_container(
                    _short_id("p1.class_bar"),
                    970, 230, 920, 430, 6,
                    "clusteredColumnChart",
                    {
                        "Category": {"projections": [_proj_col("dataset_summary", "dataset_name")]},
                        "Y": {
                            "projections": [
                                _proj_meas("dataset_summary", "Total Legitimate Transactions"),
                                _proj_meas("dataset_summary", "Total Fraud Cases"),
                            ]
                        },
                    },
                    "Class Volume Distribution (Legitimate vs Fraud)",
                ),
                _visual_container(
                    _short_id("p1.tbl"),
                    30, 690, 1860, 360, 7,
                    "tableEx",
                    {
                        "Values": {
                            "projections": [
                                _proj_col("dataset_summary", "dataset_name"),
                                _proj_col("dataset_summary", "total_records"),
                                _proj_col("dataset_summary", "legitimate_records"),
                                _proj_col("dataset_summary", "fraud_records"),
                                _proj_col("dataset_summary", "fraud_prevalence_pct"),
                                _proj_col("dataset_summary", "numerical_features"),
                                _proj_col("dataset_summary", "categorical_features"),
                                _proj_col("dataset_summary", "dropped_high_null_features"),
                            ]
                        }
                    },
                    "Dataset Ingestion & Feature Schema Summary",
                ),
            ],
        },
        {
            "id": "p2patterns0000000002",
            "title": "Fraud Pattern Analysis",
            "visuals": p2_visuals,
        },
        {
            "id": "p3models000000000003",
            "title": "Model Performance Comparison",
            "visuals": [
                _slicer_ds("p3", 30, 20, 380, 170, 0),
                _visual_container(
                    _short_id("p3.m_slicer"),
                    430, 20, 350, 170, 1,
                    "slicer",
                    {"Values": {"projections": [_proj_col("model_comparison", "model_name")]}},
                    "Filter Classifier",
                ),
                _visual_container(_short_id("p3.kpi1"), 810, 20, 350, 170, 2, "cardVisual", {"Data": {"projections": [_proj_meas("model_comparison", "Top Performing Model")]}}, "Top PR-AUC Classifier"),
                _visual_container(_short_id("p3.kpi2"), 1180, 20, 340, 170, 3, "cardVisual", {"Data": {"projections": [_proj_meas("model_comparison", "Best PR-AUC")]}}, "Best PR-AUC"),
                _visual_container(_short_id("p3.kpi3"), 1540, 20, 350, 170, 4, "cardVisual", {"Data": {"projections": [_proj_meas("model_comparison", "Lowest Log Loss")]}}, "Lowest Log Loss"),
                _visual_container(
                    _short_id("p3.metrics_bar"),
                    30, 220, 1140, 430, 5,
                    "clusteredColumnChart",
                    {
                        "Category": {"projections": [_proj_col("model_comparison", "model_name")]},
                        "Y": {
                            "projections": [
                                _proj_agg("model_comparison", "precision", func=1, label="Avg"),
                                _proj_agg("model_comparison", "recall", func=1, label="Avg"),
                                _proj_agg("model_comparison", "f1_score", func=1, label="Avg"),
                                _proj_agg("model_comparison", "roc_auc", func=1, label="Avg"),
                                _proj_agg("model_comparison", "pr_auc", func=1, label="Avg"),
                            ]
                        },
                    },
                    "Classifier Comparison Across Core Discrimination Metrics",
                ),
                _visual_container(
                    _short_id("p3.logloss_bar"),
                    1200, 220, 690, 430, 6,
                    "clusteredColumnChart",
                    {
                        "Category": {"projections": [_proj_col("model_comparison", "model_name")]},
                        "Y": {"projections": [_proj_agg("model_comparison", "log_loss", func=1, label="Avg")]},
                    },
                    "Probability Calibration Error (Binary Log Loss)",
                ),
                _visual_container(
                    _short_id("p3.scorecard"),
                    30, 680, 1860, 370, 7,
                    "tableEx",
                    {
                        "Values": {
                            "projections": [
                                _proj_col("model_comparison", "model_name"),
                                _proj_col("model_comparison", "precision"),
                                _proj_col("model_comparison", "recall"),
                                _proj_col("model_comparison", "f1_score"),
                                _proj_col("model_comparison", "roc_auc"),
                                _proj_col("model_comparison", "pr_auc"),
                                _proj_col("model_comparison", "log_loss"),
                                _proj_col("model_comparison", "true_positives"),
                                _proj_col("model_comparison", "false_positives"),
                                _proj_col("model_comparison", "false_negatives"),
                                _proj_col("model_comparison", "training_time_sec"),
                            ]
                        }
                    },
                    "Held-Out Classifier Evaluation Scorecard",
                ),
            ],
        },
        {
            "id": "p4threshold000000004",
            "title": "Risk & Decision Threshold Analysis",
            "visuals": [
                _slicer_ds("p4", 30, 20, 440, 170, 0),
                _visual_container(_short_id("p4.kpi1"), 500, 20, 440, 170, 1, "cardVisual", {"Data": {"projections": [_proj_meas("threshold_analysis", "Minimum Operational Loss")]}}, "Min Operational Loss ($10 FP / $500 FN)"),
                _visual_container(_short_id("p4.kpi2"), 970, 20, 440, 170, 2, "cardVisual", {"Data": {"projections": [_proj_meas("threshold_analysis", "Optimal Threshold")]}}, "Cost-Optimal Decision Threshold"),
                _visual_container(
                    _short_id("p4.pr_line"),
                    30, 220, 910, 430, 3,
                    "lineChart",
                    {
                        "Category": {"projections": [_proj_col("threshold_analysis", "threshold")]},
                        "Y": {
                            "projections": [
                                _proj_agg("threshold_analysis", "precision", func=1, label="Avg"),
                                _proj_agg("threshold_analysis", "recall", func=1, label="Avg"),
                                _proj_agg("threshold_analysis", "f1_score", func=1, label="Avg"),
                            ]
                        },
                    },
                    "Precision, Recall & F1-Score Across Probability Cutoffs",
                ),
                _visual_container(
                    _short_id("p4.cost_line"),
                    970, 220, 920, 430, 4,
                    "lineChart",
                    {
                        "Category": {"projections": [_proj_col("threshold_analysis", "threshold")]},
                        "Y": {"projections": [_proj_agg("threshold_analysis", "total_operational_cost", func=0, label="Sum")]},
                    },
                    "Total Operational Financial Cost ($) vs Decision Threshold",
                ),
                _visual_container(
                    _short_id("p4.tbl"),
                    30, 680, 1860, 370, 5,
                    "tableEx",
                    {
                        "Values": {
                            "projections": [
                                _proj_col("threshold_analysis", "threshold"),
                                _proj_col("threshold_analysis", "precision"),
                                _proj_col("threshold_analysis", "recall"),
                                _proj_col("threshold_analysis", "f1_score"),
                                _proj_col("threshold_analysis", "true_positives"),
                                _proj_col("threshold_analysis", "false_positives"),
                                _proj_col("threshold_analysis", "false_negatives"),
                                _proj_col("threshold_analysis", "flagged_volume"),
                                _proj_col("threshold_analysis", "alert_rate_pct"),
                                _proj_col("threshold_analysis", "total_operational_cost"),
                            ]
                        }
                    },
                    "Decision Threshold Sensitivity Schedule (0.05 – 0.95)",
                ),
            ],
        },
        {
            "id": "p5crossds00000000005",
            "title": "Cross-Dataset Comparison",
            "visuals": [
                _slicer_ds("p5", 30, 20, 440, 170, 0),
                _visual_container(_short_id("p5.kpi1"), 500, 20, 440, 170, 1, "cardVisual", {"Data": {"projections": [_proj_meas("model_comparison", "Best F1 Score")]}}, "Best F1-Score"),
                _visual_container(_short_id("p5.kpi2"), 970, 20, 440, 170, 2, "cardVisual", {"Data": {"projections": [_proj_meas("model_comparison", "Best PR-AUC")]}}, "Best PR-AUC"),
                _visual_container(
                    _short_id("p5.cross_bar"),
                    30, 220, 910, 430, 3,
                    "clusteredColumnChart",
                    {
                        "Category": {"projections": [_proj_col("model_comparison", "model_name")]},
                        "Series": {"projections": [_proj_col("model_comparison", "dataset_name")]},
                        "Y": {"projections": [_proj_agg("model_comparison", "pr_auc", func=1, label="Avg")]},
                    },
                    "Cross-Dataset PR-AUC Comparison by Classifier",
                ),
                _visual_container(
                    _short_id("p5.cross_f1"),
                    970, 220, 920, 430, 4,
                    "clusteredColumnChart",
                    {
                        "Category": {"projections": [_proj_col("model_comparison", "model_name")]},
                        "Series": {"projections": [_proj_col("model_comparison", "dataset_name")]},
                        "Y": {"projections": [_proj_agg("model_comparison", "f1_score", func=1, label="Avg")]},
                    },
                    "Cross-Dataset F1-Score Comparison by Classifier",
                ),
                _visual_container(
                    _short_id("p5.tuning_tbl"),
                    30, 680, 1860, 370, 5,
                    "tableEx",
                    {
                        "Values": {
                            "projections": [
                                _proj_col("hyperparameter_tuning", "dataset_name"),
                                _proj_col("hyperparameter_tuning", "model_name"),
                                _proj_col("hyperparameter_tuning", "hyperparameters"),
                                _proj_col("hyperparameter_tuning", "val_pr_auc"),
                                _proj_col("hyperparameter_tuning", "val_roc_auc"),
                                _proj_col("hyperparameter_tuning", "val_log_loss"),
                                _proj_col("hyperparameter_tuning", "selected"),
                            ]
                        }
                    },
                    "Validation Hyperparameter Search Results Across Datasets",
                ),
            ],
        },
    ]

    page_ids: List[str] = []
    for ps in pages_spec:
        pid = ps["id"]
        page_ids.append(pid)
        pdir = rep_pages / pid
        vdir = pdir / "visuals"
        vdir.mkdir(parents=True, exist_ok=True)
        (pdir / "page.json").write_text(
            json.dumps(
                {
                    "$schema": SCHEMA_PAGE,
                    "name": pid,
                    "displayName": ps["title"],
                    "displayOption": "FitToPage",
                    "height": 1080,
                    "width": 1920,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        for vis in ps["visuals"]:
            vid = vis["name"]
            vis_folder = vdir / vid
            vis_folder.mkdir(parents=True, exist_ok=True)
            (vis_folder / "visual.json").write_text(json.dumps(vis, indent=2), encoding="utf-8")

    (rep_pages / "pages.json").write_text(
        json.dumps({"$schema": SCHEMA_PAGES, "pageOrder": page_ids, "activePageName": page_ids[0]}, indent=2),
        encoding="utf-8",
    )

    print(f"5-page Power BI Project (.pbip) generated cleanly at: {pbip_path}")
    return pbip_path


if __name__ == "__main__":
    out_dir = Path(__file__).resolve().parent.parent / "powerbi"
    build_powerbi_project(out_dir)

