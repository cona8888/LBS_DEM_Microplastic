# Stage33B — PET morphology-to-pore-scale bridge preflight (V1)

**Status:** design complete; experimental acquisition, model calibration and numerical execution remain closed.  
**Date:** 2026-08-31  
**Purpose:** convert the clarified water-only PET treatment and future raw microscopy into a publication-grade morphology data set and, only after empirical gates pass, a controlled geometry input for the existing fixed-solid DEM/LBM hydraulic framework.

## 1. Scientific position

The source experiment is a **water-only hydrothermal treatment** of 1.0 g PET wool/cotton in 50 mL water for 12 h at 120, 140, 160 or 180 °C in a sealed passive-pressure chamber. No catalyst or other reagent was added. This is better publication wording than “no chemical was used,” because water is a reactant in hydrolysis. Pressure is autogenous and was not independently imposed in the available record. Consequently, temperature and pressure history are coupled and the study must not claim an independent pressure effect.

The source photographs support a temperature-associated morphology progression, with the largest visible fragmentation/morphological change at 180 °C. Fibre or fragment length is a valid **physical fragmentation response**, but length alone is not a molecular-degradation scale. PET hydrolysis must be established independently through molar-mass/end-group/product evidence. A shorter object can arise from handling, cutting, recovery or imaging as well as chemical embrittlement; conversely, chain scission can occur before macroscopic fragmentation is visible.

The current 180 °C slide composite is retained only as workflow-development evidence:

- 11 displayed lengths: 74–226 µm; median 132 µm;
- seven provisionally isolated objects: exploratory aspect ratio 2.85–6.85; median 4.08;
- embedded source: annotated JPEG with compression, overlaps and baked-in graphics;
- these values may define a provisional code-verification envelope, but must not calibrate a publication model.

## 2. Publication question and hypotheses

### Primary experimental question

At fixed 12 h duration and fixed PET/water loading, how does treatment temperature alter the batch-level joint distribution of PET object size and shape, and is that physical fragmentation associated with independently measured hydrolytic degradation?

### Primary hypotheses

1. The temperature-conditioned morphology distribution changes across untreated, 120, 140, 160 and 180 °C material.
2. Any shift toward shorter objects is accompanied by at least one independent hydrolysis indicator: reduced number-average molar mass, increased carboxyl end groups, or quantified soluble PET products.
3. Hydraulic response is governed by a joint geometry/topology state—not length alone—including width, straightness/curvature, orientation, placement and pore-throat-normalized size.
4. No monotonic permeability trend is imposed. Shortening may reduce bridging while increased object count, placement in throats, irregularity or packing alteration may increase obstruction.

### Claims that remain prohibited

- “180 °C is the most chemically degraded” from photographs alone;
- a universal conversion from fibre length to degradation level;
- an independent pressure effect without controlled pressure or a measured pressure history;
- validation of the existing straight-string geometry as the actual recovered PET shape;
- mobile-fibre, deformation, migration or clogging claims from fixed-solid simulations;
- absolute permeability validation before the blinded Stage32 laboratory campaign is populated and accepted.

## 3. Evidence ladder

| Tier | Evidence | Required interpretation |
|---|---|---|
| E0 | Hash-bound recipe, vessel, time, actual temperature and pressure histories, recovery log | Treatment provenance only |
| E1 | Raw calibrated microscopy with blinded object selection | Physical size/shape distribution |
| E2 | Recovery mass, fragment count per recovered mass, broken-end class and standardized handling control | Physical fragmentation evidence |
| E3 | SEC/GPC molar-mass distribution plus an orthogonal method such as carboxyl end groups/FTIR, DSC crystallinity, and liquid-phase HPLC/LC | Hydrolysis/chain-scission evidence |
| E4 | Closed solid/liquid mass balance and repeatable batch effect | Quantified chemical degradation or conversion |
| E5 | Hash-bound morphology-to-geometry translation with solution verification and held-out validation | Numerical geometry claim only |

Length may be discussed as a degradation-conditioned morphology response after E0–E2. It may be called a degradation proxy only if its batch-level association with E3 is demonstrated prospectively. Conversion requires E4.

## 4. Experimental design inherited from Stage33A

- Five material levels: untreated/as-received, 120, 140, 160 and 180 °C.
- Three independent reactor blocks: 15 independently charged, processed, recovered and dried PET batches.
- Fifteen matched water blanks for contamination and soluble-product background.
- Three descriptive as-received references from the same confirmed PET lot.
- Fixed recipe: 1.0 g PET and 50 mL water, 12 h at set point.
- Randomize vessel/run order within block; blind imaging, segmentation and primary chemistry identifiers.
- Record reactor internal volume, fill fraction, ramp, time-at-temperature, cooling and actual pressure history. If pressure is not logged, retain “temperature/autogenous-pressure treatment condition” as the factor label.
- Freeze washing, filtration, drying and transfer steps. Record every loss and preserve all filter fractions.
- Use an unchallenged aliquot for treatment effect and a preregistered standardized-handling aliquot to estimate handling-induced fragmentation.

The experimental unit is the reactor batch, not an individual fragment or image field. Object measurements are nested observations and must not be treated as independent treatment replicates.

## 5. Image acquisition and morphology record

### Acquisition gates

1. Obtain original uncropped images for all five material levels with scale/calibration metadata.
2. Sample fields by a frozen random or systematic rule; do not select only visibly fragmented regions.
3. Use at least two magnifications if required to cover the full distribution, with an overlap band for cross-magnification agreement.
4. Save raw images losslessly; hash-bind raw files, calibration, masks, segmentation parameters and adjudication decisions.
5. Record blank fields, zero-object fields, border censoring, aggregates and below-detection truncation.
6. Confirm PET identity on a representative subset and document whether recovered material includes intact textile bundles.

### Per-object variables

- maximum Feret dimension, `Fmax_um`, for every accepted object;
- geodesic contour length, `Lc_um`, only for unbranched two-endpoint fibres;
- end-to-end distance, `Le_um`, and straightness `S = Le/Lc`;
- median/minimum/maximum local width and width coefficient of variation;
- aspect ratios `Lc/W50` and `Fmax/Fmin`, kept as distinct definitions;
- centreline curvature: mean, RMS and 95th percentile, with a dimensionless curvature-width measure;
- projected area, perimeter, convex-hull area, solidity and circularity;
- endpoint condition, fraying, branch count, inflection count, cracks/pits and thinning flags;
- shape class: straight fibre, curved fibre, branched/peeled fibre, ribbon, compact irregular fragment, or aggregate/bundle;
- treatment, reactor block, batch, aliquot, field, magnification and QC/exclusion code.

The primary empirical object is the batch-conditioned joint distribution

`p(Lc, width, straightness, curvature, shape_class | treatment, batch)`.

Marginal means are secondary. Report medians, robust spread, quantiles, detection limits, class fractions and batch-level uncertainty. Keep number-weighted and mass/volume-weighted summaries separate.

## 6. Chemical and physical degradation measurements

### Required core

- SEC/GPC: `Mn`, `Mw` and dispersity for untreated and every independent treatment batch;
- recovery mass for every solid fraction and dry residue;
- liquid-phase TPA/MHET/BHET/EG or other agreed PET-product quantification by calibrated HPLC/LC or an orthogonal validated method;
- at least one orthogonal solid-state measure: carboxyl end groups/validated FTIR index and DSC crystallinity;
- microscopy morphology described above.

### Recommended confirmation

- tensile or fracture response of a retained bulk-fibre aliquot where specimen geometry permits;
- SEM/confocal subset for surface damage and three-dimensional width/thickness checks;
- reagent/water blanks and spiked recovery controls;
- carbon or component mass balance sufficient to distinguish redistribution from loss.

Do not collapse these measurements into a single “degradation index” until direction, scaling and repeatability are preregistered and independently confirmed. The primary analysis should show physical fragmentation and molecular hydrolysis on separate axes.

## 7. Morphology-to-numerical geometry mapping

### Geometry families

| Empirical class | Future numerical representation | Current authority |
|---|---|---|
| Straight fibre | Spherocylinder or bead/segment centreline with measured length and width | Existing straight-string work is an idealized baseline only |
| Curved fibre | Piecewise centreline preserving contour length, end-to-end distance and curvature statistics | Verification design only |
| Branched/peeled fibre | Explicit branch graph or excluded sensitivity class | Not production-authorized |
| Ribbon | Anisotropic strip/voxel geometry preserving projected dimensions and solid volume | Not production-authorized |
| Compact irregular fragment | Voxel/mesh or calibrated superquadric; never forced into a rod | Not production-authorized |
| Aggregate/bundle | Explicit topology or separate aggregate class | Excluded from single-object calibration until topology is measured |

### Required dimensionless inputs

- `Lc/dt`: contour length divided by local pore-throat diameter;
- `W50/dt`: median width divided by local pore-throat diameter;
- aspect ratio and straightness;
- curvature × width or curvature × throat diameter;
- orientation relative to the pressure gradient;
- solid volume fraction and PET dry mass fraction;
- placement class: pore body, throat, grain contact or wall;
- topology: isolated, separated, crossing, bridging and contact count;
- clean porosity, throat-size distribution and packing seed.

`dt` must come from the actual clean numerical packing or matched experimental pore-size measurement. A literature threshold must not be copied as a universal throat criterion.

### Mass and geometry closure

For each mapped object, preserve empirical contour length, width definition and class. For comparisons between shape families, either hold PET solid volume constant or state explicitly that count is held constant; never change both silently. The voxelized/segment solid volume, bounding dimensions and centreline must pass pre-run checks. Joint empirical dependence among length, width and shape class must be retained rather than sampling independent marginals.

## 8. Numerical verification ladder — design only

No case is launched under this preflight. After empirical gates close, the first permitted wave is code/geometry verification, not a production concentration study.

1. **Primitive tests:** one straight, one curved and one compact object; verify dimensions, volume, orientation and mask topology analytically.
2. **Segmentation invariance:** subdivide an identical centreline at increasing segment count; solid volume and `k/k0` must converge without geometry drift.
3. **Resolution:** CPD2 → CPD4 and one bounded higher-resolution sentinel for each selected class; retain the existing shift gates unless a preregistered stricter gate is adopted.
4. **Clean reproduction:** exact hash-bound clean control for every packing/context.
5. **Paired placement:** compare shapes in the same clean packing and placement context; do not infer a shape effect from unmatched packings.
6. **Finite-domain and seed checks:** at least three independent packing contexts before a population claim.
7. **Held-out confirmation:** freeze the selected contrasts before opening the held-out batches/geometries.

Primary hydraulic response remains intrinsic-permeability ratio `k/k0`, with pressure drop and flux as co-primary numerical records. Secondary diagnostics include local velocity, throat conductance, stagnant volume and flow partition. Numerical health, convergence and exact equilibrium closure are mandatory.

## 9. Provisional verification envelope from the slide

The following values are permitted only for non-calibrating software tests:

- length sentinels: 75, 132 and 225 µm;
- aspect-ratio sentinels: 3, 4 and 7;
- shape sentinels: straight, one controlled curved centreline and one compact irregular object;
- all are labelled `slide_derived_exploratory_not_empirical_calibration`.

No hydraulic result from these sentinels may be described as the 180 °C material response. Raw representative images and batch distributions must replace them before a physical interpretation.

## 10. Analysis plan

- Model treatment with reactor block/batch as the replication level and image/object observations nested within batch.
- Estimate distributional shifts and batch-resampled confidence intervals; do not rely only on object-level p-values.
- Test monotone temperature trend only as a planned contrast, while retaining an unrestricted treatment model.
- Relate morphology to `Mn`, carboxyl/product measures and crystallinity at the batch level, with uncertainty in both variables.
- Predefine the minimum relevant effect for length distribution, shape-class fraction and chemistry before unblinding.
- Use untreated material and water blanks as negative controls; use spiked analytical recovery as a positive method control.
- Treat actual pressure history as a recorded covariate/mediator, not an independently randomized factor.

## 11. Literature basis and boundary

- Water-only PET at 180 °C is chemically plausible: Kazarian and Martirosyan observed PET decomposition and terephthalic acid at 180 °C and 1.0 MPa, but that apparatus is not proof of conversion in the present chamber ([DOI](https://doi.org/10.1039/B202119F)).
- A textile-fibre study reported no detectable depolymerization for PET fibre at 180 °C/12 bar after a much shorter exposure, while 250 °C/39 bar produced substantial terephthalic acid; this demonstrates condition and material sensitivity ([DOI](https://doi.org/10.1111/1751-7915.12734)).
- In contrast, a cotton/PET textile study in pure water at 180 °C measured strong number-average-molecular-weight loss over 10–180 minutes even while yarn remained visibly present at the early time point. This is direct evidence that molecular chain scission and visible fragmentation need not advance together ([DOI](https://doi.org/10.1021/acsomega.3c09350)).
- Water treatment of amorphous and semicrystalline PET at 180 °C showed that chain scission, crystallization and amorphous-region loss depend on initial structure ([DOI](https://doi.org/10.1016/0032-3861(93)90726-Q); [DOI](https://doi.org/10.1080/00222349408248096)).
- Steam treatment at 200 °C linked decreasing molecular weight, increased crystallinity and progressive breakup into fine particles, supporting the mechanistic sequence without providing a quantitative calibration for the present liquid-water condition ([DOI](https://doi.org/10.1295/polymj.PJ2007237)).
- PET hydrolysis kinetics depend on temperature, water activity and morphology/crystallinity; chain scission should be measured rather than inferred from appearance ([DOI](https://doi.org/10.1016/j.polymer.2018.03.043); [DOI](https://doi.org/10.1016/j.polymdegradstab.2019.01.021)).
- Polyester-fibre hydrodynamics depend on length, curliness and orientation, supporting a joint morphology representation ([DOI](https://doi.org/10.1016/j.scitotenv.2022.156011)).
- Fibre length relative to pore opening controls retardation in a bead–rod-chain pore-scale model; that study itself required experimental validation ([DOI](https://doi.org/10.1016/j.advwatres.2018.08.011)).
- Direct monofilament pore-scale imaging shows trapping/waiting behaviours not represented by ordinary passive-solute transport ([DOI](https://doi.org/10.1029/2024WR037901)).
- Sand-column evidence shows that retention need not reduce flow under every tested condition, and soil studies report that fibre-induced packing changes can reverse a simple obstruction expectation ([DOI](https://doi.org/10.1016/j.scitotenv.2022.155888); [DOI](https://doi.org/10.1021/acs.est.2c09822); [DOI](https://doi.org/10.1016/j.jhazmat.2022.128912)).

These studies motivate variables and controls; they do not validate the current model or supply substitute observations for this PET wool.

## 12. Fail-closed gates and next handoff

The next handoff is **experimental acquisition and method qualification**, not numerical execution. All of the following must be true before empirical geometry is frozen:

1. PET lot, initial textile architecture, density, moisture, additives/finish and starting size distribution are documented.
2. Reactor geometry, fill, temperature and pressure histories, recovery, washing, filtration and drying are complete.
3. Original raw images for all conditions and calibration metadata are present and publication rights are confirmed.
4. Segmentation repeatability, inter-analyst agreement, detection limits and field-sampling rules pass.
5. Three independent batches per temperature exist with batch-level chemistry and morphology.
6. Molecular/chemical hydrolysis evidence is available; length is not the only degradation measure.
7. A frozen joint-distribution file and object-to-geometry mapping are independently audited.
8. Stage32 absolute-permeability validation remains separate and is not claimed until laboratory data are populated and accepted.

Until then, Stage31f remains accepted numerical solution verification for idealized fixed straight fibres; Stage33A remains a characterization preflight; and Stage33B authorizes no reactor run, image relabelling, DEM/LBM execution, mechanics rerun, migration, deformation, clogging or coupling.
