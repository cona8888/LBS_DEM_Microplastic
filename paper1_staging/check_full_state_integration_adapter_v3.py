"""Fake-mechanics controls of the actual generated loop, never native solves.

This is an engineering fixture. Its artificial field/mass/force operator does
not validate the physical candidate or authorize any numerical experiment.
"""
from contextlib import contextmanager,ExitStack
from pathlib import Path
from types import SimpleNamespace,FunctionType
from datetime import datetime,timezone
import copy
import importlib
import json
import math
import sys
import time
import unittest
from unittest.mock import patch
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'paper1_staging'),str(ROOT/'stage153_staging')]
import full_state_integration_adapter_v3 as a
import full_state_stepdoubling_v1 as p


class FakeCapture:
    @contextmanager
    def scope(self,role,before):
        self.role=role
        self.trace=dict(schema='fake-only',trial_inner_counts=[],trial_route_counts=[],cycle_guard_trials=[],detailed_trials=[])
        yield dict(contact_trial_trace=self.trace,normal_gap_operand_policy=dict(policy='fake-only',prepare_calls=[]),
            early_attempts=[],fallback_systems=[],repairs=[],stage119_repair_calls=[],certificates=[],
            sweep_certificates=[],backend_calls=[dict(enabled=True,backend='fake-only')])


class FakeBackend:
    def __init__(self,capture):
        self.value=False;self.log=[];self.capture=capture;self.fail=None;self.bearing=[]
        self.finite_re=SimpleNamespace(prolate_sphericity=lambda *x:1.,reynolds_number=lambda *x:0.)
    def set_recovery_mode(self,value):self.value=bool(value)
    def recovery_mode(self):return self.value
    def stokes_generalized_resistance(self,*x):return np.eye(6)
    def generalized_mass_matrix(self,*x):return np.eye(6),None
    def inertial_contact_step(self,q,bg,body,resistance,lub,mass,active,ell,h,*rest):
        role=self.capture.role;self.log.append((role,self.value,float(h)))
        self.capture.trace['trial_inner_counts'].append(1);self.capture.trace['trial_route_counts'].append([0,0])
        self.capture.trace['cycle_guard_trials'].append(dict(trial_index=len(self.capture.trace['cycle_guard_trials']),records=[]))
        if self.fail==role:raise RuntimeError('fixture physical failure')
        self.value=(role=='C')
        candidate=(q/h+bg+body)/(1/h+1)
        return candidate,dict(momentum_residual=0.,contact=dict(residual=0.,force_residual=0.,iterations=1),
            reynolds=0.,total_contact_iterations=1,load_bearing_grain_ids=list(self.bearing),
            reaction_world_by_grain={gid:[0.,0.,0.] for gid in self.bearing})


class FakeMonitor:
    def __init__(self,*args,**kwargs):
        self.anchor=None;self.contact_ids=();self.load_bearing_ids=();self.age=0.
    def update(self,h,*args):
        self.age+=h
        return dict(persistent_contact_observed=False)


def make_runtime(horizon=.08,cap=.01,exit_at=None):
    # Import/compile the original graph, but replace every physical callable
    # before invoking its generated integrator. No original force is called.
    modal=importlib.import_module('modal_rotation_dt_v1')
    capture=FakeCapture();backend=FakeBackend(capture)
    mechanics=SimpleNamespace(finite=lambda x:np.asarray(x,float),unit=lambda x:np.asarray(x,float)/np.linalg.norm(x),
        free_motion=lambda p,g,u,*rest:(np.r_[u,np.zeros(3)],None),
        advance_pose=lambda x,p,q,ell,h:(x+h*q[:3],p.copy()),
        linear_pose_exit_time=lambda x,p,q,ell,b,outlet,h:exit_at if exit_at is not None and exit_at<h else None)
    ns=dict(modal.CANDIDATE.__globals__)
    ns.update(np=np,copy=copy,json=json,time=time,math=math,inertial=backend,mechanics=mechanics,
        trap_event_v2=SimpleNamespace(TrapMonitor=FakeMonitor),
        geometry_tools=SimpleNamespace(swept_gap=lambda *args:1.),
        enrich=lambda geometry,contacts:contacts,
        lubrication_matrix=lambda *args:(np.zeros((6,6)),[]),
        gyro_load=lambda *args:np.zeros(3),shortest_mode=lambda *args:1.)
    selector=SimpleNamespace(select=lambda base,near,q,ell,speed,untruncated_dt:(base,[]))
    def assemble(*args):
        v=[None]*14;v[8]=cap;return v
    provider=lambda gate:dict(source=modal.GENERATED_SOURCE,namespace=ns,selector=selector,capture=capture,assemble=assemble)
    spec=dict(config=dict(prolate_semiaxes_m=[1.,1.,1.],dynamic_viscosity_Pa_s=1.,particle_density_kg_m3=1.,
        fluid_density_kg_m3=1.,gravity_m_s2=[0.,0.,0.],friction_coefficient=0.,added_mass_fraction=0.,
        target_mean_interstitial_velocity_m_s=1.,trap=dict(dwell_time_s=1.,speed_ratio=.01,drift_over_minor_radius=.01,absorbing=False),
        numerics=dict(displacement_fraction=1.,angle_limit_rad=1.,relaxation_fraction=1.,max_dt_s=cap,reynolds_limit=3.)),
        initial_state=dict(position_m=[0.,0.,0.],orientation=[1.,0.,0.],velocity_generalized=[0.]*6),
        field_metadata=dict(cell_length_m=100.),horizon_s=horizon)
    field=SimpleNamespace(sample=lambda x:(np.array([1.,0.,0.]),np.zeros((3,3))))
    geometry=SimpleNamespace(r=np.array([1.]),contacts=lambda *args:[])
    runtime=a.build_runtime(spec,'fake-only-binding',field,geometry,
        dispatch_gate=lambda:dict(native_dispatch_authorized=True,
            simulation_cutoff_utc=datetime.fromtimestamp(time.time()+100,timezone.utc).isoformat()),source_provider=provider)
    limits=p.Limits(1.,1.,1.,1.,8,1e-12,'1'*64)
    return runtime,limits,backend


def packet(runtime,limits,cp=None,rows=4,phase=None,work=30):
    return runtime.advance_packet(cp,limits,max_work_rows=work,pause_after_accepted_rows=rows,
        time_bound=time.time()+10,record_id='fixture',pause_at_phase=phase,
        previous_packet_receipt_sha256='2'*64 if cp is not None else None)


class Controls(unittest.TestCase):
    def test_actual_loop_ast_and_three_branch_work(self):
        r,l,b=make_runtime();x=packet(r,l,rows=2)
        self.assertEqual(x['status'],'paused_controller',x['error'])
        self.assertTrue(x['source_proof']['original_loop_ast_after_removing_two_hooks_identical'])
        self.assertEqual([z['role'] for z in x['work_branches']],['C','F1','F2'])
        self.assertEqual(x['work_rows'],3);self.assertEqual(len(x['accepted_rows']),2)
        self.assertEqual(x['checkpoint']['physical_checkpoint']['state_sha256'],a.original_digest(x['checkpoint']['physical_checkpoint']['state']))

    def test_serial_vs_even_split_complete_state(self):
        r,l,_=make_runtime();serial=packet(r,l,rows=4)
        left=packet(r,l,rows=2);right=packet(r,l,a.controller_checkpoint(left),rows=2)
        self.assertEqual(a.trace_rows(serial),a.trace_rows(left)+a.trace_rows(right))
        self.assertEqual(a.numeric_restart_signature(serial),a.numeric_restart_signature(right))

    def test_all_between_branch_phases(self):
        for phase in ('C_done','F1_done','F2_done','decision_done'):
            r,l,_=make_runtime();serial=packet(r,l,rows=2)
            left=packet(r,l,phase=phase,rows=2)
            self.assertEqual(len(left['accepted_rows']),0,phase)
            right=packet(r,l,a.controller_checkpoint(left),rows=2)
            self.assertEqual(a.numeric_restart_signature(serial),a.numeric_restart_signature(right),phase)
            self.assertEqual(serial['work_rows'],left['work_rows']+right['work_rows'])

    def test_odd_publication_only_after_decision(self):
        r,l,_=make_runtime();serial=packet(r,l,rows=4)
        left=packet(r,l,rows=1)
        self.assertEqual(left['cursor_after']['phase'],'publish_second_half')
        self.assertEqual(left['work_rows'],3)
        right=packet(r,l,a.controller_checkpoint(left),rows=3)
        self.assertEqual(a.trace_rows(serial),a.trace_rows(left)+a.trace_rows(right))
        self.assertEqual(a.numeric_restart_signature(serial),a.numeric_restart_signature(right))

    def test_source_policy_and_old_bare_checkpoint_reject_before_force(self):
        r,l,b=make_runtime();old=dict(schema=1,state={},contract='old',state_sha256='old')
        with self.assertRaises(a.Stop):packet(r,l,old)
        self.assertEqual(b.log,[])
        good=packet(r,l,rows=2)['checkpoint'];good['policy_sha256']='3'*64
        count=len(b.log)
        with self.assertRaises(a.Stop):packet(r,l,good)
        self.assertEqual(len(b.log),count)

    def test_coarse_recovery_never_leaks_into_first_half(self):
        r,l,b=make_runtime();x=packet(r,l,rows=2)
        self.assertEqual([(role,mode) for role,mode,_ in b.log],[('C',False),('F1',False),('F2',False)])

    def test_physical_failure_preserved_no_successor(self):
        r,l,b=make_runtime();b.fail='C';x=packet(r,l,rows=2)
        self.assertEqual(x['status'],'negative');self.assertEqual(x['work_rows'],1)
        self.assertEqual([z[0] for z in b.log],['C']);self.assertEqual(x['accepted_rows'],[])
        self.assertEqual(a.packet_summary(x)['known_unaccepted_rows'],1)

    def test_export_is_bounded_negative_without_extension(self):
        r,l,b=make_runtime(exit_at=.001);x=packet(r,l,rows=2)
        self.assertEqual(x['status'],'negative');self.assertEqual(x['accepted_rows'],[])
        self.assertEqual(x['work_branches'][0]['result_status'],'full_window_exit')
        self.assertEqual(len(b.log),1)

    def test_finite_work_limit_no_partial_production_pair(self):
        r,l,b=make_runtime();x=packet(r,l,rows=20,work=5)
        self.assertEqual(x['work_rows'],3);self.assertEqual(len(b.log),3)
        self.assertEqual(x['cursor_after']['phase'],'idle')

    def test_history_roundtrip_and_original_sentinels(self):
        literal=[[0.,1.,float('inf')],[1.,2.,-float('inf')]]
        store=a.HistoryStore(literal);h=store.start('4'*64);fork=h.fork();fork.append([2.,3.])
        self.assertEqual(store.materialize(h.node),literal)
        self.assertEqual(store.materialize(fork.node),literal+[[2.,3.]])
        self.assertEqual(a.token(float('inf')),a.token(float('inf')))
        with self.assertRaises(a.Stop):a.token(float('nan'))

    def test_nonzero_literal_midpoint_and_exact_full_horizon(self):
        for t in (.15,.15358074327919755,.4,.9364396280429767):
            z=a.choose_clock_interval(t,3.108865289e-7,1e-15,8)
            self.assertEqual(z['h_s'],3.108865289e-7)
            self.assertEqual(t+z['first_interval_s'],z['midpoint_time_s'])
            self.assertEqual(z['midpoint_time_s']+z['second_interval_s'],z['end_time_s'])
        r,l,_=make_runtime(horizon=.025)
        x=packet(r,l,rows=100,work=30)
        self.assertEqual(x['status'],'present_at_horizon',x['error'])
        self.assertEqual(x['checkpoint']['physical_checkpoint']['state']['t'],.025)

    def test_administrative_time_pause_does_not_clip_full_horizon(self):
        r,l,_=make_runtime(horizon=.08)
        x=r.advance_packet(None,l,max_work_rows=30,pause_after_time_s=.015,
            time_bound=time.time()+10,record_id='clock-pause')
        self.assertEqual(x['checkpoint']['physical_checkpoint']['state']['t'],.02)
        self.assertEqual(x['cursor_after']['phase'],'idle')
        self.assertEqual(x['work_rows'],6)
        self.assertEqual(r.spec['horizon_s'],.08)

    def test_pure_policy_arithmetic_matches_compiled_bridge(self):
        limits=p.Limits(2.,.01,.01,.01,8,1e-12,'1'*64)
        def frame(i,parent,t,x,q):
            return dict(token=str(i)*64,parent=parent,state=dict(t=t,x=[x,0.,0.],p=[1.,0.,0.],q=[q,0.,0.,0.,0.,0.]))
        origin=frame(1,None,.4,0.,0.);coarse=frame(2,origin['token'],.4+.01,.02,.03)
        first=frame(3,origin['token'],.4+.01/2,.01,.015);second=frame(4,first['token'],.4+.01,.021,.031)
        def endpoint(f):
            s=f['state'];return p.Endpoint(s['t'],tuple(s['x']),tuple(s['p']),tuple(s['q']),f['token'],
                f['parent'] or '0'*64,'5'*64,'6'*64,limits.numerical_binding,True)
        actual=a.decision_values(limits,origin,coarse,first,second,.01,.01,0)
        expected=p.decide(limits,endpoint(origin),.01,.01,0,endpoint(coarse),endpoint(first),endpoint(second))
        for key in ('action','position_defect_m','director_defect','velocity_defect_over_U','scaled_defect','next_h_s','next_halving_depth'):
            self.assertEqual(actual[key],getattr(expected,key))

    def test_accuracy_reject_work_retained_and_bounded(self):
        r,l,b=make_runtime();l=p.Limits(1.,1e-15,1.,1e-15,8,1e-12,'1'*64)
        x=packet(r,l,rows=2,work=12)
        self.assertEqual(x['work_rows'],12);self.assertEqual(len(b.log),12)
        self.assertEqual(x['accepted_rows'],[])
        self.assertTrue(all(t['decision']['action']=='discard_all_and_halve' for t in x['trials']))
        self.assertEqual(a.packet_summary(x)['rejected_rows'],12)
        self.assertEqual(x['cursor_after']['phase'],'after_rejection')

    def test_real_original32_vs_compiled_C32_with_fake_mechanics(self):
        r,l,b=make_runtime(horizon=1.)
        old=a._native_smoke(r,l,'original','7'*64,'fixture gaps','8'*64)
        compiled=a._native_smoke(r,l,'compiled','7'*64,'fixture gaps','8'*64)
        self.assertEqual(old['work_rows'],compiled['work_rows'])
        self.assertEqual(old['record']['rows'],compiled['record']['rows'])
        self.assertEqual(old['physical_checkpoint'],compiled['physical_checkpoint'])
        self.assertEqual(len(b.log),64)
        self.assertTrue(all(v[0]=='original_nominal' for v in b.log[:32]))
        self.assertTrue(all(v[0]=='C' for v in b.log[32:]))
        self.assertNotIn('checkpoint',compiled)

    def test_explicit_prelude_counts_synthetic_kernels_and_restores(self):
        hot=SimpleNamespace(phase=lambda label:label)
        def warmup():return [hot.phase('false'),hot.phase('true')]
        hot.warmup=warmup
        def configured():hot.warmup()
        configured=FunctionType(configured.__code__,{**globals(),'hot':hot},configured.__name__,configured.__defaults__,configured.__closure__)
        backend=SimpleNamespace(inertial_contact_step=lambda:None)
        kernel=SimpleNamespace(warm=lambda:dict(contact_solver_calls=0,outer_calls=0),reset=lambda:None)
        candidate=SimpleNamespace(warm=lambda:None,__file__='fake-arithmetic')
        def outer():pass
        outer=FunctionType(outer.__code__,{'candidate':candidate})
        def execute():pass
        execute=FunctionType(execute.__code__,{'frozen':SimpleNamespace(execute=outer)})
        configure_path=SimpleNamespace(configure=configured)
        q=SimpleNamespace(reference=SimpleNamespace(JOB=SimpleNamespace(parent=SimpleNamespace(b=SimpleNamespace(old=SimpleNamespace(parent=configure_path))))),
            baseline=SimpleNamespace(execute=execute),job=SimpleNamespace(observer=SimpleNamespace(backend=backend)),kernel=kernel)
        real_import=a.importlib
        original_phase=hot.phase;original_outer=backend.inertial_contact_step
        a.importlib=SimpleNamespace(import_module=lambda name:SimpleNamespace(s=SimpleNamespace(q=q)))
        try:
            report=a.native_stack_prelude(lambda:dict(native_dispatch_authorized=True,native_prelude_authorized=True,
                simulation_cutoff_utc=datetime.fromtimestamp(time.time()+100,timezone.utc).isoformat()))
        finally:a.importlib=real_import
        self.assertEqual(report['nonadvancing_contact_kernel_invocations'],2)
        self.assertEqual(report['saved_work_rows'],0);self.assertEqual(report['target_outer_transport_calls'],0)
        self.assertIs(hot.phase,original_phase);self.assertIs(backend.inertial_contact_step,original_outer)

    def test_half_state_cap_mismatch_is_retained_accuracy_rejection(self):
        r,l,b=make_runtime()
        r.selector.select=lambda base,near,q,ell,speed,untruncated_dt:(min(base,.001) if q[0]>0 else base,[])
        x=packet(r,l,rows=2,work=30)
        self.assertEqual(x['status'],'paused_controller',x['error'])
        rejects=[t for t in x['trials'] if t['decision']['action']=='discard_all_and_halve']
        self.assertGreater(len(rejects),0)
        self.assertTrue(all(t['decision']['reason']=='cap_mismatch' and t['decision']['scaled_defect'] is None for t in rejects))
        self.assertEqual(x['work_rows'],3*len(x['trials']))
        self.assertEqual(x['checkpoint']['physical_checkpoint']['state']['rejected'],0)

    def test_new_origin_can_recover_fresh_original_cap(self):
        r,l,_=make_runtime()
        r.selector.select=lambda base,near,q,ell,speed,untruncated_dt:(min(base,.001) if q[0]==0 else base,[])
        x=packet(r,l,rows=4,work=30)
        self.assertEqual([t['h_s'] for t in x['trials']],[.001,.01])
        self.assertEqual([t['depth'] for t in x['trials']],[0,0])

    def test_literal_original_inner_scope_extraction_no_integration(self):
        reconstruction=importlib.import_module('reconstruct_fixed_pose_v3')
        q=reconstruction.s.q
        first=q.job.parent.engine.runtime.previous.api.frozen.Runner.integrate.__func__.__globals__['parent']
        modules=[first,first.h.candidate,first.h.candidate.parent,first.h.candidate.parent.parent]
        for module in modules:
            scope,proof=a.extract_original_scope(module.integrate)
            self.assertTrue(proof['original_prefix_and_finally_ast_identical'])
            self.assertEqual(proof['nested_integrate_calls_replaced_by_yield'],1)
        # Execute the actual extracted Stage80 prefix/finally against fake
        # handles. Its original nested integrate must never be invoked.
        source80=modules[-1];scope,_=a.extract_original_scope(source80.integrate)
        phase=[];initial=object();original_sweep=object();replacement=object()
        contact=SimpleNamespace(reuse_stats=lambda:{},set_recovery_mode=lambda value:phase.append(value))
        core=SimpleNamespace(geometry_tools=SimpleNamespace(swept_gap=original_sweep),inertial=initial,
            integrate=lambda *args,**kwargs:(_ for _ in ()).throw(AssertionError('nested integration forbidden')))
        fast=SimpleNamespace(stats=lambda:{},swept_gap=replacement)
        function=scope.__wrapped__
        fake=FunctionType(function.__code__,{**function.__globals__,'core':core,'fast':fast,'contact':contact},
            function.__name__,function.__defaults__,function.__closure__)
        with contextmanager(fake)():
            self.assertIs(core.inertial,contact);self.assertIs(core.geometry_tools.swept_gap,replacement)
        self.assertIs(core.inertial,initial);self.assertIs(core.geometry_tools.swept_gap,original_sweep)
        self.assertEqual(phase,[False,False])

    def test_actual_cold_inner_scope_live_binding_and_restoration_no_force(self):
        reconstruction=importlib.import_module('reconstruct_fixed_pose_v3');q=reconstruction.s.q
        namespace=reconstruction.modal.CANDIDATE.__globals__
        original_sweep=namespace['geometry_tools'].swept_gap
        original_portfolio=q.job.parent.engine.runtime.probe.RECOVERY.portfolio._solve
        with a.original_inner_execution_scopes(q) as proofs:
            provider=a.default_source_provider(lambda:{})
            self.assertEqual(len(proofs),4)
            self.assertIs(provider['namespace']['inertial'],q.job.observer.backend)
            self.assertIs(provider['namespace']['geometry_tools'].swept_gap,
                          q.job.parent.engine.runtime.previous.candidate.swept_gap)
        self.assertIs(namespace['geometry_tools'].swept_gap,original_sweep)
        self.assertIs(q.job.parent.engine.runtime.probe.RECOVERY.portfolio._solve,original_portfolio)

    def test_literal_supported_bearing_survives_dwell_reset(self):
        r,l,b=make_runtime();b.bearing=[15]
        r.geometry.contacts=lambda *args:[(15,0.,np.array([1.,0.,0.]),np.zeros(3),1.)]
        x=packet(r,l,rows=2)
        self.assertEqual(x['status'],'paused_controller',x['error'])
        self.assertTrue(all(row['supported_bearing_ids']==[15] for row in x['accepted_rows']))
        self.assertEqual(x['checkpoint']['physical_checkpoint']['state']['monitor']['load_bearing_ids'],[])

    def test_failed_v1_order_and_repaired_real_production_scope_graph(self):
        """Actual original contexts/kernel AST, no field, warm, force or transport.

        Only the kernel's private source-validation flag/templates are supplied
        by a private AST-only build. It compiles Python callback source, never
        evaluates a residual or invokes a native contact/optimizer function.
        """
        import full_state_integration_adapter_v1 as old
        reconstruction=importlib.import_module('reconstruct_fixed_pose_v3');q=reconstruction.s.q
        kernel=q.kernel;original=kernel.scope.__wrapped__;namespace=dict(original.__globals__)
        namespace.update(_SOURCE_VALIDATED=True,_TEMPLATES=None,_ACTIVE=False)
        origins=[]
        def checked_origins():
            origins.append('entry');return kernel._origins()
        namespace['_origins']=checked_origins
        build=FunctionType(kernel.build.__code__,namespace,kernel.build.__name__,kernel.build.__defaults__,kernel.build.__closure__)
        namespace['build']=build
        build()  # Pure Python AST template compilation; no callback evaluation.
        originals=(kernel.hot.s50._solve,kernel.s53._solve,kernel.hot.s50._project,
                   q.job.observer.backend.inertial_contact_step,q.job.observer.backend.stage42.inertial_contact_step)
        clone=FunctionType(original.__code__,namespace,original.__name__,original.__defaults__,original.__closure__)
        wrapped=contextmanager(clone)
        raw=q.raw.__globals__;native=q.job.parent.engine.runtime
        outer=q.baseline.execute.__globals__['frozen'].execute;deps=outer.__globals__
        future=datetime.fromtimestamp(time.time()+100,timezone.utc).isoformat();epoch=time.time()+100
        gate=lambda:dict(simulation_cutoff_utc=future)
        native_calls=[];real_outer=q.job.observer.backend.inertial_contact_step
        def no_outer(*args,**kwargs):
            native_calls.append(1);raise AssertionError('No native outer solve authorized in source regression')
        @contextmanager
        def production_outer_graph():
            with ExitStack() as stack:
                stack.enter_context(deps['repair'].scope(native,True,epoch))
                stack.enter_context(deps['candidate'].scope('compiled_direct'))
                stack.enter_context(deps['previous'].baseline.repair.scope(native,True,epoch))
                stack.enter_context(raw['prior'].p.hot.scope())
                stack.enter_context(raw['parent'].fix.scope())
                stack.enter_context(raw['deadline'].scope(native,future,True))
                stack.enter_context(raw['capture'].scope(native,True))
                stack.enter_context(raw['prior'].candidate.scope())
                yield
        with patch.object(kernel,'scope',wrapped),patch.object(q.job.observer.backend,'inertial_contact_step',no_outer):
            origins.clear()
            with self.assertRaisesRegex(RuntimeError,'Frozen original solver/projection origins'):
                with production_outer_graph(),native.repair_scope(),old.original_inner_execution_scopes(q):
                    with old.QualifiedCapture(q,gate).packet_scope():
                        self.fail('Failed V1 graph must never reach numerical dispatch')
            self.assertEqual(origins,['entry'])
            origins.clear()
            capture=a.QualifiedCapture(q,gate)
            with production_outer_graph():
                with capture.packet_scope():
                    self.assertEqual(origins,['entry'])
                    self.assertEqual(capture.trace['trial_inner_counts'],[])
                    self.assertEqual(capture.gap_log['prepare_calls'],[])
                    self.assertEqual(len(capture.inner_proofs),4)
                    self.assertIs(reconstruction.modal.CANDIDATE.__globals__['geometry_tools'].swept_gap,
                                  raw['prior'].candidate.swept_gap)
            self.assertEqual(origins,['entry'])
            self.assertEqual(native_calls,[])
        self.assertIs(q.job.observer.backend.inertial_contact_step,real_outer)
        restored=(kernel.hot.s50._solve,kernel.s53._solve,kernel.hot.s50._project,
                  q.job.observer.backend.inertial_contact_step,q.job.observer.backend.stage42.inertial_contact_step)
        self.assertEqual(originals,restored)

    def test_v2_changes_only_scope_and_administrative_evidence(self):
        import ast
        old=ast.parse((ROOT/'paper1_staging/full_state_integration_adapter_v1.py').read_text(encoding='utf-8'))
        new=ast.parse((ROOT/'paper1_staging/full_state_integration_adapter_v2.py').read_text(encoding='utf-8'))
        def functions(tree):
            result={}
            for item in tree.body:
                if isinstance(item,ast.FunctionDef):result[item.name]=ast.dump(item,include_attributes=False)
                if isinstance(item,ast.ClassDef):
                    for value in item.body:
                        if isinstance(value,ast.FunctionDef):result[item.name+'.'+value.name]=ast.dump(value,include_attributes=False)
            return result
        before,after=functions(old),functions(new)
        changed={name for name in before if before[name]!=after[name]}
        self.assertEqual(changed,{'QualifiedCapture.packet_scope','Runtime.advance_packet','native_execution_scope','_native_smoke'})
        for name in ('compile_machine','Runtime._advance_packet','Runtime.select_dt','Runtime._branch','Runtime.complete',
                     'decision_values','choose_clock_interval','original_inner_execution_scopes'):
            self.assertEqual(before[name],after[name],name)


    def test_v3_changes_only_factory_import_and_preserved_v2_pin(self):
        import ast
        before=ast.parse((ROOT/'paper1_staging/full_state_integration_adapter_v2.py').read_text(encoding='utf-8'))
        after=ast.parse((ROOT/'paper1_staging/full_state_integration_adapter_v3.py').read_text(encoding='utf-8'))
        left={n.name:n for n in before.body if isinstance(n,(ast.FunctionDef,ast.ClassDef))}
        right={n.name:n for n in after.body if isinstance(n,(ast.FunctionDef,ast.ClassDef))}
        changed={name for name in left if ast.dump(left[name],include_attributes=False)!=ast.dump(right[name],include_attributes=False)}
        self.assertEqual(changed,{'native_execution_scope'})
        def revert(node):
            if isinstance(node,ast.Constant) and node.value=='audit_full_state_stepdoubling_v2':node.value='audit_full_state_stepdoubling_v1'
            for child in ast.iter_child_nodes(node):revert(child)
        revert(right['native_execution_scope'])
        self.assertEqual(ast.dump(left['native_execution_scope'],include_attributes=False),ast.dump(right['native_execution_scope'],include_attributes=False))
        self.assertEqual(a.SOURCE_PINS['paper1_staging/full_state_integration_adapter_v2.py'],'eb8a6d0c87026303e9c0e8807c61ffd816a11aa1e0216c7cf527ebd9b49db252')
        self.assertEqual(set(left),set(right))

    def test_v3_actual_factory_marker_belongs_new_auditor_in_readonly_environment(self):
        # No physical field read, scope warm, force, geometry query or transport:
        # the ACTUAL new factory only constructs its original source-bound callback.
        import tempfile
        audit=importlib.import_module('audit_full_state_stepdoubling_v2')
        old_audit=importlib.import_module('audit_full_state_stepdoubling_v1')
        reconstruction=importlib.import_module('reconstruct_fixed_pose_v3');s=reconstruction.s
        physical_path=ROOT/'paper1_designs/full_horizon_repair_20261018/physical_cases_qualification_01.json'
        physical=json.loads(physical_path.read_text(encoding='utf-8-sig'));spec=physical['cases'][0]['spec']
        metadata=spec['field_metadata'];field=object();geometry=object();force_calls=[]
        @contextmanager
        def no_field_scope(*args,**kwargs):yield
        def forbidden_force(*args,**kwargs):
            force_calls.append(1);raise AssertionError('Native force prohibited in marker source control')
        backend=s.q.job.observer.backend
        gate=lambda:dict(read_only_audit_authorized=True,simulation_cutoff_utc=datetime.fromtimestamp(time.time()+100,timezone.utc).isoformat())
        with tempfile.TemporaryDirectory() as td:
            plan=Path(td)/'plan.json';auth=Path(td)/'auth.json';plan.write_text('{}');auth.write_text('{}')
            with patch.object(s.context.fields,'scope',no_field_scope),patch.object(s.api.fields,'load',lambda *args:(field,dict(sand_centres_m=[],sand_radii_m=[]),metadata)),patch.object(s.api.frozen.h.geometry_exact_v1,'GrainGeometry',lambda *args:geometry),patch.object(backend,'inertial_contact_step',forbidden_force):
                with a.native_execution_scope(spec,'source-fixture-only-binding',gate,plan_path=plan,auth_path=auth,physical_path=physical_path,numerical=False) as env:
                    callback=env['mechanical_stencil_adapter']
                    self.assertIs(callback.original_stencil_adapter_marker,audit._ORIGINAL_STENCIL_ADAPTER_MARKER)
                    self.assertIsNot(callback.original_stencil_adapter_marker,old_audit._ORIGINAL_STENCIL_ADAPTER_MARKER)
                    self.assertEqual(callback.__code__.co_filename,audit.create_original_mechanical_adapter.__code__.co_filename)
                    self.assertIsNone(env['runtime']);self.assertEqual(env['native_setup_force_calls'],0)
                    self.assertIn(str(Path(audit.__file__).resolve()),env['source_bindings'])
                    self.assertNotIn(str(Path(old_audit.__file__).resolve()),callback.source_files)
        self.assertEqual(force_calls,[])



if __name__=='__main__':unittest.main(verbosity=2)
