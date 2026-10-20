# Stage33A PET hydrothermal-fragmentation characterization contract v2

## Status and source correction

This version incorporates the user's 29 August 2026 clarification of `pet plastic.pptx`. It is a prospective experimental-characterization preflight and does not authorize laboratory or numerical execution. Version 1 and its audit remain immutable.

Confirmed source facts are:

- 1 g PET wool/cotton was treated in 50 mL water;
- no catalyst or other added chemical was used;
- the material was held for 12 h at 120, 140, 160 or 180 degC in a sealed passive-pressure chamber;
- pressure was generated passively/autogenously during heating and was not an independently controlled factor in the available record;
- slide 2 shows the recovered 180 degC, 12 h material;
- the 180 degC condition shows the greatest visible fragmentation/morphological change in the displayed photographs.

The correct source description is therefore **water-only hydrothermal treatment of PET wool**, not thermocatalytic treatment. Because temperature, water vapour pressure, compressed headspace gas and hydrothermal severity co-vary in a sealed vessel, the existing source cannot separate a pressure effect from a temperature effect.

## Research question

Under one fixed 12 h water-only hydrothermal protocol and one PET grade/lot, do process-matched control, 120, 140, 160 and 180 degC treatments produce reproducibly different molecular states and different fragmentation responses to a standardized mechanical challenge?

Fibre or fragment length is an operational descriptor of physical fragmentation state. It is not by itself a molecular-degradation scale. The existing photographs support the hypothesis that hydrothermal severity changes morphology; they do not quantify chain scission, conversion or degradation kinetics.

## Evidence roles

1. **Historical source evidence:** the two-slide deck supplies the treatment recipe, qualitative progression and a preliminary annotated 180 degC image.
2. **Exploratory image evidence:** the embedded annotated JPEG may be used to reproduce the displayed 11 lengths and to test a future measurement workflow. It may not be treated as raw publication data.
3. **Prospective confirmation evidence:** independent reactor batches, raw microscopy and molecular/chemical measurements are required for a publication claim.
4. **Future numerical evidence:** only audited empirical length, width, curvature and shape distributions may define a later PET geometry branch. Existing straight-string simulations remain idealized and are not retroactively relabelled as the observed PET morphology.

## Experimental boundary and Wave-1 design

- Material: one chemically confirmed PET grade and lot, with measured density, moisture, additives/finish, feed carbon fraction, initial length and width distributions.
- Source treatment levels: 120, 140, 160 and 180 degC for 12 h, 1 g PET in 50 mL water.
- Prospective control: a process-matched ambient water control, explicitly identified as a new design element rather than a condition shown in the source deck.
- Blanks: water-only process blanks at every temperature in every block.
- Experimental unit: an independently weighed, charged, processed, recovered and dried vessel batch.
- Replication: three complete blocks, giving 15 independent PET process batches, 15 water blanks and 3 descriptive as-received references.
- Split plot: each recovered PET batch is divided by mass into unchallenged and standardized-challenge aliquots.
- Randomization: vessel/run order is randomized within block, with imaging and challenge orders randomized separately and sample codes blinded through primary QC.

Wave 1 is method locking, feasibility and variance estimation. An independent confirmation wave remains necessary for confirmatory inference.

## Co-primary endpoints and terminology

1. Batch-level number-weighted median maximum-Feret dimension after the standardized challenge, analysed as `log(D50_Feret_um)`.
2. One predeclared molecular chain-scission endpoint, preferably `log(Mn_g_mol)` by SEC/GPC; intrinsic viscosity may be a frozen fallback.

The mechanistic secondary endpoint is

`FSI = log(D50_Feret_pre / D50_Feret_post)`.

Until independent molecular evidence is available, use:

- “hydrothermal treatment severity” for the process;
- “fragmentation” or “morphological change” for the photographs;
- “highest visible fragmentation among the displayed conditions” for 180 degC.

Do not use “most chemically degraded,” “conversion,” or an independent “pressure effect” based only on the slide images.

## Morphology rules

- Maximum Feret dimension is the universal object-size measure.
- Skeletonized geodesic contour length is used only for accepted, unbranched elongate objects with two endpoints and no branch points.
- Width is measured with a validated distance-transform or equivalent method along the centreline; maximum/minimum Feret ratio is reported separately.
- Record aspect ratio, straightness (`end-to-end / contour length`), curvature or tortuosity, solidity, circularity, broken-end class, branching and cluster/aggregate status.
- Keep compact fragments, straight fibres, curved fibres and clusters as explicit classes. Do not force every object into the straight-string model class.
- Border-clipped objects are censored, below-detection material creates truncation, and zero-object fields remain recorded.
- Raw images, calibration files, segmentation settings, masks and adjudication decisions are immutable and hash-bound.

The embedded slide-2 image is a JPEG composite with baked-in red brackets, labels and histogram. It is suitable only for exploratory workflow testing because compression, overlays and overlap bias object edges, widths, curvature and aspect ratios. Publication estimates require the original uncropped micrograph and calibration metadata.

## Relation between experiment and the current numerical model

The current fibre representation is a deliberately simple straight string. It can test an idealized length/count obstruction mechanism, but it does not yet represent the observed irregular 180 degC fragments.

A future empirical PET branch must therefore freeze at least:

- length definition and distribution;
- width/diameter distribution and PET density;
- morphology-class fractions;
- straightness/curvature distribution;
- cross-section and end-cap convention;
- dry PET mass fraction relative to dry sand;
- the mapping from an empirical object to a numerical centreline or compact fragment.

The future geometry must pass solid-volume conservation, mask invariance, segmentation-invariance and CPD2/CPD4/selected-CPD8 solution-verification gates before any permeability conclusion.

## Remaining fail-closed blockers

`B01` is closed: the process is confirmed water-only hydrothermal treatment with no catalyst.

The remaining execution blockers are:

1. PET grade, lot, density, feed carbon, purity/additives and starting length/width distributions.
2. Original 180 degC raw microscopy, calibration metadata and the measurement/selection record behind slide 2.
3. Reactor volume/fill fraction, temperature ramp/cooling history, measured pressure history if available, safety and quantitative-transfer procedures.
4. Standardized mechanical-challenge dose and calibration.
5. Filter train, recovery, drying and handling-fragmentation controls.
6. Imaging calibration, probability sampling, completeness, segmentation, censoring and PET-confirmation rules.
7. SEC/IV and liquid-product methods, blanks, limits of quantification, recoveries and carbon attribution.
8. Analysis-mass allocation for the 1 g PET feed.
9. Blinded identifiers, numerical QC, exclusions, minimum relevant effects and confirmation-wave replication.
10. Image/data ownership and publication permission.
11. Final laboratory safety/operating release after all method records are frozen.

Until these gates close, the strongest defensible conclusion is that the source shows a **temperature-associated hydrothermal fragmentation/morphology progression**, with the 180 degC material providing a preliminary high-severity morphology case.

## Preserved boundaries

- Stage32 remains unchanged and pre-data.
- The F37 polyethylene surrogate is not relabelled PET.
- No new DEM/LBM, mechanics, migration, clogging, deformation or coupling run is authorized by this contract.
- No absolute permeability-validation or molecular-degradation claim is authorized.
