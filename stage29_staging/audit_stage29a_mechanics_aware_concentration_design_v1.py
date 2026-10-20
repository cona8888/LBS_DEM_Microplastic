from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(r"C:\MATDEM_MICROPLASTIC")
STUDY = "stage29a_mechanics_aware_concentration_design_20260825"
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
    matrix_path = DESIGN_DIR / "case_matrix.csv"
    for p in (manifest_path, completion_path, matrix_path):
        if not p.is_file():
            raise SystemExit(f"Missing design artifact: {p}")
    d = json.loads(manifest_path.read_text(encoding="utf-8"))
    c = json.loads(completion_path.read_text(encoding="utf-8"))
    cases = d["cases"]
    ids = [x["case_id"] for x in cases]
    by_count = {}
    by_pair = {}
    for x in cases:
        by_count[x["fibre_count"]] = by_count.get(x["fibre_count"], 0) + 1
        key = (x["fibre_count"], x["topology_regime"])
        by_pair[key] = by_pair.get(key, 0) + 1
    source_hashes_match = all(sha256(Path(d["source_paths"][k])) == v for k, v in d["source_hashes"].items())
    checks = {
        "schema": d["schema"] == "lbs.stage29a-mechanics-aware-concentration-design.v1",
        "completion_passed": c.get("passed") is True,
        "completion_binds_manifest": c.get("design_manifest_sha256") == sha256(manifest_path),
        "completion_binds_csv": c.get("case_matrix_csv_sha256") == sha256(matrix_path),
        "source_hashes_match": source_hashes_match,
        "exact_15_unique_new_cases": len(cases) == 15 and len(set(ids)) == 15,
        "count_replication": by_count == {1: 3, 2: 6, 4: 6},
        "topology_replication": by_pair == {
            (1, "single_open"): 3,
            (2, "separated"): 3,
            (2, "crossing"): 3,
            (4, "low_contact"): 3,
            (4, "contact_rich"): 3,
        },
        "blocks_complete": all(
            {x["placement_block"] for x in cases if x["fibre_count"] == n and x["topology_regime"] == t} == {"A", "B", "C"}
            for n, t in by_pair
        ),
        "randomized_order_is_permutation": sorted(x["frozen_randomized_run_order"] for x in cases) == list(range(1, 16)),
        "case_matrix_hash": d["case_matrix_sha256"] == canonical_sha(cases),
        "concentration_strictly_increasing": all(
            d["concentration_mapping"][i]["achieved_dry_mass_percent"] < d["concentration_mapping"][i + 1]["achieved_dry_mass_percent"]
            for i in range(3)
        ),
        "four_fibre_is_below_stage24_0p05_level": d["concentration_mapping"][-1]["achieved_dry_mass_percent"] < 0.05,
        "mechanics_first": d["sequential_plan"][0] == "qualify six four-fibre mechanics cases",
        "no_monotonicity_gate": d["predeclared_gates"]["monotonicity_required"] is False,
        "resolution_band_conservative_vs_stage28c": d["predeclared_gates"]["numerical_resolution_band_k_over_k0"] >= 0.00012252563027514984,
        "execution_not_authorized": all(d["authority"][k] is False for k in (
            "mechanics_execution", "cpd2_gpu_execution", "cpd4_execution", "production_concentration_execution", "new_physics"
        )),
    }
    passed = all(checks.values())
    audit = {
        "schema": "lbs.stage29a-mechanics-aware-concentration-design.v1.audit",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "status": "passed_design_audit_execution_not_authorized" if passed else "failed_design_audit",
        "passed": passed,
        "checks": checks,
        "design_manifest_sha256": sha256(manifest_path),
        "case_matrix_csv_sha256": sha256(matrix_path),
        "completion_sha256": sha256(completion_path),
        "summary": {
            "new_case_count": len(cases),
            "reused_clean_count": 1,
            "fibre_counts": [0, 1, 2, 4],
            "maximum_dry_mass_percent": d["concentration_mapping"][-1]["achieved_dry_mass_percent"],
            "four_fibre_mechanics_cases_to_qualify_first": 6,
        },
        "next_handoff": {
            "authorized": "design and independent audit of a six-case four-fibre mechanics qualification",
            "not_authorized": "mechanics execution, GPU flow execution, CPD4, higher concentration, or new physics",
        },
    }
    OUT.mkdir(parents=True)
    audit_path = OUT / "design_audit.json"
    audit_path.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    checkpoint = {
        "schema": "lbs.stage29a-mechanics-aware-concentration-design.v1.checkpoint",
        "passed": passed,
        "design_audit_sha256": sha256(audit_path),
        "design_manifest_sha256": audit["design_manifest_sha256"],
        "case_matrix_csv_sha256": audit["case_matrix_csv_sha256"],
        "authority": audit["next_handoff"],
    }
    (OUT / "checkpoint_manifest.json").write_text(json.dumps(checkpoint, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(OUT), **audit}, indent=2))
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
