# Literature comparison outputs

- Current result: [comparison_02/TREND_COMPARISON.md](comparison_02/TREND_COMPARISON.md).
- Data: `comparison_02/measurements.json`; model evidence/status: `comparison_02/simulation_comparison.json`.
- 77 plotted values extracted, plus three exact count groups. These are not 77 independent experiments: some controls repeat, and some points belong to the same curve.
- `comparison_02` supersedes `comparison_01`: bar-reading sensitivity was widened from two to four native pixels after checking outline/error-cap overlap, and dimensionless quantities from the current frozen designs were added. Point estimates did not change. Earlier outputs remain preserved.
- Independent affine-coordinate recalculation and source/output hash checks passed after creation. Current record hashes were checked against the existing numerical evaluation. This is not a new full physical or solver validation audit.
- No parameter fitting, simulation dispatch, manuscript or publication figure. Source-image previews are reading/digitisation QA only.
- DEM research guidance kept numerical verification, trend comparison and empirical validation distinct; PDF guidance provided source-coordinate and visual extraction checks.

Reproduce into a **new** output directory using `digitise_and_compare.py --out <new direct child of this directory>`. Existing output directories are never overwritten. The script reads local archived inputs only.
