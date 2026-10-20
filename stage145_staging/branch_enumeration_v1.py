"""Stage145: complete open/stick/slide enumeration for small contact sets.

Answers a question the residual and dissipation gates structurally cannot: is the
instantaneous Coulomb problem's solution UNIQUE at this state?  For n <= 3 contacts
it enumerates all 3^n modes; for each mode with sliding contacts it searches the
slide-direction angles on a periodic grid and polishes every local minimum of the
alignment misfit with a finite-difference Gauss-Newton iteration.  A mode is kept
only if its own reaction is inside the cones without polishing, its equations are
consistent to the declared ceiling, every unchanged physical gate passes, and its
mode inequalities hold.

Distinct branches are distinguished by GENERALIZED VELOCITY, not by reaction: on a
hyperstatic support the admissible reactions form a family that all share one
velocity, and that family dimension is reported separately.

Selection among several admissible branches is a DECLARED rule, never "most
constrained first" (which is a preference for sticking, and therefore for
retention).  With contact history: continuation -- the branch whose reaction is
closest to the previous one.  Without: Gauss's principle of least constraint,
the branch deviating least from the free motion in the kinetic metric.  Neither
rule inspects dwell, drift, position or any release observable.
"""
from itertools import product
import math

import numpy as np

OPEN, STICK, SLIDE = 0, 1, 2
MODE_NAMES = {OPEN: "open", STICK: "stick", SLIDE: "slide"}
GRID = (72, 24, 12)          # angular samples per sliding contact for n_slide = 1, 2, 3
MAX_MINIMA = 8


def prepare(system, delta_geom, contact_relative=1e-10):
    """Derived quantities shared by every mode evaluation."""
    v = np.asarray(system["vfree"], float)
    M = np.asarray(system["mobility"], float)
    J = np.asarray(system["jacobian"], float)
    g = np.asarray(system["gaps"], float)
    dt, mu = float(system["dt"]), float(system["mu"])
    A = J @ M @ J.T
    A = 0.5 * (A + A.T)
    n = len(g)
    scale = max(float(np.linalg.norm(v)), 1e-15)
    return {"v": v, "M": M, "J": J, "g": g, "dt": dt, "mu": mu, "n": n, "A": A, "z": J @ v,
            "scale": scale, "delta_geom": float(delta_geom),
            "ceiling": max(contact_relative * scale, float(delta_geom) / dt),
            "steps": np.array([np.linalg.eigvalsh(A[3*k+1:3*k+3, 3*k+1:3*k+3]).max() for k in range(n)])}


def _mode_rows(P, mode):
    rows, rhs = [], []
    for k in range(P["n"]):
        if mode[k] != OPEN:
            rows.append(P["A"][3*k, :])
            rhs.append(-(P["z"][3*k] + P["g"][k] / P["dt"]))
    for k in range(P["n"]):
        if mode[k] == STICK:
            for j in (1, 2):
                rows.append(P["A"][3*k+j, :])
                rhs.append(-P["z"][3*k+j])
    return np.array(rows).reshape(len(rows), 3*P["n"]), np.array(rhs)


def _mode_solve(P, mode, thetas):
    """Batched minimum-norm solve of a mode's equations over slide-direction angles."""
    n, mu = P["n"], P["mu"]
    closed = [k for k in range(n) if mode[k] != OPEN]
    sticks = [k for k in range(n) if mode[k] == STICK]
    slides = [k for k in range(n) if mode[k] == SLIDE]
    thetas = np.asarray(thetas, float)
    thetas = thetas.reshape(-1, len(slides)) if slides else np.zeros((1, 0))
    N = thetas.shape[0]
    m = len(closed) + 2 * len(sticks)
    if m == 0:
        return np.zeros((N, 3*n)), np.zeros(N), np.zeros((3*n, 0))
    Bf = np.zeros((N, 3*n, m))
    col = 0
    for k in closed:
        Bf[:, 3*k, col] = 1.0
        if mode[k] == SLIDE:
            th = thetas[:, slides.index(k)]
            Bf[:, 3*k+1, col] = -mu * np.cos(th)
            Bf[:, 3*k+2, col] = -mu * np.sin(th)
        col += 1
    for k in sticks:
        for j in (1, 2):
            Bf[:, 3*k+j, col] = 1.0
            col += 1
    R, d = _mode_rows(P, mode)
    C = R @ Bf
    u, s, vh = np.linalg.svd(C)
    keep = s > np.maximum(s[:, :1], 1e-300) * 1e-11
    sinv = np.where(keep, 1.0 / np.where(keep, s, 1.0), 0.0)
    kdim = s.shape[1]
    utd = np.einsum("nrk,r->nk", u[:, :, :kdim], d)
    x = np.einsum("nmk,nk->nm", np.transpose(vh, (0, 2, 1))[:, :, :kdim], sinv * utd)
    force = np.einsum("nfm,nm->nf", Bf, x)
    consistency = np.max(np.abs(np.einsum("nrm,nm->nr", C, x) - d[None, :]), axis=1) if len(d) else np.zeros(N)
    rank0 = int(keep[0].sum())
    family = Bf[0] @ vh[0, rank0:].T if rank0 < m else np.zeros((3*n, 0))
    return force, consistency, family


def _alignment(P, mode, forces, thetas):
    """[cross(v_t, d), max(0, -v_t.d)] per sliding contact, scaled."""
    vel = P["z"][None, :] + forces @ P["A"].T
    slides = [k for k in range(P["n"]) if mode[k] == SLIDE]
    out = np.zeros((len(forces), 2*len(slides)))
    for j, k in enumerate(slides):
        c, s = np.cos(thetas[:, j]), np.sin(thetas[:, j])
        vt = vel[:, 3*k+1:3*k+3]
        out[:, 2*j] = vt[:, 0]*s - vt[:, 1]*c
        out[:, 2*j+1] = np.maximum(0.0, -(vt[:, 0]*c + vt[:, 1]*s))
    return out / P["scale"]


def _misfit(P, mode, th):
    th = np.atleast_1d(np.asarray(th, float))[None, :]
    f, _, _ = _mode_solve(P, mode, th)
    return _alignment(P, mode, f, th)[0]


def _polish(P, mode, th0, m, iterations=40, h=1e-7):
    th = np.array(th0, float)
    E = np.eye(m) * h
    best = (np.inf, th.copy())
    for _ in range(iterations):
        pts = np.vstack([th[None, :], th[None, :] + E])
        f, _, _ = _mode_solve(P, mode, pts)
        r = _alignment(P, mode, f, pts)
        r0 = r[0]
        n0 = float(np.linalg.norm(r0))
        if n0 < best[0]:
            best = (n0, th.copy())
        if n0 <= 1e-13:
            break
        jac = ((r[1:] - r0[None, :]) / h).T
        step = np.linalg.lstsq(jac, -r0, rcond=1e-12)[0]
        if not np.isfinite(step).all():
            break
        alpha, moved = 1.0, False
        for _ls in range(12):
            trial = th + alpha * step
            ft, _, _ = _mode_solve(P, mode, trial[None, :])
            if float(np.linalg.norm(_alignment(P, mode, ft, trial[None, :])[0])) < n0:
                th, moved = trial, True
                break
            alpha *= 0.5
        if not moved:
            break
    return best[1]


def _local_minima(score, shape):
    S = score.reshape(shape)
    mask = np.ones_like(S, dtype=bool)
    for axis in range(S.ndim):
        for shift in (1, -1):
            mask &= S <= np.roll(S, shift, axis=axis)
    return np.flatnonzero(mask.ravel())


def _cone_ok(P, f):
    fs = max(np.linalg.norm(f), 1e-30)
    for k in range(P["n"]):
        i = 3*k
        if f[i] < 0 or np.linalg.norm(f[i+1:i+3]) > P["mu"]*f[i] + 1e-12*fs:
            return False
    return True


def _feasible_in_family(P, force0, family):
    """Hyperstatic mode: find a cone-feasible member of {f : J^T f = J^T f0}.

    Every member shares the same generalized velocity, so this only decides which
    reaction REPRESENTS the branch. Without it a hyperstatic branch whose minimum-norm
    representative grazes the cone is discarded, which silently loses real branches.
    Declared rule: minimum Euclidean norm among the feasible members.
    """
    if family.shape[1] == 0 or _cone_ok(P, force0):
        return force0
    from scipy.optimize import minimize
    n, mu = P["n"], P["mu"]
    fs = max(float(np.linalg.norm(force0)), 1e-30)
    F = family * fs                                  # y dimensionless: LP/SLSQP tolerances are absolute

    def cons(y):
        f = (force0 + F @ y).reshape(n, 3)
        return np.column_stack([f[:, 0], mu*f[:, 0] - np.linalg.norm(f[:, 1:], axis=1)]).ravel() / fs

    def cons_jac(y):
        f = (force0 + F @ y).reshape(n, 3)
        Fk = F.reshape(n, 3, -1)
        nt = np.maximum(np.linalg.norm(f[:, 1:], axis=1), 1e-300)
        row_n = Fk[:, 0, :]
        row_c = mu*Fk[:, 0, :] - np.einsum("kj,kjm->km", f[:, 1:]/nt[:, None], Fk[:, 1:, :])
        return np.stack([row_n, row_c], axis=1).reshape(2*n, -1) / fs

    def obj(y):
        f = force0 + F @ y
        return float(f @ f)/fs**2

    def obj_grad(y):
        return 2.0*(F.T @ (force0 + F @ y))/fs**2

    best = None
    rng = np.random.default_rng(145)
    for start in range(3):
        y0 = np.zeros(F.shape[1]) if start == 0 else rng.normal(size=F.shape[1])
        r = minimize(obj, y0, jac=obj_grad, method="SLSQP",
                     constraints={"type": "ineq", "fun": cons, "jac": cons_jac},
                     options={"ftol": 1e-13, "maxiter": 200})
        f = force0 + F @ r.x
        if cons(r.x).min() >= -1e-9 and (best is None or np.linalg.norm(f) < np.linalg.norm(best)):
            best = f
            if start == 0:
                break
    return force0 if best is None else best


def _gates(P, f):
    """The unchanged Stage50 physical gates, with the dt-consistent ceiling."""
    vel = P["z"] + P["A"] @ f
    residual = 0.0
    for k in range(P["n"]):
        i = 3*k
        residual = max(residual, abs(min(P["A"][i, i]*f[i], vel[i] + P["g"][k]/P["dt"])))
        t = f[i+1:i+3] - vel[i+1:i+3]/P["steps"][k]
        tn = np.linalg.norm(t)
        proj = t * min(1., P["mu"]*f[i]/max(tn, 1e-300))
        residual = max(residual, np.linalg.norm(f[i+1:i+3]-proj)*P["steps"][k])
    q = P["v"] + P["M"] @ P["J"].T @ f
    closure = float(np.linalg.norm(np.linalg.solve(P["M"], q - P["v"]) - P["J"].T @ f)
                    / max(np.linalg.norm(P["J"].T @ f), 1e-30))
    work = sum(float(f[3*k+1:3*k+3] @ vel[3*k+1:3*k+3]) for k in range(P["n"]))
    tnorm = sum(float(np.linalg.norm(f[3*k+1:3*k+3])) for k in range(P["n"]))
    work_ceiling = 1e-8*max(np.linalg.norm(f)*P["scale"], 1e-30) + tnorm*P["ceiling"]
    passed = (_cone_ok(P, f) and residual <= P["ceiling"] and closure <= 1e-8 and work <= work_ceiling)
    return bool(passed), {"residual": float(residual), "force_residual": closure,
                          "dissipation": float(-work), "velocity": q}


def _inequalities(P, mode, f, thetas):
    vel = P["z"] + P["A"] @ f
    slides = [k for k in range(P["n"]) if mode[k] == SLIDE]
    thetas = np.atleast_1d(np.asarray(thetas, float))
    for k in range(P["n"]):
        i = 3*k
        if mode[k] == OPEN and vel[i] + P["g"][k]/P["dt"] < -P["ceiling"]:
            return False
        if mode[k] == SLIDE:
            d = np.array([math.cos(thetas[slides.index(k)]), math.sin(thetas[slides.index(k)])])
            vt = vel[i+1:i+3]
            if vt @ d < -P["ceiling"] or np.linalg.norm(vt) <= P["ceiling"]:
                return False
        if mode[k] == STICK and np.linalg.norm(vel[i+1:i+3]) > 10*P["ceiling"]:
            return False
    return True


def enumerate_branches(system, delta_geom, contact_relative=1e-10):
    """All admissible branches, one entry per distinct generalized velocity."""
    P = prepare(system, delta_geom, contact_relative)
    if P["n"] > 3:
        raise ValueError("enumeration supports at most three contacts")
    found = []
    for mode in product((OPEN, STICK, SLIDE), repeat=P["n"]):
        slides = [k for k in range(P["n"]) if mode[k] == SLIDE]
        m = len(slides)
        if not m:
            candidates = [np.zeros(0)]
        else:
            per = GRID[min(m, len(GRID)) - 1]
            angles = 2*np.pi*np.arange(per)/per
            grid = np.array(list(product(angles, repeat=m)))
            f, cons, _ = _mode_solve(P, mode, grid)
            score = np.sum(np.abs(_alignment(P, mode, f, grid)), axis=1) + cons/P["scale"]
            minima = _local_minima(score, (per,)*m)
            minima = minima[np.argsort(score[minima])][:MAX_MINIMA]
            candidates = [_polish(P, mode, grid[i], m) for i in minima]
        for th in candidates:
            th = np.atleast_1d(np.asarray(th, float))
            if m and np.linalg.norm(_misfit(P, mode, th)) > 1e-9:
                continue
            f, cons, family = _mode_solve(P, mode, th[None, :] if m else th)
            if cons[0] > 10*P["ceiling"]:
                continue
            force = _feasible_in_family(P, f[0], family)
            if not _cone_ok(P, force):
                continue                      # no admissible reaction in this mode's family
            ok, report = _gates(P, force)
            if not ok or not _inequalities(P, mode, force, th):
                continue
            q = report["velocity"]
            for entry in found:
                if np.linalg.norm(entry["velocity"] - q) <= 1e-9*P["scale"] + 10*P["ceiling"]:
                    if np.linalg.norm(force) < np.linalg.norm(entry["force"]):
                        entry.update(force=force, mode=mode, report=report)
                    break
            else:
                found.append({"mode": mode, "mode_name": "/".join(MODE_NAMES[x] for x in mode),
                              "force": force, "velocity": q, "report": report,
                              "force_family_dimension": int(family.shape[1]),
                              "slide_directions": [float(x) for x in th]})
    return found, P


def branch_spread(branches):
    if len(branches) < 2:
        return 0.0
    return float(max(np.linalg.norm(a["velocity"] - b["velocity"]) for a in branches for b in branches))


def select_branch(branches, P, previous_force=None):
    """Declared, outcome-blind selection."""
    if len(branches) == 1:
        return branches[0], "unique"
    if previous_force is not None and len(previous_force) == len(branches[0]["force"]):
        return min(branches, key=lambda b: float(np.linalg.norm(b["force"] - previous_force))), "continuation_from_history"
    B = np.linalg.inv(P["M"])
    def constraint(b):
        d = b["velocity"] - P["v"]
        return float(d @ B @ d)
    return min(branches, key=constraint), "least_constraint_no_history"
