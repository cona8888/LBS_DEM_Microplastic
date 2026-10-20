"""Check every isolated necessary polynomial root with unchanged full gates."""
from pathlib import Path
from fractions import Fraction as F
import os,sys,traceback
import numpy as np
import authenticate_failed_system_v1 as source
import qualify_sliding_projection_v1 as tests
job,api,ROOT=source.job,source.api,source.ROOT
BASE=ROOT/'stage210_evaluations/three_contact_failure_20261001'
POLY=BASE/'mixed_mode_polynomials_02/results.json'
OUT=BASE/'mixed_polynomial_classification_01'


def run():
    sys.set_int_max_str_digits(100000)
    d=api.read(job.DESIGN);job.verify(d);r=api.read(POLY)
    assert api.read(POLY.parent/'completion.json')['results_sha256']==api.sha(POLY)
    bridge=api.read(POLY.parent/'serialization_bridge.json');api.verify_mapping(bridge['inputs'])
    assert bridge['results_sha256']==api.sha(POLY)
    fp=source.OUT/'failed_systems.json';item=api.read(fp)['failed_inner_systems'][0]
    assert item['system_sha256']==r['system_sha256']==api.digest(item['system'])
    args=tests.args(item['system']);v,M,J,g,dt,mu,tol,maxiter=args
    B=np.linalg.inv(M);fs=max(np.linalg.norm(B@v),1e-30);A=J@M@J.T;z=J@v
    steps=np.array([np.linalg.eigvalsh(A[3*k+1:3*k+3,3*k+1:3*k+3]).max() for k in range(3)])
    inputs={str(p):api.sha(p) for p in (Path(__file__),source.WORK,job.DESIGN,fp,POLY,POLY.parent/'serialization_bridge.json',Path(tests.__file__))}
    OUT.mkdir(parents=True,exist_ok=False);job.commit(OUT/'launch.json',dict(pid=os.getpid(),utc=job.utc().isoformat(),inputs=inputs,new_trajectory_steps=0,maximum_candidates=28))
    rows=[]
    try:
        with job.parent.fix.scope():
            gate=job.fast.gate
            for mode in r['modes']:
                q0=np.array([float(F(x)) for x in mode['exact_velocity_particular']]);direction=np.array([float(F(x)) for x in mode['exact_velocity_direction']]);qs=float(F(mode['velocity_scale']))
                for interval in mode['root_intervals']:
                    y=float((F(interval['left'])+F(interval['right']))/2);q=(q0+direction*y)*qs;vc=J@q
                    columns=[];tiny=False
                    for k in range(3):
                        if k==mode['sticking_contact']:
                            for j in range(3):
                                e=np.zeros(9);e[3*k+j]=1.;columns.append(e)
                        else:
                            vt=vc[3*k+1:3*k+3];speed=np.linalg.norm(vt)
                            if speed<qs*1e-14:tiny=True
                            e=np.zeros(9);e[3*k]=1.;e[3*k+1:3*k+3]=-mu*vt/max(speed,1e-300);columns.append(e)
                    E=np.column_stack(columns);H=J.T@E;load=B@(q-v)/fs
                    coeff=np.linalg.lstsq(H,load,rcond=1e-13)[0];f=E@coeff*fs
                    row=dict(sticking_contact=mode['sticking_contact'],root_interval=interval,y=y,prescribed_velocity=q.tolist(),
                      force=f.tolist(),signed_normal_forces=f[::3].tolist(),sliding_direction_near_degenerate=tiny,
                      equilibrium_residual=float(np.linalg.norm(H@coeff-load)),original_gate_pass=False)
                    projected=f.copy()
                    if np.all(f[::3]>=0):
                        for k in range(3):
                            i=3*k;length=np.linalg.norm(f[i+1:i+3]);radius=mu*f[i]
                            if length>radius:projected[i+1:i+3]*=radius/length
                    row['relative_force_retraction']=float(np.linalg.norm(projected-f)/max(np.linalg.norm(f),1e-30))
                    try:
                        assert row['relative_force_retraction']<=1e-10
                        answer=gate._finish(v,M,J,projected,z,A,g,dt,mu,steps,0,'held_exact_polynomial_root_candidate',{})
                        audit,saved=tests.audit(args,answer);row.update(original_gate_pass=True,independent_audit=audit,saved_system=saved)
                    except (AssertionError,RuntimeError,ValueError) as error:row['gate_error']=repr(error)
                    rows.append(row)
                print('CLASSIFIED_POLYNOMIAL_MODE',mode['sticking_contact'],sum(z['original_gate_pass'] for z in rows if z['sticking_contact']==mode['sticking_contact']),flush=True)
        api.verify_mapping(inputs);job.verify(d)
        result=dict(new_trajectory_steps=0,inputs=inputs,roots_checked=len(rows),original_gate_passes=sum(z['original_gate_pass'] for z in rows),candidates=rows,no_repair_installed=True,
          claim='Floating evaluation of every isolated necessary polynomial root followed by unchanged full gates. Squaring roots may be extraneous and floating classification is not an interval proof of exact admissibility or tolerance-global infeasibility.')
        job.commit(OUT/'results.json',result);job.commit(OUT/'completion.json',dict(results_sha256=api.sha(OUT/'results.json')))
    except Exception as error:
        job.commit(OUT/'failure.json',dict(error=repr(error),traceback=traceback.format_exc(),new_trajectory_steps=0,candidates=rows));raise


if __name__=='__main__':run()
