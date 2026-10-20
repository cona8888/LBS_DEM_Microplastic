"""Frozen zero-step geometric certificate checks and archived sweep replays."""
from pathlib import Path
import copy,sys,time,traceback
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'stage173_staging'))
import qualify_immutable_field_v1 as upstream
import certified_sweep_v1 as candidate
api,parent,p,fast=upstream.api,upstream.parent,upstream.p,upstream.fast
DESIGN=ROOT/'stage174_designs/certified_sweep_20260924/design_01.json'
OUT=ROOT/'stage174_evaluations/certified_sweep_20260924/units_01'


def prepare():
    upstream.prior.unit.check_time();upstream.verify(api.read(upstream.DESIGN))
    audit=upstream.OUT.parent/'independent_audit_01';api.require(api.read(audit/'results.json')['passed'],'snapshot audit required')
    cases=api.read(upstream.DESIGN)['cases'];inputs=[upstream.DESIGN,upstream.OUT/'results.json',upstream.OUT/'completion.json',
        audit/'results.json',audit/'completion.json']
    for c in cases:
        for path in [Path(c['source']),upstream.RUN/(c['id']+'_cached.json.gz')]:inputs.extend([path,path.with_suffix('.seal.json')])
    d={'stage':'Stage174_certificate_units','physical_changes':[],'acceptance_threshold_changed':False,
       'purpose':'Certify nonpenetration conservatively before expensive swept minimization; use unchanged minimizers otherwise.',
       'diagnostic_semantics':'minimum_gap_m and checkpoint minimum_gap/history gap are conservative lower bounds after any certified step; never label them measured minima. All physical trajectory state, timestep and acceptance thresholds unchanged.',
       'roundoff':'Original Stage116 engineering pad retained; this is not formal interval arithmetic.',
       'limits':{'maximum_bound_excess_m':1e-17,'trajectory_rows_required_bitwise':True},
       'cases':cases,'random_seed':174,'synthetic_cases':64,'dense_samples_per_synthetic_case':129,
       'maximum_new_trajectory_steps':0,'maximum_wall_s':180.,'stop_utc':api.read(upstream.DESIGN)['stop_utc'],
       'sources':parent.source_map(),'inputs':{str(x):api.sha(x) for x in inputs}}
    d['binding']=api.digest(d);DESIGN.parent.mkdir(parents=True,exist_ok=True);api.write(DESIGN,d);print('FROZEN',api.sha(DESIGN),flush=True)


def verify(d):
    api.require(d['binding']==api.digest({k:v for k,v in d.items() if k!='binding'}),'sweep design binding')
    api.verify_mapping(d['sources']);api.verify_mapping(d['inputs']);upstream.verify(api.read(upstream.DESIGN))


def run():
    d=api.read(DESIGN);verify(d);upstream.prior.unit.check_time();OUT.mkdir(parents=True,exist_ok=False)
    start=time.perf_counter();reports=[];records=[]
    try:
        # Fixed-seed synthetic motions include clear, penetrating, grazing,
        # translating, rotating and periodic poses; these are development tests.
        rng=np.random.default_rng(d['random_seed']);a=4e-5;b=1e-5;L=1e-3;radius=1e-4
        for i in range(d['synthetic_cases']):
            x=rng.uniform(0,L,3);orientation=rng.normal(size=3);orientation/=np.linalg.norm(orientation)
            direction=rng.normal(size=3);direction/=np.linalg.norm(direction)
            distance=radius+rng.uniform(.8*b,1.2*a)
            centre=np.mod(x+distance*direction,L)
            geometry=candidate.original.GrainGeometry([centre],[radius],L)
            v=rng.normal(size=6)*10.**rng.uniform(-7,-2);dt=10.**rng.uniform(-6,-2)
            if i%8==0:v[:]=0.
            old=candidate.REFERENCE(geometry,x,orientation,v,a,b,dt)
            row=candidate.certificate(geometry,x,orientation,v,a,b,dt)
            new=candidate.swept_gap(geometry,x,orientation,v,a,b,dt)
            same=(old>=-1e-5*b)==(new>=-1e-5*b)
            conservative=True;dense_min=None
            if row is not None:
                delta=geometry.c[0]-x;delta-=L*np.round(delta/L);c=x+delta
                motion=candidate.original._FixedMotion(x,orientation,v,a)
                samples=[candidate.original._gap_at_pose(*motion.at(t),a,b,c,radius) for t in np.linspace(0,dt,d['dense_samples_per_synthetic_case'])]
                dense_min=min(samples)
                conservative=row['lower_bound_m']<=min(old,dense_min)+d['limits']['maximum_bound_excess_m']
            reports.append({'id':f'synthetic_{i}','passed':same and conservative,'same_acceptance':same,'bound_conservative':conservative,
                            'old_gap_m':old,'new_bound_or_gap_m':new,'dense_min_m':dense_min,'certificate':row})
        # Original archive motions provide the actual contact-stage boundary.
        parent.b.old.parent.configure();metadata=api.read(upstream.DESIGN)
        with upstream.snapshot.scope(api,parent.storage.read_record(Path(d['cases'][0]['source']),d['cases'][0]['source_design_sha256'])['spec']['field_metadata']):
            field,data,meta=api.fields.load(2,1.,6)
            geometry=candidate.original.GrainGeometry(data['sand_centres_m'],data['sand_radii_m'],meta['cell_length_m'])
            for case in d['cases']:
                source=parent.storage.read_record(Path(case['source']),case['source_design_sha256'])
                raw=parent.storage.read_record(upstream.RUN/(case['id']+'_cached.json.gz'),api.sha(upstream.DESIGN))
                spec=raw['spec'];a,b,_=spec['config']['prolate_semiaxes_m'];state=source['result']['checkpoint']['state']
                x=np.array(state['x']);orientation=np.array(state['p']);old_s=new_s=0.;passed=True;certified=0;case_rows=[]
                for i,row in enumerate(raw['rows']):
                    v=np.array(row['velocity_generalized']);dt=row['dt_s']
                    t=time.perf_counter();old=candidate.REFERENCE(geometry,x,orientation,v,a,b,dt);old_s+=time.perf_counter()-t
                    t=time.perf_counter();proof=candidate.certificate(geometry,x,orientation,v,a,b,dt);new=candidate.swept_gap(geometry,x,orientation,v,a,b,dt);new_s+=time.perf_counter()-t
                    same=(old>=-1e-5*b)==(new>=-1e-5*b)
                    bound=proof is None or proof['lower_bound_m']<=old+d['limits']['maximum_bound_excess_m']
                    passed &= same and bound;certified+=bool(proof and proof['certified'])
                    case_rows.append({'index':i,'passed':same and bound,'original_gap_m':old,'candidate_m':new,'certificate':proof})
                    x=np.array(row['position_m']);orientation=np.array(row['orientation'])
                path=OUT/(case['id']+'_sweeps.json');api.write(path,case_rows,raw=True);records.append(path)
                reports.append({'id':case['id'],'passed':bool(passed),'archived_motions':len(raw['rows']),'certified':certified,
                                'reference_s':old_s,'candidate_with_duplicate_proof_s':new_s})
                print('SWEEP',case['id'],'PASS',passed,'CERTIFIED',certified,'/',len(raw['rows']),flush=True)
        elapsed=time.perf_counter()-start;api.require(elapsed<=d['maximum_wall_s'],'bounded geometric checks')
        result={'passed':all(x['passed'] for x in reports),'reports':reports,'new_trajectory_steps':0,'wall_s':elapsed,
                'design_sha256':api.sha(DESIGN),'artifacts':{str(x):api.sha(x) for x in records},
                'diagnostic_semantics':d['diagnostic_semantics'],'claim':'Analytical Lipschitz bound with engineering floating-point pad and finite development tests, not formal interval proof.'}
        verify(d);api.write(OUT/'results.json',result,raw=True);api.write(OUT/'completion.json',{'passed':result['passed'],'results_sha256':api.sha(OUT/'results.json')})
        print('CERTIFICATE_UNITS',result['passed'],'FAILED',[x['id'] for x in reports if not x['passed']],flush=True)
    except Exception as e:
        api.write(OUT/'failure.json',{'error':repr(e),'traceback':traceback.format_exc()});raise


if __name__=='__main__':
    if sys.argv[1:]==['prepare']:prepare()
    elif sys.argv[1:]==['run']:run()
    else:raise ValueError('prepare | run')
