"""Conservative, nondimensional pore-scale capillary equilibrium on fixed masks.

Order parameter phi is +1 for liquid and -1 for gas. Cells and time have
arbitrary consistent lattice units. The bulk free-energy density A has pressure
units in the chosen system. width is the denominator of the planar tanh profile.
All quantities and plots here are nondimensional; no SI mapping is assumed.
"""
import argparse
import csv
import json
from pathlib import Path

import numpy as np
from scipy import sparse
from scipy.fft import dctn, idctn
from scipy.sparse.linalg import factorized


class PoreField:
    """Cell-centred finite volumes; outer boundary is neutral and impermeable.

    Internal labels are 0 fluid, 1 grain or 2 root. A wetting angle is measured
    through water. Faces between fluid cells conduct chemical-potential flux;
    there is no flux across any fluid-solid or exterior face. Wetting energies
    are applied along the Cartesian exposed faces of each mask. Stair-step
    geometry limits contact-angle accuracy, especially for small curved grains.
    """
    def __init__(self, solid, phi, dx=1., width=2., A=1., mobility=0.12,
                 theta_grain_deg=90., theta_root_deg=90.):
        self.solid = np.asarray(solid)
        if self.solid.ndim != 2 or not np.isin(self.solid, [0, 1, 2]).all():
            raise ValueError("solid must be a 2D array with labels 0, 1 or 2")
        self.fluid = self.solid == 0
        phi = np.asarray(phi, dtype=float)
        if phi.shape != self.solid.shape or not self.fluid.any() or not np.isfinite(phi[self.fluid]).all():
            raise ValueError("phi must supply a finite value at each fluid cell")
        if not all(np.isfinite(v) and v > 0 for v in (dx, width, A, mobility)):
            raise ValueError("dx, width, A and mobility must be finite and positive")
        if not all(np.isfinite(v) and 0 <= v <= 180 for v in (theta_grain_deg, theta_root_deg)):
            raise ValueError("contact angles must lie in [0, 180] degrees")
        self.dx, self.width, self.A, self.mobility = dx, width, A, mobility
        self.kappa = A * width**2 / 2
        self.sigma = 2 * A * width / 3
        self._x = phi[self.fluid].copy()
        self._cache_dt = None
        self.time = 0.
        self._wall = np.zeros(self._x.size)
        ids = np.full(self.solid.shape, -1)
        ids[self.fluid] = np.arange(self._x.size)
        pairs = []
        wall_cos = np.cos(np.deg2rad([90, theta_grain_deg, theta_root_deg]))
        wall_cos[np.abs(wall_cos) < 1e-15] = 0.
        for a, b in ((np.s_[:-1, :], np.s_[1:, :]), (np.s_[:, :-1], np.s_[:, 1:])):
            fa, fb = ids[a], ids[b]
            both = (fa >= 0) & (fb >= 0)
            pairs.append((fa[both], fb[both]))
            for left, right, label in ((fa, fb, self.solid[b]), (fb, fa, self.solid[a])):
                wall = (left >= 0) & (right < 0)
                np.add.at(self._wall, left[wall], wall_cos[label[wall].astype(int)])
        left, right = [np.concatenate([p[i] for p in pairs]) for i in (0, 1)]
        rows, cols = np.r_[left, right], np.r_[right, left]
        n = self._x.size
        adjacency = sparse.coo_matrix((np.ones(rows.size), (rows, cols)), shape=(n, n)).tocsr()
        self._lap = (adjacency - sparse.diags(np.asarray(adjacency.sum(axis=1)).ravel())) / dx**2
        self._eigs = None
        if self.fluid.all():
            ny, nx = self.solid.shape
            eig_y = -4*np.sin(np.pi*np.arange(ny)/(2*ny))**2 / dx**2
            eig_x = -4*np.sin(np.pi*np.arange(nx)/(2*nx))**2 / dx**2
            self._eigs = eig_y[:, None] + eig_x[None, :]

    def _field(self, x):
        f = np.full(self.fluid.shape, np.nan)
        f[self.fluid] = x
        return f

    @property
    def phi(self):
        return self._field(self._x)

    def _local_mu(self, x):
        # Wall free energy per area h = -sigma*cos(theta)*(3*phi-phi**3)/4.
        return self.A*x*(x*x - 1) - 0.75*self.sigma*self._wall*(1 - x*x)/self.dx

    def _mu(self):
        return self._local_mu(self._x) - self.kappa*(self._lap @ self._x)

    def chemical_potential(self):
        return self._field(self._mu())

    def bulk_pressure(self):
        """Order-parameter pressure phi*mu-f in each cell (bulk sampling only).

        Away from the interface and walls |grad phi| tends to zero, so this is
        the isotropic thermodynamic pressure relative to an arbitrary constant.
        It is not a local scalar pressure inside a diffuse interface. There the
        reversible pressure tensor has additional gradient contributions.
        """
        return self._field(self._x*self._mu() - self.A*(self._x**2-1)**2 / 4)

    def mass(self):
        """Conserved integral of phi over fluid cells, per unit depth."""
        return float(np.sum(self._x) * self.dx**2)

    def energy(self):
        x = self._x
        bulk = self.A*(x*x - 1)**2/4
        gradient = -0.5*self.kappa*x*(self._lap @ x)
        wall = -self.sigma*self._wall*(3*x-x**3)/(4*self.dx)
        return float(np.sum(bulk+gradient+wall)*self.dx**2)

    def step(self, dt, n=1):
        """Semi-implicit stabilized CH update. The graph Laplacian conserves mass."""
        if not np.isfinite(dt) or dt <= 0 or not isinstance(n, (int, np.integer)) or n < 0:
            raise ValueError("positive finite dt and nonnegative integer n required")
        t = self.mobility*dt
        stab = 3*self.A
        if dt != self._cache_dt:
            if self._eigs is None:
                lap = self._lap
                system = sparse.eye(lap.shape[0]) - t*stab*lap + t*self.kappa*(lap @ lap)
                self._solve = factorized(system.tocsc())
            else:
                self._den = 1 - t*stab*self._eigs + t*self.kappa*self._eigs**2
            self._cache_dt = dt
        for _ in range(n):
            rhs = self._x + t*(self._lap @ (self._local_mu(self._x)-stab*self._x))
            if self._eigs is None:
                self._x = self._solve(rhs)
            else:
                rhs = rhs.reshape(self.fluid.shape)
                self._x = idctn(dctn(rhs, type=2, norm="ortho")/self._den,
                                 type=2, norm="ortho").ravel()
        self.time += dt*n


def bubble_case(radius=12., width=2.5, dt=12., steps=1500):
    """Closed 2D square containing a gas bubble; s=p_g-p_w = sigma/R."""
    side = int(4*radius)+1
    y, x = np.indices((side, side))
    center = (side-1)/2
    r = np.hypot(x-center, y-center)
    sigma = 2*width/3
    phi = np.tanh((r-radius)/width) - sigma/(4*radius)
    sim = PoreField(np.zeros_like(x), phi, width=width)
    m0 = sim.mass()
    sim.step(dt, steps)
    order = sim.phi
    pressure = sim.bulk_pressure()
    # Interpolate phi=0 radially along a centreline after relaxation.
    mid = int(center)
    line = order[mid, mid:]
    j = np.flatnonzero(line >= 0)[0]
    measured = j-1 - line[j-1]/(line[j] - line[j-1])
    p_g = float(np.mean(pressure[r < measured - 3.2*width]))
    p_w = float(np.mean(pressure[r > measured + 3.2*width]))
    analytic = sim.sigma / measured
    return dict(radius_initial=radius, radius_measured=float(measured), sigma=sim.sigma,
                p_g=p_g, p_w=p_w, suction=p_g-p_w, laplace=analytic,
                relative_error=abs((p_g-p_w)/analytic-1),
                max_minus_min_mu=float(np.ptp(sim.chemical_potential())),
                mass_drift_per_pore_area=abs(sim.mass()-m0)/order.size)


def root_pore():
    """Wetting relaxation of an initially imposed water lens in a root–grain gap."""
    y, x = np.indices((54, 72))
    s = np.zeros(x.shape, int)
    for cx, cy, r in ((41, 26, 8), (41, 3, 8), (51, 48, 10), (67, 24, 10), (15, 52, 7)):
        s[(x-cx)**2 + (y-cy)**2 <= r*r] = 1
    s[(x-12)**2+(y-26)**2 <= 9**2] = 2
    distance_approx = (np.hypot((x-27)/12., (y-26)/7.) - 1)*7
    sim = PoreField(s, -np.tanh(distance_approx/2.), width=2.,
                    theta_root_deg=60, theta_grain_deg=70)
    return sim


def plot_map(csv_path, output_dir):
    import matplotlib
    matplotlib.use("Agg")
    matplotlib.rcParams["svg.fonttype"] = "none"
    import matplotlib.pyplot as plt
    from matplotlib.colors import ListedColormap
    table = np.genfromtxt(csv_path, names=True, delimiter=",")
    shape = (1+int(table["y"].max()), 1+int(table["x"].max()))
    phi = table["phi"].reshape(shape)
    solid = table["solid"].reshape(shape)
    fig, ax = plt.subplots(figsize=(6, 4.3), constrained_layout=True)
    from matplotlib.colors import LinearSegmentedColormap
    cmap = LinearSegmentedColormap.from_list("pore", ["#f8f6ee", "#9dd8de", "#00718c"])
    edges_x = np.arange(shape[1]+1)-.5
    edges_y = np.arange(shape[0]+1)-.5
    im = ax.pcolormesh(edges_x, edges_y, phi, cmap=cmap, vmin=-1, vmax=1)
    ax.pcolormesh(edges_x, edges_y, np.ma.masked_equal(solid, 0),
                  cmap=ListedColormap(["#88877c", "#a06335"]), vmin=1, vmax=2)
    ax.set_aspect("equal")
    ax.contour(phi, levels=[0.], colors=["#124452"], linewidths=0.9)
    ax.text(12, 26, "Root", ha="center", va="center", color="white", weight="bold")
    ax.text(41, 26, "Grain", ha="center", va="center", color="white", weight="bold")
    ax.set(xlabel="Horizontal distance, x / Δx", ylabel="Vertical distance, y / Δx")
    fig.colorbar(im, ax=ax, label="Phase field, φ   (−1 gas, +1 water)", shrink=0.78)
    for ext in ("svg", "pdf", "png"):
        fig.savefig(output_dir/f"pore_field.{ext}", dpi=170)
    plt.close(fig)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", type=Path, default=Path("results"))
    p.add_argument("--replot", action="store_true", help="render the existing pore_map.csv")
    args = p.parse_args()
    args.output.mkdir(exist_ok=True, parents=True)
    target = args.output/"pore_map.csv"
    if args.replot:
        plot_map(target, args.output)
        return
    sim = root_pore()
    initial_energy, initial_mass = sim.energy(), sim.mass()
    sim.step(3., 1200)
    y, x = np.indices(sim.solid.shape)
    data = np.column_stack([x.ravel(), y.ravel(), sim.solid.ravel(), sim.phi.ravel(),
                            sim.chemical_potential().ravel()])
    np.savetxt(target, data, delimiter=",", header="x,y,solid,phi,mu", comments="",
               fmt=["%d", "%d", "%d", "%.9g", "%.9g"])
    plot_map(target, args.output)
    bubbles = [bubble_case(radius=r) for r in (12., 16., 20.)]
    with (args.output/"pore_laplace.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=bubbles[0].keys())
        w.writeheader()
        w.writerows(bubbles)
    summary = dict(initial_energy=initial_energy, final_energy=sim.energy(),
                   initial_mass=initial_mass, final_mass=sim.mass(),
                   mass_drift_per_pore_area=abs(sim.mass()-initial_mass)/sim.fluid.sum(),
                   root_theta_deg=60., grain_theta_deg=70., dt=3., steps=1200,
                   fluid_cells=int(sim.fluid.sum()), max_minus_min_mu=float(np.nanmax(sim.chemical_potential())-np.nanmin(sim.chemical_potential())),
                   bubble_cases=bubbles)
    (args.output/"pore_checks.json").write_text(json.dumps(summary, indent=2)+"\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
