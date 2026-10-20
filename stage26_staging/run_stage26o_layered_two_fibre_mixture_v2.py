"""Layered-pluviation adapter for the immutable Stage26o mixture runner.

Only the deterministic initial z distribution and fibre-leakage diagnostics
are changed.  All contact physics, phase controls, and acceptance gates remain
in the bound v1 runner/configuration.
"""
from __future__ import print_function

import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(os.environ.get("STAGE26O_MIXTURE_SCRIPT", __file__)))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
BASE_PATH = os.path.join(HERE, "run_stage26o_two_fibre_mixture_v1.py")
SPEC = importlib.util.spec_from_file_location("stage26o_mixture_v1", BASE_PATH)
mixture = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mixture)
for symbol, value in list(globals().items()):
    if not symbol.startswith("__") and symbol not in {"mixture", "SPEC"}:
        mixture.__dict__.setdefault(symbol, value)

_NativeRandom = mixture.random.Random
_base_diagnostic = mixture.diagnostic
_base_gate = mixture.final_gate


class LayeredRandom(object):
    """Preserve x/y RSA sampling and alternate z trials across two sand bands."""

    def __init__(self, seed):
        self._rng = _NativeRandom(seed)
        self._coordinate_call = 0
        self._z_trial = 0

    def uniform(self, lower, upper):
        axis = self._coordinate_call % 3
        self._coordinate_call += 1
        if axis != 2:
            return self._rng.uniform(lower, upper)
        length = lower + upper
        use_lower_band = self._z_trial % 2 == 0
        self._z_trial += 1
        if use_lower_band:
            band_upper = min(upper, 0.45 * length)
            if band_upper <= lower:
                raise RuntimeError("lower sand band cannot contain this radius")
            return self._rng.uniform(lower, band_upper)
        band_lower = max(lower, 0.57 * length)
        if upper <= band_lower:
            raise RuntimeError("upper sand band cannot contain this radius")
        return self._rng.uniform(band_lower, upper)

    def __getattr__(self, name):
        return getattr(self._rng, name)


def leakage_diagnostic(record, phase, phase_index, cfg, triax, sand_ids, sand_volume, total_weight, fibre_members, parent_ids, initial_poses, wall_ids):
    row = _base_diagnostic(record, phase, phase_index, cfg, triax, sand_ids, sand_volume, total_weight, fibre_members, parent_ids, initial_poses, wall_ids)
    dimensions, lower, upper = mixture.core.wall_dimensions(triax)
    leaked_members = 0
    bounds = []
    for members in fibre_members:
        centres = [[float(mixture.O.bodies[body_id].state.pos[axis]) for axis in range(3)] for body_id in members]
        bounds.append({
            "minimum_member_centre_m": [min(centre[axis] for centre in centres) for axis in range(3)],
            "maximum_member_centre_m": [max(centre[axis] for centre in centres) for axis in range(3)],
        })
        for body_id, centre in zip(members, centres):
            radius = float(mixture.O.bodies[body_id].shape.radius)
            if any(centre[axis] < lower[axis] - radius or centre[axis] > upper[axis] + radius for axis in range(3)):
                leaked_members += 1
    row["leaked_sand_particle_count"] = int(row["leaked_particle_count"])
    row["leaked_fibre_member_count"] = int(leaked_members)
    # The bound base state machine already fails closed on this combined field.
    row["leaked_particle_count"] = int(row["leaked_particle_count"]) + int(leaked_members)
    row["fibre_parent_positions_m"] = [[float(mixture.O.bodies[parent_id].state.pos[axis]) for axis in range(3)] for parent_id in parent_ids]
    row["fibre_member_bounds_m"] = bounds
    row["layered_initialization"] = True
    row["sand_initial_z_bands_fraction"] = [[0.0, 0.45], [0.57, 1.0]]
    row["fibre_initial_fall_zone_fraction"] = cfg["initialization"]["fibre_pivot_fractions"]
    return row


def leakage_gate(row, cfg):
    checks = _base_gate(row, cfg)
    if row.get("phase") == "zero_gravity_final_hold":
        checks["no_fibre_leakage"] = row["leaked_fibre_member_count"] == 0
    return checks


def layered_write_history(path, rows):
    json_fields = {
        "wall_dimensions_m",
        "principal_wall_stress_pa_compression_positive",
        "distinct_sand_contacts_by_fibre",
        "contacted_sand_body_ids_by_fibre",
        "fibre_wall_real_contact_count_by_fibre",
        "fibre_member_count_by_fibre",
        "fibre_translation_m_by_fibre",
        "fibre_translation_over_D50_by_fibre",
        "fibre_rotation_deg_by_fibre",
        "fibre_parent_positions_m",
        "fibre_member_bounds_m",
        "sand_initial_z_bands_fraction",
        "fibre_initial_fall_zone_fraction",
    }
    with open(path, "x") as stream:
        writer = mixture.csv.DictWriter(stream, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        for row in rows:
            encoded = dict(row)
            for field in json_fields:
                if field in encoded:
                    encoded[field] = mixture.json.dumps(encoded[field], separators=(",", ":"))
            writer.writerow(encoded)


mixture.random.Random = LayeredRandom
mixture.diagnostic = leakage_diagnostic
mixture.final_gate = leakage_gate
mixture.write_history = layered_write_history

if __name__ == "__main__":
    mixture.main()
