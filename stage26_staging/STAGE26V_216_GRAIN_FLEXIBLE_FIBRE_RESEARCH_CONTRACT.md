# Stage26v — 216-Grain Flexible-Fibre Caging Pilot Contract

## Physical question

Can the verified 37-node flexible F37-like fibre distinguish a geometry-predicted cage path from an open path inside the accepted Stage26o wall-bounded 216-grain sand geometry, before sand mobility or fluid coupling is introduced?

## System boundary and scale

- Exact accepted Stage26o `clean_control_13` state: 216 spherical LBS grains, six fixed walls, approximately 100 Pa terminal wall stress, and zero gravity.
- One 0.900 mm long, 0.100 mm diameter, 37-node flexible fibre using the Stage26s/Stage26t model.
- Nonperiodic three-dimensional geometry. Sand grains and walls remain fixed during this integration rung.
- Two deterministic paths selected from the exported geometry: one predicted cage path and one open-path negative control.
- Each path receives a zero-load hold followed by the same bounded axial pull used by Stage26u.

## Observables

- Initial analytical minimum surface clearance and swept-path clearance, in metres and normalized by fibre radius.
- Fibre–sand contact count, distinct contacted grains, normal-contact force, maximum normalized penetration, leading-node advance, node passage count, transverse displacement, bond count, and hold drift.
- Sand coordinates and radii, fibre centreline coordinates, wall bounds, time step, iteration count, and immutable artifact hashes.

## Model assumptions and omissions

- Fixed sand isolates pore geometry and fibre contact/flexure from granular rearrangement.
- Contact is frictionless and non-adhesive; fibre stiffness and density remain nominal numerical references, not polymer calibration.
- No gravity, buoyancy, electrostatics, degradation, fluid force, pore pressure, flow, permeability, mobile-sand response, stress redistribution, or representative-volume claim.
- The 216-grain wall specimen is a small-assembly integration geometry, not the requested 50 mm by 20 mm production permeameter.

## Evidence ladder

1. Bind and export the accepted Stage26o state without DEM stepping.
2. Select paths using deterministic analytical swept-capsule clearance and wall-containment checks.
3. Require a zero-load hold with intact bonds, finite state, and negligible drift.
4. Pull both paths using the Stage26u verified force, duration, and time-step factor.
5. Require the cage and open paths to show distinct contact/passage responses without violating the penetration guard.
6. Independently verify hashes, geometry, histories, classifications, and render actual-scale evidence.

## Acceptance and stop gates

- Export: exactly 216 non-clump spheres, six box walls, nonperiodic state, and exact binding to the accepted Stage26o checkpoint/state.
- Both initial fibres are wall-contained and overlap-free, with all 36 internal bonds present.
- Zero-load hold drift is at most 1 micrometre and maximum hold speed is finite.
- Maximum sand–fibre penetration is at most 0.01 fibre radius.
- Open path: no recorded contact, at least four centreline nodes pass its declared terminal plane, and leading-node advance is at least 0.25 mm.
- Cage path: persistent terminal contact, no centreline node passes its declared cage plane, and leading-node advance is at most 0.12 mm beyond its initial value.
- Open-minus-cage terminal advance is at least 0.15 mm.

Failure is preserved and classified. Passing authorizes design of one mobile-sand release pilot only; it does not itself authorize mobile-sand execution, flow, permeability, deformation, or a concentration campaign.

