"""Seal Stage129 narrow miss."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'stage129_staging'));import cpd6_stationarity_continuation_v1 as job
def main():
 d=job.read(job.DESIGN);job.verify(d);c=job.read(job.RUN/'completion.json');job.require(not(job.RUN/'failure.json').exists(),'failure marker')
 for k in ['record','field','state']:job.require(job.sha(c[k]['path'])==c[k]['sha256'],k+' drift')
 root=job.EVAL/'independent_evaluation_01';r=job.read(root/'results.json');rc=job.read(root/'completion.json');job.require(rc['results_sha256']==job.sha(root/'results.json'),'evaluation drift');job.require(r['passed'] and not r['qualified'] and r['checks']['mean_match'] and r['checks']['adjacent_field'] and not r['checks']['long_window_field'],'disposition drift');cp=job.EVAL/'completion.json';files=sorted({p.resolve() for b in [job.DESIGN.parent,job.RUN,job.EVAL,ROOT/'stage129_staging'] for p in b.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.resolve()!=cp.resolve()});out={'status':r['status'],'qualified':False,'mean_match_passed':True,'adjacent_field_passed':True,'long_window_field_passed':False,'relative_gate_excess':r['relative_gate_excess'],'transport_authorized':False,'artifacts':{str(p):job.sha(p) for p in files},'next':'Decide prospectively whether the 2.84% threshold miss justifies one final short fixed-force confirmation; do not extend automatically.'};job.write(cp,out);print(out['status'],'sealed',len(files),'artifacts')
if __name__=='__main__':main()
