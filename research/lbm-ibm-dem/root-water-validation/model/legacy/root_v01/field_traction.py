"""Net force from a spatial equilibrium phase field on each immersed solid.

On a closed fluid contour enclosing one solid, integrate the Cauchy stress
T = -(phi*mu - f - kappa*|grad phi|^2/2) I - kappa grad(phi) grad(phi)^T.
The outward normal points from the enclosed control volume into external fluid.
A spatially constant pressure gauge integrates to zero. The full contour
must be in fluid and include both bulk and diffuse-interface portions.
This construction is valid in quasistatic equilibrium with no body forces.

The CSV contains dimensionless forces per out-of-plane depth. At dx = 50 um,
the 20- and 7-cell radii represent 1 mm and 0.35 mm respectively. For
gamma = 0.072 N/m, sigma_star = 5/3 gives P0 = gamma/(sigma_star*dx) =
864 Pa. Multiply F_star by P0*dx = 0.0432 N/m and torque_star by P0*dx**2
= 2.16e-6 N. Positive torques rotate counterclockwise. No physical time
mapping is assigned to Cahn-Hilliard relaxation.
"""
import argparse
import csv
import json
from pathlib import Path

import numpy as np
from scipy.ndimage import distance_transform_edt

from pore_field import PoreField


ROOT_CENTER = (28, 33)
ROOT_RADIUS = 20
GRAIN_RADIUS = 7
ANGLE_ROOT = 50.
ANGLE_GRAIN = 60.
WIDTH = 2.5


def make_case(gap, previous=None):
    """Fixed-volume continuation; opening by integer cells preserves pore area."""
    if not isinstance(gap, int) or not 9 <= gap <= 18:
        raise ValueError("gap must be an integer from 9 to 18")
    x0, y0 = ROOT_CENTER
    x1 = x0+ROOT_RADIUS+gap+GRAIN_RADIUS
    y, x = np.indices((67, 94))
    labels = np.zeros(x.shape, int)
    labels[(x-x0)**2+(y-y0)**2 <= ROOT_RADIUS**2] = 2
    labels[(x-x1)**2+(y-y0)**2 <= GRAIN_RADIUS**2] = 1
    if previous is None:
        lens_x = x0+ROOT_RADIUS+gap/2
        d = (np.hypot((x-lens_x)/(gap/2+6.), (y-y0)/5.8) - 1)*5.8
        phi = -np.tanh(d/WIDTH)
    else:
        # Extend formerly buried sites by their nearest old fluid value.
        # Conservatively redistribute the tiny mass difference over interface sites.
        previous_phi = previous.phi
        inds = distance_transform_edt(~previous.fluid, return_distances=False, return_indices=True)
        phi = previous_phi[tuple(inds)]
        fluid = labels == 0
        weights = np.maximum(1-phi**2, 0.)
        delta = previous.mass() - phi[fluid].sum()
        phi[fluid] += delta * weights[fluid] / weights[fluid].sum()
    return PoreField(labels, phi, width=WIDTH, theta_root_deg=ANGLE_ROOT,
                     theta_grain_deg=ANGLE_GRAIN)


def equilibrate(sim, tol=3.e-6, max_steps=10000, dt=20.):
    start_mass = sim.mass()
    for n in range(0, max_steps+1, 100):
        residual = float(np.ptp(sim.chemical_potential()[sim.fluid]))
        if residual <= tol:
            return n, residual, abs(sim.mass()-start_mass)/sim.fluid.sum()
        if n < max_steps:
            sim.step(dt, 100)
    raise RuntimeError(f"chemical potential range {residual:.3g}, tolerance {tol:.3g}")


def face_tractions(sim):
    """Positive-normal tractions on x and y faces of the uniform FV mesh.

    Compute normal derivatives by adjacent-cell differences and tangential
    derivatives by averaging centred cell derivatives. A stencil that touches
    a solid has NaN stress and is explicitly rejected by contour_force.
    """
    phi, mu, dx = sim.phi, sim.chemical_potential(), sim.dx
    gy, gx = np.gradient(phi, dx)
    result = []
    for axis, deriv_t in ((1, gy), (0, gx)):
        a, b = (np.s_[:,:-1], np.s_[:,1:]) if axis == 1 else (np.s_[:-1,:], np.s_[1:,:])
        n = (phi[b]-phi[a])/dx
        t = (deriv_t[b]+deriv_t[a])/2
        pf = (phi[a]+phi[b])/2
        mf = (mu[a]+mu[b])/2
        isotropic = pf*mf - sim.A*(pf*pf-1)**2/4 - sim.kappa*(n*n+t*t)/2
        normal, tangent = -isotropic - sim.kappa*n*n, -sim.kappa*n*t
        result.append(np.stack((normal,tangent) if axis == 1 else (tangent,normal), axis=-1))
    return result


def contour_force(sim, faces, label, padding):
    """Force and torque per depth on one solid, and inclusive rectangle bounds."""
    ys, xs = np.where(sim.solid == label)
    if len(xs) == 0:
        raise ValueError("solid not found")
    x0, x1 = xs.min()-padding, xs.max()+padding
    y0, y1 = ys.min()-padding, ys.max()+padding
    if x0 < 2 or y0 < 2 or x1+2 >= sim.solid.shape[1] or y1+2 >= sim.solid.shape[0]:
        raise ValueError("insufficient exterior fluid for centred stress stencil")
    region = sim.solid[y0:y1+1, x0:x1+1]
    if np.any((region != 0) & (region != label)):
        raise ValueError("contour contains another solid")
    tx, ty = faces
    sides = (tx[y0:y1+1,x1], -tx[y0:y1+1,x0-1], ty[y1,x0:x1+1], -ty[y0-1,x0:x1+1])
    if not all(np.isfinite(side).all() for side in sides):
        raise ValueError("stress stencil intersects a solid")
    # Outward tractions act at the physical face centres. The disk centroid
    # follows from its complete symmetric mask and is independent of padding.
    cx, cy = xs.mean(), ys.mean()
    yy, xx = np.arange(y0,y1+1), np.arange(x0,x1+1)
    points = ((x1+.5,yy),(x0-.5,yy),(xx,y1+.5),(xx,y0-.5))
    torque = sum(np.sum((px-cx)*side[:,1]-(py-cy)*side[:,0])
                 for (px,py),side in zip(points,sides))*sim.dx**2
    return np.sum([side.sum(axis=0) for side in sides], axis=0)*sim.dx, torque, (x0,x1,y0,y1)


def traction_rows(sim, gap):
    faces = face_tractions(sim)
    rows, details = [], []
    for body_id, label in ((0,2), (1,1)):
        forces, torques = [], []
        for pad in (2,3,4,5):
            force, torque, box = contour_force(sim, faces, label, pad)
            torques.append(torque)
            forces.append(force)
            details.append(dict(gap_star=gap, body_id=body_id, padding_cells=pad,
                                Fx_star=force[0], Fy_star=force[1],
                                x0=box[0], x1=box[1], y0=box[2], y1=box[3], torque_star=torque))
        mean = np.mean(forces, axis=0)
        spread = np.max(np.linalg.norm(np.asarray(forces)-mean, axis=1))
        rows.append(dict(gap_star=gap, body_id=body_id, Fx_star=mean[0], Fy_star=mean[1],
                         max_dev_star=spread, n_contours=len(forces), torque_star=np.mean(torques)))
    return rows, details


def save_rows(path, rows):
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=rows[0].keys())
        w.writeheader()
        w.writerows(rows)


def plot(out):
    import matplotlib
    matplotlib.use("Agg")
    matplotlib.rcParams["svg.fonttype"] = "none"
    import matplotlib.pyplot as plt
    from matplotlib.colors import ListedColormap, LinearSegmentedColormap
    from matplotlib.patches import Rectangle
    m = np.genfromtxt(out/"pore_traction_map.csv", delimiter=",", names=True)
    details = np.genfromtxt(out/"pore_traction_contours.csv", delimiter=",", names=True)
    rows = np.genfromtxt(out/"pore_traction.csv", delimiter=",", names=True)
    gap = int(m["gap_star"][0])
    d = details[details["gap_star"] == gap]
    s = rows[rows["gap_star"] == gap]
    shape = (int(m["y"].max()+1),int(m["x"].max()+1))
    solid, phi = m["solid"].reshape(shape), m["phi"].reshape(shape)
    fig, ax = plt.subplots(figsize=(6.5,4.4), constrained_layout=True)
    xx, yy = np.arange(shape[1]+1)-.5, np.arange(shape[0]+1)-.5
    cmap = LinearSegmentedColormap.from_list("fluid", ["#f7f5ed", "#a7dce1", "#00758c"])
    im = ax.pcolormesh(xx, yy, phi, cmap=cmap, vmin=-1, vmax=1)
    ax.pcolormesh(xx, yy, np.ma.masked_equal(solid,0), cmap=ListedColormap(["#85877e","#a7673e"]),vmin=1,vmax=2)
    for rr in d[d["padding_cells"]==3]:
        ax.add_patch(Rectangle((rr["x0"]-.5,rr["y0"]-.5),rr["x1"]-rr["x0"]+1,rr["y1"]-rr["y0"]+1,
                               fill=False,linestyle=(0,(3,2)),lw=1,color="#544553"))
    for i, cx in ((0,ROOT_CENTER[0]),(1,ROOT_CENTER[0]+ROOT_RADIUS+gap+GRAIN_RADIUS)):
        vx, vy = float(s["Fx_star"][s["body_id"]==i][0]),float(s["Fy_star"][s["body_id"]==i][0])
        cy = ROOT_CENTER[1]
        ax.annotate("",xy=(cx+2*vx,cy+2*vy),xytext=(cx,cy),arrowprops=dict(arrowstyle="-|>",lw=2,color="white"))
    ax.set(aspect="equal",xlabel="Horizontal distance, x / Δx",ylabel="Vertical distance, y / Δx")
    fig.colorbar(im, ax=ax, label="Phase field, φ   (−1 gas, +1 water)", shrink=.8)
    for ext in ("svg","pdf","png"):
        fig.savefig(out/f"pore_traction_field.{ext}",dpi=170)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=Path,default=Path("results"))
    parser.add_argument("--replot",action="store_true")
    args = parser.parse_args()
    out = args.output
    out.mkdir(exist_ok=True, parents=True)
    if args.replot:
        plot(out)
        return
    rows, details, checks = [], [], []
    previous = None
    for gap in (10,12,14):
        sim = make_case(gap,previous)
        n, residual, drift = equilibrate(sim)
        rr, dd = traction_rows(sim,gap)
        forces = np.array([[row["Fx_star"], row["Fy_star"]] for row in rr])
        magnitudes = np.linalg.norm(forces, axis=1)
        if not np.all(magnitudes > 0):
            raise RuntimeError("The water bridge produced no capillary load")
        contour_spread = max(row["max_dev_star"]/magnitude for row, magnitude in zip(rr, magnitudes))
        imbalance = np.linalg.norm(forces.sum(axis=0))/magnitudes[0]
        water_area = float(np.sum((1+sim.phi[sim.fluid])/2))
        if checks and abs(water_area-checks[0]["water_area_star"]) > 1.e-6:
            raise RuntimeError("Opening the gap failed to preserve the phase inventory")
        if (forces[0,0] <= 0 or forces[1,0] >= 0 or imbalance > 0.01
                or contour_spread > 0.01 or drift > 1.e-8):
            raise RuntimeError("Capillary equilibrium failed sign, contour, phase or pair-balance check")
        summary = dict(gap_star=gap,steps=n,range_mu=residual,mass_drift_per_pore_area=float(drift),
                       water_area_star=water_area, net_relative=float(imbalance),
                       max_relative_contour_deviation=float(contour_spread))
        print(summary, [(r["Fx_star"],r["max_dev_star"]) for r in rr], flush=True)
        checks.append(summary)
        rows.extend(rr)
        details.extend(dd)
        if gap == 12:
            y,x = np.indices(sim.solid.shape)
            matrix = np.column_stack((np.full(x.size,gap),x.ravel(),y.ravel(),sim.solid.ravel(),sim.phi.ravel(),sim.chemical_potential().ravel()))
            np.savetxt(out/"pore_traction_map.csv",matrix,delimiter=",",header="gap_star,x,y,solid,phi,mu",
                       fmt=["%d","%d","%d","%d","%.10g","%.10g"],comments="")
        previous = sim
    control = make_case(12)
    uniform = PoreField(control.solid, -np.ones(control.solid.shape),
                        width=WIDTH,theta_root_deg=ANGLE_ROOT,theta_grain_deg=ANGLE_GRAIN)
    uniform.step(1., 1)
    control_rows, _ = traction_rows(uniform,12)
    save_rows(out/"pore_traction_uniform.csv",control_rows)
    save_rows(out/"pore_traction.csv",rows)
    save_rows(out/"pore_traction_contours.csv",details)
    (out/"pore_traction_checks.json").write_text(json.dumps(checks,indent=2)+"\n")
    plot(out)


if __name__ == "__main__":
    main()
