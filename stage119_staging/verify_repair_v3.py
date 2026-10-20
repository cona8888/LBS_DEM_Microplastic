"""Frozen local acceptance tests; no application trajectory dispatch."""
from pathlib import Path
import copy
import json
import sys
import time
from types import SimpleNamespace
import numpy as np
import repaired_runtime_v1 as runtime
import evaluate_probe_v1 as audit

api, probe = runtime.api, runtime.probe
ROOT = runtime.ROOT
BASE = 'contact_solver_repair_20260916'
DESIGN = ROOT/'stage119_designs'/BASE/'design_03.json'
OUT = ROOT/'stage119_evaluations'/BASE/'verification_03'


def prepare():
    probe.verify(api.read(probe.DESIGN))
    seal = probe.EVAL/'completion.json'
    api.verify_mapping(api.read(seal)['artifacts'])
    paths = [Path(m.__file__).resolve() for m in list(sys.modules.values()) if getattr(m,'__file__',None) and Path(m.__file__).suffix=='.py' and ROOT in Path(m.__file__).resolve().parents]
    paths += list(Path(__file__).parent.glob('*.py'))
    d = {'stage':'Stage119', 'scope':'Numerical repair verification, not calibration or physical validation.',
         'physics_changes':[], 'algorithm':'Failure-only scaled open/stick/slide mode enumeration. Original gaps and original Stage50 acceptance gates; no clipped or zero-gap replacement.',
         'acceptance':{'contact_residual':1e-10,'force_and_momentum':1e-8,'toy_velocity_abs_max':1e-11,
             'required_successful_probes':['accepted_control','failed_remaining','failed_half','failed_retry10','failed_without_endpoint_clip'],
             'required_fail_closed_probe':'failed_retry29','exact_original_accepted_control':True,'restart_exact':True},
         'negative_test_boundary':'The extreme retry29 matrix remains outside verified successful-solve range and must not return an inadmissible state. No universal contact solver robustness or uniqueness claimed.',
         'budget':{'local_probes':6,'max_small_mode_optimizer_evaluations':200,'local_test_wall_ceiling_s':120},
         'next_authorized':'Only after all local checks pass: declare a bounded checkpoint episode at three step caps and fresh seed-1 paired sphere/AR4 0.5-second sentinels at three caps. No population campaign.',
         'source_hashes':{str(p):api.sha(p) for p in paths},'inputs':{str(seal):api.sha(seal),str(probe.DESIGN):api.sha(probe.DESIGN)}}
    d['binding']=api.digest(d)
    DESIGN.parent.mkdir(parents=True,exist_ok=True);api.write(DESIGN,d)
    print('FROZEN',api.sha(DESIGN))


def verify(d):
    api.require(d['binding']==api.digest({k:v for k,v in d.items() if k!='binding'}),'design drift')
    api.verify_mapping(d['source_hashes']);api.verify_mapping(d['inputs'])
    probe.verify(api.read(probe.DESIGN))


def independent_contact(v,M,J,g,dt,mu,q,h):
    f=np.asarray(h['reactions']);A=J@M@J.T;vc=J@q;scale=max(np.linalg.norm(v),1e-15)
    residual=0.
    for k in range(len(g)):
        i=3*k;step=np.linalg.eigvalsh(A[i+1:i+3,i+1:i+3]).max()
        trial=f[i+1:i+3]-vc[i+1:i+3]/step
        project=trial*min(1,mu*f[i]/max(np.linalg.norm(trial),1e-300))
        residual=max(residual,abs(min(A[i,i]*f[i],vc[i]+g[k]/dt)),np.linalg.norm(f[i+1:i+3]-project)*step)
    force=J.T@f
    closure=np.linalg.norm(np.linalg.solve(M,q-v)-force)/max(np.linalg.norm(force),1e-30)
    work=sum(f[3*k+1:3*k+3]@vc[3*k+1:3*k+3] for k in range(len(g)))
    return bool(np.all(f[::3]>=0) and all(np.linalg.norm(f[3*k+1:3*k+3])<=mu*f[3*k]+1e-12*max(np.linalg.norm(f),1e-30) for k in range(len(g))) and residual/scale<=1e-10 and closure<=1e-8 and work<=1e-8*max(np.linalg.norm(f)*scale,1e-30))


def toys():
    cases=[('stick',[-1,.1,0,0,0,0],0,.3,[0,0,0,0,0,0]),
           ('slip',[-1,1,0,0,0,0],0,.3,[0,.7,0,0,0,0]),
           ('open',[1,.2,0,0,0,0],0,.3,[1,.2,0,0,0,0]),
           ('no_premature_contact',[-1,.1,0,0,0,0],2,.3,[-1,.1,0,0,0,0]),
           ('frictionless',[-1,1,0,0,0,0],0,0,[0,1,0,0,0,0]),
           ('gap_closure',[-1,1,0,0,0,0],.2,.3,[-.2,.76,0,0,0,0]),
           ('penetration_recovery',[-1,1,0,0,0,0],-.2,.3,[.2,.64,0,0,0,0])]
    rows=[]
    for name,v0,g,mu,expected in cases:
        for scale in [1.,1e-7,1e3]:
            M=np.eye(6);J=np.c_[np.eye(3),np.zeros((3,3))];v=np.asarray(v0)*scale;gap=np.array([g*scale])
            q,h=runtime.mixed.solve(v,M,J,gap,1.,mu,1e-10,25000)
            error=float(np.max(np.abs(q-np.asarray(expected)*scale))/scale)
            rows.append({'case':name,'scale':scale,'relative_scale_error':error,'health':h,
                         'passed':error<=1e-11 and independent_contact(v,M,J,gap,1.,mu,q,h)})
    return rows


def checkpoint_tests():
    core=runtime.core;old_inertial,old_time,old_sweep=core.inertial,core.time,core.geometry_tools.swept_gap
    state={'failure':False,'inject':True,'clock_budget':False}
    real=runtime.mixed.original.s42
    recovery={'value':False}
    def step(*args,**kwargs):
        if state['inject'] and not state['failure']:
            state['failure']=True
            raise RuntimeError('direct contact residual nonconvergence')
        return real.inertial_contact_step(*args,**kwargs)
    proxy=SimpleNamespace(finite_re=real.finite_re,stokes_generalized_resistance=real.stokes_generalized_resistance,
        generalized_mass_matrix=real.generalized_mass_matrix,inertial_contact_step=step,
        set_recovery_mode=lambda value:recovery.update(value=bool(value)), recovery_mode=lambda:recovery['value'])
    field=SimpleNamespace(sample=lambda x:(np.array([1e-4,0.,0.]),np.zeros((3,3))))
    geometry=SimpleNamespace(r=np.array([1e-4]),contacts=lambda *args:[])
    args=(field,geometry,[0.,0.,0.],[1.,0.,0.],[0.]*6,8e-5,8e-5,.001002,1380.,998.2,[0.,0.,-9.80665],.3,.01,.002)
    kwargs={'checkpoint_binding':'stage119-toy-only','wall_budget':1.,'max_dt':.0005,'trap_reference_speed':1e-4,'trap_dwell_time':.5}
    try:
        core.inertial=proxy;core.geometry_tools.swept_gap=lambda *a:1.
        core.time=SimpleNamespace(perf_counter=lambda:2. if state['clock_budget'] and state['failure'] else 0.)
        full=api.normalized(core.integrate(*args,**kwargs))
        state.update(failure=False,clock_budget=True);recovery['value']=False
        paused=api.normalized(core.integrate(*args,**kwargs));cp=paused['checkpoint']
        state.update(clock_budget=False)
        resumed=api.normalized(core.integrate(*args,**kwargs,checkpoint=cp))
        normalize=lambda r:{k:v for k,v in r.items() if k!='runtime_seconds'}
        checks={'budget_stops_before_uncommitted_trial':paused['status']=='incomplete_budget' and paused['time_s']==0.,
                'pending_halved_dt_saved':cp['state']['pending_trial']['dt_s']==.00025 and cp['state']['pending_trial']['attempt']==1,
                'explicit_rejected_reason_saved':cp['state']['rejected_trials'][0]['reason']=='direct contact residual nonconvergence',
                'exact_restart_after_rejection':normalize(full)==normalize(resumed),'completed':full['status']=='present_at_horizon'}
        for key in ['contract','state_sha256']:
            bad=copy.deepcopy(cp);bad[key]='tampered'
            try:core.integrate(*args,**kwargs,checkpoint=bad)
            except ValueError:checks['tamper_'+key]=True
            else:checks['tamper_'+key]=False
        return {'checks':checks,'passed':all(checks.values()),'full':full,'paused':paused,'resumed':resumed}
    finally:
        core.inertial=old_inertial;core.time=old_time;core.geometry_tools.swept_gap=old_sweep


def run():
    d=api.read(DESIGN);verify(d);OUT.mkdir(parents=True,exist_ok=False)
    started=time.perf_counter();raw=api.read(probe.DESIGN);ledger=[]
    toy=toys();api.write(OUT/'contact_toys.json',toy)
    restart=checkpoint_tests();api.write(OUT/'checkpoint_tests.json',restart,raw=True)
    for scenario in raw['scenarios']:
        runtime._calls.clear()
        with runtime.repair_scope():r=probe.execute(raw['spec'],scenario)
        r['stage119_repair_calls']=list(runtime._calls)
        api.write(OUT/(scenario['id']+'.json'),r)
        health=audit.physical_checks(r,raw['spec'])
        expected='solver_raised' if scenario['id']==d['acceptance']['required_fail_closed_probe'] else 'solver_returned'
        exact=scenario['id']!='accepted_control' or all(x==0 for x in r['positive_control'].values())
        passed=health['passed'] and r['status']==expected and exact
        ledger.append({'case':scenario['id'],'passed':passed,'status':r['status'],'health':health,'repair_calls':r['stage119_repair_calls']})
        print(scenario['id'],r['status'],'PASS',passed,flush=True)
    passed=all(r['passed'] for r in ledger+toy) and restart['passed']
    verify(d)
    result={'passed':passed,'local_solver_repair_verified':passed,'probe_ledger':ledger,'toy_count':len(toy),'toy_passed':sum(x['passed'] for x in toy),
        'checkpoint_checks':restart['checks'],'wall_s':time.perf_counter()-started,'design_sha256':api.sha(DESIGN),
        'scope':'Local endpoint repair verified; extreme retry29 intentionally fails closed. No application trajectory advanced or physical validation claimed.',
        'artifacts':{str(p):api.sha(p) for p in OUT.glob('*.json')}}
    api.write(OUT/'results.json',result);api.write(OUT/'completion.json',{'passed':passed,'results_sha256':api.sha(OUT/'results.json')})
    print('LOCAL_VERIFICATION',passed,'TOYS',sum(x['passed'] for x in toy),'/',len(toy),'RESTART',restart['checks'])
    return 0 if passed else 4


if __name__=='__main__':
    if sys.argv[1]=='prepare':prepare()
    else:raise SystemExit(run())




