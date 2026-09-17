# Lyra EAP — Power BI report

A Power BI project (PBIP) generated from the warehouse data. It has 8 pages, 109 visuals, 44 DAX measures, a star schema across three fact tables, and dynamic row-level security.

## Open it

1. Right-click `Setup-DataPaths.ps1` and choose **Run with PowerShell**. This points the `DataFolder` parameter at `powerbi/data` on your machine.
2. Open `LyraEAP.pbip` in Power BI Desktop and click **Refresh**. The load takes about a minute: 668K sessions and 750K medication sales.

## Rebuild it

```bash
python powerbi/export_data.py    # warehouse CSVs -> typed Parquet, data-quality checks, findings.json
python powerbi/build_pbip.py     # semantic model (TMDL)
python powerbi/build_report.py   # report pages; every field and layout is checked before writing
```

`export_data.py` reads the full fact CSVs in `data/facts`. They exceed GitHub's file limit, so regenerate them with `scripts/build_project_chunked.py` first. The Parquet files committed in `powerbi/data` are enough to open and refresh the report.

## Pages

| Page | Answers |
|---|---|
| Executive Overview | Volume, reach, revenue and outcomes by month, country, issue group and channel; year-on-year change |
| Clinical Risk | How severe cases are, and whether high and critical cases get resolved |
| Clients & Contracts | Revenue and outcomes per corporate client and contract package |
| Service Delivery | Service mix, counsellor caseload, delivery by city |
| Patient Experience | Satisfaction, Net Promoter Score, complaints and waiting time (2022 surveys) |
| Medication | Pharmacy sales by therapeutic class and client, with the mental-health share |
| Data Quality | Eight checks with evidence, affected rows and the fix at source |
| Recommendations | Five actions, each quoting figures computed by `export_data.py` |

## Model

- **Facts:** `fact_session`, `fact_experience`, `fact_medication`.
- **Conformed dimensions:** date (a marked date table), country, client, service type and issue category.
- **Other dimensions:** facility, counsellor, risk level, medication.
- **Relationships:**
  - Dimension-to-fact links are single direction.
  - `dim_client → dim_country` and `dim_facility → dim_country` are inactive, so country filters take exactly one path.
- **Measures:** all sit on `_Measures`, grouped into display folders: Sessions, Clinical, Capacity, Experience, Medication and Data Quality.
- **Row-level security:** the `Country Manager` role filters `dim_country` to the countries mapped to `USERPRINCIPALNAME()` in `security_country_access`, and the filter flows to all three facts. To test it, go to **Modeling → View as → Country Manager** and enter `za.manager@lyra-demo.example`. Expect 133,440 sessions.

## Verified

The model was loaded and refreshed in Power BI Desktop, and its measures were queried against DuckDB over the same Parquet files. These figures match:

| Measure | Value |
|---|---|
| Sessions | 668,293 |
| Resolution rate | 61.6% |
| High/critical share | 44.5% |
| Revenue | R25.74bn |
| Employees served | 487,844 |
| Net Promoter Score | −59.5 |
| Mental-health medication share | 15.1% |
| Under-18 sessions | 132,426 |
| Province mismatches | 589 |
| Sessions per year (2018–2022) | match |
| Year-on-year change | matches |
| RLS lookup for the ZA manager | returns only ZA |

The data is synthetic. The Data Quality page lists where it is not credible, so the findings demonstrate the method rather than describe a real programme.
