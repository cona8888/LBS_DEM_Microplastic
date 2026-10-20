"""Eight nonadvancing complete outer solves, exact route and physical audits."""
from pathlib import Path
import inspect,copy
import numpy as np
import qualify_projection_auditor_v1 as old
import semismooth_rejected_seed_v1 as repair
import audit_semismooth_routes_v1 as auditor
q=old.q;job,api=old.job,old.api;BASE=old.BASE;OUT=BASE/'semismooth_outer_qualification_01'

def run():
    proto=q.ROOT/'stage194_designs/evidence_repair_20260924/semismooth_seed_qualification_01.json';p=api.read(proto);api.verify_mapping(p['inputs']);api.verify_mapping(p['sources'])
    api.require(api.read(BASE/'semismooth_seed_qualification_01/results.json')['passed'],'qualified new solver')
    extra=BASE/'dispatch_failure_audit_01/failure_details.json';function=inspect.getsource(old.run)
    replacements={"trials=api.read(source)['failed_outer_trials']":"trials=api.read(source)['failed_outer_trials']+api.read(EXTRA)['failed_outer_trials']", "'max_outer_calls':5":"'max_outer_calls':8", "'fixed_pose_solve_fixtures':5":"'fixed_pose_solve_fixtures':8"}
    for a,b in replacements.items():api.require(function.count(a)==1,'exact bounded fixture expansion');function=function.replace(a,b)
    paths=[proto,extra,Path(__file__),Path(old.__file__),Path(repair.__file__),Path(auditor.__file__),BASE/'semismooth_seed_qualification_01/results.json']
    inputs={str(x):api.sha(x) for x in paths};manifest=q.ROOT/'stage194_designs/evidence_repair_20260924/semismooth_outer_sources_01.json';job.commit(manifest,{'inputs':inputs,'new_trajectory_steps':0,'exact_fixture_changes':replacements})
    ns={**old.run.__globals__,'repair':repair,'auditor':auditor,'OUT':OUT,'EXTRA':extra,'__file__':__file__}
    exec(compile(function,str(Path(__file__))+'::eight_fixed_poses','exec'),ns);ns['run']()
    fixtures=api.read(OUT/'fixtures.json');reference=api.read(BASE/'outer_qualification_01/results.json')['reports'];comparisons=[]
    for i in range(5):
        trial=fixtures[i]['fixture']['contact_trial_trace']['detailed_trials'][0];free=np.asarray(trial['inner_systems'][0]['vfree'])
        error=float(np.linalg.norm(np.asarray(trial['velocity'])-np.asarray(reference[i]['velocity']))/max(np.linalg.norm(free),1e-15))
        comparisons.append({'index':i,'normalized_velocity_difference':error,'passed':error<=1e-10})
    guards=[];good=fixtures[0]
    for name,key,value in [('false_same_system','same_system_seed',False),('bad_seed_count','seed_candidate_count',100),('bad_seed_force','seed_reactions',[0.]),('bad_iterations','semismooth_nfev',2001)]:
        bad=copy.deepcopy(good['fixture'])
        # Corrupt every exact-copy occurrence, so this tests method provenance,
        # not just a disagreement between one copy and its parent.
        def edit(obj):
            if isinstance(obj,dict):
                if obj.get('solver')==repair.NAME:obj[key]=value
                for x in obj.values():edit(x)
            elif isinstance(obj,list):
                for x in obj:edit(x)
        edit(bad)
        try:auditor.evaluate(bad,good['before'])
        except (RuntimeError,ValueError,KeyError):guards.append({'test':name,'passed':True})
        else:guards.append({'test':name,'passed':False})
    api.verify_mapping(inputs);api.verify_mapping(p['inputs']);api.verify_mapping(p['sources'])
    r={'passed':api.read(OUT/'results.json')['passed'] and all(c['passed'] for c in comparisons+guards),'new_trajectory_steps':0,
       'old_fixed_pose_comparisons':comparisons,'additional_guards':guards,'manifest_sha256':api.sha(manifest),'outer_result_sha256':api.sha(OUT/'results.json')}
    job.commit(OUT/'qualification_closure.json',r);print('SEMISMOOTH_OUTER_CLOSURE',r['passed'],flush=True)

if __name__=='__main__':run()
