"""Separately versioned same-window recovery after an evidence-access failure.

The administrative plan changes clocks, output paths and renewed shared limits.
The physical design, case IDs, dynamics/checkpoint binding, numerical-gap policy,
integration code and independent physical/whole-path gates remain Stage222's.
No contact optimization prototype is installed by this module.
Frozen v1/v2 attempts remain unchanged. All original paths and hashes remain
mandatory; no physical, accuracy, restart, deadline or resource gate is relaxed.
Transient file-access causes are unproven. No optimization prototype is installed.
"""
from pathlib import Path
from datetime import timedelta
import copy, hashlib, os, shutil, sys, time, traceback
import psutil
import numpy as np
import campaign_common_v1 as c
import continue_baseline_v2 as prior_worker
import finalize_overnight_v1 as prior_finalizer

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'stage222_staging'))
import overnight_campaign_v1 as baseline

api, job = baseline.api, baseline.job
SELF = Path(__file__).resolve()
PLAN = c.DESIGNS/'transport_design_03.json'
RUN = c.RUN/'run_02'
OUT = c.OUT
AUTH = c.AUTH
FINAL = ROOT/'stage222_evaluations/overnight_coarser_20261007/final_disposition_01/results.json'
SEED_NAME = 's2_i0_fibre_f0p125'
SEED_FOLDER = baseline.RUN/SEED_NAME
EXPECTED_PHYSICAL_SHA = 'bad6127d636511ab08dbf9a432cc6919885b5e779d2edc577ce0305a8de1a4fc'
EXPECTED_FINAL_SHA = '6d9587da7052de083c87981778c89c796e20f3320029726e51025888a25bf80c'
EXPECTED_SEED_DIGEST = 'e5dcdd7b03a821f2dea77619faf941231ec5a3fe2c0dd538ff5f42a1c7d8559a'
EXPECTED_LAST_RECEIPT = '17b1544284cb9243cc963165687bc5f31e32943ce805ce2b3b89da1d104a90b9'
PRIOR_SOURCE = SELF.with_name('continue_baseline_v2.py')
PRIOR_PLAN = c.DESIGNS/'transport_design_02.json'
PRIOR_PREPARATION = OUT/'transport_preparation_02/results.json'
RECOVERY_FINAL = OUT/'final_disposition_01/results.json'
RECOVERY_SEED = OUT/'recovery_seed_01'
RECOVERY_SEED_DIGEST = 'b3521bb95f478e0eaf8c80c324d0d142f22cddb13966ea411feccf48da4c83fa'
RECOVERY_LAST_RECEIPT = '187a88dfb3cac85e65c65cf25558ea3f84409aa7aa849c33c197f866def35dfe'
DISPATCH = OUT/'dispatch_decision_02/results.json'
READ_GUARD_CONTROLS = OUT/'recovery_guard_controls_01/results.json'


def verify_frozen_file(path, expected, read_hash, fresh_bound, pause, receipt):
    """Pure read guard; dependencies are explicit for isolated negative controls."""
    failures=[]
    for attempt in range(1,4):
        fresh_bound()
        try:
            actual=read_hash(path)
        except OSError as error:
            failures.append(dict(attempt=attempt,error=repr(error),utc=c.utc()))
            if attempt==3:
                receipt(dict(path=path,expected_sha256=expected,failures=failures,recovered=False,
                             transient_cause_unproven=True))
                raise
            fresh_bound();pause(.25)
            continue
        api.require(actual==expected,'Frozen same-path content mismatch: '+path)
        if failures:
            receipt(dict(path=path,expected_sha256=expected,actual_sha256=actual,failures=failures,
                         recovered=True,successful_attempt=attempt,transient_cause_unproven=True))
        return


def verify_frozen_mapping(mapping):
    """Production always binds the original exact hash and fresh shared clock."""
    def receipt(value):
        c.bound()
        c.commit(OUT/'input_access_events_03'/f'{os.getpid()}_{time.time_ns()}.json',
                 dict(**value,authorization_sha256=c.sha(AUTH)))
    for path,expected in mapping.items():
        verify_frozen_file(path,expected,c.sha,c.bound,time.sleep,receipt)


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


def authenticate_original_stage222():
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
    verify_frozen_mapping(proof['artifacts'])
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
        verify_frozen_mapping(row['artifacts'])
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


def authenticate_inherited():
    """Authenticate569+470 lineage using its sealed full-state reconstruction.

    The retired v2 finalizer independently decoded every accepted raw archive.
    Reuse that sealed proof and rehash every inherited raw/trace/receipt now;
    independently decode the last full logical record again to bind this seed.
    """
    original_before,original_prefix,original=authenticate_original_stage222()
    old_plan=c.read(PRIOR_PLAN)
    verify_frozen_mapping(old_plan['source_files']);verify_frozen_mapping(old_plan['inputs'])
    api.require(old_plan['inherited']==original,'Exact previously frozen569-segment seed')
    proof=sealed(RECOVERY_FINAL)
    api.require(proof['passed'] and proof['final_accounting_authenticated']
        and proof['all_accepted_full_checkpoint_history_ancestry_reconstructed']
        and proof['new_audited_physical_steps']==1304148 and proof['diagnostic_audited_steps']==512
        and proof['new_known_saved_steps_including_diagnostics']==1304660
        and proof['known_unaccepted_saved_steps']==0 and not proof['unresolved'],
        'Sealed independent v2 disposition accepts exactly known prior work')
    verify_frozen_mapping(proof['artifacts'])
    failure=c.read(prior_worker.RUN/'failure.json')
    api.require(failure['transport_design_sha256']==c.sha(PRIOR_PLAN)
        and failure['last_verified_checkpoint_sha256']==RECOVERY_SEED_DIGEST
        and failure['verified_saved_steps']==1304660 and failure['diagnostics_verified_steps']==512,
        'Preserved failed v2 accounting')
    trace=failure['traceback']
    api.require('verify_scientific_inputs' in trace and 'FileNotFoundError' in trace
        and 'conditional_fine.json.seal.json' in trace,'Preserved evidence-access failure, cause unproven')
    root=prior_worker.RUN/SEED_NAME;folders=sorted(root.glob('segment_*'))
    api.require(len(folders)==470 and not (root/'segment_00471').exists(),
        'Exactly470 accepted folders; failed471 never launched')
    physical=physical_design();case=next(row for row in physical['cases'] if row['id']==SEED_NAME)
    expected_contract=job.parent.engine.prior.contracts.expected_contract(case['spec'],
        job.parent.model.binding_for(job.binding(physical,case),True))
    previous=original['inherited_last_receipt_sha256'];checkpoint_sha=api.digest(original_before)
    new_steps=0;stop=original_before['state']['t'];traces=list(original['trace_paths']);inputs=dict(original['inputs'])
    inputs.update({str(p):c.sha(p) for p in (PRIOR_PLAN,PRIOR_SOURCE,PRIOR_PREPARATION,
        PRIOR_PREPARATION.parent/'completion.json',prior_worker.RUN/'failure.json',
        Path(prior_finalizer.__file__).resolve(),RECOVERY_FINAL,RECOVERY_FINAL.parent/'completion.json')})
    for index,folder in enumerate(folders,1):
        c.bound();api.require(folder.name==f'segment_{index:05d}' and folder.is_dir(),'Contiguous470-segment genealogy')
        launch,cap=prior_finalizer.launch_header(prior_worker,old_plan,folder,'production',10000)
        row=sealed(folder/'results.json');verify_frozen_mapping(row['artifacts'])
        api.require(row['transport_design_sha256']==c.sha(PRIOR_PLAN)
            and row['physical_design_sha256']==EXPECTED_PHYSICAL_SHA
            and row['numerical_policy_contract_sha256']==old_plan['numerical_policy_contract_sha256']
            and row['original_binding']==job.binding(physical,case) and row['role']=='production'
            and row['previous_receipt_sha256']==previous
            and row['input_checkpoint_sha256']==launch['input_checkpoint_sha256']==checkpoint_sha,
            'Exact inherited launch/receipt/dynamics ancestry')
        account=c.read(folder/'accounting.json');steps=row['new_saved_steps'];raw=folder/'call.json.xz'
        api.require(account['saved_steps_known'] and account['saved_steps']==steps==row['summary']['steps']
            and 0<steps<=cap and account['role']=='production' and account['raw_sha256']==c.sha(raw)
            and account['rejected']==0 and row['passed'] and row['summary']['passed']
            and row['summary']['start_s']==stop,'Exact accepted inherited health/time/step accounting')
        receipt=folder/'results.json';completion=folder/'completion.json'
        association={**row['artifacts'],str(receipt):c.sha(receipt),str(completion):c.sha(completion)}
        for path,sha in association.items():
            api.require(proof['artifacts'].get(path)==sha,'Independent complete accepted artifact association')
        inputs.update(association);traces.append(str(folder/'trace.npy'))
        previous=c.sha(receipt);checkpoint_sha=row['output_checkpoint_sha256'];stop=row['summary']['stop_s'];new_steps+=steps
    recovery=RECOVERY_FINAL.parent/'recoverable'/SEED_NAME
    for path in (recovery/'checkpoint.json',recovery/'prefix.json'):
        api.require(proof['artifacts'].get(str(path))==c.sha(path),'Sealed independent full recoverable seed artifact')
        inputs[str(path)]=c.sha(path)
    before=c.read(recovery/'checkpoint.json');history=before['state']['history'];reference=c.read(recovery/'prefix.json')
    prefix=job.codec.HistoryState(**reference,history_bytes=job.codec.packed_history(history))
    job.codec.validate_prefix(prefix,EXPECTED_PHYSICAL_SHA)
    api.require(new_steps==1304148 and before['state']['steps']==3526694
        and stop==before['state']['t']==4.385606625455791
        and api.digest(before)==checkpoint_sha==RECOVERY_SEED_DIGEST and previous==RECOVERY_LAST_RECEIPT,
        'Exact inherited470-segment recovered endpoint')
    api.require(before['contract']==expected_contract and api.digest(before['state'])==before['state_sha256']
        ==row['summary']['output_checkpoint_state_sha256'] and len(history)==prefix.history_length
        and hashlib.sha256(job.codec.packed_history(history)).hexdigest()==prefix.history_sha256,
        'Complete recovered dynamics/state/history/prefix contract')
    selected=next(item for item in proof['cases'] if item['case']==SEED_NAME)
    api.require(selected['new_audited_segments']==470 and selected['cumulative_physical_steps']==3526694
        and selected['time_s']==stop and selected['last_sealed_receipt_sha256']==previous,
        'Independent disposition matches complete recovered seed')
    raw=root/'segment_00470/call.json.xz'
    wrapper=baseline.source.stack.storage.fresh_reader(raw,EXPECTED_PHYSICAL_SHA)
    api.require(wrapper['evidence_encoding']==physical['codec_schema'],'Original exact lossless evidence schema')
    env=wrapper['packed_envelope'];parent_ref=env['history']['prefix']
    parent_history=history[:parent_ref['history_length']]
    parent_prefix=job.codec.HistoryState(**parent_ref,history_bytes=job.codec.packed_history(parent_history))
    job.codec.validate_prefix(parent_prefix,EXPECTED_PHYSICAL_SHA)
    decoded,independent_prefix=job.codec.read_record(raw,EXPECTED_PHYSICAL_SHA,parent_prefix)
    api.require(api.digest(decoded['result']['checkpoint'])==api.digest(before)
        and independent_prefix.reference()==reference and decoded['spec']==case['spec']
        and decoded['numerical_policy_contract_sha256']==c.sha(job.WORK)
        and decoded['effective_binding']==job.parent.model.binding_for(job.binding(physical,case),True)
        and decoded['input_checkpoint_sha256']==row['input_checkpoint_sha256'],
        'Independent last logical raw/checkpoint/prefix/physical binding identity')
    recovered=dict(passed=True,inherited_segments=1039,inherited_physical_steps=3526694,
        inherited_stop_s=stop,input_checkpoint_sha256=api.digest(before),inherited_last_receipt_sha256=previous,
        inherited_prefix=reference,trace_paths=traces,inputs=inputs,original_physical_audits_reused=True,
        original_physical_audits_rerun=False,original_stage222_segments=569,prior_stage229_segments=470,
        prior_stage229_saved_steps=1304660,prior_stage229_diagnostic_steps=512,prior_stage229_physical_steps=1304148,
        failed_pre_dispatch_reservation_resolved_to_zero=True,failed_attempt_preserved=True,
        transient_file_access_cause_unproven=True,independent_prior_disposition_sha256=c.sha(RECOVERY_FINAL),
        inherited_complete_raw_reconstruction_reused=True,independent_full_logical_tail_records=1,
        old_complete_checkpoint_reconstruction_proof_sha256=c.sha(FINAL))
    if not (RECOVERY_SEED/'completion.json').exists():
        c.commit(RECOVERY_SEED/'checkpoint.json',before);c.commit(RECOVERY_SEED/'prefix.json',reference)
        c.commit(RECOVERY_SEED/'history.json',history)
        c.commit(RECOVERY_SEED/'results.json',dict(**recovered,new_trajectory_steps=0,numerical_calls=0,
            artifacts={str(p):c.sha(p) for p in RECOVERY_SEED.glob('*.json')}))
        c.commit(RECOVERY_SEED/'completion.json',dict(passed=True,results_sha256=c.sha(RECOVERY_SEED/'results.json')))
    else:
        previous_proof=sealed(RECOVERY_SEED/'results.json');verify_frozen_mapping(previous_proof['artifacts'])
        api.require(previous_proof['input_checkpoint_sha256']==api.digest(before)
            and previous_proof['inputs']==inputs,'Existing create-only recovery proof unchanged')
    recovered['inputs'].update({str(p):c.sha(p) for p in RECOVERY_SEED.glob('*.json')})
    return before,prefix,recovered


def prepare():
    a = c.bound(); c.environment(); verify_frozen_mapping(a['sources']); verify_frozen_mapping(a['inputs'])
    checks = structural_checks()
    controls=sealed(READ_GUARD_CONTROLS)
    api.require(controls['passed'] and controls['numerical_calls']==0 and controls['controls_passed']==4
        and controls['frozen_maps_unchanged'] and controls['all271_original_physical_inputs_passed'],
        'Meaningful same-path retry/content/deadline negative controls')
    verify_frozen_mapping(controls['sources']);verify_frozen_mapping(controls['inputs'])
    before, prefix, inherited = authenticate_inherited()
    physical = physical_design()
    b = a['independent_baseline']
    api.require(b['authorized'] and b['factor'] == .125 and not a['candidate_production_authorized'],
                'Original baseline alone is authorized')
    api.require([row['id'] for row in physical['cases']] == b['case_order'], 'Original case order')
    plan = dict(stage='Stage229 separately frozen original baseline recovery v3', utc=c.utc(),
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
        prior_shared_saved_steps=1304660,prior_shared_diagnostic_saved_steps=512,
        inherited=inherited, no_force_structural_checks=checks,
        source_files={**physical['sources'], str(SELF): c.sha(SELF), str(Path(c.__file__).resolve()): c.sha(c.__file__),
                      str(Path(prior_finalizer.__file__).resolve()):c.sha(prior_finalizer.__file__),
                      str(PRIOR_SOURCE):c.sha(PRIOR_SOURCE)},
        physical_inputs={**physical['inputs'], str(job.DESIGN):c.sha(job.DESIGN), str(job.WORK):c.sha(job.WORK)},
        inputs={str(AUTH): c.sha(AUTH), **physical['inputs'], str(job.DESIGN):c.sha(job.DESIGN), str(job.WORK):c.sha(job.WORK),
                **inherited['inputs'], str(PRIOR_SOURCE):c.sha(PRIOR_SOURCE), str(PRIOR_PLAN):c.sha(PRIOR_PLAN),
                str(PRIOR_PREPARATION):c.sha(PRIOR_PREPARATION),
                str(PRIOR_PREPARATION.parent/'completion.json'):c.sha(PRIOR_PREPARATION.parent/'completion.json'),
                str(READ_GUARD_CONTROLS):c.sha(READ_GUARD_CONTROLS),
                str(READ_GUARD_CONTROLS.parent/'completion.json'):c.sha(READ_GUARD_CONTROLS.parent/'completion.json'),
                str(baseline.PREREQUISITE): c.sha(baseline.PREREQUISITE),
                str(baseline.PREREQUISITE.parent/'completion.json'): c.sha(baseline.PREREQUISITE.parent/'completion.json')},
        claim=a['claim_boundary'], original_stage222_remains_closed=True,
        prior_failed_v2_preserved=True,prior_frozen_v1_preparation_preserved_unexecuted=True,
        prior_worker_source_sha256=c.sha(PRIOR_SOURCE),prior_transport_design_sha256=c.sha(PRIOR_PLAN),
        strengthened_input_guard='All same-path original physical inputs and frozen physical-design/policy hashes checked before every segment, case and whole-path comparison; only bounded OSError read retry, content mismatch never retried.',
        failure_rule=a['failure_rule'])
    plan['binding'] = c.digest(plan)
    c.commit(PLAN, plan)
    verify(plan)
    destination = OUT/'transport_preparation_03'
    c.commit(destination/'results.json', dict(passed=True, numerical_calls=0, new_trajectory_steps=0,
        transport_design_sha256=c.sha(PLAN), authorization_sha256=c.sha(AUTH),
        structural_checks=checks, inherited_summary={k:v for k,v in inherited.items() if k not in ('inputs','trace_paths')},
        artifacts={str(PLAN):c.sha(PLAN)}))
    c.commit(destination/'completion.json', dict(passed=True, results_sha256=c.sha(destination/'results.json')))
    print('STAGE229_TRANSPORT_PREPARED', c.sha(PLAN), flush=True)


def verify(plan):
    a = c.bound(); c.environment()
    verify_frozen_mapping(a['sources']); verify_frozen_mapping(a['inputs'])
    api.require(plan['binding'] == c.digest({k:v for k,v in plan.items() if k != 'binding'}), 'Immutable transport design')
    verify_frozen_mapping(plan['source_files']); verify_frozen_mapping(plan['inputs'])
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
    api.require(plan['prior_shared_saved_steps']==1304660 and plan['prior_shared_diagnostic_saved_steps']==512
        and plan['inherited']['inherited_segments']==1039 and plan['inherited']['inherited_physical_steps']==3526694,
        'Prior failed attempt remains inside shared renewed limits')
    api.require(plan['physical_design_sha256'] == c.sha(job.DESIGN) == EXPECTED_PHYSICAL_SHA
                and plan['numerical_policy_contract_sha256'] == c.sha(job.WORK), 'Original scientific identities')
    physical = physical_design()
    expected_inputs = {**physical['inputs'],str(job.DESIGN):plan['physical_design_sha256'],
                       str(job.WORK):plan['numerical_policy_contract_sha256']}
    api.require(plan['physical_inputs'] == expected_inputs
                and all(plan['inputs'][path] == sha for path,sha in expected_inputs.items()),
                'Complete original physical-input bindings, including design and policy')
    baseline.clone_check()
    return plan


def verify_scientific_inputs(plan):
    """Fresh immutable scientific identities and relevant inputs at every dispatch."""
    c.bound()
    verify_frozen_mapping(plan['source_files'])
    verify_frozen_mapping(plan['physical_inputs'])
    api.require(plan['authorization_sha256'] == c.sha(AUTH), 'Frozen shared authority before dispatch')
    api.require(plan['physical_design_sha256'] == c.sha(job.DESIGN) == EXPECTED_PHYSICAL_SHA,
                'Live original physical design cannot be relabelled')
    api.require(plan['numerical_policy_contract_sha256'] == c.sha(job.WORK),
                'Live original numerical-gap policy cannot be relabelled')
    baseline.clone_check()


def dispatch_allowed(plan):
    verify_scientific_inputs(plan)
    c.bound();decision=sealed(DISPATCH);verify_frozen_mapping(decision['inputs'])
    api.require(decision['baseline_allowed'] is True and decision['candidate_production_authorized'] is False,
        'Specific separately sealed original-baseline recovery dispatch')
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
    verify_scientific_inputs(plan)
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
    verify_scientific_inputs(plan)
    verify_frozen_mapping(plan['inherited']['inputs'])
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
        receipt = sealed(folder/'results.json'); verify_frozen_mapping(receipt['artifacts'])
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
        authorization_sha256=c.sha(AUTH),dispatch_decision_sha256=c.sha(DISPATCH),
        prior_shared_saved_steps=plan['prior_shared_saved_steps'],inherited_cumulative_production_calls=1039))
    total=plan['prior_shared_saved_steps'];diagnostic=plan['prior_shared_diagnostic_saved_steps']
    cases = []
    reservation = None
    reason = 'work_window'
    try:
        for case in d['cases']:
            verify_scientific_inputs(plan)
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
            current_run_saved_steps_including_diagnostics=total-plan['prior_shared_saved_steps'],
            current_run_physical_steps=(total-diagnostic)-(plan['prior_shared_saved_steps']-plan['prior_shared_diagnostic_saved_steps']),
            prior_shared_saved_steps=plan['prior_shared_saved_steps'],
            cases=cases,utc=c.utc(),transport_design_sha256=c.sha(PLAN),physical_design_sha256=c.sha(job.DESIGN),
            authorization_sha256=c.sha(AUTH),whole_overnight_success=reason=='all_four_numerical_cases_complete',
            original_stage222_remains_closed=True,candidate_production_authorized=False,claim=plan['claim'])
        c.commit(RUN/'results.json',result);c.commit(RUN/'completion.json',dict(results_sha256=c.sha(RUN/'results.json'),finished=True))
        print('STAGE229_TRANSPORT_FINISHED',reason,total,flush=True)
    except Exception as error:
        c.commit(RUN/'failure.json',dict(error=repr(error),traceback=traceback.format_exc(),verified_saved_steps=total,
            diagnostics_verified_steps=diagnostic,unresolved_reservation=reservation,utc=c.utc(),
            current_run_verified_saved_steps=total-plan['prior_shared_saved_steps'],prior_shared_saved_steps=plan['prior_shared_saved_steps'],
            transport_design_sha256=c.sha(PLAN),physical_design_sha256=c.sha(job.DESIGN),
            last_verified_checkpoint_sha256=api.digest(locals().get('cp')),dependent_dispatch_stopped=True))
        raise


if __name__=='__main__':
    {'prepare':prepare,'check':lambda:verify(c.read(PLAN)),'structure':lambda:print(structural_checks(),flush=True),'run':run}[sys.argv[1]]()
