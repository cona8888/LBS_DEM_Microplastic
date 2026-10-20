"""Non-advancing, original-equation checks of saved sphere endpoint systems.

No geometry, gap, pose, timestep, contact tolerance or trajectory is changed.
The Decimal diagnostic treats stored binary coordinates as exact numbers; it
does not purport to recover an exact physical pose from rounded coordinates.
"""
from pathlib import Path
from decimal import Decimal, localcontext
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'stage139_staging'), str(ROOT/'stage140_staging')]
import sphere_only_verification_v1 as parent
import sphere_dwell_refinement_v1 as dwell
api, engine, hot, fast = parent.api, parent.engine, parent.hot, parent.fast
np = api.np
BASE = 'signed_gap_endpoint_diagnosis_20260919'
OUT = ROOT/'stage142_evaluations'/BASE/'probe_01'


def assemble(spec, source):
    cfg = spec['config']; a, b, _ = cfg['prolate_semiaxes_m']
    api.require(a == b == cfg['prolate_semiaxes_m'][2], 'sphere only')
    cp = source['checkpoint']
    api.require(cp['state_sha256'] == api.digest(cp['state']), 'checkpoint state')
    x, p, q = map(np.array, (source['position_m'], source['orientation'], source['velocity_generalized']))
    field, data, metadata = api.fields.load(spec['seed'], spec['flow_factor'], spec['cpd'])
    api.require(metadata == spec['field_metadata'], 'field binding')
    geom = api.frozen.h.geometry_exact_v1.GrainGeometry(data['sand_centres_m'], data['sand_radii_m'], metadata['cell_length_m'])
    core = engine.runtime.core; inertial = hot.s50.s42
    mu = cfg['dynamic_viscosity_Pa_s']; rhop = cfg['particle_density_kg_m3']; rhof = cfg['fluid_density_kg_m3']
    u, grad = field.sample(x)
    background, _ = core.mechanics.free_motion(p, grad, u, a, b, mu, 1., 1., [0, 0, 0])
    stokes = inertial.stokes_generalized_resistance(p, a, b, mu)
    mass, _ = inertial.generalized_mass_matrix(p, a, b, rhop, rhof, cfg['added_mass_fraction']); mass[3:, 3:] = 0.
    body = np.r_[(rhop-rhof)*4*np.pi*a*b*b/3*np.array(cfg['gravity_m_s2']), np.zeros(3)]
    near = core.enrich(geom, geom.contacts(x, p, a, b, .2*max(geom.r)))
    lubrication, _ = core.lubrication_matrix(near, p, a, b, a, mu, .2, .01)
    trans = max(np.linalg.norm(q[:3]), np.linalg.norm(background[:3]), np.linalg.norm(body[:3])/np.linalg.eigvalsh(stokes[:3, :3]).min(), 1e-30)
    rot = max(np.linalg.norm(q[3:]), np.linalg.norm(background[3:]), 1e-30)/a
    n = cfg['numerics']
    dt0 = min(n['max_dt_s'], n['displacement_fraction']*b/trans, n['angle_limit_rad']/rot, n['relaxation_fraction']*np.linalg.eigvalsh(mass[:3, :3]).min()/np.linalg.eigvalsh(stokes[:3, :3]).max())
    re = inertial.finite_re.reynolds_number(q[:3]-background[:3], rhof, mu, 2*(a*b*b)**(1/3))
    drag = stokes.copy(); drag[:3, :3] *= inertial.finite_re.inertial_multiplier(re, inertial.finite_re.prolate_sphericity(a, b))

    def at_step(dt):
        contacts = geom.contacts(x, p, a, b, (trans+a*rot)*dt+1e-5*b)
        J, g, _ = hot.s50.s41._prepare_geometry(contacts, a)
        M = np.linalg.inv(mass/dt+drag+lubrication)
        v = M@(mass@q/dt+drag@background+body)
        diagnostic = []
        with localcontext() as context:
            context.prec = 80
            D = lambda z: Decimal.from_float(float(z))
            for k, gap, _, _ in contacts:
                delta = [D(geom.c[k, i])-D(x[i]) for i in range(3)]
                delta = [z-D(geom.L)*(z/D(geom.L)).to_integral_value() for z in delta]
                exact = sum(z*z for z in delta).sqrt()-D(a)-D(geom.r[k])
                diagnostic.append({'grain': int(k), 'raw_gap_m': float(gap), 'stored_coordinate_decimal_gap_m': str(exact), 'gap_difference_m': float(D(gap)-exact)})
        return (v, M, J, g, dt, cfg['friction_coefficient'], 1e-10, 25000), diagnostic
    return dt0, at_step


def main():
    parent.verify(api.read(parent.DESIGN)); dwell.verify(api.read(dwell.DESIGN))
    handoff = ROOT/'stage141_evaluations/fibre_identical_system_branch_check_20260918/handoff_01/results.json'
    api.require(api.sha(handoff) == '36c15a347e69ff75d2df6795d4d3272c8d13297ed2309705b5a1c0482e352810', 'verified handoff')
    api.verify_mapping(api.read(handoff)['binding_hashes'])
    pd = api.read(parent.DESIGN); dd = api.read(dwell.DESIGN)
    c = next(c for c in pd['cases'] if c['id'] == 'sphere_12_terminal')
    entries = [('initial', c['source'], c['spec'])]
    dc = next(c for c in dd['cases'] if c['factor'] == 1.)
    for segment in [2, 9]:
        p = dwell.RUN/dc['id']/f'segment_{segment:02d}/record.json'
        api.require(api.read(p.parent/'completion.json')['record_sha256'] == api.sha(p), 'endpoint seal')
        entries.append((f'endpoint_{segment:02d}', str(p), dc['spec']))
    OUT.mkdir(parents=True, exist_ok=False)
    protocol = {'question': 'Can the existing exact signed-gap active-mode solver handle the frozen matrices without tolerance relaxation?',
                'claim': 'First fixed-point matrices only, no trajectory, dwell or release inference.',
                'inputs': {str(p): api.sha(p) for p in [parent.DESIGN, dwell.DESIGN, handoff]+[e[1] for e in entries]},
                'source_sha256': api.sha(__file__), 'tests': 'Initial normal/half/quarter; two endpoints at remaining horizon and saved pending retry dt.',
                'acceptance': 'Unchanged Stage50 physical gates plus independent original contact residual/balance check; all raw signed gaps retained.',
                'physical_changes': [], 'trajectory_dispatch': False}
    api.write(OUT/'protocol.json', protocol)
    parent.old.prior.prior.configure()
    rows = []
    for name, source_path, spec in entries:
        source = api.read(source_path)['result']; dt0, system = assemble(spec, source)
        tests = [('normal', dt0), ('half', dt0/2), ('quarter', dt0/4)] if name == 'initial' else [('remaining', 1.3-source['time_s']), ('pending', source['checkpoint']['state']['pending_trial']['dt_s'])]
        for label, dt in tests:
            args, diagnostics = system(dt)
            row = {'id': name+'_'+label, 'source': source_path, 'source_sha256': api.sha(source_path), 'time_s': source['time_s'], 'dt_s': dt,
                   'system': [z.tolist() if isinstance(z, np.ndarray) else z for z in args], 'geometry_diagnostic': diagnostics, 'solvers': []}
            api.write(OUT/(row['id']+'_system.json'), row, raw=True)
            for solver_name, fn in [('sticking', fast.candidate), ('existing_mixed', engine.runtime.mixed.solve)]:
                start = time.perf_counter()
                try:
                    answer, h = parent.old.prior.scalar_scope._scoped(fn, *args)
                    passed = engine.local.independent_contact(*args[:6], answer, h)
                    item = {'solver': solver_name, 'returned': True, 'passed': passed, 'q': answer.tolist(), 'health': h}
                except (ValueError, RuntimeError, FloatingPointError, np.linalg.LinAlgError) as error:
                    item = {'solver': solver_name, 'returned': False, 'passed': False, 'error': str(error)}
                item['wall_s'] = time.perf_counter()-start; row['solvers'].append(item)
                print(row['id'], solver_name, item['passed'], item['wall_s'], item.get('error', ''), flush=True)
            api.write(OUT/(row['id']+'_result.json'), row, raw=True); rows.append(row)
    api.verify_mapping(protocol['inputs']); api.require(protocol['source_sha256'] == api.sha(__file__), 'source unchanged')
    result = {'rows': rows, 'all_mixed_passed': all(r['solvers'][1]['passed'] for r in rows), 'claim': protocol['claim'],
              'artifacts': {str(p): api.sha(p) for p in OUT.iterdir() if p.is_file()}}
    api.write(OUT/'results.json', result, raw=True)
    api.write(OUT/'completion.json', {'results_sha256': api.sha(OUT/'results.json'), 'protocol_sha256': api.sha(OUT/'protocol.json')})


if __name__ == '__main__':
    main()
