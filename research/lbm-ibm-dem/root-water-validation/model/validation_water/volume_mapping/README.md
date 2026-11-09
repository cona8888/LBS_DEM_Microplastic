# Geometric liquid area at fixed root–grain gap

At a 677.5 µm gap, the predicted root-versus-outer drying force contrast changes sign under plausible numerical choices for representing liquid amount. The following comparisons use the same 0.072 N/m water surface tension, nominal root wall angle of 50°, grain wall coefficient angle of 51.249016°, disk geometry and endpoint histories. They use the RhizoField equilibrium solver from commit `44301ea0df7fc7498f610757d56cc94b82ef0401`. No parameter was fitted.

| Mesh spacing | W | What is held fixed on reducing W | Contrast in attraction |
|---:|---:|---|---:|
| 25 µm | 125 µm | Original phase inventory | −1.03069% |
| 25 µm | 62.5 µm | Original phase inventory | −0.67698% |
| 25 µm | 62.5 µm | Each protocol’s original geometric liquid area | −0.35084% |
| 12.5 µm | 125 µm | Original phase inventory | −0.89046% |
| 12.5 µm | 62.5 µm | Original phase inventory | −0.23705% |
| 12.5 µm | 62.5 µm | Each protocol’s original geometric liquid area | +0.17073% |

The contrast is 100 (|Froot| / |Fouter| − 1). W sets the width in the equilibrium tanh profile. The 10–90% transition width is approximately 2.20 W. Each root or outer endpoint retains **its own** W = 125 µm reference area on its own mesh. The two drying protocols do not have equal local bridge areas. The outer reservoir is outside this static patch experiment. Adjusting the near-pore phase inventory here creates a separate measurement-matched equilibrium; it does not reproduce the full hydraulic drying history.

## Area measurement

Cell-centred gradients use local fluid neighbours in the two coordinate directions, with one-sided differences at raster walls. Within each fluid rectangle, the code analytically integrates the positive fraction of the locally reconstructed linear field. It uses the actual stretched cell widths and excludes the raster solids. This geometric diagnostic is independent of the solver’s force and conserved-area formulas. It does use the computed phase field and the solver’s mesh. It represents the area on the liquid side of the reconstructed φ = 0 interface, in m² per unit out-of-plane depth convention. A three-dimensional liquid volume requires an actual out-of-plane geometry.

On the 12.5 µm grid at W = 125 µm, root/outer conserved inventories are 0.27078/0.32024 mm². Geometric areas are 0.36657/0.40763 mm². The bulk-branch normalisation gives 0.37509/0.41811 mm². With fixed phase inventory, halving W changes the geometric areas to 0.33377/0.37638 mm². Recovering the original geometric areas instead requires phase inventories of 0.30878/0.35666 mm². Each endpoint is matched to within 0.0005% of its reference geometric area.

The CSV also reports the geometric area at the midpoint of the two extrapolated equilibrium bulk branches, and area thresholds of φ = −0.1 and +0.1. For the root endpoint on the 12.5 µm grid at W = 125 µm, the latter thresholds yield 0.38804 and 0.34524 mm² around the nominal 0.36657 mm². This span quantifies readout sensitivity. It has no statistical confidence interpretation. Staircase wetting boundaries, inferred contact-line position, curvature and the finite W all affect transfer to a physical meniscus. The two meshes do not establish a sharp-interface limit. These synthetic endpoint comparisons provide no experimental validation or measured liquid inventory.

## Reproduction

Run these commands from the `model` directory. The archived fields in `volume_mapping/fixtures/` are separate from regenerated simulation outputs. The script verifies both endpoint SHA-256 digests and the original frozen calibration files. It runs only static fixed-gap equilibria. It reads the saved fine-grid endpoints for both protocols and applies the same refinement and initialisation as the baseline width study.

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python validation_water/volume_mapping/volume_mapping.py
python -m unittest discover -s validation_water/volume_mapping -p 'test_volume_mapping.py' -v
```

The tests cover exact planar cuts on stretched rectangles, exclusion of a solid cell, and the area of an off-grid circular interface under mesh refinement. No additional dependencies beyond the recovered solver's declared NumPy and SciPy environment are required.
