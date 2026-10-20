"""Independent saved-record audit including the rejected native trajectory.

Evidence/accounting closure does not promote a failed numerical-identity test.
"""
from pathlib import Path
import os,psutil,sys,traceback
import measure_native_prefix_v1 as latest
import measure_qualified_long_fine_v1 as long
api,job,q=latest.api,latest.job,latest.q
DESIGN=latest.WORK.with_name('failure_ledger_audit_01.json')
OUT=latest.OUT.with_name('failure_ledger_audit_01')
PROBES=(latest.template,long,latest.previous,latest)

def prepare():
    inputs=[latest.WORK,latest.ORACLE,latest.ORACLE.with_suffix('.seal.json')]
    sources=[Path(__file__),Path(q.__file__),Path(job.kernel.evaluate.__code__.co_filename.split('::')[0])]
    for probe in PROBES:
        probe.verify(api.read(probe.DESIGN));sources.append(Path(probe.__file__));inputs.append(probe.DESIGN)
        inputs.extend(x for x in probe.RUN.iterdir() if x.is_file())
        inputs.extend(x for x in probe.OUT.iterdir() if x.is_file())
    p={'stage':'Stage199 independent evidence and failure-inclusive ledger closure','prior_recovery_steps':53086,'expected_counts':[3580,7406,3580,3580],'cumulative_recovery_steps':71232,
       'expected_identity_failure':'native_prefix_01','first_different_row':2995,'new_trajectory_steps':0,'production_authorized':False,
       'sources':{str(x):api.sha(x) for x in sources},'inputs':{str(x):api.sha(x) for x in inputs}}
    p['binding']=api.digest(p);job.commit(DESIGN,p);print('FAILURE_LEDGER_PROTOCOL',api.sha(DESIGN),flush=True)

def verify(p):
    api.require(p['binding']==api.digest({k:v for k,v in p.items() if k!='binding'}),'audit binding')
    api.verify_mapping(p['sources']);api.verify_mapping(p['inputs'])

def run():
    p=api.read(DESIGN);verify(p);work=api.read(latest.WORK)
    api.require(job.utc()<job.policy.utc(work['work_end_utc']),'work cutoff')
    api.require(not any(x.pid!=os.getpid() and 'python' in (x.info['name'] or '').lower() and 'matdem_microplastic' in ' '.join(x.info['cmdline'] or []).lower() for x in psutil.process_iter(['name','cmdline'])),'no other owned worker')
    OUT.mkdir(parents=True,exist_ok=False)
    job.commit(OUT/'launch.json',{'pid':os.getpid(),'argv':sys.argv,'utc':job.utc().isoformat(),'new_trajectory_steps':0,'protocol_sha256':api.sha(DESIGN)})
    reports=[];total=0
    try:
        oracle=q.independent_file(latest.ORACLE,api.sha(latest.template.old.DESIGN));job.parent.b.old.parent.configure()
        for probe,expected in zip(PROBES,p['expected_counts']):
            d=api.read(probe.DESIGN);probe.verify(d);raw=probe.RUN/'serial.json.xz';before=api.read(probe.RUN/'initial.json')
            rec=q.independent_file(raw,api.sha(probe.DESIGN));account=api.read(raw.with_suffix('.accounting.json'))
            api.require(len(rec['rows'])==account['accepted_steps']==expected and account['raw_sha256']==api.sha(raw),'full accepted-step accounting')
            case=next(c for c in d['cases'] if c['id']=='s2_i0_fibre_f0p03125')
            with job.prior.snapshot.scope(api,case['spec']['field_metadata']):
                geo=latest.template.old.pre.prior.geometry()
                check=job.kernel.evaluate(rec,case['spec'],job.binding(d,case),before,geo,api.sha(probe.DESIGN),d['minimum_gap_semantics'])
            api.require(check['passed'] and not rec['result']['rejected'],'original independent physical/health/clock audit')
            prefix=rec['rows'][:3580];exact=probe.storage.base.raw_bytes(prefix)==probe.storage.base.raw_bytes(oracle['rows'])
            fullstate=probe.storage.base.raw_bytes(rec['result']['checkpoint']['state'])==probe.storage.base.raw_bytes(oracle['result']['checkpoint']['state'])
            if probe is latest:
                f=api.read(probe.OUT/'failure.json')
                first=next(i for i,(a,b) in enumerate(zip(prefix,oracle['rows'])) if a!=b)
                api.require(not exact and not fullstate and first==2995 and f['known_new_accepted_steps']==3580 and not f['accepted_step_accounting_unresolved'],'failure preserved and independently reproduced')
                status='rejected_exact_identity';timing=None
            else:
                result=probe.OUT/'results.json';r=api.read(result)
                api.require(r['passed'] and api.read(result.parent/'completion.json')['results_sha256']==api.sha(result),'successful predecessor seal')
                api.verify_mapping(r['artifacts']);api.require(exact and (probe is long or fullstate),'qualified reference identity')
                span=check['stop_s']-check['start_s'];factor=case['spec']['horizon_s']*work['runtime_and_storage_margin']/span/3600
                api.require(span==r['simulated_seconds'] and r['compute_seconds']==rec['compute_call_wall_s'] and r['transaction_seconds']*factor==r['fine_transaction_hours_with_margin'],'original timing and margin arithmetic')
                timing=r['fine_transaction_hours_with_margin'];status='censored_healthy_prefix' if probe is long else 'exact_local_prefix'
            total+=expected;reports.append({'name':probe.RUN.name,'accepted_steps':expected,'status':status,'full_known_prefix_exact':exact,'fixed_cap_full_state_exact':fullstate,'independent_numerical_audit':check,'qualified_runtime_scenario_hours':timing,'raw_sha256':api.sha(raw)})
            print('LEDGER_AUDITED',probe.RUN.name,expected,status,flush=True)
        accounts=list(latest.RUN.parent.glob('*/*.accounting.json'));launches=list(latest.RUN.parent.glob('*/*.launch.json'))
        api.require(len(accounts)==len(launches)==4 and sum(api.read(x)['accepted_steps'] for x in accounts)==total,'no unresolved or extra trajectory reservation')
        api.require(total+53086==71232,'exact cumulative ledger');verify(p)
        r={'status':'closed_with_preserved_candidate_failure','evidence_and_accounting_passed':True,'all_candidates_passed':False,'failed_candidate_preserved':'native_prefix_01','new_trajectory_steps':0,'stage199_accepted_steps':total,'cumulative_recovery_steps':71232,'remaining_recovery_steps':28768,'no_unresolved_reservation':True,'no_other_owned_worker':True,'probes':reports,'protocol_sha256':api.sha(DESIGN),'production_authorized':False,'complete_observations':0}
        job.commit(OUT/'results.json',r);job.commit(OUT/'completion.json',{'results_sha256':api.sha(OUT/'results.json')});print('LEDGER_CLOSED_WITH_REJECTION',71232,flush=True)
    except Exception as e:
        job.commit(OUT/'failure.json',{'error':repr(e),'traceback':traceback.format_exc(),'new_trajectory_steps':0});raise

if __name__=='__main__':
    if sys.argv[1:]==['prepare']:prepare()
    elif sys.argv[1:]==['run']:run()
    else:raise ValueError('prepare | run')
