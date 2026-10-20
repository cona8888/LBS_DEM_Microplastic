"""Authenticate Stage226 evidence and close its bounded nonadvancing work."""
from pathlib import Path
import json, sys
import psutil
import replay_common_v1 as c

OUT=c.OUT/'final_disposition_01'


def close():
    auth=c.bound(); c.environment()
    designs=[c.DESIGNS/f'outer_replay_{i:02d}.json' for i in range(1,5)]
    paths=[c.AUTH,Path(__file__).resolve()]
    ledger=[]; attempted=0; completed=0; process_records=[]
    for i,design in enumerate(designs,1):
        d=c.read(design);c.verify(d['sources']);c.verify(d['inputs'])
        if 'prior_failed_inputs' in d:c.verify(d['prior_failed_inputs'])
        folder=c.OUT/f'outer_replay_{i:02d}'; launch=c.read(folder/'launch.json')
        assert launch['design_sha256']==c.sha(design)
        pid=launch['pid']; status='recorded_exact_identity_retired'
        if psutil.pid_exists(pid):
            p=psutil.Process(pid)
            if p.create_time()==launch['created']:
                raise RuntimeError('Exact task-owned replay identity still exists: '+str(pid))
            status='recorded_exact_identity_retired_pid_reused'
        process_records.append(dict(pid=pid,created=launch['created'],argv=launch['argv'],status=status))
        paths += [design,folder/'launch.json']
        if (folder/'failure.json').is_file():
            r=c.read(folder/'failure.json'); calls=r['outer_calls_attempted']; done=len(r['completed'])
            assert r['passed'] is False and r['new_trajectory_steps']==0
            c.verify({x['path']:x['sha256'] for x in r['completed']})
            paths += [folder/'failure.json']+[Path(x['path']) for x in r['completed']]
            ledger.append(dict(attempt=f'outer_replay_{i:02d}',disposition='failed_preserved',outer_calls_attempted=calls,records_completed=done,error=r['error']))
        else:
            assert i==4
            r=c.sealed(folder/'results.json');assert r['passed'] and r['new_trajectory_steps']==0
            c.verify(r['artifacts']);calls=r['outer_calls'];done=len(r['reports'])
            assert calls==done==588 and r['qualification_fixtures']==98
            assert r['strict_paired_all_scientific_fields_passed'] and r['unchanged_physics_association_audits_passed']
            paths += [folder/'results.json',folder/'completion.json']+[Path(p) for p in r['artifacts']]
            ledger.append(dict(attempt='outer_replay_04',disposition='fixed_pose_screen_complete',outer_calls_attempted=calls,records_completed=done))
        attempted+=calls;completed+=done
    for label in ('difference_diagnosis_02','difference_diagnosis_03'):
        folder=c.OUT/label;r=c.sealed(folder/'results.json');assert r['diagnosis_only'] and r['outer_calls']==2
        c.verify(r['artifacts']);paths += [folder/'results.json',folder/'completion.json']+[Path(p) for p in r['artifacts']]
        attempted+=2
        ledger.append(dict(attempt=label,disposition='diagnosis_only',outer_calls_attempted=2,new_trajectory_steps=0))
    bookkeeping=c.OUT/'difference_diagnosis_01/failure.json';r=c.read(bookkeeping)
    assert r['outer_calls']==0;paths.append(bookkeeping)
    ledger.append(dict(attempt='difference_diagnosis_01',disposition='bookkeeping_failure_preserved',outer_calls_attempted=0))
    assert attempted<=auth['maximum_nonadvancing_outer_calls']
    final=c.sealed(c.OUT/'outer_replay_04/results.json')
    reuse_logs=[c.read(x['path'])['reuse_log'] for x in final['reports'] if x['mode']=='reuse']
    logical=sum(x['logical_requests'] for x in reuse_logs);executed=sum(x['executed_requests'] for x in reuse_logs)
    reused=sum(x['reused_requests'] for x in reuse_logs)
    eligible=sum(e.get('cache_eligible') is True and e['executed'] for log in reuse_logs for e in log['events'])
    changed_certificate_repeats=[]
    for log in reuse_logs:
        previous={}
        for e in log['events']:
            key=(e['inner_call'],e.get('key_sha256'))
            origin=previous.get(key)
            if origin is not None and origin.get('cache_eligible') and origin.get('certificate_after_sha256')!=e.get('certificate_before_sha256'):
                changed_certificate_repeats.append(dict(inner_call=e['inner_call'],first_event=origin['id'],next_event=e['id'],
                    changed_channels=[k for k,v in origin['certificate_binding_after'].items() if v!=e['certificate_binding_before'].get(k)]))
            previous[key]=e
    assert logical==executed+reused and reused==final['reuse_requests']
    qualified_hit_controls=final['witness_mutation_controls'] is not None
    assert qualified_hit_controls or reused==0
    artifact_hashes={str(p):c.sha(p) for p in sorted(set(paths))}
    c.bound();c.verify(artifact_hashes)
    result=dict(stage='Stage226 final bounded nonadvancing contact disposition',passed=True,utc=c.utc(),
        authorization_sha256=c.sha(c.AUTH),end_utc=auth['end_utc'],
        shared_outer_calls_attempted=attempted,maximum_outer_calls=auth['maximum_nonadvancing_outer_calls'],
        completed_persisted_outer_screen_records=completed,attempts=ledger,processes=process_records,
        fixed_pose_comparison_passed=final['exact_outer_replay_passed'],physics_association_passed=True,
        logical_semismooth_requests=logical,executed_semismooth_requests=executed,reused_requests=reused,
        completed_cache_eligible_exhausted_searches=eligible,
        repeated_same_inner_same_key_with_changed_certificate=len(changed_certificate_repeats),
        changed_certificate_repeats=changed_certificate_repeats,
        actual_hit_mutation_controls_ran=qualified_hit_controls,
        local_material_gain_passed=final['local_material_gain_passed'],
        overall_runtime_gain_fraction=final['overall_runtime_gain_fraction'],strata=final['strata'],
        fixture_domain='All66fallback poses and32healthy controls from one saved sample0fibresegment; deliberately fallback-heavy sample, not representative campaign cost.',
        archived_residual_differences=final['archived_residual_differences'],
        prior_failures_remain_failed=True,archived_residual_discrepancy_precise_cause_resolved=False,
        new_trajectory_steps=0,new_saved_transport_steps=0,production_authorized=False,
        difficult_placement_transfer_qualified=False,transition_qualified=False,restart_qualified=False,full_path_qualified=False,
        overnight_reopened=False,overnight_heartbeat_should_remain_paused=True,
        claim='Exact paired fixed-pose verification and measured local cost only. No successful production optimization, campaign affordability or shape/flow trend follows.',
        artifacts=artifact_hashes)
    c.commit(OUT/'results.json',result)
    c.commit(OUT/'completion.json',dict(passed=True,results_sha256=c.sha(OUT/'results.json')))
    print('STAGE226_CLOSED',attempted,'attempted calls',reused,'valid reuses','gain',result['overall_runtime_gain_fraction'],c.sha(OUT/'results.json'))


if __name__=='__main__':close()
