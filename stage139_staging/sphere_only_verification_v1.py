"""Fail-closed restriction of Stage138 acceleration to explicit spheres only."""
from contextlib import contextmanager, nullcontext
from pathlib import Path
import copy
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'stage138_staging')]
import qualify_sticking_v1 as old
api,engine,hot,fast=old.api,old.engine,old.hot,old.fast
BASE='sphere_only_sticking_verification_20260918'
DESIGN=ROOT/'stage139_designs'/BASE/'design_01.json'
OUT=ROOT/'stage139_evaluations'/BASE/'qualification_01'

@contextmanager
def scope(spec):
    a,b,c=spec['config']['prolate_semiaxes_m']
    with fast.scope() if a==b==c else nullcontext():
        yield

def verify(d):
    api.require(d['binding']==api.digest({k:v for k,v in d.items() if k!='binding'}),'design hash')
    api.verify_mapping(d['sources']);api.verify_mapping(d['inputs']);old.verify(api.read(old.DESIGN))

def prepare():
    previous=api.read(old.DESIGN);old.verify(previous)
    evidence=old.OUT/'results.json';seal=old.OUT/'completion.json';ev=api.read(evidence)
    api.require(api.read(seal)['results_sha256']==api.sha(evidence),'failed experiment seal')
    api.require(not ev['passed'],'preserve failed general qualification')
    api.verify_mapping(ev['artifacts'])
    d={'stage':'Stage139','cases':previous['cases'],'accepted_steps':previous['accepted_steps'],'limits':previous['limits'],
       'physical_changes':[],'scope':'Only explicit equal-semiaxis spheres use the guarded candidate. Every non-sphere retains Stage136 exactly. No time hold or altered timestep.',
       'rejected_generalization':'Stage138 selected another admissible contact solution at the terminal fibre state. Do not use that branch for fibres or call algebraic residuals proof of trajectory uniqueness.',
       'acceptance':'All seven inherited references must pass; all three fibre replays must have zero candidate attempts and exact pose/velocity/clock; every accepted sphere candidate independently checked; scaled controls and negative guards inherited and rechecked.',
       'sources':{str(Path(__file__).resolve()):api.sha(__file__)},
       'inputs':{str(p):api.sha(p) for p in [old.DESIGN,evidence,seal]}}
    d['inputs'].update(ev['artifacts']);d['binding']=api.digest(d)
    DESIGN.parent.mkdir(parents=True,exist_ok=True);api.write(DESIGN,d)
    print('FROZEN',api.sha(DESIGN),flush=True)

def run():
    d=api.read(DESIGN);verify(d);old.prior.prior.configure();hot.warmup()
    OUT.mkdir(parents=True,exist_ok=False);pairs=[];checks=[];original=fast.candidate
    def checked(*args,**kwargs):
        q,h=original(*args,**kwargs);ok=engine.local.independent_contact(*args[:6],q,h)
        checks.append({'passed':ok,'health':h});api.require(ok,'independent contact');return q,h
    fast.candidate=checked
    try:
        for c in d['cases']:
            cp=copy.deepcopy(api.read(c['source'])['result']['checkpoint'])
            api.require(cp['state_sha256']==c['state_sha256']==api.digest(cp['state']),'source state')
            bound=api.digest([d['binding'],c['id']]);cp['contract']=engine.prior.contracts.expected_contract(c['spec'],bound)
            before=copy.deepcopy(fast.work)
            with hot.scope(),scope(c['spec']):
                r,rows=engine.runtime.execute(c['spec'],bound,checkpoint=cp,pause=cp['state']['steps']+d['accepted_steps'])
            health=engine.prior.reference.independent_health(r,c['spec']);work={k:fast.work[k]-before[k] for k in before}
            reference=api.read(old.OUT/(c['id']+'_reference.json'));a=reference['result']
            cmp=old.prior.compare_results(a,r,c['spec'],d['limits'])
            decisions=all(a[k]==r[k] for k in ['status','steps','rejected','contact_solver_retries','persistent_contact_observed'])
            intervals_ok=len(rows)==len(reference['rows'])==d['accepted_steps'] and all(old.prior.compare_results(x,y,c['spec'],d['limits'])['passed'] and x['dt_s']==y['dt_s'] and x['active_contact_ids']==y['active_contact_ids'] and x['supported_bearing_ids']==y['supported_bearing_ids'] for x,y in zip(reference['rows'],rows))
            a0,b0,c0=c['spec']['config']['prolate_semiaxes_m'];sphere=a0==b0==c0
            excluded=sphere or (work['attempts']==0 and all(r[k]==a[k] for k in ['position_m','orientation','velocity_generalized','time_s']))
            cmp.update(case=c['id'],sphere=sphere,work=work,same_decisions=decisions,intervals_passed=intervals_ok,non_sphere_exactly_unchanged=excluded,
                       reference_s=a['runtime_seconds'],candidate_s=r['runtime_seconds'])
            cmp['passed'] &= decisions and intervals_ok and excluded and health['passed'] and r['status']=='paused_checkpoint'
            rec={'result':r,'rows':rows,'health':health,'comparison':cmp,'design_sha256':api.sha(DESIGN),'checkpoint_input_sha256':api.digest(cp),'reference_sha256':api.sha(old.OUT/(c['id']+'_reference.json'))}
            api.write(OUT/(c['id']+'.json'),rec,raw=True);pairs.append(cmp)
            print(c['id'],cmp['passed'],r['runtime_seconds'],work,flush=True)
    finally:fast.candidate=original
    ev=api.read(old.OUT/'results.json')
    passed=all(x['passed'] for x in pairs+checks+ev['toys']) and all(x['rejected'] for x in ev['negative_guards'])
    verify(d)
    result={'passed':passed,'pairs':pairs,'independent_contact_checks':checks,
            'negative_controls':ev['negative_guards'],'scaled_controls':ev['toys'],
            'sphere_stationary_speedup':sum(x['reference_s'] for x in pairs if x['case'] in ['sphere_12','sphere_12_terminal'])/sum(x['candidate_s'] for x in pairs if x['case'] in ['sphere_12','sphere_12_terminal']),
            'artifacts':{str(p):api.sha(p) for p in OUT.iterdir() if p.is_file()},
            'claim':'Locally verified sphere-only acceleration, not a universal contact solver or fibre equilibrium proof.'}
    api.write(OUT/'results.json',result,raw=True);api.write(OUT/'completion.json',{'results_sha256':api.sha(OUT/'results.json'),'design_sha256':api.sha(DESIGN)})
    print('SPHERE_ONLY_QUALIFIED',passed,flush=True)

if __name__=='__main__':
    if sys.argv[1]=='prepare':prepare()
    elif sys.argv[1]=='run':run()
    else:raise ValueError(sys.argv[1])
