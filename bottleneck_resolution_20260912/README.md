# Contact-loop bottleneck resolution

See [REPORT.md](REPORT.md) for measured outcomes and qualification limits.
Historical stages remain unchanged. The candidate combines the corrected
explicit trajectory with Stage53 ordinary contact and Stage70 recovery order;
the cold PGS and SOR loops are compiled. Its exact-cycle guard stops only
provably repeated, nonconvergent outer iterations of the audited deterministic
solver. It keeps the same rejection and timestep-halving behavior.

## Run the bounded verification

From `C:/MATDEM_MICROPLASTIC`, choose new output directories:

```powershell
python bottleneck_resolution_20260912/src/run_cycle_verification.py --mode smoke --kernel blas --output bottleneck_resolution_20260912/evidence/smoke_repeat
python bottleneck_resolution_20260912/src/run_bottleneck_verification.py --mode local --kernel blas --budget 120 --output bottleneck_resolution_20260912/evidence/local_blas_repeat
python bottleneck_resolution_20260912/src/run_cycle_verification.py --mode crossing --kernel blas --seeds 2 --budget 300 --output bottleneck_resolution_20260912/evidence/crossing_repeat
python bottleneck_resolution_20260912/src/run_cycle_verification.py --mode refinement --kernel blas --seeds 1 2 3 --levels 1 0.5 0.25 --horizon 0.02 --budget 120 --output bottleneck_resolution_20260912/evidence/refinement_repeat
```

The BLAS-only `local` check runs the baseline and candidate serially from the
same saved mechanical state. `crossing` starts from the original Stage55 pose and targets 0.05 seconds
past its previous failure. `refinement` rebuilds the full dynamics at each
step and scales all four time bounds together. These commands perform bounded
numerical checks, not the six-case study or physical validation. Each trace
records rejected attempts as well as accepted ones. Final JSON records are
written before console summaries; nonfinite diagnostic values are explicitly
labelled rather than silently changed to valid numbers.

## Python integration

Add this directory's `src` to `sys.path`, then:

```python
from cycle_model import make_cycle_contact_model
from driver_consolidated import integrate

model = make_cycle_contact_model()
result = integrate(field, geometry, position, orientation, velocity,
                   a, b, viscosity, particle_density, fluid_density,
                   gravity, friction, outlet, horizon, contact_model=model)
```

Use the public validated solvers; the compiled `cold_loop` is an internal
kernel and must not receive arbitrary shapes or storage layouts. Keep each
trajectory's model instance separate. Reaction forces are not warm-started
between solves.

The cycle factory intentionally accepts no custom solver injection. The lower
level `inertial_cycle_guard.ContactModel` defaults cycle detection off; enabling
it for a new solver requires proving that repeated full map inputs have
identical outputs and that no hidden state changes selection. See the
[proof and verification](CYCLE_GUARD_PROOF.md). An exact cycle proves failure of
this iteration at this timestep, not physical jamming or absence of a solution.

## Qualified runtime and reproducibility

The local compiler dependencies are isolated in `deps` and pinned in
`requirements-compiler.txt`. The existing environment supplies Python3.12,
NumPy2.3.1 and SciPy1.16.0. The arithmetic-preserving backend requires Windows
and the recorded NumPy OpenBLAS0.3.29 ILP64 DLL. It checks the version and ABI
and uses that same DLL for dot products, matrix-vector products and norms.
It does not substitute SciPy's BLAS library or enable fast-math/parallel
reductions. JIT code containing library function pointers is not disk-cached.

These choices follow the installed NumPy implementation of
[matrix multiplication](https://github.com/numpy/numpy/blob/v2.3.1/numpy/_core/src/umath/matmul.c.src)
and [vector norms](https://github.com/numpy/numpy/blob/v2.3.1/numpy/linalg/_linalg.py).
[Numba's installation documentation](https://numba.readthedocs.io/en/stable/user/installing.html)
describes its wheel-based LLVM dependency and version compatibility.
Source reasoning is backed by direct force/residual trace comparisons here;
library compatibility alone does not prove numerical equivalence.

Runs record source and input hashes, DLL hash/configuration, versions, processor,
thread environment and compilation/setup cost. Requalify the backend after a
NumPy, BLAS, compiler, architecture or relevant thread-setting change. Historical
`health.iterations` mixes counters and omits some failed work; use per-branch
wall times and separate work counters. Untouched reference fallback evaluation
counts remain unknown where the historical code does not expose them.

The initial scalar-summation compiled candidates remain in this directory as
failed performance experiments. They are not the `blas` backend and must not
be substituted merely because their local force differences look small.
