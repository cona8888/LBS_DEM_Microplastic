"""Replicated Stage 4 far-field bound. Never launches LBM/DEM/GPU work."""
import argparse,hashlib,json,platform,sys,time
from pathlib import Path
import numpy as np
from scipy.stats import qmc

ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/'stage37_staging'))
import transport_contact as model
import trajectory_farfield_v1 as engine

DESIGN=ROOT/'stage37_designs/stage4_farfield_bound_v1.json'
VERIFY=ROOT/'stage37_evaluations/farfield_verification_04/results.json'

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def packing_paths(seed):
    case=f's31b_n216_s{seed}_clean'
    geometry=ROOT/'stage31_designs/stage31d_replicated_nested_cpd2_geometry_20260826/geometry_01'/case/'geometry_cpd2.npz'
    run=ROOT/'stage31_runs/stage31e_replicated_nested_cpd2_gpu_20260826/gpu_screen_01'/f'stage31e_{case}_cpd2'
    return geometry,run/'final_fields.npz',run/'record.json'

def load(seed,cfg):
    gp,fp,rp=packing_paths(seed); record=json.loads(rp.read_text())
    if not record.get('passed') or not record.get('converged'): raise RuntimeError(f'packing {seed} flow record not accepted')
    if sha(fp)!=record['artifacts']['final_fields_npz_sha256']: raise RuntimeError(f'packing {seed} field hash mismatch')
    g=np.load(gp); f=np.load(fp); dx=float(g['spacing_m'][0]); L=float(g['cell_length_m'][0])
    phase=np.asarray(f['phase']).transpose(2,1,0); geomphase=np.asarray(g['phase']).transpose(2,1,0)
    if not np.array_equal(phase,geomphase): raise RuntimeError('field/geometry phase mismatch')
    u=np.asarray(f['velocity_xyz_lu'],float).transpose(0,3,2,1); fluid=phase==0
    mean=float(u[0,fluid].mean()); target=cfg['fluid']['target_mean_interstitial_x_velocity_m_s']
    if not mean>0: raise RuntimeError('nonpositive archived mean flow')
    field=model.CellField(u*(target/mean),dx,fluid)
    geom=model.GrainGeometry(np.asarray(g['sand_centres_m']),np.asarray(g['sand_radii_m']),L)
    return field,geom,L,dx,mean,(gp,fp,rp)

def starts(field,geom,L,a,b,rs,count,seed,cutoff):
    sob=qmc.Sobol(5,scramble=True,seed=seed).random_base2(17); candidate=[]
    for row in sob:
        x=row[:3]*L; z=2*row[3]-1; phi=2*np.pi*row[4]
        p=np.array([np.sqrt(max(0,1-z*z))*np.cos(phi),np.sqrt(max(0,1-z*z))*np.sin(phi),z])
        sx=max(model.support([1,0,0],p,a,b),rs)
        if x[0]-sx<=0 or x[0]+sx>=L: continue
        try: field.sample(x)
        except ValueError: continue
        cp=engine.clearance_ratio_at(geom,x,p,a,b,cutoff*geom.r.max())
        cs=engine.clearance_ratio_at(geom,x,p,rs,rs,cutoff*geom.r.max())
        if min(cp,cs)<=cutoff: continue
        candidate.append({'position_m':x,'orientation':p,'clearance':min(cp,cs)})
        if len(candidate)>=4096: break
    if len(candidate)<count*3: raise RuntimeError('insufficient admissible start pool')
    q=np.quantile([v['clearance'] for v in candidate],[1/3,2/3]); groups={(i,j):[] for i in range(3) for j in range(3)}
    for v in candidate:
        xb=min(2,int(3*v['position_m'][0]/L)); cb=int(v['clearance']>q[0])+int(v['clearance']>q[1]); groups[xb,cb].append(v)
    quota={k:count//9+(i<count%9) for i,k in enumerate(sorted(groups))}; chosen=[]
    for k in sorted(groups):
        if len(groups[k])<quota[k]: raise RuntimeError(f'insufficient stratum {k}')
        for v in groups[k][:quota[k]]: v['stratum']=list(k); chosen.append(v)
    return [{'id':i,'position_m':v['position_m'].tolist(),'orientation':v['orientation'].tolist(),
             'initial_minimum_clearance_ratio':float(v['clearance']),'stratum':v['stratum']} for i,v in enumerate(chosen)]

def one(field,geom,L,cfg,start,shape,disp,wall_budget):
    a,b,_=cfg['shapes']['prolate']['semiaxes_m']; rs=(a*b*b)**(1/3)
    aa,bb=(rs,rs) if shape=='sphere' else (a,b)
    U=cfg['fluid']['target_mean_interstitial_x_velocity_m_s']; horizon=cfg['observation']['horizon_pore_volumes']*L/U
    row=engine.integrate(field,geom,start['position_m'],start['orientation'],aa,bb,
        cfg['fluid']['dynamic_viscosity_Pa_s'],L,horizon,
        clearance_cutoff=cfg['observation']['near_wall_clearance_over_grain_radius_cutoff'],
        displacement_fraction=disp,angle_limit=cfg['numerics']['angle_limit_rad'],wall_budget=wall_budget)
    row.update({'id':start['id'],'shape':shape,'displacement_fraction':disp,'stratum':start['stratum']})
    return row

def counts(rows): return {s:sum(r['status']==s for r in rows) for s in sorted({r['status'] for r in rows})}
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--output',required=True); ap.add_argument('--mode',choices=['profile','pilot'],required=True); ap.add_argument('--profile-parent'); args=ap.parse_args()
    out=Path(args.output); out.mkdir(parents=True,exist_ok=False); cfg=json.loads(DESIGN.read_text())
    verify=json.loads(VERIFY.read_text());
    if not verify['passed']: raise RuntimeError('far-field implementation verification failed')
    if args.mode=='pilot':
        if not args.profile_parent: raise RuntimeError('pilot requires profile parent')
        parent=Path(args.profile_parent)/'results.json'; pd=json.loads(parent.read_text())
        if not pd.get('passed'): raise RuntimeError('profile gates did not pass')
    else: parent=None
    a,b,_=cfg['shapes']['prolate']['semiaxes_m']; rs=(a*b*b)**(1/3); cutoff=cfg['observation']['near_wall_clearance_over_grain_radius_cutoff']
    input_hashes={str(DESIGN.resolve()):sha(DESIGN),str(VERIFY.resolve()):sha(VERIFY),str(Path(__file__).resolve()):sha(__file__),str(Path(model.__file__).resolve()):sha(model.__file__),str(Path(engine.__file__).resolve()):sha(engine.__file__)}
    if parent: input_hashes[str(parent.resolve())]=sha(parent)
    datasets={}; allrows=[]; started=time.perf_counter(); profile_alloc={1:3,2:3,3:2}
    for seed,sobseed in zip(cfg['packings'],cfg['sampling']['seeds_by_packing']):
        field,geom,L,dx,mean,paths=load(seed,cfg)
        for p in paths: input_hashes[str(p.resolve())]=sha(p)
        ss=starts(field,geom,L,a,b,rs,64,sobseed,cutoff); (out/f'starts_s{seed}.json').write_text(json.dumps(ss,indent=2))
        selected=ss if args.mode=='pilot' else ss[:profile_alloc[seed]]
        disps=[cfg['numerics']['displacement_fractions'][-1]] if args.mode=='pilot' else cfg['numerics']['displacement_fractions']
        rows=[]
        for disp in disps:
            for shape in ('sphere','prolate'):
                for st in selected:
                    r=one(field,geom,L,cfg,st,shape,disp,120.0); r['packing_seed']=seed; rows.append(r); allrows.append(r)
        datasets[str(seed)]={'L_m':L,'dx_m':dx,'archived_mean_u_lu':mean,'selected_starts':len(selected),'rows':rows}
        (out/f'trajectories_s{seed}.json').write_text(json.dumps(rows,indent=2)); print(json.dumps({'packing':seed,'executions':len(rows),'counts':counts(rows),'elapsed_s':time.perf_counter()-started}),flush=True)
    statuses=set(r['status'] for r in allrows); numerical=sum(r['status']=='numerical_failure' for r in allrows); budgets=sum(r['status']=='incomplete_budget' for r in allrows)
    checks={'no_numerical_failure':numerical==0,'no_incomplete_budget':budgets==0,'inputs_unchanged':all(sha(Path(p))==h for p,h in input_hashes.items())}
    if args.mode=='profile':
        fine={(r['packing_seed'],r['shape'],r['id']):r['status'] for r in allrows if r['displacement_fraction']==0.05}
        medium={(r['packing_seed'],r['shape'],r['id']):r['status'] for r in allrows if r['displacement_fraction']==0.1}
        agreement=sum(fine[k]==medium[k] for k in fine)/len(fine); checks['fine_medium_status_agreement']=agreement>=cfg['acceptance']['fine_medium_status_agreement_fraction_min']; checks['exactly_16_unique_trajectories']=len(fine)==16
    else:
        agreement=None; checks['all_384_accounted']=len(allrows)==384; checks['parent_profile_bound']=True
    summary={}
    fine=[r for r in allrows if r['displacement_fraction']==0.05]
    for shape in ('sphere','prolate'):
        q=[r for r in fine if r['shape']==shape]; c=counts(q); n=len(q); unresolved=c.get('unresolved_near_wall',0)+c.get('unresolved_field',0)
        summary[shape]={'N':n,'counts':c,'release_lower_bound':c.get('full_window_exit',0)/n if n else None,'release_upper_bound':(c.get('full_window_exit',0)+unresolved)/n if n else None}
    result={'completed':True,'mode':args.mode,'passed':all(checks.values()),'checks':checks,'fine_medium_status_agreement':agreement,'summary':summary,'datasets':datasets,'runtime_seconds':time.perf_counter()-started,'input_hashes':input_hashes,'environment':{'python':platform.python_version(),'numpy':np.__version__},'physical_stage4_promoted':False,'claim_boundary':cfg['claim_boundary']}
    (out/'results.json').write_text(json.dumps(result,indent=2)); (out/'completion.json').write_text(json.dumps({'status':'complete_passed' if result['passed'] else 'complete_failed','results_sha256':sha(out/'results.json')},indent=2)); print(json.dumps({'passed':result['passed'],'checks':checks,'summary':summary,'runtime_s':result['runtime_seconds']}))
if __name__=='__main__': main()
