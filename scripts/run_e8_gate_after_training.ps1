param(
    [int]$TrainingPid = 0,
    [string]$Weights = "runs\train\expanded-ppe-yolov8s-e8-video150\weights\best.pt",
    [int]$MinimumEpoch = 20
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$ResultsDir = Join-Path $ProjectRoot "results"
$SummaryPath = Join-Path $ResultsDir "e8-video150-gate-summary.json"
$LogPath = Join-Path $ResultsDir "e8-video150-gate.log"
New-Item -ItemType Directory -Force -Path $ResultsDir | Out-Null

function Write-Log([string]$Message) {
    Add-Content -Path $LogPath -Value ("{0} {1}" -f (Get-Date -Format o), $Message)
}

function Save-Summary {
    $script:Summary | ConvertTo-Json -Depth 10 | Set-Content -Path $SummaryPath -Encoding UTF8
}

if ($TrainingPid -gt 0) {
    $training = Get-Process -Id $TrainingPid -ErrorAction SilentlyContinue
    if ($training) {
        Write-Log "Waiting for training PID $TrainingPid to exit"
        Wait-Process -Id $TrainingPid -ErrorAction SilentlyContinue
        Write-Log "Training process exited"
    }
}

$csvPath = Join-Path $ProjectRoot "runs\train\expanded-ppe-yolov8s-e8-video150\results.csv"
$rows = if (Test-Path $csvPath) { Import-Csv $csvPath } else { @() }
$last = $rows | Select-Object -Last 1
$lastEpoch = if ($last) { [int]$last.epoch } else { -1 }

$script:Summary = [ordered]@{
    generated_at = (Get-Date).ToString("o")
    last_epoch = $lastEpoch
    weights = $Weights
    deployed = $false
    status = $null
    commands = @()
    outputs = @()
}

if ($lastEpoch -lt $MinimumEpoch) {
    $script:Summary.status = "blocked_training_incomplete"
    $script:Summary.reason = "results.csv did not reach the minimum epoch gate"
    Save-Summary
    Write-Log "Blocked: last_epoch=$lastEpoch minimum_epoch=$MinimumEpoch"
    exit 2
}

if (-not (Test-Path $Weights)) {
    $script:Summary.status = "blocked_weights_missing"
    $script:Summary.reason = "E8 best.pt was not found"
    Save-Summary
    Write-Log "Blocked: missing weights $Weights"
    exit 2
}

function Invoke-Gate {
    param(
        [string]$Name,
        [string[]]$Arguments
    )
    $outputPath = Join-Path $ResultsDir ("e8-video150-{0}.stdout.log" -f $Name)
    Write-Log "Running $Name"
    & $Python @Arguments *> $outputPath
    $code = $LASTEXITCODE
    $script:Summary.commands += $Name
    $script:Summary.outputs += [ordered]@{
        name = $Name
        exit_code = $code
        output = $outputPath
    }
    if ($code -ne 0) {
        $script:Summary.status = "failed_$Name"
        Save-Summary
        Write-Log "Failed $Name exit_code=$code"
        exit $code
    }
}

Invoke-Gate "test" @(
    "scripts\evaluate_yolo.py",
    "--weights", $Weights,
    "--data", "data\expanded_ppe_kaggle\dataset.yaml",
    "--split", "test",
    "--imgsz", "640",
    "--device", "0",
    "--output", "results\expanded-ppe-yolov8s-e8-video150-test-metrics.json"
)

Invoke-Gate "hardcase" @(
    "scripts\evaluate_demo_set.py",
    "--weights", $Weights,
    "--images", "data\hard_cases\images\train",
    "--pattern", "hard_??.jpg",
    "--expectations", "data\hard_cases\regression_expectations.json",
    "--imgsz", "640",
    "--device", "0",
    "--output", "results\hardcase-regression-e8-video150.json"
)

Invoke-Gate "demo" @(
    "scripts\evaluate_demo_set.py",
    "--weights", $Weights,
    "--images", "data\demo\selected\images",
    "--pattern", "*",
    "--imgsz", "640",
    "--device", "0",
    "--output", "results\demo-regression-e8-video150.json"
)

Invoke-Gate "video" @(
    "scripts\evaluate_video_cases.py",
    "--weights", $Weights,
    "--video",
    "uploads\9dd0c7b9ae444314a01de70e3c3f5468.mp4",
    "uploads\7894c9c171c6449194fcc8d5f0235cc4.mp4",
    "--imgsz", "640",
    "--device", "0",
    "--output", "results\video-regression-e8-video150.json"
)

$script:Summary.status = "passed_commands_review_required"
Save-Summary
Write-Log "Completed all gate commands; deployment remains manual"
