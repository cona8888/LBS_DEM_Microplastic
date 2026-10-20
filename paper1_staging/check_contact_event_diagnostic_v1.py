"""Source/mock administrative controls only. No native/model/actor is imported."""
from __future__ import annotations
import ast
import copy
from dataclasses import asdict,make_dataclass
from datetime import datetime, timezone
import importlib.abc
import importlib.util
import json
import lzma
from pathlib import Path
import sys
import tempfile
import types
import unittest


ROOT=Path(__file__).resolve().parents[1]
STAGING=ROOT/'paper1_staging'


class NoEngine(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        blocked=('run_core_v2','transport_context_v1','compare_core_v2','numba',
                 'numpy','cost_screen_v1','full_state_integration_adapter_',
                 'audit_full_state_stepdoubling_')
        if any(fullname==s or fullname.startswith(s) for s in blocked):
            raise AssertionError('No model/native import allowed in source controls: '+fullname)
        return None


tripwire=NoEngine()
sys.meta_path.insert(0,tripwire)
spec=importlib.util.spec_from_file_location('_inactive_event_diagnostic_controls',STAGING/'run_contact_event_diagnostic_v1.py')
r=importlib.util.module_from_spec(spec);sys.modules[spec.name]=r;spec.loader.exec_module(r)


class Controls(unittest.TestCase):
    def setUp(self):
        self.n=r.private_administration()._namespace
        self.saved=dict(self.n)
        self.n['_RESERVE_HIGHWATER']=[3600.]
        self.temp=tempfile.TemporaryDirectory(prefix='event_diagnostic_source_')
        self.folder=Path(self.temp.name)

    def tearDown(self):
        self.n.clear();self.n.update(self.saved)
        self.temp.cleanup()

    def test_private_complete_graph_never_rebinds_frozen_globals(self):
        old=sys.modules['_frozen_contact_event_admin_source']
        self.assertNotEqual(old.OUT,r.OUT)
        self.assertEqual(old.MAX_WORK,17991767)
        self.assertEqual(self.n['MAX_WORK'],140000)
        for name in ('worker','commit','finish_child','post_replay_record','restart_equal'):
            self.assertIsNot(self.n[name],getattr(old,name))
            self.assertIs(self.n[name].__code__,getattr(old,name).__code__)
            self.assertIs(self.n[name].__globals__,self.n)
        self.assertIs(self.n['_DIAGNOSTIC_ORIGINAL_PACKET'].__code__,old.Execution.packet.__code__)
        self.assertIs(self.n['Execution'].packet.__globals__,self.n)
        self.assertIsNot(self.n['_RESOURCE_LAST'],old._RESOURCE_LAST)

    def test_actual_worker_and_watchdog_are_literal_frozen_code(self):
        old=sys.modules['_frozen_contact_event_admin_source']
        for name in ('worker','supervise','start_child','finish_child','register_self',
                     'inspect_identity','exact_stop','authenticate_prior_branch'):
            self.assertIs(self.n[name].__code__,getattr(old,name).__code__)
        # All JSON actor publication and exact identity semantics remain the
        # previously reviewed frozen implementations, not a fake launcher.
        self.assertIs(self.n['commit'].__code__,old.commit.__code__)

    def test_no_authority_actor_or_model_on_import(self):
        tree=ast.parse(r.SELF.read_text())
        calls=[]
        for node in tree.body:
            if isinstance(node,(ast.FunctionDef,ast.ClassDef,ast.If)):
                continue
            calls.extend(ast.unparse(c.func) for c in ast.walk(node) if isinstance(c,ast.Call))
        self.assertFalse(any('Popen' in call or 'authorize' in call or 'native' in call for call in calls))
        self.assertNotIn('numba',sys.modules)
        self.assertNotIn('run_core_v2',sys.modules)

    def test_scope_conservative_constructive_budget_and_old_unknown_retained(self):
        scope=r.approval_scope()
        self.assertEqual(scope['maximum_window_minutes'],120)
        self.assertEqual(scope['maximum_native_minutes'],60)
        self.assertEqual(r.BASELINE['diagnostic_work_rows'],157450)
        self.assertEqual(r.BASELINE['diagnostic_records'],103)
        rows=60000+128+2*4*2*768+2*2*2*4998+2*2*4998+256
        calls=22+4+2*4*3+2*2*3+2*3+1
        self.assertEqual((rows,calls),(132648,69))
        self.assertLessEqual(rows,r.MAX_WORK);self.assertLessEqual(calls,r.MAX_RECORDS)
        self.assertEqual(r.PRIOR['unknown_reserved_work_upper_bound'],4838)
        self.assertTrue(r.prior_attempt_accounting()['old_unknown_work_never_refunded'])

    def test_missing_or_unpinned_approval_rejects_without_creation(self):
        self.n['environment']=lambda:None
        self.n['OUT']=self.folder/'absent_run'
        with self.assertRaises((FileNotFoundError,RuntimeError)):
            r.authorize('0'*64,'1'*64,'2'*64)
        self.assertFalse((self.folder/'absent_run').exists())

    def clock(self):
        return dict(start_utc='2026-10-19T10:00:00+00:00',
            simulation_cutoff_utc='2026-10-19T11:00:00+00:00',
            end_utc='2026-10-19T12:00:00+00:00',original_shared_end_utc=r.ABSOLUTE_END,
            original_outer_clock_sha256='a'*64,proposal_sha256='b'*64)

    def test_fixed_clock_does_not_reset_elapsed_or_overrun_outer_cutoff(self):
        self.n['sha']=lambda p:'a'*64 if p==r.OUTER_CLOCK else 'b'*64
        clock=self.clock();validate=self.n['validate_window']
        now=r.instant(clock['start_utc'])+60
        self.assertEqual(validate(clock,now=now)[0],r.instant(clock['start_utc']))
        variants=[]
        for key,value in (('end_utc','2026-10-19T12:00:01+00:00'),
            ('simulation_cutoff_utc','2026-10-19T11:00:01+00:00'),
            ('original_shared_end_utc','2026-10-25T07:43:33.769535+00:00')):
            item=dict(clock);item[key]=value;variants.append(item)
        late=dict(clock,start_utc='2026-10-24T06:00:00+00:00',
            simulation_cutoff_utc='2026-10-24T07:00:00+00:00',end_utc='2026-10-24T07:30:00+00:00')
        variants.append(late)
        for item in variants:
            with self.subTest(item=item),self.assertRaises(RuntimeError):validate(item,now=now)
        with self.assertRaises(RuntimeError):validate(clock,now=r.instant(clock['simulation_cutoff_utc']))

    def test_approval_requires_exact_human_scope_provenance_and_fixed_clock(self):
        self.n['sha']=lambda p:{r.PROPOSAL:'a'*64,r.CLOCK:'b'*64,r.OUTER_CLOCK:'c'*64}[p]
        self.n['validate_window']=lambda clock:None
        good=dict(passed=True,proposal_sha256='a'*64,required_human_approval_scope=r.approval_scope(),
            independent_contact_event_diagnostic_authorized=True,human_origin=True,
            verbatim_direct_human_reply='Approve this bounded diagnostic',approval_provenance={'direct_reply_id':'fixture-only'},
            window_clock_sha256='b'*64,original_outer_clock_sha256='c'*64)
        self.n['verify_approval'](good,{})
        for key,value in (('human_origin',False),('approval_provenance',{}),
            ('verbatim_direct_human_reply',''),('proposal_sha256','d'*64),
            ('required_human_approval_scope',{}),('independent_contact_event_diagnostic_authorized',False)):
            item=copy.deepcopy(good);item[key]=value
            with self.subTest(key=key),self.assertRaises(RuntimeError):self.n['verify_approval'](item,{})

    def test_seed_reader_authenticates_three_literal_FULL_states_without_force(self):
        # Reading immutable pre-made source/mock inputs is not model execution
        # or old raw replay. Every physical state/history/counter remains exact.
        states=[]
        for level in r.LEVELS:
            ref=self.n['seed_reference'](level)
            cp,value=self.n['load_seed'](ref)
            states.append(cp['physical_checkpoint']['state'])
            self.assertEqual(value['case']['level_id'],level)
            self.assertEqual(cp['physical_checkpoint']['state']['t'],r.START_T)
            loaded,parent,history=self.n['load_reference'](ref,{})
            self.assertEqual(loaded,cp);self.assertIsNone(parent)
            self.assertEqual(len(history),1972)
            bad=dict(ref,no_core_prefix_credit=False)
            with self.assertRaises(RuntimeError):self.n['load_reference'](bad,{})
        self.assertTrue(all(v==states[0] for v in states))

    def test_seed_history_embedded_once_new_root_codec_not_old_prefix(self):
        physical=self.folder/'physical.json';physical.write_text('{}')
        self.n['PHYSICAL']=physical
        self.n['OUT']=self.folder
        self.n['resource_guard']=lambda **kwargs:None
        history=[[.1,1,2,3],[.2,4,5,6]]
        full=dict(state=dict(history=history,t=.2))
        packet=dict(checkpoint=dict(physical_checkpoint=full),
                    original_FULL_output_sha256=r.original_digest(full))
        prefix=self.n['store_packet'](self.folder/'first',packet,None,history)
        wire=json.loads(lzma.decompress(Path(prefix['path']).read_bytes()))
        marker=wire['packet']['checkpoint']['physical_checkpoint']['state']['history']
        self.assertIsNone(marker['parent']);self.assertEqual(marker['parent_length'],0)
        self.assertEqual(marker['delta'],history)
        self.assertEqual(self.n['load_packet'](prefix['path'],prefix,None,history),packet)
        self.assertEqual(self.n['load_reference'](prefix,{})[0],packet['checkpoint'])
        with self.assertRaises((FileExistsError,RuntimeError)):
            self.n['store_packet'](self.folder/'first',packet,None,history)

    def counts(self):
        return self.n['empty_counts']()

    def test_standalone_all_work_caps_include_old_unknown_and_no_production(self):
        counts=self.counts()
        self.n['budget_guard'](counts,'f0p0625','standalone',4998)
        for kind in ('production','unknown'):
            with self.assertRaises(RuntimeError):self.n['budget_guard'](counts,'f0p0625',kind,3)
        counts['work_rows']=139999
        with self.assertRaises(RuntimeError):self.n['budget_guard'](counts,'f0p0625','standalone',3)
        counts=self.counts();counts['records']=72
        with self.assertRaises(RuntimeError):self.n['budget_guard'](counts,'f0p0625','standalone',3)
        counts=self.counts();counts['unresolved']=[{'unknown':4998}]
        with self.assertRaises(RuntimeError):self.n['budget_guard'](counts,'f0p0625','standalone',3)
        with self.assertRaises(RuntimeError):self.n['budget_guard'](self.counts(),'f0p125','standalone',3)

    def test_negative_ledger_no_successor_partial_admission_unknown_charged(self):
        self.n['OUT']=self.folder
        plan=self.folder/'plan.json';plan.write_text('{}');self.n['PLAN']=plan
        reserve=dict(index=1,level_id='f0p0625',kind='standalone',maximum_work_rows=99,
            design_sha256=r.sha(plan),label='f0p0625_local_001')
        self.n['commit'](self.folder/'reservations/000001.json',reserve)
        self.n['commit'](self.folder/'admissions/000001/results.json',dict(passed=True))
        counts=self.n['ledger']()
        self.assertEqual(counts['unknown_reserved_work_upper_bound'],99)
        self.assertEqual(counts['discarded_diagnostic_work_rows'],99)
        with self.assertRaises(RuntimeError):self.n['budget_guard'](counts,'f0p0625','standalone',3)

    def qualification_fixture(self,work=(384,192,192)):
        def packet(n,rows,phase='idle'):
            return dict(work_rows=n,accepted_rows=[{} for _ in range(rows)],work_branches=[],carried_branches=[],
                committed_branch_ids=[],cursor_after=dict(phase=phase),
                checkpoint=dict(physical_checkpoint=dict(state=dict(pending_trial=None))))
        packets=[packet(work[0],256),packet(work[1],128),packet(work[2],128)]
        calls=[]
        def invoke(level,kind,label,ref,**kwargs):
            calls.append(kwargs);return packets[len(calls)-1],{'packet':len(calls)},'f'*64
        execution=types.SimpleNamespace(packet=invoke,plan={'source_files':{}},reference_cache={})
        self.n['OUT']=self.folder;self.n['seal']=lambda folder,body:body
        self.n['sha']=lambda path:'a'*64
        self.n['load_reference']=lambda ref,cache:(dict(seed=True),None,[])
        self.n['restart_equal']=lambda *args,**kwargs:True
        self.n['accepted_journal']=lambda packet:[]
        self.n['event_journal']=lambda packet,which:[]
        return execution,calls

    def test_actual_qualification_combined_split_work_cap_and_bound_successor(self):
        ex,calls=self.qualification_fixture()
        body=self.n['qualify'](ex,'f0p0625','initial',{'explicit_seed':True})
        self.assertEqual([c['cap'] for c in calls],[768,768,576])
        self.assertEqual(body['discarded_all_work_rows'],768)
        self.assertTrue(body['original_path_restored_unchanged'])
        ex,calls=self.qualification_fixture((700,500,300))
        with self.assertRaises(RuntimeError):self.n['qualify'](ex,'f0p0625','initial',{'explicit_seed':True})
        self.assertEqual(calls[-1]['cap'],268)

    def test_actual_event_lookup_never_uses_shadow_or_rejected_trial(self):
        branches=[dict(branch_id=str(i),role=('C','F1','F2')[i%3]) for i in range(9)]
        packet=dict(work_branches=branches,carried_branches=[],
            committed_branch_ids=['1','2','7','8'],accepted_rows=[{}]*4,trials=[
                dict(branch_ids=['0','1','2'],macro_initial_cap_s=1,original_selected_cap_s=1,
                     decision=dict(action='commit_literal_halves')),
                dict(branch_ids=['3','4','5'],macro_initial_cap_s=.5,original_selected_cap_s=1,
                     decision=dict(action='discard_all_and_halve')),
                dict(branch_ids=['6','7','8'],macro_initial_cap_s=.5,original_selected_cap_s=1,
                     decision=dict(action='commit_literal_halves'))])
        journal=self.n['event_journal'](packet,'event_reduction')
        self.assertEqual([bool(x['trigger_grain_ids']) for x in journal],[False,False,True,True])
        self.assertEqual(self.n['event_split'](packet,'event_reduction')['j'],2)
        packet['trials'][0]['macro_initial_cap_s']=.5
        with self.assertRaises(RuntimeError):self.n['event_split'](packet,'event_reduction')

    def test_clock_worker_window_single_no_setup_refund_or_second_window(self):
        c=self.clock();now=r.instant(c['start_utc'])+60
        self.assertEqual(self.n['window_bounds'](c,now,1,900),r.instant(c['simulation_cutoff_utc']))
        with self.assertRaises(RuntimeError):self.n['window_bounds'](c,now,2,900)

    def test_dynamic_replay_reserve_only_grows_with_actual_rate_and_nextcap(self):
        self.n['OUT']=self.folder
        counts=self.counts();counts['standalone_work_rows']=60000;counts['work_rows']=55000
        low=self.n['replay_reserve'](counts)
        self.assertEqual(low,3600)
        self.n['seal'](self.folder/'admissions/000001',dict(passed=True,work_rows=128,
            independent_replay_seconds=4.))
        high=self.n['replay_reserve'](counts)
        self.assertGreater(high,low)
        counts['standalone_work_rows']=1;counts['work_rows']=0
        self.assertEqual(self.n['replay_reserve'](counts),high)
        docs=[r.read(p) for p in sorted((self.folder/'reserve_estimates').glob('*.json'))]
        self.assertEqual([x['postworker_reserve_seconds'] for x in docs],[low,high,high])
        self.assertTrue(all(x['proxy_is_not_guaranteed_completion'] for x in docs))

    def test_one_row_fixed_cost_is_not_extrapolated_as_per_row_slope(self):
        self.n['OUT']=self.folder
        self.n['seal'](self.folder/'admissions/000001',dict(passed=True,work_rows=1,
            independent_replay_seconds=.0275115))
        counts=self.counts();counts['standalone_work_rows']=140000
        reserve=self.n['replay_reserve'](counts)
        doc=r.read(self.folder/'reserve_estimates/000001.json')
        self.assertEqual(doc['seconds_per_row_proxy'],.01592)
        self.assertEqual(doc['maximum_observed_small_record_seconds'],.0275115)
        self.assertEqual(reserve,3600)

    def test_actual_packet_wrapper_rejects_missing_seed_coarse_and_path_overspend_before_dispatch(self):
        calls=[]
        self.n['_DIAGNOSTIC_ORIGINAL_PACKET']=lambda *args,**kwargs:calls.append((args,kwargs))
        self.n['local_path_usage']=lambda:{'f0p0625':dict(work_rows=19998,records=2)}
        execute=self.n['Execution'].packet
        for key,kind,label,ref,kwargs in (
            ('f0p125','standalone','not_allowed',None,{}),
            ('f0p0625','production','not_allowed',{},{}),
            ('f0p0625','standalone','restart',None,{}),
            ('f0p0625','standalone','f0p0625_local_003',{},dict(cap=3,pause_time=r.STOP_T))):
            with self.subTest(label=label),self.assertRaises(RuntimeError):
                execute(object(),key,kind,label,ref,**kwargs)
        self.assertFalse(calls)
        self.n['local_path_usage']=lambda:{'f0p0625':dict(work_rows=100,records=1)}
        execute(object(),'f0p0625','standalone','f0p0625_local_002',{},cap=3,pause_time=r.STOP_T)
        self.assertEqual(len(calls),1)

    def closure_fixture(self):
        old_out,old_plan=r.OUT,r.PLAN
        self.addCleanup(setattr,r,'OUT',old_out);self.addCleanup(setattr,r,'PLAN',old_plan)
        r.OUT=self.folder;r.PLAN=self.folder/'PLAN.json'
        self.n['OUT']=self.folder;self.n['PLAN']=r.PLAN
        self.n['environment']=lambda:None
        p=dict(end_utc=r.ABSOLUTE_END,source_files={},physical_inputs={},evidence_files={},historical_evidence_files={})
        self.n['commit'](r.PLAN,p)
        self.n['authority']=lambda *args,**kwargs:p
        self.n['inspect_identity']=lambda launch:dict(retired=True,fixture_only=True)
        parent=dict(pid=1,created=1.,command=['FAKE_SOURCE_CONTROL_PARENT'])
        supervisor=dict(pid=2,created=2.,command=['FAKE_SOURCE_CONTROL_SUPERVISOR'])
        owner=dict(pid=3,created=3.,command=['FAKE_SOURCE_CONTROL_OWNER'])
        worker=dict(pid=4,created=4.,command=['FAKE_SOURCE_CONTROL_WORKER'])
        actors={'launcher':parent,'supervisor':supervisor,'owner':owner,'windows/window_001':worker}
        logs={}
        for folder,launch in actors.items():
            self.n['commit'](self.folder/folder/'launch.json',launch)
            if folder=='supervisor':continue
            for name in ('stdout.log','stderr.log'):
                path=self.folder/folder/name;path.write_bytes(b'FAKE SOURCE CONTROL LOG\n');logs[str(path)]=r.sha(path)
        def actor_exit(folder,launch):
            result=dict(returncode=0,actual_returncode_observed_from_original_popen_handle=True,
                retirement_verified=True,launch=launch,logs={k:v for k,v in logs.items() if Path(k).parent==self.folder/folder})
            self.n['commit'](self.folder/folder/'exit.json',result)
            return result
        actor_exit('owner',owner);actor_exit('windows/window_001',worker)
        counts=dict(work_rows=0,records=0,fixture_only=True)
        self.n['ledger']=lambda:copy.deepcopy(counts)
        artifacts=self.n['artifact_inventory']()
        self.n['seal'](self.folder/'final_disposition_01',dict(passed=True,held_design_sha256=r.sha(r.PLAN),
            ledger=counts,artifacts=artifacts))
        self.n['seal'](self.folder/'supervisor/completion_01',dict(passed=True,held_design_sha256=r.sha(r.PLAN),
            directly_observed_owner_exit_sha256=r.sha(self.folder/'owner/exit.json'),
            directly_observed_owner_returncode=0,ledger=counts,
            final_disposition_sha256=r.sha(self.folder/'final_disposition_01/results.json')))
        wrapper=self.folder/'launcher/completion_01/results.json'
        self.n['seal'](wrapper.parent,dict(passed=True,supervisor_returncode_directly_observed=True,
            actual_supervisor_returncode=0,supervisor_launch=supervisor,
            closed_logs={k:v for k,v in logs.items() if Path(k).parent==self.folder/'launcher'}))
        m=dict(actual_supervisor_exit_observed=True,actual_supervisor_returncode=0,
            actual_parent_terminal_exit_observed=True,actual_parent_terminal_returncode=0,
            actual_exit_provenance={'fixture':'NO REAL ACTOR'},
            actual_parent_terminal_handle_reference={'fixture':'NO REAL TERMINAL'},
            administrative_parent=parent,wrapper_completion_sha256=r.sha(wrapper),
            design_sha256=r.sha(r.PLAN),closed_log_files=logs)
        return m

    def finish_fixture(self,m):
        path=self.folder/'outside_manifest.json'
        # Manifest is caller-owned external evidence, outside the native OUT
        # inventory; emulate that by excluding this ONE caller file from the
        # native artifact-inventory function (not from any actual raw file).
        self.n['commit'](path,m)
        original=self.n['artifact_inventory']
        self.n['artifact_inventory']=lambda **kwargs:{k:v for k,v in original(**kwargs).items() if Path(k)!=path}
        return r.close_execution(path,r.sha(path))

    def test_actual_closer_complete_mock_exit_chain_is_local_only(self):
        result=self.finish_fixture(self.closure_fixture())
        self.assertTrue(result['passed']);self.assertTrue(result['administrative_execution_closed'])
        self.assertFalse(result['full_path_accuracy_passed']);self.assertFalse(result['core_result_admitted'])

    def test_actual_closer_empty_mandatory_logs_is_negative_not_pass(self):
        m=self.closure_fixture();m['closed_log_files']={}
        result=self.finish_fixture(m)
        self.assertFalse(result['passed']);self.assertFalse(result['local_diagnostic_passed'])
        self.assertTrue(any(x['stage']=='mandatory_logs_and_immutable_final_inventory' for x in result['closure_errors']))

    def test_actual_closer_ledger_extension_is_negative_not_pass(self):
        m=self.closure_fixture()
        self.n['ledger']=lambda:dict(work_rows=3,records=1,fixture_only=True)
        result=self.finish_fixture(m)
        self.assertFalse(result['passed'])
        self.assertTrue(any(x['stage']=='no_ledger_extension' for x in result['closure_errors']))

    def test_actual_closer_missing_supervisor_completion_is_negative(self):
        m=self.closure_fixture()
        (self.folder/'supervisor/completion_01/completion.json').unlink()
        result=self.finish_fixture(m)
        self.assertFalse(result['passed']);self.assertFalse(result['administrative_execution_closed'])
        self.assertTrue(any(x['stage']=='sealed_supervisor' for x in result['closure_errors']))

    def test_local_comparator_uses_original_absolute_clock_and_raw_q_metric(self):
        source=ast.parse(r.SELF.read_text())
        evaluate=next(x for x in source.body if isinstance(x,ast.FunctionDef) and x.name=='evaluate_local')
        text=ast.unparse(evaluate)
        self.assertIn('shared.s.q.job.path_metrics.metrics',text)
        self.assertIn("state['t']",text)
        self.assertNotIn('START_T -',text)
        self.assertNotIn('np.linalg.norm',text)
        self.assertNotIn('compare_full_pair',text)
        self.assertIn('full_horizon_accuracy_repaired=False',text)

    def loaded_branch(self,bid,role,normal=1.,bearing=True):
        row=dict(time_s=.1536,velocity_generalized=[1.,0.,0.,0.,0.,0.],
            active_contact_ids=[15],supported_bearing_ids=[15] if bearing else [])
        return dict(branch_id=bid,role=role,error=None,rows=[row],compact_result=dict(rejected=0),
            contact_trial_trace=dict(trial_inner_counts=[2],cycle_guard_trials=[dict(trial_index=0,records=[
                dict(inner_index=0,map_output=[0.]*6,health=dict(reactions=[0.,0.,0.])),
                dict(inner_index=1,map_output=row['velocity_generalized'],health=dict(reactions=[normal,0.,0.]))])]),
            normal_gap_operand_policy=dict(prepare_calls=[dict(index=0,contacts=[[15,1e-12,[1,0,0],[0,0,0]]])]))

    def test_loading_coverage_actual_committed_last_inner_reaction_not_shadow_or_rejected(self):
        c=self.loaded_branch('C','C',10.)
        f1=self.loaded_branch('F1','F1',0.)
        f2=self.loaded_branch('F2','F2',2.)
        rejected=self.loaded_branch('discarded','F1',100.)
        packet=dict(work_branches=[c,f1,f2,rejected],carried_branches=[],
            committed_branch_ids=['F1','F2'],accepted_rows=f1['rows']+f2['rows'])
        found=self.n['loading_coverage'](packet)['first_positive_normal_reaction_grain15']
        self.assertEqual((found['branch_id'],found['normal_reaction_N'],found['last_inner_index']),('F2',2.,1))
        f2['contact_trial_trace']['cycle_guard_trials'][0]['records'][-1]['health']['reactions'][0]=0.
        self.assertIsNone(self.n['loading_coverage'](packet)['first_positive_normal_reaction_grain15'])
        f2['contact_trial_trace']['cycle_guard_trials'][0]['records'][-1]['health']['reactions'][0]=2.
        f2['rows'][0]['supported_bearing_ids']=[]
        self.assertIsNone(self.n['loading_coverage'](packet)['first_positive_normal_reaction_grain15'])
        f2['rows'][0]['supported_bearing_ids']=[15]
        f2['contact_trial_trace']['cycle_guard_trials'][0]['records'][-1]['map_output']=[99.]*6
        with self.assertRaises(RuntimeError):self.n['loading_coverage'](packet)

    def test_loading_schema_on_sealed_admitted148_wire_without_replay_or_force(self):
        """Read existing admitted wire observations only; no FULL codec replay.

        This neither invokes an auditor nor changes/adopts old admission. It
        proves that the prospective extractor fits the actual saved schema.
        """
        self.assertEqual(r.sha(r.CLOSED),r.CLOSED_SHA)
        closed=r.read(r.CLOSED)
        old=r.ROOT/'paper1_runs/full_horizon_repair_20261018_recovery04'
        admission=old/'admissions/000163/results.json'
        self.assertEqual(r.sha(admission),closed['artifacts'][str(admission)])
        receipt=self.n['sealed'](admission,positive=True)
        raw=old/'records/f0p0625_production_00148/packet.json.xz'
        self.assertEqual(r.sha(raw),receipt['artifacts'][str(raw)])
        self.assertEqual(r.sha(raw),closed['artifacts'][str(raw)])
        packet=json.loads(lzma.decompress(raw.read_bytes(),format=lzma.FORMAT_XZ))['packet']
        self.assertEqual(len(packet['committed_branch_ids']),3332)
        result=self.n['loading_coverage'](packet)
        self.assertTrue(result['association_verified'])
        self.assertIsNone(result['first_positive_normal_reaction_grain15'])

    def test_actual_initialize_AST_accepts_frozen_seed_with_new_top_level_native_design_only(self):
        """Actual initializer + pure old contract, FAKE zero-force factory.

        No compiled physical loop is called; this checks argument and complete
        FULL/frame/contract compatibility, never native mechanical adequacy.
        """
        adapter=r.STAGING/'full_state_integration_adapter_v5.py'
        self.assertEqual(r.sha(adapter),r.RUNTIME_SHA)
        tree=ast.parse(adapter.read_text())
        wanted={'plain','validate_outer_checkpoint_admission','history_node','state_token','History','HistoryStore'}
        nodes=[copy.deepcopy(node) for node in tree.body if isinstance(node,(ast.FunctionDef,ast.ClassDef)) and node.name in wanted]
        runtime=next(node for node in tree.body if isinstance(node,ast.ClassDef) and node.name=='Runtime')
        init=copy.deepcopy(next(node for node in runtime.body if isinstance(node,ast.FunctionDef) and node.name=='_initialize'))
        nodes.append(init)
        scope=dict(need=r.need,copy=copy,original_digest=r.original_digest,token=r.digest,asdict=asdict,
                   time=__import__('time'),CHECKPOINT_SCHEMA='paper1.full-state-stepdoubling.checkpoint.v1',
                   EVENT_SOURCE_SHA256='09c72c2bc79311495b0beb9ec5443d15c0575e4295a52df16624f7fd168754af',
                   EVENT_POLICY_SHA256='a456636165ccc480f7f18e2da2a5b54db0576c2876f1c0379aaea5605854d503')
        exec(compile(ast.Module(body=nodes,type_ignores=[]),str(adapter)+'::ONLY_INITIALIZER_AND_PURE_HISTORY','exec'),scope)
        old_sources=r.read(r.SOURCE2)['consumed_original_maps']
        contract_ns=dict(api=types.SimpleNamespace(digest=r.original_digest),MODE='rigid_euler_old_gyro_v1')
        for source,name in ((r.ROOT/'stage116_staging/evaluate_short_matrix_v1.py','expected_contract'),
                            (r.ROOT/'stage151_staging/rigid_rotation_v1.py','binding_for')):
            self.assertEqual(r.sha(source),old_sources[str(source)])
            fn=copy.deepcopy(next(node for node in ast.parse(source.read_text()).body if isinstance(node,ast.FunctionDef) and node.name==name))
            exec(compile(ast.Module(body=[fn],type_ignores=[]),str(source)+'::PURE_CONTRACT','exec'),contract_ns)
        preview=r.read(r.SEEDS/'physical_cases_preview.json')
        native=copy.deepcopy(preview);native['minimum_gap_semantics']=r.read(r.ORIGINAL_PHYSICAL)['minimum_gap_semantics']
        native['schema']='NEW DIAGNOSTIC CONFIG TOP LEVEL ONLY'
        calls=[]
        for level in r.LEVELS:
            data=json.loads(lzma.decompress((r.SEEDS/(level+'.json.xz')).read_bytes()))
            untouched=copy.deepcopy(data);cp=data['checkpoint'];full=cp['physical_checkpoint']
            case=next(item for item in native['cases'] if item['level_id']==level)
            self.assertEqual(case,data['case'])
            self.assertNotEqual(r.original_digest(native),data['physical_input_digest'])
            limits_type=make_dataclass('OnlyFakeLimits',[(name,object) for name in data['limits']])
            obj=types.SimpleNamespace(spec=case['spec'],binding=case['binding'],limits=limits_type(**data['limits']),
                adapter_source_sha256=r.RUNTIME_SHA,field='NO PHYSICAL FIELD',geometry='NO PHYSICAL GEOMETRY',
                time_bound=__import__('time').time()+30)
            def factory(*args,**kwargs):
                self.assertEqual(kwargs['checkpoint'],full)
                self.assertEqual(kwargs['checkpoint_binding'],case['binding'])
                expected=contract_ns['expected_contract'](case['spec'],contract_ns['binding_for'](case['binding'],True))
                self.assertEqual(expected,full['contract'])
                self.assertEqual(r.original_digest(full['state']),full['state_sha256'])
                obj.store=scope['HistoryStore'](full['state']['history'],obj.history_descriptor)
                obj.store.start(obj.input_full_sha)
                calls.append(level)
            def materialize(frame):
                state=copy.deepcopy(frame['state']);state.pop('history_node');state.pop('history_length')
                state['history']=copy.deepcopy(full['state']['history'])
                return dict(full,state=state,state_sha256=r.original_digest(state),contract=frame['contract'])
            obj.factory=factory;obj.materialize=materialize
            scope['_initialize'](obj,cp)
            self.assertEqual(obj.materialize(obj.current),full)
            self.assertEqual(data,untouched)
            bad=copy.deepcopy(cp);bad['spec_sha256']='0'*64
            before=len(calls)
            with self.assertRaises(RuntimeError):scope['_initialize'](obj,bad)
            self.assertEqual(len(calls),before)
        self.assertEqual(calls,list(r.LEVELS))

    def test_final_exit_receipt_does_not_infer_own_returncode(self):
        tree=ast.parse(r.SELF.read_text())
        closer=next(x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name=='close_execution')
        text=ast.unparse(closer)
        for key in ('actual_supervisor_exit_observed','actual_parent_terminal_exit_observed',
                    'administrative_parent','closed_log_files','expected_manifest_sha256'):
            self.assertIn(key,text)
        self.assertNotIn('Popen(',text)
        self.assertNotIn('exact_stop(',text)


if __name__=='__main__':
    unittest.main(verbosity=2)
