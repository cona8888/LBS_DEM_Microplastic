"""Compare equilibrium diffuse and reconstructed geometric bridge areas per unit depth.

Run from the RhizoField repository root. Output is an analysis of frozen
endpoint fields plus local equilibrium re-solves. No drying histories are run.
"""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import sys

import numpy as np


def positive_fraction(offset, half_x, half_y):
    """Fraction of a rectangle for which offset+gx*x+gy*y is positive.

    The two half-variation arrays are |gx|dx/2 and |gy|dy/2. Integrating a
    plane cut over a rectangle reduces to convolution of two uniform densities.
    """
    offset, half_x, half_y = np.broadcast_arrays(offset, half_x, half_y)
    p = np.maximum(half_x, half_y)
    q = np.minimum(half_x, half_y)
    a = np.abs(offset)
    tail = np.zeros(p.shape)
    middle = (p > 0) & (a <= p-q)
    tail[middle] = .5*(1.-a[middle]/p[middle])
    corner = (q > 0) & (p-q < a) & (a < p+q)
    tail[corner] = (p[corner]+q[corner]-a[corner])**2/(8*p[corner]*q[corner])
    return np.where(offset == 0, .5, np.where(offset > 0, 1.-tail, tail))


def directional_slope(values, centres, axis):
    """Derivatives from fluid neighbours only; one-sided on the raster walls."""
    a = np.moveaxis(values, axis, -1)
    left, right = np.full_like(a, np.nan), np.full_like(a, np.nan)
    slope = np.diff(a, axis=-1)/np.diff(centres)
    left[..., 1:] = slope
    right[..., :-1] = slope
    # Centre-to-centre secant across the whole two-neighbour interval is
    # exact for a planar field on stretched/nonuniform cells.
    dl, dr = np.r_[0., np.diff(centres)], np.r_[np.diff(centres), 0.]
    num = np.nan_to_num(left)*dl + np.nan_to_num(right)*dr
    den = np.isfinite(left)*dl + np.isfinite(right)*dr
    result = np.divide(num, den, out=np.zeros_like(num), where=den>0)
    return np.moveaxis(result, -1, axis)


def geometric_area(phi, xedge, yedge, threshold=0.):
    """Reconstructed superlevel area inside the fluid raster; solids are NaN."""
    dx, dy = np.diff(xedge), np.diff(yedge)
    gx = directional_slope(phi, (xedge[1:]+xedge[:-1])/2, 1)
    gy = directional_slope(phi, (yedge[1:]+yedge[:-1])/2, 0)
    frac = positive_fraction(phi-threshold, .5*abs(gx)*dx, .5*abs(gy)*dy[:, None])
    return float(np.sum(np.where(np.isfinite(phi), frac, 0.) * dx * dy[:,None]))


def areas(mesh, phi, mu, dx0):
    field = mesh.map(phi)
    xedge = mesh.edge*dx0
    yedge = (np.arange(field.shape[0]+1)*mesh.hy-.5)*dx0
    branches = np.sort(np.roots([1., 0., -1., -mu]))
    if np.iscomplexobj(branches):
        raise ValueError("Field has no stable gas and liquid bulk branches")
    pg, pl = branches[[0,-1]]
    aub = float(mesh.V @ ((phi-pg)/(pl-pg))*dx0**2)
    return dict(phase_area_m2=float(mesh.water(phi)*dx0**2), branch_area_m2=aub,
                zero_area_m2=geometric_area(field,xedge,yedge),
                midpoint_area_m2=geometric_area(field,xedge,yedge,(pg+pl)/2),
                minus01_area_m2=geometric_area(field,xedge,yedge,-.1),
                plus01_area_m2=geometric_area(field,xedge,yedge,.1))


def readout(mesh, phi, dx0):
    _, g = mesh.energy_grad(phi)
    mu = (g@mesh.V)/(mesh.V@mesh.V)
    return areas(mesh, phi, mu, dx0)


def analysis(repo, scale):
    sys.path.insert(0, str(repo))
    from applications.rhizofield.field import Mesh, DX
    from applications.rhizofield.run import connected
    from validation_water.validate import check_frozen
    from validation_water.width_check import refine_from_fine
    check_frozen()
    profiles = json.loads((repo/'calibration/results/profiles.json').read_text())
    theta = profiles['grain_wall_inputs_deg']['25um']
    out = Path(__file__).resolve().with_name('fixtures')
    results = []
    input_digests = {
        'root':'2c132ca4e1b7abd094b97df8965cc31465e53269f5425a60926d3f384bd80057',
        'outer':'b1c2b0d89a168e479e9d4d39bc5be2c86b4de990492ed16a0019b3c86e545fc6',
    }
    for mode,expected in input_digests.items():
        endpoint = out/f'paired_s2_n18_{mode}.npz'
        if hashlib.sha256(endpoint.read_bytes()).hexdigest() != expected:
            raise ValueError(f"Endpoint digest changed for {mode}")
        with np.load(endpoint) as saved:
            labels, guess = refine_from_fine(saved['labels'],saved['phi'],scale)
            original_inventory = float(saved['near'])/DX**2
            gap = float(saved['gap'])
        target = None
        for width in (2.5,1.25):
            mesh = Mesh(labels,gap,grain_deg=theta,interface_width=width)
            base = mesh.solve(guess,original_inventory)
            def add(state, protocol):
                if not connected(mesh,state):
                    raise RuntimeError('Endpoint lost its connected bridge')
                a = readout(mesh,state.phi,DX)
                results.append(dict(mode=mode,grid_um=50/scale,width_um=width*50,protocol=protocol,
                    force_N_m=state.force,suction_Pa=-state.psi,solver_residual=state.residual,
                    target_zero_area_m2=target if target is not None else a['zero_area_m2'],**a))
                return a['zero_area_m2']
            measured = add(base,'fixed_phase_inventory')
            if width==2.5:
                target = measured
                continue
            # Invert the measurement on this same connected branch. All trials
            # use the existing conservative minimiser; no new force law or fit.
            last_a, last_g, state = original_inventory, measured, base
            derivative = DX**2
            for _ in range(10):
                if abs(last_g-target) <= 5e-6*target:
                    add(state,'matched_zero_area')
                    break
                if derivative <= 0.:
                    raise RuntimeError("Nonmonotonic area mapping")
                new_a = last_a + (target-last_g)/derivative
                state = mesh.solve(state.phi,new_a)
                new_g = readout(mesh,state.phi,DX)['zero_area_m2']
                derivative = (new_g-last_g)/(new_a-last_a)
                last_a, last_g = new_a, new_g
            else:
                raise RuntimeError("Target reconstructed liquid area was not matched")
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo',type=Path,default=Path.cwd())
    parser.add_argument('--output',type=Path,default=Path(__file__).with_name('volume_mapping_refined.csv'))
    parser.add_argument('--scales',nargs='+',type=int,choices=(2,4),default=[2,4])
    args = parser.parse_args()
    rows = [row for scale in args.scales for row in analysis(args.repo.resolve(),scale)]
    with args.output.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=rows[0])
        w.writeheader()
        w.writerows(rows)
    for scale in args.scales:
        for width,p in [(125.,'fixed_phase_inventory'),(62.5,'fixed_phase_inventory'),(62.5,'matched_zero_area')]:
            a,b=[r for r in rows if r['grid_um']==50/scale and r['width_um']==width and r['protocol']==p]
            print(f"{50/scale:g} um, W={width:g} um, {p}: contrast {100*(a['force_N_m']/b['force_N_m']-1):+.5f}%")
if __name__=='__main__':
    main()
