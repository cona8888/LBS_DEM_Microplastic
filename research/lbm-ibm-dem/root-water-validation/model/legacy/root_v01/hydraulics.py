"""Transient radial water uptake by one cylindrical root, per metre of root.

SI units. Horizontal annular section of a homogeneous rigid unsaturated soil,
constant gas pressure, no gravity component along r, osmotic gradient or axial
xylem resistance. Soil/atmosphere reference: h=(p_w-p_a)/(rho_w*g) in metres.
Positive Q [m²/s] flows from the outer soil into the root. Q times the physical
length of a uniform root segment is its volumetric flow [m³/s]. This continuum
verification case is independent of the pore-scale simulator.
"""
from argparse import ArgumentParser
from dataclasses import asdict, dataclass
from pathlib import Path
import csv
import json

import numpy as np
from scipy.integrate import quad
from scipy.linalg import solve_banded
from scipy.optimize import brentq


@dataclass(frozen=True)
class Soil:
    theta_r: float = 0.065
    theta_s: float = 0.43
    alpha_per_m: float = 3.6
    n: float = 1.6
    k_sat_m_per_s: float = 2.0e-6

    def __post_init__(self):
        if not all(np.isfinite(list(asdict(self).values()))):
            raise ValueError("Soil coefficients must be finite")
        if not (0 <= self.theta_r < self.theta_s <= 1 and self.n > 1
                and self.alpha_per_m > 0 and self.k_sat_m_per_s > 0):
            raise ValueError("Invalid van Genuchten–Mualem coefficients")

    def properties(self, h):
        """Water content [-], d(theta)/dh [1/m], and K [m/s], Mualem l=0.5."""
        x = self.alpha_per_m * np.maximum(-np.asarray(h), 0.)
        z = x ** self.n
        m = 1. - 1. / self.n
        se = (1. + z) ** -m
        theta = self.theta_r + (self.theta_s - self.theta_r) * se
        capacity = ((self.theta_s - self.theta_r) * m * self.n
                    * self.alpha_per_m * x**(self.n - 1.) * se / (1. + z))
        with np.errstate(divide="ignore"):  # z=0 gives bracket=1 at saturation
            bracket = -np.expm1(-m * np.log1p(1. / z))
        return theta, capacity, self.k_sat_m_per_s * np.sqrt(se) * bracket**2


@dataclass(frozen=True)
class RootCase:
    root_radius_m: float = 0.001
    outer_radius_m: float = 0.020
    bulk_head_m: float = -2.0
    xylem_head_m: float = -6.0
    membrane_per_s: float = 1.e-8  # water flux [m/s] per metre of pressure head

    def __post_init__(self):
        if not all(np.isfinite(list(asdict(self).values()))):
            raise ValueError("Root case coefficients must be finite")
        if not (0 < self.root_radius_m < self.outer_radius_m
                and self.membrane_per_s >= 0 and self.bulk_head_m < 0
                and self.xylem_head_m < 0):
            raise ValueError("Need 0<a<R, nonnegative conductance and unsaturated heads")


class RadialRichards:
    """Conservative backward-Euler FV on logarithmically spaced annuli."""

    def __init__(self, cells=64, case=RootCase(), soil=Soil()):
        if int(cells) != cells or cells < 2:
            raise ValueError("Use at least two integer cells")
        self.case, self.soil = case, soil
        self.faces = np.geomspace(case.root_radius_m, case.outer_radius_m, int(cells) + 1)
        self.r = np.sqrt(self.faces[:-1] * self.faces[1:])
        self.vol = np.pi * np.diff(self.faces**2)  # bulk volume per unit length, m²
        self.log_left = np.log(self.r / self.faces[:-1]) / (2*np.pi)
        self.log_right = np.log(self.faces[1:] / self.r) / (2*np.pi)
        self.membrane = 2*np.pi*case.root_radius_m*case.membrane_per_s

    def faces_and_fluxes(self, h, hydraulic_k):
        """Shell resistances in series, including both half-cells and membrane."""
        left = self.log_left / hydraulic_k
        right = self.log_right / hydraulic_k
        face_g = np.empty(h.size + 1)
        face_g[0] = self.membrane / (1. + self.membrane * left[0])
        face_g[1:-1] = 1. / (right[:-1] + left[1:])
        face_g[-1] = 1. / right[-1]
        return face_g, face_g * np.diff(np.r_[self.case.xylem_head_m, h, self.case.bulk_head_m])

    def solve(self, old, dt=None):
        """One implicit time step [s], or the discrete steady state when dt=None."""
        old = np.asarray(old, dtype=float)
        if old.shape != self.r.shape or not np.all(np.isfinite(old)) or np.any(old >= 0):
            raise ValueError("Initial heads must be finite negative cell values")
        if dt is not None and (not np.isfinite(dt) or dt <= 0):
            raise ValueError("dt must be positive and finite")
        inv_dt = 0. if dt is None else 1. / dt
        old_theta = self.soil.properties(old)[0]
        h = old.copy()
        for _ in range(100):
            theta, capacity, hydraulic_k = self.soil.properties(h)
            face_g, q = self.faces_and_fluxes(h, hydraulic_k)
            residual = self.vol * (theta - old_theta) * inv_dt - np.diff(q)
            if np.sum(np.abs(residual)) <= 1e-20 + 1e-10*np.max(np.abs(q)):
                return h, q
            bands = np.zeros((3, h.size))
            bands[1] = self.vol*capacity*inv_dt + face_g[:-1] + face_g[1:]
            bands[0, 1:] = bands[2, :-1] = -face_g[1:-1]
            delta = solve_banded((1, 1), bands, -residual)
            h += delta
            if np.any(h >= 0.) or not np.all(np.isfinite(h)):
                raise RuntimeError("Nonlinear update left unsaturated domain. Reduce time step or head contrast.")
        raise RuntimeError("Richards modified Picard iteration failed to close the cell water budgets")


def continuum_steady(r, case=RootCase(), soil=Soil()):
    """Independent continuum solution from integrating K(h) dh = Q/(2π) d(log r)."""
    r = np.asarray(r)
    if (r < case.root_radius_m).any() or (r > case.outer_radius_m).any():
        raise ValueError("Benchmark radii must lie inside the soil annulus")
    hb, hx = case.bulk_head_m, case.xylem_head_m
    if case.membrane_per_s == 0 or hb == hx:
        return np.full(r.shape, hb), 0., hb
    log_span = np.log(case.outer_radius_m / case.root_radius_m)
    def potential(h0, h1):
        return quad(lambda h: soil.properties(h)[2], h0, h1, epsabs=1.e-23)[0]
    gm = 2*np.pi*case.root_radius_m*case.membrane_per_s
    hs = brentq(lambda h: potential(h, hb) - gm*(h-hx)*log_span/(2*np.pi),
                min(hx, hb), max(hx, hb))
    q = gm * (hs - hx)
    def at_radius(x):
        if x == case.root_radius_m:
            return hs
        if x == case.outer_radius_m:
            return hb
        target = q*np.log(x / case.root_radius_m)/(2*np.pi)
        return brentq(lambda h: potential(hs, h) - target, min(hs, hb), max(hs, hb))
    return np.array([at_radius(x) for x in r.flat]).reshape(r.shape), q, hs


def simulate(model, hours=24., dt_s=120., profile_times_s=None):
    """Start from bulk equilibrium and impose the xylem potential at t=0+."""
    if not np.isfinite([hours, dt_s]).all() or min(hours, dt_s) <= 0:
        raise ValueError("Duration and dt must be positive and finite")
    end = 3600*hours
    if profile_times_s is None:
        profile_times_s = end * np.array([0., 1/48, 1/8, 1/2, 1.])
    targets = np.unique(np.r_[0., profile_times_s, end])
    if not np.isfinite(targets).all() or targets[0] < 0 or targets[-1] > end:
        raise ValueError("Profile times must be inside the simulated duration")
    h = np.full(model.r.shape, model.case.bulk_head_m, dtype=float)
    theta, _, k = model.soil.properties(h)
    initial_store = model.vol @ theta
    _, q = model.faces_and_fluxes(h, k)
    t = uptake = supply = 0.
    history, profiles = [], []
    def record(snapshot):
        hs = model.case.xylem_head_m + q[0]/model.membrane if model.membrane else h[0]
        change = model.vol @ theta - initial_store
        history.append((t, hs, q[0], q[-1], change, uptake, supply, change + uptake - supply))
        if snapshot:
            radii = np.r_[model.faces[0], model.r, model.faces[-1]]
            heads = np.r_[hs, h, model.case.bulk_head_m]
            for radius, head, wc in zip(radii, heads, model.soil.properties(heads)[0]):
                profiles.append((t, radius, head, -9.80665*head, wc))
    record(True)
    for target in targets[1:]:
        while t < target:
            next_t = min(t + dt_s, target)
            step = next_t - t
            h, q = model.solve(h, step)
            theta = model.soil.properties(h)[0]
            uptake += step * q[0]
            supply += step * q[-1]
            t = next_t
            record(t == target)
    return history, profiles


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parent / "results")
    parser.add_argument("--cells", type=int, default=64)
    parser.add_argument("--hours", type=float, default=24.)
    parser.add_argument("--dt", type=float, default=120., help="Maximum time step [s]")
    parser.add_argument("--xylem-head", type=float, default=-6., help="Xylem pressure head [m]")
    parser.add_argument("--bulk-head", type=float, default=-2., help="Outer pressure head [m]")
    parser.add_argument("--membrane", type=float, default=1.e-8, help="Membrane conductance per area [1/s]")
    args = parser.parse_args()
    case = RootCase(xylem_head_m=args.xylem_head, bulk_head_m=args.bulk_head,
                    membrane_per_s=args.membrane)
    model = RadialRichards(args.cells, case)
    history, profiles = simulate(model, args.hours, args.dt)
    args.output.mkdir(parents=True, exist_ok=True)
    for name, headers, data in [
        ("hydraulic_profile.csv", ["time_s","radius_m","pressure_head_m","suction_kPa","theta_m3_per_m3"], profiles),
        ("hydraulic_budget.csv", ["time_s","root_surface_head_m","root_inward_m2_per_s",
          "outer_inward_m2_per_s","storage_change_m2","root_cumulative_m2","outer_cumulative_m2",
          "water_budget_defect_m2"], history),
    ]:
        with (args.output/name).open("w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            writer.writerows(data)
    exact_h, exact_q, exact_hs = continuum_steady(model.r, case, model.soil)
    discrete_h, discrete_q = model.solve(np.full(model.r.shape, case.bulk_head_m))
    diag = {
        "case": asdict(case), "soil": asdict(model.soil), "n_cells": args.cells,
        "duration_h": args.hours, "max_dt_s": args.dt, "completed_steps": len(history)-1,
        "steady_continuum_root_surface_head_m": exact_hs,
        "steady_continuum_uptake_m2_per_s": exact_q,
        "steady_discrete_uptake_m2_per_s": float(discrete_q[0]),
        "steady_max_head_error_m": float(np.max(np.abs(discrete_h-exact_h))),
        "steady_relative_uptake_error": float(abs(discrete_q[0]/exact_q - 1.)) if exact_q else None,
        "transient_max_abs_budget_defect_m2": float(max(abs(row[-1]) for row in history)),
        "transient_final_root_suction_kPa": -9.80665*history[-1][1],
        "transient_final_root_uptake_m2_per_s": float(history[-1][2]),
        "transient_cumulative_uptake_m2": float(history[-1][5]),
    }
    with (args.output/"hydraulic_diagnostics.json").open("w") as f:
        json.dump(diag, f, indent=2, allow_nan=False)
        f.write("\n")
    print(json.dumps(diag, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
