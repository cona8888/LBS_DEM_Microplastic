# Stage25: load-bearing LBS packing qualification

## Why this stage is necessary

Stage24e verified the static GPU-LBM relative-permeability effects at CPD4. Its sand and fibre geometries were deliberately frozen. The source Stage23a hydraulic geometry has a terminal DEM real-contact count of zero, so it is a valid non-overlapping pore geometry but not a load-bearing granular state. It cannot be used directly for deformation or two-way hydro-mechanical coupling.

## Physical question

Can the reported Leighton Buzzard Sand Fraction-B PSD be prepared as a reproducible, load-bearing, very-loose periodic DEM packing at low effective stress while retaining a void ratio close to the permeability reference state, e = 0.744?

## Stage25a scope

- Pure sand only; no fibres and no flow.
- Same reported PSD bounds and quantiles used in Stage23.
- N = 216 and the primary Stage23 seed.
- Periodic cubic representative cell.
- Isotropic effective stress target: 100 Pa compression, representing the order of self-weight stress in a 20 mm laboratory specimen.
- Three preparation-friction candidates: 0.30, 0.45, and 0.60.
- Linear frictional contacts are a preparation surrogate, not an LBS material calibration.

## Observables and hard gates

- Mean effective stress and normalized stress error.
- Void ratio and its difference from e = 0.744.
- Real contact count, coordination excluding rattlers, and rattler fraction.
- Unbalanced force and kinetic energy normalized by pV.
- Maximum overlap divided by the smaller particle radius.
- PSD bounds and D10, D50, D60 preservation.
- Particle count, periodic-cell integrity, finite state, and no lost particles.

An admissible pilot must meet all of the following:

- stress error <= 2%;
- unbalanced force <= 0.02;
- normalized kinetic energy <= 1e-5;
- coordination excluding rattlers >= 3.0;
- rattler fraction <= 0.35;
- maximum overlap ratio <= 0.01;
- absolute void-ratio difference from 0.744 <= 0.05;
- all 216 sand particles retained and all values finite.

## Promotion sequence

1. Run the three Stage25a preparation-friction candidates.
2. Select a load-bearing state by the frozen gates, not merely by closest void ratio.
3. Repeat the selected state at three timestep safety levels and at two additional packing seeds.
4. Only after Stage25a passes, prepare paired clean, 0.1%, and 0.4% F37 mixtures by consolidating sand and fibres together from a loose state.
5. Visually audit contacts, fibre placement, and pore geometry before flow.
6. Run CPD2 static flow on the mechanics-prepared states, then a bounded CPD4 confirmation.
7. Deformation-coupled or transient two-way flow remains a later stage.

## Claim boundary

Stage25a is a DEM state-preparation and numerical qualification. It does not calibrate LBS strength or stiffness, validate polymer contact properties, predict laboratory permeability, or authorize transient/deformation-coupled flow.

