"""Independent physical recalculation and disclosed root-comparator adjudication."""
from pathlib import Path
import copy,os,traceback
import numpy as np
import authenticate_failed_system_v1 as source
import qualify_two_contact_held_v1 as physical
import audit_cone_feasibility_v1 as route
job,api,ROOT=source.job,source.api,source.ROOT
BASE=ROOT/'stage206_evaluations/contact_failure_20260930';OUT=BASE/'independent_local_01'
ADJ=ROOT/'stage206_designs/contact_failure_20260930/local_adjudication_01.json'

def sealed(label):
    p=BASE/label/'results.json';r=api.read(p)
    api.require(api.read(p.parent/'completion.json')['results_sha256']==api.sha(p),'sealed '+label)
    return r

def mutate(x,key,value):
    if isinstance(x,dict):
        if x.get('solver')==route.candidate.NAME:x[key]=copy.deepcopy(value)
        for v in x.values():mutate(v,key,value)
    elif isinstance(x,list):
        for v in x:mutate(v,key,value)

def run():
    d=api.read(job.DESIGN);job.verify(d);adjudication=api.read(ADJ)
    held,outer,controls,roots=[sealed(label) for label in ('held_qualification_01','outer_qualification_01','controls_qualification_01','manufactured_root_certificate_01')]
    api.require(held['passed'] and outer['passed'] and roots['passed'] and not controls['passed'],'all original verdicts retained')
    api.require(controls['failure']['error']=="RuntimeError('full control qualification')" and [r['index'] for r in controls['manufactured'] if not r['passed']]==[31],'only disclosed nonunique comparator failure')
    packs=[ROOT/'stage201_evaluations/contact_repair_20260928/failed_evidence_01/failed_systems.json',ROOT/'stage201_evaluations/contact_repair_20260928/extension_failure_audit_01/failed_systems.json',source.OUT/'failed_systems.json']
    systems=[x['system'] for p in packs for x in api.read(p)['failed_inner_systems']]
    files=[ADJ,job.DESIGN,Path(__file__),Path(route.__file__),Path(physical.__file__)]+packs
    for label in ('held_qualification_01','outer_qualification_01','controls_qualification_01','manufactured_root_certificate_01'):
        files+=list((BASE/label).glob('*.json'))
    inputs={str(p):api.sha(p) for p in files}
    OUT.mkdir(parents=True,exist_ok=False);job.commit(OUT/'launch.json',dict(pid=os.getpid(),utc=job.utc().isoformat(),inputs=inputs,new_trajectory_steps=0))
    fixed=[];manufactured=[];covariance=[];guards=[];failed=None
    try:
        for index,s in enumerate(systems):
            saved=api.read(BASE/'held_qualification_01'/('system_%02d.json'%index));reference=None
            for (label,t,factor),row in zip(physical.variants(s),saved['variants']):
                api.require(label==row['label'] and row['passed'],'all saved variant identities')
                q=np.asarray(row['velocity']);h=row['health'];check=physical.audit(t,q,h)
                if reference is None:reference=q.copy()
                error=np.linalg.norm(q/factor-reference)/max(np.linalg.norm(s['vfree']),1e-15)
                covariance.append(bool(check['passed'] and error<=1e-8 and row['old_success_exact']))
        for index in range(28):
            item=api.read(BASE/'outer_qualification_01'/('fixture_%02d.json'%index));check=route.evaluate(item['fixture'],item['before'])
            fixed.append(check['passed'] and outer['outer'][index]['old_velocity_exact'])
        for index in range(36):
            item=api.read(BASE/'controls_qualification_01'/('problem_%02d.json'%index));p,r=item['problem'],item['report'];s=p['system']
            api.require(r==controls['manufactured'][index],'sealed manufactured result identity')
            q=np.asarray(r['velocity']);check=physical.audit(s,q,r['health'])
            oracle=np.asarray(p['known_velocity']);f=np.asarray(p['known_force']);v,M,J,g=[np.asarray(s[k],float) for k in ('vfree','mobility','jacobian','gaps_m')]
            oraclecheck=physical.audit(s,v+M@J.T@f,dict(reactions=f));api.require(oraclecheck['passed'],'prescribed oracle satisfies original law')
            if index==31:
                api.require(adjudication['exceptional_problem']==31 and adjudication['original_controls_qualification_01_remains_failed'] is True,'explicit unchanged original failure')
                f2=np.asarray(roots['linear_sticking_force']);q2=v+M@J.T@f2;check2=physical.audit(s,q2,dict(reactions=f2))
                api.require(check2['passed'] and np.linalg.norm(J@q2+np.repeat(g/s['dt_s'],3)*np.tile([1,0,0],2))/max(np.linalg.norm(v),1e-15)<=1e-10,'independent sticking root satisfies kinematics and every original gate')
                api.require(roots['old_new_solver_same_branch_exact'] and roots['original_single_root_test_remains_failed'],'repair does not select a new branch or promote the failed comparator')
                oracle=q2
            error=float(np.linalg.norm(q-oracle));passed=check['passed'] and error/max(np.linalg.norm(v),1e-15)<=1e-8 and error/max(np.linalg.norm(oracle),1e-15)<=1e-6
            manufactured.append(dict(index=index,passed=passed,adjudicated_two_root=index==31,independent=check))
        good=api.read(BASE/'outer_qualification_01/fixture_27.json')
        mutations=[('wrong_system','cone_system_sha256','0'*64),('false_failure','unmodified_v4_failure','unrelated'),('lost_projection','cone_feasibility_projection',False),('lost_gaps','original_gaps_preserved',False),('relaxed_limit','cone_retraction_limit',1e-8),('false_delta','cone_relative_force_retraction',0.),('false_method','cone_trial_method','invented'),('wrong_old_route','pre_retraction_solver','invented'),('wrong_trial_force','cone_trial_reactions',[0.]*6),('invalid_modes','contact_modes',[9,9])]
        for label,key,value in mutations:
            fixture=copy.deepcopy(good['fixture']);mutate(fixture,key,value)
            try:route.evaluate(fixture,good['before'])
            except (RuntimeError,ValueError,KeyError,IndexError,AssertionError):guards.append(dict(test=label,rejected=True))
            else:guards.append(dict(test=label,rejected=False))
        api.require(len(covariance)==168 and all(covariance) and len(fixed)==28 and all(fixed) and len(manufactured)==36 and all(r['passed'] for r in manufactured) and len(guards)==10 and all(r['rejected'] for r in guards),'all scoped independent local gates')
        api.require(all(controls['checks'].values()) and len(controls['guards'])==12 and all(x['rejected'] for x in controls['guards']),'unchanged dispatch and physical-output corruption controls')
    except Exception as error:
        failed=dict(error=repr(error),traceback=traceback.format_exc());job.commit(OUT/'failure.json',failed)
    api.verify_mapping(inputs);job.verify(d)
    result=dict(passed=failed is None,new_trajectory_steps=0,inputs=inputs,covariance_recalculated=len(covariance),fixed_pose_reaudited=len(fixed),manufactured=manufactured,guards=guards,failure=failed,
                original_controls_qualification_01_still_failed=True,disclosed_root_adjudication=True,production_gate_changes=False,physics_changes=False,
                physical_uniqueness_proven=False,claim='Independent local same-law numerical qualification with disclosed nonunique manufactured comparator. Original failed test and Stage205 remain failed. No trajectory or campaign acceptance; unchanged full selected/fine trajectory gates still required.')
    job.commit(OUT/'results.json',result);job.commit(OUT/'completion.json',dict(passed=result['passed'],results_sha256=api.sha(OUT/'results.json')))
    print('INDEPENDENT_LOCAL_QUALIFICATION',result['passed'],len(covariance),len(fixed),len(manufactured),flush=True)

if __name__=='__main__':run()
