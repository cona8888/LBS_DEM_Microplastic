# Import verification (2 November 2026)

The ZIP member CRCs passed before building. The v0.3 source was rebuilt in a clean directory with GNU g++ 14.2.0, `-std=c++17 -O2 -fopenmp -Wall -Wextra -Wpedantic`. GNU Make ran the complete `test` target with `OMP_NUM_THREADS=1`. Exit status **0**. The target runs `bin/tests`, `bin/test_compact_commit`, `bin/test_hydro_contact` and `bin/test_film_port`. This was a fresh local check, not GitHub Actions or a new timing campaign.

- The compact commit test reported zero maximum absolute difference on the repeated moving-disk case.
- The iterated single-disk recoil oracle reported endpoint velocity error 1.58189433774e-14. The oblique history/budget test and the rejected-step rollback/retry test also passed.
- All five standalone film-port test groups passed. On the manufactured example the energy residual printed as zero. This does not validate an outer IBM-to-film connection.

The following GitHub source objects match the archived bytes (`git hash-object`):

| File within `solvers/lbm_ibm_dem_v03/` | Git blob |
|---|---|
| `include/film_port.hpp` | `2c08b58c2cd35c55d6090fe753864de1c84e8054` |
| `include/hydro_contact_step.hpp` | `ef31ae2e28fa77279f8c80d1404cd38251472d18` |
| `examples/film_conductance.cpp` | `f053902f0cb13723cd8c7b4f823b574a6a7b0cca` |

This small example can be compiled directly from those published sources, even without the full data import:

```sh
cd solvers/lbm_ibm_dem_v03
c++ -std=c++17 -O2 -Iinclude examples/film_conductance.cpp -o /tmp/lbm-film-check
/tmp/lbm-film-check 0.04 0.01 0.0025 0.000625
```

For a full build, use the complete source supplement. The input hashes are in [IMPORT.md](IMPORT.md). The full test log is included in the supplement. Source integrity and regression tests do not certify a physically validated microplastic transport prediction.
