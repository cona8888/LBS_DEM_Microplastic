# Stage33A PET fragmentation-length publication protocol — draft

**Status:** research-integration draft; no numerical or laboratory execution authorized.  
**Source deck:** `pet plastic.pptx`, SHA-256 `43b9202f6cf0b482cabf69583ec109b1512e38ed0a4d8f4f8db81119f004720d`.  
**Evidence boundary:** the deck is treated only as source material. Its visible annotations are not raw data and are not used to calibrate or validate the existing model.

## Decision

The deck contains a promising publication concept: hydrothermal treatment appears to transform intact PET wool into a shorter-fragment population, and those measured fragmentation states can be linked prospectively to pore-scale permeability. Fibre or fragment length is scientifically useful here, but it must be described as an **operational descriptor of physical fragmentation state**, not as a unique or universal measure of PET molecular degradation.

Recommended central statement:

> Fibre length is treated as a protocol-calibrated descriptor of PET fragmentation state. Its relationship to degradation severity is established under a specified ageing and standardized mechanical-challenge protocol using independent molecular, chemical, mechanical, and mass-balance measurements.

The publishable causal chain is:

`treatment severity -> chain scission / crystallinity / surface erosion -> embrittlement -> fragmentation under a fixed challenge -> length/width distribution -> pore topology -> relative permeability`

This wording separates chemical degradation from the mechanical event that creates shorter fragments.

## Review of the two-slide source

### Slide 1 — treatment sequence

The slide states `1 g PET wool / 50 mL water`, `120, 140, 160, 180 degC`, and `12 h`. The photographs visually suggest largely intact fibres at 120–140 degC, substantial shortening at 160 degC, and a fragment-rich/sludge-like state at 180 degC. This is strong hypothesis-generating material, but the photographs alone do not establish degradation kinetics or conversion.

Required corrections before publication:

- The title says “thermo catalytic”, while the displayed recipe identifies only PET and water. Name the catalyst, loading, and basis if one was used; otherwise rename the process “hydrothermal treatment”.
- Add untreated PET, reactor volume and fill fraction, pressure, heating/cooling ramps, agitation, water chemistry/pH, recovery and washing procedure, and independent reactor replicates.
- State the initial length and diameter distributions. A photograph of a tangled mat cannot supply a quantitative baseline.
- Provide polymer mass balance, including recovered solids, filter-retained fines, dissolved/oligomeric products, and losses.

### Slide 2 — sludge characterization

Eleven visible annotations were transcribed as `74–226 um`, with `n = 11`, mean `130.45 um`, sample SD `50.88 um`, and median `132 um`. These values are preliminary only. The slide does not identify the treatment condition, independent batch, measurement definition, selection rule, optical detection limit, or filter pore size. A smooth fitted curve is not defensible with eleven selectively annotated objects.

Required corrections before publication:

- Recover the original microscopy files and measurement table. Confirm the condition and reactor replicate for every image.
- For curved fibres use skeletonized contour length; for non-fibrous fragments use maximum Feret dimension. Report width, aspect ratio, and an explicit fibre/fragment classification.
- Use blinded or automated segmentation over predeclared fields. Record all detected objects and the lower detection/censoring limit.
- Replace the fitted distribution with raw points plus an ECDF or box/violin plot by independent batch. Report number-weighted and mass-weighted `D10`, `D50`, `D90`, IQR, and bootstrap intervals.
- Target at least three independent reactors per condition and enough imaged objects to stabilize distribution quantiles; `>=200` objects per condition is a practical starting target, subject to a predeclared precision analysis.
- Confirm that measured objects are PET and quantify material passing the filter or falling below optical resolution.

## Why length alone is insufficient

PET hydrolysis lowers molecular mass, while crystallization and surface erosion can evolve before a specimen visibly shortens. Fragment length also depends on yarn architecture, handling, filtration, sonication, drying, and the mechanical challenge applied after ageing. Published PET studies show both progressive shortening under defined exposure and cases where chemical or morphological damage precedes mass loss or fracture. Therefore treatment temperature, time, length, and “degree of degradation” must not be used interchangeably.

The primary outcome should be the complete measured length/width distribution. A secondary within-protocol index may be reported as

`FI50 = 1 - D50_contour(treatment) / D50_contour(untreated)`.

`FI50` is undefined until an untreated distribution is measured and remains protocol-specific. It must be accompanied by at least one molecular/chemical marker and mass balance.

Minimum corroborating measurements:

1. SEC/GPC `Mn`, `Mw`, and dispersity, or intrinsic viscosity when SEC is unavailable.
2. DSC/XRD crystallinity and thermal transitions.
3. FTIR carbonyl/carboxyl measures, supported where possible by XPS.
4. TPA/EG or BHET/oligomer yield in the liquid phase, matched to the chemistry used.
5. Retained-solid and dissolved-product mass balance.
6. SEM or AFM surface and broken-end morphology.
7. A standardized tensile, flexural, abrasion, or mixing challenge applied identically before and after ageing.

## Proposed prospective experiment

### Stage33A — characterization and evidence gate

- Factors: untreated plus 120, 140, 160, and 180 degC at 12 h. Add time as a second factor only if reactor capacity supports a balanced design.
- Replication: at least three independently treated reactor batches per condition.
- Split each batch before a predeclared mechanical challenge. The pre/post split distinguishes chemical weakening from the force that produces shortening.
- Measure contour length, Feret length, width, aspect ratio, particle count, broken-end fraction, morphology, chemistry, crystallinity, molecular mass, and complete mass balance.
- Analyze temperature as a categorical factor first; do not impose monotonicity.
- Gate: no numerical length classes are frozen until raw files, units, segmentation settings, batch identities, and data hashes pass an independent audit.

### Stage33B — variable-length numerical verification

The accepted Stage32 laboratory-validation release remains frozen at the existing 0.90 mm F37 surrogate and is not retrofitted. A separate PET branch must first:

- freeze measured PET density, diameter/width distribution, length definition, and whether concentration means percent of dry-sand mass or total-mixture mass;
- replace a fixed 37-node centreline with approximately fixed physical node spacing as length varies;
- correct capsule/end-cap volume bias, which becomes material for many short fragments;
- pass mass, solid-volume, mask, periodicity, and exact equilibrium-closure tests;
- pass a segmentation-invariance control in which one unchanged centreline is divided into adjacent pieces without changing its solid mask or permeability;
- repeat CPD2/CPD4 and selected CPD8 convergence checks for the short-fragment domain.

The current nominal geometry is 0.90 mm long and 0.10 mm in diameter. Applying that diameter to the slide median of 0.132 mm would yield aspect ratio only about 1.32, so these objects may be particles rather than fibres. Measured width is a mandatory model-form gate.

### Stage33C — two complementary hydraulic designs

**Mechanistic length/count decomposition.** Cross three measured length classes with counts 1, 2, and 4 using matched sand packings and placement blocks. Treat concentration as a derived variable; do not include it in the same statistical model because, for fixed radius and density, it is algebraically determined by count and total contour length.

**Realistic matched-mass fragmentation.** At fixed PET dry-sand mass fraction, sample untreated, intermediate, and strongly fragmented empirical distributions. Shorter fragments necessarily increase particle count; that increase is part of the fragmentation process, not a nuisance to conceal. Include a matched-mean narrow-versus-broad distribution control to test whether tails matter.

For constant density and radius, the dry-sand concentration is

`C_d = 100 * sum(rho_pet * pi * r_i^2 * L_i) / M_sand`.

Primary hydraulic response: paired `k/k0`. Secondary mechanisms: total contour length, projected area normal to flow, exposed end area, fibre/fragment–sand contacts, pore throats intersected, connected pore fraction, tortuosity, orientation tensor, packing variance, placement variance, and numerical-resolution uncertainty.

Start with CPD2 screening. Promote only predeclared endpoints and largest contrasts to CPD4; do not launch production cases from this draft.

### Stage33D — matched physical validation

Prepare actual treated PET–LBS specimens at the same PET dry-mass fraction, void ratio, temperature, saturation protocol, and constant-head procedure. Compare treatment-specific `K20/K20_clean` intervals with frozen numerical ranges without retuning. Randomize preparation order, distribute clean controls through blocks, and retain exclusions with reasons.

## Predeclared hypotheses

- **H1:** Under a fixed ageing and mechanical-challenge protocol, treatment condition changes the PET length/width distribution and at least one independent molecular, chemical, or mechanical degradation marker.
- **H2:** At fixed PET dry-mass concentration and sand state, replacing the untreated distribution with a measured fragmented distribution changes `k/k0`; no monotonic direction is imposed.
- **H3:** Length/count interaction depends on `L/D50_sand`, aspect ratio, orientation, and pore-placement context.
- **H4:** At matched PET mass and mean length, broad or bimodal distributions can differ hydraulically from narrow distributions because short and long tails occupy different pore features.
- **H5:** Treatment effects on permeability are mediated only partly by length; width, fragment count, shape, chemistry, and packing context may explain residual effects.

## Claim boundary for a paper

If the evidence gates pass, the defensible conclusion is:

> Within the tested PET material, hydrothermal protocol, fragment-size distributions, concentration, LBS state, and fixed-solid flow domain, treatment-associated fragmentation changed relative permeability by the reported amount. The matched-mass response includes the increase in fragment number required by mass conservation.

Do not claim that length alone measures degradation age; that the response is independent of fragment number; or that the model predicts migration, entanglement, flexible-fibre motion, clogging evolution, chemical ageing in situ, field-scale permeability, or long-term coupled behavior.

## Suggested paper structure

Working title: **From PET fragmentation state to pore-scale permeability in sand: a hydrothermal-treatment and DEM–LBM study**

1. Characterize treatment-dependent molecular and morphological change.
2. Define empirical fragmentation states from audited distributions.
3. Verify variable-length digital geometry and numerical resolution.
4. Separate mechanistic length/count effects from realistic matched-mass fragmentation.
5. Validate selected states with blinded matched constant-head tests.
6. Discuss detection censoring, mass conservation, packing variability, and fixed-solid limits.

Suggested main figure: treatment conditions and chemical evidence on the left; audited length/width distributions in the center; pore-scale obstruction and `k/k0` on the right. The figure should explicitly show the standardized mechanical challenge between chemical ageing and measured fragmentation.

## Primary literature basis

- Sørensen et al. (2021), *Science of the Total Environment*, “UV degradation of natural and synthetic microfibers causes fragmentation and release of polymer degradation products and chemical additives”: under a defined simulated-sunlight/seawater protocol, median PET fibre length decreased from 3115 um initially to 2492, 1249, and 257 um after 14, 28, and 56 d, respectively. https://doi.org/10.1016/j.scitotenv.2020.143170
- Arhant et al. (2019), *Polymer Degradation and Stability*, “Impact of hydrolytic degradation on mechanical properties of PET—Towards an understanding of microplastics formation”: water ageing at 80–110 degC linked chain scission to embrittlement, with a reported critical molar mass near 17 kg/mol. This supports molecular degradation -> embrittlement -> mechanically driven fragmentation. https://doi.org/10.1016/j.polymdegradstab.2019.01.021
- Pirzadeh, Zadhoush, and Haghighat (2007), *Journal of Applied Polymer Science*, “Hydrolytic and thermal degradation of PET fibers and PET granule: The effects of crystallization, temperature, and humidity”: https://doi.org/10.1002/app.26788
- Aneja et al. (2024), *Fibers*, neutral-hydrolysis model including simultaneous fragmentation and depolymerization: https://doi.org/10.3390/fib12100082
- Sarno et al. (2021), *Environmental Science & Technology Letters*, “Accelerated Hydrolysis Method for Producing Partially Degraded Polyester Microplastic Fiber Reference Materials”: 10% NaOH at 90 degC was evaluated separately by SEM, residual-solid gravimetry, and terephthalic-acid/ethylene-glycol analysis; >90% gravimetric degradation occurred by 3 h, while complete disappearance required 24 h. https://doi.org/10.1021/acs.estlett.0c01002
- Palacios-Marin et al. (2022), *Textile Research Journal*, repeated-laundering evidence that released-fibre length also depends on textile architecture and release history: https://doi.org/10.1177/00405175221090971

## Immediate handoff

1. Obtain the raw microscopy images, measurement spreadsheet, treatment identity for slide 2, untreated material, and independent batch identifiers.
2. Confirm whether a catalyst was used and document its identity and loading.
3. Confirm PET grade, density, original fibre diameter/width, and whether the source team permits reuse of images and data in a joint publication.
4. Keep Stage32 unchanged. Build and independently audit a Stage33A characterization package before any new DEM/LBM execution.
