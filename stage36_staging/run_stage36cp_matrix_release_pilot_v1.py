"""One-way resident-particle release pilot in the frozen Stage27b clean field."""
from __future__ import annotations
import argparse,hashlib,json,platform,time
from pathlib import Path
import numpy as np
from scipy.ndimage import label,generate_binary_structure
from scipy.stats import qmc
import matrix_release_transport_v1 as mt

ROOT=Path(__file__).resolve().parents[1]
FIELD=ROOT/'stage27_runs/stage27b_stage26x_mechanics_hydraulic_cpd4_20260824/gpu_confirmation_01/stage27b_clean_cpd4/final_fields.npz'
GEOM=ROOT/'stage27_designs/stage27b_stage26x_mechanics_hydraulic_cpd4_20260824/geometry_01/clean/geometry_cpd4.npz'
DESIGN=ROOT/'stage36_evaluations/stage36cn_matrix_release_design_20260911/design_01/design.json'
VERIFY=ROOT/'stage36_evaluations/stage36co_matrix_transport_verification_20260911/test_02/results.json'

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def support_x(p,a,b):return mt.ellipsoid_support([1,0,0],p,a,b)

def integrate(u,grad,grains,pos0,p0,a,b,ar,max_disp,pore_time,horizon_pv,L,trace_stride=25):
    pos=np.array(pos0,float);p=np.array(p0,float);t=0.;steps=0;trace=[];horizon=horizon_pv*pore_time;min_margin=np.inf
    while t<horizon and steps<200000:
        margin=grains.margin(pos,p,a,b);min_margin=min(min_margin,margin)
        if margin<=0:return {'status':'interception_unresolved','time_pv':t/pore_time,'steps':steps,'min_margin_cells':float(min_margin),'final_position_cells':pos.tolist(),'final_orientation':p.tolist(),'trace':trace}
        v=mt.trilinear(u,pos);g=mt.trilinear(grad,pos);speed=float(np.linalg.norm(v))
        if not np.isfinite(speed) or speed<=1e-15:return {'status':'still_present_horizon','time_pv':horizon_pv,'steps':steps,'min_margin_cells':float(min_margin),'final_position_cells':pos.tolist(),'final_orientation':p.tolist(),'trace':trace,'reason':'stagnant_or_invalid_velocity'}
        dt=min(max_disp/speed,.02*pore_time,horizon-t);pm=mt.advance_orientation(p,g,ar,.5*dt) if ar>1 else p
        mid=pos+.5*dt*v;mid[1:]=np.mod(mid[1:],L);vm=mt.trilinear(u,mid);gm=mt.trilinear(grad,mid);new=pos+dt*vm;new[1:]=np.mod(new[1:],L);pn=mt.advance_orientation(p,gm,ar,dt) if ar>1 else p
        mm=grains.margin(mid,pm,a,b);mn=grains.margin(new,pn,a,b) if new[0]<L else np.inf;min_margin=min(min_margin,mm,mn);steps+=1
        if steps%trace_stride==0:trace.append([float(t/pore_time),*map(float,pos),*map(float,p)])
        if mm<=0 or mn<=0:return {'status':'interception_unresolved','time_pv':float((t+dt)/pore_time),'steps':steps,'min_margin_cells':float(min_margin),'final_position_cells':new.tolist(),'final_orientation':pn.tolist(),'trace':trace}
        if new[0]>=L:
            frac=float(np.clip((L-pos[0])/(new[0]-pos[0]),0,1));tc=t+frac*dt;pc=p+(pn-p)*frac;pc/=np.linalg.norm(pc);extra=support_x(pc,a,b)/(L/pore_time);te=tc+extra
            status='released' if te<=horizon else 'still_present_horizon'
            return {'status':status,'time_pv':float(min(te,horizon)/pore_time),'steps':steps,'min_margin_cells':float(min_margin),'final_position_cells':new.tolist(),'final_orientation':pc.tolist(),'trace':trace}
        if new[0]+support_x(pn,a,b)<0:return {'status':'upstream_exit_unresolved','time_pv':float((t+dt)/pore_time),'steps':steps,'min_margin_cells':float(min_margin),'final_position_cells':new.tolist(),'final_orientation':pn.tolist(),'trace':trace}
        pos,p,t=new,pn,t+dt
    return {'status':'still_present_horizon' if steps<200000 else 'numerical_failure','time_pv':float(min(t,horizon)/pore_time),'steps':steps,'min_margin_cells':float(min_margin),'final_position_cells':pos.tolist(),'final_orientation':p.tolist(),'trace':trace}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output',required=True);ap.add_argument('--count',type=int,default=64);ap.add_argument('--max-displacements',default='.4,.2,.1');args=ap.parse_args();O=Path(args.output);O.mkdir(parents=True,exist_ok=False)
    if args.count<18:raise ValueError('count must be >=18 for crossed strata')
    disps=[float(x) for x in args.max_displacements.split(',')];z=np.load(FIELD);g=np.load(GEOM);u=np.asarray(z['velocity_xyz_lu'],float);phase=np.asarray(z['phase']);L=float(phase.shape[0]);dx=float(g['spacing_m'][0]);assert phase.shape==(186,186,186) and np.array_equal(phase,g['phase']);assert json.loads(VERIFY.read_text())['passed']
    grad=mt.periodic_gradient(u);fluid=phase==0;lab,nlab=label(fluid,generate_binary_structure(3,1));counts=np.bincount(lab.ravel());main_label=int(np.argmax(counts[1:])+1);main=lab==main_label
    centres=np.asarray(g['sand_centres_m'])/dx;radii=np.asarray(g['sand_radii_m'])/dx;grains=mt.PeriodicGrains(centres,radii,L)
    a=.0002/dx;b=.00005/dx;rs=(.0002*.00005*.00005)**(1/3)/dx;mean_pore=float(u[0,fluid].mean());pore_time=L/mean_pore
    resolved={'schema':'stage36cp.matrix-release-pilot.v1','status':'resolved','supersedes':str(DESIGN),'reason_for_revision':'specified missing dimensions and replaced invalid random-packing symmetry gate','count_per_shape':args.count,'max_displacements_cells':disps,'horizon_pore_volumes':7.,'seed':3601,'field_axis':'x','particle':{'prolate_semi_axes_m':[.0002,.00005,.00005],'prolate_aspect_ratio':4.,'equal_volume_sphere_radius_m':rs*dx,'prolate_axes_cells':[a,b,b],'sphere_radius_cells':rs,'initial_margin_cells_min':.25},'sampling':{'method':'scrambled Sobol','streamwise_bins':3,'clearance_bins':3,'common_centres':True},'gates':{'release_bound_shift_max':.02,'median_release_time_relative_shift_max':.01,'deterministic_repeat_exact':True,'mass_accounting_exact':True,'no_numerical_failure':True},'claim_boundary':'one-way fixed-field screening; interception is unresolved, not retained; no calibration or validation claim'}
    (O/'resolved_config.json').write_text(json.dumps(resolved,indent=2));inputs=[Path(__file__),Path(mt.__file__),FIELD,GEOM,DESIGN,VERIFY,O/'resolved_config.json'];before={str(p):sha(p) for p in inputs}
    sob=qmc.Sobol(5,scramble=True,seed=3601).random_base2(16);candidates=[]
    for row in sob:
        pos=row[:3]*L;ct=2*row[3]-1;phi=2*np.pi*row[4];p=np.array([np.sqrt(max(0,1-ct*ct))*np.cos(phi),np.sqrt(max(0,1-ct*ct))*np.sin(phi),ct]);idx=np.floor(pos).astype(int)%int(L)
        if not main[tuple(idx)]:continue
        sx=support_x(p,a,b)
        if pos[0]-sx<0 or pos[0]+sx>L:continue
        margin=grains.margin(pos,p,a,b)
        if margin<.25 or grains.margin(pos,p,rs,rs)<.25:continue
        clear=grains.margin(pos,[1,0,0],0,0);candidates.append({'position':pos,'orientation':p,'clearance':clear,'margin':margin})
        if len(candidates)>=4096:break
    if len(candidates)<args.count*4:raise RuntimeError('insufficient admissible candidate pool')
    qs=np.quantile([c['clearance'] for c in candidates],[1/3,2/3]);groups={(i,j):[] for i in range(3) for j in range(3)}
    for c in candidates:
        xb=min(2,int(3*c['position'][0]/L));cb=int(c['clearance']>qs[0])+int(c['clearance']>qs[1]);groups[(xb,cb)].append(c)
    quota={k:args.count//9+(i<args.count%9) for i,k in enumerate(sorted(groups))};selected=[]
    for k in sorted(groups):
        if len(groups[k])<quota[k]:raise RuntimeError(f'insufficient stratum {k}')
        for c in groups[k][:quota[k]]:c['stratum']=list(k);selected.append(c)
    starts=[{'id':i,'position_cells':c['position'].tolist(),'orientation':c['orientation'].tolist(),'centre_clearance_cells':float(c['clearance']),'prolate_margin_cells':float(c['margin']),'stratum':c['stratum']} for i,c in enumerate(selected)];(O/'initial_ensemble.json').write_text(json.dumps(starts,indent=2))
    all_runs={};started=time.perf_counter()
    for md in disps:
        rows=[]
        for shape in ('sphere','prolate'):
            aa,bb,ar=(rs,rs,1.) if shape=='sphere' else (a,b,4.)
            for st in starts:
                ans=integrate(u,grad,grains,st['position_cells'],st['orientation'],aa,bb,ar,md,pore_time,7.,L);ans.update({'id':st['id'],'shape':shape,'max_displacement_cells':md,'stratum':st['stratum']});rows.append(ans)
        all_runs[str(md)]=rows;(O/f'trajectories_dx_{str(md).replace(".","p")}.json').write_text(json.dumps(rows,indent=2));print(json.dumps({'max_displacement':md,'status_counts':{s:sum(r['status']==s for r in rows) for s in sorted(set(r['status'] for r in rows))}}),flush=True)
    fine=all_runs[str(disps[-1])];medium=all_runs[str(disps[-2])] if len(disps)>=2 else fine
    def summarize(rows,shape):
        a0=[r for r in rows if r['shape']==shape];n=len(a0);rel=sum(r['status']=='released' for r in a0);unr=sum(r['status'] in ('interception_unresolved','upstream_exit_unresolved') for r in a0);still=sum(r['status']=='still_present_horizon' for r in a0);times=[r['time_pv'] for r in a0 if r['status']=='released'];return {'n':n,'released':rel,'interception_or_exit_unresolved':unr,'still_present_horizon':still,'release_lower':rel/n,'release_upper':(rel+unr)/n,'median_release_time_pv':float(np.median(times)) if times else None}
    sf={s:summarize(fine,s) for s in ('sphere','prolate')};sm={s:summarize(medium,s) for s in ('sphere','prolate')}
    bound_shift=max(max(abs(sf[s][k]-sm[s][k]) for k in ('release_lower','release_upper')) for s in sf);time_shift=max(abs(sf[s]['median_release_time_pv']-sm[s]['median_release_time_pv'])/sf[s]['median_release_time_pv'] if sf[s]['median_release_time_pv'] else 0 for s in sf)
    repeats=[]
    for r in fine[:4]:
        st=starts[r['id']];aa,bb,ar=(rs,rs,1.) if r['shape']=='sphere' else (a,b,4.);q=integrate(u,grad,grains,st['position_cells'],st['orientation'],aa,bb,ar,disps[-1],pore_time,7.,L);repeats.append(q['status']==r['status'] and q['time_pv']==r['time_pv'] and q['final_position_cells']==r['final_position_cells'])
    statuses=[r['status'] for r in fine];checks={'initial_count_each_shape':len(starts)==args.count,'all_initial_margins':all(s['prolate_margin_cells']>=.25 for s in starts),'nine_strata':len({tuple(s['stratum']) for s in starts})==9,'mass_accounting':all(sum(sf[s][k] for k in ('released','interception_or_exit_unresolved','still_present_horizon'))==args.count for s in sf),'release_bound_timestep':bound_shift<=.02,'release_time_timestep':time_shift<=.01,'deterministic_repeat':all(repeats),'no_numerical_failure':'numerical_failure' not in statuses,'inputs_unchanged':before=={str(p):sha(p) for p in inputs}}
    result={'passed':all(checks.values()),'checks':checks,'summary_fine':sf,'summary_medium':sm,'numerical':{'release_bound_max_shift':bound_shift,'median_release_time_max_relative_shift':time_shift,'pore_time_lu':pore_time,'mean_pore_velocity_lu':mean_pore,'candidate_pool':len(candidates),'main_fluid_fraction':float(main.sum()/fluid.sum())},'runtime_seconds':time.perf_counter()-started,'input_hashes':before,'environment':{'python':platform.python_version(),'numpy':np.__version__}}
    (O/'results.json').write_text(json.dumps(result,indent=2));(O/'completion.json').write_text(json.dumps({'status':'complete' if result['passed'] else 'failed_gates','results_sha256':sha(O/'results.json')},indent=2));print(json.dumps(result),flush=True)
if __name__=='__main__':main()
