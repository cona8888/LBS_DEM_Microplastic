# Runnable RhizoField water validation

This directory supplies the water application, native and contact tests, frozen calibration, seed, validation drivers and archived endpoint fields. The source baseline is RhizoField revision `44301ea0df7fc7498f610757d56cc94b82ef0401`. It includes a new analysis of geometric liquid area under `validation_water/volume_mapping/`. The tests compare 2D line forces. The hydraulic comparison uses a saturated ceramic root analogue.

Run the following from this directory with Python 3, a C++17 compiler, GNU Make and the packages in requirements.txt.

```sh
python3 -m pip install -r requirements.txt
make test core-test
python3 -m validation_water.validate holdouts
make audit-areas
```

`make audit-areas` verifies three analytic geometry checks and recomputes the 12 reported endpoint conditions on two grids. It verifies the archived input hashes before using them. See the [endpoint results and definitions](validation_water/volume_mapping/README.md).

To rerun the earlier campaign from its inputs, including complete coupled extraction histories, run `python3 -m validation_water.reproduce`. This longer command writes outputs to `validation_water/results/`. The new area analysis uses its own frozen endpoint copies so you can run either command first.

The [frozen manifest](validation_water/FROZEN_INPUTS.json) identifies calibration, probe and reference data. The validation commands read these inputs. The separate calibration targets fit parameters and belong in a separate working copy. The [evidence register](../evidence-register/README.md) separates previously fitted observations, holdouts, and candidates with different geometry.
