#!/usr/bin/env python3
"""Fail-closed evaluation of the Stage26k fixed-fibre co-compaction pilot."""

from __future__ import annotations

import argparse, csv, hashlib, json
from datetime import datetime, timezone
from pathlib import Path


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load(path):
    with Path(path).open("r", encoding="utf-8") as stream:
        return json.load(stream)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--config", type=Path, required=True)
    p.add_argument("--run-dir", type=Path, required=True)
    p.add_argument("--output-dir", type=Path, required=True)
    a = p.parse_args()
    cfg, result, completion = load(a.config), load(a.run_dir / "result.json"), load(a.run_dir / "completion.json")
    history_path = a.run_dir / "cocompaction_history.csv"
    assert cfg["schema"] == "lbs.stage26k-loose-state-exact-fibre-cocompaction-pilot-config.v1"
    assert result["passed"] is True and completion["passed"] is True
    assert result["qualified"] is False and completion["qualified"] is False
    assert not (a.run_dir / "failure.json").exists()
    assert completion["result_sha256"] == sha256(a.run_dir / "result.json")
    assert result["artifacts"]["history_sha256"] == sha256(history_path)
    assert result["source_hashes"]["config"] == sha256(a.config)
    assert result["source_hashes"]["runner"] == cfg["sources"]["runner_sha256"]
    assert result["source_hashes"]["stage25_checkpoint"] == cfg["sources"]["stage25_checkpoint_sha256"]
    assert result["exact_sand_radii_unchanged"] is True and result["exact_fibre_geometry_unchanged"] is True
    assert result["artifacts"]["state_sha256"] is None and completion["state_sha256"] is None
    with history_path.open("r", encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == result["blocks_executed"] == 1400
    terminal = result["terminal"]
    assert json.loads(rows[-1]["distinct_sand_contacts_by_fibre"]) == terminal["distinct_sand_contacts_by_fibre"]
    healthy = all(result["terminal_checks"][name] for name in (
        "finite_state", "mean_stress", "principal_stress", "normalized_kinetic_energy", "overlap",
        "void_ratio", "sand_coordination", "sand_rattlers", "sand_particle_count", "exact_geometry",
        "no_fibre_fibre_contact", "no_intraclump_contact", "no_isolated_fibre",
    ))
    assert healthy is True
    assert result["terminal_checks"]["fibre_contacts"] is False
    assert terminal["distinct_sand_contacts_by_fibre"] == [2, 2]
    assert terminal["sand_sand_real_contact_count"] == 347
    assert terminal["relative_mean_stress_error"] < 0.001
    evaluation = {
        "schema": "lbs.stage26k-loose-state-exact-fibre-cocompaction-pilot-evaluation.v1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "passed": True,
        "status": "healthy_sand_skeleton_but_fixed_fibre_support_failed",
        "pilot_success": False,
        "sand_skeleton_recovered": True,
        "fibre_support_qualified": False,
        "terminal_summary": {
            "mean_effective_stress_pa": terminal["mean_effective_stress_pa_compression_positive"],
            "sand_contact_count": terminal["sand_sand_real_contact_count"],
            "sand_contact_retention_fraction": terminal["sand_sand_contact_retention_fraction"],
            "sand_coordination_excluding_rattlers": terminal["sand_coordination_excluding_degree_lt2_rattlers"],
            "sand_rattler_fraction": terminal["sand_rattler_fraction_degree_lt2_iterative"],
            "sand_skeleton_void_ratio": terminal["sand_skeleton_void_ratio"],
            "unbalanced_force": terminal["unbalanced_force"],
            "fibre_contacts": terminal["distinct_sand_contacts_by_fibre"],
        },
        "finding": (
            "Loose-state co-compaction rebuilt the 100 Pa sand skeleton with near-reference contact count, "
            "but fixed fibres did not acquire the required three contacts each."
        ),
        "mechanical_interpretation": (
            "The prior sand-network collapse is solved. Persistent fibre support now depends on allowing fibres "
            "to translate and rotate with the forming fabric rather than holding their loose-state pivots fixed."
        ),
        "next_mechanics_hypothesis": "repeat loose-state co-compaction with dynamically mobile rigid fibres and bounded-motion guards",
        "source_hashes": {"config": sha256(a.config), "result": sha256(a.run_dir / "result.json"),
                          "completion": sha256(a.run_dir / "completion.json"), "history": sha256(history_path),
                          "evaluator": sha256(Path(__file__))},
        "authority": completion["authority"],
        "claim_boundary": result["claim_boundary"],
    }
    a.output_dir.mkdir(parents=True, exist_ok=False)
    out = a.output_dir / "evaluation.json"
    with out.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(evaluation, stream, indent=2, sort_keys=True); stream.write("\n")
    print(json.dumps({"evaluation": str(out), "evaluation_sha256": sha256(out)}, sort_keys=True))


if __name__ == "__main__": main()
