param(
  [string]$LogPath = "../app.log",
  [string]$OutCsv = ""
)

function Extract-Durations($lines) {
  if (-not $lines) { return @() }
  $dur = @()
  foreach ($l in $lines) {
    if ($l -match "completed in ([0-9.]+)s") { $dur += [double]$matches[1] }
  }
  return $dur
}

function Get-Stats($arr) {
  if (-not $arr -or $arr.Count -eq 0) { return @{count=0;avg=0;p50=0;p95=0} }
  $sorted = $arr | Sort-Object
  $n = $sorted.Count
  $avg = ($sorted | Measure-Object -Average).Average
  $p50 = $sorted[[math]::Floor(0.50*($n-1))]
  $p95 = $sorted[[math]::Floor(0.95*($n-1))]
  return @{count=$n;avg=[math]::Round($avg,3);p50=[math]::Round($p50,3);p95=[math]::Round($p95,3)}
}

if (-not (Test-Path $LogPath)) {
  Write-Error "Log not found: $LogPath"
  exit 1
}

$nlpLines = Select-String -Path $LogPath -Pattern "nlp_parsing completed in"
$rankLines = Select-String -Path $LogPath -Pattern "recommendations completed in"
$schedLines = Select-String -Path $LogPath -Pattern "schedule_generation completed in"

$nlpDur = Extract-Durations $nlpLines
$rankDur = Extract-Durations $rankLines
$schedDur = Extract-Durations $schedLines

$nlpStats = Get-Stats $nlpDur
$rankStats = Get-Stats $rankDur
$schedStats = Get-Stats $schedDur

$rows = @(
  [pscustomobject]@{ Metric = 'Parse(NLP)'; Count=$nlpStats.count; Avg_s=$nlpStats.avg; P50_s=$nlpStats.p50; P95_s=$nlpStats.p95 },
  [pscustomobject]@{ Metric = 'Rank(Recs)'; Count=$rankStats.count; Avg_s=$rankStats.avg; P50_s=$rankStats.p50; P95_s=$rankStats.p95 },
  [pscustomobject]@{ Metric = 'Schedule';   Count=$schedStats.count; Avg_s=$schedStats.avg; P50_s=$schedStats.p50; P95_s=$schedStats.p95 }
)

if ($OutCsv -and $OutCsv.Trim().Length -gt 0) {
  $rows | Export-Csv -Path $OutCsv -NoTypeInformation -Encoding UTF8
  Write-Host "Metrics written to $OutCsv"
} else {
  # Print CSV to console
  "Metric,Count,Avg(s),P50(s),P95(s)"
  foreach ($r in $rows) {
    "$($r.Metric),$($r.Count),$($r.Avg_s),$($r.P50_s),$($r.P95_s)"
  }
}
