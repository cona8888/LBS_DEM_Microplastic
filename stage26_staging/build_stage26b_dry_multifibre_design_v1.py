"""Build and audit the design-only Stage26b dry multi-fibre ladder."""

import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


PROJECT = Path(r"C:\MATDEM_MICROPLASTIC")
CONFIG = PROJECT / "stage26_staging" / "stage26b_dry_multifibre_design_v1.json"
CONTRACT = PROJECT / "stage26_staging" / "STAGE26B_RESEARCH_CONTRACT.md"
OUTPUT = PROJECT / "stage26_designs" / "stage26b_dry_multifibre_20260813" / "design_01"


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_json(path):
    with path.open("r", encoding="utf-8-sig") as stream:
        return json.load(stream)


def check_source(path_text, expected):
    path = Path(path_text)
    if not path.is_file():
        raise RuntimeError("missing source: " + str(path))
    actual = sha256(path)
    if actual != expected:
        raise RuntimeError("source hash mismatch: " + str(path))
    return actual


def mass_percent(count, sand_mass, fibre_mass):
    return 100.0 * count * fibre_mass / (sand_mass + count * fibre_mass)


def main():
    if OUTPUT.exists():
        raise RuntimeError("immutable Stage26b design already exists")
    cfg = load_json(CONFIG)
    source_hashes = {}
    for key, value in cfg["sources"].items():
        if not key.endswith("_sha256"):
            hash_key = key + "_sha256"
            if hash_key in cfg["sources"]:
                source_hashes[key] = check_source(value, cfg["sources"][hash_key])

    if cfg["authority"]["multi_fibre_yade_execution_authorized"]:
        raise RuntimeError("design-only authority violated")
    if any(cfg["authority"][key] for key in (
        "flow_execution_authorized",
        "transient_two_way_coupling_authorized",
        "deformation_coupled_flow_authorized",
        "production_parametric_study_authorized",
    )):
        raise RuntimeError("forbidden downstream authority enabled")

    sand_mass = cfg["mass_basis"]["frozen_sand_mass_kg"]
    fibre_mass = cfg["mass_basis"]["single_fibre_mass_kg"]
    blocks = cfg["design"]["placement_blocks_by_count"]
    tiers = {count: tier for tier, counts in enumerate(cfg["design"]["adaptive_tiers"], start=1) for count in counts}
    block_index = {"A": 1, "B": 2, "C": 3}
    rows = []
    run_order = 0
    for count in cfg["design"]["new_execution_counts"]:
        for block in blocks[str(count)]:
            run_order += 1
            seed = cfg["design"]["placement_seed_base"] + 100 * count + block_index[block]
            rows.append({
                "run_order": run_order,
                "adaptive_tier": tiers[count],
                "case_id": f"stage26b_f{count:03d}_{block}",
                "fibre_count": count,
                "dry_mass_percent": mass_percent(count, sand_mass, fibre_mass),
                "orientation_regime": cfg["design"]["orientation_regime"],
                "placement_block": block,
                "placement_seed": seed,
                "source_state": "frozen_stage25_common_baseline",
                "execution_status": "not_authorized",
            })

    expected_pairs = {(count, block) for count in cfg["design"]["new_execution_counts"] for block in blocks[str(count)]}
    actual_pairs = {(row["fibre_count"], row["placement_block"]) for row in rows}
    checks = {
        "source_hashes_match": len(source_hashes) == 4,
        "nine_unique_candidate_cases": len(rows) == len({row["case_id"] for row in rows}) == 9,
        "factorial_rows_complete": actual_pairs == expected_pairs,
        "all_cases_use_common_stage25_baseline": all(row["source_state"] == "frozen_stage25_common_baseline" for row in rows),
        "placement_seeds_unique": len(rows) == len({row["placement_seed"] for row in rows}),
        "concentrations_strictly_increase_by_count": all(
            mass_percent(a, sand_mass, fibre_mass) < mass_percent(b, sand_mass, fibre_mass)
            for a, b in zip(cfg["design"]["all_fibre_counts"], cfg["design"]["all_fibre_counts"][1:])
        ),
        "maximum_concentration_below_0p1_percent": mass_percent(21, sand_mass, fibre_mass) < 0.1,
        "no_execution_authority": not cfg["authority"]["multi_fibre_yade_execution_authorized"],
        "no_flow_or_coupling_authority": not any(cfg["authority"][key] for key in (
            "flow_execution_authorized", "transient_two_way_coupling_authorized",
            "deformation_coupled_flow_authorized", "production_parametric_study_authorized")),
    }
    if not all(checks.values()):
        raise RuntimeError("Stage26b design audit failed: " + repr(checks))

    OUTPUT.mkdir(parents=True)
    csv_path = OUTPUT / "design_matrix.csv"
    with csv_path.open("x", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    concentrations = [
        {"fibre_count": count, "dry_mass_percent": mass_percent(count, sand_mass, fibre_mass),
         "role": "inherited_reference" if count in cfg["design"]["inherited_reference_counts"] else "new_candidate"}
        for count in cfg["design"]["all_fibre_counts"]
    ]
    resolved = {
        "schema": "lbs.stage26b-dry-multifibre-resolved-design.v1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "passed": True,
        "status": "frozen_design_only",
        "config_path": str(CONFIG),
        "config_sha256": sha256(CONFIG),
        "contract_path": str(CONTRACT),
        "contract_sha256": sha256(CONTRACT),
        "builder_path": str(Path(__file__)),
        "builder_sha256": sha256(Path(__file__)),
        "source_hashes": source_hashes,
        "concentration_ladder": concentrations,
        "candidate_case_count": len(rows),
        "design_matrix_path": str(csv_path),
        "design_matrix_sha256": sha256(csv_path),
        "checks": checks,
        "decision_rule": cfg["design"]["highest_supported_concentration_rule"],
        "authority": cfg["authority"],
        "next_required_handoff": "Independent audit and explicit frozen authorization before placement generation or YADE execution.",
    }
    resolved_path = OUTPUT / "resolved_design.json"
    with resolved_path.open("x", encoding="utf-8") as stream:
        json.dump(resolved, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
    print(json.dumps({"passed": True, "candidate_cases": len(rows), "resolved_design_sha256": sha256(resolved_path)}, sort_keys=True))


if __name__ == "__main__":
    main()
