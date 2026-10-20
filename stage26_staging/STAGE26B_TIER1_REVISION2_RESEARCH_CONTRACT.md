# Stage26b Tier-1 Revision 2: placement-stability research contract

## Decision being tested

Can a two-rigid-F37-fibre assembly be placed in the accepted Stage25 216-grain, 100 Pa periodic sand skeleton so that every fibre retains at least two sand contacts during a short **fixed-fibre conditioning prefilter**, without changing the accepted contact physics or materially disturbing the sand skeleton?

This is a placement-method qualification. It is not a permeability, microplastic-concentration, polymer-calibration, migration, deformation, or two-way-coupling result.

## Frozen evidence and diagnosis

The Stage26b Tier-1 two-fibre qualification is preserved as a valid physical failure. Both fibres had their two declared anchor contacts immediately after insertion. During the first fixed 500-step conditioning block, fibre 0 lost both contacts and remained isolated. Fibre 1 retained two contacts. The sand skeleton itself recovered: 361 sand contacts, contact retention 1.0, mean effective stress 99.933 Pa, coordination 4.011, and unbalanced force 0.01931.

The working hypothesis is therefore narrow: the original geometric screen admitted an anchor pair that was not persistent under stress-controlled conditioning. The revision tests anchor-network quality and contact persistence. It does not tune stiffness, friction, damping, fibre mass, fibre shape, confining stress, overlap, or the Stage25 packing to force a pass.

## Immutable physics invariants

- Stage25 checkpoint, particle coordinates, radii, cell, and 100 Pa target remain unchanged.
- Sand and plastic contact properties remain exactly those in the accepted Stage26a/Stage26b configuration.
- The fibre remains one rigid 37-member F37 clump with 50 micrometre member radius and 1 mm contour length.
- Target anchor penetration remains 0.005 member radii; the maximum permitted sand-fibre penetration remains 0.02 member radii.
- Gravity remains zero, Newton damping remains 0.35, and timestep safety remains 0.2.

## Revised placement screen

Before placement generation, a YADE read-only network export must be derived from the exact Stage25 checkpoint. Candidate anchors must:

1. belong to the iterative degree-2 load-bearing core;
2. have initial sand-network degree at least 3, with degree 4 or greater preferred in ranking;
3. not be reused by another fibre in the same case;
4. produce exactly two initial sand contacts per fibre;
5. satisfy normal-force-direction residual at most 0.05 and moment residual at most 0.02;
6. preserve zero initial fibre-fibre overlap and at least 0.5 D50 inter-fibre clearance.

Twelve deterministic two-fibre candidates are predeclared. All candidate attempts and rejections must be preserved; the budget may not be extended after inspecting outcomes.

## Engine-based fixed-conditioning prefilter

The prefilter reloads the exact Stage25 checkpoint for every trial, inserts the proposed fibres, keeps all fibres fixed, and runs ten blocks of 500 YADE steps using the unchanged Stage26b stress controller and damping. It records contact identities and sand-state metrics after insertion and after every block.

The prefilter implementation must first reproduce two controls:

- Positive control: the accepted Stage26a one-fibre placement must retain at least two contacts throughout the ten blocks.
- Negative control: the frozen failed Stage26b two-fibre placement must reproduce loss of engagement for fibre 0 during the first block.

If either control is not reproduced, the prefilter is invalid and no candidate may be selected.

A candidate passes only if every fibre retains at least two distinct sand contacts at every recorded block, at least one declared anchor remains attached to each fibre throughout, both declared anchors are present at the terminal block, and all frozen sand-health gates pass. Selection is lexicographic and predeclared: maximize the minimum contact count, maximize minimum anchor degree, minimize sand displacement, minimize force residual, minimize moment residual, then use candidate index. The complete candidate table—not merely the selected case—must be published.

## Sequential decision rule

- No passing candidate: stop and diagnose; do not broaden the search or alter physics in the same attempt.
- Passing candidate: freeze the selected two-fibre placement and its prefilter evidence for independent visual/source audit.
- A full free-release two-fibre rerun requires a separate checkpoint after that audit.
- Four fibres remain blocked until the revised two-fibre full qualification passes.
- Eight or more fibres, flow, deformation, and transient coupling remain blocked.

## Claim boundary

The revision can establish only that a deterministic placement/prefilter method finds a mechanically persistent two-fibre geometry in this one 216-grain periodic packing under a short fixed-fibre dry conditioning test. It cannot establish material calibration, statistical representativeness, permeability, concentration dependence, physical mixing behavior, fibre flexibility, migration, or coupled hydro-mechanical response.
