# Points the LyraEAP Power BI project at the data folder next to this script.
# Power Query's File.Contents needs an absolute path, so rerun this whenever the
# project folder is cloned, extracted or moved. Then open LyraEAP.pbip and click Refresh.
$ErrorActionPreference = 'Stop'
$dataRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot 'data')).Path
$expressions = Join-Path $PSScriptRoot 'LyraEAP.SemanticModel\definition\expressions.tmdl'
$required = 'fact_session','fact_experience','fact_medication','dim_date','dim_country','dim_client',
            'dim_facility','dim_service_type','dim_issue_category','dim_counsellor','dim_risk_level',
            'dim_medication','dq_check','security_country_access'
foreach ($t in $required) {
    if (!(Test-Path -LiteralPath (Join-Path $dataRoot "$t.parquet") -PathType Leaf)) { throw "Missing data file: $t.parquet" }
}
$text = [IO.File]::ReadAllText($expressions)
$updated = [regex]::Replace($text, '(?m)^expression DataFolder = "[^"]*"', {
    param($m) 'expression DataFolder = "' + $dataRoot.Replace('"', '""') + '"'
})
if ($updated -eq $text -and $text -notmatch [regex]::Escape($dataRoot)) { throw 'DataFolder expression not found' }
[IO.File]::WriteAllText($expressions, $updated, [Text.UTF8Encoding]::new($false))
Write-Host "DataFolder set to $dataRoot"
Write-Host 'Open LyraEAP.pbip and click Refresh.'
