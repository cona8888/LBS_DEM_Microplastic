"""Stdlib/FAKE controls only. No engine, model, force, actor or authority."""
import ast
from contextlib import contextmanager
import copy
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

PATH = Path(__file__).with_name('run_saved_momentum_probe_v1.py')
spec = importlib.util.spec_from_file_location('_saved_momentum_driver_controls', PATH)
d = importlib.util.module_from_spec(spec)
spec.loader.exec_module(d)


class SourceAndBudget(unittest.TestCase):
    def test_import_has_no_authority_or_engine(self):
        self.assertIsNone(d._ADMIN)
        forbidden = {'reconstruct_fixed_pose_v3', 'full_state_integration_adapter_v5',
                     'cancellation_safe_velocity_v1', 'inertial_contact_robust_v1'}
        self.assertFalse(forbidden & set(sys.modules))
        self.assertFalse(any(isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                             and n.func.id in ('controller', 'worker', 'authorize')
                             for n in ast.parse(PATH.read_text()).body))

    def test_exact_cumulative_caps(self):
        d.budget_guard(260, 5, 12)
        self.assertEqual(d.PRIOR['all_work_rows'] + 260, 757837)
        self.assertEqual(d.PRIOR['integration_records'] + 5, 207)
        self.assertEqual(d.BASELINE['case_work_rows'] + 260, 11070615)
        for args in ((261, 5, 12), (260, 6, 12), (260, 5, 13), (-1, 1, 1), (1., 1, 1)):
            with self.assertRaises(RuntimeError):
                d.budget_guard(*args)

    def test_fixed_clock_no_renewal(self):
        clock = dict(passed=True, original_shared_end_utc=d.ABSOLUTE_END,
            start_utc='2026-10-20T10:00:00+00:00', simulation_cutoff_utc='2026-10-20T10:15:00+00:00',
            end_utc='2026-10-20T11:15:00+00:00')
        start = d.instant(clock['start_utc'])
        d.validate_clock(clock, now=start)
        for field, value in (('start_utc', '2026-10-20T10:00:00'),
                             ('simulation_cutoff_utc', '2026-10-20T10:15:01+00:00'),
                             ('end_utc', '2026-10-20T11:14:59+00:00')):
            bad = dict(clock, **{field:value})
            with self.assertRaises(RuntimeError):
                d.validate_clock(bad, now=start)
        with self.assertRaises(RuntimeError):
            d.validate_clock(clock, now=start+900)
        d.validate_clock(clock, now=start+901, numerical=False)

    def test_units_include_reuse_and_extra_kernel(self):
        seen = []
        c = d.NonadvancingCounter(2, lambda:seen.append('clock'))
        item = dict(outer_index=0, inner_index=0)
        c.before_inner(item)
        c.phase(lambda:seen.append('kernel'))
        c.phase(lambda:seen.append('nested'))
        c.after_inner(dict(observer_entered=True))
        c.before_inner(dict(outer_index=0, inner_index=1))  # reuse: no kernel
        c.after_inner(dict(observer_entered=True))
        self.assertEqual(c.units, 5)  # 2warm+2maps+1extra
        self.assertEqual(c.actual_hot_phase_calls, 2)
        self.assertEqual(c.prepared_maps, 2)
        self.assertEqual(len(c.events), 3)

    def test_exhausted_unit_stops_BEFORE_dispatch(self):
        c = d.NonadvancingCounter(12)
        with self.assertRaisesRegex(RuntimeError, 'BEFORE'):
            c.before_inner(dict(outer_index=0, inner_index=0))
        c.after_inner(dict(observer_entered=False))  # must preserve budget cause
        self.assertEqual((c.units, c.prepared_maps), (12, 0))
        with self.assertRaises(RuntimeError):
            c.phase(lambda:self.fail('exhausted kernel was invoked'))

    def test_clock_checked_before_inner_and_kernel(self):
        def expired():
            raise RuntimeError('expired immutable numerical cutoff')
        c = d.NonadvancingCounter(2, expired)
        with self.assertRaisesRegex(RuntimeError, 'expired'):
            c.before_inner(dict(outer_index=0, inner_index=0))
        with self.assertRaisesRegex(RuntimeError, 'expired'):
            c.phase(lambda:self.fail('expired native dispatch'))
        self.assertEqual(c.units, 2)

    def test_atomic_existing_malformed_never_overwritten(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'one.json'
            path.write_text('{broken')
            with self.assertRaises(FileExistsError):
                d.commit(path, dict(valid=True))
            self.assertEqual(path.read_text(), '{broken')


class Ledger(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.plan = self.root/'plan.json'
        self.plan.write_text('{}')
        self.out = self.root/'out'
        self.patches = [patch.object(d, 'PLAN', self.plan), patch.object(d, 'OUT', self.out)]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in reversed(self.patches):
            p.stop()
        self.temp.cleanup()

    def reservation(self):
        path = self.out/'reservations/001.json'
        d.commit(path, dict(plan_sha256=d.sha(self.plan), work_cap=1, nonadvancing_cap=10))
        return path

    def test_pending_not_accepted_and_results_only_still_pending(self):
        p = self.reservation()
        folder = self.out/'admissions/001'
        d.commit(folder/'results.json', dict(passed=True))
        row = d.ledger()
        self.assertEqual(row['unknown_reserved_work_upper_bound'], 1)
        self.assertEqual(row['accepted_discarded_work_rows'], 0)
        self.assertEqual(row['nonadvancing_units'], 10)

    def test_expected_negative_work_stays_known_unaccepted(self):
        p = self.reservation()
        d.seal(self.out/'admissions/001', dict(passed=True, physical_work_accepted=False,
            reservation_sha256=d.sha(p), actual_work_rows=1, nonadvancing_units=2, artifacts={}))
        row = d.ledger()
        self.assertEqual(row['known_unaccepted_work_rows'], 1)
        self.assertEqual(row['accepted_discarded_work_rows'], 0)
        self.assertEqual(row['unknown_reserved_work_upper_bound'], 0)

    def test_bad_complete_seal_rejects(self):
        self.reservation()
        folder = self.out/'admissions/001'
        d.commit(folder/'results.json', dict(passed=True))
        d.commit(folder/'completion.json', dict(passed=True, results_sha256='0'*64))
        with self.assertRaises(RuntimeError):
            d.ledger()

    def test_linked_raw_tamper_rejects(self):
        p = self.reservation()
        raw = self.root/'raw'
        raw.write_text('original')
        d.seal(self.out/'admissions/001', dict(passed=True, physical_work_accepted=True,
            reservation_sha256=d.sha(p), actual_work_rows=1, nonadvancing_units=2,
            artifacts={str(raw):d.sha(raw)}))
        raw.write_text('tampered')
        with self.assertRaises(RuntimeError):
            d.ledger()


class Identity(unittest.TestCase):
    def test_live_schema_matches_actual_frozen_identity_helper(self):
        class NoSuchProcess(Exception):
            pass
        class Proc:
            pid = 123
            def create_time(self): return 42.
            def cmdline(self): return ['python', '-B', 'probe', 'worker']
        fake = SimpleNamespace(Process=lambda *a:Proc(), NoSuchProcess=NoSuchProcess)
        tree = ast.parse((d.STAGING/'cost_screen_v1.py').read_text())
        node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'identity')
        ns = dict(psutil=fake, require=d.need)
        exec(compile(ast.Module(body=[node], type_ignores=[]), '<actual frozen identity>', 'exec'), ns)
        with patch.dict(sys.modules, psutil=fake), patch.object(d, 'sha', lambda p:'a'*64):
            launch = d.launch_identity('worker')
        self.assertEqual(ns['identity'](launch)['retired'], False)
        bad = dict(launch, command=['unrelated'])
        with self.assertRaises(RuntimeError):
            ns['identity'](bad)
        mismatch = dict(launch, created=41.)
        self.assertTrue(ns['identity'](mismatch)['retired'])

    def test_denied_identity_not_retirement(self):
        class AccessDenied(Exception): pass
        class NoSuchProcess(Exception): pass
        fake = SimpleNamespace(Process=lambda *a:(_ for _ in ()).throw(AccessDenied()), NoSuchProcess=NoSuchProcess)
        node = next(n for n in ast.parse((d.STAGING/'cost_screen_v1.py').read_text()).body
                    if isinstance(n, ast.FunctionDef) and n.name == 'identity')
        ns = dict(psutil=fake, require=d.need)
        exec(compile(ast.Module(body=[node], type_ignores=[]), '<actual frozen identity>', 'exec'), ns)
        with self.assertRaises(AccessDenied):
            ns['identity'](dict(pid=123, created=42., command=[]))

    def test_cross_registration_requires_every_identity_field(self):
        base=dict(pid=123,created=42.,command=['python','worker'],plan_sha256='a'*64)
        self.assertTrue(d.same_actor(base,dict(base,role='different administrative role')))
        for key,value in (('pid',124),('created',43.),('command',['unrelated']),('plan_sha256','b'*64)):
            self.assertFalse(d.same_actor(base,dict(base,**{key:value})))


class NativeCompositionFake(unittest.TestCase):
    def test_actual_driver_scopes_restore_before_original_exit(self):
        events = []
        hot = SimpleNamespace(phase=lambda:events.append('nativefake'))
        original_phase = hot.phase
        compiled_namespace=dict(compiled_phase=original_phase)
        exec('def primary():\n    return compiled_phase()', compiled_namespace)
        hot.PRIMARY=compiled_namespace['primary']
        hot.s50=SimpleNamespace(_solve=hot.PRIMARY)
        live_contacts=[[15, 1e-12, [1.,0.,0.], [0.,0.,0.]]]
        state = [True]
        stage42 = SimpleNamespace()
        backend = SimpleNamespace(stage42=stage42, recovery_mode=lambda:state[0],
                                  set_recovery_mode=lambda v:state.__setitem__(0, v))
        def configure(): pass
        configure.__globals__['hot'] = hot
        q = SimpleNamespace(reference=SimpleNamespace(JOB=SimpleNamespace(parent=SimpleNamespace(
            b=SimpleNamespace(old=SimpleNamespace(parent=SimpleNamespace(configure=configure)))))),
            job=SimpleNamespace(observer=SimpleNamespace(backend=backend)))
        class Capture:
            def __init__(self): self.q=q; self.trace={}
            @contextmanager
            def packet_scope(self):
                self.assert_original()
                events.append('original_origin_entry')
                yield
                self.assert_original()
                events.append('original_origin_exit')
            def assert_original(self):
                if hot.phase is not original_phase: raise AssertionError('phase wrapped outside original origins')
                if hot.PRIMARY.__globals__['compiled_phase'] is not original_phase:
                    raise AssertionError('captured compiled alias not restored before original exit')
            @contextmanager
            def scope(self, role, before):
                value={}
                yield value
                value['closed']=True
        capture=Capture()
        @contextmanager
        def execution(*a, **k):
            yield dict(runtime=SimpleNamespace(capture=capture),native_setup_force_calls=0,
                       geometry=SimpleNamespace(contacts=lambda *a:live_contacts))
        @contextmanager
        def helper_scope(module, trace, *, enabled, before_inner, after_inner):
            journal=dict(scope_restored=False)
            def call(*args):
                if args[6] is not live_contacts:raise AssertionError('lost original live contact identity')
                for i in range(2):
                    item=dict(outer_index=0,inner_index=i,observer_entered=False)
                    try:
                        before_inner(item)
                        item['observer_entered']=True
                        if i == 0: hot.PRIMARY()  # captured alias, NOT hot.phase lookup
                    finally: after_inner(item)
                return [1.], dict(cache_policy='fake')
            backend.inertial_contact_step=call
            try: yield journal
            finally: journal['scope_restored']=True
        engine=SimpleNamespace(native_execution_scope=execution, plain=copy.deepcopy)
        helper=SimpleNamespace(scope=helper_scope)
        npfake=SimpleNamespace(asarray=lambda v, dtype:v)
        physical=dict(cases=[dict(level_id='f0p0625', spec={},binding='b')])
        fixture=dict(outer_inputs=[[]]*6+[copy.deepcopy(live_contacts),1.,1.,.1,1.,1.,1.,1.], before_runtime_recovery_mode=False,
                     geometry_context=dict(x=[],p=[],a=1.,b=1.,original_skin_m=0.))
        fixture['normal_gap_prepare_metadata']=[dict(context=fixture['geometry_context'])]
        fixture['reference_prepare_call']=dict(contacts=copy.deepcopy(live_contacts),ell_m=1.,
                                               metadata=fixture['normal_gap_prepare_metadata'])
        with patch.dict(sys.modules,numpy=npfake), patch.object(d,'read',lambda p:physical):
            value=d.native_probe(engine,helper,fixture,True,lambda:events.append('gate'),prior_units=2)
        self.assertNotIn('scope_error',value)
        self.assertTrue(value['journal']['scope_restored'])
        self.assertEqual(value['nonadvancing_units'],4)
        self.assertEqual(state[0],True)
        self.assertIs(hot.phase,original_phase)
        self.assertEqual(events[-1],'original_origin_exit')
        self.assertEqual(value['actual_hot_phase_calls'],1)
        self.assertEqual(value['counter_alias_proof']['distinct_compiled_phase_namespaces'],1)

    def test_nonzero_scope_setup_force_is_refused_before_outer(self):
        @contextmanager
        def execution(*a,**k):yield dict(native_setup_force_calls=1)
        engine=SimpleNamespace(native_execution_scope=execution)
        physical=dict(cases=[dict(level_id='f0p0625',spec={},binding='b')])
        fixture=dict(outer_inputs=[0]*14)
        with patch.dict(sys.modules,numpy=SimpleNamespace()),patch.object(d,'read',lambda p:physical):
            value=d.native_probe(engine,SimpleNamespace(),fixture,True,lambda:None,prior_units=2)
        self.assertIn('no hidden setup force',value['scope_error'])
        self.assertFalse(value['outer_call_attempted'])


class HashBoundaryClock(unittest.TestCase):
    def test_actual_authority_rechecks_clock_after_hash_scan(self):
        clock=dict(passed=True,original_shared_end_utc=d.ABSOLUTE_END,proposal_sha256='x'*64,
            approval_sha256='x'*64,original_outer_clock_sha256=d.OUTER_CLOCK_SHA,
            start_utc='2026-10-20T10:00:00+00:00',simulation_cutoff_utc='2026-10-20T10:15:00+00:00',
            end_utc='2026-10-20T11:15:00+00:00')
        plan=dict(scope=d.approval_scope(),baseline=d.BASELINE,prior=d.PRIOR,
            source_files={str(d.SELF):'x'*64},physical_inputs={},evidence_files={},historical_evidence_files={})
        for key in ('authorization_sha256','proposal_sha256','approval_sha256','preparation_sha256',
                    'clock_sha256','physical_sha256','fixtures_sha256'):plan[key]='x'*64
        plan['binding']=d.digest(plan)
        approval=dict(human_origin=True,proposal_sha256='x'*64,scope=d.approval_scope())
        prepared=dict(baseline=d.BASELINE)
        values={d.PLAN:plan,d.CLOCK:clock,d.APPROVAL:approval,d.PREPARED:prepared}
        current=[d.instant(clock['start_utc'])+899]
        def hashing(mapping):current[0]+=2
        def filesha(path):return d.OUTER_CLOCK_SHA if Path(path)==d.OUTER_CLOCK else 'x'*64
        with patch.object(d,'read',lambda p:values[Path(p)]),patch.object(d,'sealed',lambda p,**k:values[Path(p)]),\
             patch.object(d,'sha',filesha),patch.object(d,'environment',lambda:None),\
             patch.object(d,'verify_mapping',hashing),patch.object(d.time,'time',lambda:current[0]):
            with self.assertRaisesRegex(RuntimeError,'unexpired'):
                d.authority(numerical=True)

    def test_actual_authorize_cannot_write_after_preparation_crosses_cutoff(self):
        clock=dict(passed=True,original_shared_end_utc=d.ABSOLUTE_END,proposal_sha256='x'*64,
            approval_sha256='x'*64,original_outer_clock_sha256=d.OUTER_CLOCK_SHA,
            start_utc='2026-10-20T10:00:00+00:00',simulation_cutoff_utc='2026-10-20T10:15:00+00:00',
            end_utc='2026-10-20T11:15:00+00:00')
        approval=dict(human_origin=True,human_reply='Approve',question_reference='actual question',
                      proposal_sha256='x'*64,scope=d.approval_scope())
        prepared=dict(source_files={})
        current=[d.instant(clock['start_utc'])+899]
        def full_preparation(*a):current[0]+=2;return []
        with tempfile.TemporaryDirectory() as folder:
            temp=Path(folder)
            values={d.APPROVAL:approval,d.CLOCK:clock,d.PREPARED:prepared}
            with patch.object(d,'AUTH',temp/'auth'),patch.object(d,'PLAN',temp/'plan'),\
                 patch.object(d,'OUT',temp/'out'),patch.object(d,'CONTROL_LOG_DIR',temp/'logs'),\
                 patch.object(d,'environment',lambda:None),patch.object(d,'sha',lambda p:'x'*64),\
                 patch.object(d,'sealed',lambda p,**k:values[Path(p)]),patch.object(d,'read',lambda p:{}),\
                 patch.object(d,'verify_preparation',full_preparation),patch.object(d,'resource_guard',lambda:None),\
                 patch.object(d,'source_interfaces',lambda:{}),patch.object(d.time,'time',lambda:current[0]),\
                 patch.object(d,'commit',lambda *a:self.fail('expired authorization wrote a file')):
                with self.assertRaisesRegex(RuntimeError,'unexpired'):
                    d.authorize('x'*64,'x'*64,'x'*64)


class Retirement(unittest.TestCase):
    def test_idle_audit_negative_retires_gracefully_from_actual_handle(self):
        class Child:
            def __init__(self):self.code=None;self.waits=[]
            def poll(self):return self.code
            def wait(self,timeout=None):self.waits.append(timeout);self.code=0;return 0
        child=Child()
        launch=dict(pid=1,created=2.,command=['owned'],plan_sha256='a'*64)
        with tempfile.TemporaryDirectory() as folder,patch.object(d,'OUT',Path(folder)),\
             patch.object(d,'administration',lambda:SimpleNamespace(
                 exact_stop=lambda *a:self.fail('idle grace unnecessarily terminated worker'),
                 inspect_identity=lambda *a:dict(retired=True,no_such_process=True))):
            actual=d.retire_worker(child,launch,idle=True)
            self.assertEqual(actual['returncode'],0)
            self.assertFalse(actual['forced'])
            self.assertEqual(child.waits[0],2)
            self.assertTrue((Path(folder)/'controller/stop.json').exists())

    def test_pending_native_has_no_idle_grace(self):
        events=[]
        class Child:
            code=None
            def poll(self):return self.code
            def wait(self,timeout=None):events.append(('wait',timeout));return self.code
        child=Child()
        def stop(process,launch):events.append(('exact_stop',launch));process.code=1
        launch=dict(pid=1,created=2.,command=['owned'],plan_sha256='a'*64)
        with patch.object(d,'administration',lambda:SimpleNamespace(exact_stop=stop,
                inspect_identity=lambda *a:dict(retired=True))):
            actual=d.retire_worker(child,launch,idle=False)
        self.assertEqual(events[0][0],'exact_stop')
        self.assertEqual(actual['returncode'],1)
        self.assertTrue(actual['forced'])

    def test_forced_negative_missing_selfexit_is_honestly_available_only_as_negative(self):
        final=dict(passed=False,worker_forced=True,observed_worker_returncode=1,worker_retirement=dict(retired=True))
        value=d.worker_self_exit_evidence(final,False)
        self.assertFalse(value['available'])
        self.assertFalse(value['own_returncode_claimed'])
        self.assertTrue(value['observed_returncode_from_owner_handle'])
        for bad in (dict(final,passed=True),dict(final,worker_forced=False),
                    dict(final,observed_worker_returncode=None),dict(final,worker_retirement=dict(retired=False))):
            with self.assertRaises(RuntimeError):d.worker_self_exit_evidence(bad,False)


class AuditContract(unittest.TestCase):
    def setUp(self):
        self.maps=[dict(inner_index=i,vfree=[i],mobility=[[1]],jacobian=[[1]],gaps_m=[1],
            dt_s=1,friction=1,tolerance=1e-10,maxiter=25000,velocity=[i],health=dict(h=i)) for i in range(2)]
        self.fixture=dict(outer_inputs=[0]*14, before_runtime_recovery_mode=False,
            reference_legacy_velocity=[1],reference_inner_maps=[dict(map_output=[i],health=dict(h=i)) for i in range(2)],
            exact_inner_input_digests=[d.digest([s[k] for k in ('vfree','mobility','jacobian','gaps_m','dt_s',
                'friction','tolerance','maxiter')]) for s in self.maps])
        self.fixture['reference_prepare_call']=dict(identity='saved original raw/effective metadata')
        self.payload=dict(outer_call_attempted=True,input_sha256=d.digest(self.fixture['outer_inputs']),
            saved_recovery_mode=False,recovery_mode_restored=True,returned=True,velocity=[1],health={},
            prior_nonadvancing_units=2,nonadvancing_units=4,prepared_inner_maps=2,extra_nested_kernel_units=0,
            unit_events=[{},{}], journal=dict(enabled=True,outer_calls=[dict(outer_inputs=[0]*14,inner_systems=self.maps)]),
            evidence=dict(contact_trial_trace=dict(trial_route_counts=[[0,0]],cycle_guard_trials=[dict(
                records=[dict(canonical_selected=False,cycle_detected=False)]*2)]),early_attempts=[],fallback_systems=[],
                repairs=[],stage119_repair_calls=[],normal_gap_operand_policy=dict(prepare_calls=[self.fixture['reference_prepare_call']])))
        self.summary=dict(passed=True,original_negative_outer_calls=0,successful_outer_calls=1,
                          increment_inner_maps=0,outer_results=[dict(original_final_gate_passed=True)])
        self.trace_seen=[]
        def audit(journal,**kwargs):
            self.trace_seen.append(kwargs['original_trace'])
            return copy.deepcopy(self.summary)
        helper=SimpleNamespace(audit_journal=audit)
        arith=SimpleNamespace(np=None,pure_original_functions=lambda:dict(reynolds_number=lambda:None,
            inertial_multiplier=lambda:None))
        def load(path,name,expected=None):
            return helper if Path(path)==d.HELPER else arith if Path(path)==d.ARITHMETIC else SimpleNamespace(physical=lambda x:None)
        self.patches=[patch.object(d,'load_file',load),patch.object(d,'read',lambda p:dict(source_files={
            str(d.HELPER):'h'*64,str(d.ROOT/'stage183_staging/audit_fallback_systems_v1.py'):'p'*64})),
            patch.object(d,'original_cycle_audit',lambda *a:dict(passed=True))]
        for p in self.patches:p.start()

    def tearDown(self):
        for p in reversed(self.patches):p.stop()

    def test_actual_helper_api_and_original_trace_required(self):
        value=d.independent_audit(self.payload,'C_guarded',self.fixture)
        self.assertTrue(value['passed'])
        self.assertIs(self.trace_seen[0],self.payload['evidence']['contact_trial_trace'])

    def test_empty_or_substituted_actual_journal_rejects(self):
        for edit in ('empty','input','mode'):
            bad=copy.deepcopy(self.payload)
            if edit=='empty':bad['journal']['outer_calls']=[]
            elif edit=='input':bad['journal']['outer_calls'][0]['outer_inputs'][0]=99
            else:bad['journal']['enabled']=False
            with self.assertRaises(RuntimeError):d.independent_audit(bad,'C_guarded',self.fixture)

    def test_inactive_must_match_saved_and_no_broader_route(self):
        for key in ('velocity','fallback'):
            bad=copy.deepcopy(self.payload)
            if key=='velocity':bad['velocity']=[99]
            else:bad['evidence']['fallback_systems']=[dict(omitted=True)]
            with self.assertRaises(RuntimeError):d.independent_audit(bad,'C_guarded',self.fixture)

    def test_negative_is_authenticated_but_not_physical_pass(self):
        bad=copy.deepcopy(self.payload)
        bad.update(returned=False,error="RuntimeError('inertial momentum closure failed')")
        bad['journal']['enabled']=False
        self.summary.update(original_negative_outer_calls=1,successful_outer_calls=0,
                            outer_results=[dict(original_final_gate_passed=False)])
        result=d.independent_audit(bad,'F1_original',self.fixture)
        self.assertTrue(result['passed'])
        self.assertFalse(result['physical_pass'])

    def test_candidate_cannot_inherit_negative_or_fail_to_activate(self):
        with self.assertRaises(RuntimeError):d.independent_audit(self.payload,'F1_guarded',self.fixture)
        self.summary.update(increment_inner_maps=2,original_negative_outer_calls=1)
        with self.assertRaises(RuntimeError):d.independent_audit(self.payload,'F1_guarded',self.fixture)

    def test_fresh_repeat_q_and_health_exact(self):
        self.summary['increment_inner_maps']=2
        previous=copy.deepcopy(self.payload)
        d.independent_audit(self.payload,'F1_guarded_repeat',self.fixture,previous=previous)
        previous['health']={'changed':True}
        with self.assertRaises(RuntimeError):
            d.independent_audit(self.payload,'F1_guarded_repeat',self.fixture,previous=previous)


class OriginalCyclePredicate(unittest.TestCase):
    def test_actual_pinned_cycle_function_with_no_model_import(self):
        class Array:
            def __init__(self,v): self.value=v
            def copy(self): return Array(copy.deepcopy(self.value))
        npfake=SimpleNamespace(asarray=lambda v,**k:Array(v))
        trace=dict(trial_inner_counts=[2],detailed_trials=[],cycle_guard_trials=[dict(trial_index=0,records=[
            dict(inner_index=i,map_output=[i],canonical_selected=False,cycle_detected=False,
                 health=dict(solver='standard_cold_pgs')) for i in range(2)])])
        paths=(d.ROOT/'stage243_staging/per_pose_guard_v1.py',d.ROOT/'stage239_staging/fixed_point_replay_v1.py',
               d.ROOT/'stage242_staging/contact_consistency_v1.py')
        plan=dict(source_files={str(p):d.sha(p) for p in paths})
        with patch.object(d,'read',lambda p:plan):
            actual=d.original_cycle_audit(trace,npfake,lambda x:None)
            self.assertTrue(actual['passed'])
            self.assertEqual(actual['outer_trials'],1)
            bad=copy.deepcopy(trace)
            bad['cycle_guard_trials'][0]['records'][1]['inner_index']=99
            with self.assertRaises(RuntimeError):d.original_cycle_audit(bad,npfake,lambda x:None)


if __name__=='__main__':
    unittest.main(verbosity=2)
