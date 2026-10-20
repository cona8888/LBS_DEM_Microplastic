"""Authenticate bounded Stage227 records, all failures and retired identities."""
from pathlib import Path
import psutil
import replay_common_v1 as c

OUT=c.OUT/'final_disposition_01'


def close():
    a=c.bound();c.environment();ledger=[];paths=[c.AUTH,Path(__file__).resolve()]
    calls=0;records=0;candidate_logs=[];processes=[];tiny=None;full=None
    for launch_path in sorted(c.OUT.glob('*/launch.json')):
        folder=launch_path.parent;launch=c.read(launch_path)
        design_path=c.DESIGNS/(folder.name+'.json');d=c.read(design_path)
        assert launch['design_sha256']==c.sha(design_path)
        c.verify(d['inputs']);c.verify(d['sources']);paths += [launch_path,design_path]
        status='exact_launch_identity_retired'
        if psutil.pid_exists(launch['pid']):
            process=psutil.Process(launch['pid'])
            if process.create_time()==launch['created']:
                raise RuntimeError('Task-owned exact replay identity still exists: '+str(launch['pid']))
            status='exact_launch_identity_retired_pid_reused'
        processes.append(dict(pid=launch['pid'],created=launch['created'],command=launch['command'],status=status))
        if (folder/'failure.json').is_file():
            result=c.read(folder/'failure.json');reports=result['completed'];disposition='failed_preserved'
            paths.append(folder/'failure.json');c.verify(result['artifacts']);paths += [Path(p) for p in result['artifacts']]
        else:
            result=c.sealed(folder/'results.json');reports=result['reports'];assert result['passed']
            c.verify(result['artifacts']);paths += [folder/'results.json',folder/'completion.json']
            disposition='tiny_gate_passed' if folder.name.startswith('tiny') else 'local_fixed_pose_screen_complete'
            if folder.name.startswith('tiny'):tiny=result
            else:full=result
        assert result['new_trajectory_steps']==0
        for report in reports:
            assert c.sha(report['path'])==report['sha256'];paths.append(Path(report['path']))
            row=c.read(report['path']);assert row['physical_association_audit']['passed']
            if row['reuse_log'] is not None:
                assert row['reuse_audit']['passed'];candidate_logs.append(row['reuse_log'])
        calls+=result['outer_calls_attempted'];records+=len(reports)
        ledger.append(dict(attempt=folder.name,disposition=disposition,outer_calls_attempted=result['outer_calls_attempted'],
            completed_records=len(reports),error=result.get('error')))
    assert calls==c.used_outer_calls() and calls<=a['maximum_nonadvancing_outer_calls']
    for path in sorted((c.OUT/'preflight_01').glob('*.json')):
        row=c.read(path);assert row['outer_calls_attempted']==row['new_trajectory_steps']==0;paths.append(path)
        c.verify(row.get('sources',{}))
    logical=sum(x['logical_requests'] for x in candidate_logs);executed=sum(x['executed_requests'] for x in candidate_logs)
    reused=sum(x['reused_requests'] for x in candidate_logs);assert logical==executed+reused
    append_hits=sum(e.get('reused') is True and e.get('route_delta_receipt',{}).get('kind')=='failed_early_append' for x in candidate_logs for e in x['events'])
    mutations=None if tiny is None else tiny['actual_hit_mutation_controls']
    if tiny is not None:assert tiny['outer_calls_attempted']==4 and mutations['passed'] and mutations['controls_rejected']==32
    if full is not None:assert tiny is not None and full['outer_calls_attempted']==588 and full['qualification_fixtures']==98
    hashes={str(p):c.sha(p) for p in sorted(set(paths))};c.bound();c.verify(hashes)
    result=dict(stage='Stage227 final bounded route-evidence qualification',passed=True,utc=c.utc(),end_utc=a['end_utc'],
        authorization_sha256=c.sha(c.AUTH),shared_outer_calls_attempted=calls,maximum_outer_calls=a['maximum_nonadvancing_outer_calls'],
        completed_persisted_outer_records=records,attempts=ledger,processes=processes,
        tiny_qualified=tiny is not None,full_fixed_pose_equivalence_qualified=full is not None,
        all_persisted_original_physical_association_audits_passed=True,
        logical_semismooth_requests=logical,executed_semismooth_requests=executed,reused_requests=reused,append_qualified_hits=append_hits,
        actual_hit_mutation_controls=mutations,
        local_material_gain_passed=False if full is None else full['local_material_gain_passed'],
        overall_runtime_gain_fraction=None if full is None else full['overall_runtime_gain_fraction'],
        strata=None if full is None else full['strata'],
        archived_residual_differences=[] if full is None else full['archived_residual_differences'],
        raw_marshal_preflight_preserved=True,semantic_scalar_code_identity='All immutable recursive code fields and typed constant bits independently reconstructed from frozen qualified native source; raw marshal encoding retained diagnostically.',
        original_stage226_failures_and_gates_unchanged=True,
        fixture_domain='One saved sample0fibre segment, all66fallbacks plus32healthy controls; fallback-heavy local screen, not representative full-segment or campaign cost.',
        new_trajectory_steps=0,new_saved_transport_steps=0,production_authorized=False,
        difficult_placement_transfer_qualified=False,transition_qualified=False,restart_qualified=False,full_path_qualified=False,
        overnight_reopened=False,overnight_heartbeat_should_remain_paused=True,
        claim='Fixed-pose implementation/evidence and local-cost gates only. Complete-path/event accuracy, physical validation and meaningful shape/flow trends are not established by this screen.',
        artifacts=hashes)
    c.commit(OUT/'results.json',result);c.commit(OUT/'completion.json',dict(passed=True,results_sha256=c.sha(OUT/'results.json')))
    print('STAGE227_CLOSED',calls,'calls',reused,'validreuses','gain',result['overall_runtime_gain_fraction'],c.sha(OUT/'results.json'))


if __name__=='__main__':close()
