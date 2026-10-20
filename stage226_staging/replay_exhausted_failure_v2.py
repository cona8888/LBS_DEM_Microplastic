"""Fixed-pose replay and local cost screen; never calls a trajectory integrator."""
from contextlib import ExitStack
from datetime import datetime
from pathlib import Path
import copy, json, os, platform, sys, time, traceback
import replay_common_v1 as c

sys.path.insert(0,str(c.ROOT/'stage222_staging'))
import overnight_campaign_v1 as n
import numpy as np
import psutil
import exhausted_failure_memo_v2 as candidate
import audit_failure_reuse_v1 as reuse_audit

JOB=n.job
RUNTIME=JOB.parent.engine.runtime
STACK=n.source.stack
ASSOCIATION=STACK.frozen.stack.auditor
FIXTURE_DIR=c.OUT/'fixtures_01'
DESIGN=c.DESIGNS/'outer_replay_02.json'
OUT=c.OUT/'outer_replay_02'
TIMING_FIELDS=frozenset(('certificate_seconds','wall_s'))


def plain(value):
    if isinstance(value,np.ndarray):return value.tolist()
    if isinstance(value,np.generic):return value.item()
    if isinstance(value,dict):return {k:plain(v) for k,v in value.items()}
    if isinstance(value,(tuple,list)):return [plain(v) for v in value]
    return value


def scientific(value):
    if isinstance(value,dict):return {k:scientific(v) for k,v in value.items() if k not in TIMING_FIELDS}
    if isinstance(value,list):return [scientific(v) for v in value]
    return plain(value)


def archival_scientific(value):
    # Recorded residual diagnostics can differ for reconstructed JSON operands.
    # This is only the archive comparator; paired health remains fully exact.
    if isinstance(value,dict):return {k:archival_scientific(v) for k,v in value.items() if k not in TIMING_FIELDS and k!='residual'}
    if isinstance(value,list):return [archival_scientific(v) for v in value]
    return plain(value)


def archival_residual_differences(got,wanted,path='health'):
    if not isinstance(got,dict) or not isinstance(wanted,dict):return []
    output=[]
    for key in got.keys() & wanted.keys():
        if key=='residual' and got[key]!=wanted[key]:
            output.append(dict(path=path+'.residual',actual=float(got[key]),archived=float(wanted[key]),difference=float(got[key]-wanted[key])))
        elif isinstance(got[key],dict):output+=archival_residual_differences(got[key],wanted[key],path+'.'+key)
    return output


def policy_binding(inventory):
    return dict(contract_sha256=inventory['saved_numerical_policy_contract_sha256'],
        saved_binding=inventory['saved_binding'],minimum_gap_semantics=inventory['saved_minimum_gap_semantics'],
        classifier=STACK.local.policy_scope.policy.classify,
        prepare=JOB.observer.backend.stage41._prepare_geometry)


def certificate_binding():
    # These are the complete numeric evidence channels cleared by the original
    # runner. Compare content hashes as well as counts; never replay an emission.
    return {name:dict(count=len(values),sha256=c.digest(plain(values))) for name,values in (
        ('roundoff',JOB.parent.fix.telemetry),('fast_attempts',JOB.fast.attempts),
        ('fast_telemetry',JOB.fast.telemetry),('reduced',JOB.fast.old.telemetry),
        ('fallback',JOB.capture.records),('model_calls',JOB.parent.model.calls),
        ('sweep',JOB.prior.candidate.records),('stage119',RUNTIME._calls))}


def verify_identity_domain(row):
    prepare=row['saved_physical_certificates']['normal_gap_prepare']
    assert prepare['raw_gaps_m']==prepare['effective_gaps_m']
    assert all(not x['classification']['changed'] and not x['classification']['sphere'] for x in prepare['metadata'])
    assert row['outer_inputs'][6]==prepare['contacts']
    J,g,frames=JOB.observer.backend.stage41._prepare_geometry(copy.deepcopy(row['outer_inputs'][6]),row['outer_inputs'][7])
    system=row['resolved_inner_systems'][0]
    assert J.tobytes()==np.asarray(system['jacobian'],float).tobytes()
    assert g.tobytes()==np.asarray(system['gaps_m'],float).tobytes()
    return dict(fibre_operand_policy_exact_identity=True,raw_geometry_provenance='Authenticated saved reference, not recomputed geometry membership.',
                native_jacobian_and_signed_gaps_exact=True)


def call(inventory,row,mode,end_utc):
    c.bound();identity=verify_identity_domain(row)
    JOB.clear_telemetry();RUNTIME._calls.clear();JOB.fast.capture_systems=True
    RUNTIME.probe.RECOVERY.portfolio.set_recovery_mode(False)
    args=copy.deepcopy(row['outer_inputs']);before=c.digest(args)
    epoch=datetime.fromisoformat(end_utc).timestamp();memo=None
    with ExitStack() as scope:
        scope.enter_context(STACK.frozen.stack.repair.scope(RUNTIME,True,epoch))
        scope.enter_context(STACK.candidate.scope('compiled_direct'))
        if mode=='original':
            scope.enter_context(candidate.previous.scope(RUNTIME,True,epoch))
        else:
            memo=scope.enter_context(candidate.scope(RUNTIME,True,epoch,
                policy_binding=lambda:policy_binding(inventory),certificate_binding=certificate_binding,reuse=True))
        scope.enter_context(JOB.prior.p.hot.scope())
        scope.enter_context(JOB.parent.fix.scope())
        scope.enter_context(JOB.deadline.scope(RUNTIME,end_utc,True))
        scope.enter_context(JOB.capture.scope(RUNTIME,True))
        scope.enter_context(JOB.prior.candidate.scope())
        trace=scope.enter_context(JOB.observer.scope(RUNTIME,True))
        scope.enter_context(RUNTIME.repair_scope())
        if memo is not None:scope.enter_context(memo.inner_scope())
        tick=time.perf_counter()
        answer=JOB.observer.backend.inertial_contact_step(*args)
        seconds=time.perf_counter()-tick
        fixture=dict(contact_trial_trace=copy.deepcopy(trace),
            rows=[dict(velocity_generalized=np.asarray(answer[0]).tolist(),active_contact_ids=[int(x[0]) for x in args[6]])],
            sweep_certificates=[dict(dt_s=args[8])],early_attempts=copy.deepcopy(JOB.fast.attempts),
            fallback_systems=copy.deepcopy(JOB.capture.records),repairs=copy.deepcopy(JOB.fast.old.telemetry),
            result=dict(stage119_repair_calls=copy.deepcopy(RUNTIME._calls)))
    assert c.digest(args)==before,'Frozen outer input mutated'
    expected=row['expected_outer_outputs']
    assert np.asarray(answer[0]).tobytes()==np.asarray(expected['velocity'],float).tobytes(),'Original saved outer velocity bits'
    assert c.digest(archival_scientific(answer[1]))==c.digest(archival_scientific(expected['health'])),'Original saved mechanical health/forces/branch'
    archival_differences=archival_residual_differences(answer[1],expected['health'])
    audit=ASSOCIATION.evaluate(fixture,row['force_audit_before'])
    assert audit['passed'],'Unchanged independent physical/association audit'
    observed=fixture['contact_trial_trace']['detailed_trials'][0]['inner_systems']
    assert len(observed)==len(row['resolved_inner_systems'])
    for got,wanted in zip(observed,row['resolved_inner_systems']):
        for key in ('vfree','mobility','jacobian','gaps_m','velocity'):
            assert np.asarray(got[key],float).tobytes()==np.asarray(wanted[key],float).tobytes(),key+' exact recurrence'
        assert c.digest(archival_scientific(got['health']))==c.digest(archival_scientific(wanted['health'])),'Exact archived selected inner force/branch'
        archival_differences+=archival_residual_differences(got['health'],wanted['health'],f"inner{got['inner_index']}.health")
    witness_audit=None
    if memo is not None:
        witness_audit=reuse_audit.audit(plain(memo),expected_deadline=epoch)
        assert witness_audit['passed']
    return plain(dict(fixture_id=row['fixture_id'],stratum=row['stratum'],mode=mode,
        seconds=seconds,identity=identity,exact_archived_mechanical_outputs_and_inner_operands=True,physical_association_audit=audit,
        force_audit_fixture=fixture,reuse_log=memo,reuse_audit=witness_audit,archival_residual_differences=archival_differences,new_trajectory_steps=0))


def source_files():
    paths={Path(__file__).resolve(),Path(c.__file__).resolve(),Path(candidate.__file__).resolve(),Path(reuse_audit.__file__).resolve()}
    for module in list(sys.modules.values()):
        file=getattr(module,'__file__',None)
        if file:
            path=Path(file)
            if path.suffix=='.py' and path.is_file() and c.ROOT in path.resolve().parents:paths.add(path.resolve())
    return sorted(paths)


def prepare():
    authorization=c.bound();c.environment()
    fixture_receipt=c.sealed(FIXTURE_DIR/'results.json');assert fixture_receipt['passed']
    inventory=c.read(FIXTURE_DIR/'fixtures.json');c.verify(inventory['inputs']);c.verify(inventory['sources'])
    assert inventory['counts']['all_recorded_fallbacks']==66 and len(inventory['fixtures'])==98
    c.commit(DESIGN,dict(stage='Stage226 exact nonadvancing outer replay',utc=c.utc(),
        authorization_sha256=c.sha(c.AUTH),end_utc=authorization['end_utc'],maximum_outer_calls=588,
        shared_maximum_outer_calls=authorization['maximum_nonadvancing_outer_calls'],
        modes=['original','reuse'],warmup_pairs=98,timing_repetitions=2,planned_outer_calls=588,
        inputs={str(p):c.sha(p) for p in (c.AUTH,FIXTURE_DIR/'fixtures.json',FIXTURE_DIR/'results.json',FIXTURE_DIR/'completion.json')},
        sources={**inventory['sources'],**{str(p):c.sha(p) for p in source_files()}},
        timed_scope='Actual current unobserved Stage194 route versus complete candidate including key, seed exception trace, witness and cache costs. Scope construction, audits, serialization and warmup excluded; fixed-pose cost only.',
        unchanged_equations_and_gates=True,declared_timing_field_exclusions=sorted(TIMING_FIELDS),
        prospective_comparator_correction='Attempt01 remains failed: original and candidate share a reconstructed within-pose archived residual discrepancy. Require exact paired scientific force/audit fixtures including all residuals, exact archived mechanical outputs/branches/inner operands, record every archived residual difference and retain unchanged independent physical ceilings. No claim about precise cause.',
        prior_failed_inputs={str(p):c.sha(p) for p in (c.OUT/'outer_replay_01/failure.json',c.OUT/'difference_diagnosis_02/results.json',c.OUT/'difference_diagnosis_02/completion.json')},
        minimum_material_gain_fraction=authorization['minimum_material_gain_fraction'],
        fixture_domain='One saved fibre contact segment; every recorded fallback association plus32healthy controls. Difficult other-placement transfer not qualified.',
        new_trajectory_steps=0,production_authorized=False,simulation_dispatch=False))
    print('PREPARED_FIXED_POSE_REPLAY',c.sha(DESIGN),588,'maximum calls, zero trajectories')


def key_controls():
    base=np.array([0.,1.],dtype=np.float64);key=candidate._array_key(base)
    assert key==candidate._array_key(base.copy())
    changed=base.copy();changed[0]=-0.;assert key!=candidate._array_key(changed)
    onebit=base.copy();onebit[1]=np.nextafter(onebit[1],np.inf);assert key!=candidate._array_key(onebit)
    square=np.arange(9.,dtype=float).reshape(3,3)
    assert candidate._array_key(square)!=candidate._array_key(np.asfortranarray(square))
    assert candidate._scalar_key(1.)!=candidate._scalar_key(float(np.nextafter(1.,np.inf)))
    assert candidate._scalar_key(0.)!=candidate._scalar_key(-0.)
    assert candidate._scalar_key(1)!=candidate._scalar_key(np.int64(1))
    for bad in (np.array([np.nan]),np.array([1.],np.float32),[0.,1.]):
        try:candidate._array_key(bad)
        except ValueError:pass
        else:raise AssertionError('Ineligible array accepted')
    return dict(passed=True,one_bit_signed_zero_layout_dtype_scalar_and_nonfinite_controls=True)


def run():
    authorization=c.bound();c.environment();d=c.read(DESIGN);c.verify(d['inputs']);c.verify(d['sources']);c.verify(d['prior_failed_inputs'])
    assert d['authorization_sha256']==c.sha(c.AUTH)
    psutil.Process().cpu_affinity([authorization['logical_cpu']])
    c.commit(OUT/'launch.json',dict(pid=os.getpid(),created=psutil.Process().create_time(),argv=sys.argv,
        utc=c.utc(),design_sha256=c.sha(DESIGN),python=sys.version,platform=platform.platform(),
        affinity=psutil.Process().cpu_affinity(),threads={k:os.environ[k] for k in ('OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS')},
        numpy_version=np.__version__,new_trajectory_steps=0))
    inventory=c.read(FIXTURE_DIR/'fixtures.json');rows=inventory['fixtures'];reports=[];calls=0;guards=None
    try:
        controls=key_controls();JOB.parent.b.old.parent.configure();STACK.candidate.warm()
        # Every fixture gets both full routes outside measured scope before
        # subsequent timings. Preserve exactness/audit evidence from this pair.
        for index,row in enumerate(rows):
            paired=None
            for mode in (d['modes'] if index%2==0 else list(reversed(d['modes']))):
                c.bound();assert calls<d['maximum_outer_calls'];calls+=1
                item=call(inventory,row,mode,d['end_utc'])
                observed_scientific=scientific(item['force_audit_fixture'])
                if paired is None:paired=observed_scientific
                else:assert c.digest(paired)==c.digest(observed_scientific),'Strict paired full scientific fixture including residuals'
                path=OUT/'qualification'/f'{index:03d}_{mode}.json';c.commit(path,item)
                reports.append(dict(phase='qualification',fixture_id=row['fixture_id'],stratum=row['stratum'],mode=mode,
                    seconds=item['seconds'],path=str(path),sha256=c.sha(path),archival_residual_differences=item['archival_residual_differences'],reused_requests=0 if item['reuse_log'] is None else item['reuse_log']['reused_requests']))
                if guards is None and item['reuse_log'] is not None and item['reuse_log']['reused_requests']:
                    guards=reuse_audit.mutation_checks(item['reuse_log'],expected_deadline=datetime.fromisoformat(d['end_utc']).timestamp())
            if index%8==0:print('EXACT_FIXED_POSES',index+1,'calls',calls,flush=True)
        for repeat in range(d['timing_repetitions']):
            for index,row in enumerate(rows):
                paired=None
                for mode in (d['modes'] if (index+repeat)%2==0 else list(reversed(d['modes']))):
                    c.bound();assert calls<d['maximum_outer_calls'];calls+=1
                    item=call(inventory,row,mode,d['end_utc'])
                    observed_scientific=scientific(item['force_audit_fixture'])
                    if paired is None:paired=observed_scientific
                    else:assert c.digest(paired)==c.digest(observed_scientific),'Strict timed paired full scientific fixture including residuals'
                    path=OUT/'timing'/f'{repeat}_{index:03d}_{mode}.json';c.commit(path,item)
                    reports.append(dict(phase='timing',repeat=repeat,fixture_id=row['fixture_id'],stratum=row['stratum'],mode=mode,
                        seconds=item['seconds'],path=str(path),sha256=c.sha(path),archival_residual_differences=item['archival_residual_differences'],reused_requests=0 if item['reuse_log'] is None else item['reuse_log']['reused_requests']))
                if index%16==0:print('TIMED_FIXED_POSES',repeat,index+1,'calls',calls,flush=True)
        c.bound();c.verify(d['inputs']);c.verify(d['sources']);c.verify(d['prior_failed_inputs'])
        totals={}
        for stratum in sorted({r['stratum'] for r in rows}):
            times={mode:sum(x['seconds'] for x in reports if x['phase']=='timing' and x['stratum']==stratum and x['mode']==mode) for mode in d['modes']}
            gain=1-times['reuse']/times['original']
            totals[stratum]=dict(seconds=times,runtime_gain_fraction=gain,local_material_gain_passed=gain>=d['minimum_material_gain_fraction'])
        a=sum(v['seconds']['original'] for v in totals.values());b=sum(v['seconds']['reuse'] for v in totals.values())
        result=dict(passed=True,exact_outer_replay_passed=True,unchanged_physics_association_audits_passed=True,
            utc=c.utc(),design_sha256=c.sha(DESIGN),outer_calls=calls,qualification_fixtures=len(rows),new_trajectory_steps=0,
            key_controls=controls,witness_mutation_controls=guards,
            reuse_requests=sum(x['reused_requests'] for x in reports),strata=totals,
            overall_runtime_gain_fraction=1-b/a,local_material_gain_passed=(1-b/a)>=d['minimum_material_gain_fraction'],
            reports=reports,artifacts={x['path']:x['sha256'] for x in reports},production_authorized=False,
            transition_qualified=False,restart_qualified=False,full_path_qualified=False,
            strict_paired_all_scientific_fields_passed=True,prior_attempt_remains_failed=True,
            archived_residual_differences=[v for x in reports for v in x['archival_residual_differences']],
            claim='Exact paired fixed-pose implementation screen and local replay timings only. Witness eligibility/hits and strata remain explicit. No campaign speedup, difficult-placement transfer or shape/flow inference; no production promotion.')
        c.commit(OUT/'results.json',result);c.commit(OUT/'completion.json',dict(passed=True,results_sha256=c.sha(OUT/'results.json')))
        print('FIXED_POSE_SCREEN_COMPLETE',calls,result['reuse_requests'],result['overall_runtime_gain_fraction'],flush=True)
    except Exception as error:
        c.commit(OUT/'failure.json',dict(passed=False,error=repr(error),traceback=traceback.format_exc(),utc=c.utc(),
            completed=reports,outer_calls_attempted=calls,new_trajectory_steps=0,production_authorized=False))
        raise


if __name__=='__main__':
    if sys.argv[1:]==['prepare']:prepare()
    elif sys.argv[1:]==['run']:run()
    else:raise ValueError('prepare | run')
