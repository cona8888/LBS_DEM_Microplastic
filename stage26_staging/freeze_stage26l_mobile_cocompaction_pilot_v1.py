#!/usr/bin/env python3
from __future__ import annotations
import argparse,hashlib,json
from datetime import datetime,timezone
from pathlib import Path
def sha(path):
 h=hashlib.sha256()
 with Path(path).open("rb") as s:
  for c in iter(lambda:s.read(1048576),b""):h.update(c)
 return h.hexdigest()
def load(path):
 with Path(path).open("r",encoding="utf-8") as s:return json.load(s)
def main():
 p=argparse.ArgumentParser();p.add_argument("--evaluation",type=Path,required=True);p.add_argument("--render-manifest",type=Path,required=True);p.add_argument("--output-dir",type=Path,required=True);a=p.parse_args();ev=load(a.evaluation);rm=load(a.render_manifest);assert ev["passed"] is True and ev["pilot_success"] is False;assert rm["source_hashes"]["evaluation"]==sha(a.evaluation);assert all(v is False for v in ev["authority"].values())
 cp={"schema":"lbs.stage26l-mobile-cocompaction-pilot-checkpoint.v1","timestamp_utc":datetime.now(timezone.utc).isoformat(),"passed":True,"status":"mobile_tumbling_failure_evidence_frozen","pilot_success":False,"sand_skeleton_recovered":True,"mechanics_conclusion":"Fully mobile fibres tumble without retaining support during isotropic network formation.","next_action":"staged_release_after_sand_network_onset_pilot","authority":ev["authority"],"source_hashes":{"evaluation":sha(a.evaluation),"render_manifest":sha(a.render_manifest),"freezer":sha(Path(__file__))},"claim_boundary":ev["claim_boundary"]};a.output_dir.mkdir(parents=True,exist_ok=False);out=a.output_dir/"checkpoint_manifest.json"
 with out.open("x",encoding="utf-8",newline="\n") as s:json.dump(cp,s,indent=2,sort_keys=True);s.write("\n")
 print(json.dumps({"checkpoint":str(out),"checkpoint_sha256":sha(out)},sort_keys=True))
if __name__=="__main__":main()
