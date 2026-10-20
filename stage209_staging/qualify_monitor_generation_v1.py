"""Zero-step completed-worker PID-guard controls and live seal snapshot."""
from pathlib import Path
from types import FunctionType, SimpleNamespace
import json, os, traceback
import psutil
import monitor_cone_campaign_v6 as candidate
import cone_feasibility_campaign_v1 as s

api, job = s.api, s.job
OUT = job.OUT / 'monitor_generation_qualification_01'
DESIGN_SHA = 'ea1b9279008821a81e472127eb9fd602d5692568458d3af6601a5f9c160b1ca9'
ROLE = 's2_i0_sphere_f0p03125'


def process(name='chrome.exe'):
    return SimpleNamespace(pid=46968, name=lambda: name)


def run():
    api.require(not OUT.exists(), 'exclusive read-only qualification')
    OUT.mkdir(parents=True, exist_ok=False)
    job.commit(OUT / 'launch.json', dict(utc=job.utc().isoformat(), pid=os.getpid(), new_trajectory_steps=0,
                source_sha256=api.sha(__file__), design_sha256=DESIGN_SHA))
    try:
        argv = [os.sys.executable, '-B', '-u', str(job.SELF), 'worker', 'campaign', ROLE]
        assert candidate.different_executable(process(Path(os.sys.executable).name), ROLE, argv) is None
        correct = candidate.different_executable(process(), ROLE, argv)
        assert correct['original_worker_retired'] and correct['pid_reused_by_different_executable'] and not correct['alive']
        rejected = []
        tests = [('supervisor', process(), 'supervisor'), ('unknown_role', process(), 'not_a_case'),
                 ('unfinished_worker', process(), 's2_i0_fibre_f0p03125')]
        for label, proc, role in tests:
            try: candidate.different_executable(proc, role, argv)
            except (AssertionError, FileNotFoundError): rejected.append(label)
            else: raise AssertionError('unproved retirement accepted: ' + label)
        def denied(): raise psutil.AccessDenied(46968)
        try: candidate.different_executable(SimpleNamespace(pid=46968, name=denied), ROLE, argv)
        except psutil.AccessDenied: rejected.append('unreadable_identity')
        else: raise AssertionError('unreadable identity accepted')
        # Isolated immutable C-side corrupt seals; never alter an old/run file.
        for label in ('wrong_design', 'wrong_result_hash', 'wrong_producer_design'):
            root = OUT / 'fixtures' / label; folder = root / ROLE
            producer = dict(design_sha256='0'*64 if label == 'wrong_producer_design' else DESIGN_SHA)
            job.commit(folder / 'result.json', producer)
            seal = dict(design_sha256='0'*64 if label == 'wrong_design' else DESIGN_SHA,
                        result_sha256='0'*64 if label == 'wrong_result_hash' else api.sha(folder / 'result.json'))
            job.commit(folder / 'completion.json', seal)
            guarded = FunctionType(candidate.different_executable.__code__,
                                   dict(candidate.different_executable.__globals__, ROOT=root))
            try: guarded(process(), ROLE, argv)
            except AssertionError: rejected.append(label)
            else: raise AssertionError('corrupt worker seal accepted: ' + label)
        text = candidate.guarded_template(Path('C:/MATDEM_MICROPLASTIC/stage200_staging/monitor_revised_campaign_v1.py'))
        assert 'cmd=p.cmdline();expected=[str(v).lower() for v in argv]' in text
        assert 'except psutil.NoSuchProcess:processes.append' in text
        assert 'except psutil.AccessDenied' not in text
        live = candidate.run(DESIGN_SHA)
        assert live['frozen_sources_verified'] and live['frozen_inputs_verified']
        assert all(p.get('bound_active_identity') for p in live['processes'] if p.get('alive'))
        files = [Path(__file__), Path(candidate.__file__),
                 Path(candidate.__file__).with_name('monitor_cone_campaign_v4.py'),
                 Path(candidate.__file__).with_name('monitor_cone_campaign_v5.py'), job.DESIGN,
                 Path('C:/MATDEM_MICROPLASTIC/stage200_staging/monitor_revised_campaign_v1.py'),
                 job.OUT / 'read_only_monitor_generation_failures_01/results.json',
                 job.OUT / 'read_only_monitor_v5_failure_01/results.json']
        result = dict(passed=True, new_trajectory_steps=0, original_campaign_unchanged=True,
                      active_python_never_bypassed=True, retired_browser_reuse_classified=correct,
                      unproved_or_corrupt_retirement_controls_rejected=rejected,
                      original_active_command_checks_retained=True,
                      inputs={str(p): api.sha(p) for p in files}, live_snapshot=live)
        job.commit(OUT / 'results.json', result)
        job.commit(OUT / 'completion.json', dict(passed=True, results_sha256=api.sha(OUT / 'results.json'),
                   claim='Read-only monitor qualification and publication snapshot, not campaign acceptance.'))
        print('READ_ONLY_GENERATION_GUARD_PASS', api.sha(OUT / 'results.json'), rejected, flush=True)
    except Exception as error:
        job.commit(OUT / 'failure.json', dict(error=repr(error), traceback=traceback.format_exc(), new_trajectory_steps=0)); raise


if __name__ == '__main__': run()
