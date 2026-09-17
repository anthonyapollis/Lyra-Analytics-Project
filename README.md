<div align="center">

# Lyra Wellbeing Analytics — Data Warehouse

![Snowflake](https://img.shields.io/badge/Snowflake-29B5E8?style=for-the-badge&logo=snowflake&logoColor=white)
![SQL Server](https://img.shields.io/badge/SQL_Server-CC2927?style=for-the-badge&logo=microsoftsqlserver&logoColor=white)
![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Star Schema](https://img.shields.io/badge/Star_Schema-10B981?style=for-the-badge)
![SCD Type 2](https://img.shields.io/badge/SCD_Type_2-8B5CF6?style=for-the-badge)

**Production-grade dimensional data warehouse for an employee wellbeing analytics platform.**  
Designed for Lyra-style EAP (Employee Assistance Programme) reporting across corporate clients.

</div>

> **SCD Type 2 in SSIS.** The consent dimension's history is also maintained on SQL Server by an SSIS package
> generated from Biml. It hashes the tracked attributes, looks up the current version, then expires and inserts
> in one transaction. Tested with known day-1 and day-2 snapshots: 500 → 605 rows (550 current, 55 expired),
> as predicted in advance, and rerunning the same snapshot changes nothing. See [`ssis/`](ssis/README.md).

---

## ⚡ At a Glance

| | |
|--|--|
| 🏗 **16 tables** (12 dim · 3 fact · 1 geo) | 📊 **1.4M+** total rows |
| 🔄 **SCD Type 2** on Employee & Consent | 🌍 **Multi-region** ZAR + USD currency |
| 🏢 **Corporate EAP** client model | 🏥 **Mental health** issue categorisation |

---

## 🗂 Data Model

```
DimDate ─┬─ FactCounsellingSessions ─── DimServiceType ─ DimIssueCategory
         │             ├── DimClientCompany ─── DimCountry ─ DimCurrency
         │             ├── DimFacilityGeography
         │             ├── DimCounsellor
         │             ├── DimEmployee_SCD2       ◄ SCD Type 2
         │             └── DimConsent_SCD2         ◄ SCD Type 2 (GDPR audit trail)
         ├─ FactMedicationSales ────────── DimMedication
         └─ FactPatientExperience ──────── DimServiceType / DimIssueCategory
```

---

## 📐 Table Inventory

| Layer | Table | Rows | Purpose |
|-------|-------|-----:|---------|
| DIM | DimClientCompany | 16 | Corporate EAP clients |
| DIM | DimConsent_SCD2 | 475,840 | GDPR consent audit trail (SCD2) |
| DIM | DimCounsellor | 12 | Therapist/counsellor register |
| DIM | DimCountry | 5 | SA + international regions |
| DIM | DimCurrency | 5 | ZAR · USD with FX conversion |
| DIM | DimDate | 3,652 | 10-year date spine |
| DIM | DimEmployee_SCD2 | 95,168 | Employee history (SCD2) |
| DIM | DimIndustrySector | 14 | Client industry classification |
| DIM | DimIssueCategory | 15 | Mental health categories |
| DIM | DimMedication | 290 | Medication formulary |
| DIM | DimRiskLevel | 4 | Risk stratification |
| DIM | DimServiceType | 13 | Counselling, coaching, crisis, digital |
| FACT | DimFacilityGeography | 767 | Facility locations |
| FACT | FactCounsellingSessions | 668,293 | Core EAP sessions fact |
| FACT | FactMedicationSales | 750,000 | Pharmacy / medication transactions |
| FACT | FactPatientExperience | 20,000 | Patient satisfaction scores |

> **Note:** Full fact table CSVs (238MB–750MB) exceed GitHub's file limit.  
> 500-row samples are included. Run `scripts/build_project_chunked.py` to regenerate full datasets locally.

---

## 📊 Power BI Report

[`powerbi/`](powerbi/README.md) holds a generated Power BI project (PBIP). It has 8 pages: executive overview, clinical risk, clients, service delivery, patient experience, medication, data quality and recommendations. Behind them sit 44 DAX measures across three fact tables and a dynamic row-level-security role. Its measures were checked in Power BI Desktop against DuckDB over the same data.

---

## 🗺 Facility Intelligence Map

[`map.html`](map.html) is generated from the warehouse by `python scripts/build_facility_map.py` (edit `scripts/facility_map_template.html`, then rebuild). It aggregates all 668,293 sessions into a facility × year × client cube, so every figure on the page comes from the data.

- **Explore:** filter by country, city, year range, corporate client and facility type. Colour by type, sessions, escalation rate, resolution rate or high/critical risk. Toggle clustering, a session heatmap and city totals. Rank facilities, then download the filtered set as CSV.
- **Nearest:** click the map, or use your location, to find the closest matching facilities.
- **Coverage:** set a service radius to see which South African towns without a facility fall outside it.
- **Data quality:** DimFacilityGeography's coordinates fail validation: every facility sits between 4 and 14 degrees, whatever its country. In 85% of South African rows, the recorded province does not contain the recorded city. The map places facilities at their city centre, explains why on the page, and lists the fixes needed at source.

---

## 📁 Repo Structure

```
Lyra-Analytics-Project/
├── data/
│   ├── dimensions/          # All 12 dimension CSVs (full size)
│   └── facts/               # 500-row samples + DimFacilityGeography
├── sql/
│   ├── lyra_snowflake_ddl.sql          # Full Snowflake DDL
│   ├── lyra_sqlserver_ddl.sql          # SQL Server variant
│   └── 01_Create_Lyra_Snowflake_Tables.sql
├── scripts/
│   └── build_project_chunked.py        # Generates full fact tables
├── docs/
│   └── Data_Model_and_Project_Guide.md # ERD + design decisions
└── quality/
    ├── Data_Dictionary_Sample.csv
    └── Generated_Table_Row_Counts.csv
```

---

## 🔑 Key Design Decisions

| Decision | Reason |
|----------|--------|
| **SCD Type 2 on DimEmployee** | Tracks job role / department changes over time for trend analysis |
| **SCD Type 2 on DimConsent** | Full GDPR-compliant audit trail of consent changes |
| **DimClientCompany grain** | Lyra is B2B — corporate client is the top reporting level |
| **DimIssueCategory** | Enables burnout / anxiety / depression trend reporting by client |
| **Multi-currency** | Supports South Africa (ZAR) and US (USD) in same model |

---

<div align="center">

[![Full Portfolio](https://img.shields.io/badge/Full_Portfolio-anthonyapollis.github.io-3B82F6?style=for-the-badge)](https://anthonyapollis.github.io)
[![GitHub Profile](https://img.shields.io/badge/GitHub_Profile-anthonyapollis-181717?style=for-the-badge&logo=github)](https://github.com/anthonyapollis)

**Anthony Apollis · Data Engineer & Analytics Specialist · South Africa**

</div>
