# Stage35A publication evidence synthesis contract

## Purpose

Create one immutable, publication-oriented synthesis from already accepted evidence. This stage performs no DEM, LBM, GPU, mechanics, migration, deformation, clogging, or coupling execution.

## Frozen inputs

1. Stage31E replicated nested CPD2 evaluation: three clean controls and six matched packing/placement observations at each of 1, 2, and 4 fibres.
2. Stage31F selected CPD4 evaluation: clean reproduction and selected count/placement contrasts used only to establish numerical-resolution stability.
3. Stage34A primary-literature digitization release: clean Leighton Buzzard Sand magnitude benchmark and the approximately 0.4 wt% PET sandy-soil comparator.
4. Stage34C CPD4 fragmentation evaluation: four matched packing/placement contexts for intact, split-2, and split-3 states at fixed solver-resolved PET volume.

Every input is hash-bound in the release. Existing evidence must remain unchanged.

## Questions

1. What claims are supported about clean-sand hydraulic magnitude?
2. What low-concentration fibre-count response is resolved across replicated packing and placement contexts?
3. Are selected responses stable from CPD2 to CPD4?
4. Does idealized fragmentation support a practically important, context-stable hydraulic response that warrants CPD6 or a concentration-by-fragmentation campaign?

## Derived quantities and gates

- Report the Stage31E mean, sample standard deviation, range, and individual K/K0 values at each nonzero fibre count. Fibre count is a categorical model input; achieved dry-mass percentage is a descriptive mapping.
- Report the maximum absolute selected Stage31F CPD2-to-CPD4 ratio shift.
- For each Stage34C contrast family, report all four signed shifts, the median absolute shift, sign agreement, and number meeting `|Delta K/K0| >= 0.005`.
- The preregistered Stage34C promotion rule is satisfied only when a contrast has median absolute paired shift at least `0.005` and at least three of four signs agree.
- If no fragmentation contrast passes both requirements, CPD6 and concentration-by-fragmentation execution remain unauthorized.

## Claim boundary

Allowed language:

- numerically verified and externally benchmarked;
- bounded clean-sand magnitude plausibility;
- replicated low-dose obstruction in the fixed-solid computational system;
- selected effects are stable between CPD2 and CPD4;
- idealized fragmentation response is context-dependent and below the preregistered median practical-effect threshold.

Disallowed language:

- direct experimental validation;
- universal concentration or fibre-length law;
- chemical PET degradation inferred from shortening;
- field-scale permeability prediction;
- mobile-particle, migration, clogging, deformation, transient, or two-way-coupled conclusions.

## Required immutable release

The builder must refuse overwrite and produce:

- `synthesis.json`;
- `concentration_summary.csv`;
- `fragmentation_summary.csv`;
- `claim_matrix.csv`;
- `MANUSCRIPT_RESULTS.md`;
- `stage35a_publication_evidence_synthesis.png`;
- `stage35a_publication_evidence_synthesis.svg`;
- `completion.json` with input and artifact SHA-256 hashes.

The figure must distinguish CPD2 screening, selected CPD4 confirmation, and external literature context. It must display the fragmentation decision threshold and state that no new simulation was run.

## Stop condition

After the release is generated and visually inspected, stop. A subsequent solver campaign requires a new explicit, bounded contract supported by the evidence synthesized here.
