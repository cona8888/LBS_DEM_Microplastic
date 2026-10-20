"""Prospective local verification of a guarded all-stick contact branch."""
from pathlib import Path
from contextlib import nullcontext
import copy
import sys
import time
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'stage136_staging'),str(ROOT/'stage137_staging')]
import qualify_and_continue_v1 as prior
import profile_remaining_cost_v1 as diagnosis
import sticking_candidate_v1 as fast
api,engine,hot=prior.api,prior.engine,prior.hot
BASE='sticking_contact_acceleration_20260918'
DESIGN=ROOT/'stage138_designs'/BASE/'design_01.json'
OUT=ROOT/'stage138_evaluations'/BASE/'qualification_01'

def verify(d):
    api.require(d['binding']==api.digest({k:v for k,v in d.items() if k!='binding'}),'design hash')
    api.verify_mapping(d['sources']);api.verify_mapping(d['inputs'])
    prior.verify(api.read(prior.DESIGN));diagnosis.verify(api.read(diagnosis.DESIGN))

def prepare():
    pd=api.read(prior.DESIGN);prior.verify(pd)
    dd=api.read(diagnosis.DESIGN);diagnosis.verify(dd)
    ev=diagnosis.OUT/'results.json'
    api.require(api.read(ev)['passed'] and api.read(diagnosis.OUT/'completion.json')['results_sha256']==api.sha(ev),'profile seal')
    api.verify_mapping(api.read(ev)['artifacts'])
    inputs={str(p):api.sha(p) for p in [prior.DESIGN,diagnosis.DESIGN,ev]}
    cases=[copy.deepcopy(c) for c in pd['cases']]
    for c in dd['cases']:
        cases.append({'id':c['id']+'_terminal','source':c['source'],'spec':c['spec'],'state_sha256':c['source_state_sha256']})
        inputs[c['source']]=api.sha(c['source'])
    d={'stage':'Stage138','physical_changes':[], 'question':'Does a sufficient all-stick force search remove wasted nonlinear work without changing the accepted trajectory?',
       'cases':cases,'accepted_steps':8,'limits':pd['acceptance'],
       'acceptance':'Seven paired checkpoint replays, original contact gates plus independent recomputation, identical retry/contact/step decisions, three scaled constructed sticking controls and negative eligibility controls. No force identity required for statically indeterminate contacts.',
       'scope':'No equilibrium time hold or changed integration step; no production promotion from a local result. Original cold nonlinear fallback retained.',
       'sources':{str(p):api.sha(p) for p in Path(__file__).parent.glob('*.py')},'inputs':inputs}
    d['binding']=api.digest(d);DESIGN.parent.mkdir(parents=True,exist_ok=True);api.write(DESIGN,d)
    print('FROZEN',api.sha(DESIGN),flush=True)

def run():
    d=api.read(DESIGN);verify(d);prior.prior.configure();hot.warmup()
    OUT.mkdir(parents=True,exist_ok=False);pairs=[];checks=[];reference_total=fast_total=0.
    original=fast.candidate
    def independently_checked(*args,**kwargs):
        q,h=original(*args,**kwargs)
        check=engine.local.independent_contact(*args[:6],q,h)
        checks.append({'passed':check,'health':copy.deepcopy(h)})
        api.require(check,'independent candidate check')
        return q,h
    fast.candidate=independently_checked
    try:
        for c in d['cases']:
            cp=copy.deepcopy(api.read(c['source'])['result']['checkpoint'])
            api.require(cp['state_sha256']==c['state_sha256']==api.digest(cp['state']),'source state')
            bound=api.digest([d['binding'],c['id']]);cp['contract']=engine.prior.contracts.expected_contract(c['spec'],bound)
            results=[]
            for mode in ['reference','fast']:
                before=copy.deepcopy(fast.work)
                with hot.scope(), fast.scope() if mode=='fast' else nullcontext():
                    r,rows=engine.runtime.execute(c['spec'],bound,checkpoint=copy.deepcopy(cp),pause=cp['state']['steps']+d['accepted_steps'])
                health=engine.prior.reference.independent_health(r,c['spec'])
                work={k:fast.work[k]-before[k] for k in before}
                rec={'result':r,'rows':rows,'health':health,'work':work,'design_sha256':api.sha(DESIGN),'checkpoint_input_sha256':api.digest(cp)}
                api.write(OUT/(c['id']+'_'+mode+'.json'),rec,raw=True);results.append(rec)
            a,b=results
            cmp=prior.compare_results(a['result'],b['result'],c['spec'],d['limits'])
            decisions=all(a['result'][k]==b['result'][k] for k in ['status','steps','rejected','contact_solver_retries','persistent_contact_observed'])
            rows_ok=len(a['rows'])==len(b['rows'])==d['accepted_steps'] and all(prior.compare_results(x,y,c['spec'],d['limits'])['passed'] and x['dt_s']==y['dt_s'] and x['active_contact_ids']==y['active_contact_ids'] and x['supported_bearing_ids']==y['supported_bearing_ids'] for x,y in zip(a['rows'],b['rows']))
            cmp.update(case=c['id'],same_decisions=decisions,intervals_passed=rows_ok,reference_s=a['result']['runtime_seconds'],fast_s=b['result']['runtime_seconds'],fast_work=b['work'])
            cmp['passed'] &= decisions and rows_ok and a['health']['passed'] and b['health']['passed'] and a['result']['status']=='paused_checkpoint'
            pairs.append(cmp);reference_total+=cmp['reference_s'];fast_total+=cmp['fast_s']
            print(c['id'],cmp['passed'],cmp['reference_s'],cmp['fast_s'],b['work'],flush=True)
    finally:fast.candidate=original
    np=api.np
    trace=api.read(diagnosis.OUT/'sphere_12_trace.json');J=np.array(trace[0]['args'][2]);g=np.zeros(3);M=np.eye(6)
    f=np.zeros(9);f[::3]=1.;toy=[]
    for scale in [1e-7,1.,1e3]:
        v=-J.T@f*scale
        q,h=prior.scalar_scope._scoped(fast.candidate,v,M,J,g,1.,.3,1e-10,25000)
        error=float(np.linalg.norm(q)/np.linalg.norm(v));ok=error<=1e-10 and engine.local.independent_contact(v,M,J,g,1.,.3,q,h)
        toy.append({'scale':scale,'velocity_relative':error,'health':h,'passed':ok})
    negative=[]
    for label in ['rank_deficient','finite_gap','frictionless','nonfinite']:
        v=-J.T@f; jj=J.copy(); gg=g.copy();mu=.3
        if label=='rank_deficient':jj[:,3:]=0.
        if label=='finite_gap':gg[0]=1.
        if label=='frictionless':mu=0.
        if label=='nonfinite':v[0]=np.nan
        try:fast.candidate(v,M,jj,gg,1.,mu,1e-10,25000)
        except (ValueError,RuntimeError):rejected=True
        else:rejected=False
        negative.append({'test':label,'rejected':rejected})
    speed=reference_total/fast_total
    passed=all(p['passed'] for p in pairs+toy+checks) and all(p['rejected'] for p in negative) and speed>=1.2
    verify(d)
    result={'passed':passed,'pairs':pairs,'independent_candidate_checks':checks,'toys':toy,'negative_guards':negative,
            'aggregate_warmed_speedup':speed,'reference_s':reference_total,'fast_s':fast_total,
            'artifacts':{str(p):api.sha(p) for p in OUT.iterdir() if p.is_file()},
            'claim':'Local solver qualification only. No time skipping, permanent trapping, full-path convergence or population release inference.'}
    api.write(OUT/'results.json',result,raw=True);api.write(OUT/'completion.json',{'results_sha256':api.sha(OUT/'results.json'),'design_sha256':api.sha(DESIGN)})
    print('QUALIFIED',passed,'speedup',speed,flush=True)

if __name__=='__main__':
    if sys.argv[1]=='prepare':prepare()
    elif sys.argv[1]=='run':run()
    else:raise ValueError(sys.argv[1])
