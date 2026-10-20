"""Reuse frozen mixed-mode algebra on authenticated held equations only."""
from pathlib import Path
import importlib.util, os, time, traceback
import authenticate_failed_system_v1 as source
job, api, ROOT, frozen = source.job, source.api, source.ROOT, source.frozen
PROBE = ROOT / 'stage194_staging/probe_mixed_projection_v1.py'
spec = importlib.util.spec_from_file_location('stage210_exact_old_mixed_mode_probe', PROBE)
mixed = importlib.util.module_from_spec(spec); spec.loader.exec_module(mixed)
OUT = ROOT / 'stage210_evaluations/three_contact_failure_20261001/exact_gap_modes_01'


def run():
    d = api.read(job.DESIGN); job.verify(d)
    proofpath = source.OUT / 'results.json'; proof = api.read(proofpath); fp = source.OUT / 'failed_systems.json'
    api.require(api.read(proofpath.parent / 'completion.json')['results_sha256'] == api.sha(proofpath), 'authentication seal')
    api.require(proof['evidence_authentication_passed'] and not proof['numerical_gate_passed'] and api.sha(fp) == proof['failed_systems_sha256'], 'original failed equations bound')
    api.require(mixed.tests.job.fast.gate is job.fast.gate, 'same unchanged finalizer')
    files = [Path(__file__), source.WORK, job.DESIGN, fp, proofpath, PROBE, Path(mixed.tests.__file__), Path(mixed.tests.independent.__file__)]
    inputs = {str(p): api.sha(p) for p in files}
    OUT.mkdir(parents=True, exist_ok=False); end = time.time() + 900
    job.commit(OUT / 'launch.json', dict(pid=os.getpid(), utc=job.utc().isoformat(), argv=__import__('sys').argv, inputs=inputs, new_trajectory_steps=0, maximum_held_systems=3, maximum_wall_seconds=900, optimizer_nfev_per_seed=300))
    reports = []
    try:
        with job.parent.fix.scope():
            for index, item in enumerate(api.read(fp)['failed_inner_systems'][:3]):
                api.require(time.time() < end, 'bounded algebraic work clock')
                s = item['system']; api.require(api.digest(s) == item['system_sha256'], 'exact held input')
                start = time.perf_counter(); modes = mixed.probe(s, end)
                passed = any(c['passed'] for mode in modes for c in mode['candidates'])
                row = dict(index=index, system_sha256=item['system_sha256'], passed=passed, modes=modes, seconds=time.perf_counter()-start)
                reports.append(row); job.commit(OUT / ('system_%02d.json' % index), row)
                print('EXACT_GAP_MODES', index, passed, modes[-1]['mode'], modes[-1]['scale'], row['seconds'], flush=True)
        api.verify_mapping(inputs); job.verify(d)
        result = dict(new_trajectory_steps=0, original_gates_unchanged=True, inputs=inputs, systems=reports,
                      passed=all(r['passed'] for r in reports), claim='Held algebraic equations only; exact original gap kinematics, original finalizer and separate physical audit. No installed repair, trajectory qualification or production pass.')
        job.commit(OUT / 'results.json', result); job.commit(OUT / 'completion.json', dict(results_sha256=api.sha(OUT / 'results.json'), new_trajectory_steps=0))
    except Exception as error:
        job.commit(OUT / 'failure.json', dict(error=repr(error), traceback=traceback.format_exc(), new_trajectory_steps=0)); raise


if __name__ == '__main__': run()
