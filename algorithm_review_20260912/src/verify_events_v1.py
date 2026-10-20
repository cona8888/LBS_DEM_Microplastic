"""Independent analytic first-passage and endpoint-Re regression checks."""
import argparse
import hashlib
import json
import platform
import sys
from pathlib import Path
import numpy as np
import scipy
import exit_event_v1 as event
import trajectory_explicit_v1 as trajectory

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'stage41_staging'))
from verify_trajectory_optimized_v1 import Field, Empty


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=False)
    a,b = 2e-4,5e-5
    p = np.array([np.sin(.01),np.cos(.01),0])
    support0 = event.mechanics.support([1,0,0],p,a,b)
    distance = (b+support0)/2
    x = np.array([.01+distance,0,0])
    v = np.array([0,0,0,0,0,a*.02])
    analytic = (.01-np.arcsin(np.sqrt((distance**2-b**2)/(a*a-b*b))))/.02
    observed = event.linear_pose_exit_time(x,p,v,a,b,.01,1.0)
    old = event.mechanics.linear_pose_exit_time(x,p,v,a,b,.01,1.0)
    checks = {'old_misses_exit_return': old is None,
              'first_exit_return_matches_analytic': observed is not None and abs(observed-analytic)<=1e-9}
    repeated=[]
    for dt in (1.,.5,.25):
        time=0.;xx=x.copy();pp=p.copy();found=None
        for _ in range(round(1/dt)):
            part=event.linear_pose_exit_time(xx,pp,v,a,b,.01,dt)
            if part is not None:
                found=time+part;break
            xx,pp=event.mechanics.advance_pose(xx,pp,v,a,dt);time+=dt
        repeated.append(found)
    checks['three_partitions_same_first_passage'] = all(t is not None and abs(t-analytic)<1e-9 for t in repeated)
    checks['no_exit_rotation'] = event.linear_pose_exit_time([.01+b-1e-6,0,0],p,v,a,b,.01,1.) is None
    checks['linear_sphere_exact'] = event.linear_pose_exit_time([0,0,0],[1,0,0],[.1,0,0,0,0,0],b,b,.01,1.) == (.01+b)/.1
    checks['initial_exit_is_zero'] = event.linear_pose_exit_time([.011,0,0],p,v,a,b,.01,0.) == 0.

    class VaryingField:
        def __init__(self, origin=0.0, slope=10000.0):
            self.origin, self.slope = origin, slope

        def sample(self,pos):
            # Manufactured frozen-step forcing: start flow zero, endpoint large.
            # This tests applicability accounting, not flow-model accuracy.
            return np.array([self.slope*(pos[0]-self.origin),0,0]), np.zeros((3,3))

    common=dict(a=b,b=b,viscosity=.001002,particle_density=1380.,fluid_density=998.2,
                added_mass_fraction=1,gravity=[0,0,0],friction=0,
                displacement_fraction=100.,relaxation_fraction=100.,max_dt=.01)
    endpoint=trajectory.integrate(VaryingField(),Empty(),[0,0,0],[1,0,0],[.02,0,0,0,0,0],
                                  outlet=.01,horizon=.01,**common)
    initial_x = 1e-4
    outlet=trajectory.integrate(VaryingField(initial_x,1e5),Empty(),[initial_x,0,0],[1,0,0],[.02,0,0,0,0,0],
                                outlet=initial_x-b+1e-6,horizon=.01,**common)
    checks['actual_endpoint_Re_checked'] = (endpoint['status']=='unresolved_model'
        and endpoint['reason']=='endpoint particle Reynolds number exceeds declared envelope'
        and endpoint['max_reynolds']>3)
    # Whole-body exit requires only 1 micrometre of translation in this fixture.
    # The local fluid velocity at that event is 0.1 m/s. Check the exact branch;
    # an endpoint rejection does not verify the fractional-outlet safeguard.
    checks['actual_outlet_Re_checked'] = (outlet['status']=='unresolved_model'
        and outlet['reason']=='outlet particle Reynolds number exceeds declared envelope'
        and outlet['max_reynolds']>3)
    checks={k:bool(v) for k,v in checks.items()}
    result={'passed':bool(all(checks.values())),'checks':checks,'analytic_time_s':analytic,
            'observed_time_s':observed,'partition_times_s':repeated,'endpoint':endpoint,'outlet':outlet,
            'environment':{'python':platform.python_version(),'numpy':np.__version__,'scipy':scipy.__version__},
            'source_hashes':{str(path.resolve()):hashlib.sha256(path.read_bytes()).hexdigest()
                             for path in [Path(__file__),Path(event.__file__),Path(trajectory.__file__)]},
            'claim':'analytic and manufactured code verification only'}
    (output/'results.json').write_text(json.dumps(result,indent=2))
    print(json.dumps({'passed':result['passed'],'checks':checks,'event_time_s':observed},indent=2))
    if not result['passed']:raise SystemExit(1)


if __name__=='__main__':main()
