# LBS DEM Microplastic

Research source for shape-aware microplastic transport through Leighton Buzzard sand, with numerical verification tools and earlier MATLAB/MatDEM permeability prototypes.

## Current research scope

Paper 1 studies dilute, independent equal-volume spheres and rigid aspect-ratio-4 prolates in a fixed sand packing under prescribed one-way water flow. The agreed small mechanism/feasibility set contains 12 core trajectories: two shapes, three flow levels and two paired placements in one packing. Claims are conditional on those placements and that packing.

This is an in-progress research codebase. At the 20 October 2026 source snapshot, the project plan reports **1 of 12 core cases qualified**. Full-horizon fibre accuracy and the remaining case admissions are unresolved. Source/mock checks, saved-input diagnostics and successfully closed processes are not substitutes for native accuracy, complete-path verification or experimental validation. No completed shape/flow campaign is claimed by this repository.

The present transport model does not include flexible-fibre bending, mobile sand, adhesion, chemical ageing or particle-induced flow feedback. Earlier reduced permeability studies are a separate model family; they should not be interpreted as a demonstrated evolving conductivity law for the current fixed-flow transport model.

## Repository layout

| Path | Contents |
| --- | --- |
| `paper1_staging/` | Current Paper 1 designs, numerical adapters, independent auditors, source controls and bounded-run tooling |
| `stage*_staging/` | Historical numerical implementations, verification code and their dependency chain |
| `bottleneck_resolution_20260912/` | Contact-loop development source and compiler dependency notes |
| `algorithm_review_20260912/` | Earlier algorithm review and source |
| `src/`, `config/`, `scripts/`, `tests/`, `native_matdem/` | Earlier MATLAB reduced models and prepared native MatDEM cases |
| `literature_*` | Literature processing and comparison source/notes |
| `docs/` | Model assumptions and earlier implementation documentation |
| `MASTER_PLAN.md`, `CURRENT_PLAN.md` | Historical local research status and claim boundaries at the snapshot |
| `PUBLICATION_PLAN.md` | Proposed paper framing; older entries do not supersede the current plan |
| `SOURCE_SNAPSHOT.json` | Exact source-file inventory and hashes for this export |

Dated source and plan entries retain their original status and paths. Later controls and negative results do not retroactively qualify earlier attempts.

## Environment and verification

The recorded desktop Python interpreter is Python 3.12. `requirements-core.txt` records the observed NumPy, SciPy and psutil versions; it is not a universal lockfile for every historical stage. Compiled contact backends have additional, stage-specific Numba/LLVM and BLAS requirements. See `bottleneck_resolution_20260912/requirements-compiler.txt` and its README before selecting a backend.

Verify the exported file hashes and parse Python source without importing or running the numerical model:

```shell
python tools/check_snapshot.py
```

A numerical run also requires its original inputs, immutable source/evidence bindings, applicable authorization and a newly qualified runtime. Many historical scripts intentionally retain absolute Windows paths and fail closed when those bindings are absent. Cloning this repository alone does not provide the complete local execution archive or authorize a campaign. Do not bypass a failed prerequisite to make a run start.

For the earlier MATLAB models, see [the original MatDEM README](docs/LEGACY_MATDEM_README.md). Those examples require MATLAB and a separately installed MatDEM distribution. The native pore3d model is prepared code, not a claimed completed validation run.

## Snapshot contents

This repository contains project source, selected source-local configuration and documentation. Generated run/checkpoint/evaluation trees, execution grants, bundled Python runtimes, compiled caches, large input archives, dissertation documents and the MatDEM installation remain outside this source export. Some historical documentation links therefore refer to files in the original local archive.

Active working files and numerical outputs were not modified to prepare this snapshot. No simulation, force solve, accuracy probe or campaign was run as part of the GitHub update.
