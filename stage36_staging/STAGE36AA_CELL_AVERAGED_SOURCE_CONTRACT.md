# Stage36AA — cell-averaged source comparison

## Verification question

Does conservative cell averaging of the unchanged Stage36Q manufactured body source reduce the nonconvergent force and velocity errors observed in Stage36W? This is a numerical source-discretization comparison, not calibration or physical validation.

## Frozen system

Retain the Stage36Q periodic unit cube, stationary sphere of radius 0.2 centred at (0.5,0.5,0.5), density 1, viscosity 0.1, compact manufactured field with outer radius 0.4, quintic ramp duration 0.25 and final time 1. Retain the Stage36W single-population BGK/immersed-boundary solver, pre-collision equilibrium-difference source injection, force identity, marker counts, scaling and all health checks.

Run N=12, 16 and 24 with dt=1/N^2, tau=0.8, N^2 steps and marker counts 32, 56 and 128. These jointly refine space, time and marker resolution, so no formal spatial order is claimed.

## Sole intervention

For each lattice cell, replace cell-centre sampling of each time-independent source component (u0, advective term and Laplacian) by an equal-weight 4x4x4 midpoint average over that physical cell. Assemble the time-dependent source from these averages using the unchanged ramp. Do not normalize its integral, alter its support, subtract a mean velocity, tune the body force, or change the reference traction.

## Evidence and gates

Save the averaged source components, first-step packet, quarter states and complete force/source/momentum histories in a new immutable directory. Compare the numerical velocity at lattice centres with the unchanged analytical centre values. The primary gates remain maximum force error <=2% and worst-quarter exterior velocity RMS error <=2%. Health gates remain relative mass error <1e-10, momentum residual per cell <1e-12, density error <0.01, marker slip <1e-10, finite positive populations and CPU time <=180 s.

Compare results against hash-verified Stage36W point-sampled cases. A reduction is diagnostic evidence only; both gates must pass before this manufactured problem is qualified. Do not infer permeability, drag or release fraction.
