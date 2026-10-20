"""Read-only campaign interruption review; writes only a new C-side review.

Reuses the sealed monitor and existing independent receipts. This is not a
physical replay, complete checkpoint reconstruction, or terminal evaluation.
"""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import statistics
import psutil

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "stage219_evaluations/normal_gap_campaign_20261001"
SNAPSHOT = BASE / "monitor_20261006_review_01/results.json"
DESIGN = ROOT / "stage219_designs/normal_gap_campaign_20261001/design_01.json"
RUN = Path("D:/MATDEM_MICROPLASTIC/stage219_runs/normal_gap_campaign_20261001/run_01")
OUT = BASE / "interruption_review_20261006_01"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def run():
    require(not OUT.exists(), "Review destination must be new")
    snapshot = read(SNAPSHOT)
    require(read(SNAPSHOT.with_name("completion.json"))["results_sha256"] == sha(SNAPSHOT), "Snapshot seal")
    require(snapshot["design_sha256"] == sha(DESIGN), "Frozen design binding")
    require(not snapshot["terminal"] and not (RUN / "completion.json").exists(), "No terminal lifecycle record")
    require(not snapshot["terminal_evaluators"], "No terminal evaluator in snapshot")
    require(all(not p["alive"] and not psutil.pid_exists(p["pid"]) for p in snapshot["processes"]), "Recorded campaign processes absent")
    require(snapshot["frozen_sources_verified"] and snapshot["frozen_inputs_verified"], "Monitor source/input checks")
    require(snapshot["outstanding_snapshot"] == 0 and not snapshot["failure_markers"], "Saved records audited without reported failure markers")
    incomplete = [c for c in snapshot["cases"] if not c["complete_observation"]]
    require(len(incomplete) == 1, "Exactly one incomplete observation")
    case = incomplete[0]
    folder = RUN / case["case"]
    markers = sorted(folder.glob("segment_*.ready.json"))
    require(len(markers) == case["sealed_segments"], "No new records since snapshot")
    evidence = {str(SNAPSHOT): sha(SNAPSHOT), str(DESIGN): sha(DESIGN)}
    rates = []
    previous_stop = None
    for marker in markers[-10:]:
        ready = read(marker)
        receipt_path = marker.with_name(marker.name.replace(".ready.json", ".audit.json"))
        receipt = read(receipt_path)
        require(receipt["ready_sha256"] == sha(marker), "Receipt binds exact ready record")
        require(receipt["design_sha256"] == sha(DESIGN) and receipt["status"] == "independently_verified", "Passing bound receipt")
        require(receipt["input_checkpoint_sha256"] == ready["input_checkpoint_sha256"], "Input checkpoint digest agreement")
        index = ready["segment"]
        parent = folder / f"segment_{index-1:05d}.audit.json"
        require(receipt["previous_receipt_sha256"] == sha(parent), "Immediate receipt ancestry")
        summary = receipt["summary"]
        require(summary["passed"] and summary["steps"] == ready["steps"], "Passing saved-step accounting")
        require(previous_stop is None or summary["start_s"] == previous_stop, "Exact adjacent physical times")
        span = summary["stop_s"] - summary["start_s"]
        require(span > 0, "Positive segment duration")
        rates.append(ready["transaction_seconds"] / span)
        previous_stop = summary["stop_s"]
        evidence.update({str(marker): sha(marker), str(receipt_path): sha(receipt_path), str(parent): sha(parent)})
    require(previous_stop == case["last_verified_time_s"], "Snapshot endpoint agreement")
    remaining = case["horizon_s"] - previous_stop
    result = dict(
        reviewed_utc=datetime.now(timezone.utc).isoformat(),
        status="interrupted_incomplete_without_terminal_record",
        cause="undetermined; absent processes and stopped records do not establish the cause",
        new_trajectory_steps=0, campaign_passed=False,
        completed_observations=5, planned_observations=6,
        total_saved_steps=sum(c["declared_saved_steps"] for c in snapshot["cases"]),
        total_segments=sum(c["sealed_segments"] for c in snapshot["cases"]),
        incomplete_case=case, remaining_physical_seconds=remaining,
        completed_horizon_fraction=previous_stop/case["horizon_s"],
        recent_ten_segment_receipt_links_and_times_verified=True,
        full_checkpoint_history_reconstructed=False, independent_physics_replayed=False,
        monitor_full_raw_seal_scope="latest two segments per case; inherited receipts for earlier records",
        recent_rate_remaining_producer_hours=dict(
            minimum=min(rates)*remaining/3600,
            median=statistics.median(rates)*remaining/3600,
            maximum=max(rates)*remaining/3600,
            limitation="Local extrapolation only; excludes recovery qualification and final audit; not a runtime bound."),
        next_gate="Versioned recovery design: reconstruct complete history, verify identical split continuation, preserve old evidence and all original scientific gates, and recheck remaining resource/deadline fit before dispatch.",
        claim_boundary="Two placements at one packing/flow with numerical refinements; no population export fraction, shape ranking, flow trend or empirical validation.",
        source_sha256=sha(Path(__file__)), evidence=evidence)
    OUT.mkdir()
    (OUT / "results.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    (OUT / "completion.json").write_text(json.dumps(dict(review_completed=True, campaign_passed=False,
        results_sha256=sha(OUT / "results.json")), indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: result[k] for k in ("status", "total_saved_steps", "total_segments", "remaining_physical_seconds", "completed_horizon_fraction", "recent_rate_remaining_producer_hours")}, indent=2))


if __name__ == "__main__":
    run()
