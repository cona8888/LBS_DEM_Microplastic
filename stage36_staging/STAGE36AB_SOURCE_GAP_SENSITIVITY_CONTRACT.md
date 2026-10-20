# Stage36AB — fixed-grid source/interface gap sensitivity

## Question and claim boundary

At the frozen N=24 resolution, how strongly are the Stage36W errors and momentum drift affected when the numerical body-source support is separated from the immersed sphere? This is a diagnostic perturbation, not a manufactured-solution verification: after tapering, the original analytical velocity and traction are no longer exact solutions of the altered equations.

## Frozen controls

Reuse the hash-verified Stage36W N24 point-sampled case as the zero-gap baseline. Retain its unit periodic cube, sphere radius 0.2, centre, density, viscosity, BGK relaxation, time step, 576 steps, 128 markers, source injection, immersed-boundary enforcement, force ledger, analytical comparison scales and health checks.

## Diagnostic interventions

Run two new cases. Set the numerical source to zero from the sphere surface through gaps of one and two lattice cells respectively. Across the next one lattice cell, multiply every source component by the quintic smoothstep; outside that transition use the unchanged Stage36Q source. Do not renormalize the source integral or alter any other numerical setting.

Report original-comparator force and exterior velocity discrepancies only as sensitivities. Also report source integral, interpolated interior-source force, exterior mean velocity and exact momentum closure. The historical 2% gates are displayed but are not applicable to the perturbed equations. CPU limit is 180 seconds. No permeability, drag or release qualification follows.
