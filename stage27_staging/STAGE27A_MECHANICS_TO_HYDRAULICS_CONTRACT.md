# Stage27a mechanics-to-hydraulics bridge

## Question

For the accepted periodic 216-grain Leighton Buzzard Sand state, does one
mechanically resolved 100 micrometre fibre alter steady single-phase hydraulic
conductance differently when it occupies the Stage26x open path versus the
Stage26x one-grain-deflected path?

## System and assumptions

- Three-dimensional, triply periodic, saturated fixed-solid cell.
- The accepted Stage25 sand coordinates and radii are frozen.
- The terminal Stage26x fibre centrelines are frozen and rasterised as
  100 micrometre diameter capsules.
- The slightly orthorhombic DEM cell is affinely mapped to a volume-equivalent
  cube; the maximum axial distortion must remain below 0.5%.
- Water is Newtonian and incompressible in the low-Reynolds-number GPU-LBM
  approximation already qualified in Stages13, 23 and 24.
- No particle motion, fibre deformation during flow, chemistry, adsorption,
  migration, clogging evolution, or two-way coupling is represented.

## Cases and observables

1. Clean periodic sand.
2. The Stage26x terminal open-path fibre.
3. The Stage26x terminal contact-deflected fibre.

Primary observables are steady conductance proxy, intrinsic permeability in
square metres, and each fibre case's paired permeability ratio to the clean
mask. Secondary observables are porosity, connected-fluid fraction, Reynolds
number, Mach number, momentum residual, force balance, and convergence cost.

## Acceptance

- Exact immutable source-hash bindings and exactly 216 sand grains.
- Identical sand voxels in all three masks; positive fibre-only voxels.
- At least 1.9 lattice cells across the fibre diameter at CPD2.
- Connected fluid component at least 99% and spanning all axes.
- Every LBM case converged with all inherited Stage24 numerical-health gates.
- Finite positive conductance and reproducible paired ratios.

## Claim boundary

This pilot can establish a numerical fixed-geometry obstruction contrast for
one fibre in one small periodic realization. It cannot establish a physical
concentration-permeability law, experimental validation, mobile-grain
response, clogging, polymer calibration, or deformation-coupled flow.

