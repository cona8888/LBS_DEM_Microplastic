"""AST-only activation-administration fixtures. No campaign/runtime imports."""
from datetime import datetime, timezone, timedelta
from pathlib import Path
from types import FunctionType, ModuleType, SimpleNamespace
import ast
import copy
import hashlib
import json
import tempfile
import time
import traceback
import unittest

SOURCE=Path(__file__).with_name('run_first_activation_common_state_v1.py')
OLD=Path(__file__).with_name('run_support_common_state_v3.py')

def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,allow_nan=True).encode()).hexdigest()

def fixture():
    tree=ast.parse(SOURCE.read_text(encoding='utf8'));root=SOURCE.resolve().parents[1]
    ns=dict(copy=copy,ModuleType=ModuleType,FunctionType=FunctionType,Path=Path,
        datetime=datetime,timezone=timezone,timedelta=timedelta,time=time,traceback=traceback,
        ROOT=root,SELF=SOURCE.resolve())
    names=('DEADLINE','STEP_CAP','CALL_CAP','LOCAL_STEPS','LOCAL_CALLS','PRIOR_STEPS','PRIOR_CALLS',
        'CASE_STEPS','CASE_CALLS','SHARED_STEPS','SHARED_CALLS','PRIOR_SHARED_STEPS','PRIOR_SHARED_CALLS',
        'PRIOR_DIAGNOSTIC_STEPS','PRIOR_DIAGNOSTIC_CALLS','TOTAL_DIAGNOSTIC_STEPS','TOTAL_DIAGNOSTIC_CALLS',
        'PRIOR_NUMERICAL_WINDOWS','MAXIMUM_TOTAL_NUMERICAL_WINDOWS','PREPARATION_NAME','FROZEN_SHA','REUSED','ADAPTED','HELPERS')
    for node in tree.body:
        if isinstance(node,ast.Assign) and len(node.targets)==1:
            target=node.targets[0]
            if isinstance(target,ast.Name) and target.id in names: ns[target.id]=ast.literal_eval(node.value)
            elif isinstance(target,ast.Tuple) and all(isinstance(x,ast.Name) and x.id in names for x in target.elts):
                ns.update(zip((x.id for x in target.elts),ast.literal_eval(node.value)))
    d=root/'paper1_designs/first_activation_common_state_20261018'
    ns.update(DESIGNS=d,OUT=root/'paper1_runs/first_activation_common_state_20261018',
        PLAN=d/'design_01.json',AUTH=d/'authorization_01.json',PHYSICAL=d/'physical_cases_01.json',
        PROPOSAL=d/'proposal_01.json',APPROVAL=d/'human_approval_01/results.json',
        PREPARED=d/'preparation_01/results.json',PREPARATION_EXIT=d/'preparation_execution_receipt_01/results.json')
    ns['importlib']=SimpleNamespace(import_module=lambda name: (_ for _ in ()).throw(AssertionError('No lazy runtime import in fixtures')))
    nodes=[node for node in tree.body if isinstance(node,(ast.FunctionDef,ast.ClassDef))]
    exec(compile(ast.fix_missing_locations(ast.Module(body=nodes,type_ignores=[])),'<activation-administration-only>','exec'),ns)
    old=ModuleType('fixture_original_frozen_runner')
    old.__dict__.update({k:ns[k] for k in names if k in ns})
    old.__dict__.update(datetime=datetime,timezone=timezone,timedelta=timedelta,time=time,traceback=traceback,copy=copy,json=json,
        PRIOR_STEPS=10184681,PRIOR_CALLS=2125,PRIOR_SHARED_STEPS=4536769,PRIOR_SHARED_CALLS=955,
        TOTAL_DIAGNOSTIC_STEPS=70008,TOTAL_DIAGNOSTIC_CALLS=34,
        OUT=root/'fixture_old_out',SELF=OLD.resolve(),PLAN=root/'fixture_old_plan',
        CONFIG={'enabled':True,'policy':{'fixture':16}},preparation=object(),
        original=object(),timecap=object(),sha=lambda path:hashlib.sha256(Path(path).read_bytes()).hexdigest())
    old_tree=ast.parse(OLD.read_text(encoding='utf8'))
    exec(compile(ast.fix_missing_locations(ast.Module(body=[n for n in old_tree.body if isinstance(n,ast.FunctionDef)],type_ignores=[])),
        '<frozen-functions-only>','exec'),vars(old))
    old.__file__=str(OLD.resolve());ns['frozen']=old
    private=ns['build_private_namespace'](old);ns['private']=private
    private.api=SimpleNamespace(digest=digest)
    for name in (*ns['ADAPTED'],*ns['HELPERS']):
        function=ns[name];clone=FunctionType(function.__code__,vars(private),name,function.__defaults__,function.__closure__)
        clone.__kwdefaults__=copy.copy(function.__kwdefaults__);setattr(private,name,clone)
    return ns

def record(n=4,j=1,offset=0,pending=None):
    rows=[{'value':i} for i in range(offset,offset+n)]
    return dict(rows=rows,onset_timecap={'journal':[{'trigger_grain_ids':[15] if i==j else []} for i in range(n)]},
        result={'checkpoint':{'state':{'pending_trial':pending,'history':rows,'q':[1,2,3,4,5,6],'t':offset+n}},'rejected':0})

class FirstActivationAdministration(unittest.TestCase):
    def test_original_code_identity_isolation_and_exact_budget_controls(self):
        ns=fixture();self.assertTrue(ns['controls']()['passed'])
        self.assertEqual(ns['controls']()['mocked_rejections'],8)
        old,new=ns['frozen'],ns['private']
        for name in ns['REUSED']:
            self.assertIs(getattr(new,name).__code__,getattr(old,name).__code__)
            self.assertIs(getattr(new,name).__globals__,vars(new))
        new.budget_guard.__kwdefaults__['prior_case_saved']+=1
        self.assertEqual(old.budget_guard.__kwdefaults__['prior_case_saved'],10184681)
        new.CONFIG['policy']['fixture']=32
        self.assertEqual(old.CONFIG['policy']['fixture'],16)
        self.assertIs(new.run.__globals__['invoke'],new.invoke)
        self.assertIs(new.context.__globals__['SELF'],ns['SELF'])
        self.assertEqual(str(ns['OUT']).replace('\\','/').split('/')[-1],'first_activation_common_state_20261018')

    def test_new_allocation_and_unchanged_shared_case_ceilings(self):
        ns=fixture();r=ns['private']
        self.assertEqual(sum(ns['LOCAL_STEPS'])+1024+16384,30908)
        self.assertEqual(sum(ns['LOCAL_CALLS'])+6+6,17)
        self.assertEqual((ns['TOTAL_DIAGNOSTIC_STEPS'],ns['TOTAL_DIAGNOSTIC_CALLS']),(147442,68))
        for ceiling,baseline,amount in [('CASE_STEPS','PRIOR_STEPS','STEP_CAP'),('CASE_CALLS','PRIOR_CALLS','CALL_CAP'),
            ('SHARED_STEPS','PRIOR_SHARED_STEPS','STEP_CAP'),('SHARED_CALLS','PRIOR_SHARED_CALLS','CALL_CAP')]:
            original=getattr(r,ceiling);setattr(r,ceiling,ns[baseline]+ns[amount]-1)
            with self.assertRaises(RuntimeError):r.budget_guard(ns['STEP_CAP'],ns['CALL_CAP'])
            setattr(r,ceiling,original)

    def test_exact_active_original_rows_full_history_and_triggered_successor(self):
        r=fixture()['private'];original=record();serial=copy.deepcopy(original)
        left=record(1,None);right=record(3,0,1)
        right['result']['checkpoint']=copy.deepcopy(original['result']['checkpoint'])
        plan=r.verify_active(original,serial,left,right,'branch0_local_00001')
        self.assertEqual((plan['original_row_count'],plan['first_trigger_index'],plan['discarded_diagnostic_steps']),(4,1,8))
        variants=[]
        a=copy.deepcopy(serial);a['rows'][0]['value']=99;variants.append((a,left,right))
        b=copy.deepcopy(right);b['result']['checkpoint']['state']['history'][0]['value']=99;variants.append((serial,left,b))
        b=copy.deepcopy(right);b['onset_timecap']['journal'][0]['trigger_grain_ids']=[];variants.append((serial,left,b))
        b=copy.deepcopy(right);b['rows']=b['rows'][:-1];variants.append((serial,left,b))
        for args in variants:
            with self.assertRaises(RuntimeError):r.verify_active(original,*args,'branch0_local_00001')

    def test_first_active_record_rejects_zero_split_pending_missing_and_oversize(self):
        r=fixture()['private']
        for value in (record(j=0),record(j=None),record(pending={'attempt':0}),record(4097,1)):
            with self.assertRaises(RuntimeError):r.active_plan(value,'branch0_local_00001')
        pending=record(j=None);pending['onset_timecap']['journal'].append({'trigger_grain_ids':[182]})
        with self.assertRaises(RuntimeError):r.active_plan(pending,'branch0_local_00001')

    def test_active_ancestry_reset_and_split_successor_use_original_record_input(self):
        r=fixture()['private'];active={'original_production_label':'branch1_local_00002'}
        self.assertEqual(r.evidence_parent(1,'branch1_active_serial',active),'branch1_local_00001')
        self.assertEqual(r.evidence_parent(1,'branch1_active_split_a',active),'branch1_local_00001')
        self.assertEqual(r.evidence_parent(1,'branch1_active_split_b',active),'branch1_active_split_a')
        self.assertEqual(r.evidence_parent(1,'branch1_local_00003',active),'branch1_local_00002')
        self.assertIsNone(r.evidence_parent(1,'branch1_active_serial',{'original_production_label':'branch1_local_00001'}))
        with self.assertRaises(RuntimeError):r.evidence_parent(1,'unknown',active)

    def test_new_explicit_human_reply_is_required_and_old_direct_instruction_cannot_authorize(self):
        ns=fixture();good=dict(passed=True,proposal_sha256='a'*64,human_reply='Synthetic approval',question_reference='Fixture',
            human_reviewed_exact_proposal=True,preparation_execution_receipt_sha256='b'*64,scope=ns['approval_scope']())
        self.assertTrue(ns['validate_approval'](good,'a'*64))
        for key,value in [('human_reviewed_exact_proposal',False),('question_reference',''),('proposal_sha256','c'*64),
            ('preparation_execution_receipt_sha256',None)]:
            bad=copy.deepcopy(good);bad[key]=value
            with self.assertRaises(RuntimeError):ns['validate_approval'](bad,'a'*64)
        bad=copy.deepcopy(good);bad['scope']['maximum_total_numerical_windows']=4
        with self.assertRaises(RuntimeError):ns['validate_approval'](bad,'a'*64)
        with tempfile.TemporaryDirectory(prefix='activation-authority-') as temp:
            d=Path(temp);writes=[];approval=d/'approval.json';approval.write_text('{"passed":false}')
            (d/'proposal.json').write_text('{}')
            ns.update(PLAN=d/'design.json',AUTH=d/'authorization.json',OUT=d/'run',APPROVAL=approval,PROPOSAL=d/'proposal.json')
            r=ns['private'];r.s=SimpleNamespace(environment=lambda:None,fields=SimpleNamespace(sealed=lambda p:json.loads(Path(p).read_text())))
            r.commit=lambda *args:writes.append(args)
            for pin in (None,'0'*64,hashlib.sha256(approval.read_bytes()).hexdigest()):
                with self.assertRaises(RuntimeError):ns['authorize'](pin)
            self.assertEqual(writes,[])

    def test_original_clock_final_reserve_and_no_default_dispatch(self):
        ns=fixture();end=datetime.fromisoformat(ns['DEADLINE'])
        self.assertEqual(ns['private'].bounds(end-timedelta(minutes=45)),(end-timedelta(minutes=30),end))
        for bad in (end,end-timedelta(minutes=30),end+timedelta(seconds=1)):
            with self.assertRaises(RuntimeError):ns['private'].bounds(bad)
        tree=ast.parse(SOURCE.read_text());main=next(n for n in tree.body if isinstance(n,ast.If) and '__name__' in ast.unparse(n.test))
        self.assertIn('raise SystemExit',ast.unparse(main));self.assertNotIn('warm(',ast.unparse(main))

    def test_actual_invoke_physical_prefix_and_original_metric_tail_unchanged(self):
        def functions(path):return {n.name:n for n in ast.parse(path.read_text()).body if isinstance(n,ast.FunctionDef)}
        old,new=functions(OLD),functions(SOURCE)
        def prefix(node,marker):
            index=next(i for i,n in enumerate(node.body) if marker in ast.unparse(n))
            return ast.dump(ast.Module(body=node.body[:index],type_ignores=[]),include_attributes=False)
        self.assertEqual(prefix(old['invoke'],'triggered = activation_index'),prefix(new['invoke'],"journal = record['onset_timecap']['journal']"))
        def tail(node):
            i=next(i for i,n in enumerate(node.body) if ast.unparse(n).startswith('seeds ='))
            return ast.dump(ast.Module(body=node.body[i:],type_ignores=[]),include_attributes=False)
        self.assertEqual(tail(old['evaluate']),tail(new['evaluate']))

    def test_actual_invoke_preserves_and_charges_before_initial_or_pending_stop(self):
        for label,pending,expected_stop in [('branch0_serial',False,True),
            ('branch0_local_00001',False,False),('branch0_active_serial',False,False),
            ('branch0_local_00001',True,True)]:
            with self.subTest(label=label,pending=pending),tempfile.TemporaryDirectory(prefix='active-invoke-') as temp:
                r=fixture()['private'];r.OUT=Path(temp);events=[];raw=record()
                if pending:raw['onset_timecap']['journal'].append({'trigger_grain_ids':[182]})
                prefix=SimpleNamespace(reference=lambda:{'fixture':'prefix'})
                r.authority=lambda *args:{};r.sha=lambda *args:'h'
                r.ledger=lambda:dict(labels=[],conservative_call_charges=0,admission_failures=[],accepted_diagnostic_steps=0)
                gate={'passed':True,'artifacts':{},'full_checkpoint_sha256':digest(raw['result']['checkpoint'])}
                policy={'passed':True,'raw_sha256':'h','original_physical_guard_sha256':'h'}
                r.s=SimpleNamespace(utc=lambda:'fixture',fields=SimpleNamespace(sealed=lambda path:gate if 'guard_completion' in str(path) else policy))
                r.api=SimpleNamespace(digest=digest,verify_mapping=lambda files:None)
                r.commit=lambda path,value:events.append(('commit',str(path),copy.deepcopy(value)))
                r.seal=lambda path,value:events.append(('seal',str(path),copy.deepcopy(value)))
                r.store_checkpoint=lambda *args:events.append(('checkpoint',str(args[0])))
                ctx=SimpleNamespace(job=SimpleNamespace(codec=SimpleNamespace(read_record=lambda *args:(copy.deepcopy(raw),prefix))))
                transaction=lambda *args:(copy.deepcopy(raw),prefix,{})
                p={'simulation_cutoff_utc':r.DEADLINE}
                call=lambda:r.invoke(ctx,transaction,p,{},None,0,label,4,{'seed':True},None,None)
                if expected_stop:
                    with self.assertRaises(RuntimeError):call()
                    admission=next(i for i,x in enumerate(events) if x[0]=='seal' and 'admissions' in x[1])
                    stopped=next(i for i,x in enumerate(events) if x[0]=='seal' and 'activation_stop' in x[1])
                    self.assertLess(admission,stopped)
                    self.assertEqual(events[stopped][2]['completed_saved_steps_charged'],4)
                else:
                    self.assertEqual(len(call()[0]['rows']),4)
                    self.assertFalse(any('activation_stop' in x[1] for x in events))

    def test_actual_run_qualifies_first_record_before_successor_and_restores_original(self):
        for damage in (False,'probe','coverage'):
            with self.subTest(damage=damage),tempfile.TemporaryDirectory(prefix='active-run-') as temp:
                r=fixture()['private'];r.OUT=Path(temp);calls=[];seals={};saved=[]
                (r.OUT/'controller_01').mkdir();(r.OUT/'controller_01/worker_launch.json').write_text('{}')
                p={'simulation_cutoff_utc':r.DEADLINE,'end_utc':r.DEADLINE,'physical_design_sha256':'physical','source_files':{}}
                launch={'pid':42,'created':1.,'command':['fixture']}
                r.authority=lambda *args:p;r.sha=lambda path:'h';r.context=lambda:(object(),object())
                r.read=lambda path:{'cases':[{},{}]} if path==r.PHYSICAL else launch
                r.psutil=SimpleNamespace(Process=lambda:SimpleNamespace(pid=42,create_time=lambda:1.,cmdline=lambda:['fixture'],cpu_affinity=lambda value:None))
                r.commit=lambda *args:None;r.seal=lambda path,value:seals.__setitem__(str(path),copy.deepcopy(value))
                r.store_checkpoint=lambda path,cp,*args:saved.append((str(path),copy.deepcopy(cp)))
                r.control_hash_snapshot=lambda:{}
                r.ledger=lambda:dict(ledger_authenticated=True,admission_failures=[],known_unaccepted_saved_steps=0,unknown_reserved_steps_upper_bound=0)
                kernel=SimpleNamespace(warm=lambda:None,reset=lambda:None)
                r.s=SimpleNamespace(utc=lambda:'fixture',q=SimpleNamespace(kernel=kernel,
                    reference=SimpleNamespace(JOB=SimpleNamespace(parent=SimpleNamespace(b=SimpleNamespace(old=SimpleNamespace(parent=SimpleNamespace(configure=lambda:None))))))))
                initial={'state':{'k':0,'t':0,'history':[],'pending_trial':None}}
                r.preparation=SimpleNamespace(seed_for=lambda index:(copy.deepcopy(initial),None))
                r.coverage_from_record=lambda record:dict(association_verified=True,
                    first_selector={'accepted_row_index':1},
                    first_positive_normal_reaction_grain15=None if damage=='coverage' else {'grain_id':15,'normal_reaction_N':1.})
                def fake_invoke(ctx,transaction,p,physical,case,index,label,cap,before,prefix,previous):
                    k=before['state']['k'];calls.append((label,cap,k,prefix.reference() if prefix else None))
                    local='_local_' in label;active='_active_' in label
                    n=(4 if label.endswith('00001') else 2) if local else cap
                    rows=[{'step':i} for i in range(k,k+n)]
                    history=before['state']['history']+rows
                    cp={'state':{'k':k+n,'t':k+n,'history':history,'pending_trial':None}}
                    j=1-k if (local or active) and k<=1<k+n else None
                    journal=[{'trigger_grain_ids':[15] if i==j else []} for i in range(n)]
                    if damage=='probe' and label=='branch0_active_serial':cp['state']['history'][0]['step']=999
                    rec={'rows':rows,'onset_timecap':{'journal':journal},'result':{'checkpoint':cp,
                        'status':'present_at_horizon' if local and label.endswith('00002') else 'incomplete_budget','rejected':0}}
                    outprefix=SimpleNamespace(reference=lambda label=label:{'label':label})
                    return rec,outprefix,{}
                r.invoke=fake_invoke
                if damage:
                    with self.assertRaises(SystemExit):r.run()
                    if damage=='probe':self.assertFalse(any('_local_00002' in c[0] for c in calls))
                    self.assertFalse(any(c[0].startswith('branch1_') for c in calls))
                    self.assertTrue(any(cp['state']['k']>=4 for path,cp in saved))
                else:
                    r.run()
                    for branch in (0,1):
                        labels=[c[0] for c in calls if c[0].startswith(f'branch{branch}_')]
                        self.assertLess(labels.index(f'branch{branch}_active_split_b'),labels.index(f'branch{branch}_local_00002'))
                        successor=next(c for c in calls if c[0]==f'branch{branch}_local_00002')
                        self.assertEqual(successor[2:],(4,{'label':f'branch{branch}_local_00001'}))
                    final=seals[str(r.OUT/'worker_disposition_01')]
                    self.assertTrue(final['passed']);self.assertFalse(final['core_result_admitted'])

    def test_saved_loading_association_uses_final_of_multiple_inner_maps_and_native_positive_sign(self):
        r=fixture()['private'];value=record(3,1)
        value['spec']={'config':{'prolate_semiaxes_m':[.002,.0005,.0005]}}
        value['normal_gap_operand_policy']={'prepare_calls':[]}
        value['contact_trial_trace']={'trial_inner_counts':[],'cycle_guard_trials':[]}
        for i,row in enumerate(value['rows']):
            row.update(time_s=.15+(i+1)*1e-6,velocity_generalized=[i,0,0,0,0,0],active_contact_ids=[15,182])
            value['onset_timecap']['journal'][i].update(time_s=.15+i*1e-6,velocity_generalized=[-1.,0,0,0,0,0],
                near=[[15,1e-10,[1.,0,0],[0,0,0]],[182,.001,[1.,0,0],[0,0,0]]])
            reactions=[0.,0,0,0,0,0]
            if i==2:reactions[0]=1e-300
            maps=[{'inner_index':j,'map_output':copy.deepcopy(row['velocity_generalized']) if j==2 else [999]*6,
                   'health':{'reactions':reactions if j==2 else [1.,0,0,0,0,0]}} for j in range(3)]
            value['contact_trial_trace']['cycle_guard_trials'].append({'trial_index':i,'records':maps})
            value['contact_trial_trace']['trial_inner_counts'].append(3)
            value['normal_gap_operand_policy']['prepare_calls'].append({'index':i,'contacts':[[15,1e-10,[],[]],[182,.001,[],[]]]})
        got=r.coverage_from_record(value)
        self.assertEqual(got['first_selector']['accepted_row_index'],1)
        self.assertEqual(got['first_positive_normal_reaction_grain15']['accepted_row_index'],2)
        self.assertEqual(got['first_positive_normal_reaction_grain15']['normal_reaction_N'],1e-300)
        variants=[]
        bad=copy.deepcopy(value);bad['contact_trial_trace']['cycle_guard_trials'][0]['records'].pop();variants.append(bad)
        bad=copy.deepcopy(value);bad['contact_trial_trace']['cycle_guard_trials'][0]['records'][-1]['map_output'][0]=9;variants.append(bad)
        bad=copy.deepcopy(value);bad['normal_gap_operand_policy']['prepare_calls'][0]['index']=1;variants.append(bad)
        bad=copy.deepcopy(value);bad['rows'][0]['active_contact_ids'].reverse();variants.append(bad)
        bad=copy.deepcopy(value);bad['result']['checkpoint']['state']['pending_trial']={'attempt':0};variants.append(bad)
        for bad in variants:
            with self.assertRaises(RuntimeError):r.coverage_from_record(bad)
        value['contact_trial_trace']['cycle_guard_trials'][2]['records'][-1]['health']['reactions'][0]=0
        self.assertIsNone(r.coverage_from_record(value)['first_positive_normal_reaction_grain15'])

if __name__=='__main__':unittest.main(verbosity=2)
