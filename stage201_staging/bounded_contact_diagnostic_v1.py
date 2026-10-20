"""One explicitly reserved local continuation; never a production restart.

Original checkpoint/physics binding remains Stage200; a separate immutable
diagnostic protocol binds the new numerical-only route, raw bytes and budget.
"""
from pathlib import Path
import copy,os,sys,time,traceback,psutil
import two_contact_scalar_repair_v2 as repair
import audit_two_contact_routes_v2 as auditor
source=repair.algebra.source;job,api,ROOT,frozen=source.job,source.api,source.ROOT,source.frozen
BASE='contact_repair_20260928'
RUNBASE=ROOT/'stage201_runs'/BASE
EVALBASE=ROOT/'stage201_evaluations'/BASE
DESIGNBASE=ROOT/'stage201_designs/eight_hour_contact_repair_20260928'
RECON=EVALBASE/'reconstructed_window_02'
SELF=Path(__file__).resolve()


def sealed_result(path):
    r=api.read(path);api.require(api.read(path.parent/'completion.json')['results_sha256']==api.sha(path),'sealed result '+str(path));return r


def prefix196():
    r=sealed_result(RECON/'results.json');api.require(r['passed'],'reconstructed checkpoint')
    api.verify_mapping(r['inputs']);api.verify_mapping(r['artifacts'])
    ref=api.read(RECON/'prefix_00196.json');hist=api.read(RECON/'history_00196.json')
    return frozen.pre.storage.codec.HistoryState(**ref,history_bytes=frozen.pre.storage.codec.packed_history(hist))


def geometry(case):
    job.parent.b.old.parent.configure()
    with job.prior.snapshot.scope(api,case['spec']['field_metadata']):
        _,data,meta=api.fields.load(2,1.,6)
    return job.prior.candidate.original.GrainGeometry(data['sand_centres_m'],data['sand_radii_m'],meta['cell_length_m'])


def ledger():
    used=0;pending=[]
    if RUNBASE.exists():
        for launch in RUNBASE.glob('*/launch.json'):
            account=launch.parent/'accounting.json'
            if not account.exists():pending.append(str(launch));continue
            a=api.read(account);api.require(a['launch_sha256']==api.sha(launch),'step ledger launch binding')
            if not a['accepted_steps_known']:pending.append(str(launch));continue
            used+=a['accepted_steps']
    return used,pending


def require_no_diagnostic():
    for p in psutil.process_iter(['name','cmdline']):
        if p.pid==os.getpid() or 'python' not in (p.info['name'] or '').lower():continue
        cmd=' '.join(p.info['cmdline'] or [])
        api.require(not ('stage201_staging' in cmd and 'bounded_contact_diagnostic' in cmd and ' run ' in (' '+cmd+' ')),'single diagnostic worker')


def prepare(name,cap,seed_name=None):
    api.require(name.replace('_','').isalnum() and name.endswith('_01'),'explicit diagnostic label')
    w=api.read(source.WORK);api.require(job.utc()<job.policy.utc(w['no_new_trajectory_after_utc']),'launch window')
    api.require(0<cap<=w['maximum_accepted_steps_per_diagnostic_call'],'bounded call')
    d=api.read(job.DESIGN);job.verify(d);require_no_diagnostic();used,pending=ledger()
    api.require(not pending and used+cap<=w['maximum_new_accepted_trajectory_steps'],'bounded resolved ledger')
    for sub in ('held_qualification_01','outer_qualification_02'):
        r=sealed_result(EVALBASE/sub/'results.json');api.require(r['passed'],'qualification '+sub)
    inputs=[source.WORK,job.DESIGN,RECON/'results.json',RECON/'completion.json',RECON/'checkpoint_00195.json',RECON/'checkpoint_00196.json',RECON/'prefix_00196.json',RECON/'history_00196.json']
    inputs += [EVALBASE/sub/f for sub in ('held_qualification_01','outer_qualification_02') for f in ('results.json','completion.json')]
    if seed_name:
        seed=RUNBASE/seed_name;sr=sealed_result(seed/'results.json');api.require(sr['numerical_audit_passed'],'verified diagnostic parent')
        inputs += [seed/f for f in ('results.json','completion.json','checkpoint.json','prefix.json','history.json','call.json.xz','call.json.seal.json')]
    else:prefix196()
    p={'stage':'Stage201 bounded local numerical repair continuation','name':name,'maximum_new_steps':cap,'seed_diagnostic':seed_name,'prior_window_steps':used,
      'inputs':{str(x):api.sha(x) for x in inputs},'new_sources':{str(x):api.sha(x) for x in SELF.parent.glob('*.py')},'inherited_design_sha256':api.sha(job.DESIGN),
      'case':source.NAME,'physical_changes':[],'physics_checkpoint_binding_preserved':True,'raw_design_hash_remains_inherited_for_checkpoint_identity':True,'candidate':repair.NAME,'auditor_identity':auditor.STRUCTURAL_IDENTITY,
      'trajectory_cap':cap,'worker_limit':1,'minimum_free_disk_bytes':w['minimum_free_disk_bytes'],'no_production_authorization':True,'claim':'Local solution verification only, no repaired old campaign or release claim.'}
    job.commit(DESIGNBASE/(name+'.json'),p);print('PREPARED',name,cap,'used',used,flush=True)


def run(name):
    protocol=DESIGNBASE/(name+'.json');p=api.read(protocol);w=api.read(source.WORK)
    api.require(job.utc()<job.policy.utc(w['no_new_trajectory_after_utc']),'launch window');api.verify_mapping(p['inputs']);api.verify_mapping(p['new_sources'])
    api.require(job.shutil.disk_usage(ROOT).free>=p['minimum_free_disk_bytes'],'20GiB disk reserve');require_no_diagnostic();used,pending=ledger()
    api.require(not pending and used==p['prior_window_steps'] and used+p['maximum_new_steps']<=w['maximum_new_accepted_trajectory_steps'],'resolved frozen step reservation')
    d=api.read(job.DESIGN);job.verify(d);case=next(c for c in d['cases'] if c['id']==p['case']);geom=geometry(case)
    if p['seed_diagnostic']:
        seed=RUNBASE/p['seed_diagnostic'];before=api.read(seed/'checkpoint.json');ref=api.read(seed/'prefix.json');hist=api.read(seed/'history.json')
        prefix=frozen.pre.storage.codec.HistoryState(**ref,history_bytes=frozen.pre.storage.codec.packed_history(hist))
        frozen.pre.storage.codec.validate_prefix(prefix,api.sha(job.DESIGN))
    else:
        before=api.read(RECON/'checkpoint_00196.json');prefix=prefix196()
        # Independently re-audit segment196 before using its checkpoint. The
        # bootstrap is authenticated via complete canonical/history hashes.
        raw196=job.paths(job.RUN,source.NAME,196)['raw'];env=frozen.pre.storage.read_envelope(raw196,api.sha(job.DESIGN))
        rec196=copy.deepcopy(env['payload']);hist=api.read(RECON/'history_00196.json');rec196['result']['history']=hist;rec196['result']['checkpoint']['state']['history']=hist
        api.require(api.digest(rec196['result']['checkpoint'])==api.digest(before),'seed checkpoint exact')
        seedcheck=job.kernel.evaluate(rec196,case['spec'],job.binding(d,case),api.read(RECON/'checkpoint_00195.json'),geom,api.sha(job.DESIGN),d['minimum_gap_semantics'])
        api.require(seedcheck['passed'],'independent seed numerical audit')
    out=RUNBASE/name;out.mkdir(parents=True,exist_ok=False)
    job.commit(out/'launch.json',{'pid':os.getpid(),'utc':job.utc().isoformat(),'protocol_sha256':api.sha(protocol),'argv':sys.argv,'reserved_max_steps':p['maximum_new_steps'],'prior_steps':used,'seed_checkpoint_sha256':api.digest(before)})
    raw=out/'call.json.xz';rec=None
    try:
        repair.telemetry.clear();start=time.perf_counter()
        with repair.scope(job.parent.engine.runtime,True,job.policy.utc(w['work_end_utc']).timestamp()):
            rec,nextprefix,seal,elapsed=job.execute_segment(d,case,before,raw,p['trajectory_cap'],prefix,w['work_end_utc'])
        steps=int(rec['result']['steps'])-int(before['state']['steps'])
        api.require(0<=steps<=p['maximum_new_steps'],'exact bounded accepted-step delta')
        job.commit(out/'accounting.json',{'launch_sha256':api.sha(out/'launch.json'),'accepted_steps_known':True,'accepted_steps':steps,'window_steps':used+steps,'raw_sha256':api.sha(raw),'saved_status':rec['result']['status'],'rejected':rec['result']['rejected']})
        job.commit(out/'checkpoint.json',rec['result']['checkpoint']);job.commit(out/'prefix.json',nextprefix.reference());job.commit(out/'history.json',rec['result']['history'])
        # Fresh path-based decode, independent of producer object and telemetry.
        reread,state=frozen.pre.storage.codec.read_record(raw,api.sha(job.DESIGN),prefix)
        api.require(api.digest(reread)==api.digest(rec) and state.reference()==nextprefix.reference(),'exact fresh raw/history reconstruction')
        audit=None;audit_error=None
        try:audit=auditor.kernel(reread,case['spec'],job.binding(d,case),before,geom,api.sha(job.DESIGN),d['minimum_gap_semantics'])
        except Exception as error:audit_error={'error':repr(error),'traceback':traceback.format_exc()}
        comparison=None
        if p['seed_diagnostic'] is None:
            old,_=frozen.pre.storage.codec.read_record(job.paths(job.RUN,source.NAME,197)['raw'],api.sha(job.DESIGN),prefix)
            first=old['result']['rejected_trials'][0]['time_s'];oracle=[row for row in old['rows'] if row['time_s']<=first]
            count=min(len(oracle),len(rec['rows']));comparison={'rows':count,'available_original_prefix_rows':len(oracle),'exact_rows_before_first_old_rejection':rec['rows'][:count]==oracle[:count],'first_old_rejected_time_s':first,'end_time_s':rec['result']['checkpoint']['state']['t']}
        api.verify_mapping(p['inputs']);api.verify_mapping(p['new_sources']);job.verify(d)
        r={'numerical_audit_passed':bool(audit and audit['passed']),'audit':audit,'audit_error':audit_error,'steps':steps,'window_total_steps':used+steps,'rejected':rec['result']['rejected'],'status':rec['result']['status'],
          'time_s':rec['result']['checkpoint']['state']['t'],'original_prefix_comparison':comparison,'compute_seconds':rec['compute_call_wall_s'],'transaction_seconds':elapsed,'candidate_calls':len(repair.telemetry),'candidate_accepted':sum(c['accepted'] for c in repair.telemetry),
          'protocol_sha256':api.sha(protocol),'artifacts':{str(x):api.sha(x) for x in out.glob('*') if x.is_file()},'claim':'Bounded local diagnostic only; Stage200 remains failed and no full-path/release claim.'}
        job.commit(out/'results.json',r);job.commit(out/'completion.json',{'passed':r['numerical_audit_passed'],'results_sha256':api.sha(out/'results.json')});print('DIAGNOSTIC',name,r['numerical_audit_passed'],steps,r['rejected'],r['time_s'],flush=True)
    except Exception as error:
        if not (out/'accounting.json').exists():job.commit(out/'accounting.json',{'launch_sha256':api.sha(out/'launch.json'),'accepted_steps_known':False,'accepted_steps':None,'maximum_reserved_steps':p['maximum_new_steps'],'raw_exists':raw.exists()})
        job.commit(out/'failure.json',{'error':repr(error),'traceback':traceback.format_exc(),'raw_exists':raw.exists(),'claim':'Unresolved accounting blocks all further trajectory launches.'});raise


if __name__=='__main__':
    if len(sys.argv)>=4 and sys.argv[1]=='prepare':prepare(sys.argv[2],int(sys.argv[3]),sys.argv[4] if len(sys.argv)>4 else None)
    elif len(sys.argv)==3 and sys.argv[1]=='run':run(sys.argv[2])
    else:raise ValueError('prepare NAME CAP [SEED_DIAGNOSTIC] | run NAME')
