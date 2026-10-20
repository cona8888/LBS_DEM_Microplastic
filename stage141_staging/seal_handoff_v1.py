"""Read-only independent dwell recomputation and concise evidence handoff."""
from pathlib import Path
import copy
import gzip
import json
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'stage140_staging'),str(ROOT/'stage141_staging')]
import sphere_dwell_refinement_v1 as run
import check_fibre_branch_v1 as branch
api=run.api
OUT=ROOT/'stage141_evaluations/fibre_identical_system_branch_check_20260918/handoff_01'

def main():
    d=api.read(run.DESIGN);run.verify(d);done=api.read(run.RUN/'completion.json')
    evalpath=run.OUT/'results.json';ev=api.read(evalpath)
    api.require(api.read(run.OUT/'completion.json')['results_sha256']==api.sha(evalpath),'refinement seal')
    api.verify_mapping(ev['artifacts']);branch.verify(api.read(branch.DESIGN))
    bp=branch.OUT/'results.json';br=api.read(bp)
    api.require(api.read(branch.OUT/'completion.json')['results_sha256']==api.sha(bp),'branch seal')
    bindings={str(p):api.sha(p) for p in [run.DESIGN,evalpath,bp,Path(__file__).resolve()]}
    for module in list(sys.modules.values()):
        filename=getattr(module,'__file__',None)
        if filename and 'scipy' in filename and ('highs' in filename or filename.endswith('.pyd')):
            bindings[str(Path(filename).resolve())]=api.sha(filename)
    checks=[];np=api.np
    for c,e in zip(d['cases'],done['ledger']):
        cp,_=run.initial(d,c);state=cp['state'];monitor=copy.deepcopy(state['monitor'])
        a,b,_=c['spec']['config']['prolate_semiaxes_m'];anchor=np.array(monitor['anchor']);elapsed=monitor['elapsed'];angular=monitor['angular_travel']
        ids=monitor['contact_ids'];bearing=monitor['load_bearing_ids'];original_ids=list(ids);original_bearing=list(bearing)
        first=state['first_contact_dwell_time'];eligible_all=True;same_contacts=True;maxdrift=monitor['maximum_drift'];maxratio=monitor['maximum_speed_ratio'];count=0;resets_after_event=0
        for binding in e['records']:
            p=Path(binding['path']);r=api.read(p)['result'];bindings[str(p)]=api.sha(p)
            z=p.parent/'intervals.json.gz';bindings[str(z)]=api.sha(z)
            with gzip.open(z,'rb') as f:rows=json.load(f)
            for row in rows:
                q=np.array(row['velocity_generalized']);dt=row['dt_s']
                linear=float(np.linalg.norm(q[:3]));rot=float(np.linalg.norm(q[3:]))
                ratio=max(linear,rot)/monitor['reference_speed'];xx=np.array(row['position_m'])
                rid=sorted(set(row['active_contact_ids']));rb=sorted(set(row['supported_bearing_ids']))
                same_contacts &= rid==original_ids and rb==original_bearing
                eligible=ratio<=monitor['speed_ratio'] and len(rb)>=monitor['minimum_contacts'] and set(rb).issubset(rid)
                count+=1
                if not eligible:
                    elapsed=angular=maxdrift=maxratio=0.;anchor=None;ids=[];bearing=[];eligible_all=False
                    if first is not None:resets_after_event+=1
                    continue
                if anchor is None or ids!=rid or bearing!=rb:
                    elapsed=angular=maxdrift=maxratio=0.;anchor=xx-dt*q[:3];ids=rid;bearing=rb
                    if first is not None:resets_after_event+=1
                angular+=dt*rot;drift=float(np.linalg.norm(xx-anchor))+angular
                if drift>monitor['drift_limit']:
                    elapsed=angular=maxdrift=maxratio=0.;anchor=None;ids=[];bearing=[];eligible_all=False
                    if first is not None:resets_after_event+=1
                    continue
                elapsed+=dt;maxdrift=max(maxdrift,drift);maxratio=max(maxratio,ratio)
                if elapsed>=monitor['dwell_time'] and first is None:first=row['time_s']
            api.require(abs(elapsed-r['checkpoint']['state']['monitor']['elapsed'])<1e-12,'independent dwell clock')
            api.require(first==r['first_contact_dwell_time_s'],'independent first dwell')
        checks.append({'case':c['id'],'records':len(e['records']),'accepted_intervals':count,
                       'clock_and_event_recomputed':True,'continuous_eligibility':eligible_all,'unchanged_contact_set':same_contacts,
                       'first_dwell_s':first,'dwell_elapsed_s':elapsed,'max_surface_drift_m':maxdrift,'max_speed_ratio':maxratio,
                       'post_event_monitor_resets':resets_after_event,
                       'finite_dwell_observed':count>0 and first is not None})
    OUT.mkdir(parents=True,exist_ok=False)
    r={'status':'numerical_plan_correction_required_no_population_campaign',
       'sphere_only_local_qualification':True,'sphere_refinement_passed':ev['passed'],
       'refinement_complete':ev['all_queries_complete'],'no_failure_or_stderr':ev['no_failure_or_stderr'],
       'independent_dwell_checks':checks,'fibre_identical_system_branch_sensitivity':br['same_input_distinct_admissible_candidates_observed'],
       'population_release_fraction':None,'binding_hashes':bindings,
       'runtime_environment':{'python':sys.version,'numpy':np.__version__,'scipy':__import__('scipy').__version__,
                              'note':'Dependency hashes captured at handoff; local comparisons used the same installed environment.'},
       'next_actions':[
           'Repair signed-gap/small-timestep and final-time handling using roundoff-aware verification; no silent gap clipping or query-time snapping.',
           'Resolve fibre contact-mode/tolerance sensitivity on the two captured identical systems before further fibre trajectory claims.',
           'Preflight all timestep levels and add a prospective no-progress dispatch guard before repeating a short refinement.',
           'Only after those pass, resume the unchanged population/flow research objective; no calibration loop or broad campaign now.'],
       'claim':'Finite dwell in one conditional sphere case is not irreversible retention, whole-matrix release, full-path convergence or experimental validation.'}
    api.write(OUT/'results.json',r);api.write(OUT/'completion.json',{'results_sha256':api.sha(OUT/'results.json')})
    print({k:v for k,v in r.items() if k!='binding_hashes'},flush=True)

if __name__=='__main__':main()
