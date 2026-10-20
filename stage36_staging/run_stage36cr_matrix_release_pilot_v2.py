"""Corrected Stage36 matrix pilot: transpose stored [z,y,x] fields to [x,y,z]."""
from __future__ import annotations
import argparse,hashlib,json,platform,time
from pathlib import Path
import numpy as np
from scipy.ndimage import label,generate_binary_structure
from scipy.stats import qmc
import matrix_release_transport_v1 as mt
import run_stage36cp_matrix_release_pilot_v1 as old
R=Path(__file__).resolve().parents[1];FAIL=R/'stage36_runs/stage36cp_matrix_release_pilot_20260911/pilot_01/model_form_failure.json'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--output',required=True);ap.add_argument('--count',type=int,default=64);ap.add_argument('--max-displacements',default='.4,.2,.1');a0=ap.parse_args();O=Path(a0.output);O.mkdir(parents=True,exist_ok=False);assert json.loads(FAIL.read_text())['accepted'] is False
 disps=[float(v) for v in a0.max_displacements.split(',')];zf=np.load(old.FIELD);zg=np.load(old.GEOM);phase=np.asarray(zf['phase']).transpose(2,1,0);geom_phase=np.asarray(zg['phase']).transpose(2,1,0);u=np.asarray(zf['velocity_xyz_lu'],float).transpose(0,3,2,1);L=float(phase.shape[0]);dx=float(zg['spacing_m'][0]);assert np.array_equal(phase,geom_phase) and phase.shape==(186,186,186) and json.loads(old.VERIFY.read_text())['passed']
 grad=mt.periodic_gradient(u);fluid=phase==0;lab,nlab=label(fluid,generate_binary_structure(3,1));cnt=np.bincount(lab.ravel());main_id=int(np.argmax(cnt[1:])+1);main=lab==main_id;centres=np.asarray(zg['sand_centres_m'])/dx;radii=np.asarray(zg['sand_radii_m'])/dx;gr=mt.PeriodicGrains(centres,radii,L);aa=.0002/dx;bb=.00005/dx;rs=(.0002*.00005*.00005)**(1/3)/dx;mean=float(u[0,fluid].mean());pt=L/mean
 # Coordinate audit: sampled grain centres must be solid in transposed phase.
 grain_solid=[]
 for c in centres:
  idx=np.floor(np.mod(c,L)).astype(int);grain_solid.append(bool(phase[tuple(idx)]!=0))
 config={'schema':'stage36cr.matrix-release-pilot.v2','status':'resolved','supersedes_invalid_run':str(FAIL),'axis_mapping':{'stored_spatial':'zyx','working_spatial':'xyz','velocity_components':'xyz'},'count_per_shape':a0.count,'max_displacements_cells':disps,'horizon_pore_volumes':7.,'seed':3601,'particle':{'prolate_semi_axes_m':[.0002,.00005,.00005],'prolate_aspect_ratio':4.,'equal_volume_sphere_radius_m':rs*dx,'prolate_axes_cells':[aa,bb,bb],'sphere_radius_cells':rs,'initial_margin_cells_min':.25},'sampling':{'scrambled_sobol':True,'streamwise_bins':3,'clearance_bins':3,'common_centres':True},'gates':{'all_grain_centres_solid':True,'release_bound_shift_max':.02,'median_release_time_relative_shift_max':.01,'deterministic_repeat_exact':True,'mass_accounting_exact':True,'no_numerical_failure':True},'claim_boundary':'one-way fixed-field screening; conservative interception unresolved, not retained; no validation claim'};(O/'resolved_config.json').write_text(json.dumps(config,indent=2));inputs=[Path(__file__),Path(mt.__file__),Path(old.__file__),old.FIELD,old.GEOM,old.DESIGN,old.VERIFY,FAIL,O/'resolved_config.json'];before={str(p):sha(p) for p in inputs}
 sob=qmc.Sobol(5,scramble=True,seed=3601).random_base2(16);cand=[]
 for row in sob:
  pos=row[:3]*L;ct=2*row[3]-1;phi=2*np.pi*row[4];p=np.array([np.sqrt(max(0,1-ct*ct))*np.cos(phi),np.sqrt(max(0,1-ct*ct))*np.sin(phi),ct]);idx=np.floor(pos).astype(int)%int(L)
  if not main[tuple(idx)]:continue
  sx=old.support_x(p,aa,bb)
  if pos[0]-sx<0 or pos[0]+sx>L:continue
  margin=gr.margin(pos,p,aa,bb)
  if margin<.25 or gr.margin(pos,p,rs,rs)<.25:continue
  cand.append({'position':pos,'orientation':p,'clearance':gr.margin(pos,[1,0,0],0,0),'margin':margin})
  if len(cand)>=4096:break
 if len(cand)<a0.count*4:raise RuntimeError('insufficient candidate pool')
 qs=np.quantile([c['clearance'] for c in cand],[1/3,2/3]);groups={(i,j):[] for i in range(3) for j in range(3)}
 for c in cand:
  xb=min(2,int(3*c['position'][0]/L));cb=int(c['clearance']>qs[0])+int(c['clearance']>qs[1]);groups[(xb,cb)].append(c)
 quota={k:a0.count//9+(i<a0.count%9) for i,k in enumerate(sorted(groups))};sel=[]
 for k in sorted(groups):
  if len(groups[k])<quota[k]:raise RuntimeError(f'insufficient stratum {k}')
  for c in groups[k][:quota[k]]:c['stratum']=list(k);sel.append(c)
 starts=[{'id':i,'position_cells':c['position'].tolist(),'orientation':c['orientation'].tolist(),'centre_clearance_cells':float(c['clearance']),'prolate_margin_cells':float(c['margin']),'stratum':c['stratum']} for i,c in enumerate(sel)];(O/'initial_ensemble.json').write_text(json.dumps(starts,indent=2));runs={};started=time.perf_counter()
 for md in disps:
  rows=[]
  for shape in ('sphere','prolate'):
   x1,x2,ar=(rs,rs,1.) if shape=='sphere' else (aa,bb,4.)
   for st in starts:
    ans=old.integrate(u,grad,gr,st['position_cells'],st['orientation'],x1,x2,ar,md,pt,7.,L);ans.update({'id':st['id'],'shape':shape,'max_displacement_cells':md,'stratum':st['stratum']});rows.append(ans)
  runs[str(md)]=rows;(O/f'trajectories_dx_{str(md).replace(".","p")}.json').write_text(json.dumps(rows,indent=2));print(json.dumps({'dx':md,'counts':{s:sum(r['status']==s for r in rows) for s in sorted(set(r['status'] for r in rows))}}),flush=True)
 def summ(rows,shape):
  q=[r for r in rows if r['shape']==shape];n=len(q);rel=sum(r['status']=='released' for r in q);unr=sum(r['status'] in ('interception_unresolved','upstream_exit_unresolved') for r in q);still=sum(r['status']=='still_present_horizon' for r in q);ts=[r['time_pv'] for r in q if r['status']=='released'];return {'n':n,'released':rel,'interception_or_exit_unresolved':unr,'still_present_horizon':still,'release_lower':rel/n,'release_upper':(rel+unr)/n,'median_release_time_pv':float(np.median(ts)) if ts else None}
 fine=runs[str(disps[-1])];med=runs[str(disps[-2])] if len(disps)>1 else fine;sf={s:summ(fine,s) for s in ('sphere','prolate')};sm={s:summ(med,s) for s in sf};bs=max(max(abs(sf[s][k]-sm[s][k]) for k in ('release_lower','release_upper')) for s in sf);ts=max(abs(sf[s]['median_release_time_pv']-sm[s]['median_release_time_pv'])/sf[s]['median_release_time_pv'] if sf[s]['median_release_time_pv'] else 0 for s in sf);rep=[]
 for r in fine[:4]:
  st=starts[r['id']];x1,x2,ar=(rs,rs,1.) if r['shape']=='sphere' else (aa,bb,4.);q=old.integrate(u,grad,gr,st['position_cells'],st['orientation'],x1,x2,ar,disps[-1],pt,7.,L);rep.append(q['status']==r['status'] and q['time_pv']==r['time_pv'] and q['final_position_cells']==r['final_position_cells'])
 checks={'all_grain_centres_solid':all(grain_solid),'initial_count_each_shape':len(starts)==a0.count,'all_initial_margins':all(s['prolate_margin_cells']>=.25 for s in starts),'nine_strata':len({tuple(s['stratum']) for s in starts})==9,'mass_accounting':all(sum(sf[s][k] for k in ('released','interception_or_exit_unresolved','still_present_horizon'))==a0.count for s in sf),'release_bound_timestep':bs<=.02,'release_time_timestep':ts<=.01,'deterministic_repeat':all(rep),'no_numerical_failure':all(r['status']!='numerical_failure' for r in fine),'inputs_unchanged':before=={str(p):sha(p) for p in inputs}}
 result={'passed':all(checks.values()),'checks':checks,'summary_fine':sf,'summary_medium':sm,'numerical':{'release_bound_max_shift':bs,'median_release_time_max_relative_shift':ts,'pore_time_lu':pt,'mean_pore_velocity_lu':mean,'candidate_pool':len(cand),'main_fluid_fraction':float(main.sum()/fluid.sum())},'runtime_seconds':time.perf_counter()-started,'input_hashes':before,'environment':{'python':platform.python_version(),'numpy':np.__version__}};(O/'results.json').write_text(json.dumps(result,indent=2));(O/'completion.json').write_text(json.dumps({'status':'complete' if result['passed'] else 'failed_gates','results_sha256':sha(O/'results.json')},indent=2));print(json.dumps(result),flush=True)
if __name__=='__main__':main()
