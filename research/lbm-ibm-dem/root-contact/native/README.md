# Native DEM dependency snapshot

These three files are byte-identical to the full RhizoField bundle at
`03ee352240c6dd582d5d10b50e38ddb9f0d69a77`:
`solver/include/common.hpp`, `solver/include/dem.hpp`, `solver/src/dem.cpp`.
No contact law or integrator in this dependency was edited in the review.
`../review/provenance.json` records SHA-256 values.

This minimal copy makes `make integration-test`, `make native` and `make growth`
reproducible in the standalone GitHub contact module. It does not provide the
full LBM/IBM source or its regression suite; those are in the complete supplied
RhizoField archive. The Makefile uses the complete local solver when present,
otherwise this snapshot. Override `SOLVER=/path/to/solver` explicitly as needed.
