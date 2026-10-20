"""Bounded one-time initialization correction; no transport or altered LBM physics."""
from __future__ import annotations

import argparse
import gc
import hashlib
import json
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "stage113_staging"))
import audit_flow_time_levels_v1 as audit
import probe_parity_initializer_v1 as probe
import steady_flow_gate_v1 as gate

STUDY = "stationary_flow_requalification_20260915"
DESIGN = ROOT / "stage114_designs" / STUDY / "design_01.json"
BASE = ROOT / "stage113_evaluations/temporal_flow_consistency_20260915"


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def write(path, value):
    # Serialize completely before opening to avoid partially written JSON.
    encoded = json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n"
    with Path(path).open("x", encoding="utf-8") as stream:
        stream.write(encoded)


def bind(path):
    path = Path(path).resolve()
    return {"path": str(path), "sha256": audit.sha(path)}


def verify_bindings(value):
    if isinstance(value, dict):
        if "path" in value and "sha256" in value:
            require(audit.sha(value["path"]) == value["sha256"], "hash mismatch: " + value["path"])
        for item in value.values():
            verify_bindings(item)
    elif isinstance(value, list):
        for item in value:
            verify_bindings(item)


def verify_design(design):
    verify_bindings(design)
    for case in design["cases"] + [design["reused_reference"]]:
        source = case["source"]
        require(audit.sha(source["record"]) == source["record_sha256"], "source record changed")
        record = audit.read(source["record"])
        require(record["acceleration_lu"] == case["acceleration_lu"], "forcing changed")
    require(audit.sha(__file__) == design["modules"]["runner"]["sha256"], "runner changed")


def prepare():
    require(not DESIGN.exists(), "immutable design exists")
    manifest = audit.read(BASE / "audit_01/manifest.json")
    d111 = audit.read(manifest["lineage"]["stage111_design"]["path"])
    d112path = ROOT / "stage112_designs/reference_flow_resolution_packing_20260915/design_01/resolved_design.json"
    d112 = audit.read(d112path)
    accepted_path = BASE / "independent_evaluation_02/results.json"
    require(audit.sha(accepted_path) == "b8a8ca8dba298fc4cefe4aeae5978129b0a8d1787facbc91474b575585f14aea", "initializer acceptance changed")
    require(audit.read(accepted_path)["passed"] is True, "initializer not accepted")
    definitions = {c["case_id"]: {**c, "packing_seed": 2, "cpd": 2, "geometry": d111["geometry"]} for c in d111["cases"]}
    definitions.update({c["case_id"]: {**c, "flow_factor": 1.0} for c in d112["cases"]})
    definitions["stage31e_s31b_n216_s2_clean_cpd2"] = {"packing_seed": 2, "cpd": 2, "geometry": d111["geometry"], "flow_factor": None}
    sources = {c["case_id"]: c for c in manifest["sources"]}

    def item(source_id, case_id):
        source, spec = sources[source_id], definitions[source_id]
        record = audit.read(source["record"])
        return {"case_id": case_id, "source": source, "geometry": bind(spec["geometry"]),
                "packing_seed": spec["packing_seed"], "cpd": spec["cpd"],
                "flow_factor": spec["flow_factor"], "acceleration_lu": record["acceleration_lu"],
                "target_mean_interstitial_velocity_m_s": spec.get("target_physical_mean_interstitial_velocity_m_s")}

    cases = [item(old, new) for old, new in [
        ("stage111_s2_clean_f0p5_cpd2", "s2_f0p5_cpd2"),
        ("stage111_s2_clean_f2p0_cpd2", "s2_f2p0_cpd2"),
        ("stage112_s1_clean_f1p0_cpd2", "s1_f1p0_cpd2"),
        ("stage112_s3_clean_f1p0_cpd2", "s3_f1p0_cpd2"),
        ("stage31e_s31b_n216_s2_clean_cpd2", "s2_archive_low_re_cpd2"),
        ("stage112_s2_clean_f1p0_cpd4", "s2_f1p0_cpd4")]]
    reused = item("stage111_s2_clean_f1p0_cpd2", "s2_f1p0_cpd2")
    reused["corrected_bundle"] = {name: bind(BASE / "initializer_probe_01/archive_phase_average" / name)
                                    for name in ["result.json", "final_fields.npz", "final_shifted_state.npz"]}
    lineage = dict(manifest["lineage"])
    lineage.update({"stage112_design": bind(d112path), "stage113_audit": bind(BASE / "audit_01/completion.json"),
                    "stage113_probe": bind(BASE / "initializer_probe_01/completion.json"),
                    "stage113_accepted_evaluation": bind(accepted_path)})
    design = {"schema": "matdem.stage114.stationary-flow-requalification.v1", "created_utc": datetime.now(timezone.utc).isoformat(),
              "recipe": "Average consecutive stored population states ONCE as initializer, then unchanged tau=0.8 GPU update for 4096 steps. No running filter, no averaged velocity export.",
              "cases": cases, "reused_reference": reused, "lineage": lineage,
              "modules": {"runner": bind(__file__), "probe": bind(probe.__file__), "audit": bind(audit.__file__),
                          "steady_gate": bind(gate.__file__),
                          "cpu_evaluator": bind(ROOT / "stage113_staging/evaluate_parity_correction_v2.py")},
              "controls": {"tau": .8, "nu_lu": .1, "threads": 256, "steps": 4096, "sample_interval": 257, "final_consecutive": 8},
              "physical_fluid": {"density_kg_m3": 998.2, "dynamic_viscosity_Pa_s": .001002},
              "thresholds": {"target_mean_relative_error_max": .05, "independent_field_relative_l2_max": 2e-6,
                             "cpu_node_relative_l2_max": 5e-5, "steady_balance_relative_max": .005,
                             "profile_rms_max": .02, "profile_p95_max": .05, "gross_mobility_relative_shift_max": .1},
              "authority": {"six_flow_corrections_only": True, "particle_transport": False, "campaign": False},
              "claim_boundary": "Numerical clean-flow requalification, not absolute permeability validation or particle transport convergence. Corrected archive reuse tested only in seed2 CPD2; other packings' nonreference speeds remain untested."}
    verify_design(design)
    DESIGN.parent.mkdir(parents=True, exist_ok=True)
    write(DESIGN, design)
    print(json.dumps({"design": str(DESIGN), "sha256": audit.sha(DESIGN), "new_cases": len(cases)}), flush=True)


def run(output):
    output = output.resolve()
    require(output.is_relative_to(ROOT / "stage114_runs") and not output.exists(), "output is not fresh/in scope")
    design = audit.read(DESIGN)
    verify_design(design)
    output.mkdir(parents=True)
    write(output / "manifest.json", {"design": bind(DESIGN), "runner": bind(__file__),
           "case_order": [c["case_id"] for c in design["cases"]], "created_utc": datetime.now(timezone.utc).isoformat()})
    driver = None
    try:
        audit.legacy.install_generic_mask_oracle()
        lineage = design["lineage"]
        adapter = {"lineage": {"cuda_source": lineage["cuda_source"]["path"], "qualified_ptx_sha256": lineage["qualified_ptx_sha256"]}}
        driver, build = audit.legacy.create_driver(adapter, Path(r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.9\bin"), 0)
        records = {}
        for spec in design["cases"]:
            name = spec["case_id"]
            print("BEGIN", name, flush=True)
            with np.load(spec["source"]["final_shifted_state"]["path"]) as saved, np.load(spec["geometry"]["path"]) as geom:
                state, phase = saved["shifted_state"], saved["phase"]
                require(np.array_equal(phase, geom["phase"]), name + " geometry mismatch")
            case = probe.case_for(phase, spec["acceleration_lu"], name)
            next_state = probe.one_step(driver, state, phase, case)
            initial = probe.average_states(state, next_state)
            init_info = {"source_state_array_sha256": audit.digest(state), "next_state_array_sha256": audit.digest(next_state),
                         "averaged_state_array_sha256": audit.digest(initial)}
            del state, next_state
            gc.collect()
            result, field, density = probe.relax(driver, initial, phase, case, output, name, design["controls"]["steps"])
            temporal = gate.check_steady_flow([r for r in result["rows"] if r["step"] % 257 == 0], result["rows"][-8:],
                            export_exact=True, fatal_health_code=result["numerical_health"]["fatal_sticky_code"])
            record = {"case_id": name, "source": spec["source"], "geometry": spec["geometry"], "acceleration_lu": spec["acceleration_lu"],
                      "initializer": init_info, "result": bind(output / name / "result.json"), "temporal_gate": temporal,
                      "passed": bool(result["passed"] and temporal["passed"]), "design_sha256": audit.sha(DESIGN)}
            write(output / name / "record.json", record)
            records[name] = audit.sha(output / name / "record.json")
            require(record["passed"], name + " failed steady gate; stop without retry")
            del initial, phase, field, density
            gc.collect()
        verify_design(design)
        write(output / "completion.json", {"status": "complete_pending_independent_evaluation", "passed": True,
              "design_sha256": audit.sha(DESIGN), "manifest_sha256": audit.sha(output / "manifest.json"),
              "record_sha256": records, "frozen_order": [c["case_id"] for c in design["cases"]],
              "source_bindings_unchanged": True, "build": build, "particle_transport_authorized": False})
        print("ALL SIX CASES COMPLETE", flush=True)
    except Exception as exc:
        write(output / "failure.json", {"error": repr(exc), "traceback": traceback.format_exc(), "no_automatic_retry": True})
        raise
    finally:
        if driver is not None:
            driver.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["prepare", "run"])
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.mode == "prepare":
        prepare()
    else:
        require(args.output is not None, "--output required")
        run(args.output)
