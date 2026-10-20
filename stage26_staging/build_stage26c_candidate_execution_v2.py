"""Build the exact one-candidate Stage26c execution config from frozen controls."""

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "stage26_staging/stage26c_fixed_prefilter_controls_execution_v2.json"
CONTROL = ROOT / "stage26_checkpoints/stage26c_revision3_fixed_prefilter_20260816/control_requalification_checkpoint_02/checkpoint_manifest.json"
PLACEMENT = ROOT / "stage26_placements/stage26c_revision3_fixed_prefilter_20260816/normalized_01/revision3_candidate01.json"
OUTPUT = ROOT / "stage26_staging/stage26c_fixed_prefilter_candidate01_execution_v2.json"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    cfg = json.loads(BASE.read_text())
    control = json.loads(CONTROL.read_text())
    assert control["passed"] is True and control["both_controls_reproduced"] is True
    cfg["schema"] = "lbs.stage26c-fixed-prefilter-candidate-execution.v2"
    cfg["claim_boundary"] = (
        "One bounded fixed-fibre YADE prefilter of selected Revision-3 candidate01 in the exact Stage25 "
        "216-grain packing. No fibre release, promoted DEM state, polymer calibration, permeability, "
        "flow, deformation, migration, or coupled-physics result."
    )
    cfg["sources"]["control_checkpoint"] = CONTROL.as_posix()
    cfg["sources"]["control_checkpoint_sha256"] = digest(CONTROL)
    placement = json.loads(PLACEMENT.read_text())
    assert placement["passed"] is True and placement["fibre_count"] == 2
    cfg["trials"] = [{
        "trial_id": "revision3_candidate01",
        "record_type": "candidate",
        "candidate_index": 1,
        "fibre_count": 2,
        "minimum_anchor_degree": min(
            min(fibre["anchor_network_degrees"]) for fibre in placement["fibres"]
        ),
        "placement": PLACEMENT.as_posix(),
        "placement_sha256": digest(PLACEMENT),
    }]
    cfg["authority"]["candidate01_fixed_prefilter_execution_authorized"] = True
    with OUTPUT.open("x") as stream:
        json.dump(cfg, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
    print(OUTPUT)
    print(digest(OUTPUT))


if __name__ == "__main__":
    main()
