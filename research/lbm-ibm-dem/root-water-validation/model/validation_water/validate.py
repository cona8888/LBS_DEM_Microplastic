"""Validation harness for the actual RhizoField equilibrium water application.
Run from repository root with python -m validation_water.validate TASK.
No calibration function is called: saved parameter profiles are immutable inputs.
"""
from __future__ import annotations
import argparse,csv,hashlib,json,math,platform,time
from dataclasses import asdict
from pathlib import Path
import numpy as np
from scipy.optimize import least_squares,brentq
from scipy.stats import t as student_t
from applications.rhizofield.field import Mesh,seed,DX,P0,GAMMA
from applications.rhizofield.run import Params,paired,writecsv,uptake_rate,connected
from applications.rhizofield.refine import refined_geometry
ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/'validation_water/results'
PROFILE=ROOT/'calibration/results/profiles.json'

def check_frozen():
    entries=json.loads((ROOT/'validation_water/FROZEN_INPUTS.json').read_text())
    for filename,expected in entries.items():
        if hashlib.sha256((ROOT/filename).read_bytes()).hexdigest()!=expected:
            raise RuntimeError(f'Frozen calibration/input changed: {filename}')

def dump(name,value):
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/name).write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')

def loadcsv(path):
    with Path(path).open() as f:return list(csv.DictReader(f))

def geometry(scale,x=None):
    lab,guess=seed();x=guess if x is None else x
    if scale==2:return refined_geometry(lab,x)
    return lab,x

def arc(m,s,trim=1.):
    z=m.map(s.phi);y=(np.arange(z.shape[0])+.5)*m.hy-.5
    delta=m.cx[67*m.scale] - ((67*m.scale+.5)*m.hy-.5)
    c0=np.array([28.,33.]);c1=np.array([67.+delta,33.]);pts=[]
    for j,x in enumerate(m.cx):
        if not 40<x<c1[0]+1:continue
        col=z[:,j];hit=np.where((y[:-1]>=33)&(col[:-1]>=0)&(col[1:]<0))[0]
        if len(hit)!=1:continue
        i=hit[0];p=np.array([x,y[i]+m.hy*col[i]/(col[i]-col[i+1])])
        if min(np.linalg.norm(p-c0)-20,np.linalg.norm(p-c1)-7)>=trim:pts.append(p)
    a=np.asarray(pts)
    if len(a)<7:raise ValueError('Too few interface points')
    mid=a.mean(axis=0);res=lambda t:np.linalg.norm(a-t[:2],axis=1)-t[2]
    fit=least_squares(res,[mid[0],mid[1]+20,20],bounds=([-300,mid[1],.1],[300,2000,2000]))
    R=fit.x[2];return dict(n_points=len(a),R_m=R*DX,arc_rms_m=float(np.sqrt(np.mean(res(fit.x)**2))*DX),laplace_suction_Pa=GAMMA/(R*DX))

def inspect(m,s):
    f=np.array([m.contour(s,k,1) for k in (2,3,4,5)])
    r=np.array([m.contour(s,k,2) for k in (2,3,4,5)])
    a=arc(m,s)
    bulk=np.sort(np.roots([1.,0.,-1.,-s.mu]).real);pg,pl=bulk[0],bulk[-1]
    # Diagnostic only: no clipping or replacement of the model's conserved variable.
    branch_area=float(m.V@((s.phi-pg)/(pl-pg))*DX**2)
    return dict(force_N_m=s.force,contour_force_N_m=float(f.mean()),contour_spread_pct=float(np.ptp(f)/abs(s.force)*100),force_discrepancy_pct=float(abs(f.mean()-s.force)/abs(s.force)*100),pair_force_imbalance_pct=float(abs(f.mean()+r.mean())/abs(s.force)*100),suction_Pa=-s.psi,phase_inventory_m2=s.water*DX**2,bulk_branch_liquid_area_m2=branch_area,inventory_difference_pct=float(100*(branch_area/(s.water*DX**2)-1)),phi_min=float(s.phi.min()),phi_max=float(s.phi.max()),wet_length_m=s.wet_length,mu_residual=s.residual,connected=bool(connected(m,s)),laplace_error_pct=float(abs(a['laplace_suction_Pa']/(-s.psi)-1)*100),**a)

def field():
    p=json.loads(PROFILE.read_text());theta=p['grain_wall_inputs_deg']['25um'];lab,x=seed();A=Mesh(lab).water(x)
    rows=[]
    for scale in (1,2):
        labels,guess=geometry(scale,x)
        for gap in (12.,13.55):
            for amount in (1.,.85):
                m=Mesh(labels,gap,grain_deg=theta);s=m.solve(guess,A*amount)
                row=dict(scale=scale,gap_m=gap*DX,inventory_fraction=amount,grain_input_deg=theta,**inspect(m,s))
                h=.003
                sm=Mesh(labels,gap-h,grain_deg=theta).solve(s.phi,s.water)
                sp=Mesh(labels,gap+h,grain_deg=theta).solve(s.phi,s.water)
                fd=-(sp.energy-sm.energy)/(2*h)*P0*DX
                row.update(virtual_work_force_N_m=fd,virtual_work_error_pct=abs(fd/s.force-1)*100)
                rows.append(row);writecsv(OUT/'field_checks.csv',rows);print(row,flush=True)
    dump('field_summary.json',dict(frozen_angle_deg=theta,max_laplace_error_pct=max(r['laplace_error_pct'] for r in rows),max_virtual_work_error_pct=max(r['virtual_work_error_pct'] for r in rows),max_contour_discrepancy_pct=max(r['force_discrepancy_pct'] for r in rows),rows=len(rows)))

def hydraulics():
    from legacy.root_v01.hydraulics import Soil,RootCase,RadialRichards,continuum_steady,simulate
    case=RootCase();soil=Soil();rows=[]
    for cells in (16,32,64,128):
        m=RadialRichards(cells,case,soil);h,q=m.solve(np.full(cells,case.bulk_head_m));exact,Q,hs=continuum_steady(m.r,case,soil)
        rows.append(dict(cells=cells,Q_numeric_m2_s=float(q[0]),Q_exact_m2_s=float(Q),flow_error_pct=float(abs(q[0]/Q-1)*100),head_max_error_m=float(np.max(abs(h-exact))),flux_range_relative=float(np.ptp(q)/abs(Q))))
    writecsv(OUT/'radial_steady.csv',rows)
    summaries=[]
    for dt in (240.,120.,60.):
        m=RadialRichards(64,case,soil);hist,profiles=simulate(m,hours=2,dt_s=dt,profile_times_s=[0,1800,3600,7200])
        np.savetxt(OUT/f'radial_history_{int(dt)}s.csv',hist,delimiter=',',header='t_s,root_head_m,Qroot_m2_s,Qbulk_m2_s,storage_m2,uptake_m2,supply_m2,residual_m2',comments='')
        np.savetxt(OUT/f'radial_profiles_{int(dt)}s.csv',profiles,delimiter=',',header='t_s,r_m,head_m,suction_kPa,theta',comments='')
        hh=np.asarray(hist);summaries.append(dict(dt_s=dt,cumulative_uptake_m2=float(hh[-1,5]),max_mass_residual_m2=float(np.max(abs(hh[:,-1]))),root_head_final_m=float(hh[-1,1])))
    writecsv(OUT/'radial_transient.csv',summaries);dump('radial_inputs.json',dict(soil=asdict(soil),root=asdict(case),scope='separate continuum verification; NOT experimental validation or LBM coupling'))
    print(rows,summaries,flush=True)

def holdouts():
    profiles=json.loads(PROFILE.read_text());lp=profiles['ceramic']['lateral']['Lp_apparent_m_Pa_s'];area_small=math.pi*.0025*.01
    # Table 3 of Kohne2005, N=5. SD values are among replicate cups, not SE.
    table=loadcsv(ROOT/'validation_water/data/ceramic_table3.csv')
    data=[(r['size'],*[float(r[k]) for k in ('diameter_mm','length_mm','saturation_pct','applied_vacuum_bar','observation_cm3','replicate_sd_cm3')],0.,0.) for r in table]
    rows=[]
    for size,d,L,sat,vac,obs,sd,obs_t,sd_t in data:
        a=math.pi*d*1e-3*L*1e-3;ratio=a/area_small
        pred=uptake_rate(lp,a,0,-vac*1e5)*1200*1e6
        se=math.sqrt((ratio*(vac/.1)*.3)**2+sd*sd)/math.sqrt(5)
        pvar=(ratio*(vac/.1)*.3)**2/5;ovar=sd**2/5
        df=(pvar+ovar)**2/(pvar*pvar/4+ovar*ovar/4);ci=student_t.ppf(.975,df)*se
        role='calibration_not_validation' if size=='small' and sat==100 else ('heldout_geometry' if sat==100 else 'out_of_domain_challenge_bulk_pressure_unknown')
        rows.append(dict(size=size,diameter_mm=d,length_mm=L,saturation_pct=sat,applied_vacuum_bar=vac,observation_cm3=obs,replicate_sd_cm3=sd,n=5,prediction_cm3=pred,error_pct=100*(pred/obs-1),residual_cm3=pred-obs,residual_CI95_halfwidth_cm3=ci if role=='heldout_geometry' else None,role=role,passes_10pct_gate=bool(abs(pred/obs-1)<.1) if role=='heldout_geometry' else None))
    writecsv(OUT/'ceramic_frozen_predictions.csv',rows)
    # Independent geometry-transfer challenge at each saturation; NOT frozen saturated-fit validation.
    transfer=[]
    for sat in (100,85,70):
        a=next(d for d in data if d[0]=='small' and d[3]==sat);b=next(d for d in data if d[0]=='large' and d[3]==sat)
        ratio=(b[1]*b[2])/(a[1]*a[2]);pred=a[5]*ratio
        transfer.append(dict(saturation_pct=sat,area_ratio=ratio,small_observed_cm3=a[5],large_observed_cm3=b[5],conditional_large_predicted_cm3=pred,error_pct=100*(pred/b[5]-1),basis='conditioned on same-saturation small cup; not new universal fit'))
    writecsv(OUT/'ceramic_geometry_transfer.csv',transfer)
    raw=loadcsv(ROOT/'calibration/data/tree_table_II.csv');tree=[]
    for sp in profiles['trees']:
        ob=next(r for r in raw if r['species']==sp['species'] and r['split']=='holdout');obs=float(ob['Lp_1e_minus8_m_s_MPa'])*1e-14;pred=sp['Lp_fit_m_Pa_s']
        tree.append(dict(species=sp['species'],heldout_date=ob['date'],predicted_Lp_m_Pa_s=pred,observed_Lp_m_Pa_s=obs,observed_group_SD_m_Pa_s=float(ob['sd_1e_minus8_m_s_MPa'])*1e-14,error_pct=100*(pred/obs-1),passes_20pct_gate=bool(abs(pred/obs-1)<.2),evidence='chronological heldout date; same site, not independent site'))
    writecsv(OUT/'tree_frozen_holdouts.csv',tree)
    dump('holdout_summary.json',dict(ceramic_frozen_Lp_m_Pa_s=lp,calibration='one saturated small-cup observation only, no refit',profile_sha256=hashlib.sha256(PROFILE.read_bytes()).hexdigest(),saturated_large=rows[1],tree_holdouts=tree,notes='CI on difference of estimated means uses training SD and holdout SD and Welch approximation; geometry and pressure uncertainty omitted. Unsaturated bulk pressure zero is an explicit challenge, not a calibrated soil law.'))
    print(rows[1],tree,flush=True)

def pair(scale,steps,nopen):
    profiles=json.loads(PROFILE.read_text());theta=profiles['grain_wall_inputs_deg']['25um']
    p=Params(grain_deg=theta);tic=time.perf_counter();rows,maps=paired(steps,nopen,p,scale)
    tag=f'paired_s{scale}_n{steps}';writecsv(OUT/f'{tag}.csv',rows)
    summary=dict(scale=scale,steps=steps,nopen=nopen,parameters=asdict(p),seconds=time.perf_counter()-tic,max_water_residual_m2=max(abs(r['net_water_residual_m2']) for r in rows),max_force_residual_N_m=max(abs(r['force_residual_N_m']) for r in rows),fixed_gap=[])
    lab,x=geometry(scale)
    for mode,stage,a in maps:
        if stage!='opened':continue
        last=[r for r in rows if r['mode']==mode][-1]
        m=Mesh(lab,13.55,grain_deg=theta);s=m.solve(a[a[:,2]==0,3],last['near_water_m2']/DX**2)
        summary['fixed_gap'].append(dict(mode=mode,near_area_m2=last['near_water_m2'],far_area_m2=last['outer_water_m2'],uptake_m2=last['uptake_m2'],outer_drain_m2=last['outer_drain_m2'],**inspect(m,s)))
        np.savez_compressed(OUT/f'{tag}_{mode}.npz',phi=s.phi,near=last['near_water_m2'],far=last['outer_water_m2'],gap=13.55,labels=lab)
    a,b=summary['fixed_gap'][:2];summary['fixed_gap_contrast_pct']=100*(a['force_N_m']/b['force_N_m']-1)
    summary['extracted_difference_m2']=abs(a['uptake_m2']-b['outer_drain_m2'])
    dump(f'{tag}.json',summary);print(summary,flush=True)

if __name__=='__main__':
    check_frozen()
    OUT.mkdir(exist_ok=True,parents=True);ap=argparse.ArgumentParser();ap.add_argument('task',choices=['field','hydraulics','holdouts','pair']);ap.add_argument('--scale',type=int,default=1);ap.add_argument('--steps',type=int,default=18);ap.add_argument('--nopen',type=int,default=9);a=ap.parse_args()
    if a.task=='pair':pair(a.scale,a.steps,a.nopen)
    else:globals()[a.task]()
