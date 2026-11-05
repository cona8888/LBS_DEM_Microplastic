# RhizoField growing-root contact: verified dry integration repair

Read [HANDOVER.md](HANDOVER.md) for the A-I development review, actual capability
matrix, defects, corrections, numerical gates and experimental limitations.
The historical contact-search description is in [LEGACY_README.md](LEGACY_README.md).

This update fixes a reproduced root-force timing defect. Native `DEM::advance`
accepts constant external forces, but the former driver held state-dependent
root loads constant through a step. A new `DryRootStepper` refreshes root loads
in symmetric stages and updates slip history once per accepted increment.
Physical state rolls back on iteration failure. The native DEM files and all
material/calibration values are unchanged.

```sh
make test
make integration-test
make bin/growth_cell bin/native_probe
./bin/native_probe tip cached 6000
./bin/native_probe radial cached 6000
python3 run_review.py --output review_run
```

C++17, make and NumPy are required. The Makefile uses the full local solver when
available, otherwise the unchanged minimal dependency in `native/`. The Python
harness creates the raw histories, source hashes, numerical checks and timing
records. `--resume` only reuses checksum-matching completed case outputs.

Key verification: the 20-cycle normal oscillator's maximum relative energy error
at 800 steps/period falls from 0.638000 to 1.54226e-5. Dry growth direct/cached
histories match; force/envelope difference between the two finest steps is
1.37589%, and actual per-step peak difference is 0.24692%. The 56-grain fixture
has a 2.213216 N/m peak and 67.7342 micrometre final maximum grain displacement.
Compact numerical evidence is in `review/`.

The root is a prescribed tapered surface, not a flexible beam or biological
growth law. Force dynamics are 2D per unit depth; detection also supports 3D
sphere/span queries. LBM/IBM and equilibrium suction are separate project paths,
not exercised in this dry driver. This milestone is verified within scope and
experimentally unvalidated. No universal speed or whole-tree claim is made.
