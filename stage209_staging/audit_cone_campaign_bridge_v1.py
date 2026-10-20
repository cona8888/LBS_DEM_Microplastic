"""Independent zero-step fresh-launch science, executable and lifecycle bridge."""
from pathlib import Path
from types import FunctionType,SimpleNamespace
import copy,itertools
import cone_feasibility_campaign_v1 as s
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
    d=api.read(job.DESIGN);job.verify(d);s.inherited();old=api.read(s.OLD_DESIGN);qual=api.read(s.QUAL_DESIGN)
    for key in ('cases','numerical_gates','budget','preflight','minimum_gap_semantics','worker_logical_cpus','auditor_logical_cpu','maximum_unverified_segments_total','maximum_unverified_segments_per_case'):
        api.require(d[key]==old[key]==qual[key],'independent frozen scientific equality '+key)
    bindings=s.bindings();pf=s.sealed(s.QUAL_OUT/'preflight_01/results.json');api.require(pf['new_steps']==17000 and pf['exact_restart'] and pf['parallel_identity'] and pf['cutoff_and_failure_drain'],'fresh actual full-stack qualification')
    actual=job.worker.__globals__['acknowledged'];api.require(actual is s.stack.acknowledged and actual.__globals__['ack'] is s.stack.ack,'actual worker receipt callback')
    events=0;corrupt=0
    for first in (False,True):
        folder=FIXTURES/('first' if first else 'successor');proxy=SimpleNamespace(policy=job.policy,DESIGN=folder/'design.json')
        adapter=FunctionType(actual.__code__,dict(actual.__globals__,job=proxy),actual.__name__,actual.__defaults__,actual.__closure__)
        api.require(s.q.campaign.code_sha(adapter)==s.q.campaign.code_sha(actual),'same real/fixture callback bytecode')
        for observations in ((False,False),(False,True),(True,True)):
            item=entry(folder,first);boundary=Boundary(item['paths']['receipt'],observations);item['paths']['receipt']=boundary
            pending=adapter(dict(audit_source_sha256='c'*64),[item]);api.require(boundary.calls==1 and pending==([] if observations[0] else [item]),'single monotonic availability observation')
            if observations==(False,True):api.require(adapter(dict(audit_source_sha256='c'*64),pending)==[] and boundary.calls==2,'published successor verified on next observation')
            events+=1
    for folder in sorted(FIXTURES.glob('mutation_*')):
        proxy=SimpleNamespace(policy=job.policy,DESIGN=folder/'design.json');adapter=FunctionType(actual.__code__,dict(actual.__globals__,job=proxy),actual.__name__,actual.__defaults__,actual.__closure__)
        try:adapter(dict(audit_source_sha256='c'*64),[entry(folder)])
        except (ValueError,RuntimeError):corrupt+=1
        else:raise AssertionError('accepted corrupt real receipt fixture '+str(folder))
    api.require(events==6 and corrupt==17,'all inherited real callback controls')
    mutations=[('case',lambda b:b['cases'].pop()),('timestep',lambda b:b['cases'][0].update(factor=1)),('horizon',lambda b:b['cases'][0]['spec'].update(horizon_s=1.)),('physics',lambda b:b['cases'][0]['spec']['config'].update(friction_coefficient=.31)),('gate',lambda b:b['numerical_gates'].update(whole_position_over_b_max=.1)),('concurrency',lambda b:b['budget'].update(workers=6)),('cap',lambda b:b['budget'].update(step_cap_per_call=20000)),('old_source',lambda b:b['sources'].pop(next(iter(old['sources'])))),('audit',lambda b:b.update(audit_source_sha256='0'*64)),('old_checkpoint',lambda b:b.update(fresh_start_required=False)),('qualified_solver',lambda b:b['qualified_numerical_bindings'].update(candidate_sha256='0'*64)),('deadline',lambda b:b.update(simulation_cutoff_utc='2030-01-01T00:00:00+00:00'))]
    rejected=[]
    for label,change in mutations:
        bad=copy.deepcopy(d);change(bad);bad.pop('binding');bad['binding']=api.digest(bad)
        try:job.verify(bad)
        except (ValueError,RuntimeError,AssertionError):rejected.append(label)
        else:raise AssertionError('accepted corrupt campaign '+label)
    count=0;order=[c['id'] for c in d['cases']]
    for permutation in itertools.permutations(order):
        life=job.policy.initial(order);remaining=list(permutation)
        while life.queued or life.active:
            while True:
                life,name=job.policy.dispatch(life,3,True)
                if name is None:break
                api.require(len(life.active)*2<=6,'original global-six backlog bound')
            name=next(n for n in remaining if n in life.active);remaining.remove(name);life=job.policy.retire(life,name,0,True)
        api.require(len(life.retired)==6 and not life.stop_reasons,'all six original dispatch/retirement outcomes');count+=1
    api.require(count==720 and len(rejected)==12,'all frozen-domain corruption/dispatch checks')
    proof=s.verify_old_disposition();api.require(not proof['old_failed_run_fully_accounted'] and proof['old_run_remains_failed'] and proof['full_old_accounting_required_before_final_acceptance'],'pending old failure neither pooled nor promoted')
    identities=proof['allowed_read_only_processes'];api.require(identities[0]['argv'][-2:]==['evaluate','campaign'] and identities[1]['argv'][-1].endswith('run_terminal_evaluator_v1.py'),'only original read-only audit commands')
    identity_corruptions=0
    for identity in identities:
        info={k:identity[k] for k in ('pid','argv','created')};api.require(s.allowed_old_identity(info,identities),'exact original read-only identity allowed')
        for key,value in [('pid',info['pid']+1),('created',info['created']+10),('argv',info['argv']+['worker']),('argv',info['argv'][:-1]+['campaign_restarted'])]:
            bad=copy.deepcopy(info);bad[key]=value;api.require(not s.allowed_old_identity(bad,identities),'reused PID or mutated old command rejected');identity_corruptions+=1
        bad_allowed=copy.deepcopy(identities);next(x for x in bad_allowed if x['pid']==info['pid'])['source_sha256']='0'*64
        api.require(not s.allowed_old_identity(info,bad_allowed),'wrong old source cannot bypass process exclusion');identity_corruptions+=1
    api.require(identity_corruptions==10,'all exact identity mutations rejected')
    try:s.require_old_terminal_closure()
    except FileNotFoundError:pass
    else:raise AssertionError('pending old audit cannot satisfy final closure')
    api.require(not job.RUN.exists() and not s.active_owned(),'no competing job before fresh launch')
    fit=s.resource_gate(d)
    files=[Path(__file__),job.DESIGN,job.WORK,s.QUAL_DESIGN,s.QUAL_CLOSE,s.RESOURCE,s.RESOURCE_AUDIT,s.OLD_LAUNCH_PROOF]
    result=dict(passed=True,new_trajectory_steps=0,design_sha256=api.sha(job.DESIGN),qualified_bindings=bindings,actual_callback_controls=events,corrupt_receipt_fixtures_rejected=corrupt,corrupt_campaigns_rejected=rejected,zero_step_dispatch_permutations=count,read_only_identity_corruptions_rejected=identity_corruptions,pending_old_accounting_rejected_as_final_closure=True,resource_fit=fit,inputs={str(p):api.sha(p) for p in files},claim='Launch bridge only. Fresh17,000-step qualification explicitly inherited; old failed observations remain failed with disclosed mandatory pending final accounting, no production trajectory yet.')
    out=job.OUT/'independent_bridge_01';job.commit(out/'results.json',result);job.commit(out/'completion.json',dict(passed=True,results_sha256=api.sha(out/'results.json')));print('CONE_CAMPAIGN_BRIDGE_PASS',api.sha(out/'results.json'),fit,flush=True)
if __name__=='__main__':run()
