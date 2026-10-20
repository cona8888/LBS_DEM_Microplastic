# Stage26b dry multi-fibre concentration qualification

## Physical question

Can the frozen 216-grain Leighton Buzzard Sand assembly support increasing numbers of rigid F37 polyethylene fibre surrogates at 100 Pa while retaining a quasi-static load-bearing sand network and mechanically engaged fibres?

This is a dry-mechanical compatibility and placement-variability study. It does not predict permeability and it is not a physical model of specimen mixing.

## System boundary

- Three-dimensional periodic cell loaded isotropically to 100 Pa effective stress.
- Frozen Stage25 pure-sand state is the common baseline for every independent case.
- Sand grains remain spherical. Each microplastic fibre is the accepted rigid F37 clump: 37 overlapping 50-micrometre spheres, 1 mm contour length and nominal aspect ratio 10.
- Gravity, pore fluid, capillarity, fibre flexibility, surface chemistry, degradation, migration and imposed deformation are excluded.
- Contact parameters remain the uncalibrated Stage26a compatibility values. They cannot support claims about real polyethylene-sand strength or mixing behaviour.

## Concentration ladder

The exact fibre counts are 0, 1, 2, 4, 8, 13 and 21. For the frozen sand mass these correspond to 0, 0.00460, 0.00920, 0.01840, 0.03678, 0.05976 and 0.09650 dry mass percent. The 0- and 1-fibre states are inherited evidence; new execution candidates start at two fibres.

One placement realization is used at 2, 4 and 13 fibres. Three independent placement blocks are used at 8 and 21 fibres to expose placement variability. The ladder is adaptive: a failed lower tier stops promotion to higher concentration. A placement-generation failure is classified separately from a mechanical failure.

## Placement and relaxation protocol

1. Reload the same frozen Stage25 checkpoint for each case.
2. Generate all fibres using the Stage26a force- and moment-balanced two-anchor method.
3. Enforce unique clump membership, periodic clearance, no initial fibre-fibre overlap, and the Stage26a sand-fibre penetration limit.
4. Hold all fibres fixed during conditioning at 100 Pa.
5. Release all fibres together, reset velocities, and require five consecutive accepted free-relaxation blocks.

This protocol tests compatibility of a controlled embedded geometry. It deliberately does not claim to reproduce pouring, blending or compaction of laboratory microplastic mixtures.

## Primary observables and gates

- Mean and principal effective stress, compression positive: errors no greater than 2% and 3%.
- Unbalanced force no greater than 0.02 and normalized kinetic energy `KE/(pV)` no greater than `1e-5`.
- Sand coordination excluding iterative degree-less-than-two rattlers at least 3.0; rattler fraction no greater than 0.35.
- Sand-sand real-contact retention at least 90% of the frozen 361-contact baseline.
- Every fibre must retain at least two distinct sand contacts; no fibre may be mechanically isolated.
- Maximum inter-object penetration no greater than 0.02 of the smaller radius.
- RMS and maximum non-affine sand displacement no greater than 0.05 and 0.20 D50.
- Cell-volume drift no greater than 0.005.
- Rigid-clump tip-span drift no greater than `1e-8`; fibre centre-of-mass motion no greater than 0.5 contour length and rotation no greater than 90 degrees.

## Evidence and decision rule

The 0- and 1-fibre values are frozen reference evidence, not campaign repeats. New candidate runs are independent branches from the same Stage25 checkpoint. Raw failures remain immutable. Advancement occurs only after source hashes, placement preflight, terminal checkpoint, five-block equilibrium tail and all acceptance gates are independently verified.

The maximum dry-mechanically supported concentration is the highest concentration for which all prescribed placement blocks pass. A mixed pass/fail replicate set is reported as a transition region, not averaged into a pass.

## Claim boundary and authority

Stage26b design completion authorizes no simulation by itself. Multi-fibre YADE execution requires a separately frozen execution handoff. Flow, permeability, transient two-way coupling, deformation-coupled flow and production parametric execution remain prohibited at this checkpoint.
