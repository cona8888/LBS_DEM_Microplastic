# Stage29a mechanics-aware low-concentration design contract

## Scientific question

For the fixed periodic 216-grain Leighton Buzzard sand cell, how does F37 fibre dry-mass concentration change intrinsic permeability, and how much of that change is mediated by fibre-fibre interaction topology rather than fibre count alone?

## Evidence inherited, not re-claimed

- Stage24c screened rigid, artificially placed fibres from 0.005 to 0.4 dry-mass percent and found a concentration response, orientation effects, and placement variability.
- Stage24e verified selected Stage24 effects at CPD4, but explicitly did not validate polymer mechanics or physical mixing.
- Stage28a qualified deformable two-fibre mechanics for separated and crossing topologies.
- Stage28c verified at CPD4 that both two-fibre topologies obstruct flow and that the crossing topology is more obstructive.

## Bounded design

The first mechanics-aware concentration bridge is restricted to 0, 1, 2, and 4 fibres. With the frozen F37 mass and sand mass, these correspond to 0, 0.004690960879927048, 0.009381481678218612, and 0.018761203277589126 dry-mass percent.

The primary packing, sand coordinates, periodic cell, fibre material, fibre discretisation, pressure forcing, fluid properties, convergence gates, and permeability estimator remain fixed. Sand is immobile during the hydraulic solve.

Three deterministic placement blocks (A, B, C) are used:

- 1 fibre: `single_open` in each block.
- 2 fibres: `separated` and `crossing` in each block.
- 4 fibres: `low_contact` and `contact_rich` in each block.
- Clean: the accepted Stage27b/Stage28c clean control is reused exactly and is not rerun.

This gives 15 new non-clean cases plus one reused clean control. Run order is deterministically randomized only after every geometry and mechanics record passes preflight.

## Sequential gates

1. Qualify all six four-fibre mechanics cases before any Stage29 hydraulic execution.
2. Qualify the remaining one- and two-fibre placement blocks using the accepted Stage28a mechanics protocol.
3. Release the 15-case CPD2 hydraulic screen only after an independent preflight binds every geometry, mechanics checkpoint, topology label, source hash, and run-order hash.
4. Estimate concentration, topology, concentration-by-topology, and placement-block effects without imposing monotonicity.
5. Promote only a bounded clean/central/extreme subset to CPD4. Additional 8- or 11-fibre cases require a new mechanics qualification and handoff.

## Mechanics acceptance requirements

- exact fixed sand coordinates and cell;
- complete intrafibre bonds and no false same-fibre contacts;
- no cross-node bonds;
- topology labels reproduced by measured fibre-fibre contact state;
- path-match RMS no greater than 0.05 fibre diameter;
- maximum penetration no greater than 0.02 fibre radius;
- exact stable hold and the inherited Stage28a equilibrium/health gates;
- finite values and immutable checkpoint/record/artifact hashes.

## Hydraulic outcomes and analysis

Primary outcome: paired permeability ratio `k/k0`. Secondary outcomes: intrinsic permeability, relative permeability change, voxel porosity, connected pore fraction, fibre voxel count, fibre-fibre contact count, and flow-balance diagnostics.

The analysis reports block-paired contrasts and uncertainty. Placement block is a nuisance/block factor. The predeclared numerical resolution band is 0.0002 in `k/k0`, conservatively above the largest Stage28c CPD2-to-CPD4 ratio shift. Effects smaller than this are reported as unresolved, not as zero.

## Claim boundary

This stage can support only a low-concentration, fixed-packing, static-flow, mechanics-aware pore-obstruction claim for one fixed periodic 216-grain LBS realization. It does not represent dry mixing, packing rearrangement, a 50 mm by 20 mm laboratory specimen, polymer surface chemistry, fibre degradation, migration, clogging, mobile sand, deformation, transient flow, or two-way hydro-mechanical coupling.

## Authority

This contract authorizes deterministic design generation and independent design audit only. It does not authorize mechanics execution, GPU flow execution, CPD4 promotion, production concentration execution, or new physics.
