"""One original factor-0.125 fibre tail; no successor case or solver promotion.

Stage229 is closed. Required transaction and comparison functions are copied
into private globals with their EXACT original code objects. Only a fresh
administrative clock, output namespace and smaller execution caps are supplied.
Neither original module globals nor the original physical binding are mutated.
"""
from pathlib import Path
from datetime import datetime, timezone, timedelta
from types import FunctionType
import copy, os, shutil, sys, traceback
import psutil
import numpy as np
import tail_common_v1 as c

ROOT = c.ROOT
sys.path.insert(0, str(ROOT/'stage229_staging'))
import continue_baseline_v3 as prior

api, job, baseline = prior.api, prior.job, prior.baseline
NAME = 's2_i0_fibre_f0p125'
OLD = ROOT/'stage229_evaluations/overnight_20261007'
OLD_PLAN = ROOT/'stage229_designs/overnight_20261007/transport_design_03.json'
FINAL = OLD/'final_disposition_02/results.json'
RETIREMENT = OLD/'recovery_retirement_01/results.json'
ROOT_RECEIPT = OLD/'recovery_final_receipt_01/results.json'
CP_FILE = FINAL.parent/'recoverable'/NAME/'checkpoint.json'
PREFIX_FILE = CP_FILE.with_name('prefix.json')
EXPECTED = {
    str(FINAL): '1ecf9b27eccd3f3e1e05f594c33b489501f2c4d7b892f7becc5f9d656b4b97ec',
    str(RETIREMENT): '6043412221aac1d41219e8f7d7e2ac1b4f131318c15b7f4f10d37ce1b0a29a69',
    str(ROOT_RECEIPT): '990acaec37798fa33636a0961be1ca7beb95418cb403a5929913c479514311da',
    str(OLD_PLAN): 'ad7ef2ba4400f62f928f8c440e93db1169a75a0324dfba2117f04ce01ac82736',
}
CP_DIGEST = '322fa2bc4b312fdb6fbe8df201b0971a5d66716291c53de84827b3bc1a062c5f'
LAST_RECEIPT = '67fed3d4231473bf17688a35c2e92e561c1c10e470aa78c7d10684e14a3f4506'
CLONED = ('verify_frozen_file', 'verify_frozen_mapping', 'physical_design',
          'verify_scientific_inputs', 'segment', 'qualify', 'compare')
PRIVATE = dict(vars(prior), c=c, PLAN=c.PLAN, RUN=c.RUN, OUT=c.OUT, AUTH=c.AUTH)
for name in CLONED:
    fn = getattr(prior, name)
    PRIVATE[name] = FunctionType(fn.__code__, PRIVATE, fn.__name__, fn.__defaults__, fn.__closure__)

def clone_checks():
    baseline.clone_check()
    for name in CLONED:
        fn = PRIVATE[name]
        api.require(fn.__code__ is getattr(prior, name).__code__ and fn.__globals__ is PRIVATE,
                    'Exact private administrative adapter: '+name)
    api.require(prior.c is not c and prior.PLAN == OLD_PLAN and prior.RUN != c.RUN,
                'Frozen prior module globals remain unchanged')
    api.require(job.DESIGN == baseline.PLAN and c.sha(job.DESIGN) == prior.EXPECTED_PHYSICAL_SHA,
                'Original physical design binding retained')
    return dict(passed=True, original_function_code_objects_retained=list(CLONED),
                original_module_globals_unchanged=True, new_trajectory_steps=0, numerical_calls=0)

def seed(plan=None):
    """Reuse sealed full ancestry; independently decode the final logical record."""
    c.verify(EXPECTED)
    final, retirement, root = c.sealed(FINAL), c.sealed(RETIREMENT), c.sealed(ROOT_RECEIPT)
    api.require(final['passed'] and final['final_accounting_authenticated']
                and final['all_accepted_full_checkpoint_history_ancestry_reconstructed']
                and final['known_unaccepted_saved_steps'] == final['unknown_saved_steps_reservation_upper_bound'] == 0
                and final['unresolved'] == [], 'Complete sealed initial accounting without unknown work')
    api.require(retirement['passed'] and root['passed']
                and retirement['all_exact_launch_identities_retired'] and root['all_exact_launch_identities_retired']
                and root['existing_heartbeat_status'] == 'PAUSED', 'Closed original campaign and retired identities')
    c.verify(root['artifacts'])
    selected = next(row for row in final['cases'] if row['case'] == NAME)
    api.require(selected['cumulative_physical_steps'] == 3760617 and selected['new_audited_segments'] == 556
                and selected['time_s'] == 4.676500663515844 and selected['unresolved_attempts'] == 0
                and selected['last_sealed_receipt_sha256'] == LAST_RECEIPT, 'Exact final seed ledger')
    c.verify({str(p): final['artifacts'][str(p)] for p in (CP_FILE, PREFIX_FILE)})
    before, reference = api.read(CP_FILE), c.read(PREFIX_FILE)
    api.require(api.digest(before) == CP_DIGEST and api.digest(before['state']) == before['state_sha256'],
                'Original full checkpoint and state digest convention')
    physical = PRIVATE['physical_design']()
    case = next(row for row in physical['cases'] if row['id'] == NAME)
    binding = job.parent.model.binding_for(job.binding(physical, case), True)
    api.require(before['contract'] == job.parent.engine.prior.contracts.expected_contract(case['spec'], binding),
                'Original full checkpoint contract')
    history = before['state']['history']
    prefix = job.codec.HistoryState(**reference, history_bytes=job.codec.packed_history(history))
    job.codec.validate_prefix(prefix, prior.EXPECTED_PHYSICAL_SHA)
    raw = Path(reference['path'])
    folder = Path(selected['last_sealed_folder'])
    receipt = c.sealed(folder/'results.json')
    c.verify(receipt['artifacts'])
    api.require(c.sha(folder/'results.json') == LAST_RECEIPT, 'Exact final accepted receipt')
    wrapper = baseline.source.stack.storage.fresh_reader(raw, prior.EXPECTED_PHYSICAL_SHA)
    parent = wrapper['packed_envelope']['history']['prefix']
    parent_prefix = job.codec.HistoryState(**parent, history_bytes=job.codec.packed_history(history[:parent['history_length']]))
    job.codec.validate_prefix(parent_prefix, prior.EXPECTED_PHYSICAL_SHA)
    decoded, checked = job.codec.read_record(raw, prior.EXPECTED_PHYSICAL_SHA, parent_prefix)
    api.require(api.digest(decoded['result']['checkpoint']) == CP_DIGEST and checked.reference() == reference
                and decoded['spec'] == case['spec'] and decoded['effective_binding'] == binding
                and decoded['numerical_policy_contract_sha256'] == c.sha(job.WORK)
                and decoded['input_checkpoint_sha256'] == receipt['input_checkpoint_sha256'],
                'Independent terminal raw/full checkpoint/history association')
    oldplan = c.read(OLD_PLAN)
    traces = list(oldplan['inherited']['trace_paths'])
    run_result = c.sealed(ROOT/'stage229_runs/overnight_20261007/run_02'/NAME/'results.json')
    api.require(len(traces) == 1039 and len(run_result['entries']) == 86, 'Complete ordered inherited genealogy')
    traces += [str(ROOT/'stage229_runs/overnight_20261007/run_02'/NAME/f"segment_{entry['segment']:05d}"/'trace.npy')
               for entry in run_result['entries']]
    inputs = {**oldplan['inputs'], **final['artifacts'], **EXPECTED,
              str(CP_FILE): c.sha(CP_FILE), str(PREFIX_FILE): c.sha(PREFIX_FILE)}
    preflight_file=c.OUT/'preflight_02/results.json'
    inputs.update({str(preflight_file):c.sha(preflight_file),str(preflight_file.parent/'completion.json'):c.sha(preflight_file.parent/'completion.json')})
    for path in traces:
        api.require(path in inputs, 'Every original production trace bound')
    inherited = dict(passed=True, inherited_segments=1125, inherited_physical_steps=3760617,
                     inherited_stop_s=before['state']['t'], input_checkpoint_sha256=CP_DIGEST,
                     inherited_last_receipt_sha256=LAST_RECEIPT, trace_paths=traces,
                     inherited_prefix=reference, inputs=inputs,
                     inherited_full_raw_reconstruction_reused=True, independent_last_raw_record_reconstructed=True,
                     prior_physical_audits_reused=True, original_campaigns_remain_closed=True)
    if plan is not None:
        api.require(inherited == plan['inherited'], 'Frozen original seed and full ancestry unchanged')
    return physical, case, before, prefix, inherited

def prepare():
    c.environment()
    api.require(not c.AUTH.exists() and not c.PLAN.exists() and not c.RUN.exists(), 'Fresh bounded stage only')
    preflight_file=c.OUT/'preflight_02/results.json'
    preflight=c.sealed(preflight_file)
    api.require(preflight['passed'] and preflight['numerical_calls']==preflight['new_trajectory_steps']==preflight['process_actions']==0,
                'Pure administrative controls before authorization')
    for path,expected in preflight['sources'].items():
        api.require(c.sha(path)==expected, 'Unchanged reviewed fresh administrative source')
    start = datetime.now(timezone.utc)
    end = start + timedelta(minutes=30)
    c.commit(c.AUTH, dict(stage='Stage230 single original fibre terminal verification',
        human_authorization='Fresh human next instruction on 8 October after fully closed Stage229; next minimal numerical gate only, no new overnight or successor campaign.',
        start_utc=start.isoformat(), end_utc=end.isoformat(), simulation_cutoff_utc=(end-timedelta(minutes=5)).isoformat(),
        maximum_wall_seconds=1800, maximum_saved_steps_including_diagnostics=50000,
        maximum_new_production_calls=5, maximum_cumulative_physical_steps_per_case=5000000,
        maximum_cumulative_calls_per_case=1500, step_cap_per_call=10000, qualification_steps_per_case=512,
        threads=1, workers=1, maximum_unverified_records=1, logical_cpu=14,
        minimum_free_disk_bytes=20*1024**3, only_case=NAME, successor_dispatch_authorized=False,
        candidate_production_authorized=False, physics_changes=[], accuracy_gate_changes=[],
        prior_campaigns_remain_closed=True, sources={str(p):c.sha(p) for p in Path(__file__).parent.glob('*.py')},
        master_plan_sha256_at_authorization=c.sha(ROOT/'MASTER_PLAN.md')))
    controls = clone_checks()
    oldplan = c.read(OLD_PLAN)
    c.verify(oldplan['source_files'])
    physical, case, before, prefix, inherited = seed()
    c.verify(inherited['inputs'])
    baseline.verify(physical)
    baseline.old.verify(api.read(baseline.old.DESIGN))
    baseline.source.bindings()
    auth = c.bound()
    physical_inputs = {**physical['inputs'], str(job.DESIGN):c.sha(job.DESIGN), str(job.WORK):c.sha(job.WORK)}
    plan = dict(stage=auth['stage'], start_utc=auth['start_utc'], authorized_end_utc=auth['end_utc'],
        simulation_cutoff_utc=auth['simulation_cutoff_utc'], authorization_sha256=c.sha(c.AUTH),
        only_case=NAME, original_physical_design_path=str(job.DESIGN), physical_design_sha256=c.sha(job.DESIGN),
        numerical_policy_contract_sha256=c.sha(job.WORK), physical_inputs=physical_inputs,
        source_files={**oldplan['source_files'],**auth['sources']}, inputs=inherited['inputs'], inherited=inherited,
        candidate_production_authorized=False, successor_dispatch_authorized=False,
        physical_changes=[], numerical_changes=[], accuracy_gate_changes=[],
        claim='One labelled sample0 fibre at one packing/flow; original full-path temporal accuracy verification only. No population shape/flow trend, spatial convergence or experimental validation.',
        **{k:auth[k] for k in ('maximum_saved_steps_including_diagnostics','maximum_new_production_calls',
            'maximum_cumulative_physical_steps_per_case','maximum_cumulative_calls_per_case','step_cap_per_call',
            'qualification_steps_per_case','minimum_free_disk_bytes','workers','threads','logical_cpu','maximum_unverified_records')})
    plan['binding'] = c.digest(plan)
    c.commit(c.PLAN, plan)
    c.commit(c.OUT/'preparation_01/results.json',dict(passed=True, numerical_calls=0, new_trajectory_steps=0,
        unchanged_code_controls=controls, inherited_full_ancestry_authenticated=True,
        independently_reconstructed_last_raw=True, source_files=plan['source_files'],
        authorization_sha256=c.sha(c.AUTH),design_sha256=c.sha(c.PLAN), original_inputs_verified=len(plan['inputs']),
        original_seed_sha256=CP_DIGEST, artifacts={str(c.AUTH):c.sha(c.AUTH),str(c.PLAN):c.sha(c.PLAN)}))
    c.commit(c.OUT/'preparation_01/completion.json',dict(passed=True,results_sha256=c.sha(c.OUT/'preparation_01/results.json')))
    print('STAGE230_PREPARED',auth['end_utc'],len(plan['inputs']),flush=True)

def verify():
    auth = c.bound()
    c.environment(); clone_checks()
    plan = c.read(c.PLAN)
    api.require(plan['binding'] == c.digest({k:v for k,v in plan.items() if k != 'binding'}), 'Frozen new design')
    api.require(plan['authorization_sha256'] == c.sha(c.AUTH), 'New bounded authority')
    api.require(plan['start_utc'] == auth['start_utc'] and plan['authorized_end_utc'] == auth['end_utc']
                and plan['simulation_cutoff_utc'] == auth['simulation_cutoff_utc'], 'Exact new clocks')
    for key in ('maximum_saved_steps_including_diagnostics','maximum_new_production_calls',
                'maximum_cumulative_physical_steps_per_case','maximum_cumulative_calls_per_case','step_cap_per_call',
                'qualification_steps_per_case','minimum_free_disk_bytes','workers','threads','logical_cpu','maximum_unverified_records'):
        api.require(plan[key] == auth[key], 'Immutable bounded limit '+key)
    api.require(plan['only_case'] == NAME and not plan['successor_dispatch_authorized']
                and not plan['candidate_production_authorized'] and plan['physical_changes'] == plan['numerical_changes'] == plan['accuracy_gate_changes'] == [],
                'Only original single-case verification is authorized')
    preparation = c.sealed(c.OUT/'preparation_01/results.json')
    api.require(preparation['passed'] and preparation['design_sha256'] == c.sha(c.PLAN), 'Sealed original preparation')
    c.verify(plan['source_files']); c.verify(plan['inputs']); c.verify(plan['physical_inputs'])
    return plan

def dispatch_stop(plan, used, needed):
    c.bound()
    if job.utc() >= job.policy.utc(plan['simulation_cutoff_utc'])-timedelta(seconds=120):
        return 'simulation_cutoff'
    if used+needed > plan['maximum_saved_steps_including_diagnostics']:
        return 'saved_step_ceiling'
    if shutil.disk_usage(ROOT).free <= plan['minimum_free_disk_bytes']+4*job.codec.base.MAX_COMPRESSED:
        return 'disk_reserve'
    return None

def run():
    plan = verify()
    physical, case, before, prefix, inherited = seed(plan)
    process = psutil.Process(); process.cpu_affinity([plan['logical_cpu']])
    c.RUN.mkdir(parents=True,exist_ok=False)
    c.commit(c.RUN/'launch.json',dict(pid=process.pid,created=process.create_time(),argv=process.cmdline(),utc=c.utc(),
        affinity=process.cpu_affinity(),design_sha256=c.sha(c.PLAN),authorization_sha256=c.sha(c.AUTH)))
    geometry = baseline.geometry_for(case)
    cp, current_prefix, previous = copy.deepcopy(before), prefix, LAST_RECEIPT
    used = diagnostic = 0; entries=[]; reservation=None; rec=None; reason='call_limit'
    try:
        api.require(dispatch_stop(plan,0,512) is None, 'Resources for complete fresh qualification')
        reservation=dict(role='restart_diagnostic',maximum_saved_steps=512)
        diagnostic=PRIVATE['qualify'](plan,physical,case,geometry,cp,current_prefix,previous)
        used += diagnostic; reservation=None
        print('STAGE230_RESTART_VERIFIED',diagnostic,flush=True)
        for index in range(1,plan['maximum_new_production_calls']+1):
            reason=dispatch_stop(plan,used,1)
            if reason: break
            if 1125+index > plan['maximum_cumulative_calls_per_case']:
                reason='cumulative_call_limit';break
            remaining=min(plan['maximum_saved_steps_including_diagnostics']-used,
                          plan['maximum_cumulative_physical_steps_per_case']-cp['state']['steps'])
            if remaining <= 0:
                reason='case_step_ceiling';break
            cap=min(plan['step_cap_per_call'],remaining)
            reservation=dict(role='production',segment=index,maximum_saved_steps=cap,input_checkpoint_sha256=api.digest(cp))
            rec,current_prefix,row=PRIVATE['segment'](plan,physical,case,geometry,cp,current_prefix,
                c.RUN/NAME/f'segment_{index:05d}',cap,previous,'production')
            cp=rec['result']['checkpoint'];used+=row['new_saved_steps'];previous=c.sha(c.RUN/NAME/f'segment_{index:05d}/results.json')
            entries.append(dict(segment=index,cumulative_case_call=1125+index,new_saved_steps=row['new_saved_steps'],
                results_sha256=previous,stop_s=cp['state']['t']))
            reservation=None
            print('STAGE230_SEGMENT_VERIFIED',index,row['new_saved_steps'],cp['state']['t'],rec['result']['status'],flush=True)
            if rec['result']['status'] in job.policy.COMPLETE:
                reason='observation_complete';break
        else:
            reason='call_limit'
        folder=c.RUN/NAME
        case_result=dict(case=NAME,complete_observation=reason=='observation_complete',reason=reason,
            inherited_physical_steps=3760617,inherited_calls=1125,new_physical_steps=used-diagnostic,
            cumulative_physical_steps=cp['state']['steps'],cumulative_calls=1125+len(entries),diagnostic_saved_steps=diagnostic,
            entries=entries,final_checkpoint_sha256=api.digest(cp),time_s=cp['state']['t'],horizon_s=case['spec']['horizon_s'],
            final_status='unrun_continuation' if rec is None else rec['result']['status'],original_campaigns_remain_closed=True)
        c.commit(folder/'checkpoint.json',cp);c.commit(folder/'prefix.json',current_prefix.reference())
        c.commit(folder/'results.json',case_result)
        c.commit(folder/'completion.json',dict(results_sha256=c.sha(folder/'results.json'),complete_observation=case_result['complete_observation']))
        comparison=None
        if case_result['complete_observation']:
            comparison=PRIVATE['compare'](plan,physical,case,rec['result'],entries,inherited['trace_paths'])
            reason='full_path_accuracy_passed' if comparison['passed'] else 'full_path_accuracy_failed'
            print('STAGE230_FULL_PATH',reason,flush=True)
        result=dict(finished=True,reason=reason,passed=reason=='full_path_accuracy_passed',case=case_result,
            saved_steps_including_diagnostics=used,accepted_physical_steps=used-diagnostic,discarded_diagnostic_steps=diagnostic,
            known_unaccepted_saved_steps=0,unknown_saved_steps_reservation_upper_bound=0,
            comparison_sha256=None if comparison is None else c.sha(c.OUT/NAME/'comparison_01/results.json'),
            utc=c.utc(),design_sha256=c.sha(c.PLAN),authorization_sha256=c.sha(c.AUTH),
            successor_cases_started=0,contact_prototype_promoted=False,claim=plan['claim'])
        c.commit(c.RUN/'results.json',result);c.commit(c.RUN/'completion.json',dict(results_sha256=c.sha(c.RUN/'results.json'),finished=True))
    except Exception as error:
        c.commit(c.RUN/'failure.json',dict(error=repr(error),traceback=traceback.format_exc(),verified_saved_steps=used,
            verified_diagnostic_steps=diagnostic,unresolved_reservation=reservation,last_verified_checkpoint_sha256=api.digest(cp),
            accepted_entries=entries,utc=c.utc(),design_sha256=c.sha(c.PLAN),dependent_dispatch_stopped=True))
        raise

def final_authentication(exit_record):
    """Independent reconstruction of every NEW archive; reuse sealed historical audits."""
    plan=verify();physical,case,before,prefix,inherited=seed(plan)
    api.require(exit_record['retired_exact_identity'] and exit_record['returncode']==0,
                'Exact worker retirement before final successful accounting')
    result=c.sealed(c.RUN/'results.json');case_result=result['case']
    cp=copy.deepcopy(before);chain=prefix;previous=LAST_RECEIPT
    reconstructed={};known=0
    qualification=c.RUN/NAME/'qualification_01'
    for label,parent in [('serial_01',before),('split_a_01',before),('split_b_01',None)]:
        folder=qualification/label;receipt=c.sealed(folder/'results.json');c.verify(receipt['artifacts'])
        parent_cp=before if parent is not None else reconstructed['split_a_01'][0]['result']['checkpoint']
        parent_prefix=prefix if parent is not None else reconstructed['split_a_01'][1]
        rec,checked=job.codec.read_record(folder/'call.json.xz',prior.EXPECTED_PHYSICAL_SHA,parent_prefix)
        record_checks(rec,physical,case,parent_cp)
        expected_previous=LAST_RECEIPT if parent is not None else c.sha(qualification/'split_a_01/results.json')
        api.require(receipt['input_checkpoint_sha256']==api.digest(parent_cp)
                    and receipt['output_checkpoint_sha256']==api.digest(rec['result']['checkpoint'])
                    and receipt['previous_receipt_sha256']==expected_previous
                    and receipt['new_saved_steps']==len(rec['rows'])
                    and receipt['summary']['passed'] and receipt['role']=='restart_diagnostic', 'Diagnostic raw/receipt genealogy')
        reconstructed[label]=(rec,checked);known+=len(rec['rows'])
    serial=reconstructed['serial_01'][0];a=reconstructed['split_a_01'][0];b=reconstructed['split_b_01'][0]
    api.require(len(serial['rows'])==256 and len(a['rows'])==len(b['rows'])==128
                and serial['rows']==a['rows']+b['rows']
                and api.digest(serial['result']['checkpoint'])==api.digest(b['result']['checkpoint']), 'Independent exact fresh512 diagnostic qualification')
    q=c.sealed(qualification/'results.json');c.verify(q['artifacts'])
    api.require(q['passed'] and q['production_seed_sha256']==CP_DIGEST
                and q['diagnostic_saved_steps']==512 and not q['diagnostic_trajectory_promoted'], 'Sealed discarded exact restart evidence')
    for index,entry in enumerate(case_result['entries'],1):
        folder=c.RUN/NAME/f'segment_{index:05d}';receipt=c.sealed(folder/'results.json');c.verify(receipt['artifacts'])
        api.require(entry['segment']==index and entry['results_sha256']==c.sha(folder/'results.json')
                    and receipt['previous_receipt_sha256']==previous and receipt['input_checkpoint_sha256']==api.digest(cp)
                    and receipt['summary']['passed'] and receipt['role']=='production', 'Contiguous original independent physical receipt chain')
        rec,chain=job.codec.read_record(folder/'call.json.xz',prior.EXPECTED_PHYSICAL_SHA,chain)
        record_checks(rec,physical,case,cp)
        next_cp=rec['result']['checkpoint']
        expected_trace=np.asarray([[r['time_s'],*r['position_m'],*r['orientation'],*r['velocity_generalized']] for r in rec['rows']],dtype=np.float64)
        actual_trace=np.load(folder/'trace.npy',allow_pickle=False)
        api.require(np.array_equal(actual_trace,expected_trace) and api.digest(next_cp)==receipt['output_checkpoint_sha256']
                    and next_cp['state']['steps']-cp['state']['steps']==entry['new_saved_steps']==len(rec['rows']),
                    'Lossless complete new raw/trace/state reconstruction')
        cp=next_cp;previous=c.sha(folder/'results.json');known+=len(rec['rows'])
    api.require(api.digest(cp)==case_result['final_checkpoint_sha256']==api.digest(c.read(c.RUN/NAME/'checkpoint.json'))
                and chain.reference()==c.read(c.RUN/NAME/'prefix.json')
                and known==result['saved_steps_including_diagnostics']
                and cp['state']['steps']-3760617==result['accepted_physical_steps'], 'Full final checkpoint/history and truthful saved-step accounting')
    comparison=None
    if result['comparison_sha256'] is not None:
        destination=c.OUT/NAME/'comparison_01/results.json';comparison=c.sealed(destination)
        c.verify(comparison['path_artifacts'])
        api.require(c.sha(destination)==result['comparison_sha256']
                    and comparison['full_original_start_to_terminal_path']
                    and comparison['inherited_segments']==1125 and comparison['new_segments']==len(case_result['entries'])
                    and comparison['passed']==result['passed'], 'Original whole-path gates remain explicit')
    c.commit(c.OUT/'final_disposition_01/recoverable/checkpoint.json',cp)
    c.commit(c.OUT/'final_disposition_01/recoverable/prefix.json',chain.reference())
    artifacts={str(p):c.sha(p) for p in c.RUN.rglob('*') if p.is_file() and p.suffix not in ('.log',)}
    artifacts.update({str(p):c.sha(p) for p in (c.PLAN,c.AUTH)})
    if comparison is not None:
        artifacts.update({str(p):c.sha(p) for p in (destination,destination.parent/'completion.json')})
    artifacts.update({str(p):c.sha(p) for p in (c.OUT/'final_disposition_01/recoverable').glob('*.json')})
    final=dict(passed=True,scientific_full_path_passed=result['passed'],case=case_result,
        accepted_physical_steps=result['accepted_physical_steps'],discarded_diagnostic_steps=512,
        new_known_saved_steps_including_diagnostics=known,known_unaccepted_saved_steps=0,
        unknown_saved_steps_reservation_upper_bound=0,unresolved=[],new_raw_records_reconstructed=3+len(case_result['entries']),
        inherited_full_ancestry_reused=True,original_independent_physical_audits_reused=True,
        original_full_path_comparison_sha256=result['comparison_sha256'],source_files=plan['source_files'],
        worker_exit=exit_record,artifacts=artifacts,utc=c.utc(),claim=plan['claim'],
        successor_cases_started=0,contact_prototype_promoted=False,original_campaigns_remain_closed=True)
    c.commit(c.OUT/'final_disposition_01/results.json',final)
    c.commit(c.OUT/'final_disposition_01/completion.json',dict(passed=True,results_sha256=c.sha(c.OUT/'final_disposition_01/results.json')))
    print('STAGE230_FINAL_AUTHENTICATED',result['reason'],known,flush=True)

def record_checks(rec,physical,case,parent):
    api.require(rec['spec']==case['spec']
        and rec['effective_binding']==job.parent.model.binding_for(job.binding(physical,case),True)
        and rec['numerical_policy_contract_sha256']==c.sha(job.WORK)
        and rec['input_checkpoint_sha256']==api.digest(parent)
        and rec['result']['checkpoint']['contract']==parent['contract'], 'Original raw spec/binding/policy/full checkpoint association')

def failed_authentication(exit_record):
    """Preserve and account partial work; never accept an unverified checkpoint."""
    plan=verify();physical,case,before,prefix,inherited=seed(plan)
    api.require(exit_record['retired_exact_identity'], 'Retire exact worker before failure accounting')
    accepted_physical=accepted_diagnostic=known_unaccepted=unknown=0
    cp=copy.deepcopy(before);chain=prefix;previous=LAST_RECEIPT
    diagnostics={}; records=[]; blocked=False
    folders=[c.RUN/NAME/'qualification_01'/label for label in ('serial_01','split_a_01','split_b_01')]
    folders+=sorted((c.RUN/NAME).glob('segment_*'))
    for folder in folders:
        if not folder.is_dir():continue
        diagnostic=folder.parent.name=='qualification_01'
        launch=c.read(folder/'launch.json')
        if diagnostic:
            if folder.name=='split_b_01':
                if 'split_a_01' not in diagnostics:
                    blocked=True
                    parent_cp,parent_prefix=before,prefix
                else:parent_cp,parent_prefix=diagnostics['split_a_01']
            else:parent_cp,parent_prefix=before,prefix
        else:parent_cp,parent_prefix=cp,chain
        item=dict(folder=str(folder),role=launch['role'],reserved_steps=launch['maximum_saved_steps'])
        complete=(folder/'completion.json').is_file() and (folder/'results.json').is_file()
        if complete and not (blocked and not diagnostic):
            row=c.sealed(folder/'results.json');c.verify(row['artifacts'])
            rec,checked=job.codec.read_record(folder/'call.json.xz',prior.EXPECTED_PHYSICAL_SHA,parent_prefix)
            record_checks(rec,physical,case,parent_cp)
            n=len(rec['rows'])
            api.require(row['passed'] and row['summary']['passed'] and row['new_saved_steps']==n
                and row['input_checkpoint_sha256']==api.digest(parent_cp)
                and row['output_checkpoint_sha256']==api.digest(rec['result']['checkpoint']), 'Exact physically accepted partial record')
            item.update(status='accepted',saved_steps=n,receipt_sha256=c.sha(folder/'results.json'))
            if diagnostic:
                accepted_diagnostic+=n;diagnostics[folder.name]=(rec['result']['checkpoint'],checked)
            else:
                api.require(row['previous_receipt_sha256']==previous, 'Last accepted partial production genealogy')
                accepted_physical+=n;cp=rec['result']['checkpoint'];chain=checked;previous=c.sha(folder/'results.json')
        else:
            blocked=True
            if (folder/'accounting.json').is_file():
                accounting=c.read(folder/'accounting.json')
                api.require(accounting['saved_steps_known'] and accounting['raw_sha256']==c.sha(folder/'call.json.xz'),
                            'Known unaccepted saved count bound to preserved raw')
                n=accounting['saved_steps'];api.require(0<=n<=launch['maximum_saved_steps'], 'Bounded known unaccepted work')
                known_unaccepted+=n;item.update(status='known_unaccepted',saved_steps=n)
            else:
                unknown+=launch['maximum_saved_steps'];item.update(status='unknown',saved_step_upper_bound=launch['maximum_saved_steps'])
        records.append(item)
    destination=c.OUT/'failed_disposition_01'
    c.commit(destination/'recoverable/checkpoint.json',cp)
    c.commit(destination/'recoverable/prefix.json',chain.reference())
    known=accepted_physical+accepted_diagnostic+known_unaccepted
    api.require(known+unknown<=plan['maximum_saved_steps_including_diagnostics'], 'Conservative failed saved-step cap')
    artifacts={str(p):c.sha(p) for p in c.RUN.rglob('*') if p.is_file()}
    artifacts.update({str(p):c.sha(p) for p in (destination/'recoverable').glob('*.json')})
    c.commit(destination/'results.json',dict(passed=False,accounting_authenticated=True,worker_exit=exit_record,
        accepted_physical_steps=accepted_physical,accepted_discarded_diagnostic_steps=accepted_diagnostic,
        known_unaccepted_saved_steps=known_unaccepted,unknown_saved_steps_reservation_upper_bound=unknown,
        new_known_saved_steps_including_diagnostics=known,records=records,
        last_accepted_full_checkpoint_sha256=api.digest(cp),last_accepted_receipt_sha256=previous,
        cumulative_physical_steps=cp['state']['steps'],time_s=cp['state']['t'],
        original_full_ancestry_preserved=True,scientific_full_path_passed=False,dependent_dispatch_stopped=True,
        artifacts=artifacts,utc=c.utc(),claim=plan['claim']))
    c.commit(destination/'completion.json',dict(passed=False,results_sha256=c.sha(destination/'results.json')))
    print('STAGE230_FAILED_ACCOUNTING',known,unknown,flush=True)

if __name__=='__main__':
    {'prepare':prepare,'run':run}[sys.argv[1]]()
