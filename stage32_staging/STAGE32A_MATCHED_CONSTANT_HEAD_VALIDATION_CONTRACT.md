# Stage32A matched constant-head validation contract

## Research question

Can the frozen fixed-solid DEM-LBM model predict clean-sand hydraulic conductivity and the concentration-dependent relative conductivity of a laboratory specimen prepared from the same Leighton Buzzard Sand fraction, void ratio, fibre geometry and orientation convention?

## Evidence role

Stage32A is a **prospective physical-validation protocol**. It does not itself validate the model. Stage31f completed solution verification for selected replicated cases; Stage32A freezes the independent measurements and decision rules required before a physical prediction claim can be made.

## System boundary

- Material: Leighton Buzzard Sand Fraction B or the matched 0.60-1.18 mm fraction.
- Initial state: target void ratio `e = 0.744 +/- 0.010`.
- Fluid: de-aired water, saturated specimen, temperature `20.0 +/- 0.5 degC`.
- Test: steady constant-head saturated conductivity; specimen geometry and head gradient fixed within a laboratory batch.
- Fibres: rigid F37 surrogate, length 0.90 mm, radius 0.05 mm; mass fraction is percent of dry sand mass.
- Primary orientation: isotropic/random. Parallel- and transverse-biased 0.4 wt% specimens are independent mechanism holdouts.
- Primary observables: temperature-corrected hydraulic conductivity `K20` in m/s and matched relative conductivity `K20_mixture / mean(K20_clean_same_batch)`.
- Secondary observables: achieved void ratio, porosity, saturation evidence, repeatability, flow linearity with head, and specimen rejection reason.

## Prospective design

### Phase 1: clean and concentration response

Six independently prepared specimens at each of five levels:

1. clean sand;
2. 0.004691 wt% isotropic fibres (numerical detection-floor level);
3. 0.051576 wt% isotropic fibres;
4. 0.098418 wt% isotropic fibres;
5. 0.401820 wt% isotropic fibres.

Total: 30 specimens. The low-dose level is descriptive because its predicted effect is comparable to placement variability. Monotonicity is not an acceptance gate.

### Phase 2: orientation holdouts

Four independently prepared specimens at 0.401820 wt% for each of parallel-biased and transverse-biased fibres. These eight specimens are executed only after the clean repeatability and state-control gates pass.

## Frozen decision rules

1. At least five valid specimens per six-replicate Phase 1 group and at least three valid specimens per four-replicate holdout group.
2. Clean-sand repeatability coefficient of variation no greater than 5% within a batch.
3. Achieved void ratio within the frozen tolerance; exclusions are decided without viewing conductivity.
4. Clean physical-validation support requires the experimental mean-K20 interval to overlap the frozen numerical clean envelope. The external literature values remain magnitude comparators, not calibration targets.
5. Relative-response support requires the experimental mean-ratio interval to overlap the frozen numerical placement/packing range at two or more of the 0.05, 0.10 and 0.40 wt% levels, and the upper 95% interval at 0.40 wt% must be below 1.0.
6. The 0.004691 wt% condition is reported as a detection-floor test and cannot fail the model by itself.
7. Orientation support requires the 0.40 wt% parallel-biased mean ratio to be below the isotropic mean and the transverse-biased mean to be above it; uncertainty intervals and raw replicates are retained.
8. Failed or rejected specimens remain in the run table with structured reasons. No replacement is added after inspecting the outcome unless the replacement rule was triggered by a pre-measurement quality failure.

## Required controls

- Randomized run order within preparation blocks.
- Dry sand mass, dry fibre mass, water temperature, specimen dimensions, head difference, collection time and collected water mass recorded for every determination.
- At least two head gradients on the first valid clean specimen and one 0.4 wt% specimen to verify Darcy-linearity before the remaining campaign.
- Identical saturation and preparation procedure across clean and mixed specimens.
- Clean controls distributed through the run order rather than tested only at the beginning.

## Deliberately omitted physics

Stage32A does not authorize particle migration, fibre migration, clogging, flexible-fibre mechanics, sand deformation, transient coupling or two-way hydro-mechanical coupling. These mechanisms may be designed only after the matched experiment determines whether the fixed-solid prediction is adequate and identifies the dominant residual bias.

## Completion boundary

The design is complete when its contract, source hashes, randomized matrix, data-capture schema and independent design audit pass. Physical validation remains pending until laboratory data are collected and evaluated without retuning the frozen model.
