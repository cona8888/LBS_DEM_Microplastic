"""Seal corrected Stage128 evaluation."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'stage128_staging'))
import cpd6_mean_correction_v1 as job
def main():
 d=job.read(job.DESIGN);job.verify(d);p=job.read(job.EVAL/'preflight_01/results.json');job.require(p['passed'],'preflight failed');c=job.read(job.RUN/'completion.json');job.require(not(job.RUN/'failure.json').exists(),'failure marker')
 for k in ['record','field','state']:job.require(job.sha(c[k]['path'])==c[k]['sha256'],k+' drift')
 root=job.EVAL/'independent_evaluation_02';r=job.read(root/'results.json');rc=job.read(root/'completion.json');job.require(rc['results_sha256']==job.sha(root/'results.json'),'evaluation drift');job.require(r['passed'] and not r['qualified'] and r['checks']['mean_match'] and r['checks']['adjacent_field'] and not r['checks']['long_window_field'],'disposition drift');job.require((job.EVAL/'evaluation_attempt_01_disposition.json').is_file(),'disposition missing');job.require(not r['transport_authorized'],'authority drift')
 cp=job.EVAL/'completion_v2.json';files=sorted({p.resolve() for b in [job.DESIGN.parent,job.RUN,job.EVAL,ROOT/'stage128_staging'] for p in b.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.resolve()!=cp.resolve()});out={'status':r['status'],'evidence_audit_passed':True,'qualified':False,'mean_match_passed':True,'adjacent_field_passed':True,'long_window_field_passed':False,'runtime_seconds':r['runtime_seconds'],'full_flow_solution':False,'spatial_convergence_established':False,'transport_authorized':False,'artifacts':{str(p):job.sha(p) for p in files},'next':'A separately frozen bounded continuation may test long-window stationarity; no second correction is indicated and no automatic extension is authorized.'};job.write(cp,out);print(out['status'],'sealed',len(files),'artifacts')
if __name__=='__main__':main()
