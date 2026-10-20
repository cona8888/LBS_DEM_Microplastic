"""Fixed-pose replay and local cost screen; never calls a trajectory integrator."""
from contextlib import ExitStack
from datetime import datetime
from pathlib import Path
import copy, json, os, platform, sys, time, traceback
import verification_common_v1 as c

sys.path.insert(0,str(c.ROOT/'stage222_staging'))
import overnight_campaign_v1 as n
import numpy as np
import psutil
import verification_overhead_v2 as candidate
import audit_verification_overhead_v2 as reuse_audit

JOB=n.job
RUNTIME=JOB.parent.engine.runtime
STACK=n.source.stack
ASSOCIATION=STACK.frozen.stack.auditor
FIXTURE_DIR=c.PRIOR/'fixtures_01'
DESIGN=c.DESIGNS/'tiny_replay_01.json'
OUT=c.OUT/'tiny_replay_01'
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
                policy_binding=lambda:policy_binding(inventory),certificate_binding=certificate_binding,route_records=lambda:copy.deepcopy(plain(JOB.fast.attempts)),reuse=True))
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
    a=c.bound();c.environment();prior=c.used_outer_calls()
    assert prior+4<=a['maximum_nonadvancing_outer_calls']
    receipt=c.sealed(FIXTURE_DIR/'results.json');assert receipt['passed']
    inventory=c.read(FIXTURE_DIR/'fixtures.json');c.verify(inventory['sources']);c.verify(inventory['inputs'])
    byid={x['fixture_id']:x for x in inventory['fixtures']}
    rows=[byid[k] for k in a['tiny_fixture_ids']]
    assert rows[0]['stratum']=='recorded_fallback' and rows[1]['stratum']=='healthy_early_success'
    inputs=[c.AUTH,c.DESIGNS/'proposal_01.json',FIXTURE_DIR/'fixtures.json',FIXTURE_DIR/'results.json',FIXTURE_DIR/'completion.json']
    c.commit(DESIGN,dict(stage='Stage228 guarded metadata tiny fixed-pose gate',utc=c.utc(),
        authorization_sha256=c.sha(c.AUTH),end_utc=a['end_utc'],prior_outer_calls_attempted=prior,
        maximum_outer_calls=4,fixture_ids=a['tiny_fixture_ids'],modes=['original','reuse'],
        inputs={str(p):c.sha(p) for p in inputs},
        sources={**inventory['sources'],**{str(p):c.sha(p) for p in source_files()}},
        required_fallback_actual_append_hit=True,required_healthy_reused_requests=0,
        strict_paired_scientific_fields_including_residuals=True,declared_timing_field_exclusions=sorted(TIMING_FIELDS),
        inherited_archive_comparison='Exact mechanical outputs/branches/inner operands; historical scalar residual differences explicit and paired current residuals exact; original independent physical ceilings unchanged.',
        evidence_policy='Prospective one appended exactly associated early-failure row; full original route records remain intact and all numeric seed certificate channels unchanged.',
        gates='Actual append-qualified hit must pass independent witness/delta audit plus adversarial actual-hit controls; healthy route unchanged; every physics/association gate unchanged.',
        new_trajectory_steps=0,new_saved_transport_steps=0,production_authorized=False,simulation_dispatch=False))
    print('PREPARED_TINY_GATE',c.sha(DESIGN),4,'outercalls',flush=True)


def failure_output(error):
    tb=error.__traceback__;frame=None
    while tb:
        if tb.tb_frame.f_code is call.__code__:frame=tb.tb_frame.f_locals
        tb=tb.tb_next
    if frame is None:return None
    return plain({k:frame[k] for k in ('row','mode','answer','fixture','memo','seconds','audit','witness_audit') if k in frame})


def run():
    a=c.bound();c.environment();d=c.read(DESIGN);c.verify(d['inputs']);c.verify(d['sources'])
    assert d['authorization_sha256']==c.sha(c.AUTH) and c.used_outer_calls()==d['prior_outer_calls_attempted']
    p=psutil.Process();p.cpu_affinity([a['logical_cpu']])
    c.commit(OUT/'launch.json',dict(utc=c.utc(),pid=os.getpid(),created=p.create_time(),argv=sys.argv,
        command=p.cmdline(),design_sha256=c.sha(DESIGN),python=sys.version,platform=platform.platform(),
        affinity=p.cpu_affinity(),threads={k:os.environ[k] for k in ('OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS')},
        numpy_version=np.__version__,new_trajectory_steps=0))
    reports=[];calls=0;controls=None;live_controls=None
    try:
        inventory=c.read(FIXTURE_DIR/'fixtures.json');byid={x['fixture_id']:x for x in inventory['fixtures']}
        JOB.parent.b.old.parent.configure();STACK.candidate.warm()
        for index,identity in enumerate(d['fixture_ids']):
            row=byid[identity];pair=None
            for mode in d['modes']:
                c.bound();assert calls<d['maximum_outer_calls'] and calls+d['prior_outer_calls_attempted']<a['maximum_nonadvancing_outer_calls'];calls+=1
                item=call(inventory,row,mode,d['end_utc'])
                now=scientific(item['force_audit_fixture'])
                if pair is None:pair=now
                else:assert c.digest(pair)==c.digest(now),'Strict paired all scientific fields including residuals and retained route rows'
                path=OUT/f'{index:02d}_{mode}.json';c.commit(path,item)
                reports.append(dict(fixture_id=identity,stratum=row['stratum'],mode=mode,path=str(path),sha256=c.sha(path),
                    seconds=item['seconds'],reused_requests=0 if item['reuse_log'] is None else item['reuse_log']['reused_requests']))
                if mode=='reuse':
                    log=item['reuse_log']
                    if row['stratum']=='recorded_fallback':
                        assert log['reused_requests']>=1,'Tiny fallback requires an actual append-qualified hit'
                        controls=reuse_audit.mutation_checks(log,expected_deadline=datetime.fromisoformat(d['end_utc']).timestamp())
                        assert controls['passed'],'Actual-hit witness and append corruption controls'
                    else:assert log['reused_requests']==0,'Healthy success must never reuse a negative result'
            print('TINY_EXACT_PHYSICAL_PAIR',identity,flush=True)
        assert calls==4 and controls is not None
        live_controls=reuse_audit.live_binding_controls(candidate,fingerprint=candidate._ScopeCodeMetadata().fingerprint,cutoff=candidate.cutoff_control,strict=True)
        assert live_controls['passed'], 'Fresh live metadata/mutable operand/cutoff controls'
        c.bound();c.verify(d['inputs']);c.verify(d['sources'])
        c.commit(OUT/'results.json',dict(passed=True,utc=c.utc(),design_sha256=c.sha(DESIGN),outer_calls_attempted=calls,
            reports=reports,artifacts={r['path']:r['sha256'] for r in reports},actual_hit_mutation_controls=controls,live_metadata_controls=live_controls,
            exact_paired_all_scientific_outputs=True,unchanged_independent_physics_association_audits=True,
            tiny_qualified=True,local_material_gain_qualified=False,new_trajectory_steps=0,new_saved_transport_steps=0,
            production_authorized=False,transition_qualified=False,restart_qualified=False,full_path_qualified=False,
            claim='Tiny implementation falsification gate only; one fallback and one healthy control, actual independently audited append-qualified reuse. No performance or production claim.'))
        c.commit(OUT/'completion.json',dict(passed=True,results_sha256=c.sha(OUT/'results.json')))
        print('TINY_GATE_PASSED',c.sha(OUT/'results.json'),flush=True)
    except Exception as error:
        observed=failure_output(error);extra={}
        if observed is not None:
            path=OUT/'failed_call.json';c.commit(path,observed);extra[str(path)]=c.sha(path)
        c.commit(OUT/'failure.json',dict(passed=False,utc=c.utc(),error=repr(error),traceback=traceback.format_exc(),
            outer_calls_attempted=calls,completed=reports,artifacts=extra,new_trajectory_steps=0,production_authorized=False))
        raise


if __name__=='__main__':
    if sys.argv[1:]==['prepare']:prepare()
    elif sys.argv[1:]==['run']:run()
    else:raise ValueError('prepare | run')


