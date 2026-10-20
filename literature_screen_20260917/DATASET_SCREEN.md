# Literature and public-data screen

17 September 2026. Literature assessment only. No new simulation, parameter fitting, manuscript or publication figure was produced.

## Decision

- **Applicable evidence exists, including fibre measurements.** Do not abandon literature comparison on the grounds that there are no data.
- **No directly matched, ready-to-use validation dataset was identified** for dilute, rigid PET fibres versus equal-volume spheres initially distributed through our fixed, saturated sand matrix under the current low-speed flow.
- Published tables and digitizable measurements can support separate, literature-matched benchmarks or explicitly qualitative comparisons. They cannot validate the current model simply by overlaying curves.
- The DEM research skill's distinction between numerical verification and experimental validation governs this assessment. Stage134 remains short-time numerical screening, not measured population release or experimental validation.

## Best candidates

| Source | Data actually accessible | Applicable use | Important mismatch / decision |
|---|---|---|---|
| [Cohen, Edery & Radian (2025), pore-scale fibre transport](https://doi.org/10.1021/acs.est.5c12359) | Downloaded SI. Table S2 gives trapped/not-trapped counts for 120 tracked PP fibres. Published speed/trajectory plots, two supplementary videos and tracking code are available. The inspected code repository does not contain the full trajectory dataset. | Strongest new candidate for fibre length, pore obstruction and passage mechanisms. Table S2 needs no plot digitisation. | Flexible/curved PP, 2D PDMS pores, injection, and an ethanol/Tween mixture. Trapped fibres alter flow and interact. Not an equal-volume sphere–fibre experiment or resident-inventory release test. Aggregate trapping is not an admissible calibration target for our rigid, nonadhesive, one-way model without further matching. |
| [Cohen & Radian (2022), textile fibres in sand](https://doi.org/10.1021/acs.est.2c05026) | Downloaded 20-page SI, including fibre dimensions, sample counts and transport methods. Main-paper retention results can be sought for digitisation; no raw transport file was located in the supplement. | PET-specific length/mobility and morphology evidence for the paper. Quartz sand is closer to our matrix than a microfluidic device. | PET and nylon, humic-acid conditions, injection, and documented peeling/breakage. Shorter fibres are not a unique measure of degradation. Fragment production prevents treating every recovered item as an intact released parent fibre. |
| [Qiao et al. (2024), different shapes in porous media](https://doi.org/10.1021/acs.est.4c07741) | Downloaded SI: 40 particle/material conditions in Table S1; infiltration distributions and velocity-time plots in S1–S5. | Direct experimental sphere/cylinder/flake comparison; useful contact, rotation and geometric-straining evidence. | Millimetre particles and 7/14.5-mm grains. S4 shows particle speeds of tens of mm/s despite imposed flow of 0.2 mm/s. Low imposed flow does not establish low particle Reynolds number. Do not adopt quantitatively without fluid-property, settling, shape and Reynolds checks. No raw trajectory file located. |
| [Ameen et al. (2024), spheres/fragments in saturated quartz sand and gravel](https://doi.org/10.1002/jeq2.20618) | Downloaded open article: experimental breakthrough plots and reported transport/recovery results. | Candidate sphere-only column benchmark with a separately matched injection protocol. | PS particles around 1, 10 and 20 micrometres; upward injection of 2 pore volumes followed by 5 pore volumes flushing. Attachment/detachment and water chemistry matter. Their fitted continuum attachment rates are not DEM friction parameters. Not initially resident release. |
| [Aminzadeh et al. (2025), microplastic effects on sand hydraulics](https://doi.org/10.1038/s41598-025-30476-6) | Downloaded open article. Table 1 provides porosity/density; Figure 3a gives hydraulic conductivity for three sand gradings at 0/2/5% PE or PVC by mass. Authors place supporting data within the article; a replicate-level file was not located. | Best newly checked sand-based conductivity comparator; Figure 3a is a defined digitisation target. | Different polymers, concentrations, sizes and mixed-specimen preparation. Particle shape is not established as ideal spheres by the methods inspected. Not a matched sphere–fibre comparison. Packing changes differ from adding obstructions to frozen sand. |
| [Yu et al. (2023), soil physical properties](https://doi.org/10.1021/acs.est.2c09822) | Downloaded SI: Figure S6C shows conductivity with mean/SD (n=3) for polyester fibres and PP granules. | Fibre-versus-granule hydraulic context, including effects that need not decrease conductivity. | Silt loam, different polymers/sizes and specimen preparation. Not a shape-only causal comparison or clean-LBS validation. The [2026 reanalysis repository](https://doi.org/10.6084/m9.figshare.30246412) links to code, but the inspected GitHub listing lacks the input data table and its script expects an existing object `d`. Do not describe this as recovered raw data. |
| [Maqbool et al. (2024), macropore leaching dataset](https://zenodo.org/records/14415011) | Downloaded CSV plus metadata PDFs. Includes leachate MP mass/recovery, soil transport and some conductivity fields, with reported means/SD. | A genuinely machine-readable recovery dataset; useful for defining recovery bookkeeping and a future macropore benchmark. | Artificial millimetre macropores, MPs placed into top gravel, rainfall after presaturation, and soil detachment. Not uniform resident contamination or fixed-sand pore flow. Metadata uses -9999 for missing values; CSV has duplicate soil-transport headers and a mass-unit typo in the PDF. Do not ingest blindly. |

## A useful fibre result already verified

The downloaded 2025 Cohen SI, page 4, Table S2, gives:

| Fibre length class (source labels) | Trapped | Not trapped | Trapped / analysed |
|---|---:|---:|---:|
| 20–50 micrometres | 10 | 30 | 25% |
| 50–80 micrometres | 30 | 10 | 75% |
| >80 micrometres | 39 | 1 | 97.5% |

These percentages are calculated from the published counts, visually checked against the source page. They are **conditional on analysed fibres**, not a whole-matrix release fraction. Preserve the source's bin labels; its endpoint convention is not explicit. Flexibility, accumulation and chemistry are confounders, not parameters we may silently fit away.

## Other evidence and exclusions

- [Rullander et al. (2023)](https://doi.org/10.1016/j.jenvman.2023.118690): downloaded open sand-filter article. A localized initial MP-mixing zone makes it relevant to release, but high loading/agglomeration and recovery accounting differ from our dilute dispersed inventory. The article says underlying data are available on request. No author contact was made.
- Fouty & Engdahl's public experimental passage arrays were already recovered in Stage123. Retain that evidence, but the high-flow pseudo-2D experiment remains outside the present hydrodynamic domain. A normalized passage CDF is not a release fraction.
- La Capra's flume passage data remain open-channel/injected-particle evidence, not saturated-matrix release validation.

## Recommended next work, before publication claims

- Use the new fibre papers to strengthen the morphology rationale. Avoid claiming that all previous studies use spheres or that fibre transport has not been studied.
- Prioritise extracting Aminzadeh Figure 3a and Yu SI Figure S6C for a clearly labelled hydraulic literature comparison. Keep the measured conductivity K separate from intrinsic permeability k; conversion requires fluid density and viscosity. Do not force a monotonic concentration trend.
- Screen one isolated, near-rigid low-Re fibre observation from Cohen before designing any inexpensive component benchmark. If it cannot be reconstructed with adequate geometry, forcing and uncertainty, use it only as qualitative evidence.
- Keep Ameen as the sphere-injection benchmark option, conditional on matching particle scale, chemistry, boundaries and observable. Reserve independent conditions before any calibration.
- For our own release outcome, report exported count or mass divided by the **initial resident** count or mass, at a stated horizon/pore volume. Account separately for particles still present, upstream exits, numerical failures and any fragments. Unfinished or present-at-horizon trajectories are not permanent retention.
- The user’s “no applicable data” fallback is not triggered: useful evidence has been found. Publication contents/captions can be planned later, but the paper must not describe the current release model as experimentally validated. No manuscript text or new publication figure was prepared here.

## Source handling

Downloaded originals are in `sources/`. Source-page previews are reading/QA aids, not new research figures. ACS supplement metadata identifies CC BY-NC 4.0; confirm the intended journal/reuse licence before reproducing published images. Prefer newly analysed data with citations over copying artwork. The audit records hashes and verifies supplied repository checksums. Downloaded third-party analysis scripts were inspected as text, never executed. The master plan and immutable simulation evidence were left unchanged.
