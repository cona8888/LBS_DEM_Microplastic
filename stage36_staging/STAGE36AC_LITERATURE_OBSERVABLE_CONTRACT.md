# Stage36AC — literature-observable compatibility contract

## Scientific question

Can the verified release ledger and the currently assembled literature evidence support an independent validation of PET-fibre release from an initially contaminated sand matrix?

## System and observable definitions

The intended production observable is preloaded-matrix release:

`R_matrix(t) = M_PET,downstream(t) / M_PET,initially_inside`.

Its complement is instantaneous retained inventory inside the modeled matrix only when upstream loss is zero and all PET remains tagged:

`F_retained(t) = 1 - R_matrix(t)`.

The Boos et al. flume observable is a reach-storage balance after an upstream pulse injection:

`S_reach(t) = 1 - cumulative_M_out(t) / cumulative_M_in(t)`.

The Ameen et al. observable is recovered outlet mass divided by injected mass. Neither is definitionally identical to release from a preloaded matrix. The permeability-clogging observations are `K(t)/K0` and contain no release fraction.

## Compatibility rules

1. Never compare numerical `R_matrix` directly with `S_reach` as though they were the same quantity.
2. Pulse-recovery data may validate a future pulse-injection transport configuration only when inlet mass, outlet mass, observation reach, duration, particle material/shape/size, sand grading, flow, and censoring are reproduced.
3. Preloaded release requires a preloaded experimental comparator or an explicitly labeled prediction-only campaign.
4. Sphere data may test a sphere branch; it cannot validate fibre shape, bending, entanglement, or textile-derived retention.
5. Figure/text endpoints remain external validation data. `concFIT_export.txt` is quarantined and cannot supply calibration or integrated targets.
6. No acceptance tolerance will be invented without measurement uncertainty, replicate variability, or a justified engineering tolerance.

## Readiness gates

- Accounting gate: Stage36B must pass and expose tagged downstream inventory, gross outward/return mass, complete exits, pore volumes flushed, and balance residual.
- Physics gate: particle motion, hydrodynamic force/torque, contact retention and outlet treatment must be verified.
- Boundary-condition gate: numerical initial/boundary conditions must match the selected experimental observable.
- Comparator gate: raw or published endpoint provenance and preprocessing must be auditable.
- Validation gate: acceptance thresholds must be frozen before predictions.

Stage36AC is a CPU-only metadata/readiness audit. It launches no DEM, LBM, GPU or transport simulation and changes no accepted evidence.
