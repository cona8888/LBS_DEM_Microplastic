"""Bounded six-case continuation and exact restart with qualified optimizations.

132,000 new steps maximum. Conditional development windows, not production.
"""
from pathlib import Path
import copy,datetime,os,shutil,sys,time,traceback
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'stage175_staging'),str(ROOT/'stage176_staging')]
import combined_cost_preflight_v1 as prior
import qualify_record_xz_v1 as storage_test
import lossless_record_xz_v1 as codec
api,parent,p,fast=prior.api,prior.parent,prior.p,prior.fast
snapshot,candidate=prior.snapshot,prior.candidate
DESIGN=ROOT/'stage177_designs/extended_optimized_20260924/design_01.json'
RUN=ROOT/'stage177_runs/extended_optimized_20260924/preflight_01'
OUT=ROOT/'stage177_evaluations/extended_optimized_20260924/evaluation_01'


def prepare():
    prior.verify(api.read(prior.DESIGN));sd=api.read(storage_test.DESIGN);storage_test.verify(sd)
    audits=[prior.OUT.parent/'independent_audit_01',storage_test.OUT]
    for folder in audits:
        r=api.read(folder/'results.json');api.require(r.get('integration_verified',r.get('passed',False)),'qualified prerequisite')
        api.require(api.read(folder/'completion.json')['results_sha256']==api.sha(folder/'results.json'),'prerequisite seal')
    old=api.read(prior.DESIGN);cases=[];inputs=[prior.DESIGN,storage_test.DESIGN]
    for c in old['cases']:
        source=prior.RUN/c['id']/'segment_003.json.gz';rec=parent.storage.read_record(source,api.sha(prior.DESIGN))
        api.require(rec['spec']==c['spec'],'unchanged frozen spec')
        cases.append({**c,'source':str(source),'source_design_sha256':api.sha(prior.DESIGN),'initial_checkpoint_state_sha256':rec['result']['checkpoint']['state_sha256']})
        inputs+=[source,source.with_suffix('.seal.json')]
    inputs+=[f/n for f in audits for n in ['results.json','completion.json']]
    d={'stage':'Stage177','physical_changes':[],'cases':cases,'blocks_per_case':2,'steps_per_block':10000,
       'restart_steps':1000,'restart_split':[371,629],'maximum_new_steps':132000,'maximum_steps_per_trial':22000,
       'wall_s':1100.,'stop_utc':'2026-09-24T02:46:55+00:00','minimum_free_disk_bytes':20*1024**3,
       'prior_work_window_steps':69175,'work_window_step_ceiling':250000,'sources':parent.source_map(),'inputs':{str(x):api.sha(x) for x in inputs},
       'minimum_gap_semantics':old['minimum_gap_semantics'],'codec':codec.FORMAT,
       'claim':'Conditional six-case robustness and exact restart at unchanged physics. Not full observation or empirical validation. No production launch.'}
    api.require(d['prior_work_window_steps']+d['maximum_new_steps']<=d['work_window_step_ceiling'],'cumulative work allowance')
    d['binding']=api.digest(d);DESIGN.parent.mkdir(parents=True,exist_ok=True);api.write(DESIGN,d);print('FROZEN',api.sha(DESIGN),flush=True)


def verify(d):
    api.require(d['binding']==api.digest({k:v for k,v in d.items() if k!='binding'}),'design binding')
    api.verify_mapping(d['sources']);api.verify_mapping(d['inputs']);prior.verify(api.read(prior.DESIGN));storage_test.verify(api.read(storage_test.DESIGN))


def run():
    d=api.read(DESIGN);verify(d);prior.previous.unit.upstream.prior.unit.check_time();RUN.mkdir(exist_ok=False,parents=True);OUT.mkdir(exist_ok=False,parents=True)
    started=time.perf_counter();parent.b.old.parent.configure();fast.capture_systems=True;total=0;artifacts={};ledger=[]
    api.write(RUN/'launch.json',{'pid':os.getpid(),'argv':sys.argv,'design_sha256':api.sha(DESIGN),'utc':datetime.datetime.now(datetime.timezone.utc).isoformat()})
    artifacts[str(RUN/'launch.json')]=api.sha(RUN/'launch.json')
    def execute(c,binding,cp,cap,path):
        nonlocal total
        prior.previous.unit.upstream.prior.unit.check_time()
        api.require(time.perf_counter()-started<d['wall_s'] and total+cap<=d['maximum_new_steps'],'bounded work allowance')
        api.require(shutil.disk_usage(ROOT).free>d['minimum_free_disk_bytes']+codec.MAX_COMPRESSED,'disk reserve')
        before=copy.deepcopy(cp);step0=cp['state']['steps'];t0=cp['state']['t'];t=time.perf_counter()
        with p.hot.scope(),parent.storage.step_budget_scope(20_000_000),parent.fix.scope(),fast.scope(parent.engine.runtime,True),candidate.scope():
            result,rows=parent.engine.runtime.execute(c['spec'],binding,checkpoint=cp,pause=step0+cap)
        compute=time.perf_counter()-t
        rec={'spec':c['spec'],'result':result,'rows':rows,'input_checkpoint_sha256':api.digest(before),'effective_binding':parent.model.binding_for(binding,True),
             'design_sha256':api.sha(DESIGN),'step_cap':cap,'compute_call_wall_s':compute,
             'early_attempts':copy.deepcopy(fast.attempts),'repairs':copy.deepcopy(fast.old.telemetry),
             'backend_calls':copy.deepcopy(parent.model.calls),'certificates':copy.deepcopy(parent.fix.telemetry),
             'sweep_certificates':copy.deepcopy(candidate.records),'minimum_gap_semantics':d['minimum_gap_semantics']}
        seal=codec.write_record(path,rec);total+=len(rows)
        # The prior checker takes an explicit cap stored in each record and does not change gates.
        prior.check(rec,before,binding)
        api.require(codec.read_bytes(path,api.sha(DESIGN))==codec.raw_bytes(rec),'exact stored evidence bytes')
        tx={'path':str(path),'sha256':api.sha(path),'compute_s':compute,'transaction_s':time.perf_counter()-t,
            'simulated_s':result['time_s']-t0,'steps':len(rows),'compressed_bytes':path.stat().st_size,'uncompressed_bytes':seal['uncompressed_bytes']}
        txpath=path.with_suffix('.transaction.json');api.write(txpath,tx)
        for x in [path,path.with_suffix('.seal.json'),txpath]:artifacts[str(x)]=api.sha(x)
        fast.attempts.clear();fast.telemetry.clear();fast.old.telemetry.clear();candidate.records.clear();parent.fix.telemetry.clear();parent.model.calls.clear()
        print(c['id'],path.name,'steps',len(rows),'time',result['time_s'],'compute',round(compute,3),'transaction',round(tx['transaction_s'],3),'bytes',path.stat().st_size,flush=True)
        return rec,tx
    try:
        with snapshot.scope(api,d['cases'][0]['spec']['field_metadata']):
            api.fields.load(2,1.,6)
            for c in d['cases']:
                folder=RUN/c['id'];folder.mkdir();src=parent.storage.read_record(Path(c['source']),c['source_design_sha256'])
                binding=api.digest([d['binding'],c['id']]);cp=parent.model.checkpoint(c['spec'],binding,src['result']['checkpoint'],True);entries=[]
                for i in range(1,d['blocks_per_case']+1):
                    rec,tx=execute(c,binding,cp,d['steps_per_block'],folder/f'segment_{i:03d}.json.xz');cp=rec['result']['checkpoint'];entries.append(tx)
                seed=copy.deepcopy(cp)
                full,tx=execute(c,binding,copy.deepcopy(seed),d['restart_steps'],folder/'restart_full.json.xz')
                first,tx=execute(c,binding,copy.deepcopy(seed),d['restart_split'][0],folder/'restart_first.json.xz')
                last,tx=execute(c,binding,first['result']['checkpoint'],d['restart_split'][1],folder/'restart_last.json.xz')
                api.require(full['rows']==first['rows']+last['rows'] and full['result']['checkpoint']['state']==last['result']['checkpoint']['state'],'combined exact restart including gap diagnostics')
                ledger.append({'case':c['id'],'entries':entries,'final':rec['result'],'restart_exact':True})
                del rec,full,first,last,seed,src
        verify(d)
        r={'passed':True,'new_steps':total,'work_window_cumulative_steps':total+d['prior_work_window_steps'],'wall_s':time.perf_counter()-started,
           'ledger':ledger,'artifacts':artifacts,'design_sha256':api.sha(DESIGN),'full_path_qualified':False,'campaign_launched':False,'claim':d['claim']}
        api.write(OUT/'results.json',r,raw=True);api.write(OUT/'completion.json',{'passed':True,'results_sha256':api.sha(OUT/'results.json')});print('EXTENDED_PASS',total,r['wall_s'],flush=True)
    except Exception as e:
        api.write(OUT/'failure.json',{'error':repr(e),'traceback':traceback.format_exc(),'sealed_steps':total,'wall_s':time.perf_counter()-started});raise


if __name__=='__main__':
    if sys.argv[1:]==['prepare']:prepare()
    elif sys.argv[1:]==['run']:run()
    else:raise ValueError('prepare | run')
