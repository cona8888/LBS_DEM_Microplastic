# Stage30a selected low-concentration CPD4 confirmation

## Physical question

Are the Stage29e one-fibre representative and four-fibre paired topology effects stable when the hydraulic voxel resolution is doubled from CPD2 to CPD4?

## Frozen system boundary

- One fixed 216-grain periodic Leighton Buzzard Sand packing.
- Static, mechanics-qualified F37 fibre centrelines; no particle or fibre motion during flow.
- The accepted D3Q19 GPU LBM solver, forcing, fluid properties, periodic boundaries, convergence checks, and permeability estimator remain unchanged.
- New CPD4 cases: clean control, isolated single fibre from block B, four-fibre zero-contact block B, and its paired one-contact block B.
- Previously accepted Stage28c CPD4 clean/separated/crossing results are lineage evidence and are not rerun.

Block B is selected before execution because its Stage29e CPD2 one-fibre response is near the three-block mean and its four-fibre paired topology contrast is near the three-block mean. This is numerical solution verification, not a new random replicate.

## Observables and acceptance

Primary observable: paired permeability ratio `k/k0`.

- Every record, convergence, health, equilibrium-closure, artifact-hash, and balance check must pass.
- The clean CPD4 conductance must reproduce the accepted Stage27b/Stage28c clean value to relative error no larger than `1e-12`.
- Each non-clean CPD2-to-CPD4 ratio shift must have absolute magnitude no larger than `0.002`.
- The change in the paired four-fibre contrast `(one-contact - zero-contact)` must have absolute magnitude no larger than `0.001`.
- All selected fibre cases must remain obstructive relative to clean.
- The four-fibre zero-contact case must remain more obstructive than its paired one-contact case.

No monotonic concentration law is imposed.

## Claim boundary and authority

This checkpoint can support only CPD2-to-CPD4 numerical stability for selected fixed-packing, static-flow mechanisms. It cannot validate laboratory permeability or support population inference, mechanics reruns, moving sand, fibre migration, clogging, deformation, transient response, or two-way coupling.

This contract authorizes geometry construction and independent audit. GPU execution requires a separate hash-bound release.
