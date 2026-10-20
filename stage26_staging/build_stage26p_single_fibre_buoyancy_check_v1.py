"""Analytical rung-1 check for the missing saturated-fibre body force."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(r"C:\MATDEM_MICROPLASTIC")


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1048576), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main():
    source = ROOT / "stage26_evaluations" / "stage26o_gravity_joint_deposition_20260818" / "two_fibre_layered_evaluation_03" / "evaluation.json"
    output = ROOT / "stage26_evaluations" / "stage26p_single_fibre_mechanism_20260818" / "analytical_buoyancy_check_01"
    if output.exists():
        raise RuntimeError("immutable Stage26p analytical output exists")
    with source.open("r", encoding="utf-8") as stream:
        evaluation = json.load(stream)
    if not evaluation.get("passed") or not evaluation["authority"].get("single_fibre_missing_mechanism_verification_design_authorized"):
        raise RuntimeError("Stage26o evaluation does not authorize Stage26p design")
    rho_polymer = 940.0
    rho_water = 1000.0
    mass = 6.997520680643619e-9
    gravity = 9.81
    volume = mass / rho_polymer
    dry_weight = mass * gravity
    buoyancy = rho_water * volume * gravity
    net_downward = dry_weight - buoyancy
    submerged_acceleration_downward = net_downward / mass
    payload = {
        "schema": "lbs.stage26p-single-fibre-analytical-buoyancy-check.v1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "passed": True,
        "research_role": "analytical_model_form_check_not_calibration_or_validation",
        "physical_question": "Does the existing dry downward-gravity preparation have the correct body-force direction for the specified 940 kg/m3 fibre after water saturation?",
        "inputs": {"polymer_density_kg_m3": rho_polymer, "water_density_kg_m3": rho_water, "fibre_target_mass_kg": mass, "gravity_m_s2": gravity},
        "derived": {"fibre_material_volume_m3": volume, "dry_weight_downward_n": dry_weight, "water_buoyancy_upward_n": buoyancy, "net_submerged_force_downward_n": net_downward, "net_submerged_force_upward_n": -net_downward, "submerged_acceleration_downward_m_s2": submerged_acceleration_downward, "density_ratio_polymer_to_water": rho_polymer / rho_water},
        "checks": {"polymer_less_dense_than_water": rho_polymer < rho_water, "submerged_force_is_upward": net_downward < 0.0, "dry_and_saturated_body_force_directions_differ": net_downward < 0.0},
        "conclusion": "An unrestrained 940 kg/m3 F37 fibre accelerates upward in water. Dry downward-gravity deposition cannot represent its saturated mechanical tendency; confinement/contact trapping must be prepared separately and then tested against buoyancy plus drag.",
        "claim_boundary": "Analytical direction-and-scale check only. No drag coefficient, terminal speed, fibre flexibility, sand trapping, flow, or permeability prediction.",
        "source_evaluation": {"path": str(source), "sha256": sha256(source)},
        "authority": {"single_fibre_buoyancy_force_integration_smoke_authorized": True, "drag_calibration_authorized": False, "full_mixture_execution_authorized": False, "flow_execution_authorized": False, "production_parametric_study_authorized": False},
        "next_action": "verify_force_sign_and_acceleration_for_one_free_F37_clump_then_design_a_contact_trapping_test",
    }
    output.mkdir(parents=True)
    path = output / "analytical_check.json"
    with path.open("x", encoding="utf-8") as stream:
        json.dump(payload, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({"output": str(path), "sha256": sha256(path), "derived": payload["derived"]}, sort_keys=True))


if __name__ == "__main__":
    main()
