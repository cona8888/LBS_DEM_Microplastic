"""Seal bounded cost evidence and audit the already-known temporal budget."""
import spatial_cost_v1 as job

d=job.read(job.DESIGN);job.verify(d)
root=job.EVAL/'independent_evaluation_01'
r=job.read(root/'results.json');done=job.read(root/'completion.json')
job.require(r['passed'] and done['results_sha256']==job.sha(root/'results.json'),'evaluation drift')
raw=job.read(job.RUN/'completion.json')
for path,expected in raw['artifacts'].items():job.require(job.sha(path)==expected,'raw drift')
qa=job.read(job.EVAL/'render_01/visual_qa.json')
job.require(qa['passed'] and qa['figure_sha256']==job.sha(job.EVAL/'render_01/third_grid_cost.png'),'visual QA missing')
for path,expected in job.read(job.EVAL/'render_01/manifest.json')['artifacts'].items():
    job.require(job.sha(path)==expected,'render drift')
old=job.ROOT/'stage124_evaluations/mean_offset_attribution_20260916/independent_evaluation_01/results.json'
oldseal=job.read(d['bindings']['stage124_seal']['path'])
job.require(oldseal['artifacts'][str(old)]==job.sha(old),'attribution source changed')
oldresults=job.read(old)
limit=d['next_spatial_protocol']['response_budget']['position_over_minor_radius_max']
rows=[{'shape':x['shape'],'cpd4_twice_adjacent_position_difference_over_minor_radius':
       x['metrics']['position']['twice_adjacent_level_differences']['B'],
       'new_total_position_budget_over_minor_radius':limit,
       'finer_cpd4_time_levels_required':x['metrics']['position']['twice_adjacent_level_differences']['B']>=limit}
      for x in oldresults['attribution']['rows']]
budget={'source':job.bind(old),'prospective_design':job.bind(job.DESIGN),'rows':rows,
        'interpretation':'The prior individual timestep gates remain historical passes. Their twice-adjacent difference proxies already consume the new joint spatial/temporal position budget, so further CPD4 temporal refinement is needed before that tighter combined gate could pass. These proxies are not rigorous error bounds.'}
job.write(job.EVAL/'precision_budget_audit.json',budget)
files=sorted({p.resolve() for base in [job.BASE,job.EVAL,job.RUN,job.ROOT/'stage125_staging']
              for p in base.rglob('*') if p.is_file() and '__pycache__' not in p.parts})
completion={'status':r['status'],'cost_pilot_passed':True,'geometry_preflight_passed':True,
    'full_steady_solve_authorized':False,'flow_field_exported':False,
    'spatial_convergence_established':False,'empirical_validation_passed':False,
    'artifacts':{str(p):job.sha(p) for p in files},
    'next':'Bounded CPD4-initialized CPD6 convergence-rate pilot, plus finer CPD4 trajectory timesteps when comparing particle response. No cold-start long solve or full population dispatch.'}
job.write(job.EVAL/'completion.json',completion)
print(completion['status'],'sealed',len(files),'artifacts',flush=True)
