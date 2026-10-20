#!/usr/bin/env python3
"""Evaluate Stage26l design-02 and bind the design-01 resource ceiling."""
from __future__ import annotations
import argparse,csv,hashlib,json
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
 p=argparse.ArgumentParser();p.add_argument("--config",type=Path,required=True);p.add_argument("--run-dir",type=Path,required=True);p.add_argument("--resource-record",type=Path,required=True);p.add_argument("--output-dir",type=Path,required=True);a=p.parse_args()
 cfg=load(a.config);r=load(a.run_dir/"result.json");c=load(a.run_dir/"completion.json");rr=load(a.resource_record);hp=a.run_dir/"mobile_cocompaction_history.csv"
 assert cfg["schema"]=="lbs.stage26l-bounded-mobile-loose-cocompaction-pilot-config.v1" and cfg["preparation"]["maximum_check_blocks"]==3200
 assert rr["status"]=="inconclusive_precontact_resource_ceiling" and rr["physics_failure"] is False
 assert r["passed"] is True and c["passed"] is True and r["status"]=="mobile_guard_failed" and r["qualified"] is False
 assert not (a.run_dir/"failure.json").exists();assert c["result_sha256"]==sha(a.run_dir/"result.json");assert r["artifacts"]["history_sha256"]==sha(hp);assert r["source_hashes"]["config"]==sha(a.config);assert r["source_hashes"]["runner"]==cfg["sources"]["runner_sha256"]
 assert r["terminal_checks"]["bounded_rotation"] is False and r["terminal_checks"]["bounded_translation"] is True
 assert r["terminal"]["maximum_fibre_rotation_deg"]>120 and r["terminal"]["maximum_fibre_translation_over_D50"]<.12
 assert r["terminal"]["distinct_sand_contacts_by_fibre"]==[0,0] and r["terminal"]["sand_sand_real_contact_count"]==351
 assert r["terminal"]["relative_mean_stress_error"]<.002 and r["terminal"]["sand_coordination_excluding_degree_lt2_rattlers"]>4
 with hp.open("r",encoding="utf-8",newline="") as s:rows=list(csv.DictReader(s))
 assert len(rows)==r["blocks_executed"]==1972
 ev={"schema":"lbs.stage26l-mobile-cocompaction-pilot-evaluation.v1","timestamp_utc":datetime.now(timezone.utc).isoformat(),"passed":True,"status":"healthy_sand_but_unbounded_tumbling_without_persistent_fibre_support","pilot_success":False,"sand_skeleton_recovered":True,"fibre_support_qualified":False,"finding":"After contact onset the mobile rigid fibres rotated rapidly and did not retain sampled sand contacts; the 120 degree guard stopped the pilot while the sand skeleton remained healthy.","mechanical_interpretation":"Fully freeing lightweight fibres throughout isotropic compression lets them tumble through transient pore openings instead of becoming caged.","next_mechanics_hypothesis":"hold fibres through the contact-free phase, then release them when the sand network and confining stress begin to form","terminal_summary":{"stress_pa":r["terminal"]["mean_effective_stress_pa_compression_positive"],"sand_contacts":351,"fibre_contacts":[0,0],"translation_over_D50":r["terminal"]["maximum_fibre_translation_over_D50"],"rotation_deg":r["terminal"]["maximum_fibre_rotation_deg"]},"source_hashes":{"config":sha(a.config),"result":sha(a.run_dir/"result.json"),"completion":sha(a.run_dir/"completion.json"),"history":sha(hp),"resource_record":sha(a.resource_record),"evaluator":sha(Path(__file__))},"authority":c["authority"],"claim_boundary":r["claim_boundary"]}
 a.output_dir.mkdir(parents=True,exist_ok=False);out=a.output_dir/"evaluation.json"
 with out.open("x",encoding="utf-8",newline="\n") as s:json.dump(ev,s,indent=2,sort_keys=True);s.write("\n")
 print(json.dumps({"evaluation":str(out),"evaluation_sha256":sha(out)},sort_keys=True))
if __name__=="__main__":main()
