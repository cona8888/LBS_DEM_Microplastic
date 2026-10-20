"""Freeze Stage26g allocation, normalized placements, and development config."""

import argparse
import csv
import hashlib
import json
from pathlib import Path


def digest(path):
    value = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def load(path):
    with Path(path).open("r", encoding="utf-8-sig") as stream:
        return json.load(stream)


def write_json(path, value):
    with Path(path).open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--campaign", required=True)
    parser.add_argument("--static-handoff", required=True)
    parser.add_argument("--base-config", required=True)
    parser.add_argument("--runner", required=True)
    parser.add_argument("--derivation", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    campaign = Path(args.campaign).resolve()
    static_handoff_path = Path(args.static_handoff).resolve()
    base_config_path = Path(args.base_config).resolve()
    runner_path = Path(args.runner).resolve()
    derivation_path = Path(args.derivation).resolve()
    output = Path(args.output).resolve()
    if output.exists():
        raise RuntimeError("immutable Stage26g design output already exists")
    handoff, base, derivation = load(static_handoff_path), load(base_config_path), load(derivation_path)
    if handoff.get("passed") is not True or handoff["next_stage"]["stage26g_fixed_fibre_design_preparation_authorized"] is not True:
        raise RuntimeError("Stage26f handoff does not authorize Stage26g design")
    if derivation.get("passed") is not True or derivation["output_sha256"] != digest(runner_path):
        raise RuntimeError("Stage26g runner derivation mismatch")
    # Frozen deterministic permutation from seed 260617200: [6,7,8,4,2,5,1,3].
    allocation = {
        "development": [6, 7, 8],
        "heldout": [4, 2],
        "reserve": [5, 1, 3],
    }
    output.mkdir(parents=True)
    normalized_dir = output / "normalized_placements"
    normalized_dir.mkdir()
    allocation_rows = []
    normalized = {}
    for role, indices in allocation.items():
        for order, index in enumerate(indices, 1):
            source_path = campaign / f"stage26f_f002_cage_candidate_{index:02d}" / "placement.json"
            source = load(source_path)
            if source.get("passed") is not True or len(source.get("fibres", [])) != 2:
                raise RuntimeError("allocated Stage26f placement did not pass")
            stage_role = "development_capture" if role == "development" else (
                "heldout_capture" if role == "heldout" else "reserve_not_authorized"
            )
            value = dict(source)
            value.update(
                {
                    "schema": "lbs.stage26g-normalized-four-support-placement.v1",
                    "record_type": stage_role,
                    "stage26g_role": stage_role,
                    "source_stage26f_placement": str(source_path).replace("\\", "/"),
                    "source_stage26f_placement_sha256": digest(source_path),
                    "legacy_stage26b_revision3_candidate08_read_or_used": False,
                }
            )
            target = normalized_dir / f"stage26f_cage_candidate_{index:02d}_{role}.json"
            write_json(target, value)
            normalized[index] = target
            allocation_rows.append(
                {
                    "allocation_seed": 260617200,
                    "role": role,
                    "role_order": order,
                    "stage26f_candidate_index": index,
                    "normalized_placement": str(target).replace("\\", "/"),
                    "normalized_placement_sha256": digest(target),
                }
            )
    allocation_path = output / "allocation.csv"
    with allocation_path.open("x", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(allocation_rows[0]))
        writer.writeheader()
        writer.writerows(allocation_rows)

    design = {
        "schema": "lbs.stage26g-fresh-cage-fixed-fibre-qualification-design.v1",
        "status": "frozen_before_yade_execution",
        "physical_question": "Do fresh four-support cage placements robustly reach the frozen fixed-fibre equilibrium window across development and held-out geometries?",
        "allocation_seed": 260617200,
        "allocation": allocation,
        "development_acceptance": {
            "required_qualified_cases": 2,
            "case_count": 3,
            "all_cases_require_exact_four_contact_insertion": True,
            "no_geometry_or_software_failure": True,
        },
        "heldout_acceptance": {
            "execution_requires_development_acceptance": True,
            "required_qualified_cases": 2,
            "case_count": 2,
            "no_retuning_after_development": True,
        },
        "temporal_protocol": {
            "maximum_blocks": 300,
            "steps_per_block": 500,
            "minimum_blocks_before_window": 60,
            "required_consecutive_passing_blocks": 10,
            "all_fibres_fixed": True,
            "free_release": False,
        },
        "engagement_gates": {
            "minimum_distinct_sand_contacts_per_fibre_at_every_block": 2,
            "minimum_declared_support_contacts_per_fibre_at_every_block": 2,
            "maximum_isolated_fibre_count_at_every_block": 0,
        },
        "equilibrium_window_gates": {
            "minimum_distinct_sand_contacts_per_fibre": 3,
            "minimum_declared_support_contacts_per_fibre": 3,
            "maximum_relative_mean_stress_error": 0.02,
            "maximum_principal_stress_error": 0.03,
            "maximum_unbalanced_force": 0.05,
            "maximum_cell_volume_relative_drift": 0.005,
            "minimum_sand_contact_retention_fraction": 0.9,
            "maximum_sand_displacement_over_D50": 0.1,
            "maximum_sand_rattler_fraction": 0.35,
            "minimum_sand_coordination_excluding_rattlers": 3.0,
            "maximum_interobject_penetration_over_smaller_radius": 0.02,
            "maximum_fibre_fibre_real_interaction_count": 0,
            "maximum_intraclump_real_interaction_count": 0,
        },
        "source_hashes": {
            "static_handoff": digest(static_handoff_path),
            "campaign_completion": digest(campaign / "completion.json"),
            "runner": digest(runner_path),
            "runner_derivation": digest(derivation_path),
            "allocation": digest(allocation_path),
        },
        "authority": {
            "development_yade_execution_authorized": True,
            "heldout_yade_execution_authorized": False,
            "reserve_execution_authorized": False,
            "legacy_revision3_candidate08_execution_authorized": False,
            "free_release_authorized": False,
            "rehydration_authorized": False,
            "deformation_authorized": False,
            "flow_authorized": False,
        },
        "claim_boundary": "Stage26g fixed-fibre temporal qualification of fresh four-support cage geometries only; no release, rehydration, deformation, flow, permeability, migration, or production result.",
    }
    design_path = output / "resolved_design.json"
    write_json(design_path, design)
    trials = []
    for index in allocation["development"]:
        trials.append(
            {
                "trial_id": f"stage26f_cage_candidate_{index:02d}_development",
                "candidate_index": index,
                "fibre_count": 2,
                "minimum_support_degree": 4,
                "placement": str(normalized[index]).replace("\\", "/"),
                "placement_sha256": digest(normalized[index]),
                "record_type": "development_capture",
                "stage26g_role": "development_capture",
            }
        )
    sources = {
        "expected_yade_version": base["sources"]["expected_yade_version"],
        "stage25_checkpoint": base["sources"]["stage25_checkpoint"],
        "stage25_checkpoint_sha256": base["sources"]["stage25_checkpoint_sha256"],
        "network_export_completion": base["sources"]["network_export_completion"],
        "network_export_completion_sha256": base["sources"]["network_export_completion_sha256"],
        "common": base["sources"]["common"],
        "common_sha256": base["sources"]["common_sha256"],
        "stage26d_adaptive_common": base["sources"]["stage26d_adaptive_common"],
        "stage26d_adaptive_common_sha256": base["sources"]["stage26d_adaptive_common_sha256"],
        "capture_common": base["sources"]["capture_common"],
        "capture_common_sha256": base["sources"]["capture_common_sha256"],
        "capture_runner": str(runner_path).replace("\\", "/"),
        "capture_runner_sha256": digest(runner_path),
        "runner_derivation": str(derivation_path).replace("\\", "/"),
        "runner_derivation_sha256": digest(derivation_path),
        "stage26f_static_handoff": str(static_handoff_path).replace("\\", "/"),
        "stage26f_static_handoff_sha256": digest(static_handoff_path),
        "stage26g_resolved_design": str(design_path).replace("\\", "/"),
        "stage26g_resolved_design_sha256": digest(design_path),
    }
    execution = {
        "schema": "lbs.stage26g-development-fixed-cage-capture-execution.v1",
        "status": "authorized_stage26g_fixed_capture",
        "authority": {
            "capture_yade_execution_authorized": True,
            "heldout_execution_authorized": False,
            "reload_verification_execution_authorized": False,
            "two_fibre_free_release_authorized": False,
            "legacy_revision3_candidate08_execution_authorized": False,
            "flow_execution_authorized": False,
            "deformation_authorized": False,
            "production_parametric_study_authorized": False,
        },
        "sources": sources,
        "candidate_generation": base["candidate_generation"],
        "network_export": base["network_export"],
        "frozen_physics": base["frozen_physics"],
        "capture_protocol": design["temporal_protocol"] | {
            "maximum_strain_rate_s_inv": base["capture_protocol"]["maximum_strain_rate_s_inv"],
            "save_on_first_qualifying_window_only": True,
        },
        "adaptive_equilibration": {
            "maximum_blocks": design["temporal_protocol"]["maximum_blocks"],
            "minimum_blocks_before_equilibrium_window": design["temporal_protocol"]["minimum_blocks_before_window"],
            "required_consecutive_passing_blocks": design["temporal_protocol"]["required_consecutive_passing_blocks"],
        },
        "continuous_engagement_gates": design["engagement_gates"],
        "equilibrium_window_gates": design["equilibrium_window_gates"],
        "trials": trials,
        "claim_boundary": design["claim_boundary"],
    }
    execution_path = output / "development_execution.json"
    write_json(execution_path, execution)
    manifest = {
        "schema": "lbs.stage26g-development-design-manifest.v1",
        "passed": True,
        "resolved_design_sha256": digest(design_path),
        "development_execution_sha256": digest(execution_path),
        "allocation_sha256": digest(allocation_path),
        "normalized_placement_hashes": {str(index): digest(path) for index, path in normalized.items()},
        "builder_sha256": digest(Path(__file__)),
    }
    write_json(output / "design_manifest.json", manifest)
    print(json.dumps({"passed": True, "design_sha256": digest(design_path), "execution_sha256": digest(execution_path), "manifest_sha256": digest(output / "design_manifest.json")}, sort_keys=True))


if __name__ == "__main__":
    main()
