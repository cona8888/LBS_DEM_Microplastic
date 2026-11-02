# Two-way LBM–IBM–DEM for microplastic transport

Project record, 2 November 2026. This is the C++17 research prototype discussed in the microplastics solver development thread. It is separate from the earlier Python transport, MATLAB/MatDEM and Paper 1 verification work in this repository. No existing implementation is superseded. See [literature and software](LITERATURE.md), [development decisions](DECISIONS.md) and the [release inventory and import procedure](IMPORT.md).

**Use case:** determine when a plastic particle passes a throat, attaches, bridges or remobilises, and measure the resulting hydraulic resistance. The numerical objective is **lower whole-simulation time at matched mechanical and hydraulic accuracy**, not maximum lattice updates per second. An external speed record, laboratory-validated microplastic retention and a production 3D solver have not been demonstrated.

## Model actually tested

D2Q9 TRT fluid; periodic 2D domain; translating/rotating disks representing parallel cylinders per unit axial length. A matched four-point immersed-boundary interpolation/spreading pair transfers impulse in both directions. The body update uses physical mass and inertia and the change in the fictitious interior fluid's momentum, including first moments. The current global interface equation is solved by matrix-free GMRES. Cached particle blocks accelerate that solve, not replace the current interaction operator. DEM uses compliant, subcycled normal/tangential contact, damping, Coulomb sliding, rotation and retained tangential history. Wet encounters use a distinct mechanical contact envelope: the illustrative offset of 0.125 radii is not measured polymer roughness. Smooth hydrodynamic cores may not overlap.

## Run the full source tree

From `solvers/lbm_ibm_dem_v03/` after the full source import, on Linux/WSL with GNU Make, C++17 and OpenMP:

```sh
make -j4
make test
OMP_NUM_THREADS=1 ./bin/wet_impact --case oblique --resolution 16 --dt-factor 0.125 --mode fast --exchange split --commit active --warmup 2 --time 1 --substeps 8 --retraction 0.3 --lubrication off --csv results/my_oblique.csv
```

Split exchange is the recommended tested setting; `--commit active` must be specified because the archived executable defaults to dense commit. Active commit restricts the impulse update to its exact support; it does **not** skip fluid collision or streaming. The finite two-port film element is standalone. Do not add its predicted flux to the live coarse grid without replacing the already-resolved gap response.

## Where the evidence is in the source archive

| Question | Relative path inside the solver |
|---|---|
| What equations and limits apply? | `docs/IBM_PRIOR_ART.md`, `docs/WET_CONTACT_MODEL.md`, `docs/ITERATED_EXCHANGE.md` |
| What is the independent film comparison? | `include/film_port.hpp`, `docs/FILM_PORT.md`, `docs/STOKES_FILM_CHECK.md`, `stokes_film_reference.py` |
| Which v0.1/v0.2 tests and timings were recorded? | `results/VERIFICATION_SUMMARY.md`, `results/BENCHMARK_SUMMARY.md`, `results/v02/` |
| Why is split exchange recommended for the tested impacts? | `results/v03/BENCHMARK.md`, **then** `results/v03/threshold_check/THRESHOLD_CHECK.md` |
| Where are the original curves and raw results? | `results/v03/`, `figures/` (CSV, plotting scripts, editable SVG, PDF, PNG) |

**Next experiment, not a release:** connect a single fixed pressure-driven pore throat to the outer IBM fluid. Measure through-flow, pressure difference, particle load, entrance volume/power balance and the error in each, against a fine independent reference. Only then test moving contacts, deposits and a network. GPU/AMR, flexible fibres, biofilm, adhesion, unsaturated transport and external-code speed comparisons remain separate work.
