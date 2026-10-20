# Stage29c four-fibre single-contact mechanics design

Stage29b demonstrated that three independent four-fibre placements with two disjoint crossing contacts are not available in the frozen pore-path library. Stage29c therefore tests the smallest identifiable interaction increment at fixed concentration:

- `zero_contact`: four fibres with all six inter-fibre pairs separated;
- `one_contact`: four fibres with exactly one predicted/measured crossing-contact edge and the other five pairs separated.

Three matched placement blocks A, B, and C are required. Source path faces must not be reused within the same topology across blocks. Topology is determined from predicted geometry during candidate screening and from terminal mechanical contacts during acceptance; requested labels are never sufficient.

All Stage29b hard mechanics gates remain unchanged. The single-contact revision changes only the required contact graph. It is a low-concentration interaction-mechanism qualification, not a claim that real four-fibre mixtures contain exactly one contact.

This contract authorizes revised design generation and independent audit only. It does not authorize geometry acceptance, runner construction, YADE execution, hydraulic simulation, or permeability claims.
