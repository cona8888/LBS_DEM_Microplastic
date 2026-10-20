"""Zero-step re-audit: preserve v1 failure; distinguish PID reuse from ownership.

All raw, numerical, restart, fixture and step gates are cloned unchanged from
frozen v1. Only the retirement observation and output directory are replaced.
"""
from pathlib import Path
import os
import psutil
import audit_contact_repaired_stack_v1 as frozen

api, job = frozen.wrapper.api, frozen.wrapper.job
OUT = job.OUT / 'independent_readiness_02'
IDENTITY = {}


def norm(argv):
    return [os.path.normcase(os.path.normpath(x)) for x in argv]


def retired_identity(created, command, completion, owned_scripts):
    # Fail closed on a matching command regardless of PID, or an identity that
    # could predate recorded retirement. Reuse requires BOTH independent facts.
    return created > completion and not (set(norm(command)) & owned_scripts)


def verify_retired(owned, live):
    global IDENTITY
    scripts = set(norm([str(job.SELF), str(job.PREFLIGHT_SCRIPT)]))
    terminal = api.read(live/'completion.json')
    ended = job.policy.utc(terminal['utc']).timestamp()
    old = job.OUT/'independent_readiness_01'
    launch = api.read(old/'launch.json'); failure = api.read(old/'failure.json')
    dispatch = api.read(live/'dispatch_03.json')
    api.require(launch['pid'] == dispatch['pid'] == 43760, 'saved audit/worker PID collision')
    api.require(job.policy.utc(launch['utc']).timestamp() > ended and terminal['producer_exit_codes'][dispatch['case']] == 0, 'worker exited before audit reused its PID')
    api.require(failure['error'] == "RuntimeError('every owned process retired')", 'preserved v1 retirement failure')
    checks = [
        not retired_identity(ended-1, ['other.py'], ended, scripts),
        not retired_identity(ended, ['other.py'], ended, scripts),
        not retired_identity(ended+1, [str(job.SELF)], ended, scripts),
        not retired_identity(ended+1, [str(job.PREFLIGHT_SCRIPT)], ended, scripts),
        retired_identity(ended+1, [__file__], ended, scripts),
    ]
    api.require(all(checks), 'five zero-step identity mutation controls')
    observations = []
    for pid in owned:
        try:
            p = psutil.Process(pid)
            with p.oneshot():
                created, command = p.create_time(), p.cmdline()
            api.require(bool(command) and retired_identity(created, command, ended, scripts), 'no live original owned identity')
            observations.append(dict(pid=pid, status='proved_reused', create_time=created, argv=command))
        except psutil.NoSuchProcess:
            observations.append(dict(pid=pid, status='absent'))
        # AccessDenied is not interpreted as retirement.
    matching = []
    for p in psutil.process_iter(['pid', 'name']):
        if 'python' not in (p.info['name'] or '').lower():
            continue
        try:
            command = p.cmdline()
            if set(norm(command)) & scripts:
                matching.append(dict(pid=p.pid, argv=command))
        except psutil.NoSuchProcess:
            continue
    api.require(not matching, 'no matching supervisor, worker, probe or auditor command under another PID')
    inputs = [old/'launch.json', old/'failure.json', live/'dispatch_03.json', live/'completion.json', Path(frozen.__file__), Path(__file__)]
    IDENTITY = dict(passed=True, new_trajectory_steps=0, observed_utc=job.utc().isoformat(),
        former_pid=43760, cause='PID 43760 was reused by the v1 audit after the original worker exited with code zero.',
        preserved_failure=str(old/'failure.json'), identity_controls_passed=len(checks), observations=observations,
        matching_owned_commands=matching, inputs={str(p):api.sha(p) for p in inputs})
    job.commit(OUT/'retirement_identity.json', IDENTITY)


source = frozen.source
changes = {
    "OUT = job.OUT/'independent_readiness_01'": "OUT = job.OUT/'independent_readiness_02'",
    "api.require(not any(psutil.pid_exists(pid) for pid in owned), 'every owned process retired')": "verify_retired(owned, live)",
    "'all_owned_processes_retired':True, 'required_simulation_hours'": "'all_owned_processes_retired':True, 'retirement_identity_sha256':api.sha(OUT/'retirement_identity.json'), 'required_simulation_hours'",
}
for before, after in changes.items():
    assert source.count(before) == 1, before
    source = source.replace(before, after)
ns = dict(__name__='_stage202_identity_safe_audit', __file__=__file__, verify_retired=verify_retired)
exec(compile(source, __file__+'::unchanged_scientific_gates', 'exec'), ns)
if __name__ == '__main__':
    ns['run']()
