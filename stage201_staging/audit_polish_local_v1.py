"""Fresh independent local v4 raw/history, mechanics and split closure."""
from pathlib import Path
import os,traceback
import bounded_contact_diagnostic_v1 as runner
import audit_two_contact_dispatch_v3 as oldaudit
import audit_two_contact_polish_v4 as audit
job,api,source=runner.job,runner.api,runner.source
RUN,BASE=runner.RUNBASE,runner.EVALBASE
OUT=BASE/'polish_local_closure_01'
EXPECTED=('dispatch_full_01','polish_replay_01','polish_split_a_01','polish_split_b_01')


def run():
    w=api.read(source.WORK);api.require(job.utc()<job.policy.utc(w['work_end_utc']),'work cutoff')
    d=api.read(job.DESIGN);job.verify(d);case=next(c for c in d['cases'] if c['id']==source.NAME);geom=runner.geometry(case)
    used,pending=runner.ledger();api.require(not pending and used<=w['maximum_new_accepted_trajectory_steps'],'resolved ledger')
    runner.require_no_diagnostic()
    files=[source.WORK,job.DESIGN,Path(__file__),BASE/'extension_failure_audit_01/results.json']
    for name in EXPECTED:
        files += [runner.DESIGNBASE/(name+'.json'),RUN/name/'results.json',RUN/name/'completion.json',RUN/name/'launch.json',RUN/name/'accounting.json']
    bindings={str(p):api.sha(p) for p in files};OUT.mkdir(parents=True,exist_ok=False)
    job.commit(OUT/'launch.json',{'pid':os.getpid(),'utc':job.utc().isoformat(),'new_trajectory_steps':0,'inputs':bindings})
    records={};states={};reports=[];comparisons={};failure=None
    try:
        for name in EXPECTED:
            p=api.read(runner.DESIGNBASE/(name+'.json'));r=runner.sealed_result(RUN/name/'results.json')
            api.verify_mapping(p['inputs']);api.verify_mapping(p['new_sources']);api.verify_mapping(r['artifacts'])
            seed=p['seed_diagnostic']
            if seed is None:before=api.read(runner.RECON/'checkpoint_00196.json');prefix=runner.prefix196()
            else:before=records[seed]['result']['checkpoint'];prefix=states[seed]
            raw=RUN/name/'call.json.xz';rec,state=runner.frozen.pre.storage.codec.read_record(raw,api.sha(job.DESIGN),prefix)
            api.require(api.digest(before)==rec['input_checkpoint_sha256'],'exact raw input checkpoint lineage')
            delta=rec['result']['steps']-before['state']['steps'];a=api.read(RUN/name/'accounting.json')
            api.require(delta==a['accepted_steps']==r['steps'] and 0<delta<=p['maximum_new_steps'],'exact bounded step accounting')
            api.require(a['raw_sha256']==api.sha(raw) and a['launch_sha256']==api.sha(RUN/name/'launch.json'),'raw/ledger binding')
            checker=oldaudit if name=='dispatch_full_01' else audit
            report=checker.kernel(rec,case['spec'],job.binding(d,case),before,geom,api.sha(job.DESIGN),d['minimum_gap_semantics'])
            api.require(report['passed'] and rec['result']['rejected']==0,'original physical/numerical gates and zero rejections')
            api.require(rec['result']['checkpoint']==api.read(RUN/name/'checkpoint.json'),'saved checkpoint exact')
            records[name]=rec;states[name]=state
            reports.append({'name':name,'steps':delta,'passed':True,'raw_sha256':api.sha(raw),'audit':report})
            print('RE_AUDIT',name,delta,flush=True)
        comparisons['split_all_rows_exact']=records['polish_replay_01']['rows']==records['polish_split_a_01']['rows']+records['polish_split_b_01']['rows']
        comparisons['split_full_checkpoint_exact']=records['polish_replay_01']['result']['checkpoint']==records['polish_split_b_01']['result']['checkpoint']
        failed,_=runner.frozen.pre.storage.codec.read_record(RUN/'extension_call01_01/call.json.xz',api.sha(job.DESIGN),states['dispatch_full_01'])
        first=failed['result']['rejected_trials'][0]['time_s'];oracle=[r for r in failed['rows'] if r['time_s']<=first]
        comparisons['all_pre_failure_rows_exact']=records['polish_replay_01']['rows'][:len(oracle)]==oracle
        comparisons['past_failed_extension_end']=records['polish_replay_01']['result']['checkpoint']['state']['t']>failed['result']['checkpoint']['state']['t']
        api.require(all(comparisons.values()),'exact split restart, unchanged original successes, progress past failed local path')
    except Exception as error:
        failure={'error':repr(error),'traceback':traceback.format_exc()};job.commit(OUT/'failure.json',failure)
    api.verify_mapping(bindings);job.verify(d)
    result={'passed':failure is None,'new_trajectory_steps':0,'window_saved_steps':used,'failed_bundle_steps_preserved':488,'inputs':bindings,'reaudits':reports,'comparisons':comparisons,'failure':failure,
            'claim':'Local same-physics numerical/restart verification only. Failed Stage200 and v3 extension remain failed; no production or release claim.'}
    job.commit(OUT/'results.json',result);job.commit(OUT/'completion.json',{'passed':result['passed'],'results_sha256':api.sha(OUT/'results.json')})
    print('POLISH_LOCAL_CLOSURE',result['passed'],used,flush=True)


if __name__=='__main__':run()
