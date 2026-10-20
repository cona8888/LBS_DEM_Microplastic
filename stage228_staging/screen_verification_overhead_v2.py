"""Conditional fixed-pose equivalence/cost screen; zero transport steps.

Qualification/warmup and profiled diagnostics are excluded from these timings.
Each candidate timing includes the complete live binding, trace and proof cost.
"""
from pathlib import Path
import os, sys, time, traceback
import replay_verification_overhead_v4 as b

c=b.c
DESIGN=c.DESIGNS/'full_replay_01.json'
OUT=c.OUT/'full_replay_01'


def prepare():
    a=c.bound();c.environment()
    tiny=c.sealed(b.OUT/'results.json')
    assert tiny['passed'] and tiny['tiny_qualified'] and tiny['actual_hit_mutation_controls']['passed']
    assert tiny['actual_hit_mutation_controls']['controls_rejected']==32
    assert tiny['live_metadata_controls']['passed'] and tiny['live_metadata_controls']['controls_checked']>=17,'Fresh live metadata, mutable binding, operand and cutoff controls'
    metadata=c.sealed(c.OUT/'metadata_controls_03/results.json')
    assert metadata['passed'] and metadata['live_metadata_controls']['passed'],'Independent typed metadata guard qualification'
    assert len(metadata['immutable_metadata_controls'])>=8 and all(x['passed'] for x in metadata['immutable_metadata_controls'])
    assert metadata['native_type_control']['passed']
    assert len(metadata['native_attribute_controls'])==2
    assert all(x['finally_restored'] and x['exact_allowed_type'] and x['full_before_sha256']==x['full_after_sha256']
        and all(test['passed'] for test in x['tests']) for x in metadata['native_attribute_controls'])
    assert all(x['keyable'] and x['repeated_keys_exact'] for x in metadata['configured_live_bindings'])
    assert metadata.get('candidate_guard_qualified',True) is True
    c.verify(metadata.get('sources',{}));c.verify(metadata.get('inputs',{}))
    c.verify(tiny['artifacts'])
    prior=c.used_outer_calls();assert prior+588<=a['maximum_nonadvancing_outer_calls']
    inventory=c.read(b.FIXTURE_DIR/'fixtures.json');c.verify(inventory['inputs']);c.verify(inventory['sources'])
    assert len(inventory['fixtures'])==98 and inventory['counts']['all_recorded_fallbacks']==66
    assert sum(row['stratum']=='recorded_fallback' for row in inventory['fixtures'])==66
    assert sum(row['stratum']=='healthy_early_success' for row in inventory['fixtures'])==32
    inputs=[c.AUTH,b.DESIGN,b.OUT/'results.json',b.OUT/'completion.json',b.FIXTURE_DIR/'fixtures.json',b.FIXTURE_DIR/'results.json',b.FIXTURE_DIR/'completion.json',c.OUT/'metadata_controls_03/results.json',c.OUT/'metadata_controls_03/completion.json']
    c.commit(DESIGN,dict(stage='Stage228 separately frozen conditional full verification-overhead screen',utc=c.utc(),
        authorization_sha256=c.sha(c.AUTH),end_utc=a['end_utc'],prior_outer_calls_attempted=prior,
        maximum_outer_calls=588,qualification_pairs=98,qualification_outer_calls=196,timing_repetitions=2,timing_outer_calls=392,
        minimum_material_gain_fraction=a['minimum_material_gain_fraction'],modes=['original','reuse'],
        inputs={str(p):c.sha(p) for p in inputs},sources={**inventory['sources'],**{str(p):c.sha(p) for p in [*b.source_files(),Path(__file__).resolve()]}},
        strict_paired_scientific_fields_including_residuals=True,unchanged_original_physical_gates=True,
        declared_timing_field_exclusions=sorted(b.TIMING_FIELDS),
        timed_scope='Unobserved current Stage194 baseline versus entire candidate outer-call cost including exact bindings, trace, witness and append verification; all pairs qualified/warmed before two alternating unprofiled timing repetitions. Scope construction, independent auditing, serialization and warmup excluded. Diagnostic profile timings are not pooled.',
        full_cost_scope='Separately measure scoped_transaction_seconds including complete context entry, outer contact solve, telemetry capture and context exit; exclude post-call independent auditing/serialization. Setup is included per replay call, with no production amortization assumption.',
        timing_component_fields=['scope_entry_seconds','scope_exit_seconds','telemetry_capture_seconds','scoped_transaction_seconds'],
        domain='All66fallback poses plus32healthy controls from one saved fibre segment; deliberately fallback-heavy sample, no representative campaign-cost inference.',
        required_reporting='Report each stratum including healthy runtime overhead; aggregate material gain alone cannot qualify campaign affordability.',
        production_authorized=False,new_trajectory_steps=0,new_saved_transport_steps=0,simulation_dispatch=False))
    print('PREPARED_CONDITIONAL_FULL_SCREEN',c.sha(DESIGN),'max588calls',flush=True)


def run():
    a=c.bound();c.environment();d=c.read(DESIGN);c.verify(d['inputs']);c.verify(d['sources'])
    assert d['authorization_sha256']==c.sha(c.AUTH) and c.used_outer_calls()==d['prior_outer_calls_attempted']
    p=b.psutil.Process();p.cpu_affinity([a['logical_cpu']])
    c.commit(OUT/'launch.json',dict(utc=c.utc(),pid=os.getpid(),created=p.create_time(),argv=sys.argv,command=p.cmdline(),
        design_sha256=c.sha(DESIGN),python=sys.version,platform=b.platform.platform(),affinity=p.cpu_affinity(),
        threads={k:os.environ[k] for k in ('OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS')},numpy_version=b.np.__version__,new_trajectory_steps=0))
    reports=[];calls=0
    try:
        inventory=c.read(b.FIXTURE_DIR/'fixtures.json');rows=inventory['fixtures']
        b.JOB.parent.b.old.parent.configure();b.STACK.candidate.warm()
        for phase,repeat in [('qualification',None),('timing',0),('timing',1)]:
            for index,row in enumerate(rows):
                paired=None;mode_order=d['modes'] if (index+(repeat or 0))%2==0 else list(reversed(d['modes']))
                for mode in mode_order:
                    c.bound();assert calls<d['maximum_outer_calls'] and calls+d['prior_outer_calls_attempted']<a['maximum_nonadvancing_outer_calls'];calls+=1
                    item=b.call(inventory,row,mode,d['end_utc'])
                    assert item['scoped_transaction_seconds']>=item['seconds']>=0
                    assert all(item[key]>=0 for key in d['timing_component_fields'])
                    now=b.scientific(item['force_audit_fixture'])
                    if paired is None:paired=now
                    else:assert c.digest(paired)==c.digest(now),'Strict paired full scientific fixture including residuals and original route records'
                    name=f'{index:03d}_{mode}.json' if repeat is None else f'{repeat}_{index:03d}_{mode}.json'
                    path=OUT/phase/name;c.commit(path,item)
                    log=item['reuse_log']
                    reports.append(dict(phase=phase,repeat=repeat,fixture_id=row['fixture_id'],stratum=row['stratum'],mode=mode,
                        seconds=item['seconds'],scope_entry_seconds=item['scope_entry_seconds'],scope_exit_seconds=item['scope_exit_seconds'],
                        telemetry_capture_seconds=item['telemetry_capture_seconds'],scoped_transaction_seconds=item['scoped_transaction_seconds'],
                        path=str(path),sha256=c.sha(path),
                        reused_requests=0 if log is None else log['reused_requests'],archival_residual_differences=item['archival_residual_differences']))
                if index%16==0:print('FULL_EXACT_PAIRS',phase,repeat,index+1,'calls',calls,flush=True)
        assert calls==588
        assert sum(x['phase']=='qualification' for x in reports)==196
        assert sum(x['phase']=='timing' for x in reports)==392
        c.bound();c.verify(d['inputs']);c.verify(d['sources'])
        strata={}
        for stratum in sorted({x['stratum'] for x in rows}):
            timed=[x for x in reports if x['phase']=='timing' and x['stratum']==stratum]
            counts={mode:sum(x['mode']==mode for x in timed) for mode in d['modes']}
            times={mode:sum(x['seconds'] for x in timed if x['mode']==mode) for mode in d['modes']}
            assert counts['original']==counts['reuse'] and counts['original']>0
            ratio=times['reuse']/times['original'];gain=1-ratio
            components={key:{mode:sum(x[key] for x in timed if x['mode']==mode) for mode in d['modes']} for key in d['timing_component_fields']}
            transaction=components['scoped_transaction_seconds'];transaction_ratio=transaction['reuse']/transaction['original'];transaction_gain=1-transaction_ratio
            strata[stratum]=dict(seconds=times,timed_outer_calls=counts,
                mean_seconds={mode:times[mode]/counts[mode] for mode in d['modes']},
                candidate_to_original_runtime_ratio=ratio,runtime_gain_fraction=gain,
                local_material_gain_passed=gain>=d['minimum_material_gain_fraction'],timing_components_seconds=components,
                scoped_transaction_seconds=transaction,scoped_transaction_runtime_gain_fraction=transaction_gain,
                scoped_transaction_candidate_to_original_runtime_ratio=transaction_ratio,
                scoped_transaction_mean_seconds={mode:transaction[mode]/counts[mode] for mode in d['modes']},
                scoped_transaction_material_gain_passed=transaction_gain>=d['minimum_material_gain_fraction'])
        first=sum(x['seconds']['original'] for x in strata.values());second=sum(x['seconds']['reuse'] for x in strata.values())
        gain=1-second/first
        transaction_first=sum(x['scoped_transaction_seconds']['original'] for x in strata.values())
        transaction_second=sum(x['scoped_transaction_seconds']['reuse'] for x in strata.values())
        transaction_gain=1-transaction_second/transaction_first
        c.commit(OUT/'results.json',dict(passed=True,utc=c.utc(),design_sha256=c.sha(DESIGN),outer_calls_attempted=calls,
            qualification_fixtures=len(rows),qualification_outer_calls_excluded_from_timings=196,timing_outer_calls=392,timing_repetitions=2,
            reports=reports,artifacts={x['path']:x['sha256'] for x in reports},
            exact_paired_all_scientific_outputs=True,unchanged_independent_physics_association_audits=True,
            reused_requests=sum(x['reused_requests'] for x in reports),strata=strata,overall_runtime_gain_fraction=gain,
            local_material_gain_passed=gain>=d['minimum_material_gain_fraction'],
            all_strata_material_gain_passed=all(x['local_material_gain_passed'] for x in strata.values()),
            overall_scoped_transaction_runtime_gain_fraction=transaction_gain,
            scoped_transaction_material_gain_passed=transaction_gain>=d['minimum_material_gain_fraction'],
            all_strata_scoped_transaction_material_gain_passed=all(x['scoped_transaction_material_gain_passed'] for x in strata.values()),
            both_outer_and_transaction_all_strata_material_gain_passed=all(x['local_material_gain_passed'] and x['scoped_transaction_material_gain_passed'] for x in strata.values()),
            metadata_controls_source=str(c.OUT/'metadata_controls_03/results.json'),
            minimum_material_gain_fraction=d['minimum_material_gain_fraction'],
            archived_residual_differences=[v for x in reports for v in x['archival_residual_differences']],
            actual_hit_mutation_controls_source=str(b.OUT/'results.json'),profiled_timings_pooled=False,
            new_trajectory_steps=0,new_saved_transport_steps=0,
            production_authorized=False,difficult_placement_transfer_qualified=False,transition_qualified=False,restart_qualified=False,full_path_qualified=False,
            claim='Exact fixed-pose implementation screen and local unprofiled outer and complete scoped-transaction costs only, conditioned on tiny actual-hit and independent live typed metadata qualification. Sample is deliberately fallback-heavy. Setup is included in transaction costs; no production amortization assumption. Every stratum and timing scope is reported; shifting work outside the outer timer or favorable aggregate alone does not qualify campaign affordability, complete-path accuracy or shape/flow inference.'))
        c.commit(OUT/'completion.json',dict(passed=True,results_sha256=c.sha(OUT/'results.json')))
        print('FULL_SCREEN_COMPLETE',calls,'gain',gain,c.sha(OUT/'results.json'),flush=True)
    except Exception as error:
        observed=b.failure_output(error);extra={}
        if observed is not None:
            path=OUT/'failed_call.json';c.commit(path,observed);extra[str(path)]=c.sha(path)
        c.commit(OUT/'failure.json',dict(passed=False,utc=c.utc(),error=repr(error),traceback=traceback.format_exc(),
            outer_calls_attempted=calls,completed=reports,artifacts=extra,new_trajectory_steps=0,production_authorized=False))
        raise


if __name__=='__main__':
    if sys.argv[1:]==['prepare']:prepare()
    elif sys.argv[1:]==['run']:run()
    else:raise ValueError('prepare | run')
