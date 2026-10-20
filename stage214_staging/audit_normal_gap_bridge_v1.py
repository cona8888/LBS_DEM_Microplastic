"""Zero-step independent fresh namespace/design and unchanged assertion checks."""
from pathlib import Path
import ast,copy,inspect,os,shutil
import normal_gap_stack_preflight_v1 as w
import qualify_normal_gap_stack_v1 as pre
api,job=w.api,w.job
OUT=job.OUT/'independent_bridge_01'


def run():
    d=api.read(job.DESIGN);job.verify(d);w.ledger();w.no_competing_trajectory()
    api.require(not OUT.exists() and not job.PREFLIGHT.exists() and not job.RUN.exists(),'zero-step exclusive prelaunch bridge')
    baseline=ast.parse(inspect.getsource(pre.tests.run))
    # Scientific and exact numerical assertions remain the original expressions;
    # only process ownership guard and historical bookkeeping were transformed.
    expected=[];actual=[]
    for tree,target in ((baseline,expected),(pre.tree,actual)):
        for node in ast.walk(tree):
            if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute) and node.func.attr=='require':
                message=node.args[-1].value if node.args and isinstance(node.args[-1],ast.Constant) else None
                if message not in ('no duplicate simulation or benchmark','exact cumulative qualification ledger'):
                    target.append(ast.dump(node,include_attributes=False))
    api.require(expected==actual,'all original scientific/exact/restart/parallel/live assertions retained verbatim')
    cases={c['id']:c for c in d['cases']}
    case,cp=pre.ns['stress_seed'](d)
    oracle=w.q.independent_file(Path(d['stress_oracle_raw']),api.sha(d['stress_oracle_design']))
    api.require(case['id']=='s2_i124_sphere_f0p0625' and len(oracle['rows'])==1000 and oracle['rows'][0]['time_s']>cp['state']['t'],'qualified policy crossing oracle')
    api.require(cp['state']==api.read(w.local.RUNBASE/'split_a_01/checkpoint.json')['state'],'stress state copied unchanged, rebound numerical contract')
    controls=[]
    def reject(label,change):
        bad=copy.deepcopy(d);change(bad);bad['binding']=api.digest({k:v for k,v in bad.items() if k!='binding'})
        try:job.verify(bad)
        except Exception as exc:controls.append(dict(control=label,rejected=True,error=repr(exc)));return
        raise AssertionError('corruption accepted: '+label)
    reject('case_timestep',lambda x:x['cases'][0]['spec']['config']['numerics'].update(max_dt_s=1.0))
    reject('horizon',lambda x:x['cases'][0]['spec'].update(horizon_s=1.0))
    reject('physical_gate',lambda x:x['numerical_gates'].update(mean_l1_velocity_over_U=1.0))
    reject('production',lambda x:x.update(production_authorized=True))
    reject('normal_policy_contract',lambda x:x.update(numerical_policy_contract_sha256='0'*64))
    reject('independent_auditor',lambda x:x.update(audit_source_sha256='0'*64))
    reject('pending_bound',lambda x:x.update(maximum_unverified_segments_total=7))
    reject('live_workers',lambda x:x['budget'].update(workers=4))
    reject('source_seal',lambda x:x['sources'].update({str(job.SELF):'0'*64}))
    reject('old_seed',lambda x:x.update(stress_seed_raw=str(w.local.RECON/'checkpoint_00033.json')))
    reject('calendar',lambda x:x.update(agent_work_end_utc='2026-10-03T04:00:00+00:00'))
    reject('numerical_binding',lambda x:x['qualified_normal_gap_bindings'].update(integration_code_sha256='0'*64))
    identity_checks=[]
    for name,wrong in (('acknowledged',w.old_job.acknowledged),('kernel',w.old_job.kernel)):
        original=getattr(job,name);setattr(job,name,wrong)
        try:
            try:job.verify(d)
            except Exception as exc:identity_checks.append(dict(control=name,rejected=True,error=repr(exc)))
            else:raise AssertionError('wrong actual function association accepted')
        finally:setattr(job,name,original)
    job.verify(d);w.no_competing_trajectory()
    free=shutil.disk_usage(w.ROOT).free;api.require(free>d['budget']['minimum_free_disk_bytes'],'current disk reserve')
    result=dict(passed=True,new_trajectory_steps=0,all_original_assertions_retained=True,
        preserved_exact_old_policy_controls=True,negative_design_controls=controls,negative_binding_controls=identity_checks,
        qualified_bindings=w.bindings(),design_sha256=api.sha(job.DESIGN),source_sha256=api.sha(__file__),
        original_campaign_namespace_untouched=str(w.old_job.DESIGN),fresh_stack_namespace=str(job.DESIGN),
        prior_stage213_saved_and_independently_accepted_steps=4000,separate_stage214_reserved_max_saved_steps=17000,
        C_free_bytes=free,production_authorized=False,claim='Zero-step launch binding only. No numerical preflight or production pass.')
    job.commit(OUT/'results.json',result);job.commit(OUT/'completion.json',dict(passed=True,results_sha256=api.sha(OUT/'results.json')))
    print('NORMAL_GAP_BRIDGE_PASS',api.sha(OUT/'results.json'),len(controls),len(identity_checks),flush=True)

if __name__=='__main__':run()
