from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(r"C:\MATDEM_MICROPLASTIC")
STUDY = "stage29c_four_fibre_single_contact_qualification_20260825"
SOURCE = ROOT / "stage29_designs" / STUDY / "design_01"
OUT = ROOT / "stage29_evaluations" / STUDY / "design_audit_01"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canon(obj: object) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def main() -> None:
    if OUT.exists():
        raise FileExistsError(f"refusing to overwrite immutable output: {OUT}")
    p = SOURCE / "design_manifest.json"
    cp = SOURCE / "completion.json"
    d = json.loads(p.read_text(encoding="utf-8"))
    c = json.loads(cp.read_text(encoding="utf-8"))
    cases = d["cases"]
    checks = {
        "completion_passed_and_bound": c.get("passed") is True and c.get("design_manifest_sha256") == sha(p),
        "sources_bound": all(sha(Path(d["source_paths"][k])) == v for k, v in d["source_hashes"].items()),
        "stage29b_failure_bound": "stage29b_failure" in d["source_hashes"],
        "exact_six_unique_cases": len(cases) == 6 and len({x["case_id"] for x in cases}) == 6,
        "three_matched_blocks": all({x["topology_regime"] for x in cases if x["placement_block"] == b} == {"zero_contact", "one_contact"} for b in "ABC"),
        "all_four_f37_fibres": all(x["fibre_count"] == 4 and x["nodes_per_fibre"] == 37 for x in cases),
        "contact_graphs_exact": all(x["intended_terminal_contact_edges"] == ([] if x["topology_regime"] == "zero_contact" else [[1, 2]]) for x in cases),
        "topology_must_be_measured": all(x["topology_must_be_measured"] is True for x in cases),
        "matrix_bound": d["case_matrix_sha256"] == canon(cases),
        "execution_stays_forbidden": all(d["authority"][k] is False for k in ("candidate_geometry_generation", "geometry_acceptance", "runner_construction", "yade_execution", "gpu_flow")),
    }
    passed = all(checks.values())
    audit = {
        "schema": d["schema"] + ".audit",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "passed": passed,
        "status": "passed_revised_design_audit_geometry_not_authorized" if passed else "failed_revised_design_audit",
        "checks": checks,
        "design_manifest_sha256": sha(p),
        "completion_sha256": sha(cp),
        "next_handoff": {
            "authorized": "build and independently audit source-distinct zero-contact and one-contact four-fibre candidate geometries",
            "not_authorized": "geometry acceptance, runner construction, YADE execution, or GPU flow",
        },
    }
    OUT.mkdir(parents=True)
    ap = OUT / "design_audit.json"
    ap.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (OUT / "checkpoint_manifest.json").write_text(json.dumps({
        "schema": d["schema"] + ".checkpoint",
        "passed": passed,
        "design_audit_sha256": sha(ap),
        "design_manifest_sha256": sha(p),
        "authority": audit["next_handoff"],
    }, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(OUT), **audit}, indent=2))
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
