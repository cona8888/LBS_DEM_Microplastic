"""Authenticate Stage228 calls, negative evidence and retired launch identities."""
from pathlib import Path
import psutil
import verification_common_v1 as c
OUT=c.OUT/'final_disposition_01'
def close():
    a=c.bound();c.environment();ledger=[];paths=[c.AUTH,Path(__file__).resolve()]
    calls=records=0;logs=[];processes=[];tiny=full=profile=None
    for launch_path in sorted(c.OUT.glob('*/launch.json')):
        folder=launch_path.parent;launch=c.read(launch_path)
        design_path=c.DESIGNS/(folder.name+'.json');d=c.read(design_path)
        assert launch['design_sha256']==c.sha(design_path)
        c.verify(d['inputs']);c.verify(d['sources']);paths += [launch_path,design_path]
        status='exact_launch_identity_retired'
        if psutil.pid_exists(launch['pid']):
            process=psutil.Process(launch['pid'])
            if process.create_time()==launch['created']:
                assert process.cmdline()==launch['command']
                raise RuntimeError('Task-owned exact replay identity still exists: '+str(launch['pid']))
            status='exact_launch_identity_retired_pid_reused'
        processes.append(dict(pid=launch['pid'],created=launch['created'],command=launch['command'],status=status))
        if (folder/'failure.json').is_file():
            result=c.read(folder/'failure.json');reports=result['completed'];disposition='failed_preserved'
        else:
            result=c.sealed(folder/'results.json');reports=result['reports'];assert result['passed']
            disposition='qualified_local_gate'
            if folder.name.startswith('tiny'):tiny=result
            elif folder.name.startswith('full'):full=result
            elif folder.name.startswith('profile'):profile=result
        c.verify(result['artifacts']);assert result['new_trajectory_steps']==0
        for report in reports:
            assert c.sha(report['path'])==report['sha256']
            row=c.read(report['path']);assert row['physical_association_audit']['passed']
            if row['reuse_log'] is not None:
                assert row['reuse_audit']['passed'];logs.append(row['reuse_log'])
        paths.extend(p for p in folder.rglob('*') if p.is_file())
        calls+=result['outer_calls_attempted'];records+=len(reports)
        ledger.append(dict(attempt=folder.name,disposition=disposition,outer_calls_attempted=result['outer_calls_attempted'],completed_records=len(reports),error=result.get('error')))
    assert calls==c.used_outer_calls() and calls<=a['maximum_nonadvancing_outer_calls']
    pure=[]
    for leaf in ('binding_controls_baseline_01','profile_review_01','metadata_controls_01','metadata_controls_02','metadata_controls_03','fingerprint_diagnosis_01','fingerprint_diagnosis_02','preflight_02'):
        folder=c.OUT/leaf
        if (folder/'results.json').is_file():
            result=c.sealed(folder/'results.json');c.verify(result.get('sources',{}));c.verify(result.get('inputs',{}))
            assert result.get('outer_calls_attempted',0)==0
            pure.append(dict(attempt=leaf,results_sha256=c.sha(folder/'results.json'),candidate_guard_qualified=result.get('candidate_guard_qualified')))
            paths.extend(p for p in folder.rglob('*') if p.is_file())
    prepared=[]
    for design in sorted(c.DESIGNS.glob('full_replay_*.json')):
        d=c.read(design);c.verify(d['sources']);c.verify(d['inputs']);paths.append(design)
        if not (c.OUT/design.stem/'launch.json').exists():
            prepared.append(dict(design=str(design),sha256=c.sha(design),status='prepared_not_started',reason='Remaining bounded window reserved for final authentication; no full cost qualification.'))
    logical=sum(x['logical_requests'] for x in logs);executed=sum(x['executed_requests'] for x in logs);reused=sum(x['reused_requests'] for x in logs)
    assert logical==executed+reused
    append_hits=sum(e.get('reused') is True and e.get('route_delta_receipt',{}).get('kind')=='failed_early_append' for x in logs for e in x['events'])
    if tiny is not None:
        assert tiny['outer_calls_attempted']==4 and tiny['actual_hit_mutation_controls']['controls_rejected']==32
        assert tiny['live_metadata_controls']['passed']
    if full is not None:assert tiny is not None and full['outer_calls_attempted']==588 and full['qualification_fixtures']==98
    hashes={str(p):c.sha(p) for p in sorted(set(paths))};c.bound();c.verify(hashes)
    result=dict(stage='Stage228 final bounded verification-overhead qualification',passed=True,utc=c.utc(),end_utc=a['end_utc'],authorization_sha256=c.sha(c.AUTH),
        shared_outer_calls_attempted=calls,maximum_outer_calls=a['maximum_nonadvancing_outer_calls'],completed_persisted_outer_records=records,attempts=ledger,pure_diagnostics=pure,prepared_not_started=prepared,processes=processes,
        profile_gate_qualified=profile is not None,profiled_timings_pooled=False,tiny_qualified=tiny is not None,full_fixed_pose_equivalence_qualified=full is not None,
        all_persisted_original_physical_association_audits_passed=True,logical_semismooth_requests=logical,executed_semismooth_requests=executed,reused_requests=reused,append_qualified_hits=append_hits,
        actual_hit_mutation_controls=None if tiny is None else tiny['actual_hit_mutation_controls'],live_metadata_controls=None if tiny is None else tiny['live_metadata_controls'],
        local_material_gain_passed=False if full is None else full['local_material_gain_passed'],all_strata_material_gain_passed=False if full is None else full['all_strata_material_gain_passed'],
        overall_runtime_gain_fraction=None if full is None else full['overall_runtime_gain_fraction'],strata=None if full is None else full['strata'],
        overall_scoped_transaction_runtime_gain_fraction=None if full is None else full.get('overall_scoped_transaction_runtime_gain_fraction'),
        all_strata_scoped_transaction_material_gain_passed=False if full is None else full.get('all_strata_scoped_transaction_material_gain_passed',False),
        inherited_in_place_closure_guard_negative_evidence_preserved=True,immutable_metadata_identity_guard_and_live_mutable_values_required=True,
        original_stage226_and_stage227_records_preserved=True,fixture_domain='One saved sample0fibre segment, all66fallbacks plus32healthy controls; deliberately fallback-heavy, no representative segment/campaign cost.',
        new_trajectory_steps=0,new_saved_transport_steps=0,production_authorized=False,difficult_placement_transfer_qualified=False,transition_qualified=False,restart_qualified=False,full_path_qualified=False,
        overnight_reopened=False,overnight_heartbeat_should_remain_paused=True,
        claim='Bounded nonadvancing implementation/evidence and local cost screen. No complete-path/event accuracy, physical validation, campaign affordability or shape/flow trend claim.',artifacts=hashes)
    c.commit(OUT/'results.json',result);c.commit(OUT/'completion.json',dict(passed=True,results_sha256=c.sha(OUT/'results.json')))
    print('STAGE228_CLOSED',calls,'calls',reused,'validreuses',c.sha(OUT/'results.json'),flush=True)
if __name__=='__main__':close()
