# Stage28b two-fibre CPD2 hydraulic pilot

Research question: with the accepted fixed 216-grain LBS packing and the accepted Stage28a terminal flexible-fibre geometries, how do separated open/open, separated open/constricted, and controlled-crossing two-fibre arrangements change paired permeability relative to the same clean-sand mask?

The pilot uses the accepted Stage27a CPD2 sand voxelisation and solver. Each fibre is rasterised as the periodic union of 36 capsules of 0.10 mm diameter. The two fibre masks are unioned with the unchanged sand mask. Cases are executed in the fixed order clean, separated open/open, separated open/constricted, and crossing.

Hard gates: exact clean-sand array identity; 216-grain lineage; two centrelines of 37 nodes in each mixture; positive fibre-only voxel count for both fibres; connected fluid spanning x/y/z with largest component at least 99%; immutable source and artifact hashes; qualified GPU lineage; converged and healthy CPD2 records; exact clean ratio 1.0. No monotonic response is imposed.

Claim boundary: fixed-solid, periodic CPD2 numerical mechanism pilot at approximately 0.0093815 dry-mass percent only. It does not validate a concentration law, polymer properties, moving sand, fibre migration, clogging evolution, transient response, or two-way coupling. CPD4 and production studies require separate promotion.
