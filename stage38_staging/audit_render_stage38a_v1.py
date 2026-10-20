import argparse
import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "stage38_designs/stage38_normal_lubrication_contract_v1.json"
NORMAL = ROOT / "stage38_evaluations/normal_lubrication_verification_01/results.json"
POLY = ROOT / "stage38_evaluations/normal_lubrication_polydisperse_01/results.json"
TRAJECTORY = ROOT / "stage38_evaluations/lubricated_trajectory_verification_02/results.json"
FAILED_PAIR = ROOT / "stage38_evaluations/pair_operator_v2_verification_01/results.json"
FAILED_AREA = ROOT / "stage38_evaluations/pair_operator_v3_smoke_01/results.json"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def hashes_current(record, field):
    return all(Path(path).exists() and sha(path) == digest for path, digest in record[field].items())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=False)
    normal = json.loads(NORMAL.read_text())
    poly = json.loads(POLY.read_text())
    trajectory = json.loads(TRAJECTORY.read_text())
    failed_pair = json.loads(FAILED_PAIR.read_text())
    failed_area = json.loads(FAILED_AREA.read_text())
    checks = {
        "normal_primitive_passed": normal["passed"],
        "polydisperse_extension_passed": poly["passed"],
        "curved_contact_trajectory_passed": trajectory["passed"],
        "normal_sources_unchanged": hashes_current(normal, "source_hashes"),
        "polydisperse_sources_unchanged": hashes_current(poly, "source_hashes"),
        "trajectory_sources_unchanged": hashes_current(trajectory, "source_hashes"),
        "failed_global_pair_preserved": not failed_pair["passed"],
        "failed_equal_area_pair_preserved": not failed_area["passed"],
        "contract_exists": CONTRACT.exists(),
    }
    rows = normal["canonical_rows"]
    epsilon = np.array([row["gap_over_body_radius"] for row in rows])
    exact = np.array([row["exact_factor"] for row in rows])
    matched = np.array([row["matched_factor"] for row in rows])
    error = np.array([row["relative_error"] for row in rows]) * 100
    event_times = np.array(trajectory["event_times_s"])
    fractions = np.array([row["displacement_fraction"] for row in trajectory["rows"]])

    fig, axes = plt.subplots(1, 3, figsize=(12.0, 3.6))
    axes[0].loglog(epsilon, exact, color="#183B56", lw=2.2, label="Brenner exact")
    axes[0].loglog(epsilon, matched, "--", color="#E45756", lw=2, label="matched model")
    axes[0].set_xlabel("gap / mobile-sphere radius")
    axes[0].set_ylabel("normal drag factor")
    axes[0].legend(frameon=False, fontsize=8)
    axes[0].grid(alpha=0.2, which="both")
    axes[1].semilogx(epsilon, error, color="#F3A712", lw=2.2)
    axes[1].axhline(4, color="#8B1E3F", ls="--", lw=1.5, label="4% gate")
    axes[1].set_xlabel("gap / mobile-sphere radius")
    axes[1].set_ylabel("relative error (%)")
    axes[1].set_ylim(0, 4.5)
    axes[1].legend(frameon=False, fontsize=8)
    axes[1].grid(alpha=0.2, which="both")
    order = np.argsort(fractions)
    axes[2].plot(fractions[order], event_times[order], "o-", color="#2A9D8F", lw=2)
    axes[2].set_xlabel("max displacement / minor radius")
    axes[2].set_ylabel("curved-contact exit time")
    axes[2].grid(alpha=0.2)
    fig.suptitle("Stage38a: verified normal lubrication only", weight="bold")
    fig.tight_layout()
    figure = out / "stage38a_normal_lubrication_verification.png"
    fig.savefig(figure, dpi=220, bbox_inches="tight")
    plt.close(fig)

    result = {
        "completed": True,
        "passed": all(checks.values()),
        "checks": {key: bool(value) for key, value in checks.items()},
        "headline": {
            "canonical_error_max": normal["values"]["brenner_matched_relative_error_max"],
            "trajectory_fine_medium_shift": trajectory["fine_medium_event_time_relative_shift"],
        },
        "accepted_scope": "positive normal lubrication excess plus unilateral/Coulomb contact for fixed polydisperse spherical grains",
        "not_qualified": [
            "full six-degree-of-freedom pair resistance",
            "tangential or rotational lubrication",
            "finite-Re outer drag and particle inertia",
            "roughness or contact-friction calibration",
            "physical PET release fraction"
        ],
        "input_hashes": {str(path.resolve()): sha(path) for path in [CONTRACT, NORMAL, POLY, TRAJECTORY, FAILED_PAIR, FAILED_AREA]},
        "figure_sha256": sha(figure),
    }
    (out / "audit.json").write_text(json.dumps(result, indent=2))
    (out / "REPORT.md").write_text(
        "# Stage38a normal-lubrication verification\n\n"
        f"Status: **{'PASS' if result['passed'] else 'FAIL'}**. The matched normal correction has a maximum "
        f"{100*result['headline']['canonical_error_max']:.3f}% error against Brenner's exact sphere-plane result, "
        f"and the curved two-grain contact test has a {100*result['headline']['trajectory_fine_medium_shift']:.4f}% "
        "fine-to-medium event-time shift.\n\n"
        "This accepts only normal squeeze resistance below the Stage37 clearance cutoff. The failed global pair "
        "operators remain evidence that tangential/rotational near-contact resistance is not yet qualified. "
        "No physical PET release fraction is reported.\n"
    )
    print(json.dumps({"passed": result["passed"], "checks": result["checks"], "headline": result["headline"]}, indent=2))


if __name__ == "__main__":
    main()
