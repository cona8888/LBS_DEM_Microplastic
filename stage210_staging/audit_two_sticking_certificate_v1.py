"""Independent exact recheck of all nine two-sticking mode certificates."""
from pathlib import Path
from fractions import Fraction as F
import copy, math, os, traceback
import authenticate_failed_system_v1 as source
job,api,ROOT=source.job,source.api,source.ROOT
PROOF=ROOT/'stage210_evaluations/three_contact_failure_20261001/two_sticking_kinematics_02/results.json'
OUT=ROOT/'stage210_evaluations/three_contact_failure_20261001/two_sticking_independent_01'


def verify(row,s):
    api.require(row['system_sha256']==api.digest(s),'exact held source binding')
    expected=[3*k+j for k in range(3) for j in range(3) if j==0 or k!=row['sliding_contact']]
    api.require(row['contact_rows']==expected and len(expected)==7,'declared two-stick/one-slip constraints')
    J=[[F.from_float(float(x)) for x in s['jacobian'][k]] for k in expected];w=[F(x) for x in row['left_nullspace_witness']]
    api.require(len(w)==7 and any(w),'nonzero seven-component witness')
    api.require(all(sum((w[k]*J[k][j] for k in range(7)),F(0))==0 for j in range(6)),'exact left nullspace')
    target=[-s['gaps_m'][k//3]/s['dt_s'] if k%3==0 else 0. for k in expected]
    api.require(row['original_gap_velocity_targets']==target,'unchanged original gap targets')
    bound=abs(sum((w[k]*F.from_float(float(target[k])) for k in range(7)),F(0)))/sum((abs(x) for x in w),F(0))
    api.require(row['exact_residual_lower_bound_m_s']==str(bound),'independent rational bound')
    scale=max(math.sqrt(sum(x*x for x in s['vfree'])),1e-15);relative=float(bound)/scale
    api.require(abs(relative-row['relative_residual_lower_bound'])<=1e-15*relative,'bound normalization')
    api.require(row['original_tolerance']==s['tolerance']==1e-10 and relative>1e-10 and row['mode_incompatible_with_original_tolerance'],'conditional mode gate incompatibility')
    return dict(index=row['index'],sliding_contact=row['sliding_contact'],relative_bound=relative,exact_nullspace=True)


def run():
    d=api.read(job.DESIGN);job.verify(d);fp=source.OUT/'failed_systems.json';proof=api.read(PROOF)
    api.require(api.read(PROOF.parent/'completion.json')['results_sha256']==api.sha(PROOF),'sealed original certificates');api.verify_mapping(proof['inputs'])
    systems=api.read(fp)['failed_inner_systems'];inputs={str(p):api.sha(p) for p in (Path(__file__),source.WORK,job.DESIGN,fp,PROOF,PROOF.parent/'completion.json')}
    OUT.mkdir(parents=True,exist_ok=False);job.commit(OUT/'launch.json',dict(pid=os.getpid(),utc=job.utc().isoformat(),inputs=inputs,new_trajectory_steps=0))
    try:
        api.require(len(proof['reports'])==9,'three systems times three modes')
        api.require({(r['index'],r['sliding_contact']) for r in proof['reports']}=={(i,k) for i in range(3) for k in range(3)},'exact certificate coverage')
        checks=[verify(r,systems[r['index']]['system']) for r in proof['reports']]
        r=proof['reports'][0];s=systems[0]['system'];controls=[]
        changes={
            'witness':lambda r:r['left_nullspace_witness'].__setitem__(0,str(F(r['left_nullspace_witness'][0])+1)),
            'zero_witness':lambda r:r.update(left_nullspace_witness=['0']*7),
            'rows':lambda r:r['contact_rows'].__setitem__(0,1),
            'target':lambda r:r['original_gap_velocity_targets'].__setitem__(0,0.),
            'bound':lambda r:r.update(exact_residual_lower_bound_m_s='0'),
            'relative':lambda r:r.update(relative_residual_lower_bound=0.),
            'tolerance':lambda r:r.update(original_tolerance=1e-7),
            'source':lambda r:r.update(system_sha256='0'*64)}
        for label,change in changes.items():
            bad=copy.deepcopy(r);change(bad)
            try:verify(bad,s)
            except RuntimeError:controls.append(dict(test=label,rejected=True))
            else:raise RuntimeError('corrupted certificate accepted: '+label)
        api.verify_mapping(inputs);job.verify(d)
        result=dict(passed=True,new_trajectory_steps=0,inputs=inputs,checks=checks,corruption_controls=controls,
                    claim='Independent exact bounds for declared sticking modes only, not global three-contact infeasibility or authorization to change gaps/gates.')
        job.commit(OUT/'results.json',result);job.commit(OUT/'completion.json',dict(passed=True,results_sha256=api.sha(OUT/'results.json'),new_trajectory_steps=0))
        print('INDEPENDENT_TWO_STICK_CERTIFICATES',len(checks),'corruptions rejected',len(controls),flush=True)
    except Exception as error:
        job.commit(OUT/'failure.json',dict(error=repr(error),traceback=traceback.format_exc(),new_trajectory_steps=0));raise


if __name__=='__main__':run()
