$ErrorActionPreference = 'Stop'

$root = 'C:\MATDEM_MICROPLASTIC'
$study = 'stage31f_selected_replicated_cpd4_20260827'
$runner = Join-Path $root 'stage31_staging\run_stage31f_selected_replicated_cpd4_gpu_v1.py'
$config = Join-Path $root 'stage31_designs\stage31f_selected_replicated_cpd4_20260827\geometry_01\resolved_config.json'
$handoff = Join-Path $root 'stage31_evaluations\stage31f_selected_replicated_cpd4_20260827\execution_release_01\handoff.json'
$output = Join-Path $root 'stage31_runs\stage31f_selected_replicated_cpd4_20260827\gpu_confirmation_01'
$supervisor = Join-Path $root 'stage31_runs\stage31f_selected_replicated_cpd4_20260827\gpu_confirmation_01_supervisor'

if ((Test-Path -LiteralPath $output) -or (Test-Path -LiteralPath $supervisor)) {
    throw 'immutable Stage31f run or supervisor target already exists'
}
$release = Get-Content -LiteralPath $handoff -Raw | ConvertFrom-Json
$runnerHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $runner).Hash.ToLower()
$configHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $config).Hash.ToLower()
if (-not $release.passed -or $release.status -ne 'stage31f_cpd4_gpu_execution_authorized') {
    throw 'Stage31f execution release is absent'
}
if ($release.bindings.runner_sha256 -ne $runnerHash -or $release.bindings.config_sha256 -ne $configHash) {
    throw 'Stage31f runner/config hash does not match release'
}
if (Get-Process -Name python,python3,yade -ErrorAction SilentlyContinue) {
    throw 'a Python or YADE process is already running; refusing competing launch'
}

$python = (Get-Command python -ErrorAction Stop).Source
New-Item -ItemType Directory -Path $supervisor | Out-Null
$stdout = Join-Path $supervisor 'stdout.log'
$stderr = Join-Path $supervisor 'stderr.log'
$arguments = @($runner, '--config', $config, '--handoff', $handoff, '--output', $output)
$process = Start-Process -FilePath $python -ArgumentList $arguments -PassThru -WindowStyle Hidden -RedirectStandardOutput $stdout -RedirectStandardError $stderr
$launcher = $MyInvocation.MyCommand.Path
$manifest = [ordered]@{
    schema = 'lbs.stage31f-selected-replicated-cpd4-supervisor.v1'
    status = 'running'
    timestamp_utc = [DateTime]::UtcNow.ToString('o')
    pid = $process.Id
    python = $python
    arguments = $arguments
    output = $output
    stdout = $stdout
    stderr = $stderr
    hashes = [ordered]@{
        runner = $runnerHash
        config = $configHash
        handoff = (Get-FileHash -Algorithm SHA256 -LiteralPath $handoff).Hash.ToLower()
        launcher = (Get-FileHash -Algorithm SHA256 -LiteralPath $launcher).Hash.ToLower()
    }
    authority = [ordered]@{
        gpu_cpd4 = $true
        absolute_permeability_validation_claim = $false
        mobile_sand = $false
        coupling = $false
    }
}
$manifest | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $supervisor 'launch_manifest.json') -Encoding utf8
$manifest | ConvertTo-Json -Depth 8
