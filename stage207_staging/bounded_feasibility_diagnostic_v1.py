"""Separately ledgered local trajectory qualification, never a production restart."""
from pathlib import Path
from types import FunctionType
import copy,os,sys,traceback,psutil,shutil
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'stage206_staging'))
import authenticate_failed_system_v1 as source
import two_contact_cone_feasibility_v1 as repair
import audit_cone_feasibility_v1 as auditor
job,api,frozen=source.job,source.api,source.frozen
BASE='feasibility_trajectory_20260930'
RUNBASE=ROOT/'stage207_runs'/BASE
DESIGNBASE=ROOT/'stage207_designs'/BASE
EVALBASE=ROOT/'stage207_evaluations'/BASE
WORK=DESIGNBASE/'contract_01.json'
RECON=ROOT/'stage206_evaluations/contact_failure_20260930/reconstructed_window_01'
LOCAL=ROOT/'stage206_evaluations/contact_failure_20260930/independent_local_01'
execute=FunctionType(job.execute_segment.__code__,{**job.execute_segment.__globals__,'repair':repair},'execute_segment',job.execute_segment.__defaults__,job.execute_segment.__closure__)

def sealed(path):
    r=api.read(path);api.require(api.read(path.parent/'completion.json')['results_sha256']==api.sha(path),'sealed '+str(path));return r

def ledger():
    used=0;pending=[]
    for p in RUNBASE.glob('*/launch.json'):
        account=p.parent/'accounting.json'
        if not account.exists():pending.append(str(p));continue
        a=api.read(account);api.require(a['launch_sha256']==api.sha(p),'ledger launch binding')
        if not a['saved_steps_known']:pending.append(str(p));continue
        used+=a['saved_steps']
    return used,pending

def no_worker():
    for p in psutil.process_iter(['name','cmdline']):
        if p.pid==os.getpid() or 'python' not in (p.info['name'] or '').lower():continue
        argv=p.info['cmdline'] or []
        api.require(not (str(Path(__file__).resolve()) in argv and 'run' in argv),'one diagnostic worker only')

def prefix(ref,hist):
    codec=frozen.pre.storage.codec
    p=codec.HistoryState(**api.read(ref),history_bytes=codec.packed_history(api.read(hist)))
    codec.validate_prefix(p,api.sha(job.DESIGN));return p

def geometry(case):
    job.parent.b.old.parent.configure()
    with job.prior.snapshot.scope(api,case['spec']['field_metadata']):_,data,meta=api.fields.load(2,1.,6)
    return job.prior.candidate.original.GrainGeometry(data['sand_centres_m'],data['sand_radii_m'],meta['cell_length_m'])

def prerequisites():
    w=api.read(WORK);d=api.read(job.DESIGN);job.verify(d)
    api.require(api.sha(job.DESIGN)==w['source_design_sha256'] and not w['production_authorized'],'inherited checkpoint physics, no production')
    api.require(sealed(LOCAL/'results.json')['passed'] and sealed(RECON/'results.json')['passed'],'independent local and reconstruction gates')
    api.verify_mapping(api.read(LOCAL/'results.json')['inputs']);r=api.read(RECON/'results.json');api.verify_mapping(r['inputs']);api.verify_mapping(r['artifacts'])
    api.require(api.read(job.RUN/'completion.json')['all_owned_processes_retired'],'old production retired')
    return w,d

def prepare(name,seed=None):
    w,d=prerequisites();api.require(name in w['planned_calls'],'frozen explicit call')
    api.require(job.utc()<job.policy.utc(w['no_new_trajectory_after_utc']),'bounded launch clock');no_worker()
    used,pending=ledger();cap=w['planned_calls'][name]
    api.require(not pending and 0<cap<=w['maximum_saved_steps_per_call'] and used+cap<=w['maximum_new_saved_trajectory_steps'],'resolved saved-step ledger')
    files=[WORK,job.DESIGN,LOCAL/'results.json',LOCAL/'completion.json',RECON/'results.json',RECON/'completion.json']
    files+=[RECON/f for f in ('checkpoint_00226.json','checkpoint_00227.json','prefix_00227.json','history_00227.json')]
    if seed:
        sr=sealed(RUNBASE/seed/'results.json');api.require(sr['numerical_audit_passed'],'independently passing diagnostic parent')
        files += [RUNBASE/seed/f for f in ('results.json','completion.json','checkpoint.json','prefix.json','history.json','call.json.xz','call.json.seal.json')]
    plan=dict(stage='Stage207 exclusive bounded diagnostic',name=name,seed=seed,maximum_new_steps=cap,prior_saved_steps=used,
              inputs={str(p):api.sha(p) for p in files},new_sources={str(p):api.sha(p) for p in [Path(__file__),Path(repair.__file__),Path(auditor.__file__)]},
              original_design_sha256=api.sha(job.DESIGN),worker_limit=1,no_production_authorization=True,candidate=repair.NAME,audit_identity=auditor.STRUCTURAL_IDENTITY)
    job.commit(DESIGNBASE/(name+'.json'),plan);print('PREPARED_DIAGNOSTIC',name,cap,used,flush=True)

def run(name):
    protocol=DESIGNBASE/(name+'.json');p=api.read(protocol);w,d=prerequisites()
    api.require(job.utc()<job.policy.utc(w['no_new_trajectory_after_utc']),'bounded launch clock');no_worker()
    api.verify_mapping(p['inputs']);api.verify_mapping(p['new_sources'])
    api.require(shutil.disk_usage(ROOT).free>=w['minimum_free_disk_bytes'],'C-side disk reserve')
    used,pending=ledger();api.require(not pending and used==p['prior_saved_steps'] and used+p['maximum_new_steps']<=w['maximum_new_saved_trajectory_steps'],'resolved frozen reservation')
    case=next(c for c in d['cases'] if c['id']==w['case']);geom=geometry(case)
    if p['seed']:
        seed=RUNBASE/p['seed'];before=api.read(seed/'checkpoint.json');prior=prefix(seed/'prefix.json',seed/'history.json')
    else:
        before=api.read(RECON/'checkpoint_00227.json');prior=prefix(RECON/'prefix_00227.json',RECON/'history_00227.json')
        raw=job.paths(job.RUN,w['case'],227)['raw'];env=frozen.pre.storage.read_envelope(raw,api.sha(job.DESIGN))
        rec=copy.deepcopy(env['payload']);hist=api.read(RECON/'history_00227.json');rec['result']['history']=hist;rec['result']['checkpoint']['state']['history']=hist
        api.require(api.digest(rec['result']['checkpoint'])==api.digest(before),'exact diagnostic seed')
        seedcheck=job.kernel.evaluate(rec,case['spec'],job.binding(d,case),api.read(RECON/'checkpoint_00226.json'),geom,api.sha(job.DESIGN),d['minimum_gap_semantics'])
        api.require(seedcheck['passed'],'original seed numerical audit')
    out=RUNBASE/name;out.mkdir(parents=True,exist_ok=False)
    job.commit(out/'launch.json',dict(pid=os.getpid(),utc=job.utc().isoformat(),argv=sys.argv,protocol_sha256=api.sha(protocol),reserved_max_steps=p['maximum_new_steps'],prior_saved_steps=used,seed_checkpoint_sha256=api.digest(before)))
    raw=out/'call.json.xz';rec=None
    try:
        repair.telemetry.clear();rec,nextprefix,seal,elapsed=execute(d,case,before,raw,p['maximum_new_steps'],prior,w['work_end_utc'])
        steps=int(rec['result']['steps'])-int(before['state']['steps'])
        api.require(0<=steps<=p['maximum_new_steps'],'exact saved-step delta')
        job.commit(out/'accounting.json',dict(launch_sha256=api.sha(out/'launch.json'),saved_steps_known=True,saved_steps=steps,total_saved_steps=used+steps,raw_sha256=api.sha(raw),status=rec['result']['status'],rejected=rec['result']['rejected']))
        job.commit(out/'checkpoint.json',rec['result']['checkpoint']);job.commit(out/'prefix.json',nextprefix.reference());job.commit(out/'history.json',rec['result']['history'])
        decoded,state=frozen.pre.storage.codec.read_record(raw,api.sha(job.DESIGN),prior)
        api.require(api.digest(decoded)==api.digest(rec) and state.reference()==nextprefix.reference(),'independent raw/history decoding')
        check=None;error=None
        try:check=auditor.kernel(decoded,case['spec'],job.binding(d,case),before,geom,api.sha(job.DESIGN),d['minimum_gap_semantics'])
        except Exception as exc:error=dict(error=repr(exc),traceback=traceback.format_exc())
        comparison=None
        if p['seed'] is None:
            failed,_=frozen.pre.storage.codec.read_record(job.paths(job.RUN,w['case'],228)['raw'],api.sha(job.DESIGN),prior)
            first=failed['result']['rejected_trials'][0]['time_s'];oldrows=[x for x in failed['rows'] if x['time_s']<=first];count=min(len(oldrows),len(rec['rows']))
            comparison=dict(rows=count,available_original_prefix_rows=len(oldrows),exact_before_rejection=rec['rows'][:count]==oldrows[:count],first_old_rejected_time_s=first)
        api.verify_mapping(p['inputs']);api.verify_mapping(p['new_sources']);job.verify(d)
        result=dict(numerical_audit_passed=bool(check and check['passed']),audit=check,audit_error=error,steps=steps,total_saved_steps=used+steps,
                    rejected=rec['result']['rejected'],status=rec['result']['status'],time_s=rec['result']['checkpoint']['state']['t'],original_prefix_comparison=comparison,
                    protocol_sha256=api.sha(protocol),compute_seconds=rec['compute_call_wall_s'],transaction_seconds=elapsed,
                    artifacts={str(f):api.sha(f) for f in out.glob('*') if f.is_file()},claim='Local qualification only; Stage205 remains failed, no old production restart or full-path/release claim.')
        job.commit(out/'results.json',result);job.commit(out/'completion.json',dict(passed=result['numerical_audit_passed'],results_sha256=api.sha(out/'results.json')))
        print('DIAGNOSTIC_COMPLETE',name,result['numerical_audit_passed'],steps,result['rejected'],result['time_s'],flush=True)
    except Exception as error:
        if not (out/'accounting.json').exists():job.commit(out/'accounting.json',dict(launch_sha256=api.sha(out/'launch.json'),saved_steps_known=False,saved_steps=None,maximum_reserved_steps=p['maximum_new_steps'],raw_exists=raw.exists()))
        job.commit(out/'failure.json',dict(error=repr(error),traceback=traceback.format_exc(),raw_exists=raw.exists(),claim='Unresolved step reservation blocks all further launches.'));raise

if __name__=='__main__':
    if len(sys.argv)>=3 and sys.argv[1]=='prepare':prepare(sys.argv[2],sys.argv[3] if len(sys.argv)>3 else None)
    elif len(sys.argv)==3 and sys.argv[1]=='run':run(sys.argv[2])
    else:raise ValueError('prepare NAME [SEED] | run NAME')
