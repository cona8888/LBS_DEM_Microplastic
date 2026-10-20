"""Manufactured mixed-mode solutions independent of captured failure outputs.

The captured geometry/mobility are reused, but forces and velocities are
prescribed first. Free velocity is then obtained by exact equilibrium. This
checks the original equations on 24 new algebraic problems, no trajectory.
"""
from pathlib import Path
import os,time,traceback
import numpy as np
import two_contact_scalar_repair_v2 as candidate
import qualify_two_contact_held_v1 as held
job,api,ROOT,source=held.job,held.api,held.ROOT,held.source
OUT=ROOT/'stage201_evaluations/contact_repair_20260928/manufactured_qualification_01'
PROTOCOL=ROOT/'stage201_designs/eight_hour_contact_repair_20260928/manufactured_qualification_01.json'


def run():
    w=api.read(source.WORK);end=job.policy.utc(w['work_end_utc']).timestamp();api.require(time.time()<end,'work window')
    d=api.read(job.DESIGN);job.verify(d);systems=source.OUT/'failed_systems.json'
    p={'stage':'Stage201 independently manufactured two-contact mixed-mode equations','new_trajectory_steps':0,'maximum_problems':24,'relative_velocity_error_over_free_speed_max':1e-8,'relative_velocity_error_over_known_speed_max':1e-6,'unchanged_physical_gates':True,
       'inputs':{str(x):api.sha(x) for x in (source.WORK,job.DESIGN,systems,Path(__file__),Path(candidate.__file__),Path(candidate.prior.__file__),Path(candidate.algebra.__file__),Path(held.__file__))},'production_authorized':False}
    job.commit(PROTOCOL,p);OUT.mkdir(parents=True,exist_ok=False);job.commit(OUT/'launch.json',{'pid':os.getpid(),'utc':job.utc().isoformat(),'protocol_sha256':api.sha(PROTOCOL),'new_trajectory_steps':0})
    rows=[];failure=None
    try:
        with job.parent.fix.scope():
            for index in (0,21):
                original=api.read(systems)['failed_inner_systems'][index]['system'];M,J=np.asarray(original['mobility']),np.asarray(original['jacobian']);mu,dt=original['friction'],original['dt_s']
                for stick in (0,1):
                    slide=1-stick;C=J[[0,3,3*stick+1,3*stick+2]];u,s,vh=np.linalg.svd(C,full_matrices=True);rank=sum(s>s[0]*1e-12);N=vh[rank:].T
                    # Nullspace direction with maximal velocity at sliding point.
                    _,sv,V=np.linalg.svd(J[3*slide+1:3*slide+3]@N,full_matrices=False);direction=N@V[0];direction/=np.linalg.norm(direction)
                    for speed in (1e-9,1e-7,1e-5):
                        for sign in (-1.,1.):
                            api.require(time.time()<end,'work cutoff');q=direction*(speed*sign);vc=J@q
                            f=np.zeros(6);f[0],f[3]=1.1e-8,0.8e-8
                            f[3*stick+1:3*stick+3]=mu*f[3*stick]*np.array([.2,-.3])
                            tang=vc[3*slide+1:3*slide+3];f[3*slide+1:3*slide+3]=-mu*f[3*slide]*tang/np.linalg.norm(tang)
                            v=q-M@J.T@f;g=-vc[[0,3]]*dt
                            system={'vfree':v,'mobility':M,'jacobian':J,'gaps_m':g,'dt_s':dt,'friction':mu}
                            # Verify the manufactured answer itself before
                            # using it as an oracle; no optimizer output used.
                            oracle=held.audit(system,q,{'reactions':f});api.require(oracle['passed'],'manufactured oracle satisfies original equations')
                            try:
                                got,h=candidate.solve(v,M,J,g,dt,mu,1e-10,25000,end);a=held.audit(system,got,h)
                                e=float(np.linalg.norm(got-q));ev=e/max(np.linalg.norm(v),1e-15);eq=e/max(np.linalg.norm(q),1e-15)
                                row={'passed':a['passed'] and ev<=1e-8 and eq<=1e-6,'audit':a,'relative_free_error':ev,'relative_known_error':eq,'health':h}
                            except (RuntimeError,ValueError,np.linalg.LinAlgError,FloatingPointError) as error:row={'passed':False,'error':repr(error)}
                            row.update(geometry_index=index,stick=stick,speed=speed,sign=sign,oracle=oracle);rows.append(row)
                            job.commit(OUT/('problem_%02d.json'%(len(rows)-1)),{'system':system,'known_velocity':q,'known_force':f,'report':row})
                            print('MANUFACTURED',len(rows),row['passed'],flush=True)
    except Exception as error:failure={'error':repr(error),'traceback':traceback.format_exc()};job.commit(OUT/'failure.json',failure)
    api.verify_mapping(p['inputs']);job.verify(d)
    r={'passed':failure is None and len(rows)==24 and all(x['passed'] for x in rows),'new_trajectory_steps':0,'reports':rows,'failure':failure,'protocol_sha256':api.sha(PROTOCOL),'claim':'Manufactured equation verification, not experimental or trajectory validation.'}
    job.commit(OUT/'results.json',r);job.commit(OUT/'completion.json',{'passed':r['passed'],'results_sha256':api.sha(OUT/'results.json')});print('MANUFACTURED_QUALIFICATION',r['passed'],len(rows),flush=True)


if __name__=='__main__':run()
