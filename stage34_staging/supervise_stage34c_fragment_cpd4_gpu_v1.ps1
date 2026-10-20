$ErrorActionPreference = 'Stop'

$root = 'C:\MATDEM_MICROPLASTIC'
$study = 'stage34c_cpd4_first_fragmentation_geometry_20260902'
$runner = Join-Path $root 'stage34_staging\run_stage34c_fragment_cpd4_gpu_v1.py'
$config = Join-Path $root 'stage34_designs\stage34c_cpd4_first_fragmentation_geometry_20260902\gpu_config_01\resolved_config.json'
$handoff = Join-Path $root 'stage34_evaluations\stage34c_cpd4_first_fragmentation_geometry_20260902\execution_release_01\handoff.json'
$output = Join-Path $root 'stage34_runs\stage34c_cpd4_first_fragmentation_geometry_20260902\gpu_confirmation_01'
$supervisor = Join-Path $root 'stage34_runs\stage34c_cpd4_first_fragmentation_geometry_20260902\gpu_confirmation_01_supervisor'

if ((Test-Path -LiteralPath $output) -or (Test-Path -LiteralPath $supervisor)) {
    throw 'immutable Stage34C run or supervisor target already exists'
}
$release = Get-Content -LiteralPath $handoff -Raw | ConvertFrom-Json
$runnerHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $runner).Hash.ToLower()
$configHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $config).Hash.ToLower()
$supervisorHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $MyInvocation.MyCommand.Path).Hash.ToLower()
if (-not $release.passed -or $release.status -ne 'stage34c_fragment_cpd4_gpu_execution_authorized') {
    throw 'Stage34C execution release is absent'
}
if ($release.bindings.runner_sha256 -ne $runnerHash -or
    $release.bindings.config_sha256 -ne $configHash -or
    $release.bindings.supervisor_sha256 -ne $supervisorHash) {
    throw 'Stage34C runner/config/supervisor hash does not match release'
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
$manifest = [ordered]@{
    schema = 'lbs.stage34c-fragment-cpd4-supervisor.v1'
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
        supervisor = $supervisorHash
    }
    authority = [ordered]@{
        one_eight_case_cpd4_gpu_campaign = $true
        cpd6_flow = $false
        absolute_permeability_validation_claim = $false
        chemical_degradation_claim = $false
        mechanics_or_coupling = $false
    }
}
$manifest | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $supervisor 'launch_manifest.json') -Encoding utf8
$manifest | ConvertTo-Json -Depth 8
