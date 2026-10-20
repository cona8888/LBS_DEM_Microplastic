"""Read-only compact Stage229 recovery monitor; never imports the numerical worker stack.

Receipt ancestry and metadata seals are checked. Large raw/trace archives are
not reread; their earlier sealed independent audits remain inherited evidence.
"""
from pathlib import Path
from datetime import datetime, timezone
import json, shutil, sys, time
import psutil
import campaign_common_v1 as c

SUPERVISOR=c.RUN/'supervisor_02'
LAUNCHER=c.RUN/'launcher_02'
BASELINE=c.RUN/'run_02'
SUPERVISOR_DESIGN=c.DESIGNS/'supervisor_design_02.json'
LARGE_SUFFIXES=frozenset(('.xz','.npy','.npz'))


def require(condition,message):
    if not condition:raise ValueError(message)


def inspect_process(receipt):
    """Exact PID, process birth and full command; no process is ever changed."""
    pid=receipt.get('pid');created=receipt.get('created')
    expected=receipt.get('command',receipt.get('argv'))
    if type(pid) is not int or created is None or type(expected) is not list:
        return dict(status='unqualified_identity_receipt',pid=pid)
    if 'command' in receipt and 'argv' in receipt and receipt['command']!=receipt['argv']:
        return dict(status='conflicting_command_argv_receipt',pid=pid)
    try:
        process=psutil.Process(pid);actual_birth=process.create_time();actual_command=process.cmdline()
        matched=actual_birth==float(created) and actual_command==expected
        return dict(status='exact_launch_identity_running' if matched else 'identity_mismatch',pid=pid,
            birth_matches=actual_birth==float(created),command_matches=actual_command==expected,
            recorded_created=created,actual_created=actual_birth,recorded_command=expected,actual_command=actual_command)
    except psutil.NoSuchProcess:
        return dict(status='recorded_pid_absent',pid=pid,recorded_created=created,recorded_command=expected)
    except psutil.AccessDenied:
        return dict(status='identity_inspection_denied',pid=pid)


def run():
    issues=[];deferred=set();verified=set()
    scan_stop=time.monotonic()+30.
    def clock_check():
        if time.monotonic()>=scan_stop:raise RuntimeError('Compact monitor thirty-second metadata scan bound')
    def read(path):
        clock_check()
        path=Path(path)
        try:return c.read(path)
        except Exception as error:
            issues.append(dict(path=str(path),error=type(error).__name__,detail=str(error)));return None
    def mapping(values,metadata_only=False):
        for raw,wanted in values.items():
            clock_check()
            path=Path(raw)
            if metadata_only and path.suffix in LARGE_SUFFIXES:
                require(path.is_file(),'Deferred archive is missing: '+str(path))
                deferred.add(str(path));continue
            require(c.sha(path)==wanted,'Hash mismatch: '+str(path));verified.add(str(path))
    def sealed(path):
        path=Path(path)
        if not path.is_file() or not (path.parent/'completion.json').is_file():return None
        row=read(path);completion=read(path.parent/'completion.json')
        if row is None or completion is None:return None
        require(completion['results_sha256']==c.sha(path),'Result seal mismatch: '+str(path))
        verified.update((str(path),str(path.parent/'completion.json')))
        return row
    auth=read(c.AUTH);require(auth is not None,'Readable authorization required')
    mapping(auth['sources']);mapping(auth['inputs'])
    now=datetime.now(timezone.utc);end=datetime.fromisoformat(auth['end_utc'])
    report=dict(stage='Stage229 compact read-only recovery monitor',utc=now.isoformat(),authorization_sha256=c.sha(c.AUTH),
        start_utc=auth['start_utc'],end_utc=auth['end_utc'],simulation_cutoff_utc=auth['simulation_cutoff_utc'],
        authority_active=datetime.fromisoformat(auth['start_utc'])<=now<end,
        raw_archives_reconstructed=False,raw_content_rehashed=False,new_numerical_calls=0,
        claim='Accepted progress means passing sealed receipts and authenticated metadata/checkpoint ancestry; no population, full-path or cost promotion is inferred from incomplete work.')
    processes={}
    for name,path in (
        ('launcher',LAUNCHER/'launch.json'),('supervisor',SUPERVISOR/'launch.json'),
        ('final_authentication_worker',SUPERVISOR/'final_authentication_worker_launch.json'),('baseline_worker',SUPERVISOR/'baseline_worker_launch.json'),
        ('baseline_self',BASELINE/'launch.json')):
        if path.is_file():
            row=read(path)
            if row is not None:
                if 'authorization_sha256' in row:require(row['authorization_sha256']==c.sha(c.AUTH),'Launch authority: '+name)
                processes[name]=inspect_process(row)
    report['processes']=processes
    initial_processes={}
    for name,path in (
        ('launcher',c.RUN/'launcher_01/launch.json'),
        ('supervisor',c.RUN/'supervisor_01/launch.json'),
        ('cost_worker',c.RUN/'supervisor_01/cost_screen_worker_launch.json'),
        ('baseline_worker',c.RUN/'supervisor_01/baseline_worker_launch.json'),
        ('final_authentication_worker',c.RUN/'supervisor_01/final_authentication_worker_launch.json'),
        ('baseline_self',c.RUN/'run_01/launch.json')):
        if path.is_file():
            row=read(path)
            if row is not None:
                require(row.get('authorization_sha256',c.sha(c.AUTH))==c.sha(c.AUTH),'Initial launch authority')
                initial_processes[name]=inspect_process(row)
    report['initial_processes']=initial_processes
    required_initial={'launcher','supervisor','cost_worker','baseline_worker','final_authentication_worker'}
    report['initial_required_identity_inventory_complete']=required_initial<=initial_processes.keys()
    report['initial_exact_launch_identities_retired']=report['initial_required_identity_inventory_complete'] and all(
        x['status'] in ('recorded_pid_absent','identity_mismatch') for x in initial_processes.values())
    report['owned_exact_process_running_after_deadline']=now>=end and any(x['status']=='exact_launch_identity_running' for x in processes.values())
    report['owned_exact_process_running_after_deadline']|=now>=end and any(
        x['status']=='exact_launch_identity_running' for x in initial_processes.values())
    for name,path in (('supervisor_exit',SUPERVISOR/'exit.json'),('baseline_failure',BASELINE/'failure.json')):
        if path.is_file():report[name]=read(path)
    supervisor=read(SUPERVISOR_DESIGN) if SUPERVISOR_DESIGN.is_file() else None
    transport=c.DESIGNS/'transport_design_03.json'
    if supervisor is not None:
        require(supervisor['authorization_sha256']==c.sha(c.AUTH),'Supervisor authority')
        mapping(supervisor['sources']);mapping(supervisor['inputs'],True)
        candidates=[Path(p) for p in supervisor['inputs'] if Path(p).name.startswith('transport_design_') and Path(p).suffix=='.json']
        require(len(candidates)==1,'Exactly one active frozen transport design in supervisor manifest')
        transport=candidates[0]
        report['supervisor_design_sha256']=c.sha(SUPERVISOR_DESIGN)
    designs={}
    for name,path in (('tiny',c.DESIGNS/'tiny_replay_01.json'),('cost',c.DESIGNS/'cost_screen_01.json')):
        if path.is_file():
            row=read(path)
            if row is not None:
                require(row['authorization_sha256']==c.sha(c.AUTH),'Design authority: '+name)
                mapping(row.get('sources',{}));mapping(row.get('inputs',{}),True)
                designs[name]=dict(path=str(path),sha256=c.sha(path),maximum_outer_calls=row['maximum_outer_calls'])
    report['cost_designs']=designs
    known_calls=0;cost={};reservations=[]
    for folder in sorted(c.OUT.glob('*')):
        if not folder.is_dir() or not (folder/'launch.json').is_file():continue
        result=sealed(folder/'results.json')
        if result is not None:
            require(type(result.get('outer_calls_attempted')) is int,'Sealed numerical call count: '+str(folder))
            known_calls+=result['outer_calls_attempted']
            cost[folder.name]=dict(sealed=True,results_sha256=c.sha(folder/'results.json'),passed=result.get('passed'),
                outer_calls_attempted=result['outer_calls_attempted'],tiny_qualified=result.get('tiny_qualified'),
                exact_paired_all_scientific_outputs=result.get('exact_paired_all_scientific_outputs'),
                unchanged_independent_physics_association_audits=result.get('unchanged_independent_physics_association_audits'),
                strata=result.get('strata'),overall_runtime_gain_fraction=result.get('overall_runtime_gain_fraction'),
                overall_scoped_transaction_runtime_gain_fraction=result.get('overall_scoped_transaction_runtime_gain_fraction'),
                all_strata_material_gain_passed=result.get('all_strata_material_gain_passed'),
                all_strata_scoped_transaction_material_gain_passed=result.get('all_strata_scoped_transaction_material_gain_passed'),
                candidate_production_authorized=False)
        elif (folder/'failure.json').is_file():
            failure=read(folder/'failure.json')
            if failure is not None:
                known_calls+=failure['outer_calls_attempted']
                cost[folder.name]=dict(sealed_success=False,failure_sha256=c.sha(folder/'failure.json'),
                    outer_calls_attempted=failure['outer_calls_attempted'],error=failure.get('error'))
        else:
            key='cost' if folder.name=='cost_screen_01' else 'tiny'
            reservations.append(dict(folder=str(folder),maximum_outer_calls=designs.get(key,{}).get('maximum_outer_calls'),
                returned_call_files=len(list(folder.glob('qualification/*.json')))+len(list(folder.glob('timing/*.json'))),
                qualification_not_accepted=True))
    require(known_calls<=auth['maximum_nonadvancing_outer_calls'],'Shared nonadvancing call ceiling')
    report['cost']=cost
    report['shared_nonadvancing_calls']=dict(known_finished_or_failed_attempts=known_calls,
        maximum=auth['maximum_nonadvancing_outer_calls'],unfinished_reservations=reservations)
    decision=sealed(c.OUT/'dispatch_decision_02/results.json')
    if decision is not None:
        mapping(decision.get('inputs',{}),True)
        require(decision['passed'] and decision['baseline_allowed']
            and not decision['candidate_production_authorized']
            and decision['authorization_sha256']==c.sha(c.AUTH),'Sealed original-only recovery dispatch')
        report['dispatch_decision']={k:decision.get(k) for k in ('baseline_allowed','candidate_production_authorized','reason','authorization_sha256')}
    initial=sealed(c.OUT/'final_disposition_01/results.json')
    prior_saved=prior_physical=prior_diagnostic=0
    if initial is not None:
        require(initial['passed'] and initial['final_accounting_authenticated']
            and initial['all_accepted_full_checkpoint_history_ancestry_reconstructed']
            and initial['authorization_sha256']==c.sha(c.AUTH),'Authenticated initial disposition')
        require(initial['new_audited_physical_steps']==1304148
            and initial['diagnostic_audited_steps']==512
            and initial['new_known_saved_steps_including_diagnostics']==1304660
            and initial['known_unaccepted_saved_steps']==0 and not initial['unresolved'],
            'Initial known work and zero failed pre-dispatch reservation')
        prior_saved=initial['new_known_saved_steps_including_diagnostics']
        prior_physical=initial['new_audited_physical_steps'];prior_diagnostic=initial['diagnostic_audited_steps']
        report['initial_final_disposition']=dict(results_sha256=c.sha(c.OUT/'final_disposition_01/results.json'),
            prior_shared_saved_steps=prior_saved,prior_physical_steps=prior_physical,
            prior_diagnostic_steps=prior_diagnostic,cases=initial['cases'],
            raw_ancestry_reconstruction_inherited=True,raw_ancestry_reconstruction_rerun=False,
            failed_attempt_preserved=True)
    failure=read(c.RUN/'run_01/failure.json') if (c.RUN/'run_01/failure.json').is_file() else None
    if failure is not None:
        report['initial_failure_preserved']=dict(path=str(c.RUN/'run_01/failure.json'),
            sha256=c.sha(c.RUN/'run_01/failure.json'),error=failure.get('error'),
            utc=failure.get('utc'),unresolved_reservation=failure.get('unresolved_reservation'),
            transient_file_access_cause_unproven=True)
    for leaf in ('initial_retirement_01','failure_diagnosis_01'):
        evidence=sealed(c.OUT/leaf/'results.json')
        if evidence is not None:
            require(evidence['passed'],'Passing recovery prerequisite: '+leaf)
            mapping(evidence.get('inputs',{}),True);mapping(evidence.get('artifacts',{}),True)
            report[leaf]=dict(results_sha256=c.sha(c.OUT/leaf/'results.json'),passed=True,
                all_exact_launch_identities_retired=evidence.get('all_exact_launch_identities_retired'),
                failed_pre_dispatch_reservation_resolved_to_zero=evidence.get('failed_pre_dispatch_reservation_resolved_to_zero'))
    plan=read(transport) if transport.is_file() else None
    accepted_steps=diagnostic_steps=0;cases=[];unresolved=[]
    if plan is not None:
        require(plan['authorization_sha256']==c.sha(c.AUTH),'Transport authorization')
        require(plan['binding']==c.digest({k:v for k,v in plan.items() if k!='binding'}),'Transport binding digest')
        mapping(plan['source_files']);mapping(plan['physical_inputs'],True)
        # The separately sealed original disposition reconstructed the accepted
        # inherited raw genealogy. This compact monitor hashes its proof and the
        # new seed metadata, without rereading the entire old multi-GB chain.
        for raw,wanted in plan['inputs'].items():
            path=Path(raw)
            if path.parent.name in ('final_disposition_01','recovery_seed_01'):
                mapping({raw:wanted},True)
        require(initial is not None and report['initial_exact_launch_identities_retired'],
            'Recovery requires independently closed initial work and retired exact identities')
        require(plan['prior_shared_saved_steps']==prior_saved
            and plan['prior_shared_diagnostic_saved_steps']==prior_diagnostic,'Unchanged initial shared ledger')
        require(plan['inherited']['inherited_segments']==1039
            and plan['inherited']['inherited_physical_steps']==3526694
            and plan['inherited']['inherited_stop_s']==4.385606625455791,'Authenticated combined recovery endpoint')
        initial_case=next(x for x in initial['cases'] if x['case']==plan['original_case_order'][0])
        require(initial_case['new_audited_segments']==470
            and initial_case['cumulative_physical_steps']==plan['inherited']['inherited_physical_steps']
            and initial_case['time_s']==plan['inherited']['inherited_stop_s']
            and initial_case['last_sealed_receipt_sha256']==plan['inherited']['inherited_last_receipt_sha256'],
            'Original disposition and new recovery seed agree')
        report['transport_design_sha256']=c.sha(transport)
        inherited=plan['inherited'];physical_sha=plan['physical_design_sha256'];transport_sha=c.sha(transport)
        require(plan['original_case_order']==auth['independent_baseline']['case_order'],'Frozen case order')
        for index,name in enumerate(plan['original_case_order']):
            clock_check()
            folder=BASELINE/name;is_seed=index==0
            previous=inherited['inherited_last_receipt_sha256'] if is_seed else None
            checkpoint=inherited['input_checkpoint_sha256'] if is_seed else c.digest(None)
            stop=inherited['inherited_stop_s'] if is_seed else 0.
            initial_steps=inherited['inherited_physical_steps'] if is_seed else 0
            entry=dict(case=name,inherited_segments=inherited['inherited_segments'] if is_seed else 0,
                accepted_new_segments=0,accepted_new_physical_steps=0,accepted_diagnostic_steps=0,
                last_accepted_time_s=stop,last_accepted_checkpoint_sha256=checkpoint,complete_observation=False,full_path_qualified=False)
            qualification=folder/'qualification_01'
            diagnostics={}
            for part in ('serial_01','split_a_01','split_b_01'):
                q=qualification/part
                if not q.is_dir():continue
                row=sealed(q/'results.json')
                if row is None:
                    unresolved.append(dict(folder=str(q),role='restart_diagnostic',reason='unsealed_or_invalid_receipt'));continue
                require(row['passed'] and row['summary']['passed'] and row['role']=='restart_diagnostic','Passing diagnostic receipt')
                require(row['transport_design_sha256']==transport_sha and row['physical_design_sha256']==physical_sha,'Diagnostic design')
                branch=diagnostics.get('split_a_01') if part=='split_b_01' else None
                require(part!='split_b_01' or branch is not None,'Split diagnostic requires its sealed first branch')
                expected_checkpoint=branch['output_checkpoint_sha256'] if branch else checkpoint
                expected_receipt=c.sha(qualification/'split_a_01/results.json') if branch else previous
                expected_start=branch['summary']['stop_s'] if branch else stop
                require(row['input_checkpoint_sha256']==expected_checkpoint and row['previous_receipt_sha256']==expected_receipt,'Diagnostic branch ancestry')
                require(row['summary']['start_s']==expected_start,'Diagnostic branch clock')
                mapping(row['artifacts'],True);steps=row['new_saved_steps']
                require(steps==row['summary']['steps'] and steps>0,'Diagnostic saved-step count')
                diagnostics[part]=row
                entry['accepted_diagnostic_steps']+=steps;diagnostic_steps+=steps
            qr=sealed(qualification/'results.json')
            entry['exact_restart_qualified']=qr is not None and qr.get('passed') is True
            if qr is not None:
                mapping(qr['artifacts'],True)
                require(qr['production_seed_unchanged'] and not qr['diagnostic_trajectory_promoted'],'Unpromoted diagnostics')
                require(qr['diagnostic_saved_steps']==entry['accepted_diagnostic_steps']==512,'Complete diagnostic qualification count')
                require(qr['exact_serial_split_rows'] and qr['exact_full_checkpoint'] and qr['all_three_independent_physical_audits_passed'],'Exact restart qualification gates')
                require(qr['production_seed_sha256']==checkpoint and qr['transport_design_sha256']==transport_sha,'Qualified original production seed')
            blocked=False
            new_trace_bindings={}
            for segment in sorted(folder.glob('segment_*')):
                if not segment.is_dir():continue
                if blocked:
                    unresolved.append(dict(folder=str(segment),role='production',reason='after_unqualified_predecessor'));continue
                row=sealed(segment/'results.json')
                if row is None:
                    unresolved.append(dict(folder=str(segment),role='production',reason='unsealed_or_invalid_receipt'));blocked=True;continue
                sequence=int(segment.name.split('_')[-1])
                require(sequence==entry['accepted_new_segments']+1,'Contiguous new segment indices')
                require(entry['exact_restart_qualified'],'Production requires a sealed exact restart gate')
                require(row['passed'] and row['summary']['passed'] and row['role']=='production','Passing production receipt')
                require(row['transport_design_sha256']==transport_sha and row['physical_design_sha256']==physical_sha,'Production design')
                require(row['input_checkpoint_sha256']==checkpoint and row['previous_receipt_sha256']==previous,'Checkpoint/receipt ancestry')
                steps=row['new_saved_steps'];summary=row['summary']
                require(steps==summary['steps'] and 0<steps<=plan['step_cap_per_call'],'Production bounded saved steps')
                require(summary['start_s']==stop and summary['stop_s']>=stop,'Production clock ancestry')
                mapping(row['artifacts'],True)
                trace=segment/'trace.npy'
                require(str(trace) in row['artifacts'],'Accepted segment trace binding')
                new_trace_bindings[str(trace)]=row['artifacts'][str(trace)]
                accounting=read(segment/'accounting.json');rawseal=read(segment/'call.json.seal.json')
                require(accounting is not None and rawseal is not None,'Complete raw metadata')
                require(accounting['saved_steps']==steps and accounting['rejected']==0,'Raw accounting agrees')
                raw=segment/'call.json.xz'
                require(raw.is_file() and raw.stat().st_size==rawseal['compressed_bytes'],'Stored compressed archive size')
                require(rawseal['compressed_sha256']==accounting['raw_sha256']==row['artifacts'][str(raw)],'Recorded raw hash association')
                stop=summary['stop_s'];checkpoint=row['output_checkpoint_sha256'];previous=c.sha(segment/'results.json')
                accepted_steps+=steps;entry['accepted_new_physical_steps']+=steps;entry['accepted_new_segments']+=1
                entry.update(last_accepted_time_s=stop,last_accepted_checkpoint_sha256=checkpoint,last_accepted_receipt_sha256=previous)
            final=sealed(folder/'results.json')
            if final is not None:
                require(final['new_physical_steps']==entry['accepted_new_physical_steps'] and final['final_checkpoint_sha256']==checkpoint,'Case terminal accepted chain')
                require(c.digest(read(folder/'checkpoint.json'))==checkpoint,'Saved full terminal checkpoint digest')
                require(final['time_s']==stop and final['cumulative_physical_steps']==initial_steps+entry['accepted_new_physical_steps'],'Case terminal clock/steps')
                require(final['transport_design_sha256']==transport_sha and final['physical_design_sha256']==physical_sha,'Case terminal design')
                entry.update(complete_observation=final['complete_observation'],reason=final['reason'],final_status=final['final_status'])
            comparison=sealed(c.OUT/name/'comparison_01/results.json')
            if comparison is not None:
                require(final is not None and final['complete_observation'],'Comparison requires a complete sealed terminal')
                require(comparison['case']==name and comparison['transport_design_sha256']==transport_sha and comparison['physical_design_sha256']==physical_sha,'Comparison case and exact design')
                require(comparison['observation']['stop_s']==stop and final['final_checkpoint_sha256']==checkpoint,'Comparison terminal checkpoint/clock association')
                mapping(comparison['path_artifacts'],True)
                for trace,wanted in new_trace_bindings.items():
                    require(comparison['path_artifacts'].get(trace)==wanted,'Comparison exact new trace ancestry')
                for trace in inherited['trace_paths'] if is_seed else ():
                    require(comparison['path_artifacts'].get(trace)==inherited['inputs'][trace],'Comparison inherited trace ancestry')
                require(comparison['new_segments']==entry['accepted_new_segments'] and comparison['inherited_segments']==entry['inherited_segments'],'Comparison path inventory')
                require(comparison['passed']==comparison['full_path_gates']['passed'],'Comparison gate summary agrees')
                entry['full_path_qualified']=comparison['passed'] is True
            entry['cumulative_case_physical_steps']=initial_steps+entry['accepted_new_physical_steps']
            require(entry['cumulative_case_physical_steps']<=plan['maximum_cumulative_physical_steps_per_case'],'Per-case physical ceiling')
            entry['cumulative_case_calls']=entry['inherited_segments']+entry['accepted_new_segments']
            require(entry['cumulative_case_calls']<=plan['maximum_cumulative_calls_per_case'],'Per-case call ceiling')
            cases.append(entry)
        require(prior_saved+accepted_steps+diagnostic_steps<=plan['maximum_saved_steps_including_diagnostics'],'Shared saved-step ceiling')
    terminal=sealed(BASELINE/'results.json')
    if terminal is not None:
        require(terminal['saved_steps_including_diagnostics']==prior_saved+accepted_steps+diagnostic_steps,'Terminal shared accounting')
        require(terminal['current_run_saved_steps_including_diagnostics']==accepted_steps+diagnostic_steps
            and terminal['prior_shared_saved_steps']==prior_saved,'Terminal recovery-tail accounting')
        report['baseline_terminal']={k:terminal.get(k) for k in ('finished','reason','whole_overnight_success','candidate_production_authorized','utc')}
    final=sealed(c.OUT/'final_disposition_02/results.json')
    if final is not None:
        require(final['passed'] and final['final_accounting_authenticated'],'Passing independent recovery disposition')
        report['recovery_final_disposition']=dict(results_sha256=c.sha(c.OUT/'final_disposition_02/results.json'),
            passed=final['passed'],whole_overnight_success=final.get('whole_overnight_success'),
            unresolved=final.get('unresolved'),cases=final.get('cases'))
    report.update(baseline_cases=cases,accepted_new_physical_steps=accepted_steps,accepted_diagnostic_steps=diagnostic_steps,
        accepted_new_saved_steps_including_diagnostics=accepted_steps+diagnostic_steps,
        prior_shared_saved_steps=prior_saved,shared_accepted_physical_steps=prior_physical+accepted_steps,
        shared_accepted_diagnostic_steps=prior_diagnostic+diagnostic_steps,
        shared_accepted_saved_steps_including_diagnostics=prior_saved+accepted_steps+diagnostic_steps,
        maximum_shared_saved_steps=auth['maximum_saved_steps_including_diagnostics'],unresolved_folders=unresolved,
        integrity_issues=issues,verified_metadata_files=len(verified),large_archive_rehash_deferred=len(deferred),
        free_disk_bytes=shutil.disk_usage(c.ROOT).free,candidate_production_authorized=False)
    print(json.dumps(report,sort_keys=True,indent=2,allow_nan=False),flush=True)
    return report


if __name__=='__main__':
    if sys.argv[1:]:raise ValueError('Monitor takes no arguments')
    run()
