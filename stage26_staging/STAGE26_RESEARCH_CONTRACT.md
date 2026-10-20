# Stage26 research contract — dry F37 insertion into qualified LBS sand

## Question and bounded claim

Can one rigid, kinked F37 polyethylene-fibre surrogate be inserted as a two-grain bridge into the frozen Stage25a 216-particle LBS packing and relax at 100 Pa without destroying the qualified sand contact network?

Passing supports only a small-assembly dry-mechanical compatibility checkpoint for subsequent fibre-mixture design. It does not calibrate polyethylene or LBS contacts and does not support permeability, migration, transient fluid–structure interaction, or deformation-coupled-flow claims.

## System and scales

- Three-dimensional periodic cell loaded from the accepted Stage25a `mu_0.60` YADE checkpoint.
- 216 spherical LBS-PSD grains; initial void ratio 0.73858 and compression-positive mean effective stress 99.993 Pa.
- One rigid F37 clump: 37 overlapping 50 µm-radius spheres, 1.0 mm contour length, 0.10 mm nominal diameter, aspect ratio 10, single kink.
- The resulting nominal dry mass fraction is 0.00460 wt%, matching the lowest approximately 0.005 wt% screening level.
- Gravity is zero. The periodic controller maintains 100 Pa isotropic effective stress while the inserted fibre relaxes.

## Model assumptions

- Sand remains spherical and uses the Stage25 preparation contact model.
- The fibre is rigid; member overlap resolves its surface but does not represent polymer flexibility.
- Sand–plastic stiffness is deliberately matched to the sand contact stiffness for this numerical compatibility pilot. Friction and polymer stiffness are uncalibrated nuisance assumptions.
- Placement is deterministic, periodic-clearance aware, and initially bridges two distinct sand grains with sub-percent member-radius penetration.
- No fluid, chemistry, degradation, migration, tensile adhesion, rolling resistance, or fibre breakage is included.

## Observables and acceptance

- Mean effective stress and principal stress errors, compression positive, Pa.
- Unbalanced force and kinetic energy normalized by `pV`.
- Sand-network coordination after iterative degree-less-than-two rattler pruning and rattler fraction.
- Real sand–sand and sand–fibre contacts; distinct contacted sand grains.
- Maximum inter-object penetration normalized by the smaller contacting radius.
- Sand displacement from the frozen checkpoint using periodic minimum-image distance.
- Fibre centre-of-mass displacement, rotation, and tip-span drift.
- Periodic-cell volume drift.

The run passes only after five consecutive equilibrium blocks satisfying every predeclared gate. Exactly 216 sand grains and one 37-member fibre must remain. The fibre must retain at least two distinct sand contacts and the sand network must remain load bearing.

## Evidence roles

- Stage25a: qualified initial state and immutable source evidence.
- Stage26 placement search: geometry verification only.
- Stage26 YADE relaxation: numerical and dry-mechanical compatibility qualification.
- No calibration or experimental validation is performed in Stage26.

