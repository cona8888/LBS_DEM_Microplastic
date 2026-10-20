# Stage36V — discretization decision and next bounded flow test

## Decision

Retain the existing single-population immersed-boundary implementation for one controlled spatial-refinement assessment. Do not integrate Stage36U phase registers into it. Do not begin a cut-cell solver rewrite on the strength of static source bookkeeping alone.

Stage36R tested time scaling at one coarse spatial resolution, N16. Stage36S showed source integration and interior interpolation sensitivity to spatial resolution. Stage36T demonstrated noncommutation of cell averaging and phase restriction. Stage36U demonstrated loss of phase information on summation. None establishes that the original immersed-boundary method cannot converge spatially, nor that a two-register scheme is necessary. Earlier statements implying a mandatory new solver would exceed this evidence.

The interior-source diagnostic screen is not a substitute for convergence of total hydrodynamic traction. Its nonzero value is a discretization error measure against the continuum support, but individual terms can be discretization-dependent. Continue comparing the complete force, field and conservation ledgers. Do not replace an actual discrete source contribution by analytical zero while retaining its injection.

## Frozen proposed comparison (not executed in this decision stage)

Use unchanged Stage36Q manufactured field, radius .2, outer cutoff .4, centre (.5,.5,.5), density1, viscosity .1, quintic ramp duration .25, end time1. No fit or altered reference. Start from rest. Preserve Stage36R source injection and complete source-aware force identity.

Use spatial levels N12,16,24; dt=1/N^2, tau=.8, steps=N^2. This is combined diffusive space/time refinement, not an isolated spatial order estimate. Marker counts32,56,128 follow existing Stage36L levels. Radius in lattice units is N/5. Common256 off-marker probes remain. The N16 member must exactly reproduce Stage36R s1 before results can be compared. Two other members are new bounded CPU runs; do not rerun an immutable output directory.

Conversions: velocity_phys=N*velocity_LU; force_phys=force_LU because dx^4/dt^2=1; impulse_phys=impulse_LU/N^2; source impulse density_LU=source_phys*dt^2/dx. Save first source/stream/projection packets, quarter fields, all force/source/momentum histories, source integrals, and quadrature diagnostics. Compare velocity on each grid to analytical values, not interpolated coarse-grid numerical values.

Retain2% analytical peak force and worst-quarter exterior RMS velocity gates from Stage36R; no requirement to obtain a pass at these coarse grids. Report error trends as evidence, not a formal convergence order with changing markers and time step. Use identical numerical health gates, and compare interior quadrature levels separately. CPU ceiling180seconds; stop on health failure, invalid conditioning or resource cap. No GPU or existing-job interaction.

## Decision after that test

- If errors decline but remain above gates: report unresolved numerical error; estimate required resources before expanding.
- If they do not decline: inspect source splitting, force definition and interface representation against the frozen comparator; do not tune viscosity or remove startup.
- A rewrite or alternative engine requires a separately scoped implementation decision, not automatic escalation from a failed test.

No simulations were run in Stage36V. No drag, permeability or release claim is newly qualified. This memo follows the DEM-researcher requirement to test the lowest-cost falsifiable explanation before changing model fidelity.
