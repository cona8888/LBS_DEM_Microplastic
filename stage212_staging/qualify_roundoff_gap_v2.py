"""Bounded zero-trajectory numerical-policy tests; no installation or campaign."""
from pathlib import Path
import copy, hashlib, math, os, shutil, sys, time, traceback
import numpy as np
import psutil

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'stage210_staging'))
import authenticate_failed_system_v1 as source
import semismooth_rejected_seed_v1 as analytic
import roundoff_sphere_gap_v1 as policy
job, api, frozen = source.job, source.api, source.frozen
CONTRACT = ROOT / 'stage212_designs/roundoff_gap_20261001/contract_02.json'
OUT = ROOT / 'stage212_evaluations/roundoff_gap_20261001/qualification_02'


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def run():
    w = api.read(CONTRACT); d = api.read(job.DESIGN)
    require(w['user_approved_numerical_policy_qualification'] and w['maximum_new_trajectory_steps'] == 0
            and not w['production_authorized'], 'approved zero-step qualification only')
    require(all(os.environ.get(k) == '1' for k in ('OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'OMP_NUM_THREADS')), 'threads1')
    require(shutil.disk_usage(ROOT).free >= w['minimum_free_disk_bytes'], '20GiB C reserve')
    api.verify_mapping(w['sources']); api.verify_mapping(w['inputs']); job.verify(d)
    proofpath = source.OUT / 'results.json'; proof = api.read(proofpath)
    require(api.read(proofpath.parent / 'completion.json')['results_sha256'] == api.sha(proofpath)
            and proof['evidence_authentication_passed'] and not proof['numerical_gate_passed']
            and api.sha(source.OUT / 'failed_systems.json') == proof['failed_systems_sha256'], 'sealed rejected evidence')
    closure = api.read(ROOT / 'stage211_evaluations/terminal_accounting_20261001/independent_01/results.json')
    require(closure['full_failed_run_accounting_closed'] and not closure['campaign_passed'], 'failed-inclusive closure prerequisite')
    require(not frozen.active_owned(False) and not OUT.exists(), 'exclusive zero-step worker')
    OUT.mkdir(parents=True, exist_ok=False); process = psutil.Process(); end = time.time() + w['maximum_wall_seconds']
    job.commit(OUT / 'launch.json', dict(pid=process.pid, created=process.create_time(), argv=process.cmdline(), utc=job.utc().isoformat(),
               contract_sha256=api.sha(CONTRACT), source_sha256=api.sha(__file__), new_trajectory_steps=0))
    reports, geometry_checks = [], []
    try:
        spec = next(c['spec'] for c in d['cases'] if c['id'] == 's2_i124_sphere_f0p0625')
        axes = spec['config']['prolate_semiaxes_m']; require(len(axes) == 3 and axes[0] == axes[1] == axes[2], 'original exact sphere'); a, b = axes[:2]; L = spec['field_metadata']['cell_length_m']
        geo = spec['field_metadata']['geometry']; require(api.sha(geo['path']) == geo['sha256'], 'original geometry')
        data = np.load(geo['path'], allow_pickle=False)
        producer = api.read(job.RUN / 's2_i124_sphere_f0p0625/result.json')['final_result']
        x, p = np.asarray(producer['checkpoint']['state']['x']), np.asarray(producer['checkpoint']['state']['p'])
        systems = api.read(source.OUT / 'failed_systems.json')
        model = job.fast.gate.contact_model
        contexts = []
        for contact in systems['failed_outer_trials'][0]['outer_inputs'][6]:
            k, saved, n, lever = contact
            centre = data['sand_centres_m'][k]; radius = float(data['sand_radii_m'][k])
            delta = centre - x; delta -= L * np.round(delta / L); image = x + delta
            gap, normal, arm = model.ellipsoid_grain_contact(x, p, a, b, image, radius)
            require(gap == saved and np.asarray(n).tobytes() == normal.tobytes() and np.asarray(lever).tobytes() == arm.tobytes(), 'native failed geometry exactly reproduced')
            effective, meta = policy.classify(x, image, a, b, radius, gap)
            require(effective == 0.0 and meta['changed'], 'captured gap classified within frozen band')
            contexts.append(dict(grain_id=k, x=x.tolist(), c=image.tolist(), a=a, b=b, r=radius, **meta))
            # Classifier boundaries and true larger overlaps/separations stay explicit.
            band = meta['uncertainty_m']
            for testgap in (0.0, band, -band, math.nextafter(band, math.inf), -math.nextafter(band, math.inf), 1e-8*a, -1e-8*a):
                got, m = policy.classify(x, image, a, b, radius, testgap)
                expected = 0.0 if abs(testgap) <= band else testgap
                require(got == expected and (abs(testgap) <= band or got.hex() == float(testgap).hex()), 'closed band/outside exact identity')
                geometry_checks.append(dict(context=len(contexts)-1, test_gap_m=testgap, **m))
            got, m = policy.classify(x, image, a, a/4, radius, gap)
            require(got.hex() == float(gap).hex() and not m['changed'] and not m['sphere'], 'fibre identity')
        require(len(contexts) == 3, 'original three-contact scope')
        negative = []
        for label, args in [('nan_gap', (x, image, a, b, radius, math.nan)), ('negative_radius', (x, image, a, b, -radius, gap)),
                            ('nonfinite_centre', (x, np.full(3, math.inf), a, b, radius, gap)),
                            ('coordinate_scale_ceiling', (np.full(3, 1e100), image, a, b, radius, gap))]:
            try:
                policy.classify(*args)
            except ValueError:
                negative.append(label)
            else:
                raise RuntimeError('invalid policy input accepted ' + label)
        with job.parent.fix.scope():
            gate = job.fast.gate
            require(gate is analytic.gate, 'unchanged original finalizer binding')
            for item in systems['failed_inner_systems']:
                require(time.time() < end and len(reports) < w['maximum_held_systems'], 'bounded held solve')
                s = item['system']; require(api.digest(s) == item['system_sha256'], 'original held input seal')
                outer = systems['failed_outer_trials'][item['failed_outer_index']]['outer_inputs'][6]
                require([int(z[0]) for z in outer] == [z['grain_id'] for z in contexts]
                        and [z[1] for z in outer] == s['gaps_m'], 'outer/inner original contact identity')
                raw = np.asarray(s['gaps_m'], float)
                effective = np.asarray([policy.classify(c['x'], c['c'], c['a'], c['b'], c['r'], g)[0] for c, g in zip(contexts, raw)])
                v, M, J = [np.asarray(s[k], float) for k in ('vfree', 'mobility', 'jacobian')]
                row = dict(original_system_sha256=item['system_sha256'], original_system=s, raw_gaps_m=raw.tolist(),
                           effective_gaps_m=effective.tolist(), policy=policy.NAME, dt_s=s['dt_s'])
                try:
                    velocity, health = analytic.solve(v, M, J, effective, s['dt_s'], s['friction'], s['tolerance'], s['maxiter'], end)
                    row.update(accepted=True, velocity=velocity.tolist(), health=health)
                except (RuntimeError, ValueError, np.linalg.LinAlgError, FloatingPointError) as error:
                    row.update(accepted=False, error=repr(error))
                reports.append(row); job.commit(OUT / ('held_%02d.json' % (len(reports)-1)), row)
                print('REVISED_GAP_HELD', len(reports)-1, row['accepted'], row.get('error', ''), flush=True)
        require(len(reports) == len(systems['failed_inner_systems']) == w['maximum_held_systems'], 'complete bounded held inventory')
        require(shutil.disk_usage(ROOT).free >= w['minimum_free_disk_bytes'], 'final disk reserve')
        api.verify_mapping(w['inputs']); api.verify_mapping(w['sources']); job.verify(d)
        r = dict(new_trajectory_steps=0, geometry_policy_tests_passed=True, all_held_systems_passed=all(z['accepted'] for z in reports),
                 independent_verification_pending=True, production_authorized=False, old_campaign_remains_failed=True,
                 contexts=contexts, boundary_geometry_checks=geometry_checks, invalid_input_controls_rejected=negative,
                 held_system_count=len(reports), held_passes=sum(z['accepted'] for z in reports),
                 original_residual_force_cone_dissipation_gates_retained=True, revised_gap_policy_explicit=True,
                 inputs={str(p):api.sha(p) for p in (CONTRACT, Path(__file__), Path(policy.__file__), job.DESIGN, source.OUT / 'failed_systems.json')},
                 artifacts={str(p):api.sha(p) for p in OUT.glob('held_*.json')},
                 claim='Zero-step candidate qualification of revised sphere gap operands only. No old numerical acceptance, installed repair or trajectory/campaign pass.')
        job.commit(OUT / 'results.json', r); job.commit(OUT / 'completion.json', dict(results_sha256=api.sha(OUT / 'results.json'), new_trajectory_steps=0))
        print('REVISED_GAP_QUALIFICATION', r['held_passes'], len(reports), api.sha(OUT / 'results.json'), flush=True)
    except Exception as error:
        job.commit(OUT / 'failure.json', dict(error=repr(error), traceback=traceback.format_exc(), new_trajectory_steps=0, utc=job.utc().isoformat()))
        raise


if __name__ == '__main__':
    run()
