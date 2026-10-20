# Stage31f selected replicated CPD4 confirmation

## Physical question and bounded claim

Does the replicated Stage31e CPD2 fibre-count signal remain numerically stable at CPD4 for a deliberately bounded subset that exercises both the strongest count trajectory and opposite high-count placement-block contrasts?

The supported claim is solution verification for selected fixed-solid geometries only. It is not absolute permeability validation, a population model, or evidence for moving-particle physics.

## Frozen system boundary

- Three-dimensional periodic hydraulic cells containing the already mechanics-qualified 216-grain Leighton Buzzard Sand packings.
- Static F37 fibre centrelines and static sand; no sand or fibre motion during flow.
- The accepted D3Q19 GPU LBM implementation, forcing, fluid properties, convergence rules, health checks, equilibrium closure, and conductance estimator remain frozen.
- Resolution is doubled from CPD2 (93 cubed) to CPD4 (186 cubed).
- Packing `n216_s1` is exactly identical to the accepted Stage27b/Stage30a CPD4 clean geometry, so that clean control is reused by immutable hash and is not rerun.
- Packing `n216_s2` requires one new matched CPD4 clean solve.

## Predeclared selected cases

Seven new CPD4 solves, in frozen order:

1. `s31b_n216_s2_clean`
2. `s31b_n216_s1_A_f001_open`
3. `s31b_n216_s1_A_f002_open`
4. `s31b_n216_s1_A_f004_open`
5. `s31b_n216_s1_B_f004_open`
6. `s31b_n216_s2_A_f004_open`
7. `s31b_n216_s2_B_f004_open`

Selection rationale:

- s1/block A is the strongest observed Stage31e trajectory and provides a nested 1-to-2-to-4 count comparison with one packing and one placement block held fixed.
- The s1 and s2 four-fibre A/B pairs have opposite CPD2 block-contrast signs, directly testing whether placement sensitivity is numerically stable rather than universal.
- s3 adds stochastic replication at CPD2 but no distinct selected numerical mechanism, so it is withheld from this costly resolution check.

## Observables and acceptance criteria

Primary observable: matched relative conductance `G/G_clean` (numerically identical to the paired permeability ratio under the frozen conversion).

- All seven new case records, convergence flags, health checks, exact equilibrium closures, force/momentum balances, and artifact hashes must pass.
- The reused s1 clean record, geometry, completion, and independent evaluation must remain hash-bound and passed.
- The new s2 clean conductance must be finite and positive; no absolute-permeability validation criterion is imposed.
- Every selected non-clean CPD4 ratio must remain below 1.
- Each selected CPD2-to-CPD4 ratio shift must have absolute magnitude no greater than 0.002.
- The s1 and s2 four-fibre `(B - A)` contrast shifts must each have absolute magnitude no greater than 0.001.
- The s1/block A 1-to-2-to-4 ordering is reported descriptively. No monotonic constitutive law is imposed or fitted.
- Geometry resolution must be exactly doubled, the sand phase must be identical within each packing, all fluids must span all axes, and each CPD4 fibre-union voxel count must be between 7 and 9 times its CPD2 count.

## Evidence roles and omissions

- Stage31e provides replicated CPD2 screening and stochastic/block variability.
- Stage31f provides selected CPD2-to-CPD4 solution verification.
- Stage30a/Stage27b supply only the exact reused s1 clean CPD4 evidence.
- No laboratory observation is used here; therefore no absolute permeability validation claim is allowed.
- No mechanics rerun, mobile sand, fibre migration, clogging, deformation, transient response, or two-way coupling is authorized.

## Handoff sequence

1. Build immutable CPD4 geometry and resolved configuration.
2. Independently audit all source hashes, rasterization, topology, warm starts, resource bounds, frozen case order, and authority.
3. Independently audit the frozen GPU runner and issue a hash-bound execution handoff.
4. Launch one immutable seven-case GPU process only when no competing GPU/YADE/LBM job exists.
5. Independently evaluate all records and render only after verified completion.
