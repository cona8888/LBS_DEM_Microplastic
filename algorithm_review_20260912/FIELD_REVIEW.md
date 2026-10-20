# Exact field-sampling optimization

The new `src/wall_field_exact_v1.py` removes repeated stencil-index construction
and the 24 temporary arrays and reductions used for two-factor gradient
products in each field sample. It retains the Stage39 eight-cell periodic
trilinear interpolation, stencil order, three-factor velocity reduction,
gradient multiplication order, finite-state checks, and exactly zero native
solid-cell values. It changes no field data, wall location, geometry, physical
parameter, contact law, integration bound or tolerance.

Use it explicitly after the existing matrix loader:

```python
from wall_field_exact_v1 import WallCellFieldExact
field = WallCellFieldExact.from_field(field)
```

The wrapper references the same velocity and fluid arrays. There is no cache of
sampled velocities or gradients and no redefinition of an older module global.
Constructor validation is inherited from Stage39. In particular, this change
does not silently tighten or loosen the reference constructor's domain.

## Verification evidence

`evidence/wall_field_exact_01/results.json` records source hashes before and
after execution, versions, seed, invocation and measurements. All 11 checks
passed. Across 3,480 queries with spacing from 1e-12 to 1e5 and velocity amplitude
from 1e-12 to 1e6, candidate and reference velocity and gradient arrays had zero
numerical difference. Queries covered unwrapped positions, periodic wraps, cell
centres, boundary-adjacent floating values, and 3,416 mixed fluid/solid stencils.
Input arrays remained unchanged and caller mutation did not yield stale values.
Invalid positions and invalid constructor inputs retained the same exceptions.

An independent multilinear polynomial check at 256 interior positions had
maximum absolute velocity error 1.33e-15 and gradient error 6.00e-15 in its
manufactured consistent units, below the declared 2e-13 threshold.

Five alternating-order repetitions of the 174-query field microbenchmark gave
a median speedup of 1.94 times. This is a sampler benchmark, not an overall
trajectory or campaign speedup.

The independent paired trajectory check in
`evidence/wall_field_trajectory_01/results.json` subsequently passed all six
Stage55 initial-state cases: three packings, each with the prolate and its
equal-volume sphere, at a 0.02 s horizon. The unchanged Stage53 contact solver
was used for both field implementations, with recovery unused. All result
values except runtime were identical, including status, position, orientation,
generalized velocity, accepted/rejected step counts, history and health. Binary
comparison also matched every field sample, geometry query pose and contact
trial velocity/timestep; every contact trial's full health output matched.
The source and input hashes were stable. Raw traces and case records are saved
beside the aggregate evidence. Each prolate run took 26 accepted steps and each
sphere run took 16. These short original-start paths do not qualify the later
difficult contact corridor or a full release horizon.

Trajectory wall times were collected while other work was running on the host;
they are descriptive observations, not an independent whole-trajectory speed
measurement. No contact solver optimization was included in this field check.

Reproduce from `C:/MATDEM_MICROPLASTIC` into a fresh evidence directory:

```powershell
python algorithm_review_20260912/src/verify_wall_field_exact_v1.py --output algorithm_review_20260912/evidence/wall_field_exact_new
python algorithm_review_20260912/src/verify_wall_field_trajectory_v1.py --output algorithm_review_20260912/evidence/wall_field_trajectory_new --seeds 1 2 3 --horizon 0.02 --budget 30
```

## Review of other opportunities

Stage41 already uses analytical straight-segment distance for sphere sweeps,
hoisted Rodrigues factors for prolate sweeps, and exact-pose contact caching.
Those optimizations are retained; duplicate implementations are unnecessary.
Replacing four bounded prolate sweep searches with an assumed global or
single-interval minimum would require a new numerical justification and is not
an exact implementation optimization.

The later Stage55–66 cost failures involve repeated contact solver work and
very slow progress in the difficult fibre corridor. Faster field sampling can
reduce a routine per-step cost, but does not by itself solve those failures.
The Stage66 proposed solver portfolio must still pass full trajectory and
refinement gates; a locally passing root solve is insufficient.

The current Python environment has no installed numba, Cython or llvmlite.
No cl, clang, gcc or cmake was found on PATH, and the inspected Visual Studio2022
tree contained no cl.exe, clang.exe or vcvars64.bat. No compiler or dependencies
were installed for this work.

## Scientific boundary

Identical interpolation does not validate the voxel wall location, pointwise
flow sampling for a finite body, near-wall hydrodynamic closure, or a frozen
one-way flow field. The scientific claim boundary remains conditional passage
of an initialized mobile body in the declared periodic window. This work adds
no evidence for a soil-column release fraction or time-dependent permeability.
