# Lyra Wellbeing Analytics Additional Data Model

This ZIP adds Lyra-relevant analytics tables to your supplied healthcare data without overwriting the source files. It uses the existing million-row outpatient and pharmacy datasets as the base for two large fact tables.

## Generated Tables

| Layer | Table | Rows | Columns |
|---|---|---:|---:|
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

## Data Model / ERD
```text
DimDate ─┬─ FactCounsellingSessions ─ DimServiceType ─ DimIssueCategory
         │             ├ DimClientCompany ─ DimCountry ─ DimCurrency
         │             ├ DimFacilityGeography
         │             ├ DimCounsellor
         │             ├ DimEmployee_SCD2
         │             └ DimConsent_SCD2
         ├─ FactMedicationSales ─ DimMedication
         └─ FactPatientExperience ─ DimServiceType / DimIssueCategory
```

## Why these tables were added
- `DimClientCompany`: Lyra is an employee wellbeing provider serving corporate clients.
- `DimServiceType`: maps telephone counselling, in-person counselling, work-life services, crisis support, coaching, digital solutions and upskilling.
- `DimIssueCategory`: adds mental health/wellbeing categories such as depression, anxiety, burnout, trauma, stress and work conflict.
- `DimCountry` and `DimCurrency`: keeps the US source context and adds South Africa plus other regions, with ZAR conversion.
- `DimEmployee_SCD2` and `DimConsent_SCD2`: demonstrates SCD Type 2 and privacy-aware modelling.

## Important note
The largest generated fact tables are:
- `FactCounsellingSessions`: 1,000,000 rows.
- `FactMedicationSales`: 1,000,000 rows.

`FactPatientExperience` remains at the source row count because the uploaded experience dataset contains 20,000 records.
