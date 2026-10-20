"""Bounded producer/independent-auditor qualification, not a campaign launcher.

One simulation worker, 36,000 steps total, at most two unaudited segments.
Ready/receipt markers commit atomically, never replace an existing artifact.
Any failure stops new dispatch cooperatively; completed evidence is retained.
"""
from pathlib import Path
import copy,datetime,json,os,shutil,subprocess,sys,time,traceback
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'stage181_staging'),str(ROOT/'stage180_staging'),str(ROOT/'stage179_staging')]
import qualify_runtime_deadline_v1 as previous
import audit_optimized_record_v1 as kernel
import lossless_history_prefix_v1 as codec
api,parent=previous.api,previous.parent
prior,fast=previous.prior,previous.fast
DESIGN=ROOT/'stage182_designs/bounded_live_audit_20260924/design_01.json'
RUN=ROOT/'stage182_runs/bounded_live_audit_20260924/run_01'
OUT=ROOT/'stage182_evaluations/bounded_live_audit_20260924/evaluation_01'


def commit(path,data):
    path=Path(path);temporary=path.with_name(path.name+f'.pending.{os.getpid()}')
    path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists() or temporary.exists():raise FileExistsError(str(path))
    with temporary.open('x',encoding='utf-8') as f:
        json.dump(data,f,sort_keys=True,indent=2,allow_nan=True,default=api.frozen.h.json_value);f.write('\n');f.flush();os.fsync(f.fileno())
    # Windows rename fails if destination exists. No overwrite is permitted.
    if os.name!='nt':raise RuntimeError('qualified exclusive Windows rename required')
    os.rename(temporary,path)


def signal_failure(role,error):
    detail={'role':role,'error':repr(error),'traceback':traceback.format_exc(),'utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}
    commit(RUN/(role+'_failure.json'),detail)
    try:commit(RUN/'failure.json',detail)
    except FileExistsError:pass


def prepare():
    previous.verify(api.read(previous.DESIGN));r=api.read(previous.OUT/'results.json')
    api.require(r['passed'] and r['new_steps']==6000,'deadline adapter prerequisite')
    api.require(api.read(previous.OUT/'completion.json')['results_sha256']==api.sha(previous.OUT/'results.json'),'prerequisite completion seal')
    resource=ROOT/'stage179_evaluations/history_prefix_20260924/resource_independent_audit_01/results.json'
    api.require(api.read(resource)['passed'],'independent prefix resource prerequisite')
    raw_audit=ROOT/'stage180_evaluations/incremental_audit_20260924/raw_audit_01/results.json'
    api.require(api.read(raw_audit)['passed'],'incremental kernel prerequisite')
    protocol=OUT.parent/'protocol_units_01/results.json';pr=api.read(protocol)
    api.require(pr['passed'] and api.read(protocol.parent/'completion.json')['results_sha256']==api.sha(protocol),'protocol prerequisite')
    api.verify_mapping(pr['sources']);api.verify_mapping(pr['artifacts'])
    cases=[];inputs=[previous.DESIGN,previous.OUT/'results.json',previous.OUT/'completion.json',resource,resource.parent/'completion.json',raw_audit,raw_audit.parent/'completion.json',protocol,protocol.parent/'completion.json']
    for c in api.read(previous.DESIGN)['cases']:
        path=previous.RUN/(c['id']+'.json.xz');cases.append({'id':c['id'],'spec':c['spec'],'source':str(path)})
        inputs.extend([path,path.with_suffix('.seal.json')])
    d={'stage':'Stage182 bounded live audit','cases':cases,'source_raw_design_sha256':api.sha(previous.DESIGN),
       'blocks_per_case':2,'steps_per_block':3000,'maximum_new_steps':36000,'prior_work_steps':207175,'work_step_ceiling':250000,
       'simulation_workers':1,'audit_workers':1,'blas_threads':1,'maximum_unverified_segments':2,'wall_seconds':900,'poll_seconds':0.1,
       'stop_utc':'2026-09-24T02:46:55+00:00','minimum_free_bytes':20*1024**3,'physical_changes':[],
       'sources':parent.source_map(),'inputs':{str(p):api.sha(p) for p in inputs},'minimum_gap_semantics':api.read(previous.DESIGN)['minimum_gap_semantics'],
       'claim':'Short conditional producer/auditor orchestration verification only. No campaign launch, full observation or release inference.'}
    api.require(d['prior_work_steps']+d['maximum_new_steps']<=d['work_step_ceiling'],'cumulative work allowance')
    d['binding']=api.digest(d);DESIGN.parent.mkdir(exist_ok=True,parents=True);api.write(DESIGN,d);print('FROZEN',api.sha(DESIGN),flush=True)


def verify(d):
    api.require(d['binding']==api.digest({k:v for k,v in d.items() if k!='binding'}),'self binding');api.verify_mapping(d['sources']);api.verify_mapping(d['inputs']);previous.verify(api.read(previous.DESIGN))


def location(case,i):
    folder=RUN/case
    return {'raw':folder/f'segment_{i:03d}.json.xz','ready':folder/f'segment_{i:03d}.ready.json',
            'trace':folder/f'segment_{i:03d}.npy','receipt':folder/f'segment_{i:03d}.audit.json'}


def schedule(d):return [(c,i,location(c['id'],i)) for c in d['cases'] for i in range(1,d['blocks_per_case']+1)]


def stopped(d):
    return (RUN/'failure.json').exists() or (RUN/'stop_requested.json').exists() or time.time()>=previous.candidate.parse_deadline(d['stop_utc'])-60


def acknowledged(path):
    if not path.exists():return False
    receipt=api.read(path);ready=path.with_name(path.name.replace('.audit.json','.ready.json'))
    marker=api.read(ready)
    api.require(receipt['status']=='independently_verified' and receipt['summary']['passed'] is True,'back-pressure acknowledgement is a passed audit')
    api.require(receipt['design_sha256']==api.sha(DESIGN) and receipt['audit_source_sha256']==api.sha(kernel.__file__),'acknowledgement audit binding')
    api.require(receipt['ready_sha256']==api.sha(ready) and receipt['raw_sha256']==marker['raw_sha256']==api.sha(marker['raw_path']),'acknowledgement sealed raw binding')
    api.require(receipt['trace_sha256']==api.sha(receipt['trace_path']),'acknowledgement trace binding')
    return True


def seed(c,d):
    rec,_=codec.read_record(c['source'],d['source_raw_design_sha256']);binding=api.digest([d['binding'],c['id']])
    return binding,parent.model.checkpoint(c['spec'],binding,rec['result']['checkpoint'],True)


def verify_ready(marker,paths,c,i,d,before):
    api.require(marker['case']==c['id'] and marker['segment']==i and marker['design_sha256']==api.sha(DESIGN),'frozen ready identity')
    api.require(marker['raw_path']==str(paths['raw']) and marker['raw_sha256']==api.sha(paths['raw']),'explicit raw path and seal')
    api.require(marker['seal_sha256']==api.sha(paths['raw'].with_suffix('.seal.json')) and marker['input_checkpoint_sha256']==api.digest(before),'sealed input checkpoint')


def producer():
    d=api.read(DESIGN);verify(d);parent.b.old.parent.configure();fast.capture_systems=True;total=0;pending=[];maximum_pending=0;items=[]
    try:
        with prior.snapshot.scope(api,d['cases'][0]['spec']['field_metadata']):
            api.fields.load(2,1.,6)
            for c in d['cases']:
                binding,cp=seed(c,d);prefix=None
                for i in range(1,d['blocks_per_case']+1):
                    pending=[p for p in pending if not acknowledged(p)]
                    while len(pending)>=d['maximum_unverified_segments'] and not stopped(d):
                        time.sleep(d['poll_seconds']);pending=[p for p in pending if not acknowledged(p)]
                    if stopped(d):raise RuntimeError('cooperative stop before next simulation segment')
                    api.require(total+d['steps_per_block']<=d['maximum_new_steps'],'new step cap')
                    api.require(shutil.disk_usage(ROOT).free>d['minimum_free_bytes']+codec.base.MAX_COMPRESSED,'live disk reserve')
                    paths=location(c['id'],i);paths['raw'].parent.mkdir(exist_ok=True);before=copy.deepcopy(cp);t=time.perf_counter()
                    with prior.p.hot.scope(),parent.storage.step_budget_scope(20_000_000),parent.fix.scope(),previous.candidate.scope(parent.engine.runtime,d['stop_utc'],True),prior.candidate.scope():
                        result,rows=parent.engine.runtime.execute(c['spec'],binding,checkpoint=cp,pause=cp['state']['steps']+d['steps_per_block'])
                    record={'spec':c['spec'],'result':result,'rows':rows,'input_checkpoint_sha256':api.digest(before),'effective_binding':parent.model.binding_for(binding,True),
                        'design_sha256':api.sha(DESIGN),'step_cap':d['steps_per_block'],'compute_call_wall_s':time.perf_counter()-t,
                        'early_attempts':copy.deepcopy(fast.attempts),'repairs':copy.deepcopy(fast.old.telemetry),'backend_calls':copy.deepcopy(parent.model.calls),
                        'certificates':copy.deepcopy(parent.fix.telemetry),'sweep_certificates':copy.deepcopy(prior.candidate.records),'minimum_gap_semantics':d['minimum_gap_semantics']}
                    codec.write_record(paths['raw'],record,prefix);total+=len(rows)
                    api.require(len(rows)==d['steps_per_block'] and result['status']=='paused_checkpoint','exact conditional segment cap')
                    api.require(result['rejected']==before['state']['rejected']==0 and parent.engine.prior.reference.independent_health(result,c['spec'])['passed'],'producer health gate')
                    decoded,prefix=codec.read_record(paths['raw'],api.sha(DESIGN),prefix)
                    api.require(codec.base.raw_bytes(decoded)==codec.base.raw_bytes(record),'exact raw roundtrip')
                    marker={'case':c['id'],'segment':i,'raw_path':str(paths['raw']),'raw_sha256':api.sha(paths['raw']),
                        'seal_sha256':api.sha(paths['raw'].with_suffix('.seal.json')),'input_checkpoint_sha256':api.digest(before),
                        'steps':len(rows),'transaction_seconds':time.perf_counter()-t,'design_sha256':api.sha(DESIGN)}
                    commit(paths['ready'],marker);pending.append(paths['receipt']);maximum_pending=max(maximum_pending,len(pending));items.append(marker)
                    cp=result['checkpoint'];fast.attempts.clear();fast.telemetry.clear();fast.old.telemetry.clear();parent.fix.telemetry.clear();parent.model.calls.clear();prior.candidate.records.clear()
                    print('SEALED',c['id'],i,total,'unverified',len(pending),flush=True)
        verify(d);commit(RUN/'producer_complete.json',{'passed':True,'steps':total,'maximum_unverified_segments':maximum_pending,'items':items,'design_sha256':api.sha(DESIGN)})
    except Exception as e:signal_failure('producer',e);raise


def auditor():
    d=api.read(DESIGN);verify(d);parent.b.old.parent.configure();field,data,meta=api.fields.load(2,1.,6)
    geometry=prior.candidate.original.GrainGeometry(data['sand_centres_m'],data['sand_radii_m'],meta['cell_length_m']);items=[]
    try:
        for c in d['cases']:
            binding,cp=seed(c,d);prefix=None;receipt_sha=None
            for i in range(1,d['blocks_per_case']+1):
                paths=location(c['id'],i)
                while not paths['ready'].exists():
                    if stopped(d) or (RUN/'producer_complete.json').exists():raise RuntimeError('ready evidence missing at producer stop')
                    time.sleep(d['poll_seconds'])
                marker=api.read(paths['ready']);verify_ready(marker,paths,c,i,d,cp);before=cp
                record,prefix=codec.read_record(paths['raw'],api.sha(DESIGN),prefix)
                summary=kernel.evaluate(record,c['spec'],binding,before,geometry,api.sha(DESIGN),d['minimum_gap_semantics'])
                trace=np.array([[r['time_s'],*r['position_m'],*r['orientation'],*r['velocity_generalized']] for r in record['rows']],dtype=np.float64)
                with paths['trace'].open('xb') as f:np.save(f,trace,allow_pickle=False);f.flush();os.fsync(f.fileno())
                receipt={'case':c['id'],'segment':i,'ready_sha256':api.sha(paths['ready']),'raw_sha256':api.sha(paths['raw']),
                    'original_raw_sha256':prefix.original_sha256,'trace_path':str(paths['trace']),'trace_sha256':api.sha(paths['trace']),
                    'previous_receipt_sha256':receipt_sha,'input_checkpoint_sha256':api.digest(before),'summary':summary,
                    'design_sha256':api.sha(DESIGN),'audit_source_sha256':api.sha(kernel.__file__),'status':'independently_verified'}
                commit(paths['receipt'],receipt);receipt_sha=api.sha(paths['receipt']);items.append({'path':str(paths['receipt']),'sha256':receipt_sha,'case':c['id'],'segment':i})
                cp=record['result']['checkpoint'];print('VERIFIED',c['id'],i,summary['steps'],flush=True)
        verify(d);commit(RUN/'auditor_complete.json',{'passed':True,'items':items,'design_sha256':api.sha(DESIGN)})
    except Exception as e:signal_failure('auditor',e);raise


def evaluate(d,exits):
    api.require(all(code==0 for code in exits.values()) and not (RUN/'failure.json').exists() and not (RUN/'stop_requested.json').exists(),'normal worker completion, no failure/stop')
    prod=api.read(RUN/'producer_complete.json');aud=api.read(RUN/'auditor_complete.json');api.require(prod['passed'] and aud['passed'],'both completion markers')
    seen=[];total=0;previous_hash={};ends=[]
    for c,i,paths in schedule(d):
        receipt=api.read(paths['receipt']);marker=api.read(paths['ready']);trace=np.load(paths['trace'],mmap_mode='r',allow_pickle=False)
        api.require(receipt['ready_sha256']==api.sha(paths['ready']) and receipt['raw_sha256']==api.sha(paths['raw']) and receipt['trace_sha256']==api.sha(paths['trace']),'receipt evidence seals')
        api.require(receipt['previous_receipt_sha256']==previous_hash.get(c['id']) and receipt['summary']['passed'] and receipt['status']=='independently_verified','case receipt chain')
        api.require(receipt['case']==c['id'] and receipt['segment']==i and receipt['design_sha256']==api.sha(DESIGN),'ordered audit receipt')
        api.require(trace.shape==(d['steps_per_block'],13) and np.isfinite(trace).all() and np.all(np.diff(trace[:,0])>0),'sealed trace shape/clock')
        api.require(trace[-1,0]==receipt['summary']['stop_s'] and marker['steps']==receipt['summary']['steps'],'trace/receipt step and endpoint identity')
        previous_hash[c['id']]=api.sha(paths['receipt']);total+=len(trace);seen.append(str(paths['raw']))
        if i==d['blocks_per_case']:ends.append({'case':c['id'],'time_s':receipt['summary']['stop_s'],'full_observation':False})
    api.require(total==prod['steps']==d['maximum_new_steps'] and len(aud['items'])==len(seen),'complete segment accounting')
    api.require(set(seen)=={str(p) for p in RUN.rglob('*.json.xz')} and prod['maximum_unverified_segments']<=d['maximum_unverified_segments'],'no unaccounted records; bounded audit lag')
    for item in aud['items']:api.require(item['sha256']==api.sha(item['path']),'auditor manifest seal')
    verify(d);artifacts={str(p):api.sha(p) for p in RUN.rglob('*') if p.is_file()}
    report={'passed':True,'new_steps':total,'work_cumulative_steps':total+d['prior_work_steps'],'records':len(seen),'endpoints':ends,
        'max_unverified_segments':prod['maximum_unverified_segments'],'worker_exit_codes':exits,'artifacts':artifacts,'design_sha256':api.sha(DESIGN),
        'campaign_launched':False,'full_path_qualified':False,'claim':d['claim']}
    commit(OUT/'results.json',report);commit(OUT/'completion.json',{'passed':True,'results_sha256':api.sha(OUT/'results.json')});print('LIVE_AUDIT_PASS',total,flush=True)


def supervise():
    d=api.read(DESIGN);verify(d);api.require(time.time()<previous.candidate.parse_deadline(d['stop_utc'])-d['wall_seconds']-120,'work-window reserve')
    RUN.mkdir(exist_ok=False,parents=True);OUT.mkdir(exist_ok=False,parents=True);children={};streams=[];start=time.perf_counter()
    env=dict(os.environ,OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',OMP_NUM_THREADS='1');launch=[]
    try:
        for role in ['auditor','producer']:
            log=(RUN/(role+'.stdout.log')).open('xb');err=(RUN/(role+'.stderr.log')).open('xb');streams.extend([log,err])
            args=[sys.executable,'-B','-u',str(Path(__file__).resolve()),role]
            proc=subprocess.Popen(args,cwd=str(ROOT),env=env,stdout=log,stderr=err,creationflags=subprocess.CREATE_NO_WINDOW)
            children[role]=proc;launch.append({'role':role,'pid':proc.pid,'argv':args})
        commit(RUN/'launch.json',{'supervisor_pid':os.getpid(),'workers':launch,'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'design_sha256':api.sha(DESIGN)})
        print('SUPERVISOR',os.getpid(),launch,flush=True)
        while any(p.poll() is None for p in children.values()):
            for role,process in children.items():
                if process.poll() not in (None,0) and not (RUN/'failure.json').exists():
                    commit(RUN/'failure.json',{'role':role,'exit_code':process.returncode,'reason':'worker abnormal exit'})
            if (time.perf_counter()-start>=d['wall_seconds'] or time.time()>=previous.candidate.parse_deadline(d['stop_utc'])-60) and not (RUN/'stop_requested.json').exists():
                commit(RUN/'stop_requested.json',{'reason':'cooperative bounded resource stop','utc':datetime.datetime.now(datetime.timezone.utc).isoformat()})
            time.sleep(d['poll_seconds'])
        for stream in streams:stream.close()
        evaluate(d,{role:p.returncode for role,p in children.items()})
    except Exception as e:
        if not (RUN/'stop_requested.json').exists():commit(RUN/'stop_requested.json',{'reason':'supervisor error','error':repr(e)})
        # Cooperative retirement, never kill/restart. Both workers inspect this
        # marker between their bounded segments/records.
        while any(p.poll() is None for p in children.values()):time.sleep(d['poll_seconds'])
        for stream in streams:
            if not stream.closed:stream.close()
        commit(OUT/'failure.json',{'error':repr(e),'traceback':traceback.format_exc(),'worker_pids':{role:p.pid for role,p in children.items()}})
        raise
    finally:
        for stream in streams:
            if not stream.closed:stream.close()


if __name__=='__main__':
    actions={'prepare':prepare,'run':supervise,'producer':producer,'auditor':auditor}
    if len(sys.argv)!=2 or sys.argv[1] not in actions:raise ValueError('prepare | run | producer | auditor')
    actions[sys.argv[1]]()
