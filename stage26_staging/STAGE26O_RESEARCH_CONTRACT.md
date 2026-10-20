# Stage26o gravity-assisted joint-deposition benchmark

## Physical question

Can sand and exact rigid F37 fibres acquire a persistent, mobile sand-contact cage when they are settled and confined together, instead of inserting fibres into a pre-existing periodic pore geometry?

## System boundary

- Three-dimensional, dry, wall-bounded small assembly reconstructed from the 216-grain LBS PSD realization.
- Two exact F37 rigid clumps: 37 members per fibre, 50 micrometre member radius, 0.94 g/cm3 polymer density.
- Gravity-assisted settling followed by wall-controlled confinement to 100 Pa and a final zero-gravity mobile hold.
- The wall box is a preparation benchmark, not a representative 50 mm by 20 mm permeameter specimen.

## Observables

- Sand contacts per fibre, fibre-wall contacts, fibre translation and rotation.
- Sand-sand contact count, coordination excluding degree-less-than-two rattlers, rattler fraction, wall stress, unbalanced force, kinetic energy, void ratio, and maximum normalized penetration.
- Units use metres, kilograms, seconds, pascals, joules, and degrees.

## Deliberate assumptions and omissions

- Sand grains remain spheres and fibres remain rigid sphere clumps.
- No fibre bending, electrostatics, adhesion, water, air drag, pore pressure, fluid flow, permeability, degradation, or chemical interaction.
- Wall effects are expected and explicitly prevent bulk-property or permeability inference.
- Numerical damping is a preparation control and will not be interpreted as polymer damping.

## Evidence ladder and gates

1. Bind to the accepted Stage25 sand realization and the Stage26n failure checkpoint.
2. Verify local YADE 2022.01a wall, box-sphere, clump, gravity, and stress-controller APIs in a smoke case.
3. Run a clean-sand wall-bounded control to show the preparation path can form a stable 100 Pa skeleton.
4. Run one spent-development two-fibre mixture with identical sand, boundaries, and controller settings.
5. Require exact geometry, finite state, penetration at most 0.02 radius, no wall-supported fibre, at least three distinct sand contacts per fibre, no isolated fibre, sand coordination at least 3, rattlers at most 0.35, relative mean wall-stress error at most 0.05, unbalanced force at most 0.03, and five consecutive final-hold passes.

Failure is preserved and classified. A pass authorizes only fresh development-geometry replication. It does not authorize held-out geometry, flow, permeability, deformation, migration, or a production concentration study.
