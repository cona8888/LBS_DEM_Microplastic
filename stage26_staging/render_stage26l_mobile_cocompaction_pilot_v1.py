#!/usr/bin/env python3
"""Render verified Stage26l mobile-fibre failure evidence."""
from __future__ import annotations
import argparse,csv,hashlib,json
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
def main():
 p=argparse.ArgumentParser();p.add_argument("--evaluation",type=Path,required=True);p.add_argument("--run-dir",type=Path,required=True);p.add_argument("--output-dir",type=Path,required=True);a=p.parse_args();ev=load(a.evaluation);hp=a.run_dir/"mobile_cocompaction_history.csv";assert sha(hp)==ev["source_hashes"]["history"]
 with hp.open("r",encoding="utf-8",newline="") as s:rows=list(csv.DictReader(s))
 b=[int(x["block"]) for x in rows];sand=[int(x["sand_sand_real_contact_count"]) for x in rows];fc=[min(json.loads(x["distinct_sand_contacts_by_fibre"])) for x in rows];rot=[float(x["maximum_fibre_rotation_deg"]) for x in rows];trans=[float(x["maximum_fibre_translation_over_D50"]) for x in rows]
 a.output_dir.mkdir(parents=True,exist_ok=False);fig,ax=plt.subplots(2,2,figsize=(13,10.0),constrained_layout=True)
 ax[0,0].plot(b,sand,color="#6A3D9A");ax[0,0].axhline(361,color="black",ls="--",lw=1);ax[0,0].set(xlabel="check block",ylabel="sand-sand contacts",title="Sand network recovered")
 ax[0,1].plot(b,fc,color="#E15759");ax[0,1].axhline(3,color="black",ls="--",lw=1);ax[0,1].set(xlabel="check block",ylabel="minimum contacts per fibre",title="No persistent fibre support")
 ax[1,0].plot(b,rot,color="#D95319");ax[1,0].axhline(120,color="black",ls="--",lw=1,label="guard");ax[1,0].set(xlabel="check block",ylabel="maximum rotation (deg)",title="Rapid tumbling after contact onset");ax[1,0].legend(fontsize=8)
 ax[1,1].plot(b,trans,color="#2878B5");ax[1,1].axhline(.75,color="black",ls="--",lw=1,label="guard");ax[1,1].set(xlabel="check block",ylabel="maximum translation / D50",title="Translation remained bounded");ax[1,1].legend(fontsize=8)
 fig.suptitle("Stage26l mobile co-compaction: healthy sand, no persistent fibre cage\nExact geometry; one spent development case; no held-out or flow execution",fontsize=14);image=a.output_dir/"stage26l_mobile_cocompaction_failure.png";fig.savefig(image,dpi=180,facecolor="white");plt.close(fig)
 m={"schema":"lbs.stage26l-mobile-cocompaction-render-manifest.v1","passed":True,"status":"verified_mobile_pilot_failure_render","image":str(image).replace("\\","/"),"image_sha256":sha(image),"source_hashes":{"evaluation":sha(a.evaluation),"history":sha(hp),"renderer":sha(Path(__file__))},"claim_boundary":ev["claim_boundary"]};mp=a.output_dir/"render_manifest.json"
 with mp.open("x",encoding="utf-8",newline="\n") as s:json.dump(m,s,indent=2,sort_keys=True);s.write("\n")
 print(json.dumps({"image":str(image),"image_sha256":sha(image)},sort_keys=True))
if __name__=="__main__":main()
