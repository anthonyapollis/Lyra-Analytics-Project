#!/usr/bin/env python3
"""Generates the Lyra EAP Power BI report pages (PBIR-Legacy report.json).

Every field a visual uses is checked against the TMDL model, and every page
is checked for off-canvas or overlapping visuals, before anything is written.
Numbers quoted in text come from data/findings.json, written by export_data.py.

    python powerbi/build_report.py
"""
from __future__ import annotations

import json
import re
import shutil
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent
NAME = "LyraEAP"
SM = ROOT / f"{NAME}.SemanticModel" / "definition"
RPT = ROOT / f"{NAME}.Report"
FINDINGS = json.loads((ROOT / "data" / "findings.json").read_text(encoding="utf-8"))

W, H = 1280, 720
NAVY, TEAL, GREEN, AMBER, RED, PURPLE = "#0A2540", "#0077A3", "#068F6A", "#C98A12", "#C8243A", "#6D4BC2"
SLATE, RULE, PAPER, CANVAS = "#5B6B7B", "#DCE3EA", "#FFFFFF", "#F3F6F9"
SERIES = [TEAL, GREEN, AMBER, PURPLE, RED, "#2F8FCE", "#7A8B99", "#3E7C59", "#B5546B", "#8A6D3B"]
M = "_Measures"

THEME = {
    "name": "LyraEAP", "dataColors": SERIES, "background": PAPER, "foreground": NAVY,
    "tableAccent": TEAL, "good": GREEN, "neutral": AMBER, "bad": RED,
    "maximum": RED, "center": AMBER, "minimum": GREEN,
    "textClasses": {
        "title": {"fontSize": 12, "fontFace": "Segoe UI Semibold", "color": NAVY},
        "header": {"fontSize": 11, "fontFace": "Segoe UI Semibold", "color": NAVY},
        "label": {"fontSize": 10, "fontFace": "Segoe UI", "color": SLATE},
        "callout": {"fontSize": 26, "fontFace": "Segoe UI Semibold", "color": TEAL},
    },
}


def gid():
    return uuid.uuid4().hex[:20]


def lit(s):
    return {"expr": {"Literal": {"Value": f"'{s}'"}}}


def raw(v):
    return {"expr": {"Literal": {"Value": v}}}


def colour(hexstr):
    return {"solid": {"color": lit(hexstr)}}


def tint(hexstr, strength=0.12):
    """Blend a colour into white, so a KPI tile carries its accent without competing with the figure."""
    rgb = [int(hexstr[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(255 - (255 - c) * strength):02X}" for c in rgb)


def visual(vtype, x, y, w, h, title=None, projections=None, objects=None, accent=None, z=0):
    projections = projections or {}
    froms, selects, proj, seen = {}, [], {}, set()
    for role, fields in projections.items():
        proj[role] = []
        for table, name, is_measure in fields:
            alias = "t" + str(list(dict.fromkeys([*froms.values(), table])).index(table))
            froms[alias] = table
            ref = f"{table}.{name}"
            if ref not in seen:
                node = {"Expression": {"SourceRef": {"Source": alias}}, "Property": name}
                selects.append({"Measure" if is_measure else "Column": node, "Name": ref})
                seen.add(ref)
            proj[role].append({"queryRef": ref})

    vc = {"background": [{"properties": {"color": colour(PAPER), "show": raw("true"), "transparency": raw("0D")}}],
          "border": [{"properties": {"color": colour(RULE), "show": raw("true"), "radius": raw("6D")}}],
          "dropShadow": [{"properties": {"show": raw("false")}}]}
    if title:
        vc["title"] = [{"properties": {"text": lit(title), "fontColor": colour(accent or NAVY),
                                       "fontSize": raw("11D"), "fontFamily": lit("Segoe UI Semibold"),
                                       "alignment": lit("left"), "show": raw("true")}}]

    objects = dict(objects or {})
    n_series = len(proj.get("Y", [])) or 1
    if vtype in ("clusteredColumnChart", "clusteredBarChart", "lineChart"):
        objects.setdefault("dataPoint", [{"properties": {"fill": colour(accent if accent and n_series == 1 else SERIES[i % len(SERIES)])},
                                          "selector": {"metadata": proj["Y"][i]["queryRef"]}} for i in range(n_series)])
        axis = {"showAxisTitle": raw("false"), "fontSize": raw("9D"), "labelColor": colour(SLATE)}
        objects.setdefault("categoryAxis", [{"properties": dict(axis)}])
        objects.setdefault("valueAxis", [{"properties": {**axis, "gridlineColor": colour(RULE)}}])
        objects.setdefault("legend", [{"properties": {"show": raw("true" if n_series > 1 else "false"), "position": lit("Top"),
                                                      "labelColor": colour(SLATE), "fontSize": raw("9D")}}])
        if vtype != "lineChart":
            objects.setdefault("labels", [{"properties": {"show": raw("true"), "fontSize": raw("8D"), "color": colour(SLATE)}}])
    if vtype == "donutChart":
        objects.setdefault("legend", [{"properties": {"show": raw("true"), "position": lit("Bottom"), "fontSize": raw("9D")}}])
        objects.setdefault("labels", [{"properties": {"labelStyle": lit("Percent of total"), "fontSize": raw("9D")}}])
    if vtype == "card":
        vc["background"] = [{"properties": {"color": colour(tint(accent or TEAL)), "show": raw("true"), "transparency": raw("0D")}}]
        vc["border"] = [{"properties": {"color": colour(accent or TEAL), "show": raw("true"), "radius": raw("6D")}}]
        vc["title"] = [{"properties": {"text": lit(title), "fontColor": colour(SLATE), "fontSize": raw("10D"),
                                       "fontFamily": lit("Segoe UI"), "alignment": lit("left"), "show": raw("true")}}]
        objects.setdefault("labels", [{"properties": {"color": colour(accent or TEAL), "fontSize": raw("22D"),
                                                      "fontFamily": lit("Segoe UI Semibold")}}])
        objects.setdefault("categoryLabels", [{"properties": {"show": raw("false")}}])
    if vtype in ("tableEx", "pivotTable"):
        objects.setdefault("columnHeaders", [{"properties": {"fontColor": colour(PAPER), "backColor": colour(NAVY),
                                                             "fontSize": raw("9D")}}])
        objects.setdefault("values", [{"properties": {"fontSize": raw("9D"), "fontColor": colour(NAVY)}}])
    if vtype == "slicer":
        objects.setdefault("data", [{"properties": {"mode": lit("Dropdown")}}])
        objects.setdefault("header", [{"properties": {"show": raw("false")}}])

    cfg = {"name": gid(),
           "layouts": [{"id": 0, "position": {"x": x, "y": y, "z": z, "width": w, "height": h}}],
           "singleVisual": {"visualType": vtype, "projections": proj,
                            "prototypeQuery": {"Version": 2,
                                               "From": [{"Name": a, "Entity": t, "Type": 0} for a, t in froms.items()],
                                               "Select": selects},
                            "drillFilterOtherVisuals": True, "objects": objects, "vcObjects": vc}}
    return {"x": x, "y": y, "z": z, "width": w, "height": h, "config": json.dumps(cfg), "filters": "[]"}


def textbox(x, y, w, h, runs, z=0):
    paragraphs = []
    for para in runs if isinstance(runs[0], list) else [runs]:
        paragraphs.append({"textRuns": [{"value": t, "textStyle": st} for t, st in para]})
    cfg = {"name": gid(), "layouts": [{"id": 0, "position": {"x": x, "y": y, "z": z, "width": w, "height": h}}],
           "singleVisual": {"visualType": "textbox", "drillFilterOtherVisuals": True,
                            "objects": {"general": [{"properties": {"paragraphs": paragraphs}}]},
                            "vcObjects": {"background": [{"properties": {"show": raw("false")}}]}}}
    return {"x": x, "y": y, "z": z, "width": w, "height": h, "config": json.dumps(cfg), "filters": "[]"}


BIG = {"fontSize": "20pt", "fontWeight": "bold", "color": NAVY}
SUB = {"fontSize": "10pt", "color": SLATE}
HEAD = {"fontSize": "12pt", "fontWeight": "bold", "color": TEAL}
BODY = {"fontSize": "10pt", "color": NAVY}
ACT = {"fontSize": "10pt", "fontWeight": "bold", "color": GREEN}


def header(title, subtitle, slicers=True):
    v = [textbox(30, 6, 780, 50, [(title, BIG)]), textbox(30, 56, 780, 44, [(subtitle, SUB)])]
    if slicers:
        v += [visual("slicer", 830, 18, 205, 72, "Year", {"Values": [("dim_date", "year", False)]}),
              visual("slicer", 1045, 18, 205, 72, "Country", {"Values": [("dim_country", "country", False)]})]
    return v


def cards(items, y=105, h=92):
    w = (1220 - 10 * (len(items) - 1)) // len(items)
    return [visual("card", 30 + i * (w + 10), y, w, h, label, {"Values": [(M, meas, True)]}, accent=acc)
            for i, (label, meas, acc) in enumerate(items)]


def page(display, ordinal, visuals):
    return {"id": ordinal, "name": f"ReportSection{gid()}", "displayName": display, "filters": "[]",
            "ordinal": ordinal, "visualContainers": visuals,
            "config": json.dumps({"objects": {"background": [{"properties": {"color": colour(CANVAS), "transparency": raw("0D")}}],
                                              "outspace": [{"properties": {"color": colour(CANVAS)}}]}}),
            "displayOption": 1, "width": W, "height": H}


def pct(v):
    return f"{v * 100:.1f}%"


def build():
    F, pages = FINDINGS, []

    v = header("Lyra EAP — executive overview",
               "Employee assistance sessions, outcomes and revenue across five countries, 2018–2022. Synthetic data. "
               "Use Year and Country to focus; select any bar to cross-filter the page.")
    v += cards([("Sessions", "Sessions", TEAL), ("Employees served", "Employees Served", TEAL),
                ("Revenue (ZAR)", "Revenue (ZAR)", TEAL), ("Resolution rate", "Resolution Rate", GREEN),
                ("High/critical risk", "High/Critical Share", AMBER), ("Escalation rate", "Escalation Rate", RED)])
    v += [visual("lineChart", 30, 210, 610, 250, "Sessions per month",
                 {"Category": [("dim_date", "year_month", False)], "Y": [(M, "Sessions", True)]}, accent=TEAL),
          visual("clusteredBarChart", 650, 210, 600, 250, "Sessions by country",
                 {"Category": [("dim_country", "country", False)], "Y": [(M, "Sessions", True)]}, accent=TEAL),
          visual("clusteredColumnChart", 30, 470, 500, 235, "Resolution rate by issue group",
                 {"Category": [("dim_issue_category", "issue_group", False)], "Y": [(M, "Resolution Rate", True)]}, accent=GREEN),
          visual("donutChart", 540, 470, 330, 235, "Sessions by delivery channel",
                 {"Category": [("dim_service_type", "delivery_channel", False)], "Y": [(M, "Sessions", True)]}),
          visual("tableEx", 880, 470, 370, 235, "Year on year",
                 {"Values": [("dim_date", "year", False), (M, "Sessions", True), (M, "Sessions YoY %", True),
                             (M, "Resolution Rate", True)]})]
    pages.append(page("Executive Overview", 0, v))

    v = header("Clinical risk and escalation",
               "How severe are cases, and do severe cases get resolved? Risk bands follow DimRiskLevel's score ranges.")
    v += cards([("Avg risk score", "Avg Risk Score", TEAL), ("High/critical sessions", "High/Critical Sessions", AMBER),
                ("Escalations", "Escalations", RED), ("Follow-up rate", "Follow-up Rate", TEAL),
                ("Resolution rate", "Resolution Rate", GREEN), ("Unresolved high/critical", "Unresolved High/Critical", RED)])
    v += [visual("clusteredColumnChart", 30, 210, 400, 250, "Sessions by risk level",
                 {"Category": [("dim_risk_level", "risk_level", False)], "Y": [(M, "Sessions", True)]}, accent=AMBER),
          visual("clusteredColumnChart", 440, 210, 400, 250, "Resolution rate by risk level",
                 {"Category": [("dim_risk_level", "risk_level", False)], "Y": [(M, "Resolution Rate", True)]}, accent=GREEN),
          visual("clusteredBarChart", 850, 210, 400, 250, "Escalation rate by issue category",
                 {"Category": [("dim_issue_category", "issue_category", False)], "Y": [(M, "Escalation Rate", True)]}, accent=RED),
          visual("pivotTable", 30, 470, 760, 235, "Resolution rate: issue group by risk level",
                 {"Rows": [("dim_issue_category", "issue_group", False)],
                  "Columns": [("dim_risk_level", "risk_level", False)], "Values": [(M, "Resolution Rate", True)]}),
          visual("tableEx", 800, 470, 450, 235, "Risk bands and the action each requires",
                 {"Values": [("dim_risk_level", "risk_level", False), ("dim_risk_level", "score_min", False),
                             ("dim_risk_level", "score_max", False), ("dim_risk_level", "recommended_action", False)]})]
    pages.append(page("Clinical Risk", 1, v))

    v = header("Clients and contracts",
               "Which corporate clients drive volume and revenue, and are outcomes different between them?")
    v += cards([("Revenue (ZAR)", "Revenue (ZAR)", TEAL), ("Revenue per session", "Revenue per Session", TEAL),
                ("Employees served", "Employees Served", TEAL), ("Sessions per employee", "Sessions per Employee", TEAL),
                ("Resolution rate", "Resolution Rate", GREEN), ("Medication sales (ZAR)", "Medication Sales (ZAR)", PURPLE)])
    v += [visual("clusteredBarChart", 30, 210, 610, 260, "Revenue by client",
                 {"Category": [("dim_client", "client", False)], "Y": [(M, "Revenue (ZAR)", True)]}, accent=TEAL),
          visual("clusteredColumnChart", 650, 210, 600, 260, "Sessions by contract package",
                 {"Category": [("dim_client", "contract_package", False)], "Y": [(M, "Sessions", True)]}, accent=PURPLE),
          visual("tableEx", 30, 480, 1220, 225, "Client scorecard",
                 {"Values": [("dim_client", "client", False), ("dim_client", "industry", False),
                             ("dim_client", "contract_package", False), (M, "Sessions", True), (M, "Employees Served", True),
                             (M, "Revenue (ZAR)", True), (M, "Revenue per Session", True), (M, "Resolution Rate", True),
                             (M, "Escalation Rate", True)]})]
    pages.append(page("Clients & Contracts", 2, v))

    v = header("Service delivery and capacity",
               "Service mix, counsellor caseload and where sessions are delivered. Facility locations are mapped "
               "in map.html; this page uses the city-derived province.")
    v += cards([("Active counsellors", "Active Counsellors", TEAL), ("Sessions per counsellor", "Sessions per Counsellor", RED),
                ("Avg session (min)", "Avg Session Minutes", TEAL), ("Facilities used", "Facilities Used", TEAL),
                ("Sessions per facility", "Sessions per Facility", TEAL), ("Follow-up rate", "Follow-up Rate", AMBER)])
    v += [visual("clusteredBarChart", 30, 210, 610, 260, "Sessions by service type",
                 {"Category": [("dim_service_type", "service_type", False)], "Y": [(M, "Sessions", True)]}, accent=TEAL),
          visual("clusteredColumnChart", 650, 210, 600, 260, "Sessions by facility type",
                 {"Category": [("dim_facility", "facility_type", False)], "Y": [(M, "Sessions", True)]}, accent=GREEN),
          visual("tableEx", 30, 480, 600, 225, "Counsellor caseload",
                 {"Values": [("dim_counsellor", "counsellor", False), ("dim_counsellor", "profession", False),
                             (M, "Sessions", True), (M, "Resolution Rate", True), (M, "Avg Session Minutes", True)]}),
          visual("tableEx", 640, 480, 610, 225, "Delivery by city",
                 {"Values": [("dim_facility", "city", False), ("dim_facility", "province", False),
                             (M, "Facilities Used", True), (M, "Sessions", True), (M, "Resolution Rate", True)]})]
    pages.append(page("Service Delivery", 3, v))

    v = header("Patient experience",
               "Survey feedback, 2022 only. Surveys are not linked to sessions, so experience cannot yet be tied to a "
               "counsellor or outcome. Net Promoter Score uses the 0–10 recommend score.")
    v += cards([("Survey responses", "Survey Responses", TEAL), ("Avg satisfaction (/10)", "Avg Satisfaction", TEAL),
                ("Net Promoter Score", "Net Promoter Score", RED), ("Would recommend", "Would Recommend Rate", AMBER),
                ("Complaint rate", "Complaint Rate", RED), ("Avg wait (min)", "Avg Wait Minutes", AMBER)])
    v += [visual("clusteredBarChart", 30, 210, 610, 260, "Satisfaction by service type",
                 {"Category": [("dim_service_type", "service_type", False)], "Y": [(M, "Avg Satisfaction", True)]}, accent=TEAL),
          visual("clusteredColumnChart", 650, 210, 600, 260, "Complaint rate and recommend rate by country",
                 {"Category": [("dim_country", "country", False)],
                  "Y": [(M, "Complaint Rate", True), (M, "Would Recommend Rate", True)]}),
          visual("lineChart", 30, 480, 610, 225, "Satisfaction by month",
                 {"Category": [("dim_date", "year_month", False)], "Y": [(M, "Avg Satisfaction", True)]}, accent=TEAL),
          visual("tableEx", 650, 480, 600, 225, "Experience by issue category",
                 {"Values": [("dim_issue_category", "issue_category", False), (M, "Survey Responses", True),
                             (M, "Avg Satisfaction", True), (M, "Avg Improvement", True), (M, "Complaint Rate", True)]})]
    pages.append(page("Patient Experience", 4, v))

    v = header("Medication and pharmacy",
               "Medication sales linked to corporate clients, October 2018 to October 2023, with the mental-health share.")
    v += cards([("Medication sales (ZAR)", "Medication Sales (ZAR)", PURPLE), ("Units sold", "Units Sold", PURPLE),
                ("Transactions", "Medication Transactions", PURPLE), ("Avg sale value", "Avg Sale Value", PURPLE),
                ("Mental-health medication", "Mental Health Medication Sales", TEAL),
                ("Mental-health share", "Mental Health Medication Share", TEAL)])
    v += [visual("clusteredBarChart", 30, 210, 610, 260, "Sales by therapeutic class",
                 {"Category": [("dim_medication", "therapeutic_class", False)], "Y": [(M, "Medication Sales (ZAR)", True)]}, accent=PURPLE),
          visual("lineChart", 650, 210, 600, 260, "Sales per month",
                 {"Category": [("dim_date", "year_month", False)], "Y": [(M, "Medication Sales (ZAR)", True)]}, accent=PURPLE),
          visual("clusteredColumnChart", 30, 480, 610, 225, "Sales by client",
                 {"Category": [("dim_client", "client", False)], "Y": [(M, "Medication Sales (ZAR)", True)]}, accent=PURPLE),
          visual("tableEx", 650, 480, 600, 225, "Top medications",
                 {"Values": [("dim_medication", "medication", False), ("dim_medication", "therapeutic_class", False),
                             (M, "Units Sold", True), (M, "Medication Sales (ZAR)", True)]})]
    pages.append(page("Medication", 5, v))

    v = header("Data quality and trust",
               "Checks run by export_data.py on every build. Each states the evidence, how many rows it affects and "
               "the fix at source. Figures elsewhere in the report should be read with these in mind.", slicers=False)
    v += cards([("Checks failing", "DQ Checks", RED), ("Under-18 sessions", "Under-18 Sessions", RED),
                ("Under-18 share", "Under-18 Share", RED), ("Facilities", "Facilities", TEAL),
                ("Province ≠ city", "Province Mismatches", AMBER), ("Province mismatch rate", "Province Mismatch Rate", AMBER)])
    v += [visual("tableEx", 30, 210, 1220, 300, "Data-quality checks",
                 {"Values": [("dq_check", "check_name", False), ("dq_check", "source_table", False),
                             ("dq_check", "affected_rows", False), ("dq_check", "population_rows", False),
                             ("dq_check", "evidence", False), ("dq_check", "remediation", False)]}),
          visual("clusteredColumnChart", 30, 520, 610, 185, "Sessions by recorded age band",
                 {"Category": [("fact_session", "age_band", False)], "Y": [(M, "Sessions", True)]}, accent=AMBER),
          textbox(650, 520, 600, 185, [
              [("Row-level security. ", HEAD)],
              [("The model ships a dynamic 'Country Manager' role: dim_country is filtered to the countries mapped to "
                "USERPRINCIPALNAME() in security_country_access, and the filter flows to sessions, surveys and "
                "medication sales. Test it in Desktop with Modeling > View as > Country Manager and an address "
                "such as za.manager@lyra-demo.example.", BODY)]])]
    pages.append(page("Data Quality", 6, v))

    v = header("Findings and recommendations",
               "Computed from the full dataset by export_data.py. The data is synthetic, so these show the analysis "
               "method rather than claims about a real programme.", slicers=False)
    v += cards([("Resolution rate", "Resolution Rate", GREEN), ("High/critical share", "High/Critical Share", AMBER),
                ("Complaint rate", "Complaint Rate", RED), ("Would recommend", "Would Recommend Rate", AMBER),
                ("Sessions per counsellor", "Sessions per Counsellor", RED), ("Under-18 share", "Under-18 Share", RED)])
    recs = [
        ("1  Build a stepped-care pathway for mental-health cases",
         f"Mental Health and Crisis issues are {pct(F['mental_share'])} of sessions and resolve at {pct(F['res_mental'])}, "
         f"against {pct(F['res_other'])} for all other issue groups. ",
         "Allocate longer session bundles and clinical supervision to these groups, and track resolution by issue group monthly."),
        ("2  Fix continuity for high and critical risk",
         f"High and critical cases are {pct(F['high_share'])} of sessions and resolve at {pct(F['res_high'])}, against "
         f"{pct(F['res_low'])} for low and medium. Every one already gets a follow-up, so more follow-ups are not the lever. ",
         "Keep the same counsellor across a case and measure time to resolution, not just follow-up completion."),
        ("3  Price contracts on clinical mix, not on client",
         f"Resolution varies only from {pct(F['res_client_min'])} to {pct(F['res_client_max'])} across the 16 clients: "
         "outcomes follow the issue and risk mix, not the employer. ",
         "Forecast contract cost from each client's expected issue and risk mix."),
        ("4  Set a waiting-time standard",
         f"{pct(F['complaint_rate'])} of 2022 survey respondents complained, only {pct(F['recommend_rate'])} would "
         f"recommend the service, and the average wait was {F['avg_wait']:.0f} minutes. ",
         "Introduce a wait-time SLA and link each survey to its session, so experience can be traced to a counsellor and outcome."),
        ("5  Repair identity and location data before scaling analytics",
         f"{F['under18']:,} sessions are recorded for people under 18, employee keys change gender and country, "
         "facility coordinates are invalid, and escalation is a copy of the Critical flag. ",
         "Fix these at source (Data Quality page) before any model or client report relies on them."),
    ]
    y = 210
    for head, finding, action in recs:
        v.append(textbox(30, y, 1220, 96, [[(head, HEAD)], [(finding, BODY), (action, ACT)]]))
        y += 100
    pages.append(page("Recommendations", 7, v))

    return {
        "id": 0,
        "resourcePackages": [{"resourcePackage": {"disabled": False, "items": [
            {"name": "LyraEAP", "path": "StaticResources/RegisteredResources/LyraEAP.json", "type": 202}],
            "name": "SharedResources", "type": 2}}],
        "sections": pages,
        "config": json.dumps({"version": "5.43",
                              "themeCollection": {"baseTheme": {"name": "CY24SU06", "version": "5.55", "type": 2},
                                                  "customTheme": {"name": "LyraEAP", "reportVersionAtImport": "5.43", "type": 2}},
                              "activeSectionIndex": 0, "defaultDrillFilterOtherVisuals": True,
                              "settings": {"useStylableVisualContainerHeader": True}}),
        "layoutOptimization": 0,
    }


def model_fields():
    tables = {}
    for f in (SM / "tables").glob("*.tmdl"):
        text = f.read_text(encoding="utf-8")
        tname = re.match(r"table\s+(\S+)", text).group(1)
        tables[tname] = (set(re.findall(r"^\tcolumn\s+(\S+)", text, re.M)),
                         set(re.findall(r"^\tmeasure\s+'([^']+)'", text, re.M)))
    return tables


def main():
    if not (SM / "tables").exists():
        raise SystemExit("semantic model not generated - run build_pbip.py first")
    tables, report, problems, checked = model_fields(), build(), [], 0

    for sec in report["sections"]:
        rects = []
        for i, vc in enumerate(sec["visualContainers"], 1):
            x, y, w, h = vc["x"], vc["y"], vc["width"], vc["height"]
            if x < 0 or y < 0 or x + w > W or y + h > H:
                problems.append(f"{sec['displayName']}: visual {i} is off the {W}x{H} canvas")
            for j, ox, oy, ow, oh in rects:
                if max(x, ox) < min(x + w, ox + ow) and max(y, oy) < min(y + h, oy + oh):
                    problems.append(f"{sec['displayName']}: visuals {j} and {i} overlap")
            rects.append((i, x, y, w, h))
            for sel in json.loads(vc["config"])["singleVisual"].get("prototypeQuery", {}).get("Select", []):
                kind = "Measure" if "Measure" in sel else "Column"
                tbl, prop = sel["Name"].split(".", 1)
                checked += 1
                cols, meas = tables.get(tbl, (set(), set()))
                if prop not in (meas if kind == "Measure" else cols):
                    problems.append(f"{sec['displayName']}: {tbl}[{prop}] is not a {kind.lower()} in the model")
    if problems:
        print("REPORT NOT WRITTEN:")
        for p in problems:
            print("  -", p)
        raise SystemExit(1)

    # Desktop upgrades a legacy report on save (definition/ folder, report.json
    # deleted). This report is generated, so clear those and re-assert legacy.
    for stale in ("definition", ".pbi"):
        target = RPT / stale
        if target.is_dir():
            shutil.rmtree(target)
    RPT.mkdir(parents=True, exist_ok=True)
    (RPT / "definition.pbir").write_text(
        '{\n  "version": "1.0",\n  "datasetReference": {\n    "byPath": { "path": "../' + NAME +
        '.SemanticModel" }\n  }\n}\n', encoding="utf-8")
    theme_dir = RPT / "StaticResources" / "RegisteredResources"
    theme_dir.mkdir(parents=True, exist_ok=True)
    (theme_dir / "LyraEAP.json").write_text(json.dumps(THEME, indent=2), encoding="utf-8")
    (RPT / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

    n = sum(len(s["visualContainers"]) for s in report["sections"])
    print(f"wrote {RPT.name}/report.json: {len(report['sections'])} pages, {n} visuals, "
          f"{checked} field references checked")


if __name__ == "__main__":
    main()
