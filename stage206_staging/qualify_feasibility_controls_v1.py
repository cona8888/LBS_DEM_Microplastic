"""Manufactured equations, unmodified-success controls, adversarial audit tests."""
from pathlib import Path
import copy,os,time,traceback
import numpy as np
import authenticate_failed_system_v1 as source
import two_contact_cone_feasibility_v1 as candidate
import audit_cone_feasibility_v1 as auditor
import qualify_two_contact_held_v1 as independent
job,api,ROOT=source.job,source.api,source.ROOT
BASE=ROOT/'stage206_evaluations/contact_failure_20260930'
OUT=BASE/'controls_qualification_01'
PROTOCOL=ROOT/'stage206_designs/contact_failure_20260930/controls_protocol_01.json'

def mutate(value,key,replacement):
    if isinstance(value,dict):
        if value.get('solver')==candidate.NAME:value[key]=copy.deepcopy(replacement)
        for x in value.values():mutate(x,key,replacement)
    elif isinstance(value,list):
        for x in value:mutate(x,key,replacement)

def run():
    d=api.read(job.DESIGN);job.verify(d);protocol=api.read(PROTOCOL);stop=time.time()+1800
    files=[PROTOCOL,job.DESIGN,Path(__file__),Path(candidate.__file__),Path(auditor.__file__),Path(independent.__file__),source.OUT/'failed_systems.json']
    for label in ('held_qualification_01','outer_qualification_01'):
        p=BASE/label/'results.json';api.require(api.read(p)['passed'] and api.read(p.parent/'completion.json')['results_sha256']==api.sha(p),'passed sealed prerequisite');files.append(p)
    manufactured_root=ROOT/'stage201_evaluations/contact_repair_20260928/manufactured_qualification_02'
    files+=list(manufactured_root.glob('*.json'))
    goodpath=BASE/'outer_qualification_01/fixture_27.json';files.append(goodpath)
    inputs={str(p):api.sha(p) for p in files}
    OUT.mkdir(parents=True,exist_ok=False);job.commit(OUT/'launch.json',dict(pid=os.getpid(),utc=job.utc().isoformat(),inputs=inputs,new_trajectory_steps=0))
    checks={};manufactured=[];guards=[];failure=None
    try:
        a,b=candidate.scope.__wrapped__,candidate.prior.scope.__wrapped__
        checks['identical_dispatch_bytecode']=a.__code__ is b.__code__
        checks['only_dispatch_solve_changed']=[n for n in a.__code__.co_names if n in a.__globals__ and a.__globals__[n] is not b.__globals__.get(n)]==['solve']
        checks['identical_kernel_bytecode']=auditor.kernel.__code__ is job.kernel.evaluate.__code__
        checks['only_kernel_association_changed']=[n for n in auditor.kernel.__code__.co_names if n in auditor.kernel.__globals__ and auditor.kernel.__globals__[n] is not job.kernel.evaluate.__globals__.get(n)]==['association']
        sentinel=(np.arange(6.),{'unmodified_success':True});old=candidate.prior.solve
        try:
            candidate.prior.solve=lambda *args:sentinel
            checks['unmodified_success_same_object']=candidate.solve(*([None]*9)) is sentinel
            def unrelated(*args):raise RuntimeError('unrelated failure sentinel')
            candidate.prior.solve=unrelated
            try:candidate.solve(*([None]*9))
            except RuntimeError as error:checks['unrelated_failure_preserved']=str(error)=='unrelated failure sentinel'
            else:checks['unrelated_failure_preserved']=False
        finally:candidate.prior.solve=old
        checks['prior_binding_restored']=candidate.prior.solve is old
        problems=[api.read(manufactured_root/('problem_%02d.json'%i)) for i in range(24)]
        s=api.read(source.OUT/'failed_systems.json')['failed_inner_systems'][0]['system'];M,J=np.asarray(s['mobility']),np.asarray(s['jacobian']);mu,dt=s['friction'],s['dt_s']
        for stick in (0,1):
            slide=1-stick;C=J[[0,3,3*stick+1,3*stick+2]];u,sv,vh=np.linalg.svd(C,full_matrices=True);rank=sum(sv>sv[0]*1e-12);N=vh[rank:].T
            _,sv,V=np.linalg.svd(J[3*slide+1:3*slide+3]@N,full_matrices=False);direction=N@V[0];direction/=np.linalg.norm(direction)
            for speed in (1e-9,1e-7,1e-5):
                for sign in (-1.,1.):
                    q=direction*speed*sign;vc=J@q;f=np.zeros(6);f[0],f[3]=1.1e-8,.8e-8
                    f[3*stick+1:3*stick+3]=mu*f[3*stick]*np.array([.2,-.3]);tangent=vc[3*slide+1:3*slide+3]
                    f[3*slide+1:3*slide+3]=-mu*f[3*slide]*tangent/np.linalg.norm(tangent)
                    v=q-M@J.T@f;g=-vc[[0,3]]*dt
                    system=dict(vfree=v,mobility=M,jacobian=J,gaps_m=g,dt_s=dt,friction=mu)
                    oracle=independent.audit(system,v+M@J.T@f,dict(reactions=f))
                    api.require(oracle['passed'],'new manufactured oracle passes original equations')
                    problems.append(dict(system=system,known_velocity=q,known_force=f,oracle=oracle,new_geometry=True))
        with job.parent.fix.scope():
            for index,p in enumerate(problems):
                s=p['system'];args=[np.asarray(s[k]) for k in ('vfree','mobility','jacobian','gaps_m')]+[s['dt_s'],s['friction'],1e-10,25000,stop]
                q,h=candidate.solve(*args);a=independent.audit(s,q,h);error=float(np.linalg.norm(q-p['known_velocity']))
                row=dict(index=index,passed=a['passed'] and error/max(np.linalg.norm(s['vfree']),1e-15)<=1e-8 and error/max(np.linalg.norm(p['known_velocity']),1e-15)<=1e-6,
                         independent=a,absolute_velocity_error=error,velocity=q.tolist(),health=h)
                manufactured.append(row);job.commit(OUT/('problem_%02d.json'%index),dict(problem=p,report=row))
                print('FEASIBILITY_MANUFACTURED',index,row['passed'],flush=True)
        good=api.read(goodpath);checks['positive_full_audit']=auditor.evaluate(good['fixture'],good['before'])['passed']
        mutations=[('wrong_system','cone_system_sha256','0'*64),('false_failure','unmodified_v4_failure','unrelated'),('lost_projection','cone_feasibility_projection',False),
                   ('lost_gaps','original_gaps_preserved',False),('relaxed_limit','cone_retraction_limit',1e-8),('false_delta','cone_relative_force_retraction',0.),
                   ('false_method','cone_trial_method','invented'),('wrong_old_route','pre_retraction_solver','invented'),
                   ('wrong_trial_force','cone_trial_reactions',[0.]*6),('invalid_modes','contact_modes',[9,9])]
        for label,key,value in mutations:
            bad=copy.deepcopy(good['fixture']);mutate(bad,key,value)
            try:auditor.evaluate(bad,good['before'])
            except (RuntimeError,ValueError,KeyError,IndexError,AssertionError):guards.append(dict(test=label,rejected=True))
            else:guards.append(dict(test=label,rejected=False))
        for label in ('wrong_velocity','nonfinite_velocity'):
            bad=copy.deepcopy(good['fixture']);bad['rows'][0]['velocity_generalized'][0]+=1e-4
            if label=='nonfinite_velocity':bad['rows'][0]['velocity_generalized'][0]=float('nan')
            try:auditor.evaluate(bad,good['before'])
            except (RuntimeError,ValueError,KeyError,IndexError,AssertionError):guards.append(dict(test=label,rejected=True))
            else:guards.append(dict(test=label,rejected=False))
        api.require(all(checks.values()) and len(manufactured)==36 and all(r['passed'] for r in manufactured) and len(guards)==12 and all(r['rejected'] for r in guards),'full control qualification')
    except Exception as error:
        failure=dict(error=repr(error),traceback=traceback.format_exc());job.commit(OUT/'failure.json',failure)
    api.verify_mapping(inputs);job.verify(d)
    result=dict(passed=failure is None,new_trajectory_steps=0,inputs=inputs,checks=checks,manufactured=manufactured,guards=guards,failure=failure,
                claim='Local algebra and provenance controls only. Independent qualification audit and separately bounded trajectory/restart tests remain pending.')
    job.commit(OUT/'results.json',result);job.commit(OUT/'completion.json',dict(passed=result['passed'],results_sha256=api.sha(OUT/'results.json')))
    print('FEASIBILITY_CONTROLS_COMPLETE',result['passed'],checks,guards,flush=True)

if __name__=='__main__':run()
