"""Independent saved-byte/physics/clock/ledger audit of Stage199 cost probes."""
from pathlib import Path
import hashlib,os,psutil,sys,traceback
import measure_qualified_long_fine_v1 as measured
ROOT,api,job,q=measured.ROOT,measured.api,measured.job,measured.q
DESIGN=measured.WORK.with_name('independent_cost_audit_01.json')
OUT=measured.OUT.with_name('independent_cost_audit_01')

def prepare():
    paths=[measured.OUT/'results.json',measured.prior.OUT/'results.json']
    inputs=[measured.WORK,measured.DESIGN,measured.prior.DESIGN,measured.ORACLE,measured.ORACLE.with_suffix('.seal.json')]
    for path in paths:
        r=api.read(path);api.require(r['passed'] and api.read(path.parent/'completion.json')['results_sha256']==api.sha(path),'saved sealed measurement')
        api.verify_mapping(r['artifacts']);inputs.extend([path,path.parent/'completion.json',*[Path(x) for x in r['artifacts']]])
    for name in ('solver_brackets_01','trf_helpers_01','dense_dispatch_01','transaction_json_01'):
        path=OUT.parent/name/'results.json';r=api.read(path);api.require(r['passed'] and api.read(path.parent/'completion.json')['results_sha256']==api.sha(path),'sealed local qualification');inputs.extend([path,path.parent/'completion.json'])
    for name in ('benchmark.json','benchmark_completion.json'):inputs.append(OUT.parent/'transaction_json_01'/name)
    p={'stage':'Stage199 independent cost-evidence closure','new_trajectory_steps':0,'sources':{str(Path(__file__)):api.sha(__file__),str(Path(measured.__file__)):api.sha(measured.__file__),str(Path(q.__file__)):api.sha(q.__file__),str(Path(job.kernel.__file__)):api.sha(job.kernel.__file__)},'inputs':{str(x):api.sha(x) for x in inputs},'production_authorized':False,'prior_recovery_steps':53086}
    p['binding']=api.digest(p);job.commit(DESIGN,p);print('COST_AUDIT_PROTOCOL',api.sha(DESIGN),flush=True)

def run():
    p=api.read(DESIGN);api.require(p['binding']==api.digest({k:v for k,v in p.items() if k!='binding'}),'audit binding');api.verify_mapping(p['sources']);api.verify_mapping(p['inputs'])
    work=api.read(measured.WORK);api.require(job.utc()<job.policy.utc(work['work_end_utc']),'work clock')
    for proc in psutil.process_iter(['name','cmdline']):
        if proc.pid!=os.getpid() and 'python' in (proc.info['name'] or '').lower():api.require('matdem_microplastic' not in ' '.join(proc.info['cmdline'] or []).lower(),'all diagnostic workers retired')
    OUT.mkdir(parents=True,exist_ok=False);job.commit(OUT/'launch.json',{'pid':os.getpid(),'argv':sys.argv,'utc':job.utc().isoformat(),'new_trajectory_steps':0,'protocol_sha256':api.sha(DESIGN)})
    reports=[];total=0
    try:
        oracle=q.independent_file(measured.ORACLE,api.sha(measured.prior.old.DESIGN))
        job.parent.b.old.parent.configure()
        for probe in (measured.prior,measured):
            d=api.read(probe.DESIGN);probe.verify(d);r=api.read(probe.OUT/'results.json');path=probe.RUN/'serial.json.xz';before=api.read(probe.RUN/'initial.json')
            record=q.independent_file(path,api.sha(probe.DESIGN));case=next(c for c in d['cases'] if c['id']=='s2_i0_fibre_f0p03125')
            with job.prior.snapshot.scope(api,case['spec']['field_metadata']):
                geo=measured.prior.old.pre.prior.geometry()
                check=job.kernel.evaluate(record,case['spec'],job.binding(d,case),before,geo,api.sha(probe.DESIGN),d['minimum_gap_semantics'])
            count=len(record['rows']);account=api.read(path.with_suffix('.accounting.json'));api.require(account['accepted_steps']==count and account['raw_sha256']==api.sha(path),'exact raw/accepted step accounting')
            api.require(check['passed'] and not record['result']['rejected'] and record['result']['status']==r.get('status','paused_checkpoint'),'independent original numerical health/clock/balance/status')
            actual=probe.storage.base.raw_bytes(record['rows'][:3580]);expected=probe.storage.base.raw_bytes(oracle['rows'])
            api.require(actual==expected and len(record['rows'][:3580])==3580,'known archived fine trajectory exact')
            if probe is measured.prior:
                api.require(probe.storage.base.raw_bytes(record['result']['checkpoint']['state'])==probe.storage.base.raw_bytes(oracle['result']['checkpoint']['state']),'fixed-cap full state exact')
            span=check['stop_s']-check['start_s'];factor=case['spec']['horizon_s']*work['runtime_and_storage_margin']/span/3600
            api.require(span==r['simulated_seconds'] and record['compute_call_wall_s']==r['compute_seconds'],'source timing and physical interval binding')
            for key,value in [('fine_compute_hours_with_margin',r['compute_seconds']*factor),('fine_transaction_hours_with_margin',r['transaction_seconds']*factor)]:
                api.require(value==r[key],'independent original-margin scenario arithmetic')
            total+=count;reports.append({'probe':probe.OUT.name,'steps':count,'status':record['result']['status'],'raw_sha256':api.sha(path),'known_rows_sha256':hashlib.sha256(actual).hexdigest(),'audit':check,'compute_hours_with_margin':r['fine_compute_hours_with_margin'],'transaction_hours_with_margin':r['fine_transaction_hours_with_margin']})
            print('INDEPENDENT_COST_EXACT',probe.OUT.name,count,record['result']['status'],flush=True)
        accounts=sorted(measured.RUN.parent.rglob('*.accounting.json'));api.require(len(accounts)==2 and sum(api.read(x)['accepted_steps'] for x in accounts)==total,'complete Stage199 trajectory ledger')
        cumulative=53086+total;available=(job.policy.utc(work['simulation_cutoff_utc'])-job.utc()).total_seconds()/3600
        api.require(cumulative==api.read(measured.OUT/'results.json')['cumulative_recovery_steps'] and cumulative<=100000,'cumulative recovery bound')
        api.verify_mapping(p['sources']);api.verify_mapping(p['inputs'])
        result={'passed':True,'numerical_and_evidence_audit_passed':True,'new_trajectory_steps_in_audit':0,'stage199_accepted_steps':total,'cumulative_recovery_steps':cumulative,'remaining_recovery_steps':100000-cumulative,'no_unresolved_reservation':True,'no_other_owned_worker':True,'probes':reports,'available_simulation_hours_at_audit':available,'local_fine_runtime_scenario_passed':reports[-1]['transaction_hours_with_margin']<=available,'full_stack_qualified':False,'production_authorized':False,'complete_observations':0,'claim':'Local verification only. Budget-limited prefix remains censored. No full-path, population release or empirical validation; original resource margin unchanged.','protocol_sha256':api.sha(DESIGN)}
        job.commit(OUT/'results.json',result);job.commit(OUT/'completion.json',{'passed':True,'results_sha256':api.sha(OUT/'results.json')});print('COST_AUDIT_PASS',cumulative,'runtime',result['local_fine_runtime_scenario_passed'],flush=True)
    except Exception as e:
        job.commit(OUT/'failure.json',{'error':repr(e),'traceback':traceback.format_exc(),'new_trajectory_steps':0});raise

if __name__=='__main__':
    if sys.argv[1:]==['prepare']:prepare()
    elif sys.argv[1:]==['run']:run()
    else:raise ValueError('prepare | run')
