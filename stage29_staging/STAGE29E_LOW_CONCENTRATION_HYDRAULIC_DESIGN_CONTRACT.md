# Stage29e mechanics-qualified low-concentration hydraulic design

## Question

How does permeability change from zero to four F37 fibres in one fixed 216-grain periodic LBS packing, and how does the qualified contact mechanism alter the response at two and four fibres?

## Evidence-backed design

The design uses mechanics states that already passed immutable evaluation:

- zero fibres: accepted clean control, reused rather than rerun;
- one fibre: three accepted Stage28a isolated controls;
- two fibres: one accepted separated pair and one accepted crossing pair from Stage28a;
- four fibres: three paired zero-contact/one-contact context blocks from Stage29d.

The achieved concentrations are 0, 0.004690960879927048, 0.009381481678218612, and 0.018761203277589126 dry-mass percent.

This is a deliberately unbalanced, sequential mechanism design. The three four-fibre context blocks estimate context sensitivity around one shared base pair. They are not independent crossing-location replicates. The two-fibre cases have no placement replication, so their difference is descriptive mechanism evidence rather than a population estimate.

## Hydraulic protocol

Terminal mechanics centrelines are voxelized into the unchanged clean-sand CPD2 domain. The clean pressure forcing, fluid properties, boundary conditions, convergence checks, balance checks, and permeability estimator remain frozen. Sand and fibres are static during flow.

Primary output: paired `k/k0`. No monotonicity is imposed. Effects smaller than 0.0002 in `k/k0` are classified as unresolved at the current numerical evidence level.

## Planned comparisons

1. Zero-contact concentration branch: clean, mean of three isolated singles, separated pair, mean of three four-fibre zero-contact contexts.
2. Contact branch: crossing pair and mean of three four-fibre one-contact contexts.
3. Four-fibre paired topology contrast: one-contact minus zero-contact within A, B, and C.
4. Context variability: raw points, mean, sample standard deviation, and paired differences.

No inferential variance is assigned to the unreplicated two-fibre cases. No claim is made about random packings, random fibre orientation, mixing, or laboratory-scale specimens.

## Authority

This contract authorizes design generation and independent design audit only. It does not authorize hydraulic geometry generation, GPU execution, CPD4 promotion, permeability claims, mechanics reruns, mobile sand, or coupling.
