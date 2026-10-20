"""Fresh-process independent seal/kernel/reference ledger closure, zero steps."""
from pathlib import Path
import copy,os,shutil,traceback
import numpy as np
import bounded_policy_references_v1 as base
api,job=base.api,base.job
OUT=base.OUT/'independent_01'

def run():
    w,d=base.prerequisites();base.no_worker();api.require(job.utc()<job.policy.utc(w['work_end_utc']),'reference audit cutoff')
    ready=base.sealed(base.OUT/'prelaunch_qualification_01/results.json')
    api.require(ready['passed'] and ready['design_sha256']==api.sha(base.DESIGN),'qualified reference launch identity')
    api.require(not OUT.exists(),'exclusive independent reference replay')
    job.commit(OUT/'launch.json',dict(pid=os.getpid(),utc=job.utc().isoformat(),new_trajectory_steps=0))
    inputs={str(p):api.sha(p) for p in (Path(__file__),base.DESIGN,base.WORK,base.SELF,Path(base.reference.__file__),base.OUT/'prelaunch_qualification_01/results.json',base.OUT/'prelaunch_qualification_01/completion.json')}
    reports=[];controls=[];total=0
    try:
        with base.reference.forbid_producer():
            job.parent.b.old.parent.configure()
            with job.prior.snapshot.scope(api,d['cases'][0]['spec']['field_metadata']):geometry=base.original_preflight.tests.prior.geometry()
            for name,cap in w['planned_calls'].items():
                folder=base.RUN/name;r=base.sealed(folder/'results.json');api.verify_mapping(r['artifacts'])
                case,before=base.seed(d,name);saved_before=api.read(folder/'input_checkpoint.json')
                api.require(api.digest(before)==api.digest(saved_before),'full independently reconstructed reference seed')
                path=folder/'call.json.xz';independent=base.prior.q.independent_file(path,api.sha(base.DESIGN))
                record,state=job.codec.read_record(path,api.sha(base.DESIGN));api.require(api.digest(independent)==api.digest(record),'full independent compressed/uncompressed/history decode')
                check=base.kernel(independent,d,case,before,geometry)
                api.require(check['passed'] and r['passed'] and not record['result']['rejected'],'original physical numerical gates')
                api.require({k:v for k,v in check.items() if k!='audit_seconds'}=={k:v for k,v in r['numerical_audit'].items() if k!='audit_seconds'},'full independent numerical summary')
                account=api.read(folder/'accounting.json');launch=api.read(folder/'launch.json')
                steps=record['result']['steps']-(before['state']['steps'] if before else 0)
                api.require(steps==len(record['rows'])==r['saved_steps']==r['independently_physical_passing_steps']==account['saved_steps']==launch['reserved_max_steps']==cap,'complete inclusive saved/accepted/reserved accounting')
                api.require(account['launch_sha256']==api.sha(folder/'launch.json') and account['raw_sha256']==api.sha(path)
                    and launch['input_checkpoint_sha256']==api.digest(before) and launch['design_sha256']==api.sha(base.DESIGN)
                    and launch['contract_sha256']==api.sha(base.WORK),'immutable launch/raw/input/design/policy ancestry')
                api.require(api.digest(record['result']['checkpoint'])==api.digest(api.read(folder/'checkpoint.json')) and record['result']['history']==api.read(folder/'history.json')
                    and state.reference()==api.read(folder/'prefix.json'),'full checkpoint/history state seals')
                call=next((c for c in record['normal_gap_operand_policy']['prepare_calls'] if c['contacts']),None)
                for field in ('effective_gap','raw_gap','clock','velocity','policy_contract','classifier_source','operand_scale'):
                    bad=copy.deepcopy(record);active=next((c for c in bad['normal_gap_operand_policy']['prepare_calls'] if c['contacts']),None)
                    if field=='effective_gap':
                        if active:active['effective_gaps_m'][0]+=1e-10
                        else:bad['normal_gap_operand_policy']['prepare_calls'][0]['effective_gaps_m'].append(1e-10)
                    elif field=='raw_gap':
                        if active:active['contacts'][0][1]+=1e-10
                        else:bad['normal_gap_operand_policy']['prepare_calls'][0]['contacts'].append([999,1e-10,[1.,0.,0.],[0.,0.,0.]])
                    elif field=='clock':bad['rows'][0]['time_s']+=1e-9
                    elif field=='velocity':bad['rows'][0]['velocity_generalized'][0]+=1e-6
                    elif field=='policy_contract':bad['numerical_policy_contract_sha256']='0'*64
                    elif field=='classifier_source':bad['reference_classifier_sha256']='0'*64
                    elif active:active['metadata'][0]['classification']['absolute_operand_scale_m']+=1e-10
                    else:bad['normal_gap_operand_policy']['prepare_calls'][0]['metadata'].append(dict(context={},classification={}))
                    try:base.kernel(bad,d,case,before,geometry)
                    except Exception as exc:controls.append(dict(name=name,field=field,rejected=True,error=repr(exc)))
                    else:raise AssertionError('corrupt reference accepted '+name+':'+field)
                total+=steps;reports.append(dict(name=name,case=case['id'],saved_steps=steps,independently_physical_passing_steps=steps,audit=check,
                    raw_sha256=api.sha(path),logical_sha256=state.original_sha256,whole_checkpoint_sha256=api.digest(record['result']['checkpoint']),
                    had_active_contacts=bool(call),compute_seconds=r['compute_seconds'],transaction_seconds=r['transaction_seconds']))
                for path in folder.glob('*'):
                    if path.is_file():inputs[str(path)]=api.sha(path)
                print('INDEPENDENT_REFERENCE_REAUDIT',name,steps,flush=True)
        saved,pending=base.ledger();api.require(saved==total==3600 and not pending and len(reports)==6 and len(controls)==42,'all six reference ledgers and corruption controls closed')
        api.require(not list(base.RUN.rglob('failure.json')) and not any('.pending.' in p.name for p in base.RUN.rglob('*')),'no failed/unsealed reference record')
        base.no_worker();base.verify(d);api.verify_mapping(inputs)
        free=shutil.disk_usage(base.ROOT).free;api.require(free>=w['minimum_free_disk_bytes'],'current reference disk reserve')
        result=dict(passed=True,reference_qualification_closed=True,new_trajectory_steps=0,saved_steps=3600,independently_physical_passing_steps=3600,
            rejected_trials=0,unresolved_reservations=[],all_owned_processes_retired=True,producer_classifier_never_called=True,
            separate_stage213_steps=4000,failed_stage214_saved_steps=3000,failed_stage214_old_exact_comparator_steps=1000,
            total_saved_policy_qualification_steps_so_far=10600,records=reports,corruption_controls=controls,inputs=inputs,C_free_bytes=free,
            design_sha256=api.sha(base.DESIGN),contract_sha256=api.sha(base.WORK),production_authorized=False,full_six_case_stack_qualified=False,
            old_failed_preflight_remains_failed=True,claim='Six independently computed fixed-policy references accepted for exact new-policy comparisons only. No production or original-raw-gap/final-horizon acceptance.')
        job.commit(OUT/'results.json',result);job.commit(OUT/'completion.json',dict(passed=True,results_sha256=api.sha(OUT/'results.json')))
        print('INDEPENDENT_POLICY_REFERENCES_CLOSED',total,len(controls),api.sha(OUT/'results.json'),flush=True)
    except Exception as exc:
        job.commit(OUT/'failure.json',dict(error=repr(exc),traceback=traceback.format_exc(),new_trajectory_steps=0));raise

if __name__=='__main__':run()
