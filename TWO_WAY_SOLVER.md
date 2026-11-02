# Two-way microplastic solver: code, literature and project record

This is a **separate C++ research line** from the one-way Paper 1 transport model in the root README. The historical source snapshot and its hash inventory have not been edited.

- [Two-way solver overview and reproduction commands](research/lbm-ibm-dem/README.md)
- [Development decisions and benchmark corrections, v0.1–v0.3](research/lbm-ibm-dem/DECISIONS.md)
- [Annotated research and code guide](research/lbm-ibm-dem/LITERATURE.md) and [all 87 numbered source links](research/lbm-ibm-dem/reference-map.tsv) from the review, strategy and IBM prior-art note. Counts include repeat citations and software/institutional sources.
- [Local rebuild and source verification](research/lbm-ibm-dem/VERIFICATION.md)
- Exact original source files: [iterated IBM–contact exchange](solvers/lbm_ibm_dem_v03/include/hydro_contact_step.hpp), [film port](solvers/lbm_ibm_dem_v03/include/film_port.hpp), [standalone conductance example](solvers/lbm_ibm_dem_v03/examples/film_conductance.cpp).
- [Original release and report checksums](research/lbm-ibm-dem/IMPORT.md).

## Full source and evidence import

The initial GitHub update above publishes the technical record and selected native source. The complete 240-file Git payload is distributed separately as `LBM_IBM_DEM_GitHub_update.zip`. It contains all 231 original solver archive members, both DOCX reports and searchable copies, the full citations, test log and a file-integrity manifest. Its `solver-import` branch commit is `456ee7173e0ed9f38d7c305aab460594fdfd67f1`; the SHA-256 of the enclosed `LBM_IBM_DEM_v03.bundle` is `d22203c347a855d0d1b1b16f2052a9dce914e74c1a45216592ba19012c1dcc1f`.

The repository owner can extract the update ZIP and run `python3 publish.py --push` to add the rest of the evidence to this same repository. Omit `--push` for a dry run. The helper checks hashes and refuses to overwrite changed paths; it never force-pushes. To inspect the snapshot offline, run `git clone -b solver-import LBM_IBM_DEM_v03.bundle lbm-v03` instead.

Completion check: the full import is present on a branch when `solvers/lbm_ibm_dem_v03/src/ibm.cpp` and `research/lbm-ibm-dem/ARCHIVE_MEMBERS.sha256` are tracked and all 233 entries verify. No production 3D solver, GPU performance record, or new physical validation is asserted by the import.
