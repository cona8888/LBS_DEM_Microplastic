# Stage26q density–geometry–flexure research contract

## Decision being tested

The present rigid F37 mixture cannot be advanced to flow. Before changing the
fibre constitutive model, determine whether the failed caging is primarily an
artefact of the excessively loose Stage26o wall-bounded preparation.

## Evidence entering this stage

- The accepted Stage25 pure-sand state has void ratio `e = 0.7385798565`, close
  to the reported LBS reference `e = 0.744`.
- The accepted Stage26o wall-bounded clean control has `e = 1.0239268884`.
  It is mechanically equilibrated at 100 Pa, but it is not density-matched to
  the LBS reference.
- The exact F37 fibre diameter is 100 micrometres, or `0.12157 D50`.
- The ideal aperture between three touching D50 spheres is about 127.25
  micrometres, so the fibre diameter is only `0.78583` of that reference
  aperture.
- Stable release, uniform co-deposition and layered pluviation did not produce
  persistent simultaneous cages.
- The analytical and YADE force-sign checks agree that a 940 kg/m3 PE fibre in
  1000 kg/m3 water has net upward buoyancy.

## Ordered hypotheses

1. **Density mismatch:** `e = 1.024` leaves a substantially more open pore
   network than the reference LBS state and is the first model-form defect to
   remove.
2. **Pore-geometry mismatch:** even at the correct bulk void ratio, spherical
   grains may retain throat sizes and connectivity unlike angular LBS grains.
3. **Fibre flexure:** the current 53 MPa parameter controls fibre–grain contact
   stiffness only. The 37-member F37 object is a rigid clump and therefore has
   no calibrated whole-fibre bending stiffness.

These hypotheses must be tested in this order. A flexibility change cannot be
used to compensate silently for a wrong packing density.

## Stage26q-A: clean density-controller qualification

Load the accepted Stage26o clean state, compress it isotropically under
strain-rate control to `e = 0.744`, hold the volume to dissipate kinetic energy,
then restore isotropic 100 Pa stress control and equilibrate. This is a clean
controller benchmark only; it contains no microplastic.

Hard acceptance requirements:

- exactly 216 original LBS spheres and six walls;
- no particle loss or replacement;
- target void-ratio error at the fixed-volume handoff no greater than 0.002;
- terminal void-ratio error no greater than 0.02 after restoration to 100 Pa;
- mean stress error no greater than 5% and maximum principal stress error no
  greater than 10%;
- unbalanced force no greater than 0.03;
- kinetic energy divided by `pV` no greater than `1e-5`;
- maximum overlap divided by smaller particle radius no greater than 0.02,
  with a hard stop at 0.05;
- coordination excluding iterative degree-less-than-two rattlers at least 3.0;
- rattler fraction no greater than 0.35;
- five consecutive passing terminal blocks.

Failure is informative. If the target density cannot survive unloading to
100 Pa under the unchanged contact law, the specimen-preparation route—not
fibre mechanics—is the next calibration problem.

## Stage26q-B: pore-throat measurement

Only after Stage26q-A passes, extract a Delaunay-based pore-throat distribution
from the qualified dense state. The three-equal-sphere aperture is a reference
calculation, not a substitute for this measured distribution. Report at least
the 5th, 50th and 95th percentiles of throat diameter divided by D50 and the
fraction of throats wider than the 100 micrometre fibre diameter.

## Stage26q-C: fibre flexural benchmark design

The preferred YADE representation is a continuous chain of `GridConnection`
beam segments with external grain contact, not another overlapping-sphere
clump. Calibrate its effective `EI` using a cantilever tip-load benchmark:

`delta = F L^3 / (3 E I)` and `theta = F L^2 / (2 E I)` in the small-deflection
regime, with `I = pi d^4 / 64` for a circular 100 micrometre section.

Required checks are mass conservation, 37 centreline nodes, 0.9 mm centreline
length, axial response, tip displacement and rotation, energy consistency, and
19/37/73-node resolution convergence. Polymer type, manufacture, degradation
and diameter affect the modulus, so `EI` must be measured or treated as an
explicit screened uncertainty; it must not be inferred from density alone.

## Authority boundary

This contract authorizes implementation and one clean Stage26q-A controller
pilot when no other YADE job is active. It authorizes offline Stage26q-B and
Stage26q-C design work. It does not authorize a new rigid or flexible mixture,
flow, permeability, deformation, migration or a production parametric study.

