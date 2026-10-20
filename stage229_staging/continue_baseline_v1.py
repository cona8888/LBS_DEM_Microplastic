"""Create-only Stage229 continuation of the original qualified Stage222 core.

The administrative plan changes clocks, output paths and renewed shared limits.
The physical design, case IDs, dynamics/checkpoint binding, numerical-gap policy,
integration code and independent physical/whole-path gates remain Stage222's.
No contact optimization prototype is installed by this module.
"""
from pathlib import Path
from datetime import timedelta
import copy, hashlib, os, shutil, sys, time, traceback
import psutil
import numpy as np
import campaign_common_v1 as c

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'stage222_staging'))
import overnight_campaign_v1 as baseline

api, job = baseline.api, baseline.job
SELF = Path(__file__).resolve()
PLAN = c.DESIGNS/'transport_design_01.json'
RUN = c.RUN/'run_01'
OUT = c.OUT
AUTH = c.AUTH
FINAL = ROOT/'stage222_evaluations/overnight_coarser_20261007/final_disposition_01/results.json'
SEED_NAME = 's2_i0_fibre_f0p125'
SEED_FOLDER = baseline.RUN/SEED_NAME
EXPECTED_PHYSICAL_SHA = 'bad6127d636511ab08dbf9a432cc6919885b5e779d2edc577ce0305a8de1a4fc'
EXPECTED_FINAL_SHA = '6d9587da7052de083c87981778c89c796e20f3320029726e51025888a25bf80c'
EXPECTED_SEED_DIGEST = 'e5dcdd7b03a821f2dea77619faf941231ec5a3fe2c0dd538ff5f42a1c7d8559a'
EXPECTED_LAST_RECEIPT = '17b1544284cb9243cc963165687bc5f31e32943ce805ce2b3b89da1d104a90b9'


def sealed(path):
    return c.sealed(path)


def physical_design():
    api.require(job.DESIGN == baseline.PLAN and c.sha(job.DESIGN) == EXPECTED_PHYSICAL_SHA,
                'Exact original Stage222 physical design, never a new dynamics binding')
    return api.read(job.DESIGN)


def structural_checks():
    """No solver calls: prove the unchanged code, globals and seed contract."""
    baseline.clone_check()
    d = physical_design()
    baseline.verify(d)
    baseline.old.verify(api.read(baseline.old.DESIGN))
    baseline.source.bindings()
    case = next(row for row in d['cases'] if row['id'] == SEED_NAME)
    before = api.read(SEED_FOLDER/'checkpoint.json')
    effective = job.parent.model.binding_for(job.binding(d, case), True)
    expected = job.parent.engine.prior.contracts.expected_contract(case['spec'], effective)
    api.require(before['contract'] == expected and api.digest(before) == EXPECTED_SEED_DIGEST,
                'Late seed has the original full physical contract')
    return dict(passed=True, numerical_calls=0, physical_design_sha256=c.sha(job.DESIGN),
                original_binding=job.binding(d, case), checkpoint_contract=expected,
                numerical_policy_contract_sha256=c.sha(job.WORK),
                unchanged_integrator_and_independent_auditor=True,
                optimization_prototype_installed=False)


def authenticate_inherited():
    """Authenticate prior raw/trace seals and receipts; reuse prior physics audits.

    The separately sealed final disposition already reconstructed every complete
    checkpoint/history in the 569-segment raw genealogy. Its authenticated proof
    is retained; no claim that the old physical solves were rerun is made.
    """
    api.require(c.sha(FINAL) == EXPECTED_FINAL_SHA, 'Exact prior final disposition')
    proof = sealed(FINAL)
    for field in ('passed', 'final_accounting_authenticated',
                  'all_raw_seals_and_full_checkpoint_history_ancestry_reconstructed',
                  'terminal_prefix_authenticated', 'inherited_physical_audits_rehashed_and_reused'):
        api.require(proof[field] is True, 'Complete inherited proof: '+field)
    api.require(proof['terminal_reason'] == 'simulation_cutoff' and not proof['whole_overnight_success'],
                'Previous bounded attempt remains incomplete and closed')
    c.verify(proof['artifacts'])
    d = physical_design()
    case_result = sealed(SEED_FOLDER/'results.json')
    entries = case_result['entries']
    api.require(len(entries) == len(proof['all_sealed_production_receipts']) == 569,
                'Exact inherited production inventory')
    api.require(len(list(SEED_FOLDER.glob('segment_*'))) == 569, 'No extra inherited production folder')
    inputs = {str(FINAL): c.sha(FINAL), str(FINAL.parent/'completion.json'): c.sha(FINAL.parent/'completion.json'),
              **proof['artifacts']}
    previous_receipt = None
    previous_checkpoint = api.digest(None)
    count, stop = 0, 0.
    traces = []
    for index, entry in enumerate(entries, 1):
        c.bound()
        api.require(entry['segment'] == index, 'Contiguous inherited segment indices')
        folder = SEED_FOLDER/f'segment_{index:05d}'
        receipt = folder/'results.json'
        sha = c.sha(receipt)
        api.require(proof['all_sealed_production_receipts'][str(receipt)] == entry['results_sha256'] == sha,
                    'Frozen inherited receipt identity')
        row = sealed(receipt)
        c.verify(row['artifacts'])
        api.require(row['passed'] and row['summary']['passed'] and row['design_sha256'] == EXPECTED_PHYSICAL_SHA,
                    'Original passing physical receipt')
        api.require(row['input_checkpoint_sha256'] == previous_checkpoint
                    and row['previous_receipt_sha256'] == previous_receipt, 'Complete receipt/checkpoint ancestry')
        api.require(row['new_saved_steps'] == entry['new_saved_steps'] == row['summary']['steps']
                    and row['summary']['start_s'] == stop and entry['stop_s'] == row['summary']['stop_s'],
                    'Exact inherited time/step ancestry')
        accounting = api.read(folder/'accounting.json')
        api.require(accounting['saved_steps'] == row['new_saved_steps'] and accounting['rejected'] == 0,
                    'Saved raw accounting agrees with physical audit')
        raw = folder/'call.json.xz'
        seal = api.read(folder/'call.json.seal.json')
        api.require(seal['compressed_sha256'] == accounting['raw_sha256'] == c.sha(raw)
                    and seal['compressed_bytes'] == raw.stat().st_size
                    and seal['design_sha256'] == EXPECTED_PHYSICAL_SHA, 'Exact prior compressed seal')
        inputs.update(row['artifacts'])
        inputs[str(receipt)] = sha
        inputs[str(folder/'completion.json')] = c.sha(folder/'completion.json')
        traces.append(folder/'trace.npy')
        count += row['new_saved_steps']
        stop = row['summary']['stop_s']
        previous_checkpoint = row['output_checkpoint_sha256']
        previous_receipt = sha
    before = api.read(SEED_FOLDER/'checkpoint.json')
    history = before['state']['history']
    reference = api.read(SEED_FOLDER/'prefix.json')
    prefix = job.codec.HistoryState(**reference, history_bytes=job.codec.packed_history(history))
    job.codec.validate_prefix(prefix, EXPECTED_PHYSICAL_SHA)
    api.require(api.digest(before['state']) == before['state_sha256']
                == row['summary']['output_checkpoint_state_sha256'], 'Complete inherited state digest')
    api.require(api.digest(before) == previous_checkpoint == case_result['final_checkpoint_sha256']
                == EXPECTED_SEED_DIGEST and previous_receipt == EXPECTED_LAST_RECEIPT,
                'Final checkpoint matches last sealed receipt')
    api.require(count == before['state']['steps'] == proof['physical_steps'] == 2222546
                and stop == before['state']['t'] == 2.7638384455506877,
                'Exact inherited cumulative clock and step count')
    api.require(len(history) == prefix.history_length == 8890
                and hashlib.sha256(job.codec.packed_history(history)).hexdigest() == prefix.history_sha256,
                'Complete retained monitor/history, not only position and velocity')
    api.require(reference['path'] == str(SEED_FOLDER/'segment_00569/call.json.xz')
                and reference['compressed_sha256'] == c.sha(Path(reference['path'])), 'Exact terminal raw prefix')
    return before, prefix, dict(passed=True, inherited_segments=569, inherited_physical_steps=count,
        inherited_stop_s=stop, input_checkpoint_sha256=api.digest(before),
        inherited_last_receipt_sha256=previous_receipt, inherited_prefix=reference,
        trace_paths=[str(p) for p in traces], inputs=inputs, original_physical_audits_reused=True,
        original_physical_audits_rerun=False, old_complete_checkpoint_reconstruction_proof_sha256=c.sha(FINAL))


def prepare():
    a = c.bound(); c.environment(); c.verify(a['sources']); c.verify(a['inputs'])
    checks = structural_checks()
    before, prefix, inherited = authenticate_inherited()
    physical = physical_design()
    b = a['independent_baseline']
    api.require(b['authorized'] and b['factor'] == .125 and not a['candidate_production_authorized'],
                'Original baseline alone is authorized')
    api.require([row['id'] for row in physical['cases']] == b['case_order'], 'Original case order')
    plan = dict(stage='Stage229 separately frozen original baseline continuation', utc=c.utc(),
        authorization_sha256=c.sha(AUTH), start_utc=a['start_utc'], authorized_end_utc=a['end_utc'],
        simulation_cutoff_utc=a['simulation_cutoff_utc'], final_audit_deadline_utc=a['end_utc'],
        physical_design_path=str(job.DESIGN), physical_design_sha256=c.sha(job.DESIGN),
        numerical_policy_contract_sha256=c.sha(job.WORK), physical_changes=[], numerical_changes=[],
        candidate_production_authorized=False, original_case_order=b['case_order'],
        maximum_saved_steps_including_diagnostics=a['maximum_saved_steps_including_diagnostics'],
        maximum_cumulative_physical_steps_per_case=b['maximum_cumulative_physical_steps_per_case'],
        maximum_cumulative_calls_per_case=b['maximum_cumulative_calls_per_case'],
        step_cap_per_call=b['maximum_steps_per_segment'], qualification_steps_per_case=b['diagnostic_steps_per_case'],
        minimum_free_disk_bytes=a['minimum_free_disk_bytes'], logical_cpu=a['logical_cpu'],
        workers=a['workers'], threads=a['threads'], maximum_unverified_records=a['maximum_unverified_records'],
        inherited=inherited, no_force_structural_checks=checks,
        source_files={**physical['sources'], str(SELF): c.sha(SELF), str(Path(c.__file__).resolve()): c.sha(c.__file__)},
        inputs={str(AUTH): c.sha(AUTH), **inherited['inputs'],
                str(baseline.PREREQUISITE): c.sha(baseline.PREREQUISITE),
                str(baseline.PREREQUISITE.parent/'completion.json'): c.sha(baseline.PREREQUISITE.parent/'completion.json')},
        claim=a['claim_boundary'], original_stage222_remains_closed=True,
        failure_rule=a['failure_rule'])
    plan['binding'] = c.digest(plan)
    c.commit(PLAN, plan)
    verify(plan)
    destination = OUT/'transport_preparation_01'
    c.commit(destination/'results.json', dict(passed=True, numerical_calls=0, new_trajectory_steps=0,
        transport_design_sha256=c.sha(PLAN), authorization_sha256=c.sha(AUTH),
        structural_checks=checks, inherited_summary={k:v for k,v in inherited.items() if k not in ('inputs','trace_paths')},
        artifacts={str(PLAN):c.sha(PLAN)}))
    c.commit(destination/'completion.json', dict(passed=True, results_sha256=c.sha(destination/'results.json')))
    print('STAGE229_TRANSPORT_PREPARED', c.sha(PLAN), flush=True)


def verify(plan):
    a = c.bound(); c.environment()
    c.verify(a['sources']); c.verify(a['inputs'])
    api.require(plan['binding'] == c.digest({k:v for k,v in plan.items() if k != 'binding'}), 'Immutable transport design')
    c.verify(plan['source_files']); c.verify(plan['inputs'])
    api.require(plan['authorization_sha256'] == c.sha(AUTH), 'Exact new shared authorization')
    api.require(plan['start_utc'] == a['start_utc'] == c.START
                and plan['authorized_end_utc'] == a['end_utc'] == c.END
                and plan['simulation_cutoff_utc'] == a['simulation_cutoff_utc'] == c.CUTOFF,
                'Exact new twelve-hour clocks; original closed clock is not extended')
    b = a['independent_baseline']
    expected = dict(maximum_saved_steps_including_diagnostics=10000000,
        maximum_cumulative_physical_steps_per_case=5000000, maximum_cumulative_calls_per_case=1500,
        step_cap_per_call=10000, qualification_steps_per_case=512, minimum_free_disk_bytes=20*1024**3,
        workers=1, threads=1, maximum_unverified_records=1)
    for key, value in expected.items():
        api.require(plan[key] == value, 'Unchanged bounded limit: '+key)
    api.require(plan['original_case_order'] == b['case_order']
                and plan['physical_changes'] == plan['numerical_changes'] == []
                and plan['candidate_production_authorized'] is False, 'No optimization or new physics')
    api.require(plan['physical_design_sha256'] == c.sha(job.DESIGN) == EXPECTED_PHYSICAL_SHA
                and plan['numerical_policy_contract_sha256'] == c.sha(job.WORK), 'Original scientific identities')
    baseline.clone_check()
    return plan


def dispatch_allowed(plan):
    decision = c.baseline_dispatch_allowed()
    api.require(decision['authorization_sha256'] == c.sha(AUTH), 'Dispatch under the new authority')
    api.require(job.utc() < job.policy.utc(plan['simulation_cutoff_utc']) - timedelta(seconds=120),
                'Dispatch within simulation reserve')
    return decision


def resource_stop(plan, used, needed=1):
    c.bound()
    if job.utc() >= job.policy.utc(plan['simulation_cutoff_utc'])-timedelta(seconds=120):
        return 'simulation_cutoff'
    if shutil.disk_usage(ROOT).free <= plan['minimum_free_disk_bytes']+4*job.codec.base.MAX_COMPRESSED:
        return 'disk_reserve'
    if used+needed > plan['maximum_saved_steps_including_diagnostics']:
        return 'shared_step_ceiling'
    return None


def segment(plan, d, case, geometry, before, prefix, folder, cap, previous, role):
    """One synchronous transaction, followed by the unchanged independent audit."""
    api.require(0 < cap <= plan['step_cap_per_call'], 'Original maximum segment reservation')
    c.bound(); c.verify(plan['source_files'])
    api.require(plan['authorization_sha256'] == c.sha(AUTH), 'Frozen shared authority before every segment')
    baseline.clone_check()
    folder.mkdir(parents=True, exist_ok=False)
    c.commit(folder/'launch.json', dict(pid=os.getpid(),created=psutil.Process().create_time(),
        argv=psutil.Process().cmdline(),utc=c.utc(), transport_design_sha256=c.sha(PLAN),
        physical_design_sha256=c.sha(job.DESIGN), authorization_sha256=c.sha(AUTH),
        input_checkpoint_sha256=api.digest(before),maximum_saved_steps=cap,role=role,
        simulation_cutoff_utc=plan['simulation_cutoff_utc']))
    seed = copy.deepcopy(before)
    raw = folder/'call.json.xz'
    with job.prior.snapshot.scope(api, case['spec']['field_metadata']):
        rec, next_prefix, seal, elapsed = baseline.execute(d, case, before, raw, cap, prefix, plan['simulation_cutoff_utc'])
    steps = len(rec['rows'])
    c.commit(folder/'accounting.json', dict(saved_steps_known=True,saved_steps=steps,raw_sha256=c.sha(raw),
        transaction_seconds=elapsed,rejected=rec['result']['rejected'],role=role))
    decoded, checked_prefix = job.codec.read_record(raw, c.sha(job.DESIGN), prefix)
    api.require(api.digest(decoded) == api.digest(rec) and next_prefix.reference() == checked_prefix.reference(),
                'Exact independent lossless archive reconstruction')
    api.require(api.digest(before) == api.digest(seed), 'Caller seed unchanged')
    summary = baseline.kernel(decoded, case['spec'], job.binding(d,case), seed, geometry,
        c.sha(job.DESIGN), d['minimum_gap_semantics'])
    api.require(summary['passed'] and rec['result']['rejected'] == 0 and 0 < steps <= cap,
                'Original independent physical gates, no rejected step, positive bounded increment')
    cp = rec['result']['checkpoint']
    initial_steps = 0 if seed is None else seed['state']['steps']
    initial_time = 0. if seed is None else seed['state']['t']
    api.require(cp['state']['steps']-initial_steps == steps and summary['start_s'] == initial_time
                and summary['stop_s'] == cp['state']['t'], 'Exact cumulative step/clock continuity')
    trace = np.asarray([[r['time_s'],*r['position_m'],*r['orientation'],*r['velocity_generalized']]
                        for r in rec['rows']],dtype=np.float64)
    with (folder/'trace.npy').open('xb') as stream:
        np.save(stream,trace,allow_pickle=False)
    row = dict(passed=True,new_saved_steps=steps,summary=summary,transaction_seconds=elapsed,role=role,
        transport_design_sha256=c.sha(PLAN),physical_design_sha256=c.sha(job.DESIGN),
        numerical_policy_contract_sha256=c.sha(job.WORK),original_binding=job.binding(d,case),
        input_checkpoint_sha256=api.digest(seed),output_checkpoint_sha256=api.digest(cp),
        previous_receipt_sha256=previous,artifacts={str(p):c.sha(p) for p in folder.iterdir() if p.is_file()},
        original_stage222_remains_closed=True,candidate_production_authorized=False)
    c.commit(folder/'results.json',row)
    c.commit(folder/'completion.json',dict(passed=True,results_sha256=c.sha(folder/'results.json')))
    return rec, checked_prefix, row


def qualify(plan, d, case, geometry, before, prefix, inherited_receipt):
    root = RUN/case['id']/'qualification_01'
    seed_digest = api.digest(before)
    a, pa, ra = segment(plan,d,case,geometry,copy.deepcopy(before),prefix,root/'serial_01',256,inherited_receipt,'restart_diagnostic')
    b, pb, rb = segment(plan,d,case,geometry,copy.deepcopy(before),prefix,root/'split_a_01',128,inherited_receipt,'restart_diagnostic')
    cr, pc, rc = segment(plan,d,case,geometry,b['result']['checkpoint'],pb,root/'split_b_01',128,c.sha(root/'split_a_01/results.json'),'restart_diagnostic')
    api.require(ra['new_saved_steps'] == 256 and rb['new_saved_steps'] == rc['new_saved_steps'] == 128,
                'Exact512 separate diagnostic steps')
    api.require(a['rows'] == b['rows']+cr['rows'] and api.digest(a['result']['checkpoint']) == api.digest(cr['result']['checkpoint']),
                'Exact late-seed serial/split accepted rows and full checkpoint')
    api.require(api.digest(before) == seed_digest, 'Original production seed preserved; diagnostics not promoted')
    row = dict(passed=True,diagnostic_saved_steps=512,exact_serial_split_rows=True,exact_full_checkpoint=True,
        all_three_independent_physical_audits_passed=True,production_seed_unchanged=True,
        production_seed_sha256=seed_digest,transport_design_sha256=c.sha(PLAN),
        diagnostic_trajectory_promoted=False,artifacts={str(p):c.sha(p) for p in root.rglob('*') if p.is_file()})
    c.commit(root/'results.json',row);c.commit(root/'completion.json',dict(passed=True,results_sha256=c.sha(root/'results.json')))
    return 512


def compare(plan, d, case, terminal, new_entries, inherited_paths):
    """Original full start-to-terminal metrics/gates over old prefix plus new tail."""
    c.bound(); c.verify(plan['source_files'])
    c.verify(plan['inherited']['inputs'])
    refname = case['reference_case']
    if case['sample_id'] == 0:
        refname = next(row['id'] for row in api.read(baseline.old.DESIGN)['cases']
                       if row['shape'] == case['shape'] and row['sample_id'] == 0 and row['factor'] == .03125)
    proof = sealed(baseline.PREREQUISITE)
    api.require(proof['passed'], 'Original fine/reference scientific gates passed')
    reference_paths = sorted((baseline.old.RUN/refname).glob('segment_*.npy'))
    if refname == baseline.inherited.NAME:
        recovered = baseline.inherited.sealed(baseline.inherited.RUN/'production_01/results.json')
        reference_paths += [baseline.inherited.RUN/'production_01'/f"segment_{x['segment']:05d}"/'trace.npy' for x in recovered['entries']]
    for path in reference_paths:
        api.require(proof['artifacts'][str(path)] == c.sha(path), 'Authenticated original reference full path')
    paths = [Path(p) for p in inherited_paths]
    for entry in new_entries:
        folder = RUN/case['id']/f"segment_{entry['segment']:05d}"
        receipt = sealed(folder/'results.json'); c.verify(receipt['artifacts'])
        api.require(entry['results_sha256'] == c.sha(folder/'results.json') and receipt['passed'], 'Passing new full-path receipt')
        paths.append(folder/'trace.npy')
    state = terminal['checkpoint']['state']
    evidence = dict(status=terminal['status'],steps=state['steps'],start_s=0.,stop_s=state['t'],
        rejected=terminal['rejected'],failure_markers=[],pending_trial=state['pending_trial'],
        first_dwell_s=terminal['first_contact_dwell_time_s'],export_verified=terminal['status']=='full_window_exit',
        raw_hashes_verified=True,clock_steps_verified=True,physics_verified=True,fresh_start=True)
    observation = job.policy.observation(evidence,case['spec']['horizon_s'])
    reference = next(row for placement in proof['placements'] for row in placement['cases'] if row['case_id'] == refname)
    def blocks(sequence):
        for path in sequence:
            yield np.load(path,mmap_mode='r',allow_pickle=False)
    initial = case['spec']['initial_state']
    row0 = [0.,*initial['position_m'],*initial['orientation'],*initial['velocity_generalized']]
    cfg = case['spec']['config']
    metrics = job.path_metrics.metrics(blocks(paths),blocks(reference_paths),row0,row0,
        observation['stop_s'],reference['stop_s'],cfg['prolate_semiaxes_m'][1],cfg['target_mean_interstitial_velocity_m_s'])
    gates = job.policy.pair_gates(observation,reference,metrics,d['numerical_gates'])
    row = dict(passed=gates['passed'],case=case['id'],reference_case=refname,observation=observation,
        full_path_gates=gates,reference_evaluation_sha256=c.sha(baseline.PREREQUISITE),
        transport_design_sha256=c.sha(PLAN),physical_design_sha256=c.sha(job.DESIGN),
        inherited_segments=len(inherited_paths),new_segments=len(new_entries),new_trajectory_steps=0,
        full_original_start_to_terminal_path=True,original_stage222_remains_closed=True,
        path_artifacts={str(p):c.sha(p) for p in paths+reference_paths})
    destination = OUT/case['id']/'comparison_01'
    c.commit(destination/'results.json',row);c.commit(destination/'completion.json',dict(passed=row['passed'],results_sha256=c.sha(destination/'results.json')))
    return row


def run():
    plan = verify(c.read(PLAN));decision = dispatch_allowed(plan)
    structural_checks()
    d = physical_design()
    before, prefix, inherited = authenticate_inherited()
    api.require(inherited == plan['inherited'], 'Frozen inherited genealogy unchanged at launch')
    RUN.mkdir(parents=True,exist_ok=False)
    process = psutil.Process();process.cpu_affinity([plan['logical_cpu']])
    c.commit(RUN/'launch.json',dict(pid=process.pid,created=process.create_time(),argv=process.cmdline(),utc=c.utc(),
        affinity=process.cpu_affinity(),transport_design_sha256=c.sha(PLAN),physical_design_sha256=c.sha(job.DESIGN),
        authorization_sha256=c.sha(AUTH),dispatch_decision_sha256=c.sha(c.OUT/'dispatch_decision_01/results.json')))
    total = diagnostic = 0
    cases = []
    reservation = None
    reason = 'work_window'
    try:
        for case in d['cases']:
            stop = resource_stop(plan,total,512)
            if stop:
                reason=stop;break
            is_seed = case['id'] == SEED_NAME
            cp = copy.deepcopy(before) if is_seed else None
            current_prefix = prefix if is_seed else None
            previous = inherited['inherited_last_receipt_sha256'] if is_seed else None
            inherited_calls = inherited['inherited_segments'] if is_seed else 0
            inherited_steps = inherited['inherited_physical_steps'] if is_seed else 0
            inherited_paths = inherited['trace_paths'] if is_seed else []
            geometry = baseline.geometry_for(case)
            reservation=dict(case=case['id'],role='restart_diagnostic',maximum_saved_steps=512)
            diagnostic+=qualify(plan,d,case,geometry,cp,current_prefix,previous);total+=512;reservation=None
            entries=[];rec=None;case_reason='call_limit'
            for index in range(1,plan['maximum_cumulative_calls_per_case']-inherited_calls+1):
                stop=resource_stop(plan,total)
                if stop:
                    case_reason=stop;break
                remaining=min(plan['maximum_saved_steps_including_diagnostics']-total,
                    plan['maximum_cumulative_physical_steps_per_case']-(0 if cp is None else cp['state']['steps']))
                if remaining<=0:
                    case_reason='case_step_ceiling';break
                folder=RUN/case['id']/f'segment_{index:05d}'
                reservation=dict(case=case['id'],role='production',segment=index,
                    maximum_saved_steps=min(plan['step_cap_per_call'],remaining),input_checkpoint_sha256=api.digest(cp))
                rec,current_prefix,row=segment(plan,d,case,geometry,cp,current_prefix,folder,
                    reservation['maximum_saved_steps'],previous,'production')
                total+=row['new_saved_steps'];cp=rec['result']['checkpoint'];previous=c.sha(folder/'results.json');reservation=None
                entries.append(dict(segment=index,cumulative_case_call=inherited_calls+index,new_saved_steps=row['new_saved_steps'],
                    results_sha256=previous,stop_s=cp['state']['t']))
                print('STAGE229_VERIFIED',case['id'],index,total,cp['state']['t'],flush=True)
                if rec['result']['status'] in job.policy.COMPLETE:
                    case_reason='observation_complete';break
            folder=RUN/case['id']
            row=dict(case=case['id'],complete_observation=case_reason=='observation_complete',reason=case_reason,
                inherited_physical_steps=inherited_steps,inherited_calls=inherited_calls,new_physical_steps=sum(x['new_saved_steps'] for x in entries),
                cumulative_physical_steps=0 if cp is None else cp['state']['steps'],cumulative_calls=inherited_calls+len(entries),
                diagnostic_saved_steps=512,entries=entries,final_checkpoint_sha256=api.digest(cp),
                time_s=0. if cp is None else cp['state']['t'],horizon_s=case['spec']['horizon_s'],
                final_status='unrun_continuation' if rec is None else rec['result']['status'],
                transport_design_sha256=c.sha(PLAN),physical_design_sha256=c.sha(job.DESIGN),original_stage222_remains_closed=True)
            c.commit(folder/'checkpoint.json',cp);c.commit(folder/'prefix.json',None if current_prefix is None else current_prefix.reference())
            c.commit(folder/'results.json',row);c.commit(folder/'completion.json',dict(results_sha256=c.sha(folder/'results.json'),complete_observation=row['complete_observation']))
            cases.append(row)
            if not row['complete_observation']:
                reason=case_reason;break
            comparison=compare(plan,d,case,rec['result'],entries,inherited_paths)
            if not comparison['passed']:
                reason='full_path_gate_failed';break
        else:
            reason='all_four_numerical_cases_complete'
        result=dict(finished=True,reason=reason,saved_steps_including_diagnostics=total,diagnostic_saved_steps=diagnostic,
            new_physical_steps=total-diagnostic,inherited_physical_steps=inherited['inherited_physical_steps'],
            cases=cases,utc=c.utc(),transport_design_sha256=c.sha(PLAN),physical_design_sha256=c.sha(job.DESIGN),
            authorization_sha256=c.sha(AUTH),whole_overnight_success=reason=='all_four_numerical_cases_complete',
            original_stage222_remains_closed=True,candidate_production_authorized=False,claim=plan['claim'])
        c.commit(RUN/'results.json',result);c.commit(RUN/'completion.json',dict(results_sha256=c.sha(RUN/'results.json'),finished=True))
        print('STAGE229_TRANSPORT_FINISHED',reason,total,flush=True)
    except Exception as error:
        c.commit(RUN/'failure.json',dict(error=repr(error),traceback=traceback.format_exc(),verified_saved_steps=total,
            diagnostics_verified_steps=diagnostic,unresolved_reservation=reservation,utc=c.utc(),
            transport_design_sha256=c.sha(PLAN),physical_design_sha256=c.sha(job.DESIGN),
            last_verified_checkpoint_sha256=api.digest(locals().get('cp')),dependent_dispatch_stopped=True))
        raise


if __name__=='__main__':
    {'prepare':prepare,'check':lambda:verify(c.read(PLAN)),'structure':lambda:print(structural_checks(),flush=True),'run':run}[sys.argv[1]]()
