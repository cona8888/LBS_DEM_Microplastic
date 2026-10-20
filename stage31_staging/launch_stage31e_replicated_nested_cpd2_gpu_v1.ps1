$ErrorActionPreference = 'Stop'
$root = 'C:\MATDEM_MICROPLASTIC'
$runner = Join-Path $root 'stage31_staging\run_stage31e_replicated_nested_cpd2_gpu_v1.py'
$config = Join-Path $root 'stage31_designs\stage31d_replicated_nested_cpd2_geometry_20260826\geometry_01\resolved_config.json'
$handoff = Join-Path $root 'stage31_evaluations\stage31e_replicated_nested_cpd2_gpu_20260826\gpu_release_01\handoff.json'
$output = Join-Path $root 'stage31_runs\stage31e_replicated_nested_cpd2_gpu_20260826\gpu_screen_01'
$supervisor = Join-Path $root 'stage31_runs\stage31e_replicated_nested_cpd2_gpu_20260826\gpu_screen_01_supervisor'
if ((Test-Path -LiteralPath $output) -or (Test-Path -LiteralPath $supervisor)) {
    throw 'refusing to overwrite immutable Stage31e output or supervisor'
}
New-Item -ItemType Directory -Path $supervisor | Out-Null
$stdout = Join-Path $supervisor 'stdout.log'
$stderr = Join-Path $supervisor 'stderr.log'
$python = (Get-Command python -ErrorAction Stop).Source
$arguments = @($runner, '--config', $config, '--handoff', $handoff, '--output', $output)
$process = Start-Process -FilePath $python -ArgumentList $arguments -WindowStyle Hidden -RedirectStandardOutput $stdout -RedirectStandardError $stderr -PassThru
$manifest = [ordered]@{
    schema = 'lbs.stage31e-replicated-nested-cpd2-supervisor.v1'
    status = 'running'
    timestamp_utc = [DateTime]::UtcNow.ToString('o')
    pid = $process.Id
    python = $python
    arguments = $arguments
    output = $output
    stdout = $stdout
    stderr = $stderr
    hashes = [ordered]@{
        runner = (Get-FileHash -Algorithm SHA256 -LiteralPath $runner).Hash.ToLowerInvariant()
        config = (Get-FileHash -Algorithm SHA256 -LiteralPath $config).Hash.ToLowerInvariant()
        handoff = (Get-FileHash -Algorithm SHA256 -LiteralPath $handoff).Hash.ToLowerInvariant()
        launcher = (Get-FileHash -Algorithm SHA256 -LiteralPath $PSCommandPath).Hash.ToLowerInvariant()
    }
    authority = [ordered]@{
        gpu_cpd2 = $true
        cpd4 = $false
        permeability_claim = $false
        mobile_sand = $false
        coupling = $false
    }
}
$json = $manifest | ConvertTo-Json -Depth 8
[System.IO.File]::WriteAllText((Join-Path $supervisor 'launch_manifest.json'), $json + [Environment]::NewLine, [System.Text.UTF8Encoding]::new($false))
Write-Output ($manifest | ConvertTo-Json -Depth 8)
