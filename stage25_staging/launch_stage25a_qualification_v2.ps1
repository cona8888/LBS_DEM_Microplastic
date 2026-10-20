$ErrorActionPreference = 'Stop'

$projectRoot = 'C:\MATDEM_MICROPLASTIC'
$configHost = Join-Path $projectRoot 'stage25_staging\stage25a_mechanics_design_v1.json'
$runnerHost = Join-Path $projectRoot 'stage25_staging\stage25a_yade_pure_sand_mechanics_v1.py'
$launcherHost = $MyInvocation.MyCommand.Path
$outputHost = Join-Path $projectRoot 'stage25_runs\stage25a_pure_sand_mechanics_20260813\qualification_02'
$supervisorHost = Join-Path $projectRoot 'stage25_supervisors\stage25a_pure_sand_mechanics_20260813\qualification_02'

if (Test-Path -LiteralPath $outputHost) {
    throw "Immutable output already exists: $outputHost"
}
if (Test-Path -LiteralPath $supervisorHost) {
    throw "Immutable supervisor root already exists: $supervisorHost"
}

New-Item -ItemType Directory -Path $supervisorHost | Out-Null
New-Item -ItemType Directory -Path (Split-Path -Parent $outputHost) -Force | Out-Null

$configWsl = '/mnt/c/MATDEM_MICROPLASTIC/stage25_staging/stage25a_mechanics_design_v1.json'
$runnerWsl = '/mnt/c/MATDEM_MICROPLASTIC/stage25_staging/stage25a_yade_pure_sand_mechanics_v1.py'
$outputWsl = '/mnt/c/MATDEM_MICROPLASTIC/stage25_runs/stage25a_pure_sand_mechanics_20260813/qualification_02'
$stdoutPath = Join-Path $supervisorHost 'stdout.log'
$stderrPath = Join-Path $supervisorHost 'stderr.log'
$arguments = @(
    '-d', 'Ubuntu-22.04', '--', 'env',
    "STAGE25_CONFIG=$configWsl", "STAGE25_OUTPUT=$outputWsl", "STAGE25_SCRIPT=$runnerWsl",
    '/usr/bin/yade', '-n', '-x', $runnerWsl
)

$launch = [ordered]@{
    schema = 'lbs.stage25a-load-bearing-pure-sand-pilot.v1.launch'
    timestamp_utc = [DateTime]::UtcNow.ToString('o')
    output_root = $outputHost
    supervisor_pid = $PID
    config_sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $configHost).Hash.ToLowerInvariant()
    runner_sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $runnerHost).Hash.ToLowerInvariant()
    launcher_sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $launcherHost).Hash.ToLowerInvariant()
    command = @('wsl.exe') + $arguments
}
$launch | ConvertTo-Json -Depth 6 | Out-File -LiteralPath (Join-Path $supervisorHost 'launch_manifest.json') -Encoding utf8 -NoClobber
([ordered]@{
    schema = 'lbs.stage25a-load-bearing-pure-sand-pilot.v1.running'
    timestamp_utc = [DateTime]::UtcNow.ToString('o')
    supervisor_pid = $PID
    output_root = $outputHost
}) | ConvertTo-Json -Depth 4 | Out-File -LiteralPath (Join-Path $supervisorHost 'running.json') -Encoding utf8 -NoClobber

$exitCode = 1
try {
    & wsl.exe @arguments 1> $stdoutPath 2> $stderrPath
    $exitCode = $LASTEXITCODE
} catch {
    $_ | Out-String | Out-File -LiteralPath (Join-Path $supervisorHost 'launcher_exception.txt') -Encoding utf8 -NoClobber
    $exitCode = 1
}

$status = [ordered]@{
    schema = 'lbs.stage25a-load-bearing-pure-sand-pilot.v1.supervisor-status'
    timestamp_utc = [DateTime]::UtcNow.ToString('o')
    supervisor_pid = $PID
    exit_code = $exitCode
    completed = $true
    completion_exists = Test-Path -LiteralPath (Join-Path $outputHost 'completion.json')
    failure_exists = Test-Path -LiteralPath (Join-Path $outputHost 'failure.json')
}
$status | ConvertTo-Json -Depth 4 | Out-File -LiteralPath (Join-Path $supervisorHost 'status.json') -Encoding utf8 -NoClobber
exit $exitCode
