# Stage34C CPD4-first fixed-volume fragmentation geometry contract

## Question and bounded claim

At a fixed four-parent PET volume, how does an idealized intact/split-2/split-3 fragmentation state alter steady relative permeability across four matched packing/placement contexts?

The response is a fixed-solid **fragmentation-state sensitivity**. It is not a pure material length coefficient: fragment number, exposed ends and spatial redistribution necessarily change with length. It is not a chemical-degradation law or experimental validation.

## System boundary

- Three-dimensional periodic, saturated, steady LBM cells with static sand and static PET.
- Packings `n216_s1` and `n216_s2`; placement blocks `A` and `B`.
- Frozen CPD4 grid (`186^3`), forcing, fluid properties, convergence and health gates from accepted Stage31f.
- Four intact CPD4 cases and their matched clean controls are reused by immutable hash.
- At most eight new CPD4 fragment cases are permitted after geometry audit.
- No DEM mechanics rerun, mobile sand, mobile PET, migration, clogging, deformation, transient response or two-way coupling.

## Fragmentation levels

Each context represents four 0.90 mm parent-equivalent fibres of radius 50 µm.

- `frag1`: four intact accepted Stage31f paths; exact reused geometry and record.
- `frag2`: eight disconnected pieces, initially equal-volume endpoint-corrected from the exact parent contour lengths.
- `frag3`: twelve disconnected pieces, treated identically.

For a parent capsule with centreline length `L`, radius `r`, and `n` pieces, the initial per-piece centreline length is

`L_n = [L - 4 r (n-1)/3] / n`,

which preserves analytical capsule volume. The application mask must additionally match the intact context's solver-resolved PET volume outside sand within `max(1 voxel, 0.5%)`. A single preregistered uniform length multiplier, bounded to `[0.90, 1.10]`, may be selected by geometry-only search. Radius adjustment is prohibited.

## Frozen placement algorithm

The source is the pre-existing open-path candidate catalogue for the same packing. Candidates must satisfy `throat/radius >= 1.25` and swept clearance `>=2 µm` at the longer parent scale.

For each packing, construct two blocks without consulting hydraulic results:

1. seed each block with the four accepted Stage31 parent faces;
2. rank remaining candidates by a deterministic cost combining face/grain disjointness, periodic centreline separation, throat-ratio similarity, orientation mismatch and displacement from the corresponding parent-path midpoint;
3. `frag2` uses eight anchors and `frag3` uses the same eight plus four additional anchors;
4. rigidly rotate and translate cropped parent pieces to their assigned anchor directions; do not bend or rescale width;
5. require distinct fragment masks, no pair overlap, at least one CPD4 fluid voxel between fragments, and no greater sand intersection than the intact context;
6. record every source parent, target face, rigid transform, contour length, orientation, throat ratio and displacement.

If two disjoint admissible blocks cannot be built, or volume and separation cannot pass simultaneously, geometry fails closed. Candidate selection and length adjustment are frozen before flow and cannot be changed after observing conductance.

## Design and observables

The matrix has 12 condition rows: three fragmentation levels in each of four contexts. Four `frag1` rows are reused; eight `frag2/frag3` rows are new. New-case order is deterministically randomized.

Primary observable is matched `K/K0`. Retain all four context-level values and paired contrasts `frag2-frag1`, `frag3-frag1`, and `frag3-frag2`. Report packing and placement-block variability separately; impose no monotonicity.

## Pre-flow gates

- Exact Stage31f clean, intact geometry and record hashes pass.
- Candidate catalogues and source mechanics paths pass their hashes.
- CPD4 sand mask is bitwise identical within each context.
- Fragment count, parent mapping, rigid transforms and run order are exact.
- Solver-resolved PET volume error is within `max(1 voxel, 0.5%)`.
- Fluid spans x/y/z; largest fluid component fraction is at least 0.99.
- No pair overlap and at least one fluid-voxel interfragment gap.
- A CPD4/CPD6 geometry-only sentinel passes: volume-ratio shift `<=0.02`, orientation-order stability, and no topology reversal.
- Independent design, placement and raster audits pass.

## Post-screen selection rule

A response may be selected for finer solution verification only if the median absolute paired `K/K0` shift is at least 0.005 and at least three of four context signs agree. Select at most two fragment cases, spanning the strongest and a near-null or opposing context, for a preregistered finer-grid check. No concentration-interaction wave is authorized by this contract.

