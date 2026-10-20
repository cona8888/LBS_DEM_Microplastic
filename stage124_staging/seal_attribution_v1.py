"""Seal only the demonstrated finite-level diagnostic, retaining open gates."""
import mean_offset_diagnostic_v1 as job
api=job.api
d=api.read(job.DESIGN);job.execution_verify(d)
root=job.EVAL/'independent_evaluation_01'
r=api.read(root/'results.json');done=api.read(root/'completion.json')
api.require(done['passed']==r['passed'] and done['results_sha256']==api.sha(root/'results.json'),'evaluation drift')
api.require(r['passed'],'unqualified diagnostic')
api.verify_mapping(r['artifacts']);api.verify_mapping(r['attribution']['reused_records']);api.verify_mapping(r['fixed_pose_field_probe']['input_hashes'])
pre=api.read(job.PREFLIGHT);api.require(pre['identity_records_sha256']==api.sha(job.PREFLIGHT.parent/'identity_records.json'),'preflight identity drift')
qa=api.read(job.EVAL/'render_01/visual_qa.json');api.require(qa['passed'] and qa['figure_sha256']==api.sha(job.EVAL/'render_01/mean_offset_attribution.png'),'visual QA missing')
api.verify_mapping(api.read(job.EVAL/'render_01/manifest.json')['artifacts'])
files=sorted({p.resolve() for root in [job.DESIGN.parent,job.RUN,job.EVAL,job.ROOT/'stage124_staging'] for p in root.rglob('*') if p.is_file() and '__pycache__' not in p.parts})
out={'status':'mean_offset_attribution_complete_spatial_gate_open','diagnostic_temporal_passed':True,
     'counterfactual_field_physically_validated':False,'spatial_convergence_established':False,'empirical_validation_passed':False,
     'calibration_performed':False,'new_physical_model':False,'source_evidence_preserved':True,
     'attribution_screen':{row['shape']:{k:v['mean_offset_alone_insufficient_under_screen'] for k,v in row['metrics'].items()} for row in r['attribution']['rows']},
     'artifacts':{str(p):api.sha(p) for p in files},
     'next':'Use the attribution result to scope directly solved, tighter mean-flow-matched spatial/near-wall verification. Do not promote the scaled diagnostic field to physical prediction.'}
api.write(job.EVAL/'completion.json',out);print(out['status'],'sealed',len(files),'artifacts')
