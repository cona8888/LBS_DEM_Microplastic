# RhizoField calibration and validation register

Use [observations.csv](data/observations.csv) for the measurements and [sources.csv](data/sources.csv) for provenance. The 10 November 2026 edition contains 110 observation records across a register of 27 publications. Of the 110 records, 109 have numerical values and one records a missing measurement. Eleven measurements belong to the archived calibration and 25 outcomes retain their original reserved status.

[The capillary supplement](supplement/capillary_observations.md) records six approximate total-force readings for two acrylic spheres, one cylinder bridge area at zero voltage and three cylinder bridge areas in electric fields. Each row has its original measurement units, figure or table, material, geometry and intended use. The six forces are reserved for a future 3D test. The zero-voltage area is an input for a future gravity-aware shape comparison. The electric-field observations lie outside the current physics. The supplement does not add a score for living-root force or provide a receding root contact angle.

To rebuild the SQLite database, the CSV views and the integrity checks with the Python standard library, run this from the evidence-register directory.

```sh
python3 scripts/make_database.py
```

The script enforces foreign keys and asserts the calibration split, missing measurements and selected unit conventions. The original transcriptions and their hashes are in `original/` and `provenance/`. Supplemental rows use separate identifiers to avoid changing the original observation IDs. The archived register used Consensus for discovery. The supplement records the additional Consensus searches and primary-source extraction details.
