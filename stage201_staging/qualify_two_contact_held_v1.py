"""Independent direct residual calculations and held-system covariance tests."""
from pathlib import Path
from types import SimpleNamespace
import copy
import os
import time
import traceback
import numpy as np
import two_contact_scalar_repair_v1 as candidate

probe=candidate.algebra;job,api,source,ROOT=probe.job,probe.api,probe.source,probe.ROOT
PROTOCOL=ROOT/'stage201_designs/eight_hour_contact_repair_20260928/held_qualification_01.json'
OUT=ROOT/'stage201_evaluations/contact_repair_20260928/held_qualification_01'


def audit(s,q,h):
    v,M,J,g=[np.asarray(s[k],float) for k in ('vfree','mobility','jacobian','gaps_m')]
    f=np.asarray(h['reactions']);mu,dt=s['friction'],s['dt_s'];vs=max(np.linalg.norm(v),1e-15)
    A=J@M@J.T;vc=J@v+A@f;residual=0.
    for k in range(2):
        i=3*k;step=np.linalg.eigvalsh(A[i+1:i+3,i+1:i+3]).max()
        residual=max(residual,abs(min(A[i,i]*f[i],vc[i]+g[k]/dt)))
        trial=f[i+1:i+3]-vc[i+1:i+3]/step
        projected=trial*min(1.,mu*f[i]/max(np.linalg.norm(trial),1e-300))
        residual=max(residual,np.linalg.norm(f[i+1:i+3]-projected)*step)
    closure=np.linalg.norm(np.linalg.solve(M,q-v)-J.T@f)/max(np.linalg.norm(J.T@f),1e-30)
    cone=max(np.linalg.norm(f[3*k+1:3*k+3])-mu*f[3*k] for k in range(2))/max(np.linalg.norm(f),1e-30)
    work=sum(float(f[3*k+1:3*k+3]@vc[3*k+1:3*k+3]) for k in range(2))
    normalized_work=work/max(np.linalg.norm(f)*vs,1e-30)
    passed=bool(np.isfinite(q).all() and np.isfinite(f).all() and np.all(f[::3]>=0) and residual/vs<=1e-10 and closure<=1e-8 and cone<=1e-12 and normalized_work<=1e-8 and np.array_equal(q,v+M@J.T@f))
    return {'passed':passed,'contact_residual':float(residual/vs),'force_residual':float(closure),'cone_excess_relative':float(cone),'friction_work_relative':float(normalized_work)}


def variants(s):
    yield 'identity',copy.deepcopy(s),1.
    t=copy.deepcopy(s);ix=[3,4,5,0,1,2];t['jacobian']=np.asarray(t['jacobian'])[ix].tolist();t['gaps_m']=list(reversed(t['gaps_m']));yield 'swap',t,1.
    for both in (False,True):
        t=copy.deepcopy(s);T=np.eye(6)
        for k in range(2 if both else 1):T[3*k+1:3*k+3,3*k+1:3*k+3]=[[0.,-1.],[1.,0.]]
        t['jacobian']=(T@np.asarray(t['jacobian'])).tolist();yield 'both_tangents' if both else 'first_tangent',t,1.
    for factor in (.5,2.):
        t=copy.deepcopy(s);t['vfree']=(np.asarray(t['vfree'])*factor).tolist();t['gaps_m']=(np.asarray(t['gaps_m'])*factor).tolist();yield 'scale_'+str(factor),t,factor


def run():
    w=api.read(source.WORK);stop=job.policy.utc(w['work_end_utc']).timestamp();api.require(time.time()<stop,'work window')
    d=api.read(job.DESIGN);job.verify(d);p=api.read(PROTOCOL)
    sysfile=source.OUT/'failed_systems.json';api.require(api.sha(sysfile)==api.read(source.OUT/'results.json')['failed_systems_sha256'],'failed system seal')
    inputs={str(f):api.sha(f) for f in (source.WORK,PROTOCOL,Path(__file__),Path(candidate.__file__),Path(probe.__file__),sysfile,job.DESIGN)}
    OUT.mkdir(parents=True,exist_ok=False);job.commit(OUT/'launch.json',{'pid':os.getpid(),'utc':job.utc().isoformat(),'inputs':inputs,'new_trajectory_steps':0,'maximum_system_variants':132})
    rows=[];policy=[];invalid=[]
    try:
        with job.parent.fix.scope():
            for index,item in enumerate(api.read(sysfile)['failed_inner_systems']):
                s=item['system'];reference=None;group=[]
                for label,t,factor in variants(s):
                    api.require(time.time()<stop,'work cutoff')
                    args=[np.asarray(t[k],float) for k in ('vfree','mobility','jacobian','gaps_m')]+[t['dt_s'],t['friction'],t['tolerance'],t['maxiter']]
                    try:
                        q,h=candidate.solve(*args,stop_epoch=stop);check=audit(t,q,h)
                        if reference is None:reference=q.copy()
                        error=float(np.linalg.norm(q/factor-reference)/max(np.linalg.norm(s['vfree']),1e-15))
                        row={'case':index,'variant':label,'gate':check,'covariance_error':error,'passed':check['passed'] and error<=p['local_covariance_velocity_error_over_original_free_speed_max'],'health':h,'velocity':q.tolist()}
                    except (RuntimeError,ValueError,np.linalg.LinAlgError,FloatingPointError) as error:
                        row={'case':index,'variant':label,'passed':False,'error':repr(error)}
                    rows.append(row);group.append(row)
                job.commit(OUT/('system_%02d.json'%index),{'variants':group});print('COVARIANCE',index,sum(r['passed'] for r in group),'/',len(group),flush=True)
            s=api.read(sysfile)['failed_inner_systems'][0]['system']
            args=[np.asarray(s[k],float) for k in ('vfree','mobility','jacobian','gaps_m')]+[s['dt_s'],s['friction'],s['tolerance'],s['maxiter']]
            sentinel=(np.array([1.,2.,3.,4.,5.,6.]),{'sentinel':'unaltered'})
            original=lambda *args:sentinel
            rt=SimpleNamespace(mixed=SimpleNamespace(solve=original))
            with candidate.scope(rt,True,stop):api.require(rt.mixed.solve(*args) is sentinel,'successful original object preserved')
            api.require(rt.mixed.solve is original,'scope restoration');policy.append('successful_original_identity_and_restore')
            for message in ('unrelated failure','diagnostic work cutoff reached'):
                def raises(*args):raise RuntimeError(message)
                rt.mixed.solve=raises
                try:
                    with candidate.scope(rt,True,stop):rt.mixed.solve(*args)
                except RuntimeError as error:api.require(str(error)==message,'unrelated error preserved');policy.append(message)
                else:raise AssertionError('unsupported error accepted')
            bad=[]
            for label,pos,value in [('dt_zero',4,0.),('negative_mu',5,-.3),('relaxed_tolerance',6,1e-6),('wrong_g_shape',3,np.zeros(3)),('nonfinite_v',0,np.full(6,np.nan)),('negative_mobility',1,-args[1])]:
                test=copy.deepcopy(args);test[pos]=value;bad.append((label,test))
            for label,test in bad:
                try:candidate.solve(*test,stop_epoch=stop)
                except (RuntimeError,ValueError,np.linalg.LinAlgError,FloatingPointError):invalid.append(label)
                else:raise AssertionError('invalid input accepted: '+label)
        api.verify_mapping(inputs);job.verify(d)
        report={'passed':all(r['passed'] for r in rows) and len(rows)==132 and len(invalid)==6 and len(policy)==3,'new_trajectory_steps':0,'variants':rows,'invalid_inputs_rejected':invalid,'route_policy':policy,'inputs':inputs,'claim':'Local held-system and covariance qualification only; trajectory and full-path qualification pending.'}
        job.commit(OUT/'results.json',report);job.commit(OUT/'completion.json',{'passed':report['passed'],'results_sha256':api.sha(OUT/'results.json')});print('HELD_QUALIFICATION',report['passed'],sum(r['passed'] for r in rows),'/',len(rows),flush=True)
    except Exception as error:
        job.commit(OUT/'failure.json',{'error':repr(error),'traceback':traceback.format_exc(),'new_trajectory_steps':0,'completed_variants':len(rows)});raise


if __name__=='__main__':run()
