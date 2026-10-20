"""Audit the unambiguous two-fibre renderer before execution."""

import ast
import hashlib
import json
from pathlib import Path


ROOT = Path("C:/MATDEM_MICROPLASTIC")
SOURCE = ROOT / "stage26_staging/render_stage26b_revision3_selected_geometry_v2.py"
BASE = ROOT / "stage26_staging/render_stage26b_revision3_selected_geometry_v1.py"
CHECKPOINT = ROOT / "stage26_checkpoints/stage26b_revision3_joint_placement_20260816/campaign_checkpoint_01/checkpoint_manifest.json"
OUTPUT_DIR = ROOT / "stage26_renders/stage26b_revision3_joint_placement_20260816/selected_candidate_render_02"
EVALUATION = ROOT / "stage26_evaluations/stage26b_revision3_joint_placement_20260816/renderer_source_evaluation_02/evaluation.json"


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


source = SOURCE.read_text(encoding="utf-8")
tree = ast.parse(source)
imports = {node.module.split(".")[0] for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module}
checkpoint = json.loads(CHECKPOINT.read_text(encoding="utf-8"))
checks = {
    "campaign_checkpoint_passed": checkpoint.get("passed") is True,
    "render_authorized_only": checkpoint["authority"].get("selection_and_render_authorized") is True and checkpoint["authority"].get("prefilter_yade_execution_authorized") is False,
    "campaign_checkpoint_hash_bound": digest(CHECKPOINT) in source,
    "base_renderer_hash_bound": digest(BASE) in source,
    "selected_placement_hash_verified": "selected_placement_sha256" in source,
    "immutable_render02_output_guard": "if OUTPUT.exists()" in source and not OUTPUT_DIR.exists(),
    "equal_physical_scaling_reused": "set_equal_physical_scale" in source,
    "two_fibres_have_separate_labels": "Fibre {fibre_index + 1}" in source and "red Fibre 1 and blue Fibre 2" in source,
    "anchor_transparency_disclosed": "Anchor transparency" in source,
    "full_claim_boundary_present": all(term in source for term in ("YADE relaxation", "mechanical stability", "polymer calibration", "permeability", "coupled-flow")),
    "no_process_launcher": "subprocess" not in imports
}
passed = all(checks.values())
evaluation = {"schema": "lbs.stage26b-revision3-selected-geometry-renderer-source-evaluation.v2", "passed": passed, "status": "passed_unambiguous_renderer_source_audit" if passed else "failed_unambiguous_renderer_source_audit", "checks": checks, "failures": [k for k, v in checks.items() if not v], "evidence": {"source_path": str(SOURCE), "source_sha256": digest(SOURCE), "base_renderer_path": str(BASE), "base_renderer_sha256": digest(BASE), "campaign_checkpoint_path": str(CHECKPOINT), "campaign_checkpoint_sha256": digest(CHECKPOINT)}, "authority": {"render_execution_authorized": passed, "prefilter_yade_execution_authorized": False}, "claim_boundary": checkpoint["claim_boundary"]}
EVALUATION.parent.mkdir(parents=True, exist_ok=False)
EVALUATION.write_text(json.dumps(evaluation, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(json.dumps({"passed": passed, "evaluation_sha256": digest(EVALUATION)}, sort_keys=True))
if not passed:
    raise SystemExit(1)
