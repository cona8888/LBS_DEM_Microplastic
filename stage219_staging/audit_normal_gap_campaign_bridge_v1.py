"""Independent zero-step full-science, actual callback and fresh campaign bridge."""
from pathlib import Path
from types import FunctionType,SimpleNamespace
import copy,itertools
import normal_gap_campaign_v1 as s
api,job=s.api,s.job
FIXTURES=s.ROOT/'stage204_evaluations/receipt_race_20260930/qualification_01'

class Boundary:
    def __init__(self,path,events):self.path,self.events,self.calls=path,iter(events),0
    def __str__(self):return str(self.path)
    def __fspath__(self):return str(self.path)
    def exists(self):self.calls+=1;return next(self.events)

def entry(folder,first=False):
    return dict(case='fixture',index=1 if first else 2,before_sha='b'*64,previous_receipt_sha=None,previous_receipt_path=None if first else folder/'parent.audit.json',paths=dict(raw=folder/'segment.json.xz',ready=folder/'segment.ready.json',receipt=folder/'segment.audit.json',trace=folder/'segment.npy'))

def run():
    d=api.read(job.DESIGN);job.verify(d);inherit=s.inherited();qual=api.read(s.QUAL_DESIGN)
    for key in ('cases','numerical_gates','budget','preflight','minimum_gap_semantics','worker_logical_cpus','auditor_logical_cpu','maximum_unverified_segments_total','maximum_unverified_segments_per_case'):
        api.require(d[key]==qual[key],'independent original science/resource equality '+key)
    api.require(inherit['explicitly_reused_stage216_independently_passing_steps']==17000 and inherit['original_stage216_preflight_remains_failed'],'no fabricated qualification pass')
    actual=job.worker.__globals__['acknowledged']
    api.require(actual is s.acknowledged and actual.__globals__['job'] is job
        and actual.__code__ is s.stack.acknowledged.__code__,'actual isolated qualified single-pass callback')
    events=corrupt=0
    for first in (False,True):
        folder=FIXTURES/('first' if first else 'successor');proxy=SimpleNamespace(policy=job.policy,DESIGN=folder/'design.json')
        adapter=FunctionType(actual.__code__,dict(actual.__globals__,job=proxy),actual.__name__,actual.__defaults__,actual.__closure__)
        api.require(s.q.campaign.code_sha(adapter)==s.q.campaign.code_sha(actual),'same real/fixture callback bytecode')
        for observations in ((False,False),(False,True),(True,True)):
            item=entry(folder,first);boundary=Boundary(item['paths']['receipt'],observations);item['paths']['receipt']=boundary
            pending=adapter(dict(audit_source_sha256='c'*64),[item]);api.require(boundary.calls==1 and pending==([] if observations[0] else [item]),'one immutable receipt availability decision')
            if observations==(False,True):api.require(adapter(dict(audit_source_sha256='c'*64),pending)==[] and boundary.calls==2,'published successor verified next time')
            events+=1
    for folder in sorted(FIXTURES.glob('mutation_*')):
        proxy=SimpleNamespace(policy=job.policy,DESIGN=folder/'design.json');adapter=FunctionType(actual.__code__,dict(actual.__globals__,job=proxy),actual.__name__,actual.__defaults__,actual.__closure__)
        try:adapter(dict(audit_source_sha256='c'*64),[entry(folder)])
        except (ValueError,RuntimeError):corrupt+=1
        else:raise AssertionError('corrupt callback fixture accepted')
    api.require(events==6 and corrupt==17,'all original real callback controls')
    mutations=[('case',lambda b:b['cases'].pop()),('timestep',lambda b:b['cases'][0].update(factor=1)),('horizon',lambda b:b['cases'][0]['spec'].update(horizon_s=1.)),
        ('physics',lambda b:b['cases'][0]['spec']['config'].update(friction_coefficient=.31)),('gate',lambda b:b['numerical_gates'].update(whole_position_over_b_max=.1)),
        ('concurrency',lambda b:b['budget'].update(workers=6)),('cap',lambda b:b['budget'].update(step_cap_per_call=20000)),('old_source',lambda b:b['sources'].pop(next(iter(qual['sources'])))),
        ('audit',lambda b:b.update(audit_source_sha256='0'*64)),('old_checkpoint',lambda b:b.update(fresh_start_required=False)),
        ('operand_policy',lambda b:b['qualified_normal_gap_bindings'].update(numerical_policy_source_sha256='0'*64)),('policy_contract',lambda b:b.update(numerical_policy_contract_sha256='0'*64)),
        ('deadline',lambda b:b.update(simulation_cutoff_utc='2030-01-01T00:00:00+00:00'))]
    rejected=[]
    for label,change in mutations:
        bad=copy.deepcopy(d);change(bad);bad.pop('binding');bad['binding']=api.digest(bad)
        try:job.verify(bad)
        except (RuntimeError,ValueError,AssertionError):rejected.append(label)
        else:raise AssertionError('accepted corrupt campaign '+label)
    actual_controls=[]
    saved=job.kernel
    try:
        job.kernel=SimpleNamespace(evaluate=lambda *args:None)
        try:s.bindings()
        except RuntimeError:actual_controls.append('wrong_actual_auditor_rejected')
        else:raise AssertionError('wrong actual auditor accepted')
    finally:job.kernel=saved
    saved=job.acknowledged
    try:
        job.acknowledged=lambda *args:[]
        try:s.bindings()
        except RuntimeError:actual_controls.append('wrong_actual_receipt_callback_rejected')
        else:raise AssertionError('wrong actual callback accepted')
    finally:job.acknowledged=saved
    count=0;order=[c['id'] for c in d['cases']]
    for permutation in itertools.permutations(order):
        life=job.policy.initial(order);remaining=list(permutation)
        while life.queued or life.active:
            while True:
                life,name=job.policy.dispatch(life,3,True)
                if name is None:break
                api.require(len(life.active)*2<=6,'three producers/global-six bound')
            name=next(n for n in remaining if n in life.active);remaining.remove(name);life=job.policy.retire(life,name,0,True)
        api.require(len(life.retired)==6 and not life.stop_reasons,'all six complete retirement orderings');count+=1
    api.require(count==720 and len(rejected)==13 and len(actual_controls)==2,'all dispatch/design/actual-association controls')
    old=s.require_old_terminal_closure();fit=s.resource_gate(d)
    api.require(not job.RUN.exists() and not s.active_owned(),'no competing process or old restart')
    bindings=s.bindings();files=[Path(__file__),job.DESIGN,job.WORK,s.QUAL_DESIGN,s.QUAL_NUM,s.QUAL_FIX,s.RESOURCE,s.RESOURCE_AUDIT,s.OLD205,s.OLD205_AUDIT,s.OLD209]
    r=dict(passed=True,new_trajectory_steps=0,design_sha256=api.sha(job.DESIGN),qualified_bindings=bindings,actual_callback_controls=events,
        corrupt_receipt_fixtures_rejected=corrupt,corrupt_designs_rejected=rejected,actual_association_corruptions_rejected=actual_controls,dispatch_permutations=count,
        old_failed_accounting=old,old_runs_remain_failed=True,resource_fit=fit,qualification_inheritance=inherit,inputs={str(p):api.sha(p) for p in files},
        claim='Fresh campaign launch bridge only; explicit failed-inclusive numerical evidence plus separate administrative fixture complement. Original six cases/physics/timesteps/horizons/gates unchanged; no production trajectory yet.')
    out=job.OUT/'independent_bridge_01';job.commit(out/'results.json',r);job.commit(out/'completion.json',dict(passed=True,results_sha256=api.sha(out/'results.json')))
    print('NORMAL_GAP_CAMPAIGN_BRIDGE',api.sha(out/'results.json'),fit,flush=True)
if __name__=='__main__':run()
