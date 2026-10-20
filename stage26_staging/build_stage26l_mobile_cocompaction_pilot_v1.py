#!/usr/bin/env python3
"""Build the Stage26l bounded-mobile loose-state co-compaction pilot."""

from __future__ import annotations
import argparse, hashlib, json
from datetime import datetime, timezone
from pathlib import Path


def sha256(path):
    h=hashlib.sha256()
    with Path(path).open("rb") as s:
        for c in iter(lambda:s.read(1024*1024),b""):h.update(c)
    return h.hexdigest()


def load(path):
    with Path(path).open("r",encoding="utf-8") as s:return json.load(s)


def main():
    p=argparse.ArgumentParser();p.add_argument("--stage26k-config",type=Path,required=True);p.add_argument("--stage26k-evaluation",type=Path,required=True);p.add_argument("--stage26k-checkpoint",type=Path,required=True);p.add_argument("--runner",type=Path,required=True);p.add_argument("--helper",type=Path,required=True);p.add_argument("--output-dir",type=Path,required=True);a=p.parse_args()
    parent,ev,cp=load(a.stage26k_config),load(a.stage26k_evaluation),load(a.stage26k_checkpoint)
    assert parent["schema"]=="lbs.stage26k-loose-state-exact-fibre-cocompaction-pilot-config.v1"
    assert ev["passed"] is True and ev["sand_skeleton_recovered"] is True and ev["fibre_support_qualified"] is False
    assert cp["passed"] is True and cp["next_action"]=="bounded_mobile_fibre_loose_state_cocompaction_pilot"
    assert cp["source_hashes"]["evaluation"]==sha256(a.stage26k_evaluation)
    cfg=dict(parent)
    cfg.update({
        "schema":"lbs.stage26l-bounded-mobile-loose-cocompaction-pilot-config.v1",
        "timestamp_utc":datetime.now(timezone.utc).isoformat(),
        "status":"authorized_stage26l_spent_development_mobile_cocompaction_pilot",
        "physical_question":"Can dynamically mobile exact-geometry fibres acquire persistent support while the 216-sand network forms from a loose state at 100 Pa?",
        "claim_boundary":"Stage26l bounded-mobile loose-state co-compaction pilot on one spent development geometry. Exact sand radii and 50 um rigid-fibre geometry throughout. No held-out inference, flow, permeability, deformation, migration calibration, or production result.",
        "research_role":"specimen_preparation_development_pilot_not_validation",
        "trial":{"trial_id":"candidate07_loose_e4_exact_fibre_mobile_pilot","candidate_index":7,"record_type":"spent_development_mobile_cocompaction_pilot"},
        "motion_guards":{"maximum_nonaffine_translation_over_D50":0.75,"maximum_rotation_deg":120.0},
        "authority":{"mobile_cocompaction_authorized":True,"free_release_authorized":False,"heldout_execution_authorized":False,"reserve_execution_authorized":False,"flow_execution_authorized":False,"deformation_authorized":False,"production_parametric_study_authorized":False},
    })
    cfg["fibre"]=dict(parent["fibre"]);cfg["fibre"]["fixed_during_pilot"]=False
    cfg["preparation"]=dict(parent["preparation"]);cfg["preparation"]["maximum_check_blocks"]=3200
    cfg["sources"]=dict(parent["sources"])
    cfg["sources"].update({
        "stage26k_config":str(a.stage26k_config.resolve()).replace("\\","/"),"stage26k_config_sha256":sha256(a.stage26k_config),
        "stage26k_evaluation":str(a.stage26k_evaluation.resolve()).replace("\\","/"),"stage26k_evaluation_sha256":sha256(a.stage26k_evaluation),
        "stage26k_checkpoint":str(a.stage26k_checkpoint.resolve()).replace("\\","/"),"stage26k_checkpoint_sha256":sha256(a.stage26k_checkpoint),
        "runner":str(a.runner.resolve()).replace("\\","/"),"runner_sha256":sha256(a.runner),
        "helper":str(a.helper.resolve()).replace("\\","/"),"helper_sha256":sha256(a.helper),
    })
    a.output_dir.mkdir(parents=True,exist_ok=False);out=a.output_dir/"pilot_config.json"
    with out.open("x",encoding="utf-8",newline="\n") as s:json.dump(cfg,s,indent=2,sort_keys=True);s.write("\n")
    print(json.dumps({"config":str(out),"config_sha256":sha256(out)},sort_keys=True))


if __name__=="__main__":main()
