"""Freeze corrected verified zero-candidate outcome."""
import hashlib,json
from datetime import datetime,timezone
from pathlib import Path
P=Path(r"C:\MATDEM_MICROPLASTIC");E=P/"stage26_evaluations/stage26b_tier1_placement_stability_revision2_20260816/placement_campaign_evaluation_02/evaluation.json";O=P/"stage26_checkpoints/stage26b_tier1_placement_stability_revision2_20260816/placement_campaign_checkpoint_01"
def d(p):
 h=hashlib.sha256()
 with p.open("rb") as f:
  for b in iter(lambda:f.read(1048576),b""):h.update(b)
 return h.hexdigest()
def main():
 if O.exists():raise RuntimeError("checkpoint exists")
 e=json.load(E.open("r",encoding="utf-8"))
 if e.get("passed") is not True:raise RuntimeError("evaluation not passed")
 for n in ("campaign_completion","candidate_index","config","prerun_checkpoint","first_evaluation","first_failure"):
  p=Path(e["evidence"][n+"_path"])
  if d(p)!=e["evidence"][n+"_sha256"]:raise RuntimeError(n+" mismatch")
 c={"schema":"lbs.stage26b-revision2-placement-campaign-checkpoint.v2","timestamp_utc":datetime.now(timezone.utc).isoformat(),"passed":True,"status":"frozen_verified_zero_candidate_outcome","outcome":e["outcome"],"evidence":dict(e["evidence"],evaluation_path=str(E),evaluation_sha256=d(E),freezer_sha256=d(Path(__file__))),"authority":e["authority"],"claim_boundary":e["claim_boundary"]};O.mkdir(parents=True);p=O/"checkpoint_manifest.json"
 with p.open("x",encoding="utf-8") as f:json.dump(c,f,indent=2,sort_keys=True,allow_nan=False);f.write("\n")
 print(json.dumps({"passed":True,"checkpoint_sha256":d(p)},sort_keys=True))
if __name__=="__main__":main()
