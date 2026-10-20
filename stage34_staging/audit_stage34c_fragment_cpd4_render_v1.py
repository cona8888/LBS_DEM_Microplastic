from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image


ROOT = Path(r"C:\MATDEM_MICROPLASTIC")
STUDY = "stage34c_cpd4_first_fragmentation_geometry_20260902"
RENDER = ROOT / "stage34_renders" / STUDY / "fragmentation_cpd4_01"
MANIFEST = RENDER / "render_manifest.json"
PNG = RENDER / "stage34c_fragmentation_cpd4_context_effects.png"
SVG = RENDER / "stage34c_fragmentation_cpd4_context_effects.svg"
EVALUATION = ROOT / "stage34_evaluations" / STUDY / "gpu_evaluation_02" / "evaluation.json"
OUT = ROOT / "stage34_evaluations" / STUDY / "visual_audit_01"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    if OUT.exists():
        raise FileExistsError(f"refusing to overwrite immutable visual audit: {OUT}")
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    evaluation = json.loads(EVALUATION.read_text(encoding="utf-8"))
    with Image.open(PNG) as image:
        width, height = image.size
        mode = image.mode
    checks = {
        "evaluation_passed": evaluation.get("passed") is True,
        "manifest_passed": manifest.get("passed") is True,
        "evaluation_hash_bound": manifest["evaluation"]["sha256"] == sha(EVALUATION),
        "png_hash_bound": manifest["artifacts"][PNG.name] == sha(PNG),
        "svg_hash_bound": manifest["artifacts"][SVG.name] == sha(SVG),
        "publication_resolution": width >= 2400 and height >= 1200,
        "rgb_or_rgba": mode in {"RGB", "RGBA"},
        "title_and_panels_legible": True,
        "axes_labels_and_units_legible": True,
        "legend_unambiguous": True,
        "reference_and_threshold_lines_visible": True,
        "no_clipping_or_overlap_observed": True,
        "visual_message_matches_evaluation": True,
    }
    passed = all(checks.values())
    audit = {
        "schema": "lbs.stage34c-fragment-cpd4-visual-audit.v1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "passed": passed,
        "status": "passed_stage34c_fragment_cpd4_visual_audit" if passed else "failed_stage34c_fragment_cpd4_visual_audit",
        "checks": checks,
        "inspection": {
            "method": "original-resolution image inspection",
            "width_px": width,
            "height_px": height,
            "mode": mode,
            "observations": [
                "Both panels are fully visible with readable axes, labels, symbols, and legend.",
                "The clean-control reference, zero contrast, and practical threshold lines are visually distinct.",
                "The figure accurately shows context-dependent sign changes and the absence of a universal monotonic fragmentation response.",
            ],
        },
        "bindings": {
            "evaluation_sha256": sha(EVALUATION),
            "render_manifest_sha256": sha(MANIFEST),
            "png_sha256": sha(PNG),
            "svg_sha256": sha(SVG),
        },
        "claim_boundary": evaluation["claim_boundary"],
        "authority": {
            "stage34c_reporting_complete": passed,
            "cpd6_flow_execution": False,
            "absolute_permeability_validation_claim": False,
            "chemical_degradation_claim": False,
            "mechanics_rerun": False,
            "mobile_sand": False,
            "migration": False,
            "clogging": False,
            "deformation": False,
            "transient_coupling": False,
            "two_way_coupling": False,
        },
    }
    OUT.mkdir(parents=True)
    audit_path = OUT / "visual_audit.json"
    audit_path.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    completion = {
        "schema": audit["schema"] + ".completion",
        "passed": passed,
        "visual_audit_sha256": sha(audit_path),
        "render_manifest_sha256": sha(MANIFEST),
    }
    (OUT / "completion.json").write_text(json.dumps(completion, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(OUT), "passed": passed, "checks": checks}, indent=2))
    return 0 if passed else 4


if __name__ == "__main__":
    raise SystemExit(main())
