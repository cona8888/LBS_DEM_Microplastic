# Stage28a two-fibre mechanics-to-hydraulics contract

## Purpose and bounded claim

Stage28a asks whether the verified single-fibre mechanics-to-hydraulics bridge
remains numerically credible when a second flexible F37 fibre is present.  It
is a low-concentration mechanism test, not the production concentration
campaign.  The sand is the accepted periodic 216-grain Leighton Buzzard Sand
realization and remains exactly fixed.  Each fibre retains the Stage26x
37-node bonded discretization and the same physical length, diameter, density,
elastic law, loading history, periodic cell and integration controls.

The permitted claim is limited to distinguishing additive obstruction from a
resolved fibre-fibre interaction in three two-fibre geometries.  Stage28a does
not validate polymer properties, a concentration-permeability law, mixing,
mobile grains, clogging evolution or two-way hydromechanical coupling.

## Why this rung is required

Stage24 already established a rigid-fibre concentration screen from about
0.005 to 0.4 dry-mass percent and solution-verified selected cases at CPD4.
Stage27 independently solution-verified the hydraulic effect of one
mechanically resolved flexible fibre.  A full flexible-fibre concentration
campaign would introduce fibre-fibre contact before that mechanism has been
verified.  Stage28a isolates it with only two fibres.

## Frozen cases

1. `separated_open_open`: two noninteracting open-path fibres.  This is the
   independence and implementation control.
2. `separated_open_constricted`: one open-path fibre and one sand-contact-
   deflected fibre, spatially separated.  This tests whether the two verified
   single-fibre responses superpose without fibre-fibre contact.
3. `crossing_interaction`: two initially separated fibre centrelines driven
   into one controlled crossing region.  It must exercise finite periodic
   fibre-fibre contact without node interpenetration or accidental bonding.

The achieved two-fibre dry-mass concentration is approximately 0.0093815%,
matching the Stage24 two-fibre level.  Concentration is fixed in Stage28a;
geometry class is the varied mechanism.

## Mechanics acceptance gates

- exactly 216 fixed sand grains and exactly unchanged periodic cell;
- exactly two 37-node fibres and 36 intact internal bonds per fibre;
- finite state, forces, moments and energies at every recorded block;
- no sand displacement and no cell drift;
- maximum fibre-sand and fibre-fibre penetration below 1% of fibre radius;
- zero-load terminal hold with no continuing drift;
- separated controls have zero fibre-fibre contacts;
- the crossing case has at least one finite fibre-fibre contact and no
  cross-fibre bond;
- each separated terminal centreline agrees with its corresponding verified
  Stage26x single-fibre terminal shape within 0.05 fibre diameters after the
  declared periodic rigid alignment;
- force, contact and energy histories are written and hash-bound.

## Hydraulic pilot and observables

Only after an independent mechanics audit may the three fixed terminal masks
be voxelized at CPD2 and run through the qualified periodic GPU-LBM solver.
The immutable Stage27a clean-sand record is the paired control and is not
rerun.  Primary observables are:

- paired permeability ratio `k/k0` for each two-fibre case;
- additive prediction `1 + delta_1 + delta_2` from the corresponding
  independently verified Stage27 single-fibre effects;
- non-additive interaction contrast `delta_two - delta_1 - delta_2`;
- porosity change, fibre-only voxel count, connected-fluid fraction, maximum
  Mach number, Reynolds number, density drift and momentum-balance residual.

The additive contrast is descriptive: no sign or magnitude is forced.  All
standard convergence, health, flow-direction and momentum-balance gates must
pass.  A selected CPD4 confirmation can be designed only after independent
evaluation of the CPD2 pilot.

## Authority boundary

This contract authorizes design and independent preflight only.  It does not
authorize YADE mechanics execution, GPU-LBM execution, a full concentration
campaign, mobile sand or two-way coupling.  Each later release requires an
immutable checkpoint that explicitly grants that activity.

