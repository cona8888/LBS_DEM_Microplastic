"""Pure schema/accounting falsification controls; never execute a physical solver."""
from pathlib import Path
from types import SimpleNamespace as NS
import ast, copy, importlib.util, os
import campaign_common_v1 as c

HERE=Path(__file__).resolve().parent
SOURCE=HERE/'finalize_recovery_v2.py'
DEST=c.OUT/'recovery_finalizer_controls_01'


def run():
    c.environment();c.bound()
    ast.parse(SOURCE.read_text(encoding='utf-8'))
    spec=importlib.util.spec_from_file_location('_stage229_recovery_finalizer_controls',SOURCE)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    checks=[]
    def passed(name):checks.append(dict(control=name,passed=True))
    def rejects(name,thunk):
        try:thunk()
        except Exception:passed(name)
        else:raise AssertionError('Control was accepted: '+name)
    worker=HERE/'continue_baseline_v2.py'
    failure_path=c.RUN/'run_01/failure.json';failure=c.read(failure_path)
    source=worker.read_text(encoding='utf-8');trace=failure['traceback']
    order=m.pre_dispatch_source_proof(source,trace)
    assert order['guard_line']==270<order['mkdir_line']<order['execute_line']
    passed('actual_frozen_v2_guard_frame_before_mkdir_and_execution')
    rejects('incorrect_guard_traceback_line',lambda:m.pre_dispatch_source_proof(source,trace.replace('line 270, in segment','line 271, in segment')))
    rejects('guard_after_folder_creation',lambda:m.pre_dispatch_source_proof(source.replace(
        '    verify_scientific_inputs(plan)\n    folder.mkdir(parents=True, exist_ok=False)',
        '    folder.mkdir(parents=True, exist_ok=False)\n    verify_scientific_inputs(plan)'),trace))
    rejects('physical_execution_before_guard',lambda:m.pre_dispatch_source_proof(source.replace(
        '    verify_scientific_inputs(plan)\n    folder.mkdir(parents=True, exist_ok=False)',
        '    baseline.execute()\n    verify_scientific_inputs(plan)\n    folder.mkdir(parents=True, exist_ok=False)'),trace))
    rejects('missing_segment_function',lambda:m.pre_dispatch_source_proof(source.replace('def segment(', 'def wrong_segment('),trace))
    names=['accounting.json','call.json.seal.json','call.json.xz','completion.json','launch.json','results.json','trace.npy']
    m.exact_transaction_files(names);passed('exact_seven_transaction_files')
    for label,malformed in [('missing_seal',names[:1]+names[2:]),('orphan_extra_file',names+['orphan.json.xz']),
                            ('duplicate_file_name',names+[names[0]]),('renamed_raw_file',[name if name!='call.json.xz' else 'foreign.json.xz' for name in names])]:
        rejects(label,lambda malformed=malformed:m.exact_transaction_files(malformed))
    prior=dict(new_audited_physical_steps=1304148,diagnostic_audited_steps=512,
               new_known_saved_steps_including_diagnostics=1304660,known_unaccepted_saved_steps=0)
    total,conservative=m.shared_saved_totals(prior,123,512,7,11,10000000)
    assert total==1305302 and conservative;passed('prior_and_current_saved_steps_counted_once')
    assert m.shared_saved_totals(prior,123,512,7,11,total)==(total,False)
    passed('unknown_reservation_is_separate_from_confirmed_known_count')
    for field,value in [('new_audited_physical_steps',1304147),('diagnostic_audited_steps',513),
                        ('new_known_saved_steps_including_diagnostics',1304661),('known_unaccepted_saved_steps',1)]:
        bad=copy.deepcopy(prior);bad[field]=value
        rejects('inconsistent_prior_'+field,lambda bad=bad:m.shared_saved_totals(bad,123,512,7,11,10000000))
    for label,args in [('boolean_count',(True,512,7,11,10000000)),('float_count',(123.,512,7,11,10000000)),
                       ('negative_count',(-1,512,7,11,10000000)),('negative_unknown',(123,512,7,-1,10000000)),
                       ('known_cap_exceeded',(123,512,7,11,1305301))]:
        rejects(label,lambda args=args:m.shared_saved_totals(prior,*args))
    real_process=m.psutil.Process()
    live=dict(pid=os.getpid(),created=real_process.create_time(),command=real_process.cmdline())
    rejects('actual_live_identity_not_retired',lambda:m.retired_identity(live))
    different=dict(live,created=live['created']+1)
    m.retired_identity(different);passed('different_birth_is_unrelated_and_untouched')
    rejects('boolean_pid_rejected',lambda:m.retired_identity(dict(live,pid=True)))

    # Synthetic prerequisite receipts test exact field associations only. Actual
    # hashes/source text and the immutable470-folder inventory are read; no
    # retirement or raw-reconstruction success is inferred from these fixtures.
    original={name:getattr(m.c,name) for name in ('read','sealed','verify')}
    original_retired=m.retired_identity
    try:
        seed={'synthetic_full_checkpoint':True}
        cp=failure['last_verified_checkpoint_sha256'];authority=c.sha(c.AUTH)
        plan=c.DESIGNS/'transport_design_02.json';old_run=c.RUN/'run_01'
        diagnosis=dict(passed=True,authorization_sha256=authority,transport_design_sha256=c.sha(plan),
            failed_case='s2_i0_fibre_f0p125',failed_segment=471,pre_dispatch_reservation_saved_steps=0,
            unknown_saved_steps_reservation_upper_bound=0,last_verified_checkpoint_sha256=cp,
            exact_worker_identity_retired=True,frozen_pre_dispatch_source_order_verified=True,
            failed_segment_folder_absent=True,all_orphan_work_inventoried=True,
            artifacts={str(failure_path):c.sha(failure_path),str(worker):c.sha(worker)})
        old_prior={'artifacts':{str(failure_path):c.sha(failure_path)}}
        retirement=dict(passed=True,authorization_sha256=authority,all_exact_launch_identities_retired=True,
            identities=[dict(exact_identity_retired=True)],artifacts={})
        w=NS(PRIOR_SOURCE=worker,PRIOR_PLAN=plan,
            SEED_NAME='s2_i0_fibre_f0p125',prior_worker=NS(RUN=old_run),api=NS(digest=lambda value:cp))
        current_failure=copy.deepcopy(failure)
        m.c.read=lambda p:current_failure if Path(p)==failure_path else original['read'](p)
        m.c.sealed=lambda p:diagnosis if Path(p)==m.FAILURE_DIAGNOSIS else retirement if Path(p)==m.INITIAL_RETIREMENT else original['sealed'](p)
        m.c.verify=lambda mapping:None
        m.retired_identity=lambda launch:m.need(type(launch['pid']) is int,'Synthetic exact identity metadata')
        m.authenticate_zero_reservation(w,old_prior,seed);passed('synthetic_specific_zero_reservation_associations')
        mutations=[('passed',False),('authorization_sha256','foreign'),('transport_design_sha256','foreign'),
            ('failed_case','foreign'),('failed_segment',472),('pre_dispatch_reservation_saved_steps',1),
            ('pre_dispatch_reservation_saved_steps',False),('unknown_saved_steps_reservation_upper_bound',1),
            ('unknown_saved_steps_reservation_upper_bound',False),('last_verified_checkpoint_sha256','foreign'),
            ('exact_worker_identity_retired',False),('frozen_pre_dispatch_source_order_verified',False),
            ('failed_segment_folder_absent',False),('all_orphan_work_inventoried',False)]
        for field,value in mutations:
            old=diagnosis[field];diagnosis[field]=value
            rejects('zero_witness_mutation_'+field+'_'+str(value),lambda:m.authenticate_zero_reservation(w,old_prior,seed))
            diagnosis[field]=old
        for field,value in [('verified_saved_steps',1304661),('diagnostics_verified_steps',511),
                            ('last_verified_checkpoint_sha256','foreign'),('dependent_dispatch_stopped',False)]:
            old=current_failure[field];current_failure[field]=value
            rejects('failed_ledger_mutation_'+field,lambda:m.authenticate_zero_reservation(w,old_prior,seed))
            current_failure[field]=old
        old=current_failure['unresolved_reservation']['segment'];current_failure['unresolved_reservation']['segment']=472
        rejects('wrong_failed_reservation',lambda:m.authenticate_zero_reservation(w,old_prior,seed))
        current_failure['unresolved_reservation']['segment']=old
        old=current_failure['traceback'];current_failure['traceback']=old.replace('line 270, in segment','line 271, in segment')
        rejects('wrong_failed_runtime_frame',lambda:m.authenticate_zero_reservation(w,old_prior,seed))
        current_failure['traceback']=old
        old=diagnosis['artifacts'][str(failure_path)];diagnosis['artifacts'][str(failure_path)]='foreign'
        rejects('unbound_failure_bytes',lambda:m.authenticate_zero_reservation(w,old_prior,seed))
        diagnosis['artifacts'][str(failure_path)]=old
        old=retirement['all_exact_launch_identities_retired'];retirement['all_exact_launch_identities_retired']=False
        rejects('unqualified_initial_retirement',lambda:m.authenticate_zero_reservation(w,old_prior,seed))
        retirement['all_exact_launch_identities_retired']=old
    finally:
        for name,value in original.items():setattr(m.c,name,value)
        m.retired_identity=original_retired
    c.bound()
    row=dict(passed=True,numerical_calls=0,optimizer_calls=0,new_trajectory_steps=0,new_saved_transport_steps=0,
        controls=checks,controls_passed=len(checks),utc=c.utc(),authorization_sha256=c.sha(c.AUTH),
        source_sha256=c.sha(SOURCE),actual_frozen_source_order=order,
        artifacts={str(path):c.sha(path) for path in (SOURCE,Path(__file__).resolve(),worker,failure_path)},
        scope='Pure schema, runtime source-order, exact file-set, identity and shared-ledger falsification. Synthetic retired-prerequisite fixtures do not authenticate actual retirement or physical/raw outputs. Full prerequisite/hash/codec reconstruction remains mandatory in the finalizer.',
        production_authorized=False)
    c.commit(DEST/'results.json',row);c.commit(DEST/'completion.json',dict(passed=True,results_sha256=c.sha(DEST/'results.json')))
    print('RECOVERY_FINALIZER_PURE_CONTROLS',len(checks),c.sha(SOURCE),c.sha(DEST/'results.json'),flush=True)


if __name__=='__main__':run()
