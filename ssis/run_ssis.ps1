<#
.SYNOPSIS
  Point the Lyra SCD Type 2 package at a consent snapshot, run it, and check the dimension.

.DESCRIPTION
  -Snapshot <file> -SnapshotDate <yyyy-MM-dd>
      writes etl.Config (DataFolder = ssis\data, SnapshotFile, SnapshotDate). The package reads
      these when its SnapshotFile/SnapshotDate parameters are empty.
  -Run
      runs LYR_ConsentSCD2 from the built Lyra.ispac with DTExec. DTExec needs the SQL Server
      Integration Services feature; without it, run the package in Visual Studio instead
      (right-click LYR_ConsentSCD2.dtsx > Execute Package).
  always
      prints etl.PackageRun, dw.vw_DimConsentSummary and data\expected_scd2_results.json.

.EXAMPLE
  .\run_ssis.ps1 -Snapshot consent_snapshot_2024-01-01.csv -SnapshotDate 2024-01-01 -Run   # day 1: 500 rows
  .\run_ssis.ps1 -Snapshot consent_snapshot_2024-07-01.csv -SnapshotDate 2024-07-01 -Run   # day 2: 605 rows, 550 current
  .\run_ssis.ps1 -Run                                                                        # rerun day 2: no change
#>
param(
    [string]$Snapshot,
    [string]$SnapshotDate,
    [switch]$Run,
    [string]$Server = 'localhost',
    [string]$DTExec = 'C:\Program Files\Microsoft SQL Server\140\DTS\Binn\DTExec.exe'
)
$ErrorActionPreference = 'Stop'
$ssis = $PSScriptRoot

function Set-Config([string]$key, [string]$value) {
    $v = $value.Replace("'", "''")
    sqlcmd -S $Server -E -d LyraDW_SSIS -b -Q "MERGE etl.Config AS t USING (SELECT '$key' AS ConfigKey, N'$v' AS ConfigValue) AS s ON t.ConfigKey = s.ConfigKey WHEN MATCHED THEN UPDATE SET ConfigValue = s.ConfigValue, UpdatedAt = SYSDATETIME() WHEN NOT MATCHED THEN INSERT (ConfigKey, ConfigValue) VALUES (s.ConfigKey, s.ConfigValue);" | Out-Null
    Write-Host ("etl.Config {0,-12} = {1}" -f $key, $value)
}

if ($Snapshot) {
    if (-not $SnapshotDate) { throw '-SnapshotDate is required with -Snapshot' }
    Set-Config 'DataFolder' (Join-Path $ssis 'data')
    Set-Config 'SnapshotFile' $Snapshot
    Set-Config 'SnapshotDate' $SnapshotDate
}

if ($Run) {
    $ispac = Join-Path $ssis 'Lyra.SSIS\bin\Development\Lyra.ispac'
    if (-not (Test-Path $ispac)) { throw "Build the project first: $ispac not found" }
    & $DTExec /Project $ispac /Package LYR_ConsentSCD2.dtsx /Reporting EW
    Write-Host "DTExec exit code $LASTEXITCODE (0 = success)"
}

sqlcmd -S $Server -E -d LyraDW_SSIS -W -s " | " -Q "SET NOCOUNT ON; SELECT TOP 5 RunId, Status, RowsRead, RowsWritten, LEFT(Message, 160) AS Message FROM etl.PackageRun ORDER BY RunId DESC; SELECT * FROM dw.vw_DimConsentSummary;"
Write-Host "Expected:"; Get-Content (Join-Path $ssis 'data\expected_scd2_results.json')
