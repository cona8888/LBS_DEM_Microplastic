"""Bounded physical continuation, solver equivalence and application checks."""
import argparse
import hashlib
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import scipy
import trajectory_recovery_v1 as candidate
import trajectory_explicit_v1
import wall_field_exact_v1

ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'stage40_staging'),str(ROOT/'stage41_staging'),str(ROOT/'stage53_staging')]
import matrix_case_v1
import geometry_exact_v1
import trajectory_multistart_lm_v1 as baseline


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def sources():
    paths={Path(__file__).resolve()}
    for module in list(sys.modules.values()):
        value=getattr(module,'__file__',None)
        if value and Path(value).suffix=='.py' and Path(value).resolve().is_relative_to(ROOT):
            paths.add(Path(value).resolve())
    return {str(p):sha(p) for p in sorted(paths)}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',required=True)
    parser.add_argument('--mode',choices=['smoke','saved','crossing','sphere'],required=True)
    parser.add_argument('--horizon',type=float,default=.02)
    parser.add_argument('--fractions',type=float,nargs='+',default=[.1])
    parser.add_argument('--seeds',type=int,nargs='+',default=[1,2,3])
    parser.add_argument('--budget',type=float,default=300.)
    args=parser.parse_args()
    if args.mode=='smoke':
        import verify_trajectory_optimized_v1 as verification
        verification.candidate=candidate
        sys.argv=[sys.argv[0],'--output',args.output]
        verification.main()
        return
    out=Path(args.output);out.mkdir(parents=True,exist_ok=False)
    before=sources();started=datetime.now(timezone.utc).isoformat()
    cfgpath=ROOT/'stage55_designs/paired_three_packing_pilot_v1.json'
    cfg=json.loads(cfgpath.read_text());inputs={str(cfgpath):sha(cfgpath)}
    rows=[];checks={}
    for seed in args.seeds:
        field,old,L,dx,paths=matrix_case_v1.load(seed)
        fast_field=wall_field_exact_v1.WallCellFieldExact.from_field(field)
        geometry=geometry_exact_v1.GrainGeometry.from_geometry(old)
        for path in paths:inputs[str(path)]=sha(path)
        a,b,_=cfg['prolate_semiaxes_m']
        if args.mode=='saved':
            path=ROOT/f'stage55_runs/paired_three_packing_pilot_20260912/pilot_01/s{seed}_prolate_ar4.json'
            previous=json.loads(path.read_text())['result']
            position,orientation,velocity=previous['position_m'],previous['orientation'],previous['velocity_generalized']
            horizon=args.horizon
        else:
            path=ROOT/f'stage37_runs/stage4_farfield_bound_20260912/pilot_01/starts_s{seed}.json'
            item=next(c for c in cfg['packings'] if c['seed']==seed)
            start=next(c for c in json.loads(path.read_text()) if c['id']==item['start_id'])
            position,orientation,velocity=start['position_m'],start['orientation'],np.zeros(6)
            if args.mode=='sphere':
                a=b=(a*b*b)**(1/3)
                horizon=cfg['horizon_pore_volumes']*L/cfg['target_mean_interstitial_velocity_m_s']
            else:
                previous_path=ROOT/f'stage55_runs/paired_three_packing_pilot_20260912/pilot_01/s{seed}_prolate_ar4.json'
                inputs[str(previous_path)]=sha(previous_path)
                previous=json.loads(previous_path.read_text())['result']
                horizon=previous['time_s']+.05
        inputs[str(path)]=sha(path)
        for fraction in args.fractions:
            kwargs=dict(added_mass_fraction=1,cutoff_ratio=.2,roughness_ratio=.01,
                        displacement_fraction=fraction,relaxation_fraction=5*fraction,
                        angle_limit=.02,max_dt=.01,wall_budget=args.budget,
                        trap_reference_speed=1e-4,trap_dwell_time=.5,
                        stop_on_trap=False,reynolds_limit=3.)
            result=candidate.integrate(fast_field,geometry,position,orientation,velocity,a,b,
                .001002,1380.,998.2,[0,0,-9.80665],.3,L,horizon,**kwargs)
            name=f's{seed}_f{fraction}'
            checks[name+'_completed']=result['status']=='present_at_horizon' and result['time_s']==horizon
            checks[name+'_health']=(result['minimum_gap_m'] is None or result['minimum_gap_m']>=-1e-5*b) and all(
                result[k]<=1e-8 for k in ('max_contact_residual','max_force_residual','max_momentum_residual')) and result['max_reynolds']<=3
            row={'seed':seed,'fraction':fraction,'horizon_s':horizon,'result':result}
            if args.mode=='sphere':
                # Freeze baseline reference from the archived original pilot.
                refpath=ROOT/f'stage55_runs/paired_three_packing_pilot_20260912/pilot_01/s{seed}_equal_volume_sphere.json'
                reference=json.loads(refpath.read_text())['result'];inputs[str(refpath)]=sha(refpath)
                keys=('status','time_s','position_m','orientation','velocity_generalized','steps','rejected','history','total_contact_iterations')
                checks[name+'_saved_path_identical']=all(reference[k]==result[k] for k in keys)
                row['archived_runtime_s']=reference['runtime_seconds']
                # Fresh reference timings exclude historical host/load differences.
                current=baseline.integrate(field,geometry,position,orientation,velocity,a,b,
                    .001002,1380.,998.2,[0,0,-9.80665],.3,L,horizon,**kwargs)
                row['fresh_baseline']=current
                checks[name+'_fresh_path_identical']=all(current[k]==result[k] for k in keys)
                row['speedup_vs_fresh_baseline']=current['runtime_seconds']/result['runtime_seconds']
            rows.append(row)
            (out/f'{name}.json').write_text(json.dumps(row,indent=2))
            print(json.dumps({'case':name,'status':result['status'],'time_s':result['time_s'],
                              'runtime_s':result['runtime_seconds'],'retries':result['contact_solver_retries'],
                              'recovery_stats':result['contact_algorithm_stats']}),flush=True)
    refinement=[]
    if len(args.fractions)>=3:
        for seed in args.seeds:
            selected=[r for r in rows if r['seed']==seed]
            medium,fine=selected[-2]['result'],selected[-1]['result']
            shift=float(np.linalg.norm(np.array(medium['position_m'])-fine['position_m'])/b)
            angle=float(np.arctan2(np.linalg.norm(np.cross(medium['orientation'],fine['orientation'])),
                                   np.dot(medium['orientation'],fine['orientation'])))
            checks[f's{seed}_refinement']=shift<=.01 and angle<=.001 and medium['time_s']==fine['time_s']
            refinement.append({'seed':seed,'position_shift_minor_radii':shift,'orientation_shift_rad':angle})
    after=sources();checks['sources_stable']=all(after.get(k)==v for k,v in before.items())
    result={'passed':bool(all(checks.values())),'checks':{k:bool(v) for k,v in checks.items()},'rows':rows,
            'refinement':refinement,'resolved_arguments':vars(args),'physical_config':cfg,
            'source_hashes_before':before,'source_hashes':after,'input_hashes':inputs,
            'started_utc':started,'completed_utc':datetime.now(timezone.utc).isoformat(),
            'environment':{'python':platform.python_version(),'numpy':np.__version__,'scipy':scipy.__version__},
            'scope':'bounded numerical verification; no population-release, retention or permeability inference'}
    p=out/'results.json';p.write_text(json.dumps(result,indent=2))
    (out/'completion.json').write_text(json.dumps({'status':'complete_passed' if result['passed'] else 'complete_failed','results_sha256':sha(p)}))
    print(json.dumps({'passed':result['passed'],'checks':result['checks'],'refinement':refinement},indent=2))
    if not result['passed']:raise SystemExit(1)


if __name__=='__main__':main()
