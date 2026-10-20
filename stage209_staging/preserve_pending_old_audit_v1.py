"""Zero-step immutable launch disposition; pending accounting is not closure."""
from pathlib import Path
import psutil
import cone_feasibility_campaign_v1 as s
api,job=s.api,s.job

def run():
    api.require(not job.DESIGN.exists() and not job.RUN.exists() and not s.OLD_LAUNCH_PROOF.exists(),'unfrozen exclusive preparation')
    d=api.read(s.OLD_DESIGN);api.verify_mapping(d['sources']);api.verify_mapping(d['inputs'])
    terminal=api.read(s.OLD_RUN/'completion.json');inventory=s.sealed(s.OLD_OUT/'terminal_failure_01/results.json')
    api.require(terminal['all_owned_processes_retired'] and terminal['stop_reasons'] and len(terminal['unrun_cases'])==1,'old simulations retired failed/incomplete')
    api.require(sum(c['sealed_segments'] for c in inventory['cases'])==3100 and sum(c['declared_saved_steps'] for c in inventory['cases'])==30631450,'old saved inventory preserved, not full verification')
    auth_path=s.ROOT/'stage206_evaluations/contact_failure_20260930/failed_evidence_01/results.json'
    auth=s.sealed(auth_path);api.verify_mapping(auth['inputs'])
    recon=s.sealed(s.stack.RECON/'results.json');api.verify_mapping(recon['inputs']);api.verify_mapping(recon['artifacts'])
    api.require(auth['original_campaign_remains_failed'] and not auth['numerical_gate_passed'] and auth['failed_segment_saved_steps']==2988,'rejected evidence never promoted')
    s.inherited();pf=s.sealed(s.QUAL_OUT/'preflight_01/results.json');ind=s.sealed(s.QUAL_OUT/'independent_readiness_01/results.json')
    api.require(pf['parallel_identity'] and pf['exact_restart'] and max(ind['parallel_slowdown_ratios'])<=1.3,'actual qualified concurrent performance')
    witness=s.OLD_OUT/'terminal_evaluator_01';launch=api.read(witness/'evaluator_launch.json');w=api.read(witness/'witness_launch.json')
    expected=[(51512,1790783066.466845,[launch['argv'][0],'-B','-u',str(s.ROOT/'stage205_staging/receipt_repaired_campaign_v2.py'),'evaluate','campaign']),
              (58964,1790783064.5909877,[launch['argv'][0],'-B','-u',str(s.ROOT/'stage205_staging/run_terminal_evaluator_v1.py')])]
    allowed=[]
    for pid,created,argv in expected:
        p=psutil.Process(pid);api.require(p.cmdline()==argv and abs(p.create_time()-created)<.001,'exact original read-only process identity')
        source=Path(argv[3]);record=launch if pid==51512 else w
        api.require(record['pid']==pid and record['source_sha256']==api.sha(source) and record['design_sha256']==api.sha(s.OLD_DESIGN),'immutable old launch record binding')
        allowed.append(dict(pid=pid,created=created,argv=argv,source_path=str(source),source_sha256=api.sha(source)))
    api.require(not (witness/'exit.json').exists() and not (s.OLD_OUT/'evaluation_01').exists(),'old full audit remains pending, no retry')
    files=[Path(__file__),job.WORK,s.OLD_DESIGN,s.OLD_RUN/'completion.json',s.OLD_OUT/'terminal_failure_01/results.json',s.OLD_OUT/'terminal_failure_01/completion.json',auth_path,auth_path.parent/'completion.json',s.stack.RECON/'results.json',s.stack.RECON/'completion.json',s.QUAL_CLOSE,s.QUAL_DESIGN,s.QUAL_OUT/'preflight_01/results.json',s.QUAL_OUT/'independent_readiness_01/results.json',witness/'evaluator_launch.json',witness/'witness_launch.json']
    proof=dict(old_run_remains_failed=True,old_failed_run_fully_accounted=False,full_old_accounting_required_before_final_acceptance=True,new_trajectory_steps=0,fresh_old_observations_reused=0,stage208_qualification_sha256=api.sha(s.QUAL_CLOSE),allowed_read_only_processes=allowed,old_saved_steps=30631450,old_saved_records=3100,preserved_failed_saved_steps=2988,qualified_concurrent_slowdown_max=max(ind['parallel_slowdown_ratios']),utc=job.utc().isoformat(),inputs={str(p):api.sha(p) for p in files},claim='Administrative launch disposition only. Exact original read-only old audit may finish alongside qualified fresh production. No old full accounting, recovered observation, scientific pass or empirical validation claimed. Original final acceptance still requires independent old failed-run closure.')
    job.commit(s.OLD_LAUNCH_PROOF,proof);job.commit(s.OLD_LAUNCH_PROOF.parent/'completion.json',dict(passed=True,results_sha256=api.sha(s.OLD_LAUNCH_PROOF)))
    print('PENDING_OLD_AUDIT_DISPOSITION',api.sha(s.OLD_LAUNCH_PROOF),flush=True)

if __name__=='__main__':run()
