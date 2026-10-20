"""Independent zero-step closure, explicit immutable metadata-key erratum.

The test wrapper replaced the text '256' indiscriminately while raising its
step reserve, misspelling auxiliary *_sha256 keys as *_sha2048. Hash values
and the raw archive's original schema are SHA-256. Preserve all originals,
independently check their actual bindings, and block this launcher for reuse.
"""
from pathlib import Path
import os,shutil
import psutil
import qualify_failure_codec_v1 as q
import audit_early_semismooth_v1 as auditor
job,api=q.job,q.api;BASE=q.ROOT/'stage194_evaluations/evidence_repair_20260924'
RUN=q.ROOT/'stage194_runs/evidence_repair_20260924/early_semismooth_restart_01'
DESIGN=q.ROOT/'stage194_designs/evidence_repair_20260924/early_semismooth_restart_01.json'
OUT=BASE/'early_restart_independent_closure_01'

def run():
    w=api.read(q.WORK);api.require(job.utc()<job.policy.utc(w['work_end_utc']),'audit work clock');d=api.read(job.DESIGN);job.verify(d)
    p=api.read(DESIGN);api.verify_mapping(p['inputs']);api.verify_mapping(p['sources']);src=BASE/'early_semismooth_restart_01';r=api.read(src/'results.json')
    api.require(api.read(src/'completion.json')['results_sha2048']==api.sha(src/'results.json') and r['protocol_sha2048']==api.sha(DESIGN),'actual SHA-256 despite erroneous auxiliary key spelling')
    api.verify_mapping(r['artifacts']);launch=api.read(RUN/'launch.json');api.require(launch['protocol_sha2048']==api.sha(DESIGN) and launch['reserved_new_accepted_steps']==2048,'launch reserve and actual protocol SHA-256')
    api.require(not psutil.pid_exists(launch['pid']),'owned diagnostic worker retired')
    old=q.ROOT/'stage194_designs/evidence_repair_20260924/trajectory_qualification_01.json'
    initial=q.independent_file(q.ROOT/'stage194_runs/evidence_repair_20260924/trajectory_qualification_01/call_01.json.xz',api.sha(old))['result']['checkpoint']
    OUT.mkdir(parents=True,exist_ok=False);inputs={str(x):api.sha(x) for x in (Path(__file__),DESIGN,src/'results.json',src/'completion.json',RUN/'launch.json',q.WORK)}
    job.commit(OUT/'launch.json',{'pid':os.getpid(),'utc':job.utc().isoformat(),'inputs':inputs,'new_trajectory_steps':0})
    records=[];reports=[];case=p['case'];total=0;job.parent.b.old.parent.configure()
    with job.prior.snapshot.scope(api,case['spec']['field_metadata']):
        _,data,meta=api.fields.load(2,1.,6);geometry=job.prior.candidate.original.GrainGeometry(data['sand_centres_m'],data['sand_radii_m'],meta['cell_length_m'])
        for i,cap in enumerate((1024,512,512)):
            path=RUN/f'call_{i+1:02d}.json.xz';record=q.independent_file(path,api.sha(DESIGN));before=initial if i<2 else records[1]['result']['checkpoint']
            accounted=api.read(RUN/f'call_{i+1:02d}.accounting.json');launched=api.read(RUN/f'call_{i+1:02d}.launch.json')
            api.require(launched['input_checkpoint_sha2048']==api.digest(before)==record['input_checkpoint_sha256'] and launched['cap']==cap,'unchanged complete input binding')
            api.require(accounted['raw_sha2048']==api.sha(path) and len(record['rows'])==accounted['accepted_steps']==cap,'actual raw SHA-256 and exact steps')
            check=auditor.kernel(record,case['spec'],p['original_binding'],before,geometry,api.sha(DESIGN),d['minimum_gap_semantics'])
            total+=cap;records.append(record);api.require(accounted['cumulative_new_steps']==total,'ordered step accounting')
            early=record['early_attempts'];fallback=record['fallback_systems']
            reports.append({'index':i,'audit':check,'raw_sha256':api.sha(path),'steps':cap,'compute_seconds':record['compute_call_wall_s'],
               'recorded_early_seconds':sum(x['wall_s'] for x in early),'recorded_fallback_seconds':sum(x['wall_s'] for x in fallback),'fallback_count':len(fallback)})
            print('INDEPENDENT_EARLY_AUDIT',i,cap,check['passed'],flush=True)
    api.require(records[0]['rows']==records[1]['rows']+records[2]['rows'] and records[0]['result']['checkpoint']['state']==records[2]['result']['checkpoint']['state'],'independent exact complete restart')
    ledger=[('diagnostic_replay_01',9645),('trajectory_qualification_01',9696),('dispatch_restart_01',55),('semismooth_restart_01',256),('early_semismooth_restart_01',2048)]
    for name,n in ledger:
        result=api.read(BASE/name/'results.json');api.require(result.get('new_accepted_steps')==n,'exact accepted ledger '+name)
    steps=sum(n for _,n in ledger);api.require(steps==21700<=w['maximum_new_accepted_trajectory_steps'],'work budget')
    api.verify_mapping(inputs);api.verify_mapping(r['artifacts']);api.verify_mapping(p['inputs']);api.verify_mapping(p['sources']);job.verify(d)
    result={'diagnostic_numerical_and_evidence_audit_passed':True,'launcher_metadata_schema_passed':False,
       'metadata_erratum':'Auxiliary *_sha2048 means SHA-256 in this one frozen diagnostic only; actual hash bindings independently verified. Do not reuse this wrapper or generalize this alias.',
       'original_files_unchanged':True,'new_trajectory_steps':0,'diagnostic_steps_verified':total,'exact_restart':True,'window_total_new_steps':steps,'remaining_step_allowance':50000-steps,
       'production_ready':False,'complete_observation':False,'owned_worker_retired':True,'free_disk_bytes':shutil.disk_usage(q.ROOT).free,
       'end_time_s':records[0]['result']['time_s'],'ledger':[{'run':n,'accepted_steps':k} for n,k in ledger],
       'reports':reports,'inputs':inputs,'old_missing_block174_still_unknown':True}
    job.commit(OUT/'results.json',result);job.commit(OUT/'completion.json',{'results_sha256':api.sha(OUT/'results.json')})
    print('INDEPENDENT_EARLY_CLOSURE',steps,result['end_time_s'],flush=True)

if __name__=='__main__':run()
