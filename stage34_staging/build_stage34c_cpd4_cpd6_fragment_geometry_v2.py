#!/usr/bin/env python3
"""Run raster builder v1 against the audited superseding Stage34C placement."""

from pathlib import Path
import sys


ROOT = Path(r"C:\MATDEM_MICROPLASTIC")
sys.path.insert(0, str(ROOT / "stage34_staging"))
import build_stage34c_cpd4_cpd6_fragment_geometry_v1 as builder  # noqa: E402


builder.PLACEMENT = ROOT / "stage34_designs/stage34c_cpd4_first_fragmentation_geometry_20260902/placement_search_02/placement_manifest.json"
builder.PLACEMENT_COMPLETION = builder.PLACEMENT.parent / "completion.json"
builder.PLACEMENT_AUDIT = ROOT / "stage34_evaluations/stage34c_cpd4_first_fragmentation_geometry_20260902/placement_audit_04/placement_audit.json"
# Make the resolved manifest bind this entry point.  Core builder v1 remains
# independently hash-bound through placement_search_02.raster_builder_api.
builder.__file__ = __file__


if __name__ == "__main__":
    raise SystemExit(builder.main())
