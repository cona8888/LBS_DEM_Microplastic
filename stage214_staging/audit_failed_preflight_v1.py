"""Close failed exact-control accounting; independent physical replay, zero steps."""
from pathlib import Path
import copy,math,sys,traceback
import numpy as np
import normal_gap_stack_preflight_v1 as w
import qualify_normal_gap_stack_v1 as pre
job,api=w.job,w.api
OUT=job.OUT/'failed_preflight_independent_01'


def run():
    d=api.read(job.DESIGN);job.verify(d);w.no_competing_trajectory()
    api.require(not OUT.exists(),'new exclusive failed-evidence audit')
    fail=api.read(pre.OUT/'failure.json')
    api.require(fail['error']=="RuntimeError('exact old contact trajectory and full state')" and not fail['unresolved_probes']
        and fail['known_probe_steps']==3000 and fail['live_saved_steps']==0,'actual retained exact-comparator failure')
    paths=sorted((job.PREFLIGHT/'probes').glob('*.json.xz'))
    api.require(len(paths)==3 and not (job.PREFLIGHT/'live').exists(),'exact terminal inventory; no pipeline or parallel launches')
    records=[];saved=0;inputs={str(p):api.sha(p) for p in (Path(__file__),job.DESIGN,w.WORK,pre.OUT/'failure.json')}
    controls=[];original=w.local.policy_scope.policy.classify
    def forbidden(*args,**kwargs):raise AssertionError('producer classifier called by independent failed preflight audit')
    w.local.policy_scope.policy.classify=forbidden
    try:
        job.parent.b.old.parent.configure()
        with job.prior.snapshot.scope(api,d['cases'][0]['spec']['field_metadata']):
            geometry=pre.tests.prior.geometry()
            for path in paths:
                receipt=api.read(path.with_suffix('.preflight_audit.json'));case=next(c for c in d['cases'] if c['id']==receipt['case'])
                before,oracle=pre.ns['seed'](d,case)
                independent=w.q.independent_file(path,api.sha(job.DESIGN))
                record,prefix=job.codec.read_record(path,api.sha(job.DESIGN))
                api.require(api.digest(independent)==api.digest(record),'independent full compressed/uncompressed/history decode')
                audit=job.kernel.evaluate(independent,case['spec'],job.binding(d,case),before,geometry,api.sha(job.DESIGN),d['minimum_gap_semantics'])
                api.require(audit['passed'] and not record['result']['rejected'],'all unchanged physical/clock/health gates pass')
                api.require({k:v for k,v in audit.items() if k!='audit_seconds'}=={k:v for k,v in receipt['summary'].items() if k!='audit_seconds'},'full independent numerical audit reproduction')
                account=api.read(path.with_suffix('.accounting.json'));launch=api.read(path.with_suffix('.launch.json'))
                steps=record['result']['steps']-before['state']['steps']
                api.require(steps==len(record['rows'])==account['accepted_steps']==launch['reserved_new_accepted_steps']==1000
                    and account['raw_sha256']==receipt['raw_sha256']==api.sha(path) and launch['input_checkpoint_sha256']==api.digest(before),'exact failure-inclusive saved/accepted ledger and ancestry')
                different=[i for i,(a,b) in enumerate(zip(record['rows'],oracle['rows'])) if a!=b]
                fields={}
                for a,b in zip(record['rows'],oracle['rows']):
                    for key in set(a)|set(b):
                        if a.get(key)!=b.get(key):fields[key]=fields.get(key,0)+1
                changed=[i for i,call in enumerate(record['normal_gap_operand_policy']['prepare_calls']) if call['raw_gaps_m']!=call['effective_gaps_m']]
                rows=record['rows'];old=oracle['rows'];U=case['spec']['config']['target_mean_interstitial_velocity_m_s'];b=case['spec']['config']['prolate_semiaxes_m'][1]
                dp=[np.linalg.norm(np.asarray(a['position_m'])-z['position_m']) for a,z in zip(rows,old)]
                dv=[np.linalg.norm(np.asarray(a['velocity_generalized'][:3])-z['velocity_generalized'][:3]) for a,z in zip(rows,old)]
                da=[np.linalg.norm(np.asarray(a['orientation'])-z['orientation']) for a,z in zip(rows,old)]
                dt=[abs(a['time_s']-z['time_s']) for a,z in zip(rows,old)]
                first=[]
                if different:
                    i=different[0]
                    for key in sorted(rows[i]):
                        if rows[i][key]!=old[i][key]:first.append(dict(field=key,revised=rows[i][key],original=old[i][key]))
                controls_for=[]
                for field in ('gap','raw_gap','clock','velocity','contract'):
                    bad=copy.deepcopy(record)
                    if field=='gap':bad['normal_gap_operand_policy']['prepare_calls'][0]['effective_gaps_m'][0]+=1e-10
                    elif field=='raw_gap':bad['normal_gap_operand_policy']['prepare_calls'][0]['contacts'][0][1]+=1e-10
                    elif field=='clock':bad['rows'][0]['time_s']+=1e-9
                    elif field=='velocity':bad['rows'][0]['velocity_generalized'][0]+=1e-6
                    else:bad['numerical_policy_contract_sha256']='0'*64
                    try:job.kernel.evaluate(bad,case['spec'],job.binding(d,case),before,geometry,api.sha(job.DESIGN),d['minimum_gap_semantics'])
                    except Exception as exc:controls_for.append(dict(field=field,rejected=True,error=repr(exc)))
                    else:raise AssertionError('corruption accepted '+field)
                controls.extend(controls_for);saved+=steps
                records.append(dict(case=case['id'],saved_steps=steps,independent_physical_audit=audit,old_full_rows_exact=not different,
                    old_checkpoint_state_exact=record['result']['checkpoint']['state']==oracle['result']['checkpoint']['state'],
                    changed_row_count=len(different),first_changed_row=(different[0] if different else None),changed_fields=fields,
                    first_changed_fields=first,policy_changed_prepare_count=len(changed),first_policy_changed_prepare=(changed[0] if changed else None),
                    max_pointwise_position_difference_over_b=max(dp)/b,max_pointwise_axis_difference=max(da),
                    max_pointwise_velocity_difference_over_U=max(dv)/U,max_pointwise_clock_difference_s=max(dt),
                    diagnostic_comparison_not_common_clock_horizon_acceptance=True,raw_sha256=api.sha(path),logical_sha256=prefix.original_sha256))
                for p in path.parent.glob(path.name.replace('.json.xz','')+'.*'):
                    if p.is_file():inputs[str(p)]=api.sha(p)
                print('FAILED_PREFLIGHT_RECORD_AUDITED',case['id'],steps,len(different),fields,flush=True)
        api.require(saved==3000 and len(controls)==15,'full launched saved accounting and corruption controls')
        api.require(sum(not r['old_full_rows_exact'] for r in records)==1,'exact original two fibre controls passed; sphere failed')
        job.verify(d);w.no_competing_trajectory();api.verify_mapping(inputs)
        result=dict(failed_preflight_fully_accounted=True,preflight_passed=False,production_authorized=False,new_trajectory_steps=0,
            saved_steps=3000,independently_physical_passing_steps=3000,old_exact_comparator_failing_saved_steps=1000,
            rejected_trajectory_trials=0,unresolved_reservations=[],all_owned_processes_retired=True,
            producer_gap_classifier_never_called=True,records=records,corruption_controls=controls,inputs=inputs,
            design_sha256=api.sha(job.DESIGN),claim='Original exact sphere comparator failed under explicit revised policy; all saved physical audits passed independently. No promotion of failed preflight, no relaxed physical gate, no campaign or full-horizon acceptance.')
        job.commit(OUT/'results.json',result);job.commit(OUT/'completion.json',dict(results_sha256=api.sha(OUT/'results.json'),preflight_passed=False))
        print('FAILED_PREFLIGHT_ACCOUNTING_CLOSED',saved,api.sha(OUT/'results.json'),flush=True)
    except Exception as exc:
        job.commit(OUT/'failure.json',dict(error=repr(exc),traceback=traceback.format_exc(),new_trajectory_steps=0));raise
    finally:w.local.policy_scope.policy.classify=original

if __name__=='__main__':run()
