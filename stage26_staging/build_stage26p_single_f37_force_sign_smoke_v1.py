"""Freeze the Stage26p free-F37 force-integration smoke configuration."""
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


def wsl(path):
    value = str(Path(path).resolve()).replace("\\", "/")
    return "/mnt/" + value[0].lower() + value[2:]


def main():
    analytical = ROOT / "stage26_evaluations" / "stage26p_single_fibre_mechanism_20260818" / "analytical_buoyancy_check_01" / "analytical_check.json"
    placement = ROOT / "stage26_designs" / "stage26g_fresh_cage_fixed_qualification_20260817" / "design_02" / "normalized_placements" / "stage26f_cage_candidate_07_development.json"
    runner = ROOT / "stage26_staging" / "run_stage26p_single_f37_force_sign_smoke_v1.py"
    output = ROOT / "stage26_designs" / "stage26p_single_fibre_mechanism_20260818" / "force_sign_smoke_design_01"
    if output.exists():
        raise RuntimeError("immutable Stage26p force design exists")
    with analytical.open("r", encoding="utf-8") as stream:
        evidence = json.load(stream)
    if not evidence.get("passed") or not evidence["authority"].get("single_fibre_buoyancy_force_integration_smoke_authorized"):
        raise RuntimeError("analytical check does not authorize force smoke")
    cfg = {
        "schema": "lbs.stage26p-single-f37-force-sign-smoke-config.v1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "status": "authorized_stage26p_single_f37_force_sign_smoke",
        "expected_yade_version": "2022.01a",
        "member_radius_m": 5.0e-5,
        "target_mass_kg": 6.997520680643619e-9,
        "fibre_density_kg_m3": 940.0,
        "dry_acceleration_z_m_s2": -9.81,
        "submerged_acceleration_z_m_s2": 0.6261702127659586,
        "time_step_s": 1.0e-5,
        "steps": 1000,
        "maximum_relative_integration_error": 0.002,
        "sources": {"runner": wsl(runner), "runner_sha256": sha256(runner), "analytical_check": wsl(analytical), "analytical_check_sha256": sha256(analytical), "placement": wsl(placement), "placement_sha256": sha256(placement)},
        "claim_boundary": "Free rigid-clump force integration verification only; no drag, terminal speed, sand contact, trapping, flow, or permeability claim.",
        "authority": {"force_sign_smoke_authorized": True, "drag_calibration_authorized": False, "full_mixture_execution_authorized": False, "flow_execution_authorized": False},
    }
    output.mkdir(parents=True)
    path = output / "config.json"
    with path.open("x", encoding="utf-8") as stream:
        json.dump(cfg, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({"config": str(path), "sha256": sha256(path), "runner_sha256": sha256(runner)}, sort_keys=True))


if __name__ == "__main__":
    main()
