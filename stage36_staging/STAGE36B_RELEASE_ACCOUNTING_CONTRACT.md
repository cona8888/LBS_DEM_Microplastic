# Stage36B: bounded release-accounting verification

6 September 2026. Scope: the next accounting-verification step requested after Stage36A. CPU-only analytical geometry and prescribed-coordinate tests; no fluid solver, DEM dynamics, GPU use, material calibration or soil release prediction.

## Model and definitions frozen before tests

The test body is a uniform-density straight capsule aligned with x: a cylinder of centreline length L with two hemispherical caps of radius r. L >= 0 admits the sphere limit; r and body mass are positive. Each immutable body ID has one mass and one shape. Only its centre x changes. Initial bodies must lie wholly within the observation interval [a,b].

Capsule cross-sectional area is pi*r^2 inside the cylinder and pi*(r^2-s^2) in a cap, where s is distance from the cylinder end. Integrating this area gives the fraction before an axial plane. Analytical volume is pi*r^2*L + 4*pi*r^3/3. Tests compare the implemented normalized integral with independently integrated cross-sectional areas and exact hemisphere/centre values.

At every snapshot, partition each body's mass into upstream, inside and downstream compartments. The partition concerns material volume, not centre crossing or first-node crossing. All body IDs remain present, even after full exit. No numerical deletion or absorbing boundary is implemented.

Downstream net exterior fraction is current downstream mass/M0. Gross outward mass sums positive per-body increments; gross return mass sums negative increments in magnitude. Net exterior mass equals gross outward minus gross return because initial exterior mass is zero. Gross outward mass can exceed M0 after recrossing and MUST NOT be called unique cumulative release. Opposite-direction bodies in one step are counted separately before aggregation.

Complete-body exit events use the trailing extremity, not the centre. Count both event occurrences and unique body IDs ever wholly outside. Recrossing may create repeated complete-exit events but cannot duplicate a unique ID. Event time is only bracketed by snapshots. Motion is prescribed and piecewise monotone in x within each interval; unobserved substep reversals cannot be inferred and lie outside the verification claim.

Step input includes separately integrated inlet and outlet water volumes; do not assume equal volumes. Pore volumes flushed use cumulative inlet water volume/Vp0. The diagnostic outward-mass/collected-water ratio is undefined (null) when collected water is zero; a moving-body accounting fixture with no water is not a physical effluent concentration prediction. Negative water volumes/backflow are rejected in v1. PET reverse motion remains supported.

## Acceptance criteria

- Relative PET inventory residual and signed crossing ledger residual <= 1e-12 for finite double-precision fixtures. This is a bookkeeping tolerance, not transport-model accuracy.
- Exact ID completeness and uniqueness; positive finite registered masses and radii, nonnegative finite lengths; valid finite planes and strictly increasing times.
- Analytic symmetry and known half-volume fractions within 1e-12 absolute fraction.
- Independent composite-midpoint integration at 32, 128 and 512 cells over each smooth axial piece: maximum fraction error at finest <= 1e-5; error decreases on the selected off-grid clipping fixtures. Geometry quadrature only, not flow-grid convergence.
- Monotone prescribed paths sampled with 8, 32 and 128 intervals: same final net/gross mass within 1e-12 relative; exact event count. This verifies accounting sampling, not dynamics timestep convergence.
- Invalid input must fail without changing time, cumulative water, crossing counters or inventory state.
- Test normal, micro-scale and dimensionlessly rescaled fixtures, no motion, partial exit, full exit, reverse crossing, upstream escape, multiple IDs and both-end partition.
- Bind parent Stage36A design and all its recorded source hashes before tests; preserve each test attempt in a new directory. No overwriting previous artifacts.

## Boundaries and next gate

These tests do not establish a general curved/rotating fibre volume clipper, arbitrary surface crossing detection, physical forces, contact, capture, permanent retention, finite-time immobilization, fracture or coupling. Shapes from Stage31/34 are not fed to this axial-only code. The Stage36A soil pilot remains unready.

Next after a pass: design and qualify general-centreline/solid-volume outlet accounting and the single-fibre fluid-force/torque benchmark interface. Do not extrapolate an accounting pass to approval of a soil-flushing campaign.
