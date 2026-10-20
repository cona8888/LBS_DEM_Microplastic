"""AST-only fresh timing administration tests; no runtime/solver imports."""
from datetime import datetime,timezone,timedelta
from pathlib import Path
from types import FunctionType,ModuleType,SimpleNamespace
import ast,copy,hashlib,json,unittest
SOURCE=Path(__file__).with_name('run_first_activation_fresh_v1.py')
OLDTEST=Path(__file__).with_name('test_first_activation_runtime_v1.py')
OLD=Path(__file__).with_name('run_first_activation_common_state_v1.py')

def fixture():
    oldtree=ast.parse(OLDTEST.read_text());oldns={'__file__':str(OLDTEST.resolve()),'__name__':'pure_old_fixture'}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[n for n in oldtree.body if not isinstance(n,ast.If)],type_ignores=[])),
        '<prior-AST-only-fixture>','exec'),oldns)
    base=oldns['fixture']();frozen=ModuleType('fixture_frozen_activation_adapter')
    frozen.__dict__.update(base);frozen.__file__=str(OLD.resolve())
    tree=ast.parse(SOURCE.read_text());root=SOURCE.resolve().parents[1]
    ns=dict(datetime=datetime,timezone=timezone,timedelta=timedelta,Path=Path,FunctionType=FunctionType,ModuleType=ModuleType,
        copy=copy,json=json,ROOT=root,SELF=SOURCE.resolve(),frozen=frozen)
    names=('FROZEN_SHA','START','CUTOFF','DEADLINE','OLD_DEADLINE','GRANT_SHA','BASE_SHA','AMEND_SHA','PREP_EXIT_SHA','PHYSICAL_SHA')
    for n in tree.body:
        if isinstance(n,ast.Assign) and len(n.targets)==1 and isinstance(n.targets[0],ast.Name) and n.targets[0].id in names:
            ns[n.targets[0].id]=ast.literal_eval(n.value)
    d=root/'paper1_designs/first_activation_common_state_20261018_fresh'
    ns.update(DESIGNS=d,OUT=root/'paper1_runs/first_activation_common_state_20261018_fresh',PLAN=d/'design_01.json',AUTH=d/'authorization_01.json',
        APPROVAL=d/'human_time_approval_01/results.json',FRESH_PREPARED=d/'preparation_01/results.json',
        PHYSICAL=base['PHYSICAL'],BASE_PROPOSAL=base['PROPOSAL'],PROPOSAL=base['PROPOSAL'],
        TIME_PROPOSAL=base['DESIGNS']/'fresh_time_proposal_01.json',PREPARED=base['PREPARED'],PREPARATION_EXIT=base['PREPARATION_EXIT'])
    nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef)]
    exec(compile(ast.fix_missing_locations(ast.Module(body=nodes,type_ignores=[])),'<fresh-timing-only>','exec'),ns)
    ns['private']=ns['build_private_namespace'](frozen.private)
    ns['private'].authority=ns['authority']
    ns['REUSED']=tuple(dict.fromkeys((*frozen.REUSED,*frozen.ADAPTED,*frozen.HELPERS)))
    return ns

def grant(ns):
    return dict(passed=True,proposal_sha256=ns['BASE_SHA'],fresh_time_proposal_sha256=ns['AMEND_SHA'],
        human_reply='Synthetic fresh timing approval',question_reference='Fixture',human_reviewed_exact_proposal=True,
        start_utc=ns['START'],simulation_cutoff_utc=ns['CUTOFF'],end_utc=ns['DEADLINE'],observed_clock_first_utc=ns['START'],
        new_independent_authority=True,old_authority_closed_unchanged=True,only_time_authority_changes=True,
        all_preparation_inside_this_fixed_window=True,old_absolute_end_utc=ns['OLD_DEADLINE'],
        preparation_execution_receipt_sha256=ns['PREP_EXIT_SHA'],scope_original_shared_end_is_preserved_historical=True,
        scope=ns['approval_scope'](),physics_changes=[],accuracy_gate_changes=[],route_changes=[],selector_changes=[],case_shared_storage_budget_changes=[])

class FreshTimingAdministration(unittest.TestCase):
    def test_complete_private_numerical_graph_unchanged_and_old_globals_untouched(self):
        ns=fixture();result=ns['controls']();self.assertTrue(result['passed']);self.assertEqual(result['fixed_clock_rejections'],3)
        old,new=ns['frozen'].private,ns['private']
        for name in ns['REUSED']:
            if name in ('authority','bounds'):continue
            self.assertIs(getattr(old,name).__code__,getattr(new,name).__code__)
            self.assertIs(getattr(new,name).__globals__,vars(new))
        self.assertIs(new.run.__globals__['invoke'],new.invoke)
        self.assertIs(new.invoke.__globals__['context'],new.context)
        self.assertEqual(new.child.__globals__['SELF'],ns['SELF'])
        self.assertIs(new.context.__globals__['authority'],ns['authority'])
        new.CONFIG['policy']['fixture']=32
        self.assertEqual(old.CONFIG['policy']['fixture'],16)
        self.assertEqual(old.DEADLINE,ns['OLD_DEADLINE']);self.assertEqual(new.DEADLINE,ns['DEADLINE'])

    def test_eval_and_numeric_proposal_stay_original_and_time_proposal_separate(self):
        ns=fixture();r=ns['private']
        self.assertEqual(r.PROPOSAL,ns['BASE_PROPOSAL']);self.assertNotEqual(r.PROPOSAL,ns['TIME_PROPOSAL'])
        self.assertIs(r.evaluate.__code__,ns['frozen'].private.evaluate.__code__)
        self.assertEqual(r.PHYSICAL,ns['frozen'].PHYSICAL)
        self.assertIs(r.preparation,ns['frozen'].private.preparation)
        self.assertEqual(r.budget_guard.__kwdefaults__,ns['frozen'].private.budget_guard.__kwdefaults__)
        r.budget_guard(30908,17)
        for args in ((30909,17),(30908,18)):
            with self.assertRaises(RuntimeError):r.budget_guard(*args)

    def test_exact_new_grant_clock_and_old_historical_scope(self):
        ns=fixture();good=grant(ns)
        self.assertTrue(ns['validate_approval'](good,ns['BASE_SHA']))
        for key,value in [('start_utc','2026-10-18T06:50:00+00:00'),('simulation_cutoff_utc','2026-10-18T07:20:00+00:00'),
            ('end_utc','2026-10-18T07:50:00+00:00'),('new_independent_authority',False),('old_authority_closed_unchanged',False),
            ('old_absolute_end_utc',ns['DEADLINE']),('human_reply',''),('fresh_time_proposal_sha256','0'*64)]:
            bad=copy.deepcopy(good);bad[key]=value
            with self.assertRaises(RuntimeError):ns['validate_approval'](bad,ns['BASE_SHA'])
        bad=copy.deepcopy(good);bad['scope']['original_shared_end_utc']=ns['DEADLINE']
        with self.assertRaises(RuntimeError):ns['validate_approval'](bad,ns['BASE_SHA'])
        self.assertEqual(ns['bounds'](),(datetime.fromisoformat(ns['CUTOFF']),datetime.fromisoformat(ns['DEADLINE'])))
        with self.assertRaises(RuntimeError):ns['bounds'](datetime.fromisoformat(ns['START'])+timedelta(seconds=1))

    def test_actual_authority_wrapper_rejects_reset_dates_or_unpinned_preparation(self):
        ns=fixture();p=dict(start_utc=ns['START'],simulation_cutoff_utc=ns['CUTOFF'],worker_cutoff_utc=ns['CUTOFF'],
            end_utc=ns['DEADLINE'],fresh_time_authority=True,fresh_time_proposal_sha256=ns['AMEND_SHA'],
            old_absolute_end_utc=ns['OLD_DEADLINE'],old_authority_closed_unchanged=True,fresh_preparation_sha256='p')
        r=ns['private'];r.sha=lambda path:'p';r._original_authority=lambda numerical=False:copy.deepcopy(p)
        self.assertEqual(ns['authority'](True),p)
        for key,value in [('start_utc','later'),('simulation_cutoff_utc',ns['DEADLINE']),('end_utc','later'),
            ('fresh_preparation_sha256','changed'),('fresh_time_proposal_sha256','changed')]:
            old=p[key];p[key]=value
            with self.assertRaises(RuntimeError):ns['authority']()
            p[key]=old

    def test_no_default_dispatch_or_old_authorize_reuse(self):
        tree=ast.parse(SOURCE.read_text());authorize=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='authorize')
        text=ast.unparse(authorize)
        self.assertNotIn('frozen.authorize',text);self.assertNotIn('bounds(datetime.now',text)
        self.assertIn('start_utc=START',text);self.assertIn('end_utc=DEADLINE',text)
        main=next(n for n in tree.body if isinstance(n,ast.If) and '__name__' in ast.unparse(n.test))
        self.assertIn('len(sys.argv) == 4',ast.unparse(main));self.assertIn('raise SystemExit',ast.unparse(main))

if __name__=='__main__':unittest.main(verbosity=2)
