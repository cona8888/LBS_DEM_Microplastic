"""Unchanged split/pending restart gate for the newly qualified composition."""
from pathlib import Path
from types import FunctionType,SimpleNamespace
import ast,copy,inspect,sys
import measure_combined_native_prefix_v1 as current
sys.path.insert(0,str(current.ROOT/'stage198_staging'))
import qualify_fine_boundary_v1 as tests
api,q,job,WORK=current.api,current.q,current.job,current.WORK
DESIGN=WORK.with_name('composed_boundary_01.json');RUN=current.RUN.with_name('composed_boundary_01');OUT=current.OUT.with_name('composed_boundary_01')
p=SimpleNamespace(**vars(current.template.old))
p.candidate=current.candidate;p.storage=current.storage;p.DESIGN=current.DESIGN;p.RUN=current.RUN;p.OUT=current.OUT;p.execute=current.execute;p.verify=current.verify
execute=FunctionType(current.execute.__code__,{**current.execute.__globals__,'DESIGN':DESIGN},current.execute.__name__,current.execute.__defaults__,current.execute.__closure__)
tree=ast.parse(inspect.getsource(tests.run));ledger_changes=0;clock_changes=0
class Binding(ast.NodeTransformer):
    def visit_Constant(self,node):
        global ledger_changes
        if type(node.value) is int and node.value==49410:node.value=74812;ledger_changes+=1
        return node
    def visit_Assign(self,node):
        global clock_changes
        if any(isinstance(t,ast.Name) and t.id=='stop' for t in node.targets):
            if ast.unparse(node.value)!='job.utc() + timedelta(minutes=20)':raise RuntimeError('original stop expression')
            node.value=ast.parse("min(job.utc()+timedelta(minutes=20),job.policy.utc(api.read(WORK)['work_end_utc']))",mode='eval').body;clock_changes+=1
        return self.generic_visit(node)
Binding().visit(tree)
if (ledger_changes,clock_changes)!=(2,1):raise RuntimeError('two prior-ledger and one bounded-clock substitutions')
ast.fix_missing_locations(tree)
ns={**tests.__dict__,'p':p,'WORK':WORK,'DESIGN':DESIGN,'RUN':RUN,'OUT':OUT,'execute':execute,'__file__':__file__}
exec(compile(tree,__file__+'::same_restart_contract','exec'),ns)

def ledger():
    names={'combined_fine_01':3580,'long_fine_01':7406,'current_prefix_01':3580,'native_prefix_01':3580,'combined_native_prefix_01':3580}
    accounts=list(RUN.parent.glob('*/*.accounting.json'))
    api.require(len(accounts)==5,'exact five resolved predecessor calls')
    for name,n in names.items():
        raw=RUN.parent/name/'serial.json.xz';a=api.read(raw.with_suffix('.accounting.json'))
        api.require(a['accepted_steps']==n and a['raw_sha256']==api.sha(raw),'prior original raw accounting')
    api.require(53086+sum(names.values())==74812,'failure-inclusive current recovery total')

def verify(d):
    current.verify(api.read(current.DESIGN));api.require(d['binding']==api.digest({k:v for k,v in d.items() if k!='binding'}),'boundary protocol binding')
    api.verify_mapping(d['sources']);api.verify_mapping(d['inputs'])
    old=api.read(current.DESIGN);api.require(all(d[k]==old[k] for k in ('cases','budget','numerical_gates','minimum_gap_semantics')),'original scientific and budget contract')
    api.require(d['diagnostic_prior_recovery_steps']==74812 and d['diagnostic_maximum_new_steps']==3676 and 74812+3676+17000<=100000,'inclusive exact accounting and full preflight reserve')
    api.require(execute.__code__ is current.execute.__code__ and execute.__globals__['codec'] is current.storage.codec and execute.__globals__['DESIGN']==DESIGN,'unchanged integration and owned storage binding')
    current.storage.verify_bindings()
ns['verify']=verify

def prepare():
    api.require(job.utc()<job.policy.utc(api.read(WORK)['last_diagnostic_launch_utc']),'launch cutoff');ledger()
    d=copy.deepcopy(api.read(current.DESIGN));current.verify(d);d.pop('binding');w=api.read(WORK)
    r=api.read(current.OUT/'results.json');api.require(r['passed'] and r['cumulative_recovery_steps']==74812 and api.read(current.OUT/'completion.json')['results_sha256']==api.sha(current.OUT/'results.json'),'sealed exact prefix result')
    available=(job.policy.utc(w['simulation_cutoff_utc'])-job.utc()).total_seconds()/3600
    api.require(r['fine_transaction_hours_with_margin']<=available,'original hard-prefix runtime gate with current remaining time')
    serial=q.independent_file(current.RUN/'serial.json.xz',api.sha(current.DESIGN));old=q.independent_file(p.held.FINE,api.sha(p.pre.job.DESIGN));pending=tests.boundary(serial,old)
    files=[Path(__file__),Path(tests.__file__),Path(current.__file__)]
    inputs=[current.DESIGN,current.OUT/'results.json',current.OUT/'completion.json',*[x for x in current.RUN.iterdir() if x.is_file()],p.held.FINE,p.held.FINE.with_suffix('.seal.json')]
    d.update(stage='Stage199 exact composed solver split and pending-boundary qualification',sources={**d['sources'],**{str(x):api.sha(x) for x in files}},inputs={**d['inputs'],**{str(x):api.sha(x) for x in inputs}},
        calls={'split_a':1790,'split_b':1790,'old_pending_baseline':32,'old_pending_candidate':32,'paused_candidate':32},diagnostic_prior_recovery_steps=74812,diagnostic_maximum_new_steps=3676,
        observed_pending_trial=pending,old_fixed_cap_test_remains_failed=True,production_authorized=False,
        criterion='Original1790+1790 split and three32-step pending/paused continuations unchanged. Exact all rows, full state and first timestep; independent original audits, complete lossless seals, no erased pending trial.')
    d['binding']=api.digest(d);job.commit(DESIGN,d);verify(d);print('COMPOSED_BOUNDARY_PROTOCOL',api.sha(DESIGN),flush=True)

if __name__=='__main__':
    if sys.argv[1:]==['prepare']:prepare()
    elif sys.argv[1:]==['run']:
        api.require(job.utc()<job.policy.utc(api.read(WORK)['last_diagnostic_launch_utc']),'launch cutoff');ledger();current.candidate.warm();ns['run']()
    else:raise ValueError('prepare | run')
