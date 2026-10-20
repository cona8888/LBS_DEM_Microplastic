from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(r"C:\MATDEM_MICROPLASTIC")
STUDY = "stage29e_low_concentration_hydraulic_design_20260826"
SOURCE = ROOT / "stage29_designs" / STUDY / "design_01"
OUT = ROOT / "stage29_evaluations" / STUDY / "design_audit_01"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canon(obj: object) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def main() -> None:
    if OUT.exists():
        raise FileExistsError(f"refusing to overwrite immutable output: {OUT}")
    p, cp = SOURCE / "design_manifest.json", SOURCE / "completion.json"
    d, c = json.loads(p.read_text()), json.loads(cp.read_text())
    cases = d["cases"]
    by_count = {n: [x for x in cases if x["fibre_count"] == n] for n in (1, 2, 4)}
    checks = {
        "completion_passed_and_bound": c.get("passed") is True and c.get("design_manifest_sha256") == sha(p),
        "all_sources_bound": all(sha(Path(d["source_paths"][k])) == v for k, v in d["source_hashes"].items()),
        "exact_eleven_unique_new_cases": len(cases) == 11 and len({x["case_id"] for x in cases}) == 11,
        "three_single_controls": len(by_count[1]) == 3 and len({x["mechanics_source_case_id"] for x in by_count[1]}) == 3,
        "two_unreplicated_mechanism_cases": len(by_count[2]) == 2 and {x["topology"] for x in by_count[2]} == {"separated", "crossing"} and all(x["replicate_role"] == "unreplicated_mechanism_case" for x in by_count[2]),
        "six_four_fibre_paired_context_cases": len(by_count[4]) == 6 and all({x["topology"] for x in by_count[4] if x["block"] == b} == {"zero_contact", "one_contact"} for b in "ABC"),
        "four_fibre_not_mislabelled_independent_crossing_replicates": all("not_crossing_location_replication" in x["replicate_role"] for x in by_count[4]),
        "run_order_permutation": sorted(x["frozen_cpd2_run_order"] for x in cases) == list(range(1, 12)),
        "matrix_bound": d["case_matrix_sha256"] == canon(sorted(cases, key=lambda x: x["case_id"])),
        "concentration_increases": all(d["concentration_mapping"][i]["achieved_dry_mass_percent"] < d["concentration_mapping"][i + 1]["achieved_dry_mass_percent"] for i in range(3)),
        "no_monotonicity_gate": d["analysis_plan"]["monotonicity_gate"] is False,
        "two_fibre_uncertainty_explicit": d["analysis_plan"]["two_fibre_uncertainty"] == "not_estimable_from_one_case_per_topology",
        "execution_fail_closed": all(d["authority"][k] is False for k in ("hydraulic_geometry_generation", "gpu_execution", "cpd4_execution", "permeability_claim", "mechanics_rerun", "mobile_sand", "two_way_coupling")),
    }
    passed = all(checks.values())
    audit = {"schema": d["schema"] + ".audit", "timestamp_utc": datetime.now(timezone.utc).isoformat(), "passed": passed, "status": "passed_design_audit_geometry_not_authorized" if passed else "failed_design_audit", "checks": checks, "design_manifest_sha256": sha(p), "completion_sha256": sha(cp), "summary": {"new_cases": len(cases), "reused_clean": 1, "concentrations_dry_mass_percent": [x["achieved_dry_mass_percent"] for x in d["concentration_mapping"]]}, "next_handoff": {"authorized": "build and independently audit eleven mechanics-terminal hydraulic geometries at CPD2", "not_authorized": "GPU execution, CPD4, permeability claims, mechanics rerun, mobile sand, or coupling"}}
    OUT.mkdir(parents=True)
    ap = OUT / "design_audit.json"
    ap.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (OUT / "checkpoint_manifest.json").write_text(json.dumps({"schema": d["schema"] + ".checkpoint", "passed": passed, "design_audit_sha256": sha(ap), "design_manifest_sha256": sha(p), "authority": audit["next_handoff"]}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(OUT), **audit}, indent=2))
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
