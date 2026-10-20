"""Audit public experimental CDFs; never execute downloaded scripts or fit the DEM."""
from pathlib import Path
import hashlib
import json
import tarfile
import numpy as np
from scipy.io import loadmat
ROOT=Path(__file__).resolve().parents[1]
RAW=ROOT/'stage123_literature/fouty_2024_20260916'
OUT=ROOT/'stage123_evaluations/literature_validation_20260916/audit_01'
ARCHIVE_SHA='14a3b8bfd64a3fd8a1e3733e272d77a82b5a562ea9247b8bb1920d5e98618b42'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,x):
    with Path(p).open('x',encoding='utf-8') as f:json.dump(x,f,indent=2,allow_nan=False)
def quantile(t,y,p):
    i=int(np.searchsorted(y,p,side='left'))
    if i==0:return float(t[0])
    if i>=len(t):raise ValueError('CDF does not reach probability')
    return float(t[i-1]+(p-y[i-1])*(t[i]-t[i-1])/(y[i]-y[i-1]))
def cdf_ok(t,y):
    return bool(t.shape==y.shape and np.all(np.isfinite(t)) and np.all(np.isfinite(y)) and np.all(np.diff(t)>0) and np.all(np.diff(y)>=0) and y.min()>=0 and y.max()<=1 and y[0]==0 and y[-1]==1)
def main():
    archive=RAW/'MPF_Plots.tar.gz';assert sha(archive)==ARCHIVE_SHA
    members={}
    # Each extracted member is checked against archive bytes, not just filenames.
    with tarfile.open(archive,'r:gz') as ar:
        for m in ar.getmembers():
            assert m.isfile() and Path(m.name).name==m.name,'unexpected archive path or type'
            if m.name.startswith('._'):continue
            p=RAW/'extracted'/m.name
            assert hashlib.sha256(ar.extractfile(m).read()).hexdigest()==sha(p)
            members[str(p)]=sha(p)
    b=RAW/'extracted'
    pores=loadmat(b/'PoresData.mat',simplify_cells=True)
    ad=loadmat(b/'ADER_Fits.mat',simplify_cells=True)['ADER_Fits']
    wt=loadmat(b/'WT_Fits.mat',simplify_cells=True)['WT_Fits']
    labels=['3 mm fibre','5 mm fibre','8 mm fibre','Tracer beads'];rows=[];curves=[]
    tests={'linear_inverse':quantile(np.array([0.,1.,2.]),np.array([0.,.5,1.]),.25)==.5,
        'plateau_first_crossing':quantile(np.array([0.,1.,2.,3.]),np.array([0.,.5,.5,1.]),.5)==1.,
        'nonmonotone_rejected':not cdf_ok(np.array([0.,1.,2.,3.]),np.array([0.,.7,.6,1.])),
        'nonfinite_rejected':not cdf_ok(np.array([0.,1.,2.]),np.array([0.,np.nan,1.]))}
    assert all(tests.values())
    for pore,p in enumerate(pores['Pores'],1):
        t=np.asarray(p['t'],float)
        for n,label in enumerate(labels):
            # MATLAB second column is labelled experiments in both plotting scripts.
            y=np.asarray(p['CDFs'][n,1],float)
            assert cdf_ok(t,y)
            row={'pore_window':pore,'label':label,'source_field':f'Pores{{{pore},1}}.CDFs{{{n+1},2}}',
                 'points':len(t),'grid_s':float(t[1]-t[0]),'cdf_checks_passed':True,
                 't10_s':quantile(t,y,.1),'t50_s':quantile(t,y,.5),'t90_s':quantile(t,y,.9)}
            if pore==1:
                row['matches_ADER_experimental_column_exactly']=bool(np.array_equal(y,ad['CDFs'][n,1]))
                row['matches_WT_experimental_column_on_same_grid']=bool(np.array_equal(y,np.interp(t,wt['t'],wt['CDFs'][n,1])))
                assert row['matches_ADER_experimental_column_exactly'] and row['matches_WT_experimental_column_on_same_grid']
            rows.append(row);curves.append({'pore_window':pore,'label':label,'time_s':t.tolist(),'experimental_processed_cdf':y.tolist()})
    for pore in [1,2]:
        median=next(r['t50_s'] for r in rows if r['pore_window']==pore and r['label']=='Tracer beads')
        for r in rows:
            if r['pore_window']==pore:r['t50_over_same_window_beads']=r['t50_s']/median
    r3=next(r for r in rows if r['pore_window']==2 and r['label']=='3 mm fibre')
    r8=next(r for r in rows if r['pore_window']==2 and r['label']=='8 mm fibre')
    ratio=r8['t50_s']/r3['t50_s']-1
    result={'data_extraction_passed':True,'empirical_model_validation_passed':False,'calibration_performed':False,
      'source':{'article_doi':'10.1029/2024WR037901','data_doi':'10.7273/000006421',
      'repository':'https://rex.libraries.wsu.edu/esploro/outputs/dataset/Mesomodel-Microplastic-Fiber-Experiments-and-Simulation/99901100739901842',
      'download_url':'https://rex.libraries.wsu.edu/view/fileRedirect?download=true&filePid=13409987060001842&instCode=01ALLIANCE_WSU',
      'download_date':'2026-09-16','archive_sha256':ARCHIVE_SHA,'hash_is_local_integrity_not_publisher_checksum':True},
      'members':members,'rows':rows,'tests':tests,'matlab_executed':False,
      'excluded_fields':['CDFs(:,1): author simulations, not experimental target','ADERModels: fitted model','CDF_sim and TCDFs: fitted/delayed simulations','FDt: mixed simulation/experiment diagnostics; excluded from this audit'],
      'limitations':['Processed experimental CDF arrays, not raw video or unprocessed tracking observations.','CDF endpoint one is normalization; not proof of full recovery of injected mass.','Centroid passage across imaging windows is not whole-body export from an initial soil inventory.','No bootstrap confidence interval: raw independent trajectory resampling is not justified by these CDF arrays.','This archive was inspected before audit-code finalization; this is not blind held-out validation.'],
      'consistency_flag':{'quantity':'8 mm versus 3 mm median time increase across both pores','archive_fraction':ratio,'article_approximate_fraction':.35,
          'disposition':'Unresolved archive/text numerical discrepancy; do not alter archive or calibrate to the narrative number. First-pore arrays match the independent archived plotting inputs.'},
      'current_model_compatibility':{'same_geometry':False,'same_loading_and_observable':False,'same_particle_shapes_and_sizes':False,'same_forcing_domain':False,
          'notes':'Mesomodel uses injected monofilaments and passive beads in a pseudo-2D obstacle cell, at published throat Reynolds number about 1500. The present model is dense PET spheres/AR4 prolates in 3D sand at low-speed prescribed flow. A new matched benchmark and hydrodynamic domain qualification would be needed; no direct DEM validation score is admissible.'},
      'next':'Resolve remaining spatial response sensitivity; choose a genuinely matched component or transport benchmark before any model validation claim.'}
    OUT.mkdir(parents=True,exist_ok=False);write(OUT/'experimental_curves.json',curves);write(OUT/'results.json',result)
    write(OUT/'completion.json',{'data_extraction_passed':True,'empirical_model_validation_passed':False,'source_sha256':sha(__file__),
      'artifacts':{str(OUT/n):sha(OUT/n) for n in ['experimental_curves.json','results.json']}})
    print('DATA EXTRACTION PASS; MODEL VALIDATION NOT ESTABLISHED')
    for r in rows:print(r['pore_window'],r['label'],'t50',round(r['t50_s'],6),'relative',round(r['t50_over_same_window_beads'],4))
    print('Archive/text median increase',ratio,.35)
if __name__=='__main__':main()
