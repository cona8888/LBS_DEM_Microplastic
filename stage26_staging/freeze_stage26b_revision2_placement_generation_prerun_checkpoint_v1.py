"""Freeze the exact offline placement-generation execution authority."""

import hashlib, json
from datetime import datetime, timezone
from pathlib import Path

PROJECT = Path(r"C:\MATDEM_MICROPLASTIC")
EVALUATION = PROJECT / "stage26_evaluations" / "stage26b_tier1_placement_stability_revision2_20260816" / "placement_generation_prerun_evaluation_01" / "evaluation.json"
OUTPUT = PROJECT / "stage26_checkpoints" / "stage26b_tier1_placement_stability_revision2_20260816" / "placement_generation_prerun_checkpoint_01"

def digest(path):
    value=hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024*1024),b""): value.update(block)
    return value.hexdigest()

def main():
    if OUTPUT.exists(): raise RuntimeError("immutable placement pre-run checkpoint already exists")
    evaluation=json.load(EVALUATION.open("r",encoding="utf-8-sig"))
    if evaluation.get("passed") is not True or evaluation.get("status") != "passed_exact_offline_placement_generation_prerun": raise RuntimeError("placement pre-run evaluation is not accepted")
    for name in ("config","generator","source_checkpoint","network"):
        path=Path(evaluation["evidence"][name+"_path"])
        if digest(path)!=evaluation["evidence"][name+"_sha256"]: raise RuntimeError(name+" hash mismatch")
    checkpoint={"schema":"lbs.stage26b-revision2-placement-generation-prerun-checkpoint.v1","timestamp_utc":datetime.now(timezone.utc).isoformat(),"passed":True,"status":"frozen_exact_offline_placement_generation_authority","evidence":dict(evaluation["evidence"],evaluation_path=str(EVALUATION),evaluation_sha256=digest(EVALUATION),freezer_sha256=digest(Path(__file__))),"frozen_execution":evaluation["frozen_execution"],"authority":evaluation["authority"],"claim_boundary":evaluation["claim_boundary"]}
    OUTPUT.mkdir(parents=True); path=OUTPUT/"checkpoint_manifest.json"
    with path.open("x",encoding="utf-8") as stream: json.dump(checkpoint,stream,indent=2,sort_keys=True,allow_nan=False); stream.write("\n")
    print(json.dumps({"passed":True,"checkpoint_sha256":digest(path)},sort_keys=True))

if __name__=="__main__": main()
