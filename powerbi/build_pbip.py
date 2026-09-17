#!/usr/bin/env python3
"""Generates the Lyra EAP Power BI project (PBIP): semantic model in TMDL.

PBIP rather than a binary .pbix: it is plain text, so the model diffs in git,
and it is generated from the exported Parquet, so column names and types
cannot drift from the data. Run export_data.py first, then this, then
build_report.py.

The data folder is a Power Query parameter (DataFolder). Setup-DataPaths.ps1
points it at wherever the project was extracted, because File.Contents needs
an absolute path.

    python powerbi/build_pbip.py
"""
from __future__ import annotations

import shutil
import uuid
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
NAME = "LyraEAP"
SM = ROOT / f"{NAME}.SemanticModel"
RPT = ROOT / f"{NAME}.Report"

TYPES = {"BIGINT": "int64", "INTEGER": "int64", "HUGEINT": "int64", "SMALLINT": "int64",
         "DOUBLE": "double", "FLOAT": "double", "DECIMAL": "decimal", "VARCHAR": "string",
         "BOOLEAN": "boolean", "DATE": "dateTime", "TIMESTAMP": "dateTime"}

TABLES = ["fact_session", "fact_experience", "fact_medication",
          "dim_date", "dim_country", "dim_client", "dim_facility", "dim_service_type",
          "dim_issue_category", "dim_counsellor", "dim_risk_level", "dim_medication",
          "dq_check", "security_country_access"]

# (from table, from column, to table, to column, active)
RELATIONSHIPS = [
    ("fact_session", "visit_date", "dim_date", "calendar_date", True),
    ("fact_session", "country_code", "dim_country", "country_code", True),
    ("fact_session", "client_key", "dim_client", "client_key", True),
    ("fact_session", "facility_key", "dim_facility", "facility_key", True),
    ("fact_session", "service_type_key", "dim_service_type", "service_type_key", True),
    ("fact_session", "issue_category_key", "dim_issue_category", "issue_category_key", True),
    ("fact_session", "counsellor_key", "dim_counsellor", "counsellor_key", True),
    ("fact_session", "risk_level", "dim_risk_level", "risk_level", True),
    ("fact_experience", "feedback_date", "dim_date", "calendar_date", True),
    ("fact_experience", "country_code", "dim_country", "country_code", True),
    ("fact_experience", "service_type_key", "dim_service_type", "service_type_key", True),
    ("fact_experience", "issue_category_key", "dim_issue_category", "issue_category_key", True),
    ("fact_medication", "sale_date", "dim_date", "calendar_date", True),
    ("fact_medication", "country_code", "dim_country", "country_code", True),
    ("fact_medication", "client_key", "dim_client", "client_key", True),
    ("fact_medication", "medication_key", "dim_medication", "medication_key", True),
    # Dimension-to-dimension links stay inactive: facts already reach dim_country
    # directly, and a second active path would make country filtering ambiguous.
    ("dim_client", "client_country_code", "dim_country", "country_code", False),
    ("dim_facility", "facility_country_code", "dim_country", "country_code", False),
]

SORT_BY = {("dim_date", "month_name"): "month_number", ("dim_date", "month_short"): "month_number",
           ("dim_date", "year_month"): "year_month_sort", ("dim_risk_level", "risk_level"): "risk_sort",
           ("fact_session", "age_band"): "age_band_sort"}

FORMATS = {"revenue_zar": '"R"#,0', "sales_zar": '"R"#,0', "calendar_date": "yyyy-mm-dd",
           "visit_date": "yyyy-mm-dd", "feedback_date": "yyyy-mm-dd", "sale_date": "yyyy-mm-dd",
           "month_start": "mmm yyyy", "contract_start": "yyyy-mm-dd", "contract_end": "yyyy-mm-dd"}

S, E, X, MD, DQ = "01 Sessions", "02 Clinical", "03 Capacity", "04 Experience", "05 Medication"
Q = "06 Data Quality"
MEASURES = [
    ("Sessions", "SUM(fact_session[session_count])", "#,0", S),
    ("Employees Served", "DISTINCTCOUNT(fact_session[employee_key])", "#,0", S),
    ("Sessions per Employee", "DIVIDE([Sessions], [Employees Served])", "0.00", S),
    ("Revenue (ZAR)", "SUM(fact_session[revenue_zar])", '"R"#,0', S),
    ("Revenue per Session", "DIVIDE([Revenue (ZAR)], [Sessions])", '"R"#,0', S),
    ("Avg Session Minutes", "AVERAGE(fact_session[duration_minutes])", "0.0", S),
    ("Sessions Prior Year", "CALCULATE([Sessions], SAMEPERIODLASTYEAR(dim_date[calendar_date]))", "#,0", S),
    ("Sessions YoY %", "IF(NOT ISBLANK([Sessions]), DIVIDE([Sessions] - [Sessions Prior Year], [Sessions Prior Year]))", "0.0%", S),

    ("Avg Risk Score", "AVERAGE(fact_session[risk_score])", "0.0", E),
    ("High/Critical Sessions",
     'CALCULATE([Sessions], fact_session[risk_level] IN {"High", "Critical"})', "#,0", E),
    ("High/Critical Share", "DIVIDE([High/Critical Sessions], [Sessions])", "0.0%", E),
    ("Escalations", "SUM(fact_session[escalation_flag])", "#,0", E),
    ("Escalation Rate", "DIVIDE([Escalations], [Sessions])", "0.0%", E),
    ("Follow-ups Required", "SUM(fact_session[follow_up_flag])", "#,0", E),
    ("Follow-up Rate", "DIVIDE([Follow-ups Required], [Sessions])", "0.0%", E),
    ("Resolved Cases", "SUM(fact_session[resolved_flag])", "#,0", E),
    ("Resolution Rate", "DIVIDE([Resolved Cases], [Sessions])", "0.0%", E),
    ("Unresolved High/Critical",
     'CALCULATE([Sessions] - [Resolved Cases], fact_session[risk_level] IN {"High", "Critical"})', "#,0", E),

    ("Active Counsellors", "DISTINCTCOUNT(fact_session[counsellor_key])", "#,0", X),
    ("Sessions per Counsellor", "DIVIDE([Sessions], [Active Counsellors])", "#,0", X),
    ("Facilities Used", "DISTINCTCOUNT(fact_session[facility_key])", "#,0", X),
    ("Sessions per Facility", "DIVIDE([Sessions], [Facilities Used])", "#,0", X),

    ("Survey Responses", "COUNTROWS(fact_experience)", "#,0", MD),
    ("Avg Satisfaction", "AVERAGE(fact_experience[satisfaction_score])", "0.00", MD),
    ("Avg Staff Rating", "AVERAGE(fact_experience[staff_rating])", "0.00", MD),
    ("Avg Speed Rating", "AVERAGE(fact_experience[speed_rating])", "0.00", MD),
    ("Avg Wait Minutes", "AVERAGE(fact_experience[wait_minutes])", "0.0", MD),
    ("Avg Improvement", "AVERAGE(fact_experience[improvement_score])", "0.00", MD),
    ("Would Recommend Rate", "AVERAGE(fact_experience[would_recommend_flag])", "0.0%", MD),
    ("Complaint Rate", "AVERAGE(fact_experience[complaint_flag])", "0.0%", MD),
    ("Net Promoter Score",
     "VAR n = [Survey Responses] "
     "VAR p = CALCULATE(COUNTROWS(fact_experience), fact_experience[recommend_score] >= 9) "
     "VAR d = CALCULATE(COUNTROWS(fact_experience), fact_experience[recommend_score] <= 6) "
     "RETURN DIVIDE(p - d, n) * 100", "0", MD),

    ("Medication Sales (ZAR)", "SUM(fact_medication[sales_zar])", '"R"#,0', DQ),
    ("Units Sold", "SUM(fact_medication[units])", "#,0", DQ),
    ("Medication Transactions", "COUNTROWS(fact_medication)", "#,0", DQ),
    ("Mental Health Medication Sales",
     "CALCULATE([Medication Sales (ZAR)], dim_medication[mental_health_flag] = 1)", '"R"#,0', DQ),
    ("Mental Health Medication Share",
     "DIVIDE([Mental Health Medication Sales], [Medication Sales (ZAR)])", "0.0%", DQ),
    ("Avg Sale Value", "DIVIDE([Medication Sales (ZAR)], [Medication Transactions])", '"R"#,0', DQ),

    ("DQ Checks", "COUNTROWS(dq_check)", "#,0", Q),
    ("DQ Affected Rows", "SUM(dq_check[affected_rows])", "#,0", Q),
    ("Under-18 Sessions", "CALCULATE([Sessions], fact_session[age] < 18)", "#,0", Q),
    ("Under-18 Share", "DIVIDE([Under-18 Sessions], [Sessions])", "0.0%", Q),
    ("Facilities", "COUNTROWS(dim_facility)", "#,0", Q),
    ("Province Mismatches",
     "CALCULATE(COUNTROWS(dim_facility), dim_facility[province_matches_city] = 0)", "#,0", Q),
    ("Province Mismatch Rate", "DIVIDE([Province Mismatches], [Facilities])", "0.0%", Q),
]

HIDDEN_TABLES = {"security_country_access"}


def tag():
    return str(uuid.uuid4())


def hidden(table, col):
    if table.startswith("fact_") and (col.endswith("_key") or col.endswith("_sort")):
        return True
    if col.endswith("_sort") or col in ("month_number", "year_month_sort", "risk_sort"):
        return table != "dim_date" or col != "month_number"
    return table in HIDDEN_TABLES


def table_tmdl(name, cols):
    L = [f"table {name}", f"\tlineageTag: {tag()}"]
    if name == "dim_date":
        L.append("\tdataCategory: Time")
    if name in HIDDEN_TABLES:
        L.append("\tisHidden")
    L.append("")
    for cname, ctype in cols:
        dtype = TYPES.get(ctype.upper().split("(")[0].strip(), "string")
        numeric_attr = dtype in ("int64", "double", "decimal") and not (
            cname.endswith("_key") or cname.endswith("_flag") or cname.endswith("_sort") or cname.startswith("is_")
            or cname in ("year", "quarter", "month_number", "age", "risk_score", "check_order"))
        L += [f"\tcolumn {cname}", f"\t\tdataType: {dtype}"]
        if name == "dim_date" and cname == "calendar_date":
            L.append("\t\tisKey")
        if cname in FORMATS:
            L.append(f"\t\tformatString: {FORMATS[cname]}")
        elif dtype == "int64":
            L.append("\t\tformatString: 0")
        if hidden(name, cname):
            L.append("\t\tisHidden")
        L += [f"\t\tlineageTag: {tag()}",
              f"\t\tsummarizeBy: {'sum' if numeric_attr else 'none'}",
              f"\t\tsourceColumn: {cname}"]
        if (name, cname) in SORT_BY:
            L.append(f"\t\tsortByColumn: {SORT_BY[(name, cname)]}")
        L.append("")
    L += [f"\tpartition {name} = m", "\t\tmode: import", "\t\tsource =",
          "\t\t\t\tlet",
          f'\t\t\t\t    Source = Parquet.Document(File.Contents(DataFolder & "\\{name}.parquet"))',
          "\t\t\t\tin", "\t\t\t\t    Source", "", "\tannotation PBI_ResultType = Table", ""]
    return "\n".join(L)


def measures_tmdl():
    L = ["table _Measures", f"\tlineageTag: {tag()}", ""]
    for mname, expr, fmt, folder in MEASURES:
        L += [f"\tmeasure '{mname}' = {expr}", f"\t\tformatString: {fmt}",
              f"\t\tdisplayFolder: {folder}", f"\t\tlineageTag: {tag()}", ""]
    L += ["\tcolumn _placeholder", "\t\tisHidden", "\t\tdataType: string", f"\t\tlineageTag: {tag()}",
          "\t\tsummarizeBy: none", "\t\tsourceColumn: _placeholder", "",
          "\tpartition _Measures = m", "\t\tmode: import", "\t\tsource =", "\t\t\t\tlet",
          '\t\t\t\t    Source = #table(type table [_placeholder = text], {{""}})',
          "\t\t\t\tin", "\t\t\t\t    Source", ""]
    return "\n".join(L)


def main():
    con = duckdb.connect()
    schemas = {}
    for t in TABLES:
        p = DATA / f"{t}.parquet"
        if not p.exists():
            raise SystemExit(f"missing {p} - run export_data.py first")
        d = con.sql(f"describe select * from read_parquet('{p.as_posix()}')").df()
        schemas[t] = list(zip(d["column_name"], d["column_type"]))

    # Every relationship and sort column must name a real column.
    for ft, fc, tt, tc, _ in RELATIONSHIPS:
        for t, c in ((ft, fc), (tt, tc)):
            if c not in dict(schemas[t]):
                raise SystemExit(f"relationship column {t}.{c} does not exist")
    for (t, c), s in SORT_BY.items():
        if c not in dict(schemas[t]) or s not in dict(schemas[t]):
            raise SystemExit(f"sort column {t}.{c} -> {s} does not exist")

    if SM.exists():
        shutil.rmtree(SM)
    (SM / "definition" / "tables").mkdir(parents=True)
    (SM / "definition" / "roles").mkdir()

    d = SM / "definition"
    (d / "database.tmdl").write_text(f"database {NAME}\n\tcompatibilityLevel: 1600\n", encoding="utf-8")
    for t, cols in schemas.items():
        (d / "tables" / f"{t}.tmdl").write_text(table_tmdl(t, cols), encoding="utf-8")
    (d / "tables" / "_Measures.tmdl").write_text(measures_tmdl(), encoding="utf-8")

    rel = []
    for ft, fc, tt, tc, active in RELATIONSHIPS:
        rel.append(f"relationship {tag()}")
        if not active:
            rel.append("\tisActive: false")
        rel += [f"\tfromColumn: {ft}.{fc}", f"\ttoColumn: {tt}.{tc}", ""]
    (d / "relationships.tmdl").write_text("\n".join(rel), encoding="utf-8")

    data_path = str(DATA).replace('"', '""')
    (d / "expressions.tmdl").write_text(
        f'expression DataFolder = "{data_path}" meta [IsParameterQuery=true, Type="Text", IsParameterQueryRequired=true]\n'
        f"\tlineageTag: {tag()}\n\n\tannotation PBI_ResultType = Text\n", encoding="utf-8")

    # Dynamic row-level security: a signed-in user sees only the countries
    # mapped to their UPN. Country filters flow from dim_country to all facts.
    (d / "roles" / "Country Manager.tmdl").write_text(
        "role 'Country Manager'\n\tmodelPermission: read\n\n"
        "\ttablePermission dim_country = [country_code] IN CALCULATETABLE(VALUES(security_country_access[country_code]), "
        "security_country_access[user_email] = USERPRINCIPALNAME())\n\n"
        f"\tannotation PBI_Id = {uuid.uuid4().hex}\n", encoding="utf-8")

    model = ["model Model", "\tculture: en-ZA", "\tdefaultPowerBIDataSourceVersion: powerBI_V3",
             "\tdiscourageImplicitMeasures", "\tsourceQueryCulture: en-ZA", "",
             "\tannotation __PBI_TimeIntelligenceEnabled = 0", "",
             '\tannotation PBI_QueryOrder = ["DataFolder",' + ",".join(f'"{t}"' for t in ["_Measures"] + TABLES) + "]", ""]
    model += [f"ref table {t}" for t in ["_Measures"] + TABLES]
    model += ["", "ref role 'Country Manager'", ""]
    (d / "model.tmdl").write_text("\n".join(model), encoding="utf-8")
    (SM / "definition.pbism").write_text('{\n  "version": "4.2",\n  "settings": {}\n}\n', encoding="utf-8")

    (ROOT / f"{NAME}.pbip").write_text(
        '{\n  "version": "1.0",\n  "artifacts": [\n    { "report": { "path": "' + NAME + '.Report" } }\n  ],\n'
        '  "settings": { "enableAutoRecovery": true }\n}\n', encoding="utf-8")

    print(f"wrote {SM.name}: {len(schemas)} tables, {sum(len(c) for c in schemas.values())} columns, "
          f"{len(MEASURES)} measures, {len(RELATIONSHIPS)} relationships, 1 RLS role")


if __name__ == "__main__":
    main()
