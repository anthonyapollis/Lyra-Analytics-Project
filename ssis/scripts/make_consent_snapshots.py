"""Build two consent snapshot files for the SSIS SCD Type 2 load, plus the expected result.

Day 1 (2024-01-01) is the current state in data/dimensions/DimConsent_SCD2_sample500.csv:
100 employees x 5 consent types = 500 rows.

Day 2 (2024-07-01) applies seeded, non-overlapping changes so the SCD2 outcome is known in advance:
  - 30 consent status changes   (Granted -> Withdrawn, Declined -> Granted)
  - 15 channel-only changes      (consent re-captured through another channel)
  -  2 employee relocations      (country changes on all 5 consent rows = 10 changes)
  - 10 new employees             (5 consent rows each = 50 new members)

ChangeReason is descriptive only; a version is created when CountryCode, ConsentStatus or
ConsentChannel changes.
"""
import csv
import json
import random
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
SAMPLE = REPO / "data" / "dimensions" / "DimConsent_SCD2_sample500.csv"
OUT = HERE.parent / "data"
FIELDS = ["EmployeeNaturalKey", "CountryCode", "ConsentType", "ConsentStatus", "ConsentChannel", "ChangeReason"]
CHANNELS = ["Mobile App", "Call Centre", "Web Portal", "HR Upload"]
COUNTRIES = ["US", "UK", "ZA", "CA", "AU"]
SEED = 7


def write(path: Path, rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, lineterminator="\r\n")
        w.writeheader()
        w.writerows(rows)


def main() -> None:
    rng = random.Random(SEED)
    with SAMPLE.open(encoding="utf-8") as f:
        day1 = [{k: r[k] for k in FIELDS} for r in csv.DictReader(f) if r["IsCurrent"] == "1"]
    day1.sort(key=lambda r: (r["EmployeeNaturalKey"], r["ConsentType"]))

    day2 = [dict(r) for r in day1]
    employees = sorted({r["EmployeeNaturalKey"] for r in day2})
    consent_types = sorted({r["ConsentType"] for r in day2})

    movers = rng.sample(employees, 2)
    for r in day2:
        if r["EmployeeNaturalKey"] in movers:
            r["CountryCode"] = rng.choice([c for c in COUNTRIES if c != r["CountryCode"]])
            r["ChangeReason"] = "Employee Relocation"

    others = [r for r in day2 if r["EmployeeNaturalKey"] not in movers]
    picked = rng.sample(others, 45)
    for r in picked[:30]:
        r["ConsentStatus"] = "Withdrawn" if r["ConsentStatus"] == "Granted" else "Granted"
        r["ChangeReason"] = "Consent Withdrawn" if r["ConsentStatus"] == "Withdrawn" else "Consent Granted"
    for r in picked[30:]:
        r["ConsentChannel"] = rng.choice([c for c in CHANNELS if c != r["ConsentChannel"]])
        r["ChangeReason"] = "Channel Update"

    for i in range(10):
        emp = f"EMP{9100000 + i:010d}"
        country = rng.choice(COUNTRIES)
        for ct in consent_types:
            day2.append({"EmployeeNaturalKey": emp, "CountryCode": country, "ConsentType": ct,
                         "ConsentStatus": rng.choice(["Granted", "Granted", "Granted", "Declined"]),
                         "ConsentChannel": rng.choice(CHANNELS), "ChangeReason": "Initial Consent"})

    OUT.mkdir(parents=True, exist_ok=True)
    write(OUT / "consent_snapshot_2024-01-01.csv", day1)
    write(OUT / "consent_snapshot_2024-07-01.csv", day2)

    changed = 10 + 30 + 15
    new = 50
    expected = {
        "after_day1": {"dim_rows": len(day1), "current_rows": len(day1), "expired_rows": 0},
        "after_day2": {"dim_rows": len(day1) + changed + new, "current_rows": len(day1) + new,
                       "expired_rows": changed, "new_members": new, "new_versions": changed,
                       "unchanged": len(day1) - changed},
        "after_day2_rerun": {"dim_rows": len(day1) + changed + new, "new_members": 0, "new_versions": 0},
    }
    (OUT / "expected_scd2_results.json").write_text(json.dumps(expected, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(expected, indent=2))


if __name__ == "__main__":
    main()
