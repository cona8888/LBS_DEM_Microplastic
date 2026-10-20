from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(r"C:\MATDEM_MICROPLASTIC")
STUDY = "stage29b_four_fibre_mechanics_qualification_20260825"
DESIGN_DIR = ROOT / "stage29_designs" / STUDY / "design_01"
OUT = ROOT / "stage29_evaluations" / STUDY / "design_audit_01"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def canonical_sha(obj: object) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def main() -> None:
    if OUT.exists():
        raise SystemExit(f"Refusing to overwrite immutable output: {OUT}")
    manifest_path = DESIGN_DIR / "design_manifest.json"
    completion_path = DESIGN_DIR / "completion.json"
    d = json.loads(manifest_path.read_text(encoding="utf-8"))
    c = json.loads(completion_path.read_text(encoding="utf-8"))
    cases = d["cases"]
    pair_counts = {}
    for x in cases:
        pair_counts[(x["placement_block"], x["topology_regime"])] = pair_counts.get((x["placement_block"], x["topology_regime"]), 0) + 1
    contact_rich = [x for x in cases if x["topology_regime"] == "contact_rich"]
    low_contact = [x for x in cases if x["topology_regime"] == "low_contact"]
    checks = {
        "schema": d["schema"] == "lbs.stage29b-four-fibre-mechanics-qualification.v1",
        "completion_passed": c.get("passed") is True,
        "completion_binds_manifest": c.get("design_manifest_sha256") == sha256(manifest_path),
        "sources_exist_and_hash_match": all(sha256(Path(d["source_paths"][k])) == v for k, v in d["source_hashes"].items()),
        "exact_six_unique_cases": len(cases) == 6 and len({x["case_id"] for x in cases}) == 6,
        "three_complete_matched_blocks": pair_counts == {(b, t): 1 for b in "ABC" for t in ("low_contact", "contact_rich")},
        "four_fibres_and_f37_nodes": all(x["fibre_count"] == 4 and x["nodes_per_fibre"] == 37 for x in cases),
        "low_contact_has_no_intended_edges": all(x["intended_terminal_contact_edges"] == [] for x in low_contact),
        "contact_rich_has_two_disjoint_intended_edges": all(x["intended_terminal_contact_edges"] == [[1, 2], [3, 4]] for x in contact_rich),
        "contact_rich_forbids_cross_pair_edges": all(x["forbidden_terminal_contact_edges"] == [[1, 3], [1, 4], [2, 3], [2, 4]] for x in contact_rich),
        "topology_measured_not_label_only": all(x["topology_must_be_measured"] is True for x in cases),
        "fixed_sand_and_cell": all(x["sand_and_cell_fixed_exactly"] is True for x in cases),
        "stage28a_contact_suppression_inherited": "stage28a_revision2_runner" in d["source_hashes"],
        "case_matrix_hash": d["case_matrix_sha256"] == canonical_sha(cases),
        "all_execution_authorities_false": all(d["authority"][k] is False for k in (
            "candidate_geometry_generation", "geometry_acceptance", "runner_construction", "yade_execution", "gpu_flow", "permeability_claim", "new_physics"
        )),
    }
    passed = all(checks.values())
    audit = {
        "schema": "lbs.stage29b-four-fibre-mechanics-qualification.v1.audit",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "passed": passed,
        "status": "passed_design_audit_geometry_not_authorized" if passed else "failed_design_audit",
        "checks": checks,
        "design_manifest_sha256": sha256(manifest_path),
        "completion_sha256": sha256(completion_path),
        "next_handoff": {
            "authorized": "build and independently audit deterministic four-fibre candidate geometries in a new immutable revision",
            "not_authorized": "geometry acceptance before audit, runner construction, YADE execution, GPU flow, or permeability claims",
        },
    }
    OUT.mkdir(parents=True)
    p = OUT / "design_audit.json"
    p.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    checkpoint = {
        "schema": "lbs.stage29b-four-fibre-mechanics-qualification.v1.checkpoint",
        "passed": passed,
        "design_audit_sha256": sha256(p),
        "design_manifest_sha256": audit["design_manifest_sha256"],
        "authority": audit["next_handoff"],
    }
    (OUT / "checkpoint_manifest.json").write_text(json.dumps(checkpoint, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(OUT), **audit}, indent=2))
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
