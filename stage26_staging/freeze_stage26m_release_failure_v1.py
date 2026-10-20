#!/usr/bin/env python3
"""Evaluate, render, and freeze the rejected Stage26m release transient."""
from __future__ import annotations
import argparse,csv,hashlib,json
from datetime import datetime,timezone
from pathlib import Path
import matplotlib;matplotlib.use("Agg")
import matplotlib.pyplot as plt
def sha(path):
 h=hashlib.sha256()
 with Path(path).open("rb") as s:
  for c in iter(lambda:s.read(1048576),b""):h.update(c)
 return h.hexdigest()
def load(path):
 with Path(path).open("r",encoding="utf-8") as s:return json.load(s)
def dump(path,payload):
 with Path(path).open("x",encoding="utf-8",newline="\n") as s:json.dump(payload,s,indent=2,sort_keys=True);s.write("\n")
def main():
 p=argparse.ArgumentParser();p.add_argument("--config",type=Path,required=True);p.add_argument("--run-dir",type=Path,required=True);p.add_argument("--evaluation-dir",type=Path,required=True);p.add_argument("--render-dir",type=Path,required=True);p.add_argument("--checkpoint-dir",type=Path,required=True);a=p.parse_args();cfg=load(a.config);r=load(a.run_dir/"result.json");c=load(a.run_dir/"completion.json");hp=a.run_dir/"staged_release_history.csv"
 assert cfg["schema"]=="lbs.stage26m-staged-release-cocompaction-pilot-config.v1";assert r["passed"] is True and c["passed"] is True and r["qualified"] is False and r["status"]=="mobile_guard_failed";assert not (a.run_dir/"failure.json").exists();assert c["result_sha256"]==sha(a.run_dir/"result.json");assert r["artifacts"]["history_sha256"]==sha(hp);assert r["source_hashes"]["config"]==sha(a.config);assert r["terminal"]["maximum_interobject_penetration_over_smaller_radius"]>.3;assert r["terminal"]["maximum_fibre_translation_over_D50"]>2.7;assert r["terminal"]["mean_effective_stress_pa_compression_positive"]>6000
 ev={"schema":"lbs.stage26m-staged-release-pilot-evaluation.v1","timestamp_utc":datetime.now(timezone.utc).isoformat(),"passed":True,"status":"rejected_numerically_unstable_release_transient","pilot_success":False,"physical_result_accepted":False,"finding":"The fixed-to-mobile switch caused a one-block impulse: fibre translation exceeded 2.7 D50, overlap exceeded 0.32 radius, and mean stress exceeded 6 kPa.","diagnosis":"The lightweight fibre was released while carrying contact force before the timestep controller adapted from the fixed-body regime. This is a release-integration failure, not evidence of physical fibre migration.","next_action":"equilibrate_fixed_state_then_reduce_timestep_and_increase_damping_before_release","source_hashes":{"config":sha(a.config),"result":sha(a.run_dir/"result.json"),"completion":sha(a.run_dir/"completion.json"),"history":sha(hp),"freezer":sha(Path(__file__))},"authority":c["authority"],"claim_boundary":r["claim_boundary"]};a.evaluation_dir.mkdir(parents=True,exist_ok=False);ep=a.evaluation_dir/"evaluation.json";dump(ep,ev)
 with hp.open("r",encoding="utf-8",newline="") as s:rows=list(csv.DictReader(s));b=[int(x["block"]) for x in rows];stress=[float(x["mean_effective_stress_pa_compression_positive"]) for x in rows];trans=[float(x["maximum_fibre_translation_over_D50"]) for x in rows];overlap=[float(x["maximum_interobject_penetration_over_smaller_radius"]) for x in rows];contacts=[min(json.loads(x["distinct_sand_contacts_by_fibre"])) for x in rows]
 a.render_dir.mkdir(parents=True,exist_ok=False);fig,ax=plt.subplots(2,2,figsize=(13,9.5),constrained_layout=True);release=int(r["release_trigger_row"]["block"])
 for x in ax.flat:x.axvline(release,color="black",ls="--",lw=1,label="release")
 ax[0,0].plot(b,stress,color="#D95319");ax[0,0].set(xlabel="block",ylabel="mean stress (Pa)",title="Rejected stress impulse")
 ax[0,1].plot(b,trans,color="#2878B5");ax[0,1].axhline(.5,color="black",ls=":",lw=1);ax[0,1].set(xlabel="block",ylabel="translation / D50",title="Migration guard violated")
 ax[1,0].plot(b,overlap,color="#6A3D9A");ax[1,0].axhline(.05,color="black",ls=":",lw=1);ax[1,0].set(xlabel="block",ylabel="overlap / smaller radius",title="Hard overlap guard violated")
 ax[1,1].plot(b,contacts,color="#E15759");ax[1,1].axhline(3,color="black",ls=":",lw=1);ax[1,1].set(xlabel="block",ylabel="minimum contacts per fibre",title="No qualified mobile support")
 fig.suptitle("Stage26m staged release rejected as numerically unstable\nNo physical migration or mechanics claim; no held-out or flow execution",fontsize=14);image=a.render_dir/"stage26m_rejected_release_transient.png";fig.savefig(image,dpi=180,facecolor="white");plt.close(fig);rm={"schema":"lbs.stage26m-release-failure-render-manifest.v1","passed":True,"status":"rejected_transient_diagnostic_render","image":str(image).replace("\\","/"),"image_sha256":sha(image),"source_hashes":{"evaluation":sha(ep),"history":sha(hp),"renderer":sha(Path(__file__))},"claim_boundary":ev["claim_boundary"]};mp=a.render_dir/"render_manifest.json";dump(mp,rm)
 a.checkpoint_dir.mkdir(parents=True,exist_ok=False);cp={"schema":"lbs.stage26m-release-failure-checkpoint.v1","timestamp_utc":datetime.now(timezone.utc).isoformat(),"passed":True,"status":"numerically_unstable_release_rejected_and_frozen","physical_result_accepted":False,"next_action":ev["next_action"],"authority":ev["authority"],"source_hashes":{"evaluation":sha(ep),"render_manifest":sha(mp),"freezer":sha(Path(__file__))},"claim_boundary":ev["claim_boundary"]};cpp=a.checkpoint_dir/"checkpoint_manifest.json";dump(cpp,cp);print(json.dumps({"evaluation_sha256":sha(ep),"image_sha256":sha(image),"checkpoint_sha256":sha(cpp)},sort_keys=True))
if __name__=="__main__":main()
