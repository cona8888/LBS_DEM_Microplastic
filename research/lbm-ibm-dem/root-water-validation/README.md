# Root–soil–water validation audit

**Decision: the integrated root–soil–water model is not yet experimentally validated.** The current equilibrium-water application passes important numerical checks, but the earlier approximately 1% force contrast is not qualified against interface-width uncertainty. No parameters were refitted in this audit.

## A. Verdict

Limited component agreement: the frozen apparent hydraulic coefficient predicts 5.76 cm3 extraction against 6.00 cm3 measured for the held-out larger saturated ceramic cup. Biological conductivity transfer fails the selected accuracy gate. Independent wet-root force, suction and displacement validation has not run.

## B. Actual scope

The executable audited is the complete RhizoField 2D equilibrium bridge coupled to a spring-supported grain and a two-compartment hydraulic model. Its baseline full-source commit is 935f05c9f394c65742a6b829bebb4385e801c117. It is distinct from the public dry-root contact driver, the separate radial Richards reference and the native single-phase LBM/IBM/DEM implementation. No complete path connects a growing flexible root, moving granular soil and a water–air LBM field in this milestone.

This directory publishes the audit, compact evidence and optional refinement patch. It is NOT the entire executable water application. The complete source/harness/data are delivered separately as RhizoField_water_validation_source.zip and RhizoField_water_validation.bundle. Full-source history ends at 44301ea0df7fc7498f610757d56cc94b82ef0401. See DELIVERY.json for hashes. The original defaults, mechanical and hydraulic calibration files remain unchanged.

## C. Consequential findings

1. **Supported numerical/physical-readout concern:** at fixed actual gap 677.5 micrometres and fixed endpoint inventories, the root/outer attraction difference is -1.03069% at grid 25 micrometres and interface parameter W=125 micrometres. At grid 6.25 micrometres it is -0.90006% for W=125 and -0.15486% for W=62.5. Negative means root uptake leaves smaller attraction. These are frozen-endpoint tests, not full drying reruns at each width. Two widths do not establish a sharp-interface limit.
2. A curvature-derived Young–Laplace pressure check differs from the reconstructed bulk pressure by 11.06% in the original-width root-dried state on the finest grid; halving W reduces the worst endpoint discrepancy to 0.381%. This diagnostic does not prove the discrete energy algebra incorrect, and its successful refinement is not physical validation.
3. **Supported measurement-mapping concern:** the exactly conserved phase inventory integral[(1+phi)/2] differs by 30–38% from a bulk-branch-normalised liquid-area diagnostic in the original fine-grid endpoints. The latter is not asserted to be the true experimental volume either. Roundoff-level closure of the model variable is not gravimetric water-volume accuracy.
4. **Mechanism control:** after reopening the positive hydraulic link, turning extraction off, fixing gap and total remaining water, and solving common pressure independently from the two endpoint states, attractions are 0.16900361 and 0.16900366 N/m. Contrast is only -0.0000275%. The earlier contrast reflects retained near/far redistribution under its protocol, not demonstrated irreversible reinforcement. This is a steady limit, not a prediction of physical relaxation time.
5. **Missing evidence:** no independent experimental bridge-force curve or full wet-root dataset was ingested. Liao et al.'s data availability statement identifies an XLSX workbook, but its numerical data were not retrieved. Their finite-length 3D forces also require a justified conversion before comparison with 2D per-depth forces.

## D. Changes

Optional Mesh.interface_width and grids through 6.25 micrometres allow independent numerical refinement while retaining physical surface tension and original defaults. The patch consistently updates gradient, wall-energy and pressure/force scales. The full-source package adds frozen-input hashes, new regression tests and executable conservation, holdout, temporal, curvature, width and common-pressure checks. No friction, membrane coefficient or calibrated angle was retuned to pass a gate.

## E. Verification

See gates.csv. Across full coupled runs, maximum phase-water ledger residual was 1.8529e-21 m2 and force residual 9.6649e-8 N/m. Halving the hydraulic/opening increments changed force by at most 0.00673% and extraction by 0.2826%. An independent stress-contour force differed by at most 1.4173% in the base field ladder; energy/virtual-work error was 1.7745e-5%. The separate radial Richards solver showed approximately second-order steady-flow convergence (128-cell flow error 0.0000583%) and transient budget residual below 9.83e-20 m2. Those are numerical checks, not empirical validation of LBM.

All 23 Python application/calibration/refinement tests and the contact/integration and native core suites passed. A clean local clone rebuilt the native application, passed 23 tests and reproduced the fine-grid coupled history byte for byte on the same hardware/software. Existing native quadrature compilation warnings are logged in the complete evidence package.

## F. Physical validation

The cup geometry holdout has -4% mean error, within a predeclared 10% component gate. Source Table 3 reports n=5 per geometry and SD 0.3/0.5 cm3; propagating calibration and held-out mean uncertainty gives residual -0.24 cm3 with approximate 95% half-width 1.76 cm3. Geometry and model-form uncertainty are omitted. This is a weak, single-condition saturated analogue check, not a tissue-permeability validation.

Frozen date-held-out field conductivities overpredict beech by 63.86%, oak by 84.55% and spruce by 33.69%; all fail the selected 20% mean-error gate. Same-site chronological holdouts are not independent-site validation. Reported group SD is not a mean confidence interval. The prior project Table II transcription was retained; the publisher PDF was not re-downloaded during this audit.

## G. Demonstrator

Root radius 1 mm, grain radius 0.35 mm, initial gap 0.60 mm. Three matched protocols: root extraction, equal time-resolved outer extraction and sealed control. The water benchmark remains open-gap, with no root–grain mechanical contact. Forces are N/m depth and phase inventories are m2 per metre depth. Root growth, flexible-root mechanics, soil preparation, permeability and whole-root pull-out are not inferred.

## H. Reproduction and publication

From the supplied COMPLETE source, run `python -m validation_water.reproduce`. Individual commands and frozen-input hashes are included in that package. Python 3.13.5, NumPy 2.3.5, SciPy 1.17.0, GCC 14.2.0, one BLAS/OMP thread on AMD EPYC 9V74. This remote audit does not claim that the public root-contact subtree can run the water suite without the separately supplied application/seed. Main is not modified and no PR is merged by this publication.

## I. Remaining admission gates

Physical liquid-volume definition and additional width convergence; measured advancing/receding wetting for the actual analogue; geometry-matched force–gap–volume validation with frozen parameters; hydraulic tests separating tissue, soil and wetted-area resistance; only then a fully coupled wet-root experiment measuring force, suction, flow and displacement.

## Sources

Köhne (2005), Table 3, https://doi.org/10.2136/vzj2004.0111.
Leuschner et al. (2003), Table II, https://doi.org/10.1051/forest:2003071 (existing project transcription).
Rüdinger et al. (1994), https://doi.org/10.1093/jxb/45.10.1413 (applicability, not matched validation).
Liao et al. (2026), https://doi.org/10.1002/aic.70229 (experimental workbook not ingested).
