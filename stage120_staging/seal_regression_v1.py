"""Close numerical repair evidence without authorizing a population campaign."""
import platform
import sys
import numpy
import scipy
import repair_regression_v1 as job
api=job.api
d=api.read(job.DESIGN);job.verify(d)
result=api.read(job.EVAL/'independent_evaluation_01/results.json')
api.verify_mapping(result['artifacts'])
done=api.read(job.EVAL/'independent_evaluation_01/completion.json')
api.require(done['results_sha256']==api.sha(job.EVAL/'independent_evaluation_01/results.json'),'evaluation digest drift')
qa=api.read(job.EVAL/'render_01/visual_qa.json')
api.require(qa['passed'] and qa['figure_sha256']==api.sha(job.EVAL/'render_01/repair_regression.png'),'visual QA missing')
api.verify_mapping(api.read(job.EVAL/'render_01/manifest.json')['artifacts'])
roots=[job.ROOT/'stage119_staging',job.ROOT/'stage119_designs'/job.local.BASE,job.ROOT/'stage119_evaluations'/job.local.BASE,
       job.ROOT/'stage120_staging',job.DESIGN.parent,job.RUN,job.EVAL]
paths=sorted({p.resolve() for root in roots for p in root.rglob('*') if p.is_file() and '__pycache__' not in p.parts})
out=job.EVAL/'completion.json'
api.require(not out.exists(),'immutable stage seal exists')
record={'status':result['status'],'repair_local_verified':True,'trajectory_regression_passed':result['passed'],
    'qualified_cases':sum(r['qualified'] for r in result['ledger']),'passed_triplets':sum(g['passed'] for g in result['groups']),
    'population_authorized':False,'release_fraction_measured':False,'physical_model_changed':False,'physical_validation_claimed':False,
    'extreme_retry29_repaired':False,'previous_failure_evidence_preserved':True,
    'environment':{'python':sys.version,'numpy':numpy.__version__,'scipy':scipy.__version__,'platform':platform.platform()},
    'artifacts':{str(p):api.sha(p) for p in paths},'next':result['next']}
api.write(out,record);print(record['status'],'sealed artifacts',len(paths))
