# Stage26u — Three-Grain Throat Pull-Through Contract

## Question

Can the verified 37-node flexible fibre distinguish geometric blocking from passage through a deterministic three-sphere pore throat under one bounded axial pull?

## Geometry and loading

- One straight 0.900 mm by 0.100 mm flexible fibre, using the Stage26s/Stage26t numerical model.
- Three fixed, mutually tangent, equal sand spheres lie in a plane normal to the initial fibre axis.
- The fibre begins 0.150 mm before the throat plane with a fixed 2 micrometre transverse imperfection.
- Three analytical throat/fibre diameter ratios are tested: `0.80`, `1.00`, and `1.2725458139` (the ideal throat formed by three tangent LBS-D50 spheres).
- The corresponding equal-sphere diameters are derived from `d_throat / D_sphere = 2/sqrt(3) - 1`.
- A 1 micronewton axial force is ramped onto the leading grid node over 0.5 ms and maintained to 5 ms.
- Sand–fibre friction is zero, gravity is zero, spheres are fixed, and the domain is nonperiodic. This isolates geometric exclusion and flexible response.

## Evidence and inherited verification

- Stage26t checkpoint SHA-256: `6a949c51d973a7ce84efe23bfb02ae8980369cb9a1301c7b089566ce60965848`.
- Stage26s checkpoint SHA-256: `d8629d42cae87a29e6326d4592db5f5c67503464fd733bc5364e47355c8caac6`.
- Stage26t verified the chosen timestep safety factor `0.20` against `0.10` and `0.05`; this stage therefore varies geometry, not timestep.

## Frozen gates

1. Analytical throat diameters and tangent-sphere centre distances close within `1e-12` relative error.
2. All three runs remain finite, retain 37 nodes and 36 internal bonds, and keep sphere–fibre penetration below 1% of fibre radius.
3. The `0.80` throat is blocked: at least one persistent terminal sand contact, no fibre centreline node beyond the throat plane, and leading-node advance below 0.12 mm.
4. The LBS-D50 throat is passable: no sphere–fibre contact at any recorded state, at least four nodes beyond the throat plane, and leading-node advance above 0.25 mm.
5. The passable-case advance exceeds the blocked-case advance by at least 0.15 mm.
6. The ratio-1.00 result is reported as a marginal transition observation; it is not forced to pass or block.

## Claim boundary and authority

This contract authorizes exactly one immutable three-case Stage26u run, evaluation, and rendering. It does not calibrate friction, polymer stiffness, angularity, pore geometry, or hydrodynamic forcing. It does not authorize the 216-grain mixture, periodic `GridConnection` fibres, flow, permeability, deformation, migration, or production parametric claims.
