#!/usr/bin/env python3
"""Build Stage26m staged-release loose-state co-compaction pilot."""
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
 p=argparse.ArgumentParser();p.add_argument("--stage26l-config",type=Path,required=True);p.add_argument("--stage26l-evaluation",type=Path,required=True);p.add_argument("--stage26l-checkpoint",type=Path,required=True);p.add_argument("--runner",type=Path,required=True);p.add_argument("--helper",type=Path,required=True);p.add_argument("--output-dir",type=Path,required=True);a=p.parse_args();parent,ev,cp=load(a.stage26l_config),load(a.stage26l_evaluation),load(a.stage26l_checkpoint)
 assert ev["passed"] is True and ev["pilot_success"] is False and ev["sand_skeleton_recovered"] is True
 assert cp["passed"] is True and cp["next_action"]=="staged_release_after_sand_network_onset_pilot" and cp["source_hashes"]["evaluation"]==sha(a.stage26l_evaluation)
 cfg=dict(parent);cfg.update({"schema":"lbs.stage26m-staged-release-cocompaction-pilot-config.v1","timestamp_utc":datetime.now(timezone.utc).isoformat(),"status":"authorized_stage26m_spent_development_staged_release_pilot","physical_question":"Can exact fibres become mechanically caged if held only through contact-free compression and released as the sand network begins carrying stress?","claim_boundary":"Stage26m staged-release co-compaction pilot on one spent development geometry. Fixed positioning is an initialization control only; acceptance requires subsequent mobile equilibrium. Exact radii and rigid-fibre geometry throughout. No held-out, flow, permeability, deformation, or production result.","trial":{"trial_id":"candidate07_staged_release_mobile_pilot","candidate_index":7,"record_type":"spent_development_staged_release_pilot"},"release_protocol":{"minimum_sand_contact_count":200,"minimum_mean_effective_stress_pa":20.0,"fixed_phase_maximum_blocks":1400,"mobile_phase_maximum_blocks":600,"mobile_phase_minimum_blocks":20,"required_consecutive_pass_blocks":5,"steps_per_block":1000,"mobile_newton_damping":0.5},"motion_guards":{"maximum_nonaffine_translation_over_D50":0.5,"maximum_rotation_deg":180.0},"authority":{"staged_release_cocompaction_authorized":True,"heldout_execution_authorized":False,"reserve_execution_authorized":False,"flow_execution_authorized":False,"deformation_authorized":False,"production_parametric_study_authorized":False}})
 cfg["fibre"]=dict(parent["fibre"]);cfg["fibre"]["fixed_during_initialization_only"]=True;cfg["fibre"].pop("fixed_during_pilot",None)
 cfg["sources"]=dict(parent["sources"]);cfg["sources"].update({"stage26l_config":str(a.stage26l_config.resolve()).replace("\\","/"),"stage26l_config_sha256":sha(a.stage26l_config),"stage26l_evaluation":str(a.stage26l_evaluation.resolve()).replace("\\","/"),"stage26l_evaluation_sha256":sha(a.stage26l_evaluation),"stage26l_checkpoint":str(a.stage26l_checkpoint.resolve()).replace("\\","/"),"stage26l_checkpoint_sha256":sha(a.stage26l_checkpoint),"runner":str(a.runner.resolve()).replace("\\","/"),"runner_sha256":sha(a.runner),"helper":str(a.helper.resolve()).replace("\\","/"),"helper_sha256":sha(a.helper)})
 a.output_dir.mkdir(parents=True,exist_ok=False);out=a.output_dir/"pilot_config.json"
 with out.open("x",encoding="utf-8",newline="\n") as s:json.dump(cfg,s,indent=2,sort_keys=True);s.write("\n")
 print(json.dumps({"config":str(out),"config_sha256":sha(out)},sort_keys=True))
if __name__=="__main__":main()
