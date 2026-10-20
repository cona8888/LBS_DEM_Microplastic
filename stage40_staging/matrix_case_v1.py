"""Hash-checkable loader for the three accepted Stage31 clean packings."""
import hashlib, json, sys
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "stage37_staging"), str(ROOT / "stage39_staging")]
import transport_contact as mechanics
import wall_field_v1


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(seed, target_velocity=1e-4):
    if int(seed) not in (1, 2, 3) or target_velocity <= 0:
        raise ValueError("unsupported packing or velocity")
    case = f"s31b_n216_s{int(seed)}_clean"
    geometry_path = ROOT / "stage31_designs/stage31d_replicated_nested_cpd2_geometry_20260826/geometry_01" / case / "geometry_cpd2.npz"
    run_path = ROOT / "stage31_runs/stage31e_replicated_nested_cpd2_gpu_20260826/gpu_screen_01" / f"stage31e_{case}_cpd2"
    field_path = run_path / "final_fields.npz"
    record_path = run_path / "record.json"
    record = json.loads(record_path.read_text())
    if not record.get("passed") or not record.get("converged"):
        raise RuntimeError("flow record not accepted")
    if sha(field_path) != record["artifacts"]["final_fields_npz_sha256"]:
        raise RuntimeError("field hash mismatch")
    geometry_data = np.load(geometry_path)
    field_data = np.load(field_path)
    spacing = float(geometry_data["spacing_m"][0])
    length = float(geometry_data["cell_length_m"][0])
    phase = np.asarray(field_data["phase"]).transpose(2, 1, 0)
    geometry_phase = np.asarray(geometry_data["phase"]).transpose(2, 1, 0)
    if not np.array_equal(phase, geometry_phase):
        raise RuntimeError("field/geometry phase mismatch")
    velocity = np.asarray(field_data["velocity_xyz_lu"], float).transpose(0, 3, 2, 1)
    fluid = phase == 0
    if np.any(velocity[:, ~fluid] != 0):
        raise RuntimeError("solid velocities are not zero")
    velocity *= target_velocity / float(velocity[0, fluid].mean())
    field = wall_field_v1.WallCellField(velocity, spacing, fluid)
    geometry = mechanics.GrainGeometry(
        np.asarray(geometry_data["sand_centres_m"]),
        np.asarray(geometry_data["sand_radii_m"]), length,
    )
    return field, geometry, length, spacing, (geometry_path, field_path, record_path)
