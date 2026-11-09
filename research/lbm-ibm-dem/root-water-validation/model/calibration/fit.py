"""Fit independent components against transcribed measurements, excluding held-out rows.
Run from repository root: make calibrate. No external network access needed.
"""
from pathlib import Path
from functools import lru_cache
import csv,json,math,statistics as st
from scipy.optimize import brentq
from .probe_wetting import apparent,state
from applications.rhizofield.run import uptake_rate,writecsv
HERE=Path(__file__).resolve().parent

def rows(name):
    with (HERE/'data'/name).open(newline='') as f:return list(csv.DictReader(f))

def cup_area(row,tip=False):
    d,L=float(row['diameter_mm'])*1e-3,float(row['length_mm'])*1e-3
    return math.pi*d*L+bool(tip)*math.pi*d*d/4

def cup_fit():
    data=rows('ceramic_cups.csv'); train=next(r for r in data if r['role']=='train'); test=next(r for r in data if r['role']=='holdout_geometry')
    out={};dt=float(train['time_min'])*60;dP=float(train['vacuum_bar'])*1e5
    for tip,name in [(False,'lateral'),(True,'one_end_plus_lateral')]:
        lp=float(train['volume_cm3'])*1e-6/(dt*cup_area(train,tip)*dP)
        v=uptake_rate(lp,cup_area(test,tip),0,-float(test['vacuum_bar'])*1e5)*float(test['time_min'])*60*1e6
        out[name]=dict(Lp_apparent_m_Pa_s=lp,large_pred_cm3=v,large_obs_cm3=float(test['volume_cm3']),error_percent=100*(v/float(test['volume_cm3'])-1))
    time_checks=[]
    for sat in [100,85,70]:
        group=[r for r in data if r['endpoint']=='fixed_volume' and float(r['saturation_pct'])==sat]; small,large=[next(r for r in group if r['size']==n) for n in ['small','large']]
        t1,t2=float(small['time_min']),float(large['time_min']); tp=t1*cup_area(small)/cup_area(large)
        time_checks.append(dict(saturation_pct=sat,vacuum_bar=float(small['vacuum_bar']),observed_small_min=t1,observed_large_min=t2,area_transfer_large_min=tp,error_percent=100*(tp/t2-1)))
    return out,time_checks

def trees():
    data=rows('tree_table_II.csv'); species=sorted({r['species'] for r in data});out=[];points=[]
    for sp in species:
        g=[r for r in data if r['species']==sp and r['split']!='missing']; v=lambda r:float(r['Lp_1e_minus8_m_s_MPa'])*1e-14
        a=[v(r) for r in g if r['split']=='train']; L=st.mean(a);r=next(r for r in g if r['split']=='holdout');obs=v(r)
        lo=[st.mean([v(k) for k in g if k['date']!=j['date']]) for j in g]; cv_rmse=math.sqrt(st.mean([(e-v(j))**2 for e,j in zip(lo,g)]))
        out.append(dict(species=sp,n_train_dates=len(a),Lp_fit_m_Pa_s=L,holdout_m_Pa_s=obs,holdout_sd_m_Pa_s=float(r['sd_1e_minus8_m_s_MPa'])*1e-14,error_pct=100*(L/obs-1),LODO_RMSE_m_Pa_s=cv_rmse,LODO_fit_min=min(lo),LODO_fit_max=max(lo)))
        for k,lodo in zip(g,lo):
            dp=(float(k['soil_MPa'])-float(k['xylem_MPa']))*1e6
            points.append(dict(date=k['date'],species=sp,split=k['split'],delta_psi_Pa=dp,reported_Lp_m_Pa_s=v(k),reported_sd_m_Pa_s=float(k['sd_1e_minus8_m_s_MPa'])*1e-14,fit_Lp_m_Pa_s=L,LODO_pred_Lp_m_Pa_s=lodo,model_flux_m_s=uptake_rate(L,1,dp,0),reconstructed_flux_m_s=v(k)*dp))
    return out,points

def wet():
    data=rows('glass_angles.csv'); train=[float(r['apparent_deg']) for r in data if r['split']=='train']; held=[float(r['apparent_deg']) for r in data if r['split']=='holdout']; target=st.mean(train)
    @lru_cache(maxsize=100)
    def eval1(theta,scale):
        m,s=state(theta,scale)
        angles=[apparent(m,s,tr) for tr in (0.5,1.,1.5)]
        return angles,s.force,s.psi
    estimates={}; checks=[]; sweep=[]
    for sc in [1,2]:
        fun=lambda t:eval1(t,sc)[0][1][0]-target
        th=brentq(fun,50,55,xtol=1e-4); estimates[sc]=float(th)
        for t in [46.,48.,50.,52.,54.,56.,58.,60.,62.,64.,66.]:
            ang,f,p=eval1(t,sc);sweep.append(dict(grid_um=50/sc,input_deg=t,readout_deg=ang[1][0],low_trim_deg=ang[0][0],high_trim_deg=ang[2][0],force_N_m=f,psi_Pa=p))
    for sc in [1,2]:
        for role,th in [('legacy',60.),('coarse_fit_no_retuning',estimates[1]),('mesh_specific_fit',estimates[sc])]:
            ang,F,psi=eval1(th,sc);pred=ang[1][0]
            checks.append(dict(grid_um=50/sc,parameter_source=role,input_deg=th,predicted_deg=pred,train_target_deg=target,holdout_rmse_deg=math.sqrt(st.mean([(pred-h)**2 for h in held])),low_trim_readout_deg=ang[0][0],high_trim_readout_deg=ang[2][0],arc_fit_rms_um=ang[1][1]*50,n_interface_columns=ang[1][2],attraction_N_m=-F,psi_Pa=psi))
    return estimates,checks,sweep

def main():
    out=HERE/'results';out.mkdir(exist_ok=True);c,ct=cup_fit();t,tp=trees();e,checks,sweep=wet()
    prof=dict(ceramic=c,trees=t,grain_wall_inputs_deg={str(50//sc)+'um':v for sc,v in e.items()},usage='Tree and cup Lp are whole-system effective values referenced to total external area. NOT intrinsic wetted membrane values. Only transfer under stated surface and resistance assumptions. Glass angle presets are specific to initial patch geometry and readout; neither root wetting nor force was fitted.')
    (out/'profiles.json').write_text(json.dumps(prof,indent=2)+'\n');writecsv(out/'ceramic_time_checks.csv',ct);writecsv(out/'tree_holdout.csv',t);writecsv(out/'tree_individual_dates.csv',tp);writecsv(out/'wetting_checks.csv',checks);writecsv(out/'wetting_sweep.csv',sweep)
    print(json.dumps(prof,indent=2));print(checks)
if __name__=='__main__':main()
