# Stage34C Fragmentation CPD4 GPU Contract

## Question and evidence class

At fixed solver-resolved PET volume, how does the idealized intact/split-2/split-3 fibre state change the paired steady saturated conductance ratio `K/K0` across two accepted `N=216` sand packings and two placement blocks?

This is a fixed-solid, pore-scale LBM parametric comparison with CPD4 solution verification inherited from Stage31f. It is not a chemical degradation law, a pure fibre-length coefficient, an experimental validation, or a mobile-particle process.

## Frozen comparison

- Sand states: `n216_s1` and `n216_s2`.
- Placement blocks: `A` and `B` within each packing.
- Intact state: four accepted Stage31f four-fibre CPD4 records, reused by hash and never rerun.
- New states: split-2 and split-3 in every matched context, eight new CPD4 flow cases.
- PET radius: exactly 50 micrometres.
- Primary volume control: solver-resolved fibre-only voxel count at CPD4, matched to the intact context within `max(1 voxel, 0.5%)`.
- CPD6 geometries are geometry-only sentinels. CPD6 flow is not authorized.
- The eight-case order is the random order frozen before geometry construction.

## Solver and initialization

The CUDA source, qualified PTX, CPD4 lattice, fluid properties, body acceleration, BGK relaxation, convergence criteria, numerical-health gates, and force/momentum-balance gates are copied exactly from the accepted Stage31f configuration.

Each new split case uses the accepted CPD4 `final_fields.npz` from its own intact packing/placement context as a common resampled local-equilibrium warm start. The inherited attenuation factors are `velocity_scale=0.5` and `density_deviation_scale=0.125`. Split-2 never initializes split-3 and split-3 never initializes split-2.

## Outputs and analysis

For each new case preserve `record.json`, `audit.npz`, `final_fields.npz`, `final_shifted_state.npz`, and `final_flow.vtk`. Report:

- `K/K0`, where `K0` is the accepted matched clean CPD4 conductance for that packing;
- split-2 minus intact, split-3 minus intact, and split-3 minus split-2 ratios in every context;
- raw context values and cross-context sign counts;
- the predeclared practical-effect threshold `|delta(K/K0)| >= 0.005` as a descriptive screen only.

No monotonicity or obstruction direction is imposed. All convergence, finite-positive response, numerical health, exact equilibrium closure, force direction, transverse-force, Mach, Reynolds, density-drift, and momentum-balance checks must pass. Any failed or missing case fails the campaign closed and remains preserved.

## Immutability and authority boundary

The runner must refuse an existing run directory and must require a separately generated hash-bound release. The supervisor must refuse existing run/supervisor directories and any competing Python or YADE process. It must launch at most this one eight-case GPU campaign.

This stage does not authorize absolute permeability validation claims, CPD6 flow, mechanics reruns, mobile sand, migration, clogging, deformation, transient coupling, or two-way coupling. Post-flow interpretation and rendering require a separate immutable evaluation.
