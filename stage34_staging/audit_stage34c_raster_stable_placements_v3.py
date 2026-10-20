#!/usr/bin/env python3
"""Correct the overly narrow replacement-scope assertion in Stage34C audit v2."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(r"C:\MATDEM_MICROPLASTIC")
PLACEMENT = ROOT / "stage34_designs/stage34c_cpd4_first_fragmentation_geometry_20260902/placement_search_02/placement_manifest.json"
ORIGINAL = ROOT / "stage34_designs/stage34c_cpd4_first_fragmentation_geometry_20260902/placement_search_01/placement_manifest.json"
FAILED_AUDIT = ROOT / "stage34_evaluations/stage34c_cpd4_first_fragmentation_geometry_20260902/placement_audit_02/placement_audit.json"
FAILED_COMPLETION = FAILED_AUDIT.parent / "completion.json"
OUTPUT = ROOT / "stage34_evaluations/stage34c_cpd4_first_fragmentation_geometry_20260902/placement_audit_03"
PACKINGS = ("n216_s1", "n216_s2")
BLOCKS = ("A", "B")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def level_faces(manifest: dict, packing: str, block: str, child_rank: int) -> set[int]:
    return {
        int(row["face_index"])
        for row in manifest["packings"][packing]["blocks"][block]["anchors"]
        if int(row["child_rank"]) == child_rank
    }


def main() -> int:
    if OUTPUT.exists():
        raise FileExistsError(f"refusing to overwrite immutable corrected audit: {OUTPUT}")
    placement, original, failed, failed_completion = map(load, (PLACEMENT, ORIGINAL, FAILED_AUDIT, FAILED_COMPLETION))
    prior_checks = dict(failed["checks"])
    prior_failed = sorted(name for name, value in prior_checks.items() if not value)

    unchanged_blocks = True
    for packing in PACKINGS:
        for block in BLOCKS:
            if (packing, block) == ("n216_s1", "B"):
                continue
            unchanged_blocks &= all(level_faces(placement, packing, block, rank) == level_faces(original, packing, block, rank) for rank in (1, 2, 3))

    packing, block = "n216_s1", "B"
    original_seed = level_faces(original, packing, block, 1)
    selected_seed = level_faces(placement, packing, block, 1)
    original_round2 = level_faces(original, packing, block, 2)
    selected_round2 = level_faces(placement, packing, block, 2)
    original_round3 = level_faces(original, packing, block, 3)
    selected_round3 = level_faces(placement, packing, block, 3)
    promoted = selected_round2 - original_round2
    demoted = original_round2 - selected_round2
    state = placement["packings"][packing]["blocks"][block]
    corrected_scope = (
        selected_seed == original_seed
        and len(promoted) == 1
        and len(demoted) == 1
        and promoted == (original_round3 - selected_round3)
        and demoted == (selected_round3 - original_round3)
        and (selected_round2 | selected_round3) == (original_round2 | original_round3)
        and int(state["round2_rank"]) == 2
        and int(state["round3_rank"]) == 1
        and state["reused_original_round2"] is False
        and state["reused_original_round3"] is False
    )

    checks = {
        "failed_audit_is_hash_bound": sha(FAILED_AUDIT) == failed_completion.get("placement_audit_sha256"),
        "failed_audit_was_fail_closed": failed.get("passed") is False and failed_completion.get("passed") is False,
        "prior_failure_was_only_scope_assertion": prior_failed == ["only_failed_s1B_round2_was_replaced"],
        "all_other_independent_v2_checks_passed": all(value for name, value in prior_checks.items() if name != "only_failed_s1B_round2_was_replaced"),
        "three_blocks_and_all_seed_levels_unchanged": unchanged_blocks and selected_seed == original_seed,
        "s1B_exact_one_for_one_nested_level_swap": corrected_scope,
        "s1B_total_twelve_face_set_unchanged": (
            selected_seed | selected_round2 | selected_round3
            == original_seed | original_round2 | original_round3
        ),
        "promoted_face_exact": promoted == {29278},
        "demoted_face_exact": demoted == {37231},
        "selected_raster_screens_still_all_pass": all(
            block_row["raster_screen"][level]["passed"]
            for packing_row in placement["packings"].values()
            for block_row in packing_row["blocks"].values()
            for level in ("frag2", "frag3")
        ),
        "placement_and_original_exist": PLACEMENT.is_file() and ORIGINAL.is_file(),
    }
    passed = all(checks.values())
    status = "passed_corrected_placement_audit_raster_build_authorized" if passed else "failed_corrected_placement_audit_fail_closed"
    authority = {
        "raster_geometry_build": passed,
        "independent_raster_audit": False,
        "gpu_flow_execution": False,
        "mechanics_or_coupling": False,
    }
    audit = {
        "schema": "lbs.stage34c-raster-stable-fragment-placement-audit.v3",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "passed": passed,
        "status": status,
        "checks": checks,
        "correction": {
            "superseded_assertion": "only the s1/B round-2 face set changes while round 3 remains exact",
            "verified_assertion": "only s1/B changes; its total twelve-face set is preserved with a one-for-one round-2/round-3 level swap",
            "promoted_to_round2_face_indices": sorted(promoted),
            "demoted_to_round3_face_indices": sorted(demoted),
        },
        "source_bindings": {
            "placement": {"path": str(PLACEMENT.resolve()), "sha256": sha(PLACEMENT)},
            "original_placement": {"path": str(ORIGINAL.resolve()), "sha256": sha(ORIGINAL)},
            "failed_audit_v2": {"path": str(FAILED_AUDIT.resolve()), "sha256": sha(FAILED_AUDIT)},
            "failed_completion_v2": {"path": str(FAILED_COMPLETION.resolve()), "sha256": sha(FAILED_COMPLETION)},
            "auditor": {"path": str(Path(__file__).resolve()), "sha256": sha(Path(__file__).resolve())},
        },
        "authority": authority,
        "claim_boundary": placement["claim_boundary"],
    }
    OUTPUT.mkdir(parents=True)
    audit_path = OUTPUT / "placement_audit.json"
    audit_path.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    completion = {
        "schema": audit["schema"] + ".completion",
        "passed": passed,
        "status": status,
        "placement_audit_sha256": sha(audit_path),
        "checks": checks,
        "authority": authority,
    }
    (OUTPUT / "completion.json").write_text(json.dumps(completion, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "passed": passed,
        "status": status,
        "failed_checks": [name for name, value in checks.items() if not value],
        "promoted": sorted(promoted),
        "demoted": sorted(demoted),
    }, indent=2, sort_keys=True))
    return 0 if passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
