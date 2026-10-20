"""Fail-closed source audit for the selected-geometry renderer."""

import ast
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path("C:/MATDEM_MICROPLASTIC")
SOURCE = ROOT / "stage26_staging/render_stage26b_revision3_selected_geometry_v1.py"
CHECKPOINT = ROOT / "stage26_checkpoints/stage26b_revision3_joint_placement_20260816/campaign_checkpoint_01/checkpoint_manifest.json"
OUTPUT_DIR = ROOT / "stage26_renders/stage26b_revision3_joint_placement_20260816/selected_candidate_render_01"
EVALUATION = ROOT / "stage26_evaluations/stage26b_revision3_joint_placement_20260816/renderer_source_evaluation_01/evaluation.json"


def digest(path):
    value = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


source = SOURCE.read_text(encoding="utf-8")
tree = ast.parse(source)
imports = set()
for node in ast.walk(tree):
    if isinstance(node, ast.Import):
        imports.update(alias.name.split(".")[0] for alias in node.names)
    elif isinstance(node, ast.ImportFrom) and node.module:
        imports.add(node.module.split(".")[0])
checkpoint = json.loads(CHECKPOINT.read_text(encoding="utf-8"))
checks = {
    "campaign_checkpoint_passed": checkpoint.get("passed") is True,
    "render_authorized": checkpoint["authority"].get("selection_and_render_authorized") is True,
    "yade_not_authorized": checkpoint["authority"].get("prefilter_yade_execution_authorized") is False,
    "checkpoint_hash_literal_bound": digest(CHECKPOINT) in source,
    "selected_placement_hash_verified": "selected_placement_sha256" in source and "digest(PLACEMENT)" in source,
    "immutable_output_guard_present": "if OUTPUT.exists()" in source,
    "equal_physical_scaling_present": "set_box_aspect(span)" in source and "set_proj_type(\"ortho\")" in source,
    "no_coordinate_magnification_claim_is_explicit": "not magnified" in source,
    "full_claim_boundary_is_on_image": all(term in source for term in ("YADE relaxation", "mechanical stability", "polymer calibration", "permeability", "coupled-flow")),
    "no_process_launcher_import": "subprocess" not in imports,
    "output_absent_before_render": not OUTPUT_DIR.exists()
}
passed = all(checks.values())
evaluation = {
    "schema": "lbs.stage26b-revision3-selected-geometry-renderer-source-evaluation.v1",
    "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    "passed": passed,
    "status": "passed_renderer_source_audit" if passed else "failed_renderer_source_audit",
    "checks": checks,
    "failures": [name for name, value in checks.items() if not value],
    "evidence": {"source_path": str(SOURCE), "source_sha256": digest(SOURCE), "campaign_checkpoint_path": str(CHECKPOINT), "campaign_checkpoint_sha256": digest(CHECKPOINT)},
    "authority": {"render_execution_authorized": passed, "prefilter_yade_execution_authorized": False},
    "claim_boundary": checkpoint["claim_boundary"]
}
EVALUATION.parent.mkdir(parents=True, exist_ok=False)
EVALUATION.write_text(json.dumps(evaluation, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(json.dumps({"passed": passed, "evaluation_sha256": digest(EVALUATION)}, sort_keys=True))
if not passed:
    raise SystemExit(1)
