"""Separate recovery namespace; exact Stage219 integration and physical identity.

Stage219 remains interrupted. New records retain its immutable physical design
and numerical-policy IDs; the new recovery plan binds their administrative
lineage, output namespace, budgets and process identity separately.
"""
from pathlib import Path
from datetime import timedelta
import copy, json, os, shutil, subprocess, sys, time, traceback
import psutil
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'stage219_staging'))
import normal_gap_campaign_v1 as source
api, job = source.api, source.job
BASE = 'checkpoint_recovery_20261006'
RECON = ROOT / 'stage220_evaluations' / BASE / 'reconstruction_02'
OUT = ROOT / 'stage220_evaluations' / BASE
RUN = ROOT / 'stage220_runs' / BASE
PLAN = ROOT / 'stage220_designs' / BASE / 'design_01.json'
NAME = 's2_i124_fibre_f0p0625'
SELF = Path(__file__).resolve()


def sealed(path):
    row = api.read(path)
    api.require(api.read(path.parent/'completion.json')['results_sha256'] == api.sha(path), 'Sealed prerequisite')
    return row


def setup():
    d = api.read(job.DESIGN)
    job.verify(d); source.bindings()
    case = next(c for c in d['cases'] if c['id'] == NAME)
    job.parent.b.old.parent.configure()
    with job.prior.snapshot.scope(api, case['spec']['field_metadata']):
        _, data, meta = api.fields.load(2, 1., 6)
    geometry = job.prior.candidate.original.GrainGeometry(data['sand_centres_m'], data['sand_radii_m'], meta['cell_length_m'])
    return d, case, geometry


def seed():
    proof = sealed(RECON/'results.json')
    api.require(proof['passed'] and proof['complete_checkpoint_and_history_reconstructed']
        and proof['complete_chain_segments'] == 1060, 'Complete authenticated original prefix')
    # Artifact bindings cover these checkpoint/history/reference files.
    api.verify_mapping(proof['artifacts'])
    before = api.read(RECON/'checkpoint_01060.json')
    history = api.read(RECON/'history_01060.json')
    api.require(before['state']['history'] == history and api.digest(before['state']) == before['state_sha256'], 'Complete seed state')
    codec = job.codec
    prefix = codec.HistoryState(**api.read(RECON/'prefix_01060.json'), history_bytes=codec.packed_history(history))
    codec.validate_prefix(prefix, api.sha(job.DESIGN))
    return before, prefix


def execute_audited(d, case, geometry, before, prefix, folder, cap, stop, previous_receipt, save_checkpoint=False):
    folder.mkdir(parents=True, exist_ok=False)
    job.commit(folder/'launch.json', dict(pid=os.getpid(), created=psutil.Process().create_time(), argv=psutil.Process().cmdline(),
        utc=job.utc().isoformat(), recovery_design_sha256=api.sha(PLAN), physical_design_sha256=api.sha(job.DESIGN),
        input_checkpoint_sha256=api.digest(before), maximum_new_steps=cap, stop_utc=stop))
    raw = folder/'call.json.xz'
    original_seed = copy.deepcopy(before)
    with job.prior.snapshot.scope(api, case['spec']['field_metadata']):
        rec, next_prefix, seal, elapsed = source.execute(d, case, before, raw, cap, prefix, stop)
    steps = len(rec['rows'])
    job.commit(folder/'accounting.json', dict(saved_steps_known=True, saved_steps=steps,
        launch_sha256=api.sha(folder/'launch.json'), raw_sha256=api.sha(raw), transaction_seconds=elapsed,
        status=rec['result']['status'], rejected=rec['result']['rejected']))
    api.require(api.digest(before) == api.digest(original_seed), 'Integration preserves caller seed')
    decoded, audited_prefix = job.codec.read_record(raw, api.sha(job.DESIGN), prefix)
    api.require(api.digest(decoded) == api.digest(rec) and next_prefix.reference() == audited_prefix.reference(), 'Exact independent archive reconstruction')
    summary = job.kernel.evaluate(decoded, case['spec'], job.binding(d,case), original_seed, geometry,
        api.sha(job.DESIGN), d['minimum_gap_semantics'])
    api.require(summary['passed'] and rec['result']['rejected'] == 0 and 0 < steps <= cap, 'Original physical gates and positive bounded steps')
    api.require(rec['result']['checkpoint']['state']['steps'] - before['state']['steps'] == steps, 'Exact incremental step ledger')
    api.require(summary['start_s'] == before['state']['t'] and summary['stop_s'] == rec['result']['checkpoint']['state']['t'], 'Exact continuation clock')
    if save_checkpoint:
        job.commit(folder/'checkpoint.json',rec['result']['checkpoint'])
        job.commit(folder/'prefix.json',next_prefix.reference())
    # History already lives in checkpoint; no second physical-state writer.
    trace = np.asarray([[r['time_s'],*r['position_m'],*r['orientation'],*r['velocity_generalized']] for r in rec['rows']],dtype=np.float64)
    with (folder/'trace.npy').open('xb') as stream: np.save(stream,trace,allow_pickle=False)
    result = dict(passed=True,new_saved_steps=steps,summary=summary,transaction_seconds=elapsed,
        recovery_design_sha256=api.sha(PLAN),physical_design_sha256=api.sha(job.DESIGN),
        numerical_policy_contract_sha256=api.sha(job.WORK),original_binding=job.binding(d,case),
        input_checkpoint_sha256=api.digest(before),output_checkpoint_sha256=api.digest(rec['result']['checkpoint']),
        previous_recovery_receipt_sha256=previous_receipt,
        artifacts={str(p):api.sha(p) for p in folder.iterdir() if p.is_file()},
        original_campaign_remains_interrupted=True)
    job.commit(folder/'results.json',result)
    job.commit(folder/'completion.json',dict(passed=True,results_sha256=api.sha(folder/'results.json')))
    return decoded, audited_prefix, result


def prepare():
    api.require(not PLAN.exists() and not source.active_owned(), 'Exclusive new recovery design')
    early=sealed(OUT/'existing_pair_screen_01/results.json')
    api.require(early['passed'],'Existing full-path pairs must pass before spending more on continuation')
    proof = sealed(RECON/'results.json'); before,prefix = seed()
    d = api.read(job.DESIGN)
    review = sealed(ROOT/'stage219_evaluations/normal_gap_campaign_20261001/interruption_review_20261006_01/results.json')
    hours = review['recent_rate_remaining_producer_hours']['maximum'] * 1.3
    available = (job.policy.utc(d['simulation_cutoff_utc'])-job.utc()).total_seconds()/3600
    # 1,000 calls is a cap, not a storage forecast. Online reserve also applies.
    recent = [api.read(job.paths(job.RUN,NAME,n)['ready']) for n in range(1051,1061)]
    remaining_steps = max(m['steps']/(api.read(job.paths(job.RUN,NAME,m['segment'])['receipt'])['summary']['stop_s']-
        api.read(job.paths(job.RUN,NAME,m['segment'])['receipt'])['summary']['start_s']) for m in recent) * review['remaining_physical_seconds']
    estimated_bytes = max((job.paths(job.RUN,NAME,m['segment'])['raw'].stat().st_size+
        job.paths(job.RUN,NAME,m['segment'])['receipt'].stat().st_size+
        job.paths(job.RUN,NAME,m['segment'])['trace'].stat().st_size)/m['steps'] for m in recent)*remaining_steps*1.3
    estimated_bytes += 512*1024**2  # standalone qualification archives and terminal checkpoint
    free=shutil.disk_usage(ROOT).free; reserve=d['budget']['minimum_free_disk_bytes']
    api.require(available > hours+1 and free > estimated_bytes+reserve, 'Measured time and storage fit including qualification allowance')
    inputs=[job.DESIGN,job.WORK,RECON/'results.json',RECON/'completion.json',RECON/'checkpoint_01060.json',RECON/'prefix_01060.json',RECON/'history_01060.json',
        ROOT/'stage219_evaluations/normal_gap_campaign_20261001/interruption_review_20261006_01/results.json',
        OUT/'existing_pair_screen_01/results.json',OUT/'existing_pair_screen_01/completion.json']
    plan=dict(stage='Stage220 explicit unchanged-physics checkpoint recovery',authority='User next instruction after checkpoint recovery was identified as the next gate.',
        physical_design_sha256=api.sha(job.DESIGN),numerical_policy_contract_sha256=api.sha(job.WORK),original_binding=proof['original_binding'],case=NAME,
        seed_checkpoint_sha256=api.digest(before),original_saved_steps=before['state']['steps'],original_time_s=before['state']['t'],
        original_campaign_remains_interrupted=True,raw_design_identity_is_physical_lineage=True,
        raw_prefix_policy='First new record explicitly references the last original sealed prefix; subsequent records reference new sealed recovery prefixes.',
        physical_changes=[],acceptance_gates=d['numerical_gates'],qualification_steps=1024,qualification_serial_steps=512,
        qualification_split_steps=[256,256],qualification_separate_from_production=True,
        maximum_new_production_steps=3500000,maximum_production_calls=1000,step_cap_per_call=d['budget']['step_cap_per_call'],
        original_total_case_step_ceiling=next(c['step_ceiling'] for c in d['cases'] if c['id']==NAME),
        workers=1,threads=1,maximum_unverified_records=1,logical_cpu=10,
        minimum_free_disk_bytes=reserve,simulation_cutoff_utc=d['simulation_cutoff_utc'],final_audit_deadline_utc=d['final_audit_deadline_utc'],
        estimated_remaining_producer_hours_with_margin=hours,available_simulation_hours_at_design=available,
        estimated_remaining_bytes_with_margin=int(estimated_bytes),free_C_bytes_at_design=free,
        estimate_limit='Local extrapolation, not a bound; qualification and final audit are additional. Stop at original time/step/call/storage limits.',
        sources={**d['sources'],**{str(p):api.sha(p) for p in SELF.parent.glob('*.py')}},inputs={str(p):api.sha(p) for p in inputs},
        claim='Continuation of one original finite-horizon observation. No completion or population trend is implied by preparation or launch.')
    plan['binding']=api.digest(plan);job.commit(PLAN,plan)
    print('RECOVERY_DESIGN_PREPARED',hours,available,estimated_bytes,flush=True)


def verify_plan():
    p=api.read(PLAN)
    api.require(p['binding']==api.digest({k:v for k,v in p.items() if k!='binding'}),'Recovery design binding')
    api.verify_mapping(p['sources']);api.verify_mapping(p['inputs'])
    api.require(p['sources'][str(SELF)]==api.sha(SELF) and p['physical_changes']==[],'Exact recovery code and unchanged physics')
    return p


def qualify():
    p=verify_plan();api.require(not source.active_owned(),'No competing simulation')
    d,case,geometry=setup();before,prefix=seed()
    folder=RUN/'qualification_01';api.require(not folder.exists(),'Exclusive qualification')
    stop=min(job.policy.utc(p['simulation_cutoff_utc']).timestamp(),time.time()+1800)
    stop=job.utc().fromtimestamp(stop,job.utc().tzinfo).isoformat()
    a,pa,ra=execute_audited(d,case,geometry,copy.deepcopy(before),prefix,folder/'serial_01',512,stop,None,True)
    b,pb,rb=execute_audited(d,case,geometry,copy.deepcopy(before),prefix,folder/'split_a_01',256,stop,None,True)
    c,pc,rc=execute_audited(d,case,geometry,b['result']['checkpoint'],pb,folder/'split_b_01',256,stop,api.sha(folder/'split_a_01/results.json'),True)
    api.require(ra['new_saved_steps']==512 and rb['new_saved_steps']==rc['new_saved_steps']==256,'Exact qualification reservations')
    api.require(a['rows']==b['rows']+c['rows'],'Identical serial and split accepted rows')
    api.require(api.digest(a['result']['checkpoint'])==api.digest(c['result']['checkpoint']),'Identical full checkpoint including dwell/recovery/history')
    # Check the actual recovery bindings cannot alter the physical case.
    api.require(job.binding(d,case)==p['original_binding'] and before['state']['t']==p['original_time_s'],'Original physical identity preserved')
    result=dict(passed=True,new_saved_steps=1024,exact_split_rows=True,exact_full_checkpoint=True,
        all_three_independent_physics_audits_passed=True,original_seed_unchanged=True,
        recovery_design_sha256=api.sha(PLAN),original_campaign_remains_interrupted=True,
        artifacts={str(x):api.sha(x) for x in folder.rglob('*') if x.is_file()})
    destination=OUT/'restart_qualification_01';job.commit(destination/'results.json',result)
    job.commit(destination/'completion.json',dict(passed=True,results_sha256=api.sha(destination/'results.json')))
    print('RECOVERY_RESTART_QUALIFIED',1024,flush=True)


def produce():
    p=verify_plan();q=sealed(OUT/'restart_qualification_01/results.json')
    api.require(q['passed'] and q['recovery_design_sha256']==api.sha(PLAN),'Qualified exact recovery')
    api.verify_mapping(q['artifacts']);api.require(not source.active_owned(),'No competing simulation')
    d,case,geometry=setup();before,prefix=seed()
    root=RUN/'production_01';root.mkdir(parents=True,exist_ok=False)
    process=psutil.Process();process.cpu_affinity([p['logical_cpu']])
    job.commit(root/'launch.json',dict(pid=process.pid,created=process.create_time(),argv=process.cmdline(),utc=job.utc().isoformat(),
        affinity=process.cpu_affinity(),recovery_design_sha256=api.sha(PLAN),inherited_saved_steps=before['state']['steps']))
    total=0;previous=None;entries=[];reason='call_limit';remaining=None
    try:
        for index in range(1,p['maximum_production_calls']+1):
            if job.utc()>=job.policy.utc(p['simulation_cutoff_utc'])-timedelta(seconds=d['stop_reserve_seconds']):
                reason='simulation_cutoff';break
            if shutil.disk_usage(ROOT).free<=p['minimum_free_disk_bytes']+4*job.codec.base.MAX_COMPRESSED:
                reason='disk_reserve';break
            remaining=min(p['maximum_new_production_steps']-total,case['step_ceiling']-before['state']['steps'])
            if remaining<=0:reason='step_ceiling';break
            folder=root/f'segment_{index:05d}'
            rec,prefix,r=execute_audited(d,case,geometry,before,prefix,folder,min(p['step_cap_per_call'],remaining),p['simulation_cutoff_utc'],previous)
            total+=r['new_saved_steps'];before=rec['result']['checkpoint'];previous=api.sha(folder/'results.json')
            entries.append(dict(segment=index,results_sha256=previous,new_saved_steps=r['new_saved_steps'],stop_s=before['state']['t']))
            print('RECOVERY_VERIFIED',index,total,before['state']['t'],flush=True)
            if rec['result']['status'] in job.policy.COMPLETE:reason='observation_complete';break
        result=dict(recovery_finished=True,complete_observation=reason=='observation_complete',reason=reason,
            original_campaign_remains_interrupted=True,recovery_design_sha256=api.sha(PLAN),new_saved_steps=total,
            qualification_saved_steps=q['new_saved_steps'],inherited_saved_steps=p['original_saved_steps'],
            cumulative_physical_steps=before['state']['steps'],time_s=before['state']['t'],horizon_s=case['spec']['horizon_s'],
            final_status=rec['result']['status'] if entries else 'unrun_recovery',entries=entries,
            full_campaign_comparison_pending=True,final_checkpoint_sha256=api.digest(before))
        job.commit(root/'checkpoint.json',before)
        job.commit(root/'prefix.json',prefix.reference())
        job.commit(root/'results.json',result);job.commit(root/'completion.json',dict(results_sha256=api.sha(root/'results.json'),complete_observation=result['complete_observation']))
        print('RECOVERY_TERMINAL',result['complete_observation'],reason,total,before['state']['t'],flush=True)
        if result['complete_observation']:
            command=[sys.executable,'-B','-u',str(SELF.with_name('evaluate_recovery_v1.py'))]
            with (root/'evaluation.stdout.log').open('xb') as stdout,(root/'evaluation.stderr.log').open('xb') as stderr:
                child=subprocess.Popen(command,cwd=str(ROOT),env=dict(os.environ),stdout=stdout,stderr=stderr,creationflags=subprocess.CREATE_NO_WINDOW)
            job.commit(root/'evaluation_launch.json',dict(pid=child.pid,created=psutil.Process(child.pid).create_time(),argv=command,utc=job.utc().isoformat(),new_trajectory_steps=0))
            # The child enforces the original final-audit deadline on entry.
            # Preserve its output and failure even when numerical gates fail.
            code=child.wait()
            job.commit(root/'evaluation_exit.json',dict(exit_code=code,utc=job.utc().isoformat(),new_trajectory_steps=0))
    except Exception as error:
        job.commit(root/'failure.json',dict(error=repr(error),traceback=traceback.format_exc(),verified_new_saved_steps=total,entries=entries,
            physical_state_before_failing_call_sha256=api.digest(before),original_campaign_remains_interrupted=True))
        raise


if __name__=='__main__':
    {'prepare':prepare,'qualify':qualify,'produce':produce}[sys.argv[1]]()
