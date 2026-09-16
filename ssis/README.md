# Lyra consent dimension: SCD Type 2 in SSIS, generated from Biml

The Snowflake warehouse models consent as `DIMCONSENT_SCD2`. This folder maintains that history on SQL Server
with an SSIS package generated from [one Biml file](Lyra.SSIS/Lyra_SSIS.biml), fed by daily consent snapshots.

## How the package works

```
snapshot CSV ──► stg.ConsentSnapshot ──► hash(CountryCode | ConsentStatus | ConsentChannel)
                                          │
                     Lookup current version on (EmployeeNaturalKey, ConsentType)
                     ├─ no match ─────────────► insert new member   (effective from snapshot date, IsCurrent = 1)
                     ├─ match, hash differs ──► stg.ConsentChanged
                     └─ match, hash equal ────► counted only
                                          │
     one transaction: expire the changed versions (effective to = snapshot date − 1, IsCurrent = 0)
                      and insert their new versions
```

- **Tracked attributes** (a change creates a version): `CountryCode`, `ConsentStatus`, `ConsentChannel`.
  `ChangeReason` describes a version and never creates one on its own.
- The database enforces the Type 2 rule itself: a filtered unique index allows **one current row** per
  employee and consent type.
- **Idempotent.** Loading the same snapshot again changes nothing, because every row matches its current version.
- The snapshot to load comes from the `SnapshotFile` / `SnapshotDate` parameters, or from `etl.Config`.
  Every run is logged to `etl.PackageRun` with new members, new versions and unchanged counts.

## Test: known changes in, known history out

[`scripts/make_consent_snapshots.py`](scripts/make_consent_snapshots.py) builds day 1 from the repo's
500-row consent sample (100 employees × 5 consent types) and a seeded day 2 with changes that do not overlap:
30 consent status changes, 15 channel changes, 2 relocations (10 rows) and 10 new employees (50 rows).
The expected outcome is written to [`data/expected_scd2_results.json`](data/expected_scd2_results.json)
**before** the package runs.

Results from `etl.PackageRun` and `dw.vw_DimConsentSummary` (SQL Server 2017, 16 September 2026):

| Run | Snapshot rows | New members | New versions | Unchanged | Dimension rows | Current | Expired | Expected |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| Day 1 (2024-01-01) | 500 | 500 | 0 | 0 | 500 | 500 | 0 | match |
| Day 2 (2024-07-01) | 550 | 50 | 55 | 445 | 605 | 550 | 55 | match |
| Day 2 again | 550 | 0 | 0 | 550 | 605 | 550 | 55 | match (no-op) |

Integrity checks after the rerun: **0** keys with more than one current version, **0** overlapping validity periods.

One employee's history after day 2, showing a withdrawn research consent:

| ConsentType | ConsentStatus | ChangeReason | EffectiveFrom | EffectiveTo | IsCurrent |
|---|---|---|---|---|---|
| Research | Granted | Initial Consent | 2024-01-01 | 2024-06-30 | 0 |
| Research | Withdrawn | Consent Withdrawn | 2024-07-01 | 9999-12-31 | 1 |
| Analytics | Granted | Initial Consent | 2024-01-01 | 9999-12-31 | 1 |

## Run it

```powershell
sqlcmd -S localhost -E -i ssis\sql\00_setup_LyraDW_SSIS.sql
python ssis\scripts\make_consent_snapshots.py
```

1. Open `ssis\Lyra.SSIS.sln` in Visual Studio with SSDT and BimlExpress. Right-click `Lyra_SSIS.biml` → **Generate SSIS Packages**.
2. `.\ssis\run_ssis.ps1 -Snapshot consent_snapshot_2024-01-01.csv -SnapshotDate 2024-01-01`, then execute `LYR_ConsentSCD2.dtsx`.
3. `.\ssis\run_ssis.ps1 -Snapshot consent_snapshot_2024-07-01.csv -SnapshotDate 2024-07-01`, then execute it again (and once more to show the rerun changes nothing).
4. `.\ssis\run_ssis.ps1` prints the run log, the dimension summary and the expected results side by side.

Add `-Run` to use DTExec where the SQL Server Integration Services feature is installed.
