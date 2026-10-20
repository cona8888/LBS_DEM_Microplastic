"""Serial qualification of exact-cycle early rejection plus NumPy-BLAS loops."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
import platform
from pathlib import Path
import sys
import time
import numpy as np
import scipy

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(ROOT/'stage40_staging'), str(ROOT/'stage41_staging'),
                str(ROOT/'algorithm_review_20260912/src')]
import matrix_case_v1
import geometry_exact_v1
import wall_field_exact_v1
import driver_consolidated as driver
from portfolio_explicit import make_contact_model
from cycle_model import make_cycle_contact_model
import compiled_sor
from compiled_stage53 import CompiledStage53
import numba
import llvmlite


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def sources():
    paths = {Path(__file__).resolve()}
    for module in tuple(sys.modules.values()):
        value = getattr(module, '__file__', None)
        if value:
            path = Path(value).resolve()
            if path.suffix == '.py' and path.is_relative_to(ROOT) and 'deps' not in path.parts:
                paths.add(path)
    return {str(p):sha(p) for p in sorted(paths)}


def plain(value):
    if isinstance(value, dict):
        return {str(k):plain(v) for k,v in value.items()}
    if isinstance(value, (list,tuple)):
        return [plain(v) for v in value]
    if isinstance(value, np.ndarray):
        return plain(value.tolist())
    if isinstance(value, np.generic):
        return plain(value.item())
    if isinstance(value, float) and not np.isfinite(value):
        return {'nonfinite_float':str(value)}
    return value


def save(path, value):
    path.write_text(json.dumps(plain(value),indent=2,allow_nan=False))


class Sor:
    def __init__(self,module=compiled_sor):
        self.module=module
    def __call__(self,*args,**kwargs):
        return self.module.solve_prepared(*args,**kwargs)
    def stats(self):
        return self.module.stats()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output',required=True)
    parser.add_argument('--mode',choices=['local','crossing','refinement','smoke'],required=True)
    parser.add_argument('--kernel',choices=['baseline','sor','both','blas'],default='blas')
    parser.add_argument('--seeds',type=int,nargs='+',default=[2])
    parser.add_argument('--levels',type=float,nargs='+',default=[1.,.5,.25])
    parser.add_argument('--budget',type=float,default=300.)
    parser.add_argument('--horizon',type=float,default=.02)
    args = parser.parse_args()
    if args.kernel=='blas':
        import compiled_blas_loop as loop_module
        from compiled_stage53_blas import CompiledStage53 as default_class
    else:
        loop_module=compiled_sor
        default_class=CompiledStage53
    def model_for(kernel):
        if kernel == 'blas':
            return make_cycle_contact_model()
        return make_contact_model(default_solver=default_class() if kernel in ('both','blas') else None,
            sor_solver=Sor(loop_module) if kernel in ('sor','both','blas') else None)
    out = Path(args.output);out.mkdir(parents=True,exist_ok=False)
    started = datetime.now(timezone.utc).isoformat()
    before = sources()
    warmup = loop_module.warmup() if args.kernel != 'baseline' else 0.
    cfgpath=ROOT/'stage55_designs/paired_three_packing_pilot_v1.json'
    cfg=json.loads(cfgpath.read_text());inputs={str(cfgpath):sha(cfgpath)}
    checks={};rows=[]
    if args.mode == 'smoke':
        import verify_trajectory_optimized_v1 as verifier
        class Candidate:
            @staticmethod
            def integrate(*pos,**kw):
                kw['contact_model']=model_for(args.kernel)
                return driver.integrate(*pos,**kw)
        verifier.candidate=Candidate
        sys.argv=[sys.argv[0],'--output',str(out/'smoke')]
        verifier.main()
        return
    for seed in args.seeds:
        field,old,L,dx,paths=matrix_case_v1.load(seed)
        field=wall_field_exact_v1.WallCellFieldExact.from_field(field)
        for path in paths:inputs[str(path)]=sha(path)
        priorpath=ROOT/f'stage55_runs/paired_three_packing_pilot_20260912/pilot_01/s{seed}_prolate_ar4.json'
        inputs[str(priorpath)]=sha(priorpath)
        previous=json.loads(priorpath.read_text())['result']
        if args.mode == 'crossing':
            startpath=ROOT/f'stage37_runs/stage4_farfield_bound_20260912/pilot_01/starts_s{seed}.json'
            inputs[str(startpath)]=sha(startpath)
            sid=next(p['start_id'] for p in cfg['packings'] if p['seed']==seed)
            start=next(p for p in json.loads(startpath.read_text()) if p['id']==sid)
            position,orientation,velocity=start['position_m'],start['orientation'],np.zeros(6)
            horizon=previous['time_s']+.05
        else:
            position,orientation,velocity=previous['position_m'],previous['orientation'],previous['velocity_generalized']
            horizon=.002 if args.mode=='local' else args.horizon
        levels=args.levels if args.mode=='refinement' else [1.]
        kernels=['baseline',args.kernel] if args.mode=='local' and args.kernel!='baseline' else [args.kernel]
        for level in levels:
            for kernel in kernels:
                a,b,_=cfg['prolate_semiaxes_m']
                name=f's{seed}_{kernel}_l{level:g}'
                model=model_for(kernel)
                kwargs=dict(added_mass_fraction=cfg['added_mass_fraction'],cutoff_ratio=.2,roughness_ratio=.01,
                    displacement_fraction=.1*level,relaxation_fraction=.5*level,angle_limit=.02*level,
                    max_dt=.01*level,wall_budget=args.budget,trap_reference_speed=1e-4,
                    trap_dwell_time=.5,stop_on_trap=False,reynolds_limit=3.,contact_model=model,
                    capture_step_inputs=args.mode=='local',capture_prepared_inputs=args.mode=='local')
                tracepath=out/f'{name}_attempts.jsonl'
                with tracepath.open('w') as handle:
                    def observe(record):
                        handle.write(json.dumps(plain(record),allow_nan=False)+'\n')
                        handle.flush()
                    result=driver.integrate(field,geometry_exact_v1.GrainGeometry.from_geometry(old),
                        position,orientation,velocity,a,b,cfg['dynamic_viscosity_Pa_s'],
                        cfg['particle_density_kg_m3'],cfg['fluid_density_kg_m3'],cfg['gravity_m_s2'],
                        cfg['friction_coefficient'],L,horizon,attempt_observer=observe,**kwargs)
                checks[name+'_complete']=result['status']=='present_at_horizon' and result['time_s']==horizon
                checks[name+'_health']=(result['minimum_gap_m'] is None or result['minimum_gap_m']>=-1e-5*b) and all(
                    result[k]<=limit for k,limit in [('max_contact_residual',1e-10),('max_force_residual',1e-8),
                                                    ('max_momentum_residual',1e-8),('max_reynolds',3.)])
                checks[name+'_budget']=result['runtime_seconds']<=args.budget
                row={'name':name,'seed':seed,'kernel':kernel,'level':level,'horizon_s':horizon,'result':result,
                     'trace_sha256':sha(tracepath),'options':{k:v for k,v in kwargs.items() if k!='contact_model'}}
                rows.append(row);save(out/f'{name}.json',row)
                print(json.dumps({'case':name,'status':result['status'],'t':result['time_s'],
                    'runtime_s':result['runtime_seconds'],'rejected':result['rejected'],
                    'contact_retries':result['contact_solver_retries'],
                    'attempts':result['attempt_diagnostics']['counts']}),flush=True)
    comparisons=[]
    if args.mode=='local' and args.kernel!='baseline':
        for seed in args.seeds:
            reference,candidate=[r['result'] for r in rows if r['seed']==seed]
            shift=float(np.linalg.norm(np.array(reference['position_m'])-candidate['position_m']))
            angle=float(np.arctan2(np.linalg.norm(np.cross(reference['orientation'],candidate['orientation'])),
                                  np.dot(reference['orientation'],candidate['orientation'])))
            comparisons.append({'seed':seed,'position_m':shift,'orientation_rad':angle,
                'runtime_speedup':reference['runtime_seconds']/candidate['runtime_seconds']})
            checks[f's{seed}_local_agreement']=shift<=.01*b and angle<=.001 and reference['time_s']==candidate['time_s']
            checks[f's{seed}_local_faster']=candidate['runtime_seconds']<reference['runtime_seconds']
    if args.mode=='refinement':
        for seed in args.seeds:
            selected=[r for r in rows if r['seed']==seed]
            for left,right in zip(selected,selected[1:]):
                one,two=left['result'],right['result']
                shift=float(np.linalg.norm(np.array(one['position_m'])-two['position_m'])/b)
                angle=float(np.arctan2(np.linalg.norm(np.cross(one['orientation'],two['orientation'])),
                                      np.dot(one['orientation'],two['orientation'])))
                label=f's{seed}_{left["level"]}_{right["level"]}'
                comparisons.append({'name':label,'position_minor_radii':shift,'orientation_rad':angle,
                                    'same_time':one['time_s']==two['time_s']})
                checks[label+'_refinement']=shift<=.01 and angle<=.001 and one['time_s']==two['time_s']==args.horizon
    after=sources();checks['sources_stable']=all(after.get(k)==v for k,v in before.items())
    payload={'passed':all(checks.values()),'checks':checks,'rows':rows,'comparisons':comparisons,
        'algorithm_variant':'numpy_blas_with_exact_outer_cycle_rejection',
        'arguments':vars(args),'physical_config':cfg,'source_hashes_before':before,'source_hashes':after,
        'input_hashes':inputs,'jit_prepare_seconds':warmup,'started_utc':started,
        'completed_utc':datetime.now(timezone.utc).isoformat(),
        'environment':{'python':platform.python_version(),'numpy':np.__version__,'scipy':scipy.__version__,
                       'numba':numba.__version__,'llvmlite':llvmlite.__version__,
                       'processor':platform.processor(),
                       'thread_environment':{k:os.environ.get(k) for k in
                           ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMBA_NUM_THREADS')}},
        'scope':'numerical verification only; local/refinement runs reset dwell and recovery history'}
    if args.kernel=='blas':
        payload['numpy_blas']={'path':str(loop_module.BLAS_PATH),'sha256':sha(loop_module.BLAS_PATH),
                               'configuration':loop_module.BLAS_CONFIGURATION}
    save(out/'results.json',payload)
    save(out/'completion.json',{'status':'complete_passed' if payload['passed'] else 'complete_failed',
                                'results_sha256':sha(out/'results.json')})
    print(json.dumps(plain({'passed':payload['passed'],'checks':checks,'comparisons':comparisons}),indent=2),flush=True)
    if not payload['passed']:raise SystemExit(1)


if __name__=='__main__':main()
