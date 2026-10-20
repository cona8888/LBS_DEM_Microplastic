# Stage34B literature-informed fibre-length screen

## Physical question and claim

At fixed PET dose, sand packing and pore-placement context, does dividing each accepted straight-fibre parent into shorter disconnected fragments change the steady relative permeability of the frozen fixed-solid LBS model?

The permitted claim is a computational sensitivity of `K/K0` to idealized fragment length. Fibre length is a morphology or fragmentation-state variable. It is not a measurement of molecular PET degradation, and no temperature-to-length or length-to-chemical-conversion relationship is inferred.

## Frozen system boundary

- Three mechanics-qualified 216-grain periodic LBS packings: `n216_s1`, `n216_s2`, and `n216_s3`.
- Two accepted zero-interfibre-contact placement blocks per packing.
- Four accepted parent paths per packing/block and the frozen Stage31 CPD2 D3Q19 GPU LBM settings.
- Static sand and static PET geometry; no mechanics rerun, particle motion, migration, clogging, deformation, transient response or two-way coupling.
- Clean controls and intact four-parent CPD2 cases are reused only by verified immutable hashes.

## Factors and paired design

The primary screen holds the existing four-parent PET dose fixed and varies fragmentation state within each of six matched packing/placement contexts.

| Level | Fragments per parent | Total fragments | Target mean centreline length | Target aspect ratio (`(L+d)/d`, `d=0.10 mm`) |
|---|---:|---:|---:|---:|
| intact | 1 | 4 | 0.90 mm | 10.0 |
| split-2 | 2 | 8 | 0.45 mm | 5.5 |
| split-3 | 3 | 12 | 0.30 mm | 4.0 |

The exact terminal parent contour length in each accepted mechanics result is divided by the fragmentation count. The six intact cases are existing Stage31e observations. Only the 12 split-2/split-3 cases are new solves. Run order is deterministically randomized across those 12 cases.

## Geometry and mass closure

Fragmentation must not silently add PET through repeated capsule end caps. The Stage34C geometry builder must preserve, within each matched context, the intact case's solver-resolved PET volume outside sand. The primary gate is absolute fibre-only voxel-count deviation no greater than `max(1 voxel, 0.5%)` at CPD2. Fragment masks must remain disconnected with at least one fluid-voxel gap, remain within the accepted parent-path envelope, retain the parent tangent/orientation distribution, and contain no unintended pair overlap or grain penetration beyond the intact reference.

If those constraints cannot be achieved together at CPD2, geometry construction fails closed. Radius reduction, diameter retuning or relaxing mass closure after seeing hydraulic results is prohibited.

## Observables and analysis

Primary observable: matched steady `K/K0`, using the exact clean control for the same packing.

Predeclared paired contrasts within each context:

- split-2 minus intact;
- split-3 minus intact;
- split-3 minus split-2.

All six raw context values per length level are retained. Report median paired contrast, range, packing variance and within-packing placement-block variance. Do not impose monotonicity or fit a degradation law.

## Gates and sequential decision

- All lineage, geometry, record and artifact hashes pass.
- Clean sand masks reproduce exactly; all fluids span x/y/z and the largest fluid component fraction is at least 0.99.
- Frozen Stage31 convergence, Mach, Reynolds, density-drift, transverse-force, momentum-balance and exact-equilibrium gates remain unchanged.
- A length contrast is practically detectable for selection only if its median absolute `K/K0` shift is at least 0.005 and at least four of six context signs agree. This is a selection threshold, not a material law.
- CPD4 is not automatic. After the CPD2 screen, freeze at most four new fragment cases that span the largest effect and an opposing or near-null context. Confirm solution error with absolute CPD2-to-CPD4 ratio shift no greater than 0.002.
- A later concentration-interaction wave is allowed only if the CPD2 length screen is healthy and at least one length contrast meets the selection rule. That wave repeats selected length levels at the one-parent dose with the same volume and pairing rules.

## Claim boundary

This stage can support only an idealized fixed-geometry length sensitivity at low PET concentration. It cannot establish experimental hydraulic validation, a universal concentration law, a universal degradation index, chemical degradation, field transport, migration or clogging.

