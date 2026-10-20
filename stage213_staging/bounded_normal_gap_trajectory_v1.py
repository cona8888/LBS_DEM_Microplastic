"""Copied accepted diagnostic seed, immutable inclusive ledger; no production."""
from pathlib import Path
from types import FunctionType,SimpleNamespace
import copy,os,sys,shutil,time,traceback
import psutil
import normal_gap_scope_v1 as policy_scope
import audit_normal_gap_v1 as auditor
job,api=policy_scope.job,policy_scope.api
frozen=policy_scope.proof.source.frozen
ROOT=policy_scope.ROOT
BASE='normal_gap_trajectory_20261001'
RUNBASE=ROOT/'stage213_runs'/BASE
DESIGNBASE=ROOT/'stage213_designs'/BASE
EVALBASE=ROOT/'stage213_evaluations'/BASE
WORK=DESIGNBASE/'trajectory_contract_01.json'
RECON=ROOT/'stage210_evaluations/three_contact_failure_20261001/reconstructed_window_01'
LOCAL=EVALBASE/'scope_qualification_01'
SELF=Path(__file__).resolve()

def sealed(path):
    result=api.read(path);api.require(api.read(path.parent/'completion.json')['results_sha256']==api.sha(path),'sealed '+str(path));return result

def prerequisites():
    w=api.read(WORK);d=api.read(job.DESIGN);job.verify(d)
    api.require(api.sha(job.DESIGN)==w['original_design_sha256'] and not w['production_authorized']
        and w['diagnostic_workers']==w['threads']==1,'exact local one-worker contract')
    api.verify_mapping(w['sources']);api.verify_mapping(w['inputs'])
    api.require(sealed(LOCAL/'results.json')['passed'] and sealed(RECON/'results.json')['passed'],'scope and accepted seed reconstruction')
    reconstruction=sealed(RECON/'results.json');api.verify_mapping(reconstruction['inputs']);api.verify_mapping(reconstruction['artifacts'])
    api.require(api.read(job.RUN/'completion.json')['all_owned_processes_retired'],'old producers retired')
    api.require(all(os.environ.get(k)=='1' for k in ('OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS')),'threads1')
    api.require(shutil.disk_usage(ROOT).free>=w['minimum_free_disk_bytes'],'20GiB reserve')
    return w,d

def no_worker():
    api.require(not frozen.active_owned(False),'one diagnostic worker and no competing simulation/evaluation')

def ledger():
    used=0;pending=[]
    for p in RUNBASE.glob('*/launch.json'):
        account=p.parent/'accounting.json'
        if not account.exists():pending.append(str(p));continue
        row=api.read(account);api.require(row['launch_sha256']==api.sha(p),'immutable launch accounting')
        if not row['saved_steps_known']:pending.append(str(p));continue
        used+=row['saved_steps']
    return used,pending

def prefix(folder,number=None):
    suffix='_%05d'%number if number is not None else ''
    codec=frozen.stack.storage.codec
    ref=api.read(folder/('prefix'+suffix+'.json'));hist=api.read(folder/('history'+suffix+'.json'))
    value=codec.HistoryState(**ref,history_bytes=codec.packed_history(hist));codec.validate_prefix(value,api.sha(job.DESIGN));return value

def geometry(case):
    job.parent.b.old.parent.configure()
    with job.prior.snapshot.scope(api,case['spec']['field_metadata']):_,data,meta=api.fields.load(2,1.,6)
    return job.prior.candidate.original.GrainGeometry(data['sand_centres_m'],data['sand_radii_m'],meta['cell_length_m'])

def prepare(name,seed=None):
    w,d=prerequisites();no_worker();api.require(job.utc()<job.policy.utc(w['no_new_trajectory_after_utc']),'launch clock')
    api.require(name in w['planned_calls'],'explicit bounded call');used,pending=ledger();cap=w['planned_calls'][name]
    api.require(not pending and 0<cap<=w['maximum_saved_steps_per_call'] and used+cap<=w['maximum_new_saved_trajectory_steps'],'inclusive saved-step budget')
    api.require(not (RUNBASE/name).exists(),'new exclusive diagnostic output')
    files=[WORK,job.DESIGN,LOCAL/'results.json',LOCAL/'completion.json',RECON/'results.json',RECON/'completion.json']
    files+=[RECON/f for f in ('checkpoint_00031.json','checkpoint_00032.json','prefix_00031.json','history_00031.json','prefix_00032.json','history_00032.json')]
    if seed:
        r=sealed(RUNBASE/seed/'results.json');api.require(r['numerical_audit_passed'] and r['rejected']==0,'independently passing diagnostic parent')
        files+=[RUNBASE/seed/f for f in ('results.json','completion.json','checkpoint.json','prefix.json','history.json','call.json.xz','call.json.seal.json')]
    plan=dict(name=name,seed=seed,cap=cap,prior_saved_steps=used,old_raw_design_sha256=api.sha(job.DESIGN),
              revised_numerical_policy_contract_sha256=api.sha(WORK),inputs={str(p):api.sha(p) for p in files},sources=w['sources'],
              claim='Copied diagnostic accepted checkpoint only; old Stage209 remains failed. No old-run restart/production/full-path acceptance.')
    job.commit(DESIGNBASE/(name+'.json'),plan);print('PREPARED_NORMAL_GAP_DIAGNOSTIC',name,cap,used,flush=True)

def execute(d,case,before,path,cap,prior,stop):
    codec=frozen.raw_execute.__globals__['codec'];original_write=codec.write_record
    with policy_scope.scope(cap+31) as log:
        def write_record(raw,record,parent):
            record['normal_gap_operand_policy']=copy.deepcopy(log)
            record['numerical_policy_contract_sha256']=api.sha(WORK)
            record['old_design_identity_is_seed_lineage_not_original_gap_policy_acceptance']=True
            return original_write(raw,record,parent)
        proxy=SimpleNamespace(**vars(codec));proxy.write_record=write_record
        raw_execute=FunctionType(frozen.raw_execute.__code__,{**frozen.raw_execute.__globals__,'codec':proxy},'execute_segment',frozen.raw_execute.__defaults__,frozen.raw_execute.__closure__)
        outer=FunctionType(frozen.execute.__code__,{**frozen.execute.__globals__,'raw_execute':raw_execute},'execute_segment',frozen.execute.__defaults__,frozen.execute.__closure__)
        api.require(raw_execute.__code__ is frozen.raw_execute.__code__ and outer.__code__ is frozen.execute.__code__,'unchanged integration and original solver scope bytecode')
        return outer(d,case,before,path,cap,prior,stop)

def run(name):
    w,d=prerequisites();no_worker();api.require(job.utc()<job.policy.utc(w['no_new_trajectory_after_utc']),'launch clock')
    planpath=DESIGNBASE/(name+'.json');plan=api.read(planpath);api.verify_mapping(plan['inputs']);api.verify_mapping(plan['sources'])
    used,pending=ledger();api.require(not pending and used==plan['prior_saved_steps'] and used+plan['cap']<=w['maximum_new_saved_trajectory_steps'],'resolved immutable reservation')
    case=next(c for c in d['cases'] if c['id']==w['case']);geom=geometry(case)
    if plan['seed']:
        folder=RUNBASE/plan['seed'];before=api.read(folder/'checkpoint.json');prior=prefix(folder)
    else:
        before=api.read(RECON/'checkpoint_00032.json');prior=prefix(RECON,32)
        rec,parent=frozen.stack.storage.codec.read_record(job.paths(job.RUN,w['case'],32)['raw'],api.sha(job.DESIGN),prefix(RECON,31))
        seedcheck=job.kernel.evaluate(rec,case['spec'],job.binding(d,case),api.read(RECON/'checkpoint_00031.json'),geom,api.sha(job.DESIGN),d['minimum_gap_semantics'])
        api.require(seedcheck['passed'] and api.digest(rec['result']['checkpoint'])==api.digest(before),'independently passing original seed, never failed terminal checkpoint')
    out=RUNBASE/name;out.mkdir(parents=True,exist_ok=False);process=psutil.Process()
    stop=min(job.policy.utc(w['work_end_utc']).timestamp(),time.time()+w['maximum_call_wall_seconds'])
    stop_iso=job.policy.utc(w['work_end_utc']).fromtimestamp(stop,job.utc().tzinfo).isoformat()
    job.commit(out/'launch.json',dict(pid=process.pid,created=process.create_time(),argv=process.cmdline(),utc=job.utc().isoformat(),
               protocol_sha256=api.sha(planpath),reserved_max_steps=plan['cap'],prior_saved_steps=used,seed_checkpoint_sha256=api.digest(before),stop_utc=stop_iso))
    raw=out/'call.json.xz';record=None
    try:
        record,nextprefix,seal,elapsed=execute(d,case,before,raw,plan['cap'],prior,stop_iso)
        steps=int(record['result']['steps'])-int(before['state']['steps'])
        api.require(0<=steps<=plan['cap'],'exact inclusive saved-step delta')
        job.commit(out/'accounting.json',dict(launch_sha256=api.sha(out/'launch.json'),saved_steps_known=True,saved_steps=steps,
                   total_saved_steps=used+steps,raw_sha256=api.sha(raw),status=record['result']['status'],rejected=record['result']['rejected']))
        job.commit(out/'checkpoint.json',record['result']['checkpoint']);job.commit(out/'prefix.json',nextprefix.reference());job.commit(out/'history.json',record['result']['history'])
        decoded,state=frozen.stack.storage.codec.read_record(raw,api.sha(job.DESIGN),prior)
        api.require(api.digest(decoded)==api.digest(record) and state.reference()==nextprefix.reference(),'independent compressed/history decoding')
        api.require(record['numerical_policy_contract_sha256']==api.sha(WORK),'explicit revised policy raw seal')
        check=None;error=None
        try:check=auditor.kernel(decoded,case['spec'],job.binding(d,case),before,geom,api.sha(job.DESIGN),d['minimum_gap_semantics'])
        except Exception as exc:error=dict(error=repr(exc),traceback=traceback.format_exc())
        api.verify_mapping(plan['inputs']);api.verify_mapping(plan['sources']);job.verify(d)
        api.require(shutil.disk_usage(ROOT).free>=w['minimum_free_disk_bytes'],'post-call reserve')
        r=dict(numerical_audit_passed=bool(check and check['passed']),audit=check,audit_error=error,steps=steps,
               independently_accepted_steps=(steps if check and check['passed'] else 0),total_saved_steps=used+steps,
               rejected=record['result']['rejected'],status=record['result']['status'],time_s=record['result']['time_s'],
               compute_seconds=record['compute_call_wall_s'],transaction_seconds=elapsed,protocol_sha256=api.sha(planpath),
               raw_design_sha256=api.sha(job.DESIGN),numerical_policy_contract_sha256=api.sha(WORK),
               artifacts={str(p):api.sha(p) for p in out.glob('*') if p.is_file()},
               claim='Explicit revised normal-gap diagnostic, not an original raw-gap numerical pass. Stage209 remains failed. No production, population release, empirical validation or six-case full-path claim.')
        job.commit(out/'results.json',r);job.commit(out/'completion.json',dict(passed=r['numerical_audit_passed'],results_sha256=api.sha(out/'results.json')))
        print('NORMAL_GAP_DIAGNOSTIC_COMPLETE',name,r['numerical_audit_passed'],steps,r['rejected'],r['time_s'],r['audit_error'],flush=True)
    except Exception as exc:
        if not (out/'accounting.json').exists():job.commit(out/'accounting.json',dict(launch_sha256=api.sha(out/'launch.json'),saved_steps_known=False,saved_steps=None,reserved_max_steps=plan['cap'],raw_exists=raw.exists()))
        job.commit(out/'failure.json',dict(error=repr(exc),traceback=traceback.format_exc(),raw_exists=raw.exists(),claim='Unresolved saved-step reservation blocks further trajectory launches.'));raise

if __name__=='__main__':
    if len(sys.argv)>=3 and sys.argv[1]=='prepare':prepare(sys.argv[2],sys.argv[3] if len(sys.argv)>3 else None)
    elif len(sys.argv)==3 and sys.argv[1]=='run':run(sys.argv[2])
    else:raise ValueError('prepare NAME [SEED] | run NAME')
