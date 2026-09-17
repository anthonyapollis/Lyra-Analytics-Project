#!/usr/bin/env python3
"""Exports the Lyra warehouse CSVs to typed Parquet for the Power BI model.

Power BI reads these files, so the report is one refresh away from the data in
data/. The export also runs the data-quality checks and computes the findings
the report quotes, so no number on a page is typed by hand.

    python powerbi/export_data.py
"""
from __future__ import annotations

import json
from pathlib import Path

import duckdb

REPO = Path(__file__).resolve().parent.parent
FACTS = REPO / "data" / "facts"
DIMS = REPO / "data" / "dimensions"
OUT = REPO / "powerbi" / "data"

# City -> the province/state that actually contains it. DimFacilityGeography's
# ProvinceState disagrees with its City in most rows; City agrees with country.
CITY_PROVINCE = {
    "Cape Town": "Western Cape", "Durban": "KwaZulu-Natal", "Johannesburg": "Gauteng",
    "Pretoria": "Gauteng", "Bloemfontein": "Free State", "Seattle": "Washington",
    "New York": "New York", "Miami": "Florida", "Los Angeles": "California", "Austin": "Texas",
    "Cardiff": "Wales", "Manchester": "England", "Belfast": "Northern Ireland",
    "London": "England", "Edinburgh": "Scotland", "Ottawa": "Ontario",
    "Vancouver": "British Columbia", "Toronto": "Ontario", "Calgary": "Alberta",
    "Montreal": "Quebec", "Perth": "Western Australia", "Melbourne": "Victoria",
    "Sydney": "New South Wales", "Adelaide": "South Australia", "Brisbane": "Queensland",
}


def csv(path: Path) -> str:
    return f"read_csv_auto('{path.as_posix()}', header=true, sample_size=-1)"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    sessions = csv(FACTS / "FactCounsellingSessions.csv")
    city_map = " ".join(f"when '{c}' then '{p}'" for c, p in CITY_PROVINCE.items())

    queries = {
        "fact_session": f"""
            select SessionKey as session_key, cast(Visit_Date as date) as visit_date,
                   EmployeeNaturalKey as employee_key, Age as age,
                   case when Age < 18 then 'Under 18' when Age < 25 then '18-24'
                        when Age < 35 then '25-34' when Age < 45 then '35-44'
                        when Age < 55 then '45-54' when Age < 65 then '55-64' else '65+' end as age_band,
                   case when Age < 18 then 1 when Age < 25 then 2 when Age < 35 then 3 when Age < 45 then 4
                        when Age < 55 then 5 when Age < 65 then 6 else 7 end as age_band_sort,
                   Gender as gender, CountryCode as country_code,
                   ClientCompanyKey as client_key, FacilityKey as facility_key,
                   ServiceTypeKey as service_type_key, IssueCategoryKey as issue_category_key,
                   CounsellorKey as counsellor_key, RiskLevel as risk_level,
                   SessionDurationMinutes as duration_minutes, RiskScore as risk_score,
                   FollowUpRequiredFlag as follow_up_flag, EmergencyEscalationFlag as escalation_flag,
                   CaseResolvedFlag as resolved_flag, SessionCount as session_count,
                   RevenueAmountZAR as revenue_zar
            from {sessions}""",
        "dim_date": f"""
            select cast(FullDate as date) as calendar_date, Year as year, Quarter as quarter,
                   'Q' || Quarter as quarter_label, Month as month_number, MonthName as month_name,
                   left(MonthName, 3) as month_short,
                   cast(date_trunc('month', cast(FullDate as date)) as date) as month_start,
                   Year * 100 + Month as year_month_sort,
                   strftime(cast(FullDate as date), '%Y-%m') as year_month,
                   DayName as day_name, IsWeekend as is_weekend
            from {csv(DIMS / 'DimDate.csv')}""",
        "dim_country": f"""
            select CountryCode as country_code, CountryName as country, GlobalRegion as region,
                   CurrencyCode as currency_code, PrivacyRegime as privacy_regime
            from {csv(DIMS / 'DimCountry.csv')}""",
        "dim_client": f"""
            select ClientCompanyKey as client_key, ClientCompanyName as client,
                   IndustrySectorName as industry, CountryCode as client_country_code,
                   ContractPackage as contract_package, ContractStatus as contract_status,
                   cast(ContractStartDate as date) as contract_start, cast(ContractEndDate as date) as contract_end
            from {csv(DIMS / 'DimClientCompany.csv')}""",
        "dim_service_type": f"""
            select ServiceTypeKey as service_type_key, ServiceTypeName as service_type,
                   ServiceCategory as service_category, DeliveryChannel as delivery_channel
            from {csv(DIMS / 'DimServiceType.csv')}""",
        "dim_issue_category": f"""
            select IssueCategoryKey as issue_category_key, IssueCategoryName as issue_category,
                   IssueGroup as issue_group, DefaultRiskLevel as default_risk_level
            from {csv(DIMS / 'DimIssueCategory.csv')}""",
        "dim_counsellor": f"""
            select CounsellorKey as counsellor_key, CounsellorName as counsellor, Profession as profession,
                   PrimaryLanguage as primary_language, Specialisation as specialisation,
                   AccreditedFlag as accredited_flag
            from {csv(DIMS / 'DimCounsellor.csv')}""",
        "dim_risk_level": f"""
            select RiskLevel as risk_level, RiskLevelKey as risk_sort, RiskScoreMin as score_min,
                   RiskScoreMax as score_max, RecommendedAction as recommended_action
            from {csv(DIMS / 'DimRiskLevel.csv')}""",
        "dim_facility": f"""
            select FacilityKey as facility_key, 'Facility ' || FacilityKey as facility,
                   LyraFacilityType as facility_type, "Facility Type" as site_category,
                   CountryCode as facility_country_code, City as city,
                   case City {city_map} end as province,
                   ProvinceState as recorded_province,
                   case when (case City {city_map} end) = ProvinceState then 1 else 0 end as province_matches_city,
                   ActiveFlag as active_flag
            from {csv(FACTS / 'DimFacilityGeography.csv')}""",
        "fact_experience": f"""
            select ExperienceKey as experience_key, cast(Feedback_Date as date) as feedback_date,
                   CountryCode as country_code, ServiceTypeKey as service_type_key,
                   IssueCategoryKey as issue_category_key, SatisfactionScore as satisfaction_score,
                   NetPromoterScore as recommend_score, StaffRating10 as staff_rating,
                   SpeedRating10 as speed_rating, Wait_Time_minutes as wait_minutes,
                   OutcomeBeforeScore as outcome_before, OutcomeAfterScore as outcome_after,
                   ImprovementScore as improvement_score, WouldRecommendFlag as would_recommend_flag,
                   ComplaintFlag as complaint_flag
            from {csv(FACTS / 'FactPatientExperience.csv')}""",
        "fact_medication": f"""
            select MedicationSalesKey as medication_sale_key, cast(Date_Sold as date) as sale_date,
                   CountryCode as country_code, ClientCompanyKey as client_key,
                   MedicationKey as medication_key, Quantity_Sold as units,
                   MedicationSalesAmountZAR as sales_zar, PrescriptionRequiredFlag as prescription_flag,
                   TreatmentType as treatment_type
            from {csv(FACTS / 'FactMedicationSales.csv')}""",
        "dim_medication": f"""
            select MedicationKey as medication_key, MedicationName as medication,
                   trim(TherapeuticClass) as therapeutic_class, Strength as strength,
                   MentalHealthMedicationFlag as mental_health_flag
            from {csv(DIMS / 'DimMedication.csv')}""",
    }

    total = 0.0
    for name, sql in queries.items():
        dest = OUT / f"{name}.parquet"
        con.sql(f"copy ({sql}) to '{dest.as_posix()}' (format parquet, compression zstd)")
        con.sql(f"create or replace view {name} as select * from read_parquet('{dest.as_posix()}')")
        rows = con.sql(f"select count(*) from {name}").fetchone()[0]
        mb = dest.stat().st_size / 1024 / 1024
        total += mb
        print(f"  {name:<22}{rows:>10,} rows {mb:>7.1f} MB")

    # Dynamic row-level security mapping: which user may see which country.
    # Demo accounts only; the report's 'Country Manager' role reads this table.
    con.sql(f"""copy (select * from (values
        ('za.manager@lyra-demo.example', 'ZA'), ('uk.manager@lyra-demo.example', 'UK'),
        ('us.manager@lyra-demo.example', 'US'), ('global.lead@lyra-demo.example', 'ZA'),
        ('global.lead@lyra-demo.example', 'UK'), ('global.lead@lyra-demo.example', 'US'),
        ('global.lead@lyra-demo.example', 'CA'), ('global.lead@lyra-demo.example', 'AU'))
        t(user_email, country_code)) to '{(OUT / 'security_country_access.parquet').as_posix()}'
        (format parquet)""")

    one = lambda sql: con.sql(sql).fetchone()[0]
    n_sessions = one("select count(*) from fact_session")
    checks = [
        ("Facility coordinates outside their country", "DimFacilityGeography",
         one("select count(*) from read_csv_auto('" + (FACTS / 'DimFacilityGeography.csv').as_posix() +
             "') where Latitude between 4 and 14 and Longitude between 3 and 15"),
         one("select count(*) from dim_facility"),
         "Every latitude is 4-14 and every longitude 3-15, a box in the Gulf of Guinea, for facilities recorded in South Africa, the US, UK, Canada and Australia.",
         "Re-geocode from address or city and add a test that each point falls inside its country."),
        ("Recorded province does not contain the city", "DimFacilityGeography",
         one("select count(*) from dim_facility where province_matches_city = 0"),
         one("select count(*) from dim_facility"),
         "For example, Pretoria recorded in the Western Cape. City agrees with country, so the model derives province from city.",
         "Constrain ProvinceState to a city-to-province lookup at load."),
        ("Session for a person under 18", "FactCounsellingSessions",
         one("select count(*) from fact_session where age < 18"), n_sessions,
         "An employee assistance programme serves employees, yet ages run from 0.",
         "Validate age against employment records; quarantine rows under 18 until confirmed."),
        ("Employee recorded with more than one gender", "FactCounsellingSessions",
         one("select count(*) from (select employee_key from fact_session group by 1 having count(distinct gender) > 1)"),
         one("select count(distinct employee_key) from fact_session"),
         "The same EmployeeNaturalKey carries different genders across sessions, so the key is not a stable identity.",
         "Take demographics from DimEmployee_SCD2 as of the session date instead of copying them onto the fact."),
        ("Employee recorded in more than one country", "FactCounsellingSessions",
         one("select count(*) from (select employee_key from fact_session group by 1 having count(distinct country_code) > 1)"),
         one("select count(distinct employee_key) from fact_session"),
         "Employee keys are reused across countries and clients.",
         "Make the employee key client-scoped, or add a survivorship rule for genuine transfers."),
        ("Escalation is a copy of the Critical risk flag", "FactCounsellingSessions",
         one("select count(*) from fact_session where (risk_level = 'Critical') = (escalation_flag = 1)"), n_sessions,
         "Every Critical session is escalated and no other session is, so escalation adds no information and any model predicting it is trivially perfect.",
         "Record the escalation decision independently of the risk band so escalation quality can be measured."),
        ("Counsellor caseload not credible", "DimCounsellor",
         one("select count(distinct counsellor_key) from fact_session"), 12,
         f"{n_sessions:,} sessions are attributed to 12 counsellors, about {n_sessions // 12 // 5:,} each per year.",
         "Load the full counsellor register, including associate and network counsellors."),
        ("Patient experience covers one year only", "FactPatientExperience",
         one("select count(*) from fact_experience"), one("select count(*) from fact_experience"),
         "Feedback runs from " + str(one("select min(feedback_date) from fact_experience")) + " to " +
         str(one("select max(feedback_date) from fact_experience")) + ", while sessions cover 2018-2022, and feedback does not link to a session.",
         "Capture SessionKey on each survey so experience can be tied to service, counsellor and outcome."),
    ]
    dq_rows = ",".join(
        "(" + ",".join([str(i + 1), repr(n), repr(t), str(int(a)), str(int(d)), repr(e), repr(f)]) + ")"
        for i, (n, t, a, d, e, f) in enumerate(checks))
    con.sql(f"""copy (select * from (values {dq_rows})
        t(check_order, check_name, source_table, affected_rows, population_rows, evidence, remediation))
        to '{(OUT / 'dq_check.parquet').as_posix()}' (format parquet)""")
    print(f"  {'dq_check':<22}{len(checks):>10,} rows")
    print(f"  {'TOTAL':<22}{'':>10} {total:>9.1f} MB")

    # Findings quoted on the Recommendations page, computed rather than typed.
    f = {}
    f["sessions"] = n_sessions
    f["res_mental"] = one("select avg(resolved_flag) from fact_session s join dim_issue_category i using (issue_category_key) where issue_group in ('Mental Health','Crisis')")
    f["res_other"] = one("select avg(resolved_flag) from fact_session s join dim_issue_category i using (issue_category_key) where issue_group not in ('Mental Health','Crisis')")
    f["mental_share"] = one("select avg(case when issue_group in ('Mental Health','Crisis') then 1 else 0 end) from fact_session s join dim_issue_category i using (issue_category_key)")
    f["res_high"] = one("select avg(resolved_flag) from fact_session where risk_level in ('High','Critical')")
    f["res_low"] = one("select avg(resolved_flag) from fact_session where risk_level in ('Low','Medium')")
    f["high_share"] = one("select avg(case when risk_level in ('High','Critical') then 1 else 0 end) from fact_session")
    f["res_client_min"] = one("select min(r) from (select avg(resolved_flag) r from fact_session group by client_key)")
    f["res_client_max"] = one("select max(r) from (select avg(resolved_flag) r from fact_session group by client_key)")
    f["under18"] = one("select count(*) from fact_session where age < 18")
    f["complaint_rate"] = one("select avg(complaint_flag) from fact_experience")
    f["recommend_rate"] = one("select avg(would_recommend_flag) from fact_experience")
    f["avg_wait"] = one("select avg(wait_minutes) from fact_experience")
    f["mh_med_share"] = one("select sum(case when m.mental_health_flag = 1 then sales_zar end) / sum(sales_zar) from fact_medication s join dim_medication m using (medication_key)")
    (OUT / "findings.json").write_text(json.dumps({k: (round(v, 6) if isinstance(v, float) else v) for k, v in f.items()}, indent=2), encoding="utf-8")
    print("  findings.json written")


if __name__ == "__main__":
    main()
