"""Independent rational recheck of the all-sticking certificate, no LP use."""
from pathlib import Path
from fractions import Fraction as F
import copy, os, math, traceback
import authenticate_failed_system_v1 as source
job, api, ROOT = source.job, source.api, source.ROOT
PROOF = ROOT/'stage210_evaluations/three_contact_failure_20261001/sticking_kinematics_01/results.json'
OUT = ROOT/'stage210_evaluations/three_contact_failure_20261001/sticking_independent_01'


def verify(row, s):
    api.require(row['system_sha256']==api.digest(s),'original held input hash')
    J=[[F.from_float(float(x)) for x in r] for r in s['jacobian']]
    w=[F(x) for x in row['left_nullspace_witness']]
    api.require(len(w)==9 and any(w),'nonzero nine-component witness')
    for j in range(6):api.require(sum((w[k]*J[k][j] for k in range(9)),F(0))==0,'exact rational nullspace')
    target=[0.]*9
    for k in range(3):target[3*k]=-s['gaps_m'][k]/s['dt_s']
    api.require(target==row['original_gap_velocity_targets'] and s['gaps_m']==row['original_gaps_m'] and s['dt_s']==row['dt_s'],'unchanged original targets')
    numerator=abs(sum((w[k]*F.from_float(target[k]) for k in range(9)),F(0)))
    denominator=sum((abs(x) for x in w),F(0));bound=numerator/denominator
    api.require(str(bound)==row['exact_residual_lower_bound_m_s'],'exact certificate lower bound')
    scale=max(math.sqrt(sum(x*x for x in s['vfree'])),1e-15);relative=float(bound)/scale
    api.require(abs(relative-row['relative_residual_lower_bound'])<=1e-15*relative,'reported relative bound')
    api.require(row['original_tolerance']==s['tolerance']==1e-10 and relative>1e-10,'unchanged gate exceeded in all-sticking mode')
    api.require(row['claim']=='All-sticking mode only; no global no-solution claim.','bounded mode claim')
    return dict(exact_left_nullspace=True,exact_lower_bound=str(bound),relative_lower_bound=relative,original_tolerance=s['tolerance'])


def run():
    d=api.read(job.DESIGN);job.verify(d);fp=source.OUT/'failed_systems.json'
    proof=api.read(PROOF);api.require(api.read(PROOF.parent/'completion.json')['results_sha256']==api.sha(PROOF),'certificate sealed');api.verify_mapping(proof['inputs'])
    systems=api.read(fp)['failed_inner_systems'];inputs={str(p):api.sha(p) for p in (Path(__file__),source.WORK,job.DESIGN,fp,PROOF,PROOF.parent/'completion.json')}
    OUT.mkdir(parents=True,exist_ok=False);job.commit(OUT/'launch.json',dict(pid=os.getpid(),utc=job.utc().isoformat(),inputs=inputs,new_trajectory_steps=0))
    try:
        checks=[verify(row,systems[row['index']]['system']) for row in proof['reports']]
        row=proof['reports'][0];s=systems[0]['system'];mutations=[]
        changes={
            'changed_witness':lambda r:r['left_nullspace_witness'].__setitem__(0,str(F(r['left_nullspace_witness'][0])+1)),
            'zero_witness':lambda r:r.update(left_nullspace_witness=['0']*9),
            'changed_target':lambda r:r['original_gap_velocity_targets'].__setitem__(0,0.),
            'changed_gap':lambda r:r['original_gaps_m'].__setitem__(0,0.),
            'changed_dt':lambda r:r.update(dt_s=r['dt_s']*2),
            'changed_bound':lambda r:r.update(exact_residual_lower_bound_m_s='0'),
            'changed_relative':lambda r:r.update(relative_residual_lower_bound=0.),
            'changed_tolerance':lambda r:r.update(original_tolerance=1e-7),
            'changed_claim':lambda r:r.update(claim='No physical solution exists'),
            'changed_source':lambda r:r.update(system_sha256='0'*64)}
        for label,change in changes.items():
            bad=copy.deepcopy(row);change(bad)
            try:verify(bad,s)
            except RuntimeError:mutations.append(dict(test=label,rejected=True))
            else:raise RuntimeError('corrupted certificate accepted: '+label)
        api.verify_mapping(inputs);job.verify(d)
        result=dict(passed=True,new_trajectory_steps=0,inputs=inputs,independent_exact_checks=checks,corruption_controls=mutations,
                    claim='Independent all-sticking kinematic certificate only. Does not prove global three-contact infeasibility or authorize a changed gap/gate.')
        job.commit(OUT/'results.json',result);job.commit(OUT/'completion.json',dict(passed=True,results_sha256=api.sha(OUT/'results.json'),new_trajectory_steps=0))
        print('INDEPENDENT_STICKING_CERTIFICATE',len(checks),'corruptions rejected',len(mutations),flush=True)
    except Exception as error:
        job.commit(OUT/'failure.json',dict(error=repr(error),traceback=traceback.format_exc(),new_trajectory_steps=0));raise


if __name__=='__main__':run()
