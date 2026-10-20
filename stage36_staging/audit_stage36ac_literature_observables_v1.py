"""Audit observable compatibility; no solver execution or parameter fitting."""
import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INPUTS = {
    "contract": ROOT / "stage36_staging" / "STAGE36AC_LITERATURE_OBSERVABLE_CONTRACT.md",
    "stage36b_verification": ROOT / "stage36_evaluations" / "stage36b_release_accounting_20260906" / "verification_01" / "verification.json",
    "stage36b_history": ROOT / "stage36_evaluations" / "stage36b_release_accounting_20260906" / "verification_01" / "manufactured_history.json",
    "published_endpoints": ROOT / "stage36_evaluations" / "literature_sphere_fibre_20260909" / "published_endpoints.json",
    "flume_endpoints": ROOT / "stage36_evaluations" / "literature_extraction_20260909" / "published_flume_endpoints.json",
    "processing_audit": ROOT / "stage36_evaluations" / "literature_extraction_20260909" / "processing_code_audit.json",
}


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"immutable output already exists: {args.output}")
    missing = [str(path) for path in INPUTS.values() if not path.is_file()]
    if missing:
        raise FileNotFoundError(missing)

    verification = json.loads(INPUTS["stage36b_verification"].read_text(encoding="utf-8"))
    history = json.loads(INPUTS["stage36b_history"].read_text(encoding="utf-8"))
    endpoints = json.loads(INPUTS["published_endpoints"].read_text(encoding="utf-8"))
    flume = json.loads(INPUTS["flume_endpoints"].read_text(encoding="utf-8"))
    processing = json.loads(INPUTS["processing_audit"].read_text(encoding="utf-8"))

    required = {
        "net_downstream_fraction", "gross_outward_mass_kg", "gross_return_mass_kg",
        "complete_exit_events", "unique_ever_completely_exited", "pore_volumes_flushed",
        "maximum_relative_balance_residual",
    }
    schema = set.intersection(*(set(row) for row in history)) if history else set()
    accounting_ready = bool(verification.get("passed") and required <= schema)
    concfit_rejected = processing.get("concfit_export_disposition") == "rejected_for_integration_fitting_and_calibration"

    classes = [
        {"evidence": "Boos et al. sphere flume", "observable": "pulse-injection reach storage and passage timing", "matrix_release_compatible": False, "role": "future matched pulse-transport validation"},
        {"evidence": "Ameen et al. spheres", "observable": "outlet recovery / injected mass", "matrix_release_compatible": False, "role": "future matched sphere-recovery validation"},
        {"evidence": "La Capra et al. fibres", "observable": "exported fraction of injected fibre mass", "matrix_release_compatible": False, "role": "future matched fibre pulse-transport validation"},
        {"evidence": "sphere clogging study", "observable": "K(t)/K0", "matrix_release_compatible": False, "role": "hydraulic-response validation only"},
    ]
    result = {
        "stage": "Stage36AC",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "status": "passed_observable_classification_but_matrix_release_validation_not_ready",
        "input_hashes": {name: sha256(path) for name, path in INPUTS.items()},
        "accounting_schema_ready": accounting_ready,
        "accounting_required_fields": sorted(required),
        "quarantined_export_confirmed": concfit_rejected,
        "literature_observation_count": len(endpoints.get("observations", [])) + len(flume.get("published_observations", [])),
        "comparators": classes,
        "preloaded_matrix_release_comparator_available": False,
        "physics_verification_ready": False,
        "calibration_authorized": False,
        "transport_run_authorized": False,
        "next_action": "qualify an independent nonzero-force particle benchmark, then implement a matched pulse-injection validation configuration or retain matrix release as prediction-only",
    }
    if not accounting_ready or not concfit_rejected:
        result["status"] = "failed_readiness_audit"

    args.output.mkdir(parents=True)
    (args.output / "audit.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# Stage36AC literature-observable readiness audit", "",
        f"**Result:** {result['status']}.", "",
        f"The Stage36B accounting schema is ready: **{accounting_ready}**. The suspect fitted export remains quarantined: **{concfit_rejected}**.", "",
        "None of the assembled experimental datasets measures release from an initially contaminated matrix. They measure pulse-injection passage/recovery, temporary reach storage, or permeability change. Consequently, they cannot directly validate the intended matrix-release fraction.", "",
        "| Evidence | Observable | Permitted role |", "|---|---|---|",
    ]
    lines += [f"| {c['evidence']} | {c['observable']} | {c['role']} |" for c in classes]
    lines += ["", "No physics run or calibration was launched. Next, qualify the independent particle-force benchmark; after that, use a matched pulse-injection model for external validation and keep preloaded-matrix release explicitly prediction-only unless a matching dataset is found.", ""]
    (args.output / "RESULTS.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
