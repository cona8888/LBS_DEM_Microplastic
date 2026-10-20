"""Freeze audited Revision-3 placement design."""
import hashlib,json
from datetime import datetime,timezone
from pathlib import Path
P=Path(r"C:\MATDEM_MICROPLASTIC");E=P/"stage26_evaluations/stage26b_revision3_joint_placement_20260816/design_evaluation_01/evaluation.json";O=P/"stage26_checkpoints/stage26b_revision3_joint_placement_20260816/design_checkpoint_01"
def d(p):
 h=hashlib.sha256();h.update(p.read_bytes());return h.hexdigest()
def main():
 if O.exists():raise RuntimeError("checkpoint exists")
 e=json.load(E.open("r",encoding="utf-8"))
 if e.get("passed") is not True:raise RuntimeError("audit failed")
 for n in ("design","revision2_campaign_checkpoint","network_checkpoint"):
  p=Path(e["evidence"][n+"_path"])
  if d(p)!=e["evidence"][n+"_sha256"]:raise RuntimeError(n+" mismatch")
 c={"schema":"lbs.stage26b-revision3-joint-placement-design-checkpoint.v1","timestamp_utc":datetime.now(timezone.utc).isoformat(),"passed":True,"status":"frozen_revision3_algorithm_only_design","evidence":dict(e["evidence"],evaluation_path=str(E),evaluation_sha256=d(E),freezer_sha256=d(Path(__file__))),"authority":e["authority"],"claim_boundary":e["claim_boundary"]};O.mkdir(parents=True);p=O/"checkpoint_manifest.json"
 with p.open("x",encoding="utf-8") as f:json.dump(c,f,indent=2,sort_keys=True,allow_nan=False);f.write("\n")
 print(json.dumps({"passed":True,"checkpoint_sha256":d(p)},sort_keys=True))
if __name__=="__main__":main()
