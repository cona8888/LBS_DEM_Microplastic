"""Hash-bound Stage B diagnostic runner preparation; no campaign dispatcher.

The only executable segment entry point is restricted to reference-flow
diagnostics. A separate physical-flow certificate is required before any
scaled-field transport may be implemented or promoted.
"""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "stage109_staging"), str(ROOT / "stage106_staging")]
import comparison_case_core_v1 as adapter
import verify_checkpoint_v2 as checkpoint_module

PROTOCOL = adapter.PROTOCOL
POP_RESULT = ROOT / "stage95_designs/common_admissible_population_01/results.json"
STAGE108_MANIFEST = ROOT / "stage108_runs/first_iid_fibre_2pv_01/manifest.json"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def check_hashes(mapping):
    for path, digest in mapping.items():
        if sha(path) != digest:
            raise RuntimeError(f"frozen lineage drift: {path}")


class BoundRunner(checkpoint_module.Runner):
    """Fresh-process wrapper around the Stage108-accepted checkpoint core."""
    checkpoint = None
    pause = None
    binding = ""


def prepare(seed, sample_id, shape, flow_factor, horizon_s):
    seed, sample_id, flow_factor = int(seed), int(sample_id), float(flow_factor)
    horizon_s = float(horizon_s)
    protocol = read(PROTOCOL)
    completion = read(PROTOCOL.with_name("completion.json"))
    population = read(POP_RESULT)
    stage108 = read(STAGE108_MANIFEST)
    if sha(PROTOCOL) != completion["protocol_sha256"]:
        raise RuntimeError("Stage A protocol drift")
    if sha(POP_RESULT) != protocol["input_hashes"][str(POP_RESULT)]:
        raise RuntimeError("Stage95 population result drift")
    if sha(STAGE108_MANIFEST) != protocol["input_hashes"][str(STAGE108_MANIFEST)]:
        raise RuntimeError("Stage108 manifest drift")
    check_hashes(stage108["source_hashes"])
    check_hashes(stage108["input_hashes"])
    check_hashes(population["source_hashes"])
    config, state = adapter.resolve(seed, sample_id, shape, flow_factor)
    target = config["target_mean_interstitial_velocity_m_s"]
    if not (0 < horizon_s <= protocol["observation"]["per_packing_2pv_horizon_s_by_flow_factor"][str(seed)][str(flow_factor)]):
        raise ValueError("diagnostic horizon outside frozen 2-PV observation")
    if sha(checkpoint_module.__file__) != stage108["source_hashes"][str(Path(checkpoint_module.__file__).resolve())]:
        raise RuntimeError("checkpoint runner source drift")
    case = f"s31b_n216_s{seed}_clean"
    geometry = ROOT / "stage31_designs/stage31d_replicated_nested_cpd2_geometry_20260826/geometry_01" / case / "geometry_cpd2.npz"
    flow_run = ROOT / "stage31_runs/stage31e_replicated_nested_cpd2_gpu_20260826/gpu_screen_01" / f"stage31e_{case}_cpd2"
    field = flow_run / "final_fields.npz"
    record = flow_run / "record.json"
    starts = ROOT / f"stage95_designs/common_admissible_population_01/starts_s{seed}.json"
    for path in (geometry, field, record):
        if str(path) not in population["input_hashes"] or sha(path) != population["input_hashes"][str(path)]:
            raise RuntimeError(f"selected packing/start drift: {path}")
    if str(starts) not in population["artifact_hashes"] or sha(starts) != population["artifact_hashes"][str(starts)]:
        raise RuntimeError(f"selected start-pool drift: {starts}")
    sources = dict(stage108["source_hashes"])
    sources[str(Path(adapter.__file__).resolve())] = sha(adapter.__file__)
    sources[str(Path(__file__).resolve())] = sha(__file__)
    inputs = dict(stage108["input_hashes"])
    for path in (PROTOCOL, PROTOCOL.with_name("completion.json"), POP_RESULT,
                 STAGE108_MANIFEST, geometry, field, record, starts):
        inputs[str(path)] = sha(path)
    payload = {"source_hashes": sources, "input_hashes": inputs,
               "config": config, "initial_state": state,
               "packing_seed": seed, "sample_id": sample_id,
               "shape": shape, "flow_factor": flow_factor,
               "horizon_s": horizon_s,
               "claim_class": "Stage B diagnostic only; no population release inference"}
    binding = hashlib.sha256(json.dumps(payload, sort_keys=True, allow_nan=False,
                                        separators=(",", ":")).encode()).hexdigest()
    return {**payload, "binding": binding, "target_mean_interstitial_velocity_m_s": target}


def run_reference_diagnostic_segment(spec, wall_budget_s, checkpoint=None):
    """Run only an explicitly prepared U0 diagnostic in an isolated process.

    Caller must write an immutable manifest/result/completion chain. This
    function deliberately does not dispatch a population or a scaled flow.
    """
    if spec["flow_factor"] != 1.0:
        raise RuntimeError("scaled-flow physical gate is open")
    if wall_budget_s <= 0:
        raise ValueError("positive wall budget required")
    expected = prepare(spec["packing_seed"], spec["sample_id"], spec["shape"],
                       spec["flow_factor"], spec["horizon_s"])
    if expected != spec:
        raise RuntimeError("prepared diagnostic spec drift")
    if checkpoint is not None:
        digest = hashlib.sha256(json.dumps(checkpoint["state"], sort_keys=True,
                                           allow_nan=True).encode()).hexdigest()
        if digest != checkpoint["state_sha256"]:
            raise RuntimeError("checkpoint state drift")
    BoundRunner.binding = spec["binding"]
    BoundRunner.checkpoint = checkpoint
    BoundRunner.pause = None
    return adapter.run_local(BoundRunner, spec["config"], spec["initial_state"],
                             spec["packing_seed"], spec["horizon_s"], wall_budget_s)
