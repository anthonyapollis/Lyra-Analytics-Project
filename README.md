# Lyra Wellbeing Analytics — Data Warehouse Project

End-to-end dimensional data model for an employee wellbeing analytics platform, built on **Snowflake + SQL Server** with SCD Type 2 history tracking.

---

## Overview

| Metric | Value |
|--------|-------|
| Total rows (fact tables) | 1,438,293 |
| Dimension tables | 12 |
| Fact tables | 3 + 1 geography |
| Schema layers | DIM / FACT |
| SCD Type 2 tables | 2 (Employee, Consent) |
| Platforms | Snowflake · SQL Server |

---

## Data Model

```
DimDate ─┬─ FactCounsellingSessions ─ DimServiceType ─ DimIssueCategory
         │             ├── DimClientCompany ─ DimCountry ─ DimCurrency
         │             ├── DimFacilityGeography
         │             ├── DimCounsellor
         │             ├── DimEmployee_SCD2          ← SCD Type 2
         │             └── DimConsent_SCD2            ← SCD Type 2
         ├─ FactMedicationSales ─ DimMedication
         └─ FactPatientExperience ─ DimServiceType / DimIssueCategory
```

### Table Inventory

| Layer | Table | Rows | Columns |
|-------|-------|-----:|--------:|
| DIM | DimClientCompany | 16 | 12 |
| DIM | DimConsent_SCD2 | 475,840 | 11 |
| DIM | DimCounsellor | 12 | 8 |
| DIM | DimCountry | 5 | 9 |
| DIM | DimCurrency | 5 | 8 |
| DIM | DimDate | 3,652 | 10 |
| DIM | DimEmployee_SCD2 | 95,168 | 13 |
| DIM | DimIndustrySector | 14 | 3 |
| DIM | DimIssueCategory | 15 | 5 |
| DIM | DimMedication | 290 | 8 |
| DIM | DimRiskLevel | 4 | 5 |
| DIM | DimServiceType | 13 | 5 |
| FACT | DimFacilityGeography | 767 | 14 |
| FACT | FactCounsellingSessions | 668,293 | 45 |
| FACT | FactMedicationSales | 750,000 | 25 |
| FACT | FactPatientExperience | 20,000 | 34 |

---

## Repository Structure

```
Lyra-Analytics-Project/
├── data/
│   ├── dimensions/          # 12 dimension CSV files
│   └── facts/               # 3 fact tables + geography
├── sql/
│   ├── lyra_snowflake_ddl.sql          # Full Snowflake DDL
│   ├── lyra_sqlserver_ddl.sql          # SQL Server DDL variant
│   └── 01_Create_Lyra_Snowflake_Tables.sql
├── scripts/
│   ├── build_project_chunked.py        # Chunked data generation
│   ├── continue_project.py
│   └── finalise_project.py
├── docs/
│   └── Data_Model_and_Project_Guide.md
└── quality/
    ├── Data_Dictionary_Sample.csv
    ├── Generated_Table_Row_Counts.csv
    └── Source_Row_Counts.csv
```

---

## Key Design Decisions

- **DimClientCompany** — Lyra serves corporate clients; company is the top-level grain for EAP reporting.
- **DimServiceType** — Covers telephone counselling, in-person, work-life services, crisis support, coaching, digital and upskilling.
- **DimIssueCategory** — Mental health categories: depression, anxiety, burnout, trauma, stress, work conflict.
- **DimCountry / DimCurrency** — Multi-region support including ZAR (South Africa) and USD with FX conversion.
- **SCD Type 2** — `DimEmployee_SCD2` and `DimConsent_SCD2` track historical changes with `ValidFrom` / `ValidTo` / `IsCurrent` columns, preserving GDPR consent audit trails.

---

## Tech Stack

| Tool | Usage |
|------|-------|
| Snowflake | Primary cloud DW; COPY INTO, clustering, stages |
| SQL Server | On-prem variant DDL |
| Python | Data generation & project orchestration |
| CSV | Portable data layer for portability |

---

## Getting Started

**Snowflake:**
```sql
-- Run in order
\i sql/lyra_snowflake_ddl.sql
\i sql/01_Create_Lyra_Snowflake_Tables.sql
```

**Load dimensions first, then facts:**
```sql
COPY INTO DimDate FROM @lyra_stage/DimDate.csv ...;
-- ... repeat for all dimension tables
COPY INTO FactCounsellingSessions FROM @lyra_stage/FactCounsellingSessions.csv ...;
```

---

## Author

**Anthony Apollis** — Data Engineer & Analytics Specialist  
[GitHub](https://github.com/anthonyapollis) · [Portfolio](https://anthonyapollis.github.io)
