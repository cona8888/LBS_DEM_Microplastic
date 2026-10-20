"""Read-only fresh audit of all local bundles, including preserved failures.

No trajectory execution and no writes to any source run. This closes local
evidence/accounting, never the failed production or its separate evaluator.
"""
from pathlib import Path
import hashlib,lzma,os,psutil,traceback
import bounded_contact_dispatch_polish_v4 as harness
import audit_two_contact_routes_v2 as audit2
import audit_two_contact_dispatch_v3 as audit3
import audit_two_contact_polish_v4 as audit4
r=harness.ns;job,api,source=r['job'],r['api'],r['source']
RUN,BASE=r['RUNBASE'],r['EVALBASE'];OUT=BASE/'window_independent_close_01'


def run():
    w=api.read(source.WORK);api.require(job.utc()<job.policy.utc(w['work_end_utc']),'development window remains open')
    r['require_no_diagnostic']();used,pending=r['ledger']();api.require(not pending and used<=w['maximum_new_accepted_trajectory_steps'],'resolved bounded saved-step ledger')
    d=api.read(job.DESIGN);job.verify(d);case=next(c for c in d['cases'] if c['id']==source.NAME);geom=r['geometry'](case)
    launches=sorted(RUN.glob('*/launch.json'),key=lambda p:api.read(p)['utc'])
    files=[Path(__file__),source.WORK,job.DESIGN,BASE/'polish_extended_closure_02/results.json',BASE/'polish_bounded_extension_02/results.json']
    for launch in launches:
        files += [launch,launch.parent/'results.json',launch.parent/'completion.json',launch.parent/'accounting.json',r['DESIGNBASE']/(launch.parent.name+'.json')]
    bindings={str(f):api.sha(f) for f in files};OUT.mkdir(parents=True,exist_ok=False)
    job.commit(OUT/'launch.json',{'pid':os.getpid(),'utc':job.utc().isoformat(),'inputs':bindings,'new_trajectory_steps':0})
    records={};states={};reports=[];comparisons={};failure=None;total=0;passing=0
    try:
        for launchfile in launches:
            folder=launchfile.parent;name=folder.name;pfile=r['DESIGNBASE']/(name+'.json')
            p=api.read(pfile);launch=api.read(launchfile);account=api.read(folder/'accounting.json');result=r['sealed_result'](folder/'results.json')
            api.verify_mapping(p['inputs']);api.verify_mapping(p['new_sources']);api.verify_mapping(result['artifacts'])
            api.require(launch['protocol_sha256']==api.sha(pfile)==result['protocol_sha256'],'immutable protocol identity')
            api.require(p['prior_window_steps']==launch['prior_steps']==total,'complete chronological launch ledger')
            seed=p['seed_diagnostic']
            if seed is None:before=api.read(r['RECON']/'checkpoint_00196.json');prefix=r['prefix196']()
            else:
                api.require(seed in records and records[seed]['independent_passed'],'only independently passing parent seeds')
                before=records[seed]['record']['result']['checkpoint'];prefix=states[seed]
            raw=folder/'call.json.xz';seal=api.read(folder/'call.json.seal.json');packed=raw.read_bytes();unpacked=lzma.decompress(packed)
            api.require(hashlib.sha256(packed).hexdigest()==seal['compressed_sha256'] and len(packed)==seal['compressed_bytes'],'independent compressed seal')
            api.require(hashlib.sha256(unpacked).hexdigest()==seal['uncompressed_sha256'] and len(unpacked)==seal['uncompressed_bytes'],'independent uncompressed seal')
            rec,state=r['frozen'].pre.storage.codec.read_record(raw,api.sha(job.DESIGN),prefix)
            api.require(rec['input_checkpoint_sha256']==api.digest(before),'exact inherited checkpoint lineage')
            delta=rec['result']['steps']-before['state']['steps']
            api.require(account['accepted_steps_known'] and delta==account['accepted_steps']==result['steps'] and 0<=delta<=p['maximum_new_steps']<=10000,'bounded exact accepted-step delta')
            total+=delta;api.require(account['window_steps']==result['window_total_steps']==total,'exact cumulative step ledger')
            api.require(account['raw_sha256']==api.sha(raw) and account['launch_sha256']==api.sha(launchfile),'raw and launch accounting identity')
            api.require(rec['result']['checkpoint']==api.read(folder/'checkpoint.json'),'saved checkpoint exact')
            api.require(state.reference()==api.read(folder/'prefix.json') and rec['result']['history']==api.read(folder/'history.json'),'full raw/history seals and saved prefix')
            checkers={audit2.repair.NAME:audit2,audit3.repair.NAME:audit3,audit4.repair.NAME:audit4}
            checker=checkers[p['candidate']];independent=False;error=None
            try:
                check=checker.kernel(rec,case['spec'],job.binding(d,case),before,geom,api.sha(job.DESIGN),d['minimum_gap_semantics'])
                independent=bool(check['passed'])
            except Exception as exc:error=repr(exc)
            api.require(independent==result['numerical_audit_passed'],'independent gate outcome agrees, including failures')
            if independent:
                api.require(rec['result']['rejected']==0,'passing bundle has no rejected trials');passing+=delta
            else:api.require(name=='extension_call01_01' and delta==488 and rec['result']['rejected']==5,'only already diagnosed preserved local failure')
            records[name]={'record':rec,'independent_passed':independent};states[name]=state
            reports.append({'name':name,'steps':delta,'independent_passed':independent,'rejected_trials':rec['result']['rejected'],'audit_error':error,'raw_sha256':api.sha(raw),'original_record_sha256':state.original_sha256,'history_sha256':state.history_sha256})
            print('WINDOW_REAUDIT',name,delta,independent,flush=True)
        api.require(total==used and passing+488==used,'all passing and failed saved steps retained separately')
        for full,left,right in [('continuation_01','restart_a_01','restart_b_01'),('dispatch_full_01','dispatch_split_a_01','dispatch_split_b_01'),('polish_replay_01','polish_split_a_01','polish_split_b_01'),('polish_long_01','polish_long_split_a_01','polish_long_split_b_01')]:
            f,a,b=[records[n]['record'] for n in (full,left,right)]
            comparisons[full+'_split_rows_exact']=f['rows']==a['rows']+b['rows']
            comparisons[full+'_split_checkpoint_exact']=f['result']['checkpoint']==b['result']['checkpoint']
        api.require(all(comparisons.values()),'all exact local restart comparisons')
        ext=r['sealed_result'](BASE/'polish_bounded_extension_02/results.json')
        api.require(ext['passed'] and ext['reason']=='bounded_target_reached' and ext['extension_steps']==10000,'complete preregistered v4 local extension')
        for call in ext['calls']:
            api.require(records[call['name']]['independent_passed'] and call['results_sha256']==api.sha(RUN/call['name']/'results.json'),'all extension calls independently passing')
    except Exception as error:
        failure={'error':repr(error),'traceback':traceback.format_exc()};job.commit(OUT/'failure.json',failure)
    api.verify_mapping(bindings);job.verify(d);r['require_no_diagnostic']()
    evaluator=None
    if psutil.pid_exists(40572):
        proc=psutil.Process(40572);cmd=proc.cmdline()
        api.require(any('revised_deadline_campaign_v1.py' in x for x in cmd) and cmd[-2:]==['evaluate','campaign'],'existing evaluator exact command identity')
        evaluator={'pid':40572,'cmdline':cmd,'cpu_seconds':sum(proc.cpu_times()[:2]),'preserved_running':True}
    result={'passed':failure is None,'new_trajectory_steps':0,'utc':job.utc().isoformat(),'saved_steps':used,'independently_passing_steps':passing,'failed_saved_steps':used-passing,'remaining_budget':50000-used,'unresolved_reservations':pending,'raw_reaudits':reports,'exact_restart_comparisons':comparisons,'inputs':bindings,'failure':failure,'existing_stage200_evaluator':evaluator,
            'C_free_bytes':job.shutil.disk_usage(r['ROOT']).free,'claim':'Local numerical and storage verification only. No production authority, full fresh paired observation, release fraction, calibration or empirical validation. All older failures preserved.'}
    job.commit(OUT/'results.json',result);job.commit(OUT/'completion.json',{'passed':result['passed'],'results_sha256':api.sha(OUT/'results.json')})
    print('WINDOW_CLOSE',result['passed'],used,passing,'failed',used-passing,flush=True)


if __name__=='__main__':run()
