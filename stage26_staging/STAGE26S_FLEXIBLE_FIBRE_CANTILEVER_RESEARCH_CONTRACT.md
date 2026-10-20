# Stage26s — Flexible-Fibre Cantilever Verification Contract

## Purpose

Verify that a nonperiodic YADE `GridNode`/`GridConnection` chain can represent the small-deflection bending of one F37-like microplastic fibre before that representation is allowed near sand.

## Bound evidence

- Stage26r checkpoint SHA-256: `817ebec07709ddf66844dd40a87f3c39214afeac6855057ad97b3d993e450225`.
- Stage26r finding: exact fixed-cell radius restoration unjams the 216-sphere state; this does not invalidate the independently accepted Stage25 stress-controlled sand state.
- Stage26p mechanism checkpoint SHA-256: `a87dc95e2f3c15af25ac1fb90669fe73cde8ae6a8ddd46a1302ef1add956ef3d`.

## Model and test

- Fibre centreline length: 0.900 mm.
- Circular diameter: 0.100 mm.
- Nominal density: 940 kg/m3.
- Nominal Young modulus: 53 MPa, used only as a numerical reference—not a calibrated polymer property.
- Straight, initially unstressed, nonperiodic cantilever; gravity disabled.
- First node fully clamped; a transverse tip load is ramped quasi-statically.
- Target Euler–Bernoulli tip deflection: 1% of length (9 micrometres).
- Analytical reference: `delta = F L^3 / (3 E I)`, with `I = pi d^4 / 64`.
- Meshes: 19, 37, and 73 nodes, including both endpoints.
- YADE's installed grid-connection constitutive mapping must be probed and recorded before interpreting the comparison.

## Acceptance gates

1. All source/config/output hashes bind and all values are finite.
2. The clamped node remains fixed to numerical precision.
3. The terminal response is quasi-static: tip-speed and force-residual gates pass.
4. Terminal displacement remains below 5% of fibre length.
5. The analytical-comparison convention is explicit and identical for all meshes.
6. The 37-to-73-node displacement change is at most 5%.
7. The 73-node displacement differs from the declared analytical reference by at most 10%, unless the API probe proves YADE's native stiffness mapping is not equivalent to `EI`; in that case Stage26s closes as a documented model-form nonacceptance, without fitting the result.

## Authority

This contract authorizes:

- read-only YADE API/source inspection;
- one immutable constitutive/API probe;
- one immutable three-mesh standalone cantilever benchmark;
- evaluation and rendering of those results.

This contract does **not** authorize:

- polymer-property calibration;
- contact calibration against sand;
- insertion into the sand specimen;
- periodic use of `GridConnection` fibres;
- DEM–fluid coupling, permeability, migration, deformation, or a production parametric study.

The run must fail closed. A failed gate is evidence, not permission to tune the modulus or rerun under looser limits.
