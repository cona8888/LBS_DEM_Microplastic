# Stage26t — Sand–Fibre Contact and Three-Point Bending Contract

## Question

Does YADE's nonperiodic sphere–`GridConnection` contact transmit a mechanically consistent, reversible normal load into the verified 37-node F37-like flexible fibre?

## Evidence and boundary

- Stage26s checkpoint SHA-256: `d8629d42cae87a29e6326d4592db5f5c67503464fd733bc5364e47355c8caac6`.
- Stage26p mechanism checkpoint SHA-256: `a87dc95e2f3c15af25ac1fb90669fe73cde8ae6a8ddd46a1302ef1add956ef3d`.
- Fibre: 0.900 mm long, 0.100 mm diameter, 37 nodes, nominal `E = 53 MPa`, density 940 kg/m3.
- Sand indenter: one fixed spherical grain with the Stage26p LBS `D50 = 0.822586545 mm`.
- The fibre is straight, nonperiodic, gravity-free, frictionless at the sand–fibre interface, and fixed against translation and rotation at both ends.
- The sphere is moved normally at the fibre midpoint through a small load–hold–unload–hold cycle.
- The benchmark is a contact/code-verification problem, not a model of bulk sand or fibre caging.

## Comparator and observables

- Native sphere–grid normal stiffness and force direction are recorded in a one-contact API probe.
- During the peak hold, the measured sphere reaction is compared with the fixed–fixed beam point-load relation `F = 192 E I delta / L^3`, using the measured fibre midpoint deflection `delta`.
- Contact count, penetration, reaction direction, endpoint motion, maximum node speed, unloading recovery, and three timestep levels are recorded.

## Frozen gates

1. API probe creates a real sphere–grid contact with positive penetration, positive normal stiffness, and an upward reaction on the downward-moving sphere.
2. All three timestep levels (`0.20`, `0.10`, `0.05` of the bending-controlled estimate) remain finite and complete the same physical cycle.
3. Peak-hold sphere–fibre contact persists and the reaction direction is correct.
4. Both endpoint positions remain fixed within `1e-15 m`.
5. Peak midpoint deflection is below 2% of fibre length.
6. Fine-level beam-theory force error is at most 10%.
7. Medium-to-fine peak-force and midpoint-deflection changes are each at most 2%.
8. After complete unloading, contact is absent and residual midpoint deflection is at most 1% of peak deflection.

## Authority

This contract authorizes one immutable API probe and one immutable three-timestep Stage26t benchmark, independent evaluation, and rendering. It does not authorize friction calibration, polymer calibration, multi-grain caging, a sand mixture, periodic grid fibres, flow, permeability, deformation, migration, or production parametric inference.
