"""Bounded read-only Stage155 replay and an analytical rigid-impact counterexample.

No application dynamics, initial state, acceptance threshold or old result changes.
The diagnostic distinguishes step-averaged impulsive reactions from finite forces.
"""
from pathlib import Path
import copy
import datetime
import os
import sys
import numpy as np
from scipy.linalg import eigvalsh

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'stage155_staging'))
import contact_transitions_v1 as old

api, model = old.api, old.model
core = model.core
backend = old.engine.runtime.probe.RECOVERY
BASE = 'impact_diagnosis_20260922'
DESIGN = ROOT / 'stage156_designs' / BASE / 'design_01.json'
OUT = ROOT / 'stage156_evaluations' / BASE / 'diagnosis_01'


def piecewise_l1(rows_a, rows_b, start, stop, scale):
    """Exact integral of norm difference of the implemented interval velocities.

    Each accepted q is constant on its preceding pose-update interval. No event
    alignment, masking, smoothing, or resampling approximation is used.
    """
    ta = np.array([r['time_s'] for r in rows_a])
    tb = np.array([r['time_s'] for r in rows_b])
    qa = np.array([r['velocity_generalized'] for r in rows_a])
    qb = np.array([r['velocity_generalized'] for r in rows_b])
    assert ta[-1] == tb[-1] == stop and start < min(ta[0], tb[0])
    times = np.unique(np.r_[start, ta, tb])
    mid = times[:-1] + .5 * np.diff(times)
    delta = qa[np.searchsorted(ta, mid)] - qb[np.searchsorted(tb, mid)]
    errors = np.linalg.norm(delta, axis=1) / scale
    integral = float(errors @ np.diff(times))
    return {'mean_norm_over_scale': integral / (stop-start),
            'integrated_norm_over_scale_s': integral,
            'interval_velocity_sup_over_scale': float(errors.max())}


def impact_toy():
    # Unit mass/speed; unilateral wall x>=0; zero restitution, no other forces.
    # Same implicit gap law as the application: v_next=max(v_old,-x_old/h).
    # Impact at 1/3, so dyadic grids never align it and the phase alternates.
    out = []
    for n in [32, 64, 128, 256, 512]:
        h = 1/n
        x, v = 1/3, -1.
        t = 0.
        rows, impulses, energies = [], [], []
        max_x = 0.
        for k in range(n):
            vn = max(v, -x/h)
            impulse = vn-v
            xn = x+h*vn
            t = (k+1)*h
            max_x = max(max_x, abs(xn-max(1/3-t, 0.)))
            impulses.append(impulse)
            energies.append(.5*(vn*vn-v*v))
            rows.append({'time_s': t, 'velocity_generalized': [vn]})
            x, v = xn, vn
        times = np.unique(np.r_[0., [r['time_s'] for r in rows], 1/3])
        mid = times[:-1] + np.diff(times)/2
        q = np.array([r['velocity_generalized'][0] for r in rows])
        approx = q[np.searchsorted([r['time_s'] for r in rows], mid)]
        exact = np.where(mid < 1/3, -1., 0.)
        errors = abs(approx-exact)
        node_t = np.r_[0., [r['time_s'] for r in rows]]
        node_q = np.r_[-1., q]
        # Both one-sided exact limits are tested at impact; the approximate
        # linearly interpolated q is continuous, and cannot approximate a jump
        # uniformly. This is the original Stage155 reconstruction convention.
        probes = np.unique(np.r_[node_t, 1/3])
        linear = np.interp(probes,node_t,node_q)
        linear_error = max(float(max(abs(linear-np.where(probes<1/3,-1.,0.)))),
                           abs(float(np.interp(1/3,node_t,node_q))+1.))
        row = {'steps': n, 'dt_s': h, 'maximum_position_error': max_x,
               'velocity_sup_error': float(max(errors)),
               'original_linear_velocity_sup_error': linear_error,
               'velocity_L1_error': float(errors @ np.diff(times)),
               'total_impulse': float(sum(impulses)),
               'kinetic_energy_change': float(sum(energies)),
               'peak_step_average_reaction': max(impulses)/h,
               'no_energy_creation': max(energies) <= 1e-15,
               'nonpenetration': x >= -1e-15}
        out.append(row)
    checks = {'exact_total_impulse': all(abs(r['total_impulse']-1.)<1e-14 for r in out),
              'exact_energy_loss': all(abs(r['kinetic_energy_change']+.5)<1e-14 for r in out),
              'positions_at_grid_points_exact': max(r['maximum_position_error'] for r in out)<1e-14,
              'L1_halves': all(abs(b['velocity_L1_error']/a['velocity_L1_error']-.5)<1e-12 for a,b in zip(out,out[1:])),
              'sup_error_does_not_vanish': min(r['velocity_sup_error'] for r in out)>.6,
              'original_linear_sup_cannot_resolve_jump': min(r['original_linear_velocity_sup_error'] for r in out)>=.5,
              'dissipative_and_admissible': all(r['no_energy_creation'] and r['nonpenetration'] for r in out)}
    # Function tests: identity, time partition and vector norm integration.
    r = [{'time_s': .5, 'velocity_generalized': [1., 0.]}, {'time_s': 1., 'velocity_generalized': [0., 0.]}]
    z = [{'time_s': 1., 'velocity_generalized': [0., 0.]}]
    checks['L1_unit_tests'] = piecewise_l1(r, r, 0., 1., 1.)['mean_norm_over_scale'] == 0. and piecewise_l1(r,z,0.,1.,1.)['mean_norm_over_scale'] == .5
    return {'passed': all(checks.values()), 'checks': checks, 'rows': out,
            'meaning': 'Analytical counterexample: uniform instantaneous velocity accuracy is not a consistent qualification gate for a nonsmooth impact using step-averaged velocities. This does not prove the application trajectory accurate.'}


def prepare():
    old.verify(api.read(old.DESIGN))
    ev = api.read(old.OUT/'results.json')
    aud = api.read(old.AUDIT/'results.json')
    api.require(not ev['passed'] and aud['audit_integrity_passed'] and not aud['scientific_gates_passed'], 'verified failed prior')
    inputs = dict(ev['artifacts'])
    for folder in [old.OUT, old.AUDIT, old.OUT.parent/'failure_localization_01']:
        api.require(api.read(folder/'completion.json')['results_sha256'] == api.sha(folder/'results.json'), 'prior seal')
        for p in [folder/'results.json',folder/'completion.json']:
            inputs[str(p)] = api.sha(p)
    inputs[str(old.DESIGN)] = api.sha(old.DESIGN)
    d = {'stage': 'Stage156', 'question': 'Are Stage155 peak discrepancies contact-impulse/initialization effects or a replay/closure defect?',
         'application_changes': [], 'selection': {'first_steps_per_level': 8, 'engagement_neighbourhood_s': [.57036,.57044]},
         'replay_velocity_tolerance_over_U': 1e-8, 'momentum_tolerance': 1e-8,
         'toy': 'Unit mass strikes x=0 at t=1/3 with speed -1, no force, no friction, inelastic gap-complementarity update. 32,64,128,256,512 steps to t=1.',
         'claim': 'Read-only diagnosis and analytical verification of error metrics. No retrospective acceptance of Stage155 and no production or release-fraction claim.',
         'budget': {'maximum_frozen_pose_calls': 180, 'workers': 1, 'threads': 1},
         'sources': {str(Path(m.__file__).resolve()): api.sha(m.__file__) for m in list(sys.modules.values())
                     if getattr(m,'__file__',None) and Path(m.__file__).suffix=='.py' and ROOT in Path(m.__file__).resolve().parents},
         'inputs': inputs,
         'literature': {'authors': 'David Stewart and J. C. Trinkle', 'title': 'An Implicit Time-Stepping Scheme for Rigid Body Dynamics with Coulomb Friction',
                        'url': 'https://www.researchgate.net/profile/Jc-jeff-Trinkle/publication/221071311_An_Implicit_Time-Stepping_Scheme_for_Rigid_Body_Dynamics_with_Coulomb_Friction/links/55451e6e0cf234bdb21d50fd/An-Implicit-Time-Stepping-Scheme-for-Rigid-Body-Dynamics-with-Coulomb-Friction.pdf',
                        'support': 'Primary author paper, pp1-3: impulse-momentum stepping handles finite and impulsive reactions. The toy counterexample here is our own derivation, not an assertion that our full solver is their method.'}}
    d['binding'] = api.digest(d)
    DESIGN.parent.mkdir(parents=True,exist_ok=True)
    api.write(DESIGN,d)
    print('FROZEN',api.sha(DESIGN),flush=True)


def verify(d):
    api.require(d['binding']==api.digest({k:v for k,v in d.items() if k!='binding'}),'design binding')
    api.verify_mapping(d['sources']); api.verify_mapping(d['inputs'])
    old.verify(api.read(old.DESIGN))


def replay(field, geometry, spec, state, dt):
    cfg = spec['config']; a,b,_ = cfg['prolate_semiaxes_m']
    x,p,q = [np.asarray(state[k],float) for k in ['x','p','q']]
    mu,rhop,rhof = [cfg[k] for k in ['dynamic_viscosity_Pa_s','particle_density_kg_m3','fluid_density_kg_m3']]
    fluid,grad = field.sample(x)
    bg,_ = core.mechanics.free_motion(p,grad,fluid,a,b,mu,1.,1.,[0,0,0])
    R = backend.stokes_generalized_resistance(p,a,b,mu)
    M,_ = backend.generalized_mass_matrix(p,a,b,rhop,rhof,cfg['added_mass_fraction'])
    load = np.r_[(rhop-rhof)*4*np.pi*a*b*b/3*np.array(cfg['gravity_m_s2']),np.zeros(3)]
    load[3:] -= model.original.gyro_load(M,q,a)
    near = core.enrich(geometry,geometry.contacts(x,p,a,b,.2*float(max(geometry.r))))
    L,_ = core.lubrication_matrix(near,p,a,b,a,mu,.2,.01)
    trans = max(np.linalg.norm(q[:3]),np.linalg.norm(bg[:3]),np.linalg.norm(load[:3])/max(np.linalg.eigvalsh(R[:3,:3]).min(),1e-30),1e-30)
    rot = max(np.linalg.norm(q[3:]),np.linalg.norm(bg[3:]),1e-30)/a
    contacts = geometry.contacts(x,p,a,b,(trans+a*rot)*dt+1e-5*b)
    backend.set_recovery_mode(state.get('recovery',False))
    new,h = backend.inertial_contact_step(q,bg,load,R,L,M,contacts,a,dt,cfg['friction_coefficient'],rhof,mu,2*(a*b*b)**(1/3),backend.finite_re.prolate_sphericity(a,b))
    J,gaps,_ = backend.stage41._prepare_geometry(contacts,a)
    F = np.asarray(h['contact']['reactions']); reaction = J.T@F if len(F) else np.zeros(6)
    D=R.copy(); D[:3,:3] *= h['finite_re_multiplier']
    applied = D@(bg-new)-L@new+load
    change=.5*(new@M@new-q@M@q)
    numerical_loss=.5*((new-q)@M@(new-q))
    work=dt*float(new@(applied+reaction))
    U=cfg['target_mean_interstitial_velocity_m_s']
    return new, {'dt_s':dt,'contacts':[{'grain_id':int(c[0]),'gap_m':float(c[1]),'normal_velocity_old_m_s':float(core.lubrication.normal_jacobian(c[2],c[3],a)@q),
                'normal_reaction_N':float(F[3*i]),'normal_impulse_N_s':float(dt*F[3*i])} for i,c in enumerate(contacts)],
                'velocity_change_over_U':float(np.linalg.norm(new-q)/U),'scaled_rotational_change_over_U':float(np.linalg.norm(new[3:]-q[3:])/U),
                'momentum_residual':h['momentum_residual'],'contact_residual':h['contact']['residual'],
                'force_residual':h['contact']['force_residual'],'kinetic_change_frozen_mass_J':float(change),
                'implicit_numerical_loss_J':float(numerical_loss),'contact_work_J':float(dt*new@reaction),
                'work_balance_relative':float(abs(change+numerical_loss-work)/max(abs(change),numerical_loss,abs(work),1e-30)),
                'fastest_Stokes_tau_s':float(eigvalsh(M,R)[0]),'fastest_lubricated_tau_s':float(eigvalsh(M,D+L)[0]),
                'impulse_generalized':(dt*reaction).tolist(),'state':api.normalized(state)}


def run():
    d=api.read(DESIGN);verify(d); OUT.mkdir(parents=True,exist_ok=False)
    api.write(OUT/'launch.json',{'pid':os.getpid(),'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'design_sha256':api.sha(DESIGN),'python':sys.version})
    toy=impact_toy(); api.write(OUT/'analytical_toy.json',toy); api.require(toy['passed'],'analytical metric counterexample')
    old.parent.configure(); prior=api.read(old.DESIGN)
    spec=prior['base_spec'];field,data,metadata=api.fields.load(spec['seed'],spec['flow_factor'],spec['cpd'])
    geometry=core.geometry_tools.GrainGeometry(data['sand_centres_m'],data['sand_radii_m'],metadata['cell_length_m'])
    reports=[];calls=0
    with old.hot.scope(),old.engine.runtime.repair_scope():
        for wi,w in enumerate(prior['windows']):
            seed=old.read_record(old.RUN/w['id']/'seed.json')['result']['checkpoint']['state']
            recs=[old.join_case(prior,wi,f) for f in old.FACTORS]
            U=spec['config']['target_mean_interstitial_velocity_m_s']
            window={'id':w['id'],'levels':[],'L1_diagnostic_only':[piecewise_l1(r['rows'],recs[-1]['rows'],seed['t'],w['horizon_s'],U) for r in recs[:-1]]}
            for f,r in zip(old.FACTORS,recs):
                selected=[i for i,row in enumerate(r['rows']) if i<d['selection']['first_steps_per_level'] or (wi==0 and d['selection']['engagement_neighbourhood_s'][0]<=row['time_s']<=d['selection']['engagement_neighbourhood_s'][1])]
                samples=[]
                for i in selected:
                    row=r['rows'][i]
                    prev=seed if i==0 else {'x':r['rows'][i-1]['position_m'],'p':r['rows'][i-1]['orientation'],'q':r['rows'][i-1]['velocity_generalized'],'t':r['rows'][i-1]['time_s'],'recovery':seed['recovery']}
                    calls+=1;api.require(calls<=d['budget']['maximum_frozen_pose_calls'],'call cap')
                    q,detail=replay(field,geometry,r['spec'],prev,row['dt_s'])
                    detail.update(time_s=row['time_s'],step_index=i,replay_error_over_U=float(np.linalg.norm(q-row['velocity_generalized'])/U))
                    samples.append(detail)
                window['levels'].append({'factor':f,'samples':samples})
            reports.append(window)
    samples=[s for w in reports for level in w['levels'] for s in level['samples']]
    checks={'replay_matches_all_selected_steps':max(s['replay_error_over_U'] for s in samples)<=d['replay_velocity_tolerance_over_U'],
            'momentum_closes':max(s['momentum_residual'] for s in samples)<=d['momentum_tolerance'],
            'discrete_work_balance':max(s['work_balance_relative'] for s in samples)<=1e-8,
            'toy_passed':toy['passed']}
    result={'stage':'Stage156','diagnostic_integrity_passed':all(checks.values()),'checks':checks,'windows':reports,'toy':toy,
            'frozen_pose_calls':calls,'maximum_replay_error_over_U':max(s['replay_error_over_U'] for s in samples),
            'maximum_work_balance_relative':max(s['work_balance_relative'] for s in samples),
            'prior_stage155_scientific_passed':False,'application_accuracy_accepted':False,'production_promotion':False,
            'design_sha256':api.sha(DESIGN),'claim':d['claim']}
    verify(d);api.write(OUT/'results.json',result,raw=True);api.write(OUT/'completion.json',{'results_sha256':api.sha(OUT/'results.json'),'diagnostic_integrity_passed':result['diagnostic_integrity_passed']})
    print('DIAGNOSIS',checks,'calls',calls,'replay',result['maximum_replay_error_over_U'],flush=True)
    api.require(result['diagnostic_integrity_passed'],'diagnostic integrity')


if __name__=='__main__':
    if sys.argv[1:] == ['prepare']: prepare()
    elif sys.argv[1:] == ['run']: run()
    elif sys.argv[1:] == ['selftest']: print(impact_toy())
    else: raise ValueError('Use prepare, run or selftest')
