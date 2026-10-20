"""Fresh-process full raw/kernel replay and inclusive serial/split ledger."""
from pathlib import Path
import copy,os,sys,traceback
import bounded_normal_gap_trajectory_v1 as base
job,api=base.job,base.api

def run(label,final=False):
    w,d=base.prerequisites();base.no_worker();api.require(job.utc()<job.policy.utc(w['work_end_utc']),'bounded independent qualification clock')
    names=['serial_01','split_a_01','split_b_01']
    if final:names+=['extension_a_01','extension_b_01','extension_c_01','extension_d_01']
    case=next(c for c in d['cases'] if c['id']==w['case']);geometry=base.geometry(case)
    inputs={str(p):api.sha(p) for p in (Path(__file__),base.WORK,job.DESIGN)}
    OUT=base.EVALBASE/label;OUT.mkdir(parents=True,exist_ok=False)
    job.commit(OUT/'launch.json',dict(pid=os.getpid(),utc=job.utc().isoformat(),new_trajectory_steps=0,inputs=inputs))
    saved=0;checks=[];records={};rejections=[]
    # The independent replay must never execute the producer policy classifier.
    original_classifier=base.policy_scope.policy.classify
    def forbidden(*args,**kwargs):raise RuntimeError('producer classifier used in independent replay')
    base.policy_scope.policy.classify=forbidden
    try:
        for name in names:
            folder=base.RUNBASE/name;result=base.sealed(folder/'results.json');planpath=base.DESIGNBASE/(name+'.json');plan=api.read(planpath)
            api.verify_mapping(plan['inputs']);api.verify_mapping(plan['sources']);api.verify_mapping(result['artifacts'])
            seed=base.RUNBASE/plan['seed'] if plan['seed'] else base.RECON
            before=api.read(seed/('checkpoint.json' if plan['seed'] else 'checkpoint_00032.json'))
            prior=base.prefix(seed,None if plan['seed'] else 32)
            record,state=base.frozen.stack.storage.codec.read_record(folder/'call.json.xz',api.sha(job.DESIGN),prior)
            api.require(record['numerical_policy_contract_sha256']==api.sha(base.WORK)
                and record['old_design_identity_is_seed_lineage_not_original_gap_policy_acceptance'],'exact revised-policy/nonpromotion disclosure')
            check=base.auditor.kernel(record,case['spec'],job.binding(d,case),before,geometry,api.sha(job.DESIGN),d['minimum_gap_semantics'])
            account=api.read(folder/'accounting.json');steps=record['result']['steps']-before['state']['steps']
            api.require(check['passed'] and result['numerical_audit_passed'] and record['result']['rejected']==0,'original remaining numerical gates and zero-rejection '+name)
            api.require(0<steps==len(record['rows'])==account['saved_steps']==result['steps']==result['independently_accepted_steps']<=plan['cap'],'full inclusive saved/accepted step count '+name)
            api.require(account['launch_sha256']==api.sha(folder/'launch.json') and account['raw_sha256']==api.sha(folder/'call.json.xz')
                and state.reference()==api.read(folder/'prefix.json'),'launch/raw/history seals '+name)
            api.require(api.digest(record['result']['checkpoint'])==api.digest(api.read(folder/'checkpoint.json')),'whole checkpoint identity '+name)
            for field in ('effective_gap','raw_gap','time','velocity','policy_contract'):
                bad=copy.deepcopy(record)
                if field=='effective_gap':bad['normal_gap_operand_policy']['prepare_calls'][0]['effective_gaps_m'][0]=1e-12
                elif field=='raw_gap':bad['normal_gap_operand_policy']['prepare_calls'][0]['contacts'][0][1]+=1e-12
                elif field=='time':bad['rows'][0]['time_s']+=1e-10
                elif field=='velocity':bad['rows'][0]['velocity_generalized'][0]+=1e-6
                else:bad['numerical_policy_contract_sha256']='0'*64
                try:
                    api.require(bad['numerical_policy_contract_sha256']==api.sha(base.WORK),'policy contract corruption')
                    base.auditor.kernel(bad,case['spec'],job.binding(d,case),before,geometry,api.sha(job.DESIGN),d['minimum_gap_semantics'])
                except (RuntimeError,AssertionError):rejections.append(name+':'+field)
                else:raise RuntimeError('corrupt trajectory accepted '+name+':'+field)
            records[name]=record;saved+=steps
            checks.append(dict(name=name,steps=steps,stop_s=record['result']['time_s'],passed=True,audit=check,compute_seconds=result['compute_seconds']))
            for path in list(folder.glob('*'))+[planpath]:
                if path.is_file():inputs[str(path)]=api.sha(path)
            print('INDEPENDENT_NORMAL_GAP_RECORD',name,steps,check['passed'],flush=True)
        serial=records['serial_01'];first=records['split_a_01'];second=records['split_b_01']
        api.require(serial['rows']==first['rows']+second['rows'],'exact full serial/split accepted rows')
        api.require(api.digest(serial['result']['checkpoint'])==api.digest(second['result']['checkpoint']),'exact full serial/split checkpoint state')
        used,pending=base.ledger();api.require(not pending and used==saved<=w['maximum_new_saved_trajectory_steps'],'full saved/failure-inclusive ledger closed')
        base.no_worker();api.verify_mapping(inputs);job.verify(d)
        result=dict(passed=True,new_trajectory_steps=0,independently_passing_saved_steps=saved,inclusive_saved_steps=saved,
                    independently_rejected_saved_steps=0,unresolved_reservations=pending,exact_restart_full_rows=True,
                    exact_restart_full_checkpoint=True,all_owned_diagnostics_retired=True,records=checks,
                    producer_gap_classifier_never_called=True,corrupt_controls_rejected=rejections,inputs=inputs,
                    source_policy_explicit=True,production_authorized=False,old_stage209_remains_failed=True,
                    claim='Bounded local trajectory verification with revised normal-gap operands only. Not an original raw-gap pass, full six-case convergence, production readiness, population release or empirical validation.')
        job.commit(OUT/'results.json',result);job.commit(OUT/'completion.json',dict(results_sha256=api.sha(OUT/'results.json'),new_trajectory_steps=0))
        print('INDEPENDENT_NORMAL_GAP_TRAJECTORIES',label,saved,len(checks),len(rejections),api.sha(OUT/'results.json'),flush=True)
    except Exception as error:
        job.commit(OUT/'failure.json',dict(error=repr(error),traceback=traceback.format_exc(),new_trajectory_steps=0));raise
    finally:base.policy_scope.policy.classify=original_classifier

if __name__=='__main__':run(sys.argv[1],len(sys.argv)>2 and sys.argv[2]=='final')
