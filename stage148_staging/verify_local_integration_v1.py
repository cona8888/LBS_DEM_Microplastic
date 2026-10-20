"""Local compiled-stack qualification of the externally supplied tolerance idea.

Single-threaded CPU only. Exclusive outputs, prospective protocol, no campaign.
The imported tests are evidence to review, not authority to mutate prior stages.
"""
from pathlib import Path
import copy
import os
import sys
import time
import traceback
import numpy as np
import scipy

ROOT = Path(__file__).resolve().parents[1]
import compiled_geometric_contract_v1 as method
parent = method.parent
api, engine, hot = parent.api, parent.engine, parent.hot
sys.path.insert(0, str(ROOT/'stage145_staging'))
import frozen_systems_v1 as frozen
import geometric_tolerance_v1 as external
OUT = ROOT/'stage148_evaluations/local_compiled_contract_20260921/qualification_01'
EXTERNAL = [ROOT/'stage145_evaluations/tolerance_contract_and_branch_audit_20260920/run_00_external_environment',
            ROOT/'stage146_evaluations/rotational_inertia_20260920/run_00_external_environment',
            ROOT/'stage147_evaluations/trajectory_stall_clearance_20260920/run_00_external_environment']
ENDPOINT = ROOT/'stage140_runs/sphere_finite_dwell_refinement_20260918/refinement_01/sphere_dwell_factor_1'


def mapped_path(p):
    prefix = '/home/claude/work/matdem_mirror/'
    api.require(str(p).startswith(prefix), 'unrecognized external path prefix')
    local = (ROOT/str(p)[len(prefix):]).resolve()
    api.require(local.is_relative_to(ROOT), 'external path escaped project')
    return local


def import_audit():
    rows = []
    for folder in EXTERNAL:
        seal = api.read(folder/'completion.json')
        checks = {'results_hash': api.sha(folder/'results.json') == seal['results_sha256']}
        if (folder/'protocol.json').exists():
            protocol = api.read(folder/'protocol.json')
            checks['protocol_hash'] = api.sha(folder/'protocol.json') == seal['protocol_sha256']
            for group in ('inputs', 'sources'):
                for source, sha in protocol[group].items():
                    checks[str(mapped_path(source))] = api.sha(mapped_path(source)) == sha
        else:
            for key, path in [('runner_sha256', 'stage147_staging/run_stage147_v1.py'),
                              ('solver_sha256', 'stage147_staging/contact_solver_v1.py'),
                              ('harness_sha256', 'stage147_staging/replay_harness_v1.py')]:
                checks[key] = api.sha(ROOT/path) == seal[key]
        rows.append({'directory': str(folder), 'passed': all(checks.values()), 'checks': checks,
                     'imported_pass_claim': api.read(folder/'results.json')['passed']})
    return rows


def write_record(name, record):
    api.write(OUT/(name+'.json'), record, raw=True)


def main():
    OUT.mkdir(parents=True, exist_ok=False)
    start = time.perf_counter()
    imported = import_audit()
    pd = api.read(parent.DESIGN)
    parent.verify(pd)
    spheres, fibres, bindings = frozen.load()
    inputs = [parent.DESIGN]+[Path(c['source']) for c in pd['cases']]
    inputs += [parent.OUT/(c['id']+'.json') for c in pd['cases']]
    inputs += [ENDPOINT/f'segment_{i:02d}/record.json' for i in (2, 9)]
    inputs += [p for folder in EXTERNAL for p in folder.iterdir() if p.is_file()]
    sources = {str(Path(m.__file__).resolve()): api.sha(m.__file__) for m in list(sys.modules.values())
               if getattr(m, '__file__', None) and Path(m.__file__).suffix == '.py'
               and Path(m.__file__).resolve().is_relative_to(ROOT)
               and 'staging' in str(m.__file__)}
    sources[str(Path(__file__).resolve())] = api.sha(__file__)
    protocol = {
        'stage': 'Stage148', 'question': 'Does an explicit geometric tolerance revision work in the actual compiled transport stack without changing disabled or fibre paths?',
        'inputs': {str(p): api.sha(p) for p in inputs}, 'sources': sources,
        'imported_evidence_audit': imported,
        'environment': {'python': sys.version, 'numpy': np.__version__, 'scipy': scipy.__version__,
                        'numba': hot.njit.__module__, 'threads': {k: os.getenv(k) for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS')}},
        'numerical_contract': 'Raw gaps unchanged. Projected normal AND tangential residual <= max(tol*max(norm(vfree),1e-15), kappa*eps*L/dt). Work ceiling = old ceiling + sum(norm(ft))*kappa*eps*L/dt. Both raw and rescaled residuals recorded. No assertion this is an unchanged physical gate.',
        'acceptance': {'disabled_seven_replays_bitwise': True, 'fibres_excluded_bitwise': True,
                       'sphere_common_clock_limits': pd['limits'], 'restart_exact_state': True,
                       'frozen_spheres_all_pass': True, 'multipliers': [8,16,64],
                       'timestep_factors': [1.,.5,.25], 'every_contact_independently_certified': True,
                       'negative_reaction_controls_rejected': True, 'long_dispatch': False},
        'budget': '45 s cooperative per call, <=64 steps per short replay; six common-clock 0.01 s sphere windows <=4096 steps each, at most 900 s total. One CPU thread. No GPU/YADE dispatch.',
        'model_changes': [], 'default_enabled': False, 'fibre_enabled': False,
        'not_claimed': ['Imported claims independently reproduced in full', 'Exact global geometric error bound',
                        'Unchanged solver branch selection', 'Population release fraction', 'Experimental validation',
                        'Rotational inertia validated for moving fibres'],
    }
    api.write(OUT/'protocol.json', protocol)
    api.require(all(r['passed'] for r in imported), 'imported hash mismatch')
    parent.old.prior.prior.configure()
    hot.warmup()
    tests, certs = [], []
    certificates = []
    # Primitive tests use actual archived matrices, not a scene reconstructed with
    # potentially different last-bit gap geometry.
    for s in spheres:
        for kappa in (8,16,64):
            for dt_factor in (1., 1/16):
                delta = kappa*np.finfo(float).eps*frozen.CELL_LENGTH_M
                args = [s[k] for k in ('vfree','mobility','jacobian','gaps')]+[s['dt']*dt_factor,s['mu'],s['tol'],s['maxiter']]
                before = api.digest(args)
                try:
                    q,h,certificate = method.solve(*args, delta=delta)
                    row = {'id': s['id'], 'kappa': kappa, 'dt_factor': dt_factor,
                           'passed': certificate['passed'] and before == api.digest(args),
                           'velocity': q, 'health': h, 'certificate': certificate}
                    certs.append(certificate)
                except Exception as exc:
                    row = {'id': s['id'], 'kappa': kappa, 'dt_factor': dt_factor, 'passed': False, 'error': repr(exc)}
                tests.append(row)
    write_record('primitive_tests', {'rows': tests, 'passed': all(r['passed'] for r in tests)})
    print('PRIMITIVES', sum(r['passed'] for r in tests), '/', len(tests), flush=True)
    api.require(all(r['passed'] for r in tests), 'primitive test failed; no trajectory dispatch')
    # Deliberately corrupt a reaction; recompute velocity so closure alone cannot
    # conceal negative normals, cone violations or changed gaps.
    s = spheres[0]
    args = [s[k] for k in ('vfree','mobility','jacobian','gaps','dt','mu','tol','maxiter')]
    delta = 16*np.finfo(float).eps*frozen.CELL_LENGTH_M
    q,h,_ = method.solve(*args, delta=delta)
    controls = []
    for name in ('negative_normal', 'outside_cone', 'nan_force', 'large_gap_change'):
        f = np.array(h['reactions']); g = s['gaps'].copy()
        if name == 'negative_normal': f[0] = -abs(f[0])-1e-9
        elif name == 'outside_cone': f[1] = 1e3*max(np.linalg.norm(f), 1e-9)
        elif name == 'nan_force': f[0] = np.nan
        else: g[0] += 1e6*delta
        qq = s['vfree']+s['mobility']@s['jacobian'].T@f
        check = method.audit(s['vfree'],s['mobility'],s['jacobian'],g,s['dt'],s['mu'],qq,f,delta,s['tol'])
        controls.append({'id': name, 'passed': not check['passed'], 'certificate': check})
    write_record('negative_controls', {'rows': controls, 'passed': all(r['passed'] for r in controls)})
    api.require(all(r['passed'] for r in controls), 'negative control failed')

    def run(label, c, *, enabled, target=None, factor=1., kappa=16, steps=64, cp_in=None, bound=None, expect_pause=False):
        api.require(time.perf_counter()-start < 900, 'stage wall budget exhausted')
        spec = copy.deepcopy(c['spec'])
        spec['config']['numerics']['wall_budget_s_per_case'] = 45.
        if target is not None:
            spec['horizon_s'] = target
            spec['horizon_pv'] = target*spec['field_metadata']['pv_per_second']
        for key in api.DT_CONTROLS: spec['config']['numerics'][key] *= factor
        cp = copy.deepcopy(cp_in if cp_in is not None else api.read(c['source'])['result']['checkpoint'])
        api.require(cp['state_sha256'] == api.digest(cp['state']), 'checkpoint input integrity')
        L = spec['field_metadata']['cell_length_m']
        api.require(max(np.abs(cp['state']['x'])) <= L, 'coordinate scale assumption violated')
        bound = bound or api.digest([api.sha(OUT/'protocol.json'), label])
        cp['contract'] = engine.prior.contracts.expected_contract(spec, bound)
        local = []
        with hot.scope(), parent.scope(spec), method.scope(spec, enabled=enabled, multiplier=kappa, certificates=local):
            r, rows = engine.runtime.execute(spec, bound, checkpoint=cp, pause=cp['state']['steps']+steps)
        health = engine.prior.reference.independent_health(r, spec)
        clock_closure = abs(sum(x['dt_s'] for x in rows)-(r['time_s']-cp['state']['t'])) <= 2e-14
        final_state_hash = r['checkpoint']['state_sha256'] == api.digest(r['checkpoint']['state'])
        coordinates = all(max(np.abs(x['position_m'])) <= L for x in rows)
        passed = health['passed'] and clock_closure and final_state_hash and coordinates and all(x['passed'] for x in local)
        if enabled and len(set(spec['config']['prolate_semiaxes_m'])) == 1:
            passed = passed and not r.get('stage119_repair_calls')
        if target is not None and not expect_pause: passed = passed and r['time_s'] == target and r['status'] == 'present_at_horizon'
        else: passed = passed and r['status'] == 'paused_checkpoint' and len(rows) == steps
        record = {'passed': passed, 'result': r, 'rows': rows, 'health': health, 'certificates': local,
                  'clock_closure': clock_closure, 'checkpoint_hash_pass': final_state_hash,
                  'coordinate_scale_verified': coordinates, 'enabled': enabled, 'kappa': kappa,
                  'dt_factor': factor, 'spec': spec, 'source': c['source'], 'source_sha256': api.sha(c['source']),
                  'input_checkpoint_sha256': api.digest(cp), 'binding': bound}
        write_record(label, record)
        certificates.extend(local)
        print(label, passed, r['status'], r['time_s'], 'steps',len(rows), 'certs',len(local), flush=True)
        return record

    disabled, exclusions, comparisons, refinements, endpoints = [], [], [], [], []
    for c in pd['cases']:
        old = api.read(parent.OUT/(c['id']+'.json'))
        rec = run('disabled_'+c['id'], c, enabled=False, steps=8)
        ref = old['result']
        keys = ('position_m','orientation','velocity_generalized','time_s','status','steps','rejected','contact_solver_retries')
        exact = all(rec['result'][k] == ref[k] for k in keys)
        row = {'id': c['id'], 'passed': rec['passed'] and exact and not rec['certificates'], 'bitwise_state_and_decisions': exact}
        disabled.append(row)
        sphere = len(set(c['spec']['config']['prolate_semiaxes_m'])) == 1
        if not sphere:
            excluded = run('excluded_'+c['id'], c, enabled=True, steps=8)
            same = all(excluded['result'][k] == rec['result'][k] for k in keys)
            exclusions.append({'id': c['id'], 'passed': excluded['passed'] and same and not excluded['certificates']})
        else:
            candidate = run('common_'+c['id'], c, enabled=True, target=ref['time_s'])
            cmp = parent.old.prior.compare_results(ref,candidate['result'],c['spec'],pd['limits'])
            cmp.update(id=c['id'], passed=cmp['passed'] and candidate['passed'])
            comparisons.append(cmp)
    write_record('replay_summary', {'disabled': disabled,'fibre_exclusions': exclusions,'common_clock_comparisons': comparisons})
    api.require(all(r['passed'] for r in disabled+exclusions+comparisons), 'short replay gate failed; no extension')
    c = next(c for c in pd['cases'] if c['id'] == 'sphere_12_terminal')
    target = api.read(c['source'])['result']['time_s']+0.01
    reference = None
    for factor,kappa in [(1.,16),(.5,16),(.25,16),(1.,8),(1.,64)]:
        label = f'local_factor_{factor:g}_kappa_{kappa}'
        rec = run(label,c,enabled=True,target=target,factor=factor,kappa=kappa,steps=4096)
        if reference is None: reference=rec
        cmp = parent.old.prior.compare_results(reference['result'],rec['result'],c['spec'],pd['limits'])
        cmp.update(factor=factor,kappa=kappa,passed=cmp['passed'] and rec['passed'])
        refinements.append(cmp)
    # Same bound, target and controls across split replay; state must be exact.
    first = run('restart_first',c,enabled=True,target=target,steps=8,bound=reference['binding'],expect_pause=True)
    # A step-budget pause is expected for this one record, not an endpoint pass.
    first_ok = first['result']['status'] == 'paused_checkpoint' and first['health']['passed'] and len(first['rows']) == 8
    second = run('restart_second',c,enabled=True,target=target,steps=4096,
                 cp_in=first['result']['checkpoint'],bound=reference['binding'])
    restart = {'passed': first_ok and second['passed'] and reference['result']['checkpoint']['state'] == second['result']['checkpoint']['state']}
    for i in (2,9):
        ec = copy.deepcopy(c); ec['source']=str(ENDPOINT/f'segment_{i:02d}/record.json')
        rec = run(f'endpoint_{i:02d}',ec,enabled=True,target=1.3,steps=64)
        endpoints.append({'segment':i,'passed':rec['passed'],'time_s':rec['result']['time_s'], 'steps':len(rec['rows'])})
    api.verify_mapping(protocol['sources']);api.verify_mapping(protocol['inputs']);parent.verify(pd)
    passed = all(r['passed'] for r in tests+controls+disabled+exclusions+comparisons+refinements+endpoints+[restart])
    result = {'stage':'Stage148','passed':passed,'imported_hash_checks_passed':all(r['passed'] for r in imported),
              'primitive_tests_passed':sum(r['passed'] for r in tests),'primitive_tests_total':len(tests),
              'negative_controls':controls,'disabled_replays':disabled,'fibre_exclusions':exclusions,
              'common_clock_comparisons':comparisons,'refinement':refinements,'restart':restart,'endpoints':endpoints,
              'trajectory_contact_certificates':len(certificates),
              'max_raw_contact_residual':max(x['legacy_residual_over_vfree'] for x in certificates),
              'max_residual_over_ceiling':max(x['residual_over_ceiling'] for x in certificates),
              'legacy_energy_gate_violations':sum(not x['legacy_work_gate_pass'] for x in certificates),
              'wall_s':time.perf_counter()-start,
              'claim':'Local compiled-stack numerical qualification only. Fibre physics and branch selection not promoted. Full sphere horizon not yet tested.',
              'artifacts':{str(p):api.sha(p) for p in OUT.iterdir() if p.is_file()}}
    write_record('results',result)
    write_record('completion',{'passed':passed,'results_sha256':api.sha(OUT/'results.json'),'protocol_sha256':api.sha(OUT/'protocol.json')})
    print('STAGE148_PASS',passed,flush=True)
    return 0 if passed else 4


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as exc:
        if OUT.exists() and not (OUT/'failure.json').exists():
            write_record('failure',{'error':repr(exc),'traceback':traceback.format_exc(),
                                    'artifacts':{str(p):api.sha(p) for p in OUT.iterdir() if p.is_file()}})
        raise
