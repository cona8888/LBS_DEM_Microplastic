"""Authenticate retired Stage229 work without new physical solves."""
from pathlib import Path
import sys, traceback
import campaign_common_v1 as c

DEST = c.OUT/'final_disposition_01'


def need(condition, message):
    if not condition:
        raise RuntimeError(message)


def inventory(folder, artifacts):
    for path in sorted(folder.rglob('*')):
        c.bound()
        if path.is_file():
            artifacts[str(path)] = c.sha(path)


def launch_header(w, plan, folder, role, cap_limit):
    launch = c.read(folder/'launch.json')
    need(launch['authorization_sha256'] == c.sha(c.AUTH)
         and launch['transport_design_sha256'] == c.sha(w.PLAN)
         and launch['physical_design_sha256'] == w.EXPECTED_PHYSICAL_SHA
         and launch['role'] == role and launch['simulation_cutoff_utc'] == plan['simulation_cutoff_utc'],
         'Frozen numerical launch authority/role/cutoff')
    cap = launch['maximum_saved_steps']
    need(type(cap) is int and 0 < cap <= cap_limit, 'Exact bounded numerical reservation')
    return launch, cap


def raw_identity(w, physical, case, rec, seed):
    need(rec['spec'] == case['spec']
         and rec['input_checkpoint_sha256'] == w.api.digest(seed)
         and rec['numerical_policy_contract_sha256'] == c.sha(w.job.WORK)
         and rec['effective_binding'] == w.job.parent.model.binding_for(w.job.binding(physical, case), True),
         'Raw physical case, seed and numerical-policy bindings')


def accepted_record(w, plan, physical, case, folder, role, cap_limit, seed, prefix, previous):
    launch, cap = launch_header(w, plan, folder, role, cap_limit)
    row = c.sealed(folder/'results.json'); c.verify(row['artifacts'])
    need(row['transport_design_sha256'] == c.sha(w.PLAN)
         and row['physical_design_sha256'] == w.EXPECTED_PHYSICAL_SHA
         and row['numerical_policy_contract_sha256'] == plan['numerical_policy_contract_sha256']
         and row['original_binding'] == w.job.binding(physical, case)
         and row['role'] == role and row['previous_receipt_sha256'] == previous
         and row['input_checkpoint_sha256'] == launch['input_checkpoint_sha256'] == w.api.digest(seed),
         'Accepted receipt case/role/authority/ancestry')
    rec, next_prefix = w.job.codec.read_record(folder/'call.json.xz', w.EXPECTED_PHYSICAL_SHA, prefix)
    raw_identity(w, physical, case, rec, seed)
    account = c.read(folder/'accounting.json'); steps = row['new_saved_steps']
    need(account['saved_steps_known'] is True and type(steps) is int and 0 < steps <= cap
         and type(account['saved_steps']) is int
         and account['saved_steps'] == steps == len(rec['rows']) == row['summary']['steps']
         and account['role'] == role and account['raw_sha256'] == c.sha(folder/'call.json.xz')
         and account['rejected'] == rec['result']['rejected'] == 0
         and row['passed'] is True and row['summary']['passed'] is True,
         'Authenticated accepted physical and saved-step evidence')
    cp = rec['result']['checkpoint']; initial = 0 if seed is None else seed['state']['steps']
    initial_t = 0. if seed is None else seed['state']['t']
    need(row['output_checkpoint_sha256'] == w.api.digest(cp)
         and cp['state']['steps']-initial == steps and row['summary']['start_s'] == initial_t
         and row['summary']['stop_s'] == cp['state']['t'], 'Exact accepted checkpoint/time chain')
    for name in ('launch.json','accounting.json','call.json.xz','call.json.seal.json','trace.npy'):
        need(row['artifacts'].get(str(folder/name)) == c.sha(folder/name), 'Complete accepted artifact association')
    return row, rec, next_prefix


def unresolved_record(w, plan, physical, case, folder, role, cap_limit, seed, prefix, kind):
    """Count a complete sealed raw record as saved, without promoting its physics.

    A missing/corrupt archive or uncertain ancestry leaves the entire launch
    reservation unknown. Accounting alone never establishes a saved-step count.
    """
    item = dict(folder=str(folder), kind=kind, physical_acceptance=False,
                known_saved_steps=0, unknown_saved_steps_reservation_upper_bound=cap_limit)
    rec = next_prefix = None
    try:
        launch, cap = launch_header(w, plan, folder, role, cap_limit)
        item['maximum_saved_steps'] = cap
        item['unknown_saved_steps_reservation_upper_bound'] = cap
        account = c.read(folder/'accounting.json')
        count = account['saved_steps']
        need(account['saved_steps_known'] is True and type(count) is int and 0 <= count <= cap
             and account['role'] == role and account['raw_sha256'] == c.sha(folder/'call.json.xz')
             and launch['input_checkpoint_sha256'] == w.api.digest(seed),
             'Known-unaccepted accounting/header/raw association')
        rec, next_prefix = w.job.codec.read_record(folder/'call.json.xz', w.EXPECTED_PHYSICAL_SHA, prefix)
        raw_identity(w, physical, case, rec, seed)
        initial = 0 if seed is None else seed['state']['steps']
        need(count == len(rec['rows']) == rec['result']['checkpoint']['state']['steps']-initial,
             'Known-unaccepted exact raw saved-step count')
        item.update(known_saved_steps=count, unknown_saved_steps_reservation_upper_bound=0,
                    saved_count_authenticated_from_sealed_raw=True,
                    raw_sha256=c.sha(folder/'call.json.xz'))
    except Exception as error:
        item.update(reason=repr(error), saved_count_authenticated_from_sealed_raw=False)
        rec = next_prefix = None
    return item, rec, next_prefix


def reference_paths(w, physical, case):
    name = case['reference_case']
    if case['sample_id'] == 0:
        name = next(row['id'] for row in w.api.read(w.baseline.old.DESIGN)['cases']
                    if row['shape'] == case['shape'] and row['sample_id'] == 0 and row['factor'] == .03125)
    proof = c.sealed(w.baseline.PREREQUISITE); need(proof['passed'] is True, 'Original reference prerequisite')
    paths = sorted((w.baseline.old.RUN/name).glob('segment_*.npy'))
    if name == w.baseline.inherited.NAME:
        recovered = c.sealed(w.baseline.inherited.RUN/'production_01/results.json')
        paths += [w.baseline.inherited.RUN/'production_01'/f"segment_{row['segment']:05d}"/'trace.npy'
                  for row in recovered['entries']]
    for path in paths:
        c.bound(); need(proof['artifacts'][str(path)] == c.sha(path), 'Original reference trace identity')
    return name, paths


def finish():
    import continue_baseline_v2 as w
    a = c.bound(); c.verify(a['sources']); c.verify(a['inputs'])
    plan = w.verify(c.read(w.PLAN))
    before, prefix, inherited = w.authenticate_inherited()
    need(inherited == plan['inherited'], 'Frozen inherited numerical genealogy')
    physical = w.physical_design(); run = w.RUN
    artifacts = {str(c.AUTH):c.sha(c.AUTH), str(w.PLAN):c.sha(w.PLAN)}
    cost_calls = cost_unknown = 0; cost = []; unresolved = []; screen = None
    for launch in sorted(c.OUT.glob('*/launch.json')):
        c.bound(); folder = launch.parent
        design_path = c.DESIGNS/(folder.name+'.json')
        design = c.read(design_path); launch_row = c.read(launch)
        need(design['authorization_sha256'] == c.sha(c.AUTH)
             and launch_row['design_sha256'] == c.sha(design_path), 'Cost launch/design authority')
        c.verify(design['inputs']); c.verify(design['sources'])
        cap = design['maximum_outer_calls']
        need(type(cap) is int and 0 < cap <= a['maximum_nonadvancing_outer_calls'], 'Bounded cost reservation')
        result = folder/'results.json'; failure = folder/'failure.json'
        if result.is_file() and (folder/'completion.json').is_file():
            row = c.sealed(result); c.verify(row.get('artifacts', {}))
            count = row['outer_calls_attempted']; need(type(count) is int and 0 <= count <= cap, 'Cost count')
            need(row['design_sha256'] == c.sha(design_path)
                 and row['new_trajectory_steps'] == row['new_saved_transport_steps'] == 0
                 and row['production_authorized'] is False, 'Fixed-pose result authority and zero transport')
            cost_calls += count
            cost.append(dict(folder=str(folder),passed=row['passed'],outer_calls_attempted=count,results_sha256=c.sha(result)))
            if folder.name == 'cost_screen_01': screen = row
        elif failure.is_file():
            row = c.read(failure); c.verify(row.get('artifacts', {}))
            count = row['outer_calls_attempted']; need(type(count) is int and 0 <= count <= cap, 'Failed cost count')
            cost_calls += count
            cost.append(dict(folder=str(folder),passed=False,outer_calls_attempted=count,failure_sha256=c.sha(failure)))
        else:
            cost_unknown += cap
            unresolved.append(dict(folder=str(folder),kind='unfinished_fixed_pose_reservation',maximum_outer_calls=cap))
        inventory(folder, artifacts); artifacts[str(design_path)] = c.sha(design_path)
    need(cost_calls <= a['maximum_nonadvancing_outer_calls'], 'Confirmed fixed-pose cap')
    accepted = diagnostic = known_unaccepted = 0; cases = []; comparisons = []
    for case in physical['cases']:
        c.bound(); root = run/case['id']; is_seed = case['id'] == w.SEED_NAME
        cp = before if is_seed else None; current_prefix = prefix if is_seed else None
        previous = inherited['inherited_last_receipt_sha256'] if is_seed else None
        new_count = case_steps = diag_steps = 0; last = last_rec = None
        case_unresolved = []; qual = root/'qualification_01'
        qseed = cp; qp = current_prefix; split_cp = split_prefix = split_previous = None
        diag_records = {}; diag_valid = True
        expected_parts = dict(serial_01=256, split_a_01=128, split_b_01=128)
        for name, cap in expected_parts.items():
            c.bound(); folder = qual/name
            if not folder.exists(): diag_valid = False; continue
            seed = split_cp if name == 'split_b_01' else qseed
            parent = split_prefix if name == 'split_b_01' else qp
            prev = split_previous if name == 'split_b_01' else previous
            sealed = (folder/'results.json').is_file() and (folder/'completion.json').is_file()
            if sealed and (name != 'split_b_01' or 'split_a_01' in diag_records):
                row, rec, next_prefix = accepted_record(w,plan,physical,case,folder,'restart_diagnostic',cap,seed,parent,prev)
                need(row['new_saved_steps'] == cap, 'Exact restart branch cap')
                diag_records[name] = rec
                diagnostic += cap; diag_steps += cap
                if name == 'split_a_01':
                    split_cp = rec['result']['checkpoint']; split_prefix = next_prefix; split_previous = c.sha(folder/'results.json')
            else:
                diag_valid = False
                item, rec, next_prefix = unresolved_record(w,plan,physical,case,folder,'restart_diagnostic',cap,seed,parent,'unaccepted_restart_diagnostic')
                known_unaccepted += item['known_saved_steps']; unresolved.append(item); case_unresolved.append(item)
                if name == 'split_a_01' and rec is not None:
                    split_cp = rec['result']['checkpoint']; split_prefix = next_prefix
            inventory(folder, artifacts)
        if qual.exists():
            for folder in sorted(qual.iterdir()):
                if folder.is_dir() and folder.name not in expected_parts:
                    item,_,_ = unresolved_record(w,plan,physical,case,folder,'restart_diagnostic',plan['step_cap_per_call'],None,None,'unexpected_restart_folder')
                    known_unaccepted += item['known_saved_steps']; unresolved.append(item);case_unresolved.append(item);diag_valid=False
                    inventory(folder,artifacts)
        qualification_passed = False
        if (qual/'completion.json').is_file():
            q = c.sealed(qual/'results.json'); c.verify(q['artifacts'])
            need(diag_valid and set(diag_records) == set(expected_parts)
                 and q['passed'] is True and q['diagnostic_trajectory_promoted'] is False
                 and q['transport_design_sha256'] == c.sha(w.PLAN) and q['production_seed_sha256'] == w.api.digest(qseed)
                 and q['diagnostic_saved_steps'] == diag_steps == 512,
                 'Authenticated complete restart qualification')
            serial = diag_records['serial_01']; left = diag_records['split_a_01']; right = diag_records['split_b_01']
            need(serial['rows'] == left['rows']+right['rows']
                 and w.api.digest(serial['result']['checkpoint']) == w.api.digest(right['result']['checkpoint']),
                 'Independent exact serial/split rows and full checkpoint')
            qualification_passed = True
        if qual.exists(): inventory(qual,artifacts)
        chain_broken = False; forensic_cp = cp; forensic_prefix = current_prefix; accepted_paths = []
        for index, folder in enumerate(sorted(root.glob('segment_*')), 1):
            c.bound()
            if not folder.is_dir():
                artifacts[str(folder)] = c.sha(folder)
                chain_broken = True
                item = dict(folder=str(folder),kind='unexpected_production_file',physical_acceptance=False,
                    known_saved_steps=0,unknown_saved_steps_reservation_upper_bound=plan['step_cap_per_call'])
                unresolved.append(item);case_unresolved.append(item);continue
            contiguous = folder.name == f'segment_{index:05d}'
            sealed = (folder/'results.json').is_file() and (folder/'completion.json').is_file()
            if contiguous and sealed and not chain_broken:
                need(qualification_passed, 'Production requires exact restart qualification')
                row,rec,next_prefix = accepted_record(w,plan,physical,case,folder,'production',plan['step_cap_per_call'],cp,current_prefix,previous)
                accepted += row['new_saved_steps']; case_steps += row['new_saved_steps']; new_count += 1
                cp = rec['result']['checkpoint'];current_prefix = next_prefix;previous = c.sha(folder/'results.json')
                forensic_cp = cp;forensic_prefix = current_prefix;last = folder;last_rec = rec
                accepted_paths.append(folder/'trace.npy')
            else:
                chain_broken = True
                item,rec,next_prefix = unresolved_record(w,plan,physical,case,folder,'production',plan['step_cap_per_call'],forensic_cp,forensic_prefix,'unaccepted_production' if contiguous else 'nonancestral_production')
                known_unaccepted += item['known_saved_steps']; unresolved.append(item);case_unresolved.append(item)
                if rec is not None:forensic_cp=rec['result']['checkpoint'];forensic_prefix=next_prefix
            inventory(folder, artifacts)
        if cp is not None and new_count:
            recovery = DEST/'recoverable'/case['id']
            c.bound()
            c.commit(recovery/'checkpoint.json',cp);c.commit(recovery/'prefix.json',current_prefix.reference())
            inventory(recovery,artifacts)
        case_result = c.sealed(root/'results.json') if (root/'completion.json').is_file() else None
        complete = False
        if case_result is not None:
            need(not chain_broken and case_result['case'] == case['id']
                 and case_result['transport_design_sha256'] == c.sha(w.PLAN)
                 and case_result['physical_design_sha256'] == w.EXPECTED_PHYSICAL_SHA
                 and case_result['final_checkpoint_sha256'] == w.api.digest(cp)
                 and case_result['new_physical_steps'] == case_steps
                 and case_result['cumulative_physical_steps'] == (0 if cp is None else cp['state']['steps'])
                 and case_result['time_s'] == (0. if cp is None else cp['state']['t']), 'Bound terminal numerical case')
            complete = case_result['complete_observation'] is True
            if complete:need(last_rec is not None and last_rec['result']['status'] in w.job.policy.COMPLETE
                             and case_result['final_status'] == last_rec['result']['status'], 'Complete actual terminal observation')
        comparison = None;comp = c.OUT/case['id']/'comparison_01/results.json'
        if (comp.parent/'completion.json').is_file():
            comparison = c.sealed(comp);c.verify(comparison['path_artifacts'])
            name, references = reference_paths(w,physical,case)
            paths = ([Path(x) for x in inherited['trace_paths']] if is_seed else [])+accepted_paths+references
            need(complete and not case_unresolved and comparison['case'] == case['id']
                 and comparison['reference_case'] == name and comparison['transport_design_sha256'] == c.sha(w.PLAN)
                 and comparison['physical_design_sha256'] == w.EXPECTED_PHYSICAL_SHA
                 and comparison['reference_evaluation_sha256'] == c.sha(w.baseline.PREREQUISITE)
                 and comparison['observation']['complete_observation'] is True
                 and comparison['observation']['steps'] == cp['state']['steps']
                 and comparison['observation']['stop_s'] == cp['state']['t']
                 and comparison['path_artifacts'] == {str(path):c.sha(path) for path in paths}
                 and comparison['passed'] == comparison['full_path_gates']['passed'],
                 'Comparison bound to complete actual case and entire exact path inventory')
            inventory(comp.parent,artifacts);artifacts.update(comparison['path_artifacts'])
            comparisons.append(dict(case=case['id'],passed=comparison['passed'],full_path_gates=comparison['full_path_gates']))
        cumulative = 0 if cp is None else cp['state']['steps']; inherited_calls = inherited['inherited_segments'] if is_seed else 0
        need(cumulative <= plan['maximum_cumulative_physical_steps_per_case']
             and new_count+inherited_calls <= plan['maximum_cumulative_calls_per_case'], 'Cumulative production ceiling')
        status = ('complete_path_passed' if comparison and comparison['passed'] else
                  'full_path_gate_failed' if comparison else 'observation_complete_accuracy_pending' if complete else
                  'incomplete' if root.exists() else 'not_started')
        cases.append(dict(case=case['id'],status=status,new_audited_physical_steps=case_steps,new_audited_segments=new_count,
            diagnostic_saved_steps=diag_steps,qualification_passed=qualification_passed,cumulative_physical_steps=cumulative,
            time_s=0. if cp is None else cp['state']['t'],horizon_s=case['spec']['horizon_s'],
            last_sealed_receipt_sha256=previous,last_sealed_folder=None if last is None else str(last),unresolved_attempts=len(case_unresolved)))
        if root.exists():inventory(root,artifacts)
    total = accepted+diagnostic+known_unaccepted
    unknown_upper = sum(x.get('unknown_saved_steps_reservation_upper_bound',0) for x in unresolved)
    need(total <= plan['maximum_saved_steps_including_diagnostics'], 'Confirmed known shared saved-step cap')
    controller = c.RUN/'supervisor_01'
    # This finalizer is still writing its own process logs. Preserve them on
    # disk without asserting a final byte hash before that process retires.
    deferred_live_logs = []
    for path in sorted(controller.rglob('*')):
        c.bound()
        if not path.is_file():continue
        if path.name in ('final_authentication_stdout.log','final_authentication_stderr.log'):
            deferred_live_logs.append(str(path));continue
        artifacts[str(path)]=c.sha(path)
    for path in run.glob('*.json'):artifacts[str(path)]=c.sha(path)
    overall = not unresolved and all(x['status'] == 'complete_path_passed' for x in cases)
    cost_status = ('scientific_cost_screen_unqualified' if screen is None or screen['passed'] is not True else
        'scientific_cost_screen_passed_material_gain_passed' if screen['both_outer_and_transaction_all_strata_material_gain_passed'] else
        'scientific_cost_screen_passed_material_gain_failed')
    c.bound()
    result = dict(passed=True,final_accounting_authenticated=True,utc=c.utc(),authorization_sha256=c.sha(c.AUTH),
        transport_design_sha256=c.sha(w.PLAN),maximum_end_utc=a['end_utc'],whole_overnight_success=overall,
        cost=cost,cost_qualification_status=cost_status,fixed_pose_outer_calls_attempted=cost_calls,
        unknown_fixed_pose_outer_call_reservation_upper_bound=cost_unknown,
        confirmed_known_fixed_pose_cap_compliance=True,conservative_fixed_pose_cap_compliance=cost_calls+cost_unknown<=a['maximum_nonadvancing_outer_calls'],
        new_audited_physical_steps=accepted,diagnostic_audited_steps=diagnostic,known_unaccepted_saved_steps=known_unaccepted,
        new_known_saved_steps_including_diagnostics=total,unknown_saved_steps_reservation_upper_bound=unknown_upper,
        confirmed_known_saved_step_cap_compliance=True,conservative_saved_step_cap_compliance=total+unknown_upper<=plan['maximum_saved_steps_including_diagnostics'],
        inherited_physical_steps=inherited['inherited_physical_steps'],cases=cases,comparisons=comparisons,unresolved=unresolved,
        unresolved_work_preserved=True,all_accepted_full_checkpoint_history_ancestry_reconstructed=True,
        physical_audits_rehashed_and_reused=True,physical_audits_rerun=False,artifacts=artifacts,
        finalizer_live_logs_preserved_unsealed=deferred_live_logs,
        candidate_production_authorized=False,population_shape_flow_campaign=False,claim=a['claim_boundary'])
    c.commit(DEST/'results.json',result);c.commit(DEST/'completion.json',dict(results_sha256=c.sha(DEST/'results.json'),passed=True))
    c.bound()
    summary = f"Stage229 is closed: {cost_status.replace('_',' ')}; {cost_calls}/640 known fixed-pose calls, {accepted:,} new audited physical steps, {diagnostic:,} audited diagnostic steps, {known_unaccepted:,} known unaccepted saved steps and {len(unresolved)} unresolved attempts. Original baseline cases: "+'; '.join(f"{x['case']}: {x['status']}" for x in cases)+'. The optimization remains unpromoted; further execution requires a new bounded authorization.'
    path = c.ROOT/'MASTER_PLAN.md'; text = path.read_text(encoding='utf-8')
    begin = '<!-- STAGE229_OVERNIGHT_BEGIN -->'; end = '<!-- STAGE229_OVERNIGHT_END -->'
    paragraph = '\n'.join([begin,'## Stage229 bounded overnight disposition - 8 October 2026','',
        '[Authenticated final disposition](stage229_evaluations/overnight_20261007/final_disposition_01/results.json). '+summary,'',
        *[f"- `{x['case']}`: **{x['status']}**, {x['time_s']:.9f}/{x['horizon_s']:.9f} s; {x['new_audited_segments']} new audited segments." for x in cases],'',
        'All available accepted raw checkpoint/history ancestry is authenticated. Unknown work is preserved and never promoted. This is numerical verification at labelled placements and one packing/flow; no population shape/flow trend or field escape fraction is established. The campaign heartbeat must pause after this disposition.',end])
    need(begin in text and end in text,'Prepared Stage229 master-plan markers')
    text = text[:text.index(begin)]+paragraph+text[text.index(end)+len(end):]
    lines = text.splitlines()
    for index,line in enumerate(lines):
        if line.startswith('**Contact optimization / current work:**'):
            lines[index]='**Contact optimization / current work:** '+summary+'  ';break
    else:raise RuntimeError('Prepared current-work master-plan pointer')
    c.bound();path.write_text('\n'.join(lines)+'\n',encoding='utf-8',newline='\n')
    current = c.ROOT/'CURRENT_PLAN.md';parts=current.read_text(encoding='utf-8').split('\n\n',2)
    need(len(parts)==3 and parts[0].startswith('# Current execution:'),'Prepared current-execution pointer')
    c.bound();current.write_text('# Current execution: Stage229 closed disposition\n\n'+summary+' See [MASTER_PLAN.md](MASTER_PLAN.md).\n\n'+parts[2],encoding='utf-8',newline='\n')
    c.bound();c.commit(DEST/'plan_update.json',dict(master_plan_sha256=c.sha(path),current_plan_sha256=c.sha(current),final_results_sha256=c.sha(DEST/'results.json'),utc=c.utc()))
    print('STAGE229_FINAL_AUTHENTICATED',accepted,diagnostic,len(unresolved),c.sha(DEST/'results.json'),flush=True)


if __name__ == '__main__':
    try:finish()
    except Exception as error:
        c.commit(c.OUT/'final_authentication_failure_01.json',dict(error=repr(error),traceback=traceback.format_exc(),utc=c.utc(),evidence_preserved=True))
        raise
