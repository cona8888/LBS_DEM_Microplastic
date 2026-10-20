"""Prospective canonical and bounded moving-fibre inertia diagnostic.

Not contact-history selection, not a production or release campaign.
"""
from pathlib import Path
import copy
import json
import sys
import time
import traceback
import numpy as np
import rigid_rotation_v1 as model

api,engine,hot=model.api,model.engine,model.hot
prior=model.prior
ROOT=model.ROOT
BASE='bounded_rigid_rotation_20260921'
DESIGN=ROOT/'stage151_designs'/BASE/'design_01.json'
OUT=ROOT/'stage151_evaluations'/BASE/'qualification_01'


def prepare():
    sensitivity=api.read(prior.OUT/'results.json')
    api.require(sensitivity['passed'],'full-duration sphere sensitivity prerequisite')
    api.require(api.sha(prior.OUT/'results.json')==api.read(prior.OUT/'completion.json')['results_sha256'],'Stage150 seal')
    pd=api.read(prior.parent.DESIGN);prior.parent.verify(pd)
    case=next(c for c in pd['cases'] if c['id']=='fibre_10')
    sources={str(Path(m.__file__).resolve()):api.sha(m.__file__) for m in list(sys.modules.values())
             if getattr(m,'__file__',None) and Path(m.__file__).suffix=='.py' and ROOT in Path(m.__file__).resolve().parents}
    sources[str(Path(__file__).resolve())]=api.sha(__file__)
    d={'stage':'Stage151','question':'Does an explicit rigid-body rotational-inertia option pass canonical mechanics and a bounded moving-fibre timestep check?',
       'case':case,'mode':model.MODE,'physical_change':'Solid rotational inertia retained with old-state gyroscopic torque. Translational added mass, drag, lubrication and cold Coulomb contact selection unchanged.',
       'equation':'I(p)*omega_dot + omega cross (I(p)*omega) = hydrodynamic + contact torque; q_rot=a*omega. Backward-Euler damping/acceleration, explicit old-state gyro, first-order pose update.',
       'reference':'https://ocw.mit.edu/courses/2-12-introduction-to-robotics-fall-2005/c7caaa2376b8ec01e270328a3b80b029_chapter7.pdf',
       'reference_location':'H. Harry Asada, Introduction to Robotics, Chapter7, section7.1.1, equation7.1.3; inertial-frame Euler torque equation.',
       'canonical':{'torque_free_duration_s':0.1,'steps':[100,200,400],'finest_L_relative_max':0.005,'finest_energy_relative_max':0.005,'error_reduction_ratio_max':0.7,
                    'principal_spin_steps':[16,32,64],'spin_end_error_over_initial_max':0.004},
       'moving':{'window_s':0.002,'factors':[1.,0.5,0.25],'maximum_steps':6000,'segment_budget_s':45.,
                 'limits':{'position_over_b':1e-4,'axis_vector_norm':1e-4,'generalized_velocity_relative':0.005},
                 'error_reduction_ratio_max':0.8,'noise_floor':1e-10,
                 'acceptance':'All common horizons and health pass; fine-pair position/b, axis, q/U differences below limits and <=0.8 of coarse-pair differences unless both are below noise floor. Model-versus-quasistatic differences are reported, not fitted away.'},
       'restart':'At the finest level, split after half the recorded accepted steps and require exact final checkpoint state and pose/velocity/clock. No wall-budget truncation is accepted as a completed local window.',
       'negative_controls':['wrong checkpoint mode binding rejected','gyro omitted in non-principal torque-free prolate must fail momentum conservation'],
       'scope':'Diagnostic model change from an inherited moving-fibre checkpoint. Not a fresh full-path trajectory, globally qualified integrator, rotational added-fluid inertia, contact-history rule, population release or experimental validation.',
       'sources':sources,'inputs':{str(p):api.sha(p) for p in [prior.OUT/'results.json',prior.OUT/'completion.json',prior.parent.DESIGN,Path(case['source'])]},
       'generated_integrator_sha256':api.digest(model.GENERATED_SOURCE)}
    d['binding']=api.digest(d);DESIGN.parent.mkdir(parents=True,exist_ok=True);api.write(DESIGN,d)
    print('FROZEN',api.sha(DESIGN),flush=True)


def verify(d):
    api.require(d['binding']==api.digest({k:v for k,v in d.items() if k!='binding'}),'design binding')
    api.verify_mapping(d['sources']);api.verify_mapping(d['inputs'])
    api.require(api.digest(model.GENERATED_SOURCE)==d['generated_integrator_sha256'],'generated integrator')


def props(p,cfg):
    a,b,_=cfg['prolate_semiaxes_m']
    return model.core.inertial.generalized_mass_matrix(p,a,b,cfg['particle_density_kg_m3'],cfg['fluid_density_kg_m3'],cfg['added_mass_fraction'])[0]


def canonical(d):
    cfg=d['case']['spec']['config'];a,b,_=cfg['prolate_semiaxes_m'];rho=cfg['particle_density_kg_m3']
    p=np.array([0.,0.,1.]);M=props(p,cfg);mass=rho*4*np.pi*a*b*b/3
    expected=np.diag([mass*(a*a+b*b)/5,mass*(a*a+b*b)/5,2*mass*b*b/5])/(a*a)
    mass_ok=np.allclose(M[3:,3:],expected,rtol=1e-14,atol=0)
    q0=np.r_[np.zeros(3),a*np.array([3.,4.,2.])]
    L0=a*M[3:,3:]@q0[3:];E0=.5*q0[3:]@M[3:,3:]@q0[3:]
    records=[]
    for n in d['canonical']['steps']:
        for gyro in [True,False]:
            axis=p.copy();q=q0.copy();dt=d['canonical']['torque_free_duration_s']/n
            for _ in range(n):
                mm=props(axis,cfg);load=np.zeros(6)
                if gyro:load[3:]=-model.gyro_load(mm,q,a)
                # Exact algebraic no-drag/no-contact specialization of the BE step.
                q=np.linalg.solve(mm,mm@q+dt*load)
                _,axis=model.core.mechanics.advance_pose(np.zeros(3),axis,q,a,dt)
            mf=props(axis,cfg);Lf=a*mf[3:,3:]@q[3:];Ef=.5*q[3:]@mf[3:,3:]@q[3:]
            records.append({'steps':n,'gyro':gyro,'angular_momentum_relative_error':float(np.linalg.norm(Lf-L0)/np.linalg.norm(L0)),
                            'energy_relative_error':float(abs(Ef-E0)/E0),'axis':axis.tolist()})
    corrected=[r for r in records if r['gyro']];bad=[r for r in records if not r['gyro']]
    decay=[]
    C=model.core.inertial.stokes_generalized_resistance(p,a,b,cfg['dynamic_viscosity_Pa_s'])
    tau=float(M[5,5]/C[5,5]);w0=.2;qspin=np.array([0.,0.,0.,0.,0.,a*w0]);exact=a*w0*np.exp(-1.)
    for n in d['canonical']['principal_spin_steps']:
        q=qspin.copy();dt=tau/n
        for _ in range(n):
            load=np.r_[np.zeros(3),-model.gyro_load(M,q,a)]
            q,h=model.core.inertial.inertial_contact_step(q,np.zeros(6),load,C,np.zeros((6,6)),M,[],a,dt,cfg['friction_coefficient'],
                       cfg['fluid_density_kg_m3'],cfg['dynamic_viscosity_Pa_s'],2*(a*b*b)**(1/3),model.core.inertial.finite_re.prolate_sphericity(a,b))
        decay.append({'steps':n,'error_over_initial':float(abs(q[5]-exact)/(a*w0)),'momentum_residual':h['momentum_residual']})
    positive=(corrected[-1]['angular_momentum_relative_error']<=d['canonical']['finest_L_relative_max'] and corrected[-1]['energy_relative_error']<=d['canonical']['finest_energy_relative_max']
        and all(b['angular_momentum_relative_error']<=d['canonical']['error_reduction_ratio_max']*a['angular_momentum_relative_error'] for a,b in zip(corrected,corrected[1:])))
    negative=bad[-1]['angular_momentum_relative_error']>d['canonical']['finest_L_relative_max']
    spin=(decay[-1]['error_over_initial']<=d['canonical']['spin_end_error_over_initial_max'] and all(b['error_over_initial']<.7*a['error_over_initial'] for a,b in zip(decay,decay[1:])))
    original=engine.runtime.core
    with model.scope(False):disabled_identity=engine.runtime.core is original
    with model.scope(True):enabled_distinct=engine.runtime.core is not original
    restoration=engine.runtime.core is original
    result={'passed':bool(mass_ok and positive and negative and spin and disabled_identity and enabled_distinct and restoration),
            'mass_formula':bool(mass_ok),'torque_free':records,'principal_spin_tau_s':tau,'principal_spin':decay,
            'omitted_gyro_negative_control_rejected':bool(negative),'default_off_exact_dispatch':disabled_identity,'scope_restoration':restoration}
    api.write(OUT/'canonical.json',result,raw=True);print('CANONICAL',result['passed'],flush=True)
    return result


def integrate_case(d,factor,enabled,*,steps=None,original_horizon=False):
    spec=copy.deepcopy(d['case']['spec']);source=api.read(d['case']['source'])['result']['checkpoint']
    if not original_horizon:
        spec['horizon_s']=source['state']['t']+d['moving']['window_s'];spec['horizon_pv']=spec['horizon_s']*spec['field_metadata']['pv_per_second']
    for k in api.DT_CONTROLS:spec['config']['numerics'][k]*=factor
    binding=api.digest([d['binding'],factor,enabled,original_horizon]);cp=model.checkpoint(spec,binding,source,enabled)
    with hot.scope(),model.scope(enabled):
        r,rows=engine.runtime.execute(spec,binding,checkpoint=cp,pause=cp['state']['steps']+(steps or d['moving']['maximum_steps']))
    health=engine.prior.reference.independent_health(r,spec);clock=prior.audit.clock_chain(cp['state']['t'],rows,r['time_s'])
    result={'factor':factor,'enabled':enabled,'spec':spec,'result':r,'rows':rows,'health':health,'clock':clock,'input_checkpoint_sha256':api.digest(cp),
            'effective_binding':model.binding_for(binding,enabled),'design_sha256':api.sha(DESIGN),
            'passed':bool(health['passed'] and clock['passed'] and not r.get('stage119_repair_calls') and (r['status']=='paused_checkpoint' if steps else r['status']=='present_at_horizon'))}
    return result


def compare(a,b,spec):
    scale=spec['config']['target_mean_interstitial_velocity_m_s'];minor=spec['config']['prolate_semiaxes_m'][1]
    return {'position_over_b':float(np.linalg.norm(np.array(a['position_m'])-b['position_m'])/minor),
            'axis_vector_norm':float(np.linalg.norm(np.array(a['orientation'])-b['orientation'])),
            'generalized_velocity_relative':float(np.linalg.norm(np.array(a['velocity_generalized'])-b['velocity_generalized'])/scale)}


def run():
    d=api.read(DESIGN);verify(d);OUT.mkdir(parents=True,exist_ok=False)
    api.write(OUT/'protocol.json',d)
    canon=canonical(d)
    if not canon['passed']:raise RuntimeError('canonical gate failed; no transport')
    prior.parent.old.prior.prior.configure();hot.warmup()
    # Wrong-mode checkpoint is structurally rejected before advancing any state.
    spec=d['case']['spec'];source=api.read(d['case']['source'])['result']['checkpoint'];binding=api.digest([d['binding'],'negative'])
    wrong=model.checkpoint(spec,binding,source,False);rejected=False
    try:
        with hot.scope(),model.scope(True):engine.runtime.execute(spec,binding,checkpoint=wrong,pause=wrong['state']['steps']+1)
    except ValueError as e:rejected='checkpoint binding or integrity mismatch' in str(e)
    api.write(OUT/'checkpoint_negative.json',{'wrong_mode_rejected':rejected})
    api.require(rejected,'cross-model checkpoint silently accepted')
    baseline=integrate_case(d,1.,False);api.write(OUT/'quasistatic.json',baseline,raw=True)
    print('QUASISTATIC',baseline['passed'],baseline['result']['status'],flush=True)
    api.require(baseline['passed'],'bounded quasistatic baseline failed')
    cases=[]
    for factor in d['moving']['factors']:
        rec=integrate_case(d,factor,True);api.write(OUT/f'rigid_{factor}.json',rec,raw=True);cases.append(rec)
        print('RIGID',factor,rec['passed'],rec['result']['status'],len(rec['rows']),flush=True)
        if not rec['passed']:raise RuntimeError('bounded moving-fibre gate failed; no automatic extension')
    errors=[compare(a['result'],b['result'],b['spec']) for a,b in zip(cases,cases[1:])]
    convergence=all(errors[-1][k]<=lim and (errors[-1][k]<=d['moving']['error_reduction_ratio_max']*errors[0][k] or max(errors[-1][k],errors[0][k])<d['moving']['noise_floor']) for k,lim in d['moving']['limits'].items())
    model_difference=compare(baseline['result'],cases[-1]['result'],cases[-1]['spec'])
    restart_ok=False
    if convergence:
        factor=d['moving']['factors'][-1]
        first=integrate_case(d,factor,True,steps=max(1,len(cases[-1]['rows'])//2))
        api.write(OUT/'restart_first.json',first,raw=True)
        api.require(first['passed'],'restart first segment')
        cp=first['result']['checkpoint'];spec=first['spec'];binding=api.digest([d['binding'],factor,True,False])
        with hot.scope(),model.scope(True):
            last,rows=engine.runtime.execute(spec,binding,checkpoint=cp,pause=cp['state']['steps']+d['moving']['maximum_steps'])
        clock=prior.audit.clock_chain(cp['state']['t'],rows,last['time_s']);health=engine.prior.reference.independent_health(last,spec)
        restart_ok=(last['checkpoint']['state_sha256']==cases[-1]['result']['checkpoint']['state_sha256'] and clock['passed'] and health['passed'] and not last.get('stage119_repair_calls'))
        api.write(OUT/'restart_second.json',{'passed':restart_ok,'result':last,'rows':rows,'clock':clock,'health':health},raw=True)
        print('RESTART',restart_ok,flush=True)
    verify(d)
    result={'stage':'Stage151','passed':bool(convergence and restart_ok),'canonical_passed':canon['passed'],'wrong_checkpoint_mode_rejected':rejected,'exact_restart':bool(restart_ok),
            'timestep_pair_errors':errors,'quasistatic_to_rigid_finest_difference':model_difference,
            'new_steps':[len(r['rows']) for r in cases],'physical_window_s':d['moving']['window_s'],
            'claim':d['scope'],'next':'No production promotion. If local tests pass, test longer contact-onset/release windows; contact-history selection remains a separate question.',
            'design_sha256':api.sha(DESIGN),'artifacts':{str(p):api.sha(p) for p in OUT.iterdir() if p.is_file()}}
    api.write(OUT/'results.json',result,raw=True);api.write(OUT/'completion.json',{'results_sha256':api.sha(OUT/'results.json'),'passed':result['passed']})
    print('STAGE151_PASS',result['passed'],flush=True)
    return 0 if result['passed'] else 4


if __name__=='__main__':
    try:
        if sys.argv[1]=='prepare':prepare()
        elif sys.argv[1]=='run':raise SystemExit(run())
        else:raise ValueError('unknown command')
    except Exception as exc:
        if OUT.exists() and not (OUT/'failure.json').exists():api.write(OUT/'failure.json',{'error':repr(exc),'traceback':traceback.format_exc()})
        raise
