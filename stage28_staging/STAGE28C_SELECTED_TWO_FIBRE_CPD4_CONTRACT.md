# Stage28c selected two-fibre CPD4 solution-verification contract

## Question and bounded claim

Determine whether the paired permeability effects measured at CPD2 for the
accepted two-fibre `separated_open_open` and `crossing_interaction` states are
stable when the lattice is refined from 93 cubed (CPD2) to 186 cubed (CPD4).
This is numerical solution verification of a fixed-solid pore-scale model. It
is not a concentration law, a mobile-fibre simulation, or two-way coupling.

## Frozen system

- Periodic 216-sphere Leighton Buzzard sand geometry and equivalent cell size.
- Accepted Stage28a Revision-2 terminal 37-node fibre centrelines.
- Fibre radius 50 micrometres and all physical fluid properties.
- Stage27b-qualified CPD4 D3Q19 GPU-LBM solver, forcing, convergence, health,
  balance, and warm-start scaling.
- Three cases only, in order: `clean`, `separated_open_open`, and
  `crossing_interaction`.

The clean CPD4 geometry is reused byte-for-byte from accepted Stage27b. The two
fibre cases are rerasterized from the immutable Stage28b centrelines at 186
cubed. No geometry is moved or tuned after inspecting hydraulic results.

## Predeclared acceptance

- Every solver record and all inherited convergence, Mach, Reynolds, density,
  force, torque, and momentum-balance checks pass.
- The clean CPD4 conductance reproduces the accepted Stage27b clean CPD4 value
  within a relative tolerance of 1e-12.
- For each non-clean case, the absolute CPD2-to-CPD4 paired-ratio shift is no
  greater than 0.002.
- Both non-clean ratios remain below one.
- `crossing_interaction` remains more obstructive than
  `separated_open_open`.
- The CPD2-to-CPD4 shift in the crossing-minus-separated contrast is no greater
  than 0.001 in absolute permeability-ratio units.

If a criterion fails, preserve the run and report failed solution verification;
do not retune, rerun, or reinterpret it as a physical concentration trend.

## Execution and authority boundary

CPD2 final fields may be resampled as declared warm starts using velocity scale
0.5 and density-deviation scale 0.125. Raw CPD2 and CPD4 outputs remain
separate and immutable. Geometry construction authorizes only an independent
design audit. A passed audit may authorize one immutable three-case GPU run,
followed by independent evaluation and rendering. Production concentration,
mobile mechanics, migration, clogging, deformation, and two-way coupling remain
unauthorized.
