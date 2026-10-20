"""Audit the exact Stage26c two-control fixed-prefilter schedule."""

import hashlib
import json
from pathlib import Path


ROOT = Path("C:/MATDEM_MICROPLASTIC")
CONFIG = ROOT / "stage26_staging/stage26c_fixed_prefilter_controls_execution_v1.json"
DESIGN = ROOT / "stage26_staging/stage26b_tier1_placement_stability_revision2_design_v1.json"
OUTPUT_ROOT = ROOT / "stage26_runs/stage26c_revision3_fixed_prefilter_20260816/controls_01"
EVALUATION = ROOT / "stage26_evaluations/stage26c_revision3_fixed_prefilter_20260816/controls_execution_evaluation_01/evaluation.json"


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
design = json.loads(DESIGN.read_text(encoding="utf-8"))
checks = {}
checks["status_exact"] = cfg["status"] == "authorized_stage26b_revision2_fixed_prefilter"
checks["all_source_hashes"] = all(digest(value) == cfg["sources"][name + "_sha256"] for name, value in cfg["sources"].items() if not name.endswith("_sha256") and name != "expected_yade_version")
checks["expected_yade_exact"] = cfg["sources"]["expected_yade_version"] == "2022.01a"
checks["protocol_exact"] = cfg["prefilter"] == {"all_fibres_fixed": True, "free_release": False, "steps_per_block": 500, "blocks": 10, "maximum_strain_rate_s_inv": 0.02}
checks["frozen_physics_match_design"] = all(cfg["frozen_physics"][name] == design["frozen_physics"][name] for name in cfg["frozen_physics"])
checks["contact_gates_match_design"] = cfg["candidate_contact_gates"] == design["prefilter"]["candidate_contact_gates"]
checks["sand_gates_match_design"] = cfg["sand_health_gates_at_terminal_block"] == design["prefilter"]["sand_health_gates_at_terminal_block"]
checks["controls_exact_order"] = [row["trial_id"] for row in cfg["trials"]] == ["positive_stage26a", "negative_stage26b_failure"]
checks["placements_hash_bound"] = all(digest(row["placement"]) == row["placement_sha256"] for row in cfg["trials"])
checks["outputs_absent"] = not OUTPUT_ROOT.exists()
checks["authority_narrow"] = cfg["authority"]["prefilter_yade_execution_authorized"] is True and not any(value for name, value in cfg["authority"].items() if name != "prefilter_yade_execution_authorized")
passed = all(checks.values())
evaluation = {"schema": "lbs.stage26c-controls-execution-evaluation.v1", "passed": passed, "checks": checks, "failures": [k for k, v in checks.items() if not v], "config_sha256": digest(CONFIG), "authority": {"controls_yade_execution_authorized": passed, "candidate_yade_execution_authorized": False}}
EVALUATION.parent.mkdir(parents=True, exist_ok=False)
EVALUATION.write_text(json.dumps(evaluation, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(json.dumps({"passed": passed, "evaluation_sha256": digest(EVALUATION), "config_sha256": digest(CONFIG)}, sort_keys=True))
if not passed:
    raise SystemExit(1)
