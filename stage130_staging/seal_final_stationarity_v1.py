"""Seal qualified Stage130 CPD6 flow."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'stage130_staging'));import cpd6_final_stationarity_v1 as job
def main():
 d=job.read(job.DESIGN);job.verify(d);c=job.read(job.RUN/'completion.json');job.require(not(job.RUN/'failure.json').exists(),'failure marker')
 for k in ['record','field','state']:job.require(job.sha(c[k]['path'])==c[k]['sha256'],k+' drift')
 root=job.EVAL/'independent_evaluation_01';r=job.read(root/'results.json');rc=job.read(root/'completion.json');job.require(rc['results_sha256']==job.sha(root/'results.json') and r['passed'] and r['qualified'],'qualification absent');job.require(not r['transport_authorized'] and not r['spatial_convergence_established'],'authority drift');cp=job.EVAL/'completion.json';files=sorted({p.resolve() for b in [job.DESIGN.parent,job.RUN,job.EVAL,ROOT/'stage130_staging'] for p in b.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.resolve()!=cp.resolve()});out={'status':r['status'],'qualified':True,'mean_match_passed':True,'stationarity_passed':True,'numerical_health_passed':True,'transport_authorized':False,'spatial_convergence_established':False,'accepted_field':c['field'],'accepted_state':c['state'],'artifacts':{str(p):job.sha(p) for p in files},'next':'Refine the CPD4 particle timestep prospectively, then freeze the matched CPD4/CPD6 sphere/fibre response comparison. No transport campaign yet.'};job.write(cp,out);print(out['status'],'sealed',len(files),'artifacts')
if __name__=='__main__':main()
