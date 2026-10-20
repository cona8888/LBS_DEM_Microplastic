"""One non-promoted fibre step: compare two candidates on identical systems."""
from pathlib import Path
import copy
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'stage139_staging'))
import sphere_only_verification_v1 as parent
api,engine,hot,fast=parent.api,parent.engine,parent.hot,parent.fast
BASE='fibre_identical_system_branch_check_20260918'
DESIGN=ROOT/'stage141_designs'/BASE/'design_01.json'
OUT=ROOT/'stage141_evaluations'/BASE/'probe_01'

def verify(d):
    api.require(d['binding']==api.digest({k:v for k,v in d.items() if k!='binding'}),'design hash')
    api.verify_mapping(d['sources']);api.verify_mapping(d['inputs']);parent.verify(api.read(parent.DESIGN))

def prepare():
    pd=api.read(parent.DESIGN);parent.verify(pd)
    case=next(c for c in pd['cases'] if c['id']=='fibre_11_terminal')
    paths=[parent.DESIGN,parent.old.DESIGN,parent.old.OUT/'results.json',Path(case['source'])]
    d={'stage':'Stage141','case':case,'physical_changes':[],
       'question':'Can both moving and sticking contact candidates pass independent checks for the exact same saved fibre contact-system inputs?',
       'protocol':'Replay one accepted original-solver step only; observe every Krylov system and independently solve the all-stick sufficient search on exactly those arrays. Never return the alternative to the integrator; no checkpoint promotion.',
       'criterion':{'independent_original_and_alternative':True,'material_generalized_velocity_relative':1e-7},
       'scope':'Finite-precision contact-branch sensitivity diagnostic. A pair of accepted algebraic candidates is not physical validation, a unique trajectory, or release/retention evidence.',
       'budget':'One original accepted step with the unchanged 45-second cooperative budget; a few 9-variable linear programs only.',
       'sources':{str(Path(__file__).resolve()):api.sha(__file__)},'inputs':{str(p):api.sha(p) for p in paths}}
    d['binding']=api.digest(d);DESIGN.parent.mkdir(parents=True,exist_ok=True);api.write(DESIGN,d)
    print('FROZEN',api.sha(DESIGN),flush=True)

def run():
    d=api.read(DESIGN);verify(d);parent.old.prior.prior.configure();hot.warmup()
    c=d['case'];cp=copy.deepcopy(api.read(c['source'])['result']['checkpoint'])
    api.require(cp['state_sha256']==c['state_sha256']==api.digest(cp['state']),'source state')
    bound=api.digest([d['binding'],c['id']]);cp['contract']=engine.prior.contracts.expected_contract(c['spec'],bound)
    OUT.mkdir(parents=True,exist_ok=False);rows=[];portfolio=fast.portfolio;original=portfolio._root_candidate
    np=api.np
    def capture(method,*args):
        q,h=original(method,*args)
        v,M,J,g,dt,mu,*_=args
        row={'method':method,'inputs':api.normalized(args),'input_sha256':api.digest(args),'original_velocity':q.tolist(),
             'original_health':copy.deepcopy(h),'original_independent':engine.local.independent_contact(*args[:6],q,h),
             'jacobian_singular_values':np.linalg.svd(J,compute_uv=False).tolist()}
        try:
            alt,ah=fast.candidate(*args)
            row.update(alternative_returned=True,alternative_velocity=alt.tolist(),alternative_health=copy.deepcopy(ah),
                       alternative_independent=engine.local.independent_contact(*args[:6],alt,ah),
                       velocity_difference_over_reference_flow=float(np.linalg.norm(alt-q)/c['spec']['config']['target_mean_interstitial_velocity_m_s']))
            for label,qq,hh in [('original',q,h),('alternative',alt,ah)]:
                f=np.array(hh['reactions']).reshape(-1,3)
                row[label+'_contact_velocity']=(J@qq).reshape(-1,3).tolist()
                row[label+'_cone_margin_N']=(mu*f[:,0]-np.linalg.norm(f[:,1:],axis=1)).tolist()
                row[label+'_normal_reaction_N']=f[:,0].tolist()
                row[label+'_reaction_norm_N']=float(np.linalg.norm(f))
        except (ValueError,RuntimeError) as exc:row.update(alternative_returned=False,error=str(exc))
        rows.append(row)
        return q,h
    portfolio._root_candidate=capture
    try:
        with hot.scope():r,intervals=engine.runtime.execute(c['spec'],bound,checkpoint=cp,pause=cp['state']['steps']+1)
    finally:portfolio._root_candidate=original
    health=engine.prior.reference.independent_health(r,c['spec'])
    observed=any(x['original_independent'] and x.get('alternative_independent',False) and x.get('velocity_difference_over_reference_flow',0)>d['criterion']['material_generalized_velocity_relative'] for x in rows)
    reference=api.read(parent.old.OUT/'fibre_11_terminal_reference.json')['rows'][0]
    unchanged=all(r[k]==reference[k] for k in ['time_s','position_m','orientation','velocity_generalized'])
    verify(d)
    result={'probe_completed':health['passed'] and r['status']=='paused_checkpoint' and len(intervals)==1 and unchanged,
            'original_step_exactly_reproduced':unchanged,'same_input_distinct_admissible_candidates_observed':observed,
            'systems':rows,'result':r,'health':health,'design_sha256':api.sha(DESIGN),
            'checkpoint_input_sha256':api.digest(cp),'interpretation':d['scope'],
            'promotion':'None. Fibre acceleration remains disabled; do not resolve branch selection by choosing whichever solution supports a preferred retention or release result.'}
    api.write(OUT/'results.json',result,raw=True);api.write(OUT/'completion.json',{'results_sha256':api.sha(OUT/'results.json'),'design_sha256':api.sha(DESIGN)})
    print('IDENTICAL_SYSTEM_PROBE',result['probe_completed'],'BRANCH_SENSITIVITY',observed,
          [x.get('velocity_difference_over_reference_flow') for x in rows],flush=True)

if __name__=='__main__':
    if sys.argv[1]=='prepare':prepare()
    elif sys.argv[1]=='run':run()
    else:raise ValueError(sys.argv[1])
